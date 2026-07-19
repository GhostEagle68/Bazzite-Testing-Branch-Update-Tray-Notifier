#!/usr/bin/env bash
# Removes everything install.sh set up: the systemd user service, the script
# in ~/.local/bin, plus the badge icon and state files the app created at
# runtime. Safe to re-run; each step is skipped if already gone.
set -euo pipefail

# Unconditional (not guarded by is-enabled): also catches a service that is
# running but not enabled, which would otherwise survive its unit file.
echo "Stopping and disabling service..."
systemctl --user disable --now bazzite-testing-tray.service 2>/dev/null || true

rm -f "$HOME/.config/systemd/user/bazzite-testing-tray.service"
systemctl --user daemon-reload

rm -f "$HOME/.local/bin/bazzite-testing-tray.py"

# Runtime artifacts: composited badge icon and state files
rm -f "$HOME/.local/share/icons/hicolor/128x128/apps/bazzite-testing-notifier-update.png"
rm -f "$HOME/.cache/bazzite-testing-latest-tag" "$HOME/.cache/bazzite-testing-acked-tag"

echo "Uninstalled."
