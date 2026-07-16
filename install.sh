#!/usr/bin/env bash
# Installs the bazzite-testing-notifier tray icon daemon and systemd service.
# Run this from inside the extracted bazzite-testing-notifier directory.
#
# This is the tray-icon version. If you previously installed the old
# timer-based (auto-popup) version, this will disable that first.
set -euo pipefail

mkdir -p "$HOME/.local/bin" "$HOME/.config/systemd/user"

# Disable old timer-based install if present, to avoid double-checking
if systemctl --user is-enabled bazzite-testing-notify.timer &>/dev/null; then
  echo "Disabling old timer-based notifier..."
  systemctl --user disable --now bazzite-testing-notify.timer || true
fi

cp bazzite-testing-tray.py "$HOME/.local/bin/"
chmod +x "$HOME/.local/bin/bazzite-testing-tray.py"

cp bazzite-testing-tray.service "$HOME/.config/systemd/user/"

systemctl --user daemon-reload
systemctl --user enable --now bazzite-testing-tray.service

echo "Installed. Service status:"
systemctl --user status bazzite-testing-tray.service --no-pager
