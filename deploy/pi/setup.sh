#!/usr/bin/env bash
# Around the Grounds: turn a Raspberry Pi (Zero 2 W or better) running
# Raspberry Pi OS Lite into a scoreboard that starts on the TV by itself.
#
# Run from the project folder:   sudo ./deploy/pi/setup.sh
# Safe to run again (e.g. after changing settings.env).
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "Please run with sudo:  sudo ./deploy/pi/setup.sh"
    exit 1
fi

APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_USER="${SUDO_USER:-$(stat -c %U "$APP_DIR")}"
echo "== Around the Grounds: setting up $APP_DIR for user $APP_USER"

echo "== Installing software (this takes a while on a Pi Zero)"
apt-get update
BROWSER_PACKAGE=chromium-browser
apt-cache show chromium-browser >/dev/null 2>&1 || BROWSER_PACKAGE=chromium
apt-get install -y --no-install-recommends \
    python3-flask python3-requests python3-waitress \
    cage "$BROWSER_PACKAGE" fonts-noto-core curl git v4l-utils iw

# The browser needs access to the screen, GPU and keyboard.
usermod -aG video,render,input "$APP_USER"

# A Pi Zero 2 W has 512 MB of memory: a bigger swap file keeps the browser happy.
if [ -f /etc/dphys-swapfile ]; then
    sed -i 's/^#\?CONF_SWAPSIZE=.*/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
    systemctl restart dphys-swapfile || true
fi

# The club's settings, logo and sponsors (made on the setup page) live here.
mkdir -p "$APP_DIR/data"
chown "$APP_USER": "$APP_DIR/data"

# Marks this as a scoreboard box (the setup page then offers Wi-Fi and restarts),
# and lets the scoreboard run its root helper, and nothing else, with sudo.
echo "APP_DIR=$APP_DIR" > /etc/around-the-grounds.conf
echo "$APP_USER ALL=(root) NOPASSWD: $APP_DIR/deploy/pi/admin.sh" > /etc/sudoers.d/around-the-grounds
chmod 440 /etc/sudoers.d/around-the-grounds
visudo -cf /etc/sudoers.d/around-the-grounds >/dev/null

if [ ! -f "$APP_DIR/settings.env" ]; then
    cp "$APP_DIR/settings.example.env" "$APP_DIR/settings.env"
    chown "$APP_USER": "$APP_DIR/settings.env"
fi
chmod +x "$APP_DIR/deploy/pi/"*.sh

echo "== The scoreboard web server"
cat > /etc/systemd/system/around-the-grounds.service <<EOF
[Unit]
Description=Around the Grounds scoreboard
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=-$APP_DIR/settings.env
ExecStart=/usr/bin/python3 $APP_DIR/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "== The full-screen browser on the TV"
cat > /etc/pam.d/around-the-grounds-kiosk <<'EOF'
auth     required pam_unix.so nullok
account  required pam_unix.so
session  required pam_unix.so
session  required pam_systemd.so
EOF
cat > /etc/systemd/system/around-the-grounds-kiosk.service <<EOF
[Unit]
Description=Around the Grounds kiosk (full-screen browser on the TV)
After=systemd-user-sessions.service around-the-grounds.service
Wants=around-the-grounds.service
Conflicts=getty@tty1.service

[Service]
User=$APP_USER
PAMName=around-the-grounds-kiosk
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes
TTYVTDisallocate=yes
StandardInput=tty-fail
UtmpIdentifier=tty1
UtmpMode=user
EnvironmentFile=-$APP_DIR/settings.env
ExecStart=$APP_DIR/deploy/pi/kiosk.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "== Wi-Fi watcher (opens a setup hotspot when there's no Wi-Fi)"
cat > /etc/systemd/system/around-the-grounds-wifi.service <<EOF
[Unit]
Description=Around the Grounds Wi-Fi watcher and setup hotspot
After=NetworkManager.service
Wants=NetworkManager.service

[Service]
EnvironmentFile=-$APP_DIR/settings.env
ExecStart=$APP_DIR/deploy/pi/wifi-check.sh watch
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

echo "== TV remote (HDMI-CEC: Samsung Anynet+)"
cat > /etc/systemd/system/around-the-grounds-remote.service <<EOF
[Unit]
Description=Around the Grounds TV remote (HDMI-CEC)
After=around-the-grounds.service
Wants=around-the-grounds.service

[Service]
EnvironmentFile=-$APP_DIR/settings.env
ExecStart=/usr/bin/python3 $APP_DIR/deploy/pi/cec_remote.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

echo "== Automatic updates (daily at 5 am, and shortly after each start)"
cat > /etc/systemd/system/around-the-grounds-update.service <<EOF
[Unit]
Description=Update Around the Grounds from GitHub
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$APP_DIR/deploy/pi/update.sh
EOF
cat > /etc/systemd/system/around-the-grounds-update.timer <<'EOF'
[Unit]
Description=Update Around the Grounds daily

[Timer]
OnBootSec=5min
OnCalendar=*-*-* 05:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "== Optional: TV on and off by the clock (edit to turn on)"
if [ ! -f /etc/cron.d/around-the-grounds-tv ]; then
    cat > /etc/cron.d/around-the-grounds-tv <<'EOF'
# Turn the TV on and off through HDMI-CEC (Samsung: turn on Anynet+ in the TV's settings).
# Remove the # at the start of both lines below to use them; times are 24-hour.
# 0 9  * * * root cec-ctl -d /dev/cec0 --playback >/dev/null && cec-ctl -d /dev/cec0 --to 0 --image-view-on
# 0 22 * * * root cec-ctl -d /dev/cec0 --playback >/dev/null && cec-ctl -d /dev/cec0 --to 0 --standby
EOF
fi

systemctl daemon-reload
systemctl disable getty@tty1.service >/dev/null 2>&1 || true
systemctl enable around-the-grounds.service around-the-grounds-kiosk.service around-the-grounds-wifi.service \
    around-the-grounds-remote.service around-the-grounds-update.timer
systemctl restart around-the-grounds.service
systemctl restart around-the-grounds-kiosk.service || true
systemctl restart around-the-grounds-wifi.service
systemctl restart around-the-grounds-remote.service || true
systemctl start around-the-grounds-update.timer

echo
echo "== Done. The scoreboard should now be on the TV, asking to be set up."
echo "   Restart the Pi any time with:  sudo reboot"
PORT="$(sed -n 's/^ATG_PORT=//p' "$APP_DIR/settings.env")"
echo "   Set it up from a phone or laptop on the same Wi-Fi:  http://$(hostname).local:${PORT:-8080}/setup"
