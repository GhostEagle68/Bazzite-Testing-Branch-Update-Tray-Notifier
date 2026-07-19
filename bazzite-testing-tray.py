#!/usr/bin/env python3
"""
bazzite-testing-tray.py

Persistent system tray icon that watches ublue-os/bazzite's GitHub releases
for new "testing" branch builds (tags like testing-44.20260715) and lets you
open the release page from the tray menu.

Replaces bazzite-testing-tray.sh (yad-based). That version's --notification
tray mode is built on the deprecated GtkStatusIcon API and its click/menu
handling silently breaks under KDE Plasma Wayland (menu never appears, no
error output — see v1cont/yad#52 for a related but not identical symptom).

This version uses AppIndicator3 (a StatusNotifierItem), which is the tray
mechanism KDE and GNOME actually expect natively on Wayland. No GDK_BACKEND=x11
shim required.

Dependencies (install with pacman inside the Arch distrobox):
    sudo pacman -S python-gobject gtk3 python-cairo libayatana-appindicator
If libayatana-appindicator isn't in your repos, the AUR package
libappindicator-gtk3 is the fallback (yay -S libappindicator-gtk3).
python-cairo is needed for the round badge on the "new release" icon.

Run directly in the foreground to test: ./bazzite-testing-tray.py
"""

import gi

gi.require_version("Gtk", "3.0")
try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3

from gi.repository import Gtk, GLib, GdkPixbuf, Gdk
import cairo

import json
import math
import os
import subprocess
import sys
import threading
import urllib.error
import urllib.request

REPO = "ublue-os/bazzite"
STATE_FILE = os.path.expanduser("~/.cache/bazzite-testing-latest-tag")
SEEN_FILE = os.path.expanduser("~/.cache/bazzite-testing-acked-tag")
API_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=10"
CHECK_INTERVAL_SECS = int(os.environ.get("CHECK_INTERVAL_SECS", "3600"))  # 1 hour default
RETRY_INTERVAL_SECS = 60  # first retry after a failed check, e.g. network not up yet at login
                          # (doubles per consecutive failure, capped at CHECK_INTERVAL_SECS,
                          # so a persistent outage can't hammer GitHub's 60 req/hr limit)

ICON_IDLE = "bazzite-logo-icon"    # "up to date" / checking
ICON_NEW = "bazzite-logo"          # new release flagged (overwritten by
                                   # build_badged_icon() if compositing works)

BADGE_ICON_NAME = "bazzite-testing-notifier-update"
BADGE_ICON_SIZE = 128
BADGE_ICON_DIR = os.path.expanduser(
    f"~/.local/share/icons/hicolor/{BADGE_ICON_SIZE}x{BADGE_ICON_SIZE}/apps"
)
BADGE_ICON_PATH = os.path.join(BADGE_ICON_DIR, BADGE_ICON_NAME + ".png")

APP_ID = "bazzite-testing-notifier"


def find_icon_file(name):
    """
    Locate a raster icon file directly on disk, bypassing GTK's icon theme
    lookup entirely. Bazzite's own branding icons (bazzite-logo-icon etc.)
    are dropped straight into hicolor/<size>/<name>.png with no apps/places
    context subdirectory -- non-standard placement that GTK's strict
    Gtk.IconTheme lookup won't find (even though KDE's own icon resolution,
    used when the tray icon name is sent over D-Bus, is more lenient and
    displays it fine). So for our own compositing we search for the file
    ourselves and pick the largest size available.
    """
    search_roots = [
        "/usr/share/icons/hicolor",
        os.path.expanduser("~/.local/share/icons/hicolor"),
    ]
    candidates = []
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for size_dir in os.listdir(root):
            size_path = os.path.join(root, size_dir)
            if not os.path.isdir(size_path):
                continue
            direct = os.path.join(size_path, f"{name}.png")
            if os.path.isfile(direct):
                candidates.append((size_dir, direct))
            for context in ("apps", "places", "status", "categories", "devices"):
                std_path = os.path.join(size_path, context, f"{name}.png")
                if os.path.isfile(std_path):
                    candidates.append((size_dir, std_path))

    if not candidates:
        return None

    def size_key(item):
        try:
            return int(item[0].split("x")[0])
        except (ValueError, IndexError):
            return 0

    candidates.sort(key=size_key, reverse=True)
    return candidates[0][1]


