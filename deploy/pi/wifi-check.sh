#!/usr/bin/env bash
# Keeps the scoreboard online. If there's no network a minute or so after
# start-up, it opens a setup hotspot so a phone can connect and choose the
# club's Wi-Fi (the TV shows the hotspot's name and password). While the
# hotspot is on, it retries the saved networks every 10 minutes, unless a
# phone is connected to the hotspot.
#
#   wifi-check.sh                  watch (run by the around-the-grounds-wifi service)
#   wifi-check.sh start-hotspot    open the setup hotspot now
#   wifi-check.sh stop-hotspot     close it
set -u
STATE_DIR=/run/around-the-grounds
SSID="${ATG_HOTSPOT_SSID:-AroundTheGrounds-Setup}"
PASSWORD="${ATG_HOTSPOT_PASSWORD:-scoreboard}"   # Wi-Fi passwords need at least 8 characters
HOTSPOT=atg-setup

mkdir -p "$STATE_DIR"
chmod 755 "$STATE_DIR"

online() {
    nmcli -t -f TYPE,STATE dev 2>/dev/null | grep -Eq '^(wifi|ethernet):connected$'
}

hotspot_on() {
    [ -f "$STATE_DIR/hotspot.json" ]
}

start_hotspot() {
    # Remember the networks in range first: the Wi-Fi can't scan while it's a hotspot.
    nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list --rescan yes > "$STATE_DIR/wifi-scan.txt" 2>/dev/null || true
    chmod 644 "$STATE_DIR/wifi-scan.txt"
    nmcli connection delete "$HOTSPOT" >/dev/null 2>&1
    if nmcli dev wifi hotspot ifname wlan0 con-name "$HOTSPOT" ssid "$SSID" password "$PASSWORD" >/dev/null; then
        printf '{"ssid": "%s", "password": "%s", "address": "10.42.0.1"}\n' "$SSID" "$PASSWORD" > "$STATE_DIR/hotspot.json"
        chmod 644 "$STATE_DIR/hotspot.json"
        echo "Setup hotspot $SSID is on."
    fi
}

stop_hotspot() {
    nmcli connection down "$HOTSPOT" >/dev/null 2>&1
    nmcli connection delete "$HOTSPOT" >/dev/null 2>&1
    rm -f "$STATE_DIR/hotspot.json"
}

phone_on_hotspot() {
    [ -n "$(iw dev wlan0 station dump 2>/dev/null)" ]
}

try_saved_networks() {
    stop_hotspot
    for _ in $(seq 1 30); do
        online && return 0
        sleep 2
    done
    return 1
}

case "${1:-watch}" in
    start-hotspot) start_hotspot ;;
    stop-hotspot) stop_hotspot ;;
    watch)
        # A ready-for-a-club card may carry the club's Wi-Fi details.
        python3 "$(dirname "$0")/provision_wifi.py" || true
        stop_hotspot
        for _ in $(seq 1 45); do
            online && break
            sleep 2
        done
        while true; do
            if ! online && ! hotspot_on; then
                start_hotspot
            elif hotspot_on && ! phone_on_hotspot && nmcli -t -f NAME,TYPE connection show | grep -v "^$HOTSPOT:" | grep -q ':802-11-wireless$'; then
                # A saved network might be back: try it, and reopen the hotspot if not.
                try_saved_networks || start_hotspot
            fi
            sleep 600
        done
        ;;
esac
