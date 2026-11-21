#!/usr/bin/env bash
# Started by the kiosk service: waits for the scoreboard, then shows it full
# screen on the TV (cage is a minimal full-screen window manager).
PORT="${ATG_PORT:-8080}"
URL="http://127.0.0.1:${PORT}/"

for _ in $(seq 1 90); do
    curl -sf "${URL}health" >/dev/null && break
    sleep 2
done

BROWSER="$(command -v chromium-browser || command -v chromium)"
exec cage -s -- "$BROWSER" \
    --kiosk --start-fullscreen --incognito \
    --noerrdialogs --disable-infobars --no-first-run --disable-session-crashed-bubble \
    --disable-translate --disable-features=Translate,TranslateUI \
    --disable-extensions --renderer-process-limit=1 --disk-cache-size=1048576 \
    --password-store=basic --check-for-update-interval=31536000 \
    --ozone-platform=wayland \
    "$URL"
