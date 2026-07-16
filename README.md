# Bazzite Testing Notifier

A small system tray icon for [Bazzite](https://bazzite.gg) that watches
[ublue-os/bazzite](https://github.com/ublue-os/bazzite) releases for new
`testing` branch builds (tags like `testing-44.20260715`), so you don't have
to keep checking the GitHub releases page by hand.

## What it does

- Polls the GitHub API hourly for the latest `testing-*` release tag.
- Compares that tag against the version your system is actually booted into
  (via `rpm-ostree status`), so "up to date" reflects reality rather than
  just whether you clicked the link before.
- Shows a Bazzite-branded tray icon with the current status, and a menu item
  that opens the matching GitHub release page.
- Runs as a systemd user service, so it keeps checking in the background
  across logins and reboots.

## Requirements

This is Bazzite-specific — it checks your actual booted `rpm-ostree`
version against ublue-os/bazzite's releases, so it only makes sense on
Bazzite itself. Needs PyGObject/GTK3 bindings, cairo bindings (for drawing
the "new release" badge), and libayatana-appindicator (the tray icon
library). Bazzite's base image already ships most of these —
`libayatana-appindicator` is usually the only one actually missing.

**Check what's already installed** (on the Bazzite host):

```
rpm -q python3-gobject python3-cairo gtk3 libayatana-appindicator-gtk3
```

Anything printed as "not installed" needs installing.

**Install, without a reboot** — `--apply-live` patches the package into the
running system immediately, while still layering it permanently so it
survives future updates:

```
sudo rpm-ostree install --apply-live python3-gobject python3-cairo gtk3 libayatana-appindicator-gtk3
```

## Install

```
git clone https://github.com/GhostEagle68/bazzite-testing-notifier.git
cd bazzite-testing-notifier
./install.sh
```

This copies `bazzite-testing-tray.py` to `~/.local/bin`, installs the
systemd user service to `~/.config/systemd/user`, and enables it.

## Files

- `bazzite-testing-tray.py` — the tray application itself
- `bazzite-testing-tray.service` — systemd user service definition
- `install.sh` — installer

## Development / testing hooks

A couple of environment variables exist purely for testing without waiting
on (or faking) a real pending update:

- `BAZZITE_TRAY_TEST_TAG=testing-99.99999999` — pretends this is the latest
  GitHub release tag, to exercise the "new release" state.
- `BAZZITE_TRAY_BASE_ICON_PATH=/path/to/icon.png` — overrides where the base
  icon is loaded from when compositing the "new release" badge (useful if
  testing somewhere `/usr/share/icons` isn't the real host filesystem, e.g.
  inside a distrobox container).
- `CHECK_INTERVAL_SECS=30` — overrides the hourly poll interval.

## Disclaimer

This project was built collaboratively with Claude (Anthropic's AI),
working as a coworker in Cowork mode — from diagnosing the original yad/
Wayland tray bug, to rewriting the tray as an AppIndicator3 app, to sorting
out rpm-ostree version detection and icon theming. 🤖