def build_badged_icon():
    """
    Compose a small red badge onto the bottom-right corner of the Bazzite
    logo, so "update available" is visible at a glance instead of relying on
    people noticing the icon itself changed.

    Falls back to the plain "bazzite-logo" icon name if the base icon can't
    be found at all -- e.g. while testing inside the Arch container, where
    /usr/share/icons is the container's own filesystem, not the host's.
    """
    if os.path.exists(BADGE_ICON_PATH):
        return BADGE_ICON_NAME

    theme = Gtk.IconTheme.get_default()
    try:
        # Debug/testing hook: point at a manually-copied base icon file when
        # the real one isn't reachable (e.g. testing inside the Arch
        # container). Not used in normal operation.
        icon_path = os.environ.get("BAZZITE_TRAY_BASE_ICON_PATH") or find_icon_file(ICON_IDLE)
        if icon_path:
            base = GdkPixbuf.Pixbuf.new_from_file_at_size(
                icon_path, BADGE_ICON_SIZE, BADGE_ICON_SIZE
            )
        else:
            base = theme.load_icon(ICON_IDLE, BADGE_ICON_SIZE, 0)
        if base is None:
            raise ValueError("base icon not found")

        # Draw the base icon onto a cairo surface, then draw a round red dot
        # (with a thin white ring for contrast against light/dark themes)
        # over it -- GdkPixbuf alone can only stamp rectangles, so this needs
        # actual drawing.
        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, BADGE_ICON_SIZE, BADGE_ICON_SIZE
        )
        ctx = cairo.Context(surface)
        Gdk.cairo_set_source_pixbuf(ctx, base, 0, 0)
        ctx.paint()

        radius = BADGE_ICON_SIZE * 0.20
        inset = BADGE_ICON_SIZE * 0.06
        cx = cy = BADGE_ICON_SIZE - radius - inset

        ctx.set_line_width(BADGE_ICON_SIZE * 0.025)
        ctx.arc(cx, cy, radius, 0, 2 * math.pi)
        ctx.set_source_rgba(1, 1, 1, 1)  # white ring for contrast
        ctx.stroke_preserve()
        ctx.set_source_rgba(0.86, 0.15, 0.15, 1.0)  # solid red (#DC2626)
        ctx.fill()

        composed = Gdk.pixbuf_get_from_surface(
            surface, 0, 0, BADGE_ICON_SIZE, BADGE_ICON_SIZE
        )

        os.makedirs(BADGE_ICON_DIR, exist_ok=True)
        composed.savev(BADGE_ICON_PATH, "png", [], [])
        theme.rescan_if_needed()
        return BADGE_ICON_NAME
    except Exception:
        import traceback
        print("build_badged_icon() failed, falling back to plain logo:", file=sys.stderr)
        traceback.print_exc()
        return "bazzite-logo"


def release_url_for_tag(tag):
    return f"https://github.com/{REPO}/releases/tag/{tag}"


def get_current_system_version():
    """
    Return the currently booted rpm-ostree version string, e.g.
    'testing-44.20260715' -- rpm-ostree reports the full release tag as-is
    in its "version" field, so this is compared directly against the GitHub
    tag name, no prefix stripping needed.

    Returns None if it can't be determined.

    Tries a direct rpm-ostree call first (works once this runs natively on the
    Bazzite host), then falls back to distrobox-host-exec, which runs the
    command on the host from inside the Arch container — this is how we check
    real system state during dev/testing without rpm-ostree being installed
    in the container itself.
    """
    candidates = [
        ["rpm-ostree", "status", "--json"],
        ["distrobox-host-exec", "rpm-ostree", "status", "--json"],
    ]
    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=15
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        if result.returncode != 0 or not result.stdout.strip():
            continue
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            continue
        for deployment in data.get("deployments", []):
            if deployment.get("booted"):
                return deployment.get("version")
    return None


