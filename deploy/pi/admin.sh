#!/usr/bin/env bash
# Root jobs the setup page may ask for. setup.sh lets the scoreboard run this
# (and only this) with sudo:  admin.sh wifi SSID PASSWORD | update | restart | reboot
set -u
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PI="$APP_DIR/deploy/pi"

case "${1:-}" in
    wifi)
        ssid="${2:-}"
        password="${3:-}"
        [ -n "$ssid" ] || exit 1
        sleep 3   # let the setup page answer before the network changes
        "$PI/wifi-check.sh" stop-hotspot
        nmcli dev wifi rescan >/dev/null 2>&1
        sleep 5
        if [ -n "$password" ]; then
            nmcli dev wifi connect "$ssid" password "$password" ifname wlan0
        else
            nmcli dev wifi connect "$ssid" ifname wlan0
        fi || "$PI/wifi-check.sh" start-hotspot   # didn't work: back to the setup hotspot
        ;;
    update)
        "$PI/update.sh"
        ;;
    restart)
        systemctl restart around-the-grounds-kiosk.service
        ;;
    reboot)
        sleep 2
        systemctl reboot
        ;;
    *)
        echo "usage: admin.sh wifi SSID PASSWORD | update | restart | reboot"
        exit 1
        ;;
esac
