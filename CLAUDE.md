# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single-file Python system tray app for Bazzite Linux. It polls the GitHub
API for new `ublue-os/bazzite` `testing-*` release tags and shows an
AppIndicator3 tray icon reflecting whether the system is up to date, with a
menu item to open the matching GitHub release page. Runs as a systemd user
service (`bazzite-testing-tray.service`).

The entire application is `bazzite-testing-tray.py` — there is no build step,
package manager, or test suite. `install.sh` copies the script and service
file into place and enables the systemd unit.

## Running / testing

Run directly in the foreground (no install needed):

```
./bazzite-testing-tray.py
```

Useful env vars for exercising states without waiting on a real release or
faking GitHub data:

- `BAZZITE_TRAY_TEST_TAG=testing-99.99999999` — pretends this is the latest
  GitHub release tag, to force the "new release" state.
- `BAZZITE_TRAY_BASE_ICON_PATH=/path/to/icon.png` — overrides where the base
  icon is loaded from when compositing the badge (needed when testing inside
  a distrobox container, where `/usr/share/icons` is the container's own
  filesystem, not the host's).
- `CHECK_INTERVAL_SECS=30` — overrides the hourly poll interval for faster
  iteration.

There is no lint/test/build command — verify changes by running the script
in the foreground and observing tray/menu behavior, ideally with the env
vars above to hit both the "up to date" and "new release" code paths.

Dependencies: PyGObject/GTK3, cairo bindings, and libayatana-appindicator
(see README.md for install commands — `rpm-ostree install --apply-live ...`
on Bazzite itself).

## Architecture notes

- **Tray backend**: uses `AyatanaAppIndicator3` (falling back to
  `AppIndicator3`) rather than the older `GtkStatusIcon`. This is a deliberate
  replacement for a prior yad-based script whose tray mode broke silently
  under KDE Plasma Wayland — see the module docstring for context. Don't
  reintroduce `GtkStatusIcon` or a yad-based approach.
  - Foreground runs print `libayatana-appindicator is deprecated. Please use
    libayatana-appindicator-glib in newly written code.` This is harmless and
    expected: as of Fedora 44, `libayatana-appindicator-glib` is not packaged
    at all, so there is nothing to migrate to yet. Don't try to suppress it.
    When Fedora ships the glib variant, port by adding its namespace as a
    third candidate in the existing `gi.require_version` try/except fallback
    chain (the API is near-identical).
- **Version-of-truth for "is an update pending"**: `get_current_system_version()`
  shells out to `rpm-ostree status --json` (or `distrobox-host-exec rpm-ostree
  status --json` as a container-dev fallback) to read the actually-booted
  deployment's version, and compares it directly against the GitHub tag name
  (no prefix stripping — rpm-ostree reports the full tag as-is). Only when
  that fails entirely does the app fall back to a weaker heuristic: comparing
  against the last tag the user manually clicked through to (persisted in
  `~/.cache/bazzite-testing-acked-tag`). Keep this priority order — the
  rpm-ostree check is authoritative, the "acked tag" file is a degraded
  fallback, not a parallel source of truth.
- **Icon badge compositing**: `build_badged_icon()` draws a red dot onto the
  base Bazzite logo using cairo (GdkPixbuf alone can't draw circles) and
  caches the composed PNG under
  `~/.local/share/icons/hicolor/128x128/apps/`. `find_icon_file()` exists
  because Bazzite's branding icons live directly under `hicolor/<size>/` with
  no `apps/`/`places/` context subdirectory, which GTK's own strict
  `Gtk.IconTheme` lookup won't find (KDE's D-Bus-based tray icon resolution is
  more lenient and finds them fine) — so icon *file* lookup for compositing is
  done manually, separately from the icon *name* handed to AppIndicator3.
- **Threading**: polling runs on a background daemon thread
  (`poll_loop`/`check_for_update`); all GTK/indicator state mutations from
  that thread are marshalled back to the main thread via `GLib.idle_add`
  (`set_error_state`, `set_update_state`). Don't touch `Gtk`/`indicator` APIs
  directly from the poll thread.
- State files live in `~/.cache/`: `bazzite-testing-latest-tag` (last seen
  latest tag) and `bazzite-testing-acked-tag` (last tag the user opened,
  used only in the rpm-ostree-unavailable fallback path).

## Workflow (see CONTRIBUTING.md for full detail)

- Work happens on `dev`; PRs merge into `main` via squash merge. Nothing is
  pushed directly to `main`.
- Releases are tagged from `main` with `gh release create vX.Y.Z
  --generate-notes` — notes are auto-generated from PR/commit titles, so
  there's no changelog file to maintain by hand; write clear PR titles.