class TrayApp:
    def __init__(self):
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

        self.indicator = AppIndicator3.Indicator.new(
            APP_ID, ICON_IDLE, AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_title("Bazzite Testing Notifier — starting...")

        self.menu = Gtk.Menu()
        self._rebuild_menu(label="Checking...", tag=None, clickable=False)
        self.indicator.set_menu(self.menu)

        self.stop_event = threading.Event()
        self.wake_event = threading.Event()  # set by "Check now" to skip the wait
        self.manual_check = False  # next check was user-requested -> notify result
        self.poll_thread = threading.Thread(target=self.poll_loop, daemon=True)
        self.poll_thread.start()

    # -- menu construction -------------------------------------------------

    def _rebuild_menu(self, label, tag, clickable):
        for child in self.menu.get_children():
            self.menu.remove(child)

        status_item = Gtk.MenuItem(label=label)
        if clickable and tag is not None:
            status_item.connect("activate", self.on_open_release, tag)
        else:
            status_item.set_sensitive(False)
        self.menu.append(status_item)

        self.menu.append(Gtk.SeparatorMenuItem())

        check_item = Gtk.MenuItem(label="Check now")
        check_item.connect("activate", self.on_check_now)
        self.menu.append(check_item)

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.on_quit)
        self.menu.append(quit_item)

        self.menu.show_all()

    # -- actions -------------------------------------------------------------

    def on_quit(self, _item):
        self.stop_event.set()
        self.wake_event.set()
        Gtk.main_quit()

    def on_check_now(self, _item):
        self.indicator.set_title("Bazzite Testing Notifier — checking...")
        self._rebuild_menu("Checking...", tag=None, clickable=False)
        self.manual_check = True
        self.wake_event.set()

    def on_open_release(self, _item, tag):
        subprocess.Popen(["xdg-open", release_url_for_tag(tag)])
        # Manual fallback only: used when we can't read the actual booted
        # system version (see check_for_update). When rpm-ostree status is
        # readable, "up to date" is driven by the real installed version
        # instead, so opening the page doesn't fake an update having happened.
        with open(SEEN_FILE, "w") as f:
            f.write(tag)

    # -- polling ---------------------------------------------------------

    def check_for_update(self):
        # Consume the manual flag up front: only a user-clicked "Check now"
        # gets a desktop notification with the result, hourly polls stay quiet.
        manual = self.manual_check
        self.manual_check = False

        req = urllib.request.Request(
            API_URL, headers={"User-Agent": "bazzite-testing-notifier"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                releases = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, OSError):
            GLib.idle_add(self.set_error_state, manual)
            return False

        latest_testing_tag = next(
            (r.get("tag_name", "") for r in releases
             if r.get("tag_name", "").startswith("testing-")),
            None,
        )

        if not latest_testing_tag:
            GLib.idle_add(self.set_error_state, manual)
            return False

        # Debug/testing hook: force a fake "latest" tag so the new-release
        # icon/menu can be exercised without waiting for (or faking) an
        # actual pending update. Not used in normal operation.
        latest_testing_tag = os.environ.get(
            "BAZZITE_TRAY_TEST_TAG", latest_testing_tag
        )

        with open(STATE_FILE, "w") as f:
            f.write(latest_testing_tag)

        current_version = get_current_system_version()

        if current_version is not None:
            # Authoritative: are we actually booted into this build?
            is_new = current_version != latest_testing_tag
        else:
            # Fallback when rpm-ostree status isn't reachable at all: fall
            # back to "did the user click through to this tag before".
            acked = ""
            if os.path.exists(SEEN_FILE):
                with open(SEEN_FILE) as f:
                    acked = f.read().strip()
            is_new = latest_testing_tag != acked

        GLib.idle_add(self.set_update_state, latest_testing_tag, is_new, manual)
        return True

    def poll_loop(self):
        failures = 0
        while not self.stop_event.is_set():
            ok = self.check_for_update()
            if ok:
                failures = 0
                wait_secs = CHECK_INTERVAL_SECS
            else:
                failures += 1
                wait_secs = min(
                    RETRY_INTERVAL_SECS * 2 ** (failures - 1), CHECK_INTERVAL_SECS
                )
                print(
                    f"check failed ({failures} in a row), retrying in {wait_secs}s",
                    file=sys.stderr,
                )
            self.wake_event.wait(wait_secs)
            self.wake_event.clear()

    # -- state transitions (must run on the GTK main thread) ----------------

    def _notify(self, message):
        try:
            subprocess.Popen(
                ["notify-send", "--app-name=Bazzite Testing Notifier",
                 f"--icon={ICON_IDLE}", "Bazzite Testing Notifier", message]
            )
        except OSError:
            pass  # notify-send missing -- the menu/title still show the state

    def set_error_state(self, manual=False):
        self.indicator.set_title("Bazzite Testing Notifier — check failed (network?)")
        self._rebuild_menu("Check failed, retrying...", tag=None, clickable=False)
        if manual:
            self._notify("Check failed (network?) — will retry.")
        return False

    def set_update_state(self, tag, is_new, manual=False):
        icon = ICON_NEW if is_new else ICON_IDLE
        self.indicator.set_icon_full(icon, "Bazzite Testing Notifier")
        if is_new:
            self.indicator.set_title(f"Bazzite Testing Notifier — new release: {tag}")
            self._rebuild_menu(f"New: {tag}", tag, clickable=True)
        else:
            self.indicator.set_title(f"Bazzite Testing Notifier — up to date ({tag})")
            self._rebuild_menu(f"Up to date: {tag}", tag, clickable=True)
        if manual:
            self._notify(f"New release: {tag}" if is_new else f"Up to date ({tag})")
        return False


def main():
    global ICON_NEW
    ICON_NEW = build_badged_icon()
    TrayApp()
    Gtk.main()


if __name__ == "__main__":
    main()
