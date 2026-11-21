#!/usr/bin/env bash
# Turns a working scoreboard Pi into a clean "master" card that can be copied
# for any club. Run it LAST, on a Pi already set up with deploy/pi/setup.sh:
#
#   sudo ./deploy/image/prepare-image.sh            # then it shuts down
#   sudo ./deploy/image/prepare-image.sh --keep-ssh # leave SSH on (for your own boxes)
#
# It removes everything specific to this box: the club's settings, logo,
# sponsors and PIN; saved Wi-Fi networks; SSH keys; logs and history. On the
# next start the box shows "Connect me to Wi-Fi" with its setup hotspot.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run with sudo:  sudo ./deploy/image/prepare-image.sh"
    exit 1
fi
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_USER="$(stat -c %U "$APP_DIR")"
KEEP_SSH=no
[ "${1:-}" = "--keep-ssh" ] && KEEP_SSH=yes

echo "This wipes the club settings, saved Wi-Fi and logs from this box, then shuts it down."
read -r -p "Type YES to carry on: " answer
[ "$answer" = "YES" ] || { echo "Stopped; nothing changed."; exit 1; }

echo "== Latest version"
runuser -u "$APP_USER" -- git -C "$APP_DIR" pull --ff-only --quiet || echo "(couldn't update; carrying on)"

echo "== Club settings, logo, sponsors and PIN"
systemctl stop around-the-grounds-kiosk.service around-the-grounds.service around-the-grounds-wifi.service || true
find "$APP_DIR/data" -mindepth 1 -delete 2>/dev/null || true
cp "$APP_DIR/settings.example.env" "$APP_DIR/settings.env"
chown "$APP_USER": "$APP_DIR/settings.env"

echo "== Saved Wi-Fi networks"
nmcli -t -f NAME,TYPE connection show | awk -F: '$2 == "802-11-wireless" {print $1}' | while read -r name; do
    nmcli connection delete "$name" >/dev/null || true
done

echo "== SSH"
rm -f /etc/ssh/ssh_host_*
if [ "$KEEP_SSH" = yes ]; then
    # New host keys are made on the next start.
    cat > /etc/systemd/system/atg-ssh-keys.service <<'EOF'
[Unit]
Description=Make new SSH host keys on first start
Before=ssh.service
ConditionPathExistsGlob=!/etc/ssh/ssh_host_*_key

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A

[Install]
WantedBy=multi-user.target
EOF
    systemctl enable atg-ssh-keys.service
else
    systemctl disable ssh.service >/dev/null 2>&1 || true
fi
rm -rf "/home/$APP_USER/.ssh/known_hosts"

echo "== Logs and history"
journalctl --rotate >/dev/null 2>&1 || true
journalctl --vacuum-time=1s >/dev/null 2>&1 || true
rm -f /root/.bash_history "/home/$APP_USER/.bash_history"
apt-get clean

echo "== Done. Shutting down: copy the card once the green light stops flashing."
sync
sleep 2
systemctl poweroff
