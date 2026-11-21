#!/usr/bin/env bash
# Started by the kiosk service: waits for the scoreboard, then shows it full
# screen on the TV (cage is a minimal full-screen window manager).
PORT="${ATG_PORT:-8080}"
URL="http://127.0.0.1:${PORT}/"

# Say something on the TV while the browser starts (it takes a minute or so
# on a Pi), so a dark screen doesn't look like a fault.
TTY=/dev/tty1
if [ -w "$TTY" ]; then
    setfont /usr/share/consolefonts/Uni3-TerminusBold32x16.psf.gz -C "$TTY" 2>/dev/null || true
    printf '\033[2J\033[H\033[?25l\n\n\n     Around the Grounds is starting...\n\n     The scoreboard appears in about a minute.\n' > "$TTY"
fi

for _ in $(seq 1 90); do
    curl -sf "${URL}health" >/dev/null && break
    sleep 2
done

BROWSER="$(command -v chromium-browser || command -v chromium)"
cage -s -- "$BROWSER" \
    --kiosk --start-fullscreen --incognito \
    --noerrdialogs --disable-infobars --no-first-run --disable-session-crashed-bubble \
    --disable-translate --disable-features=Translate,TranslateUI \
    --disable-extensions --renderer-process-limit=1 --disk-cache-size=1048576 \
    --password-store=basic --check-for-update-interval=31536000 \
    --ozone-platform=wayland \
    "$URL"
status=$?

# The browser closed or couldn't start: say so on the TV (the service restarts it).
if [ -w "$TTY" ]; then
    printf '\033[2J\033[H\n\n\n     The scoreboard screen stopped (code %s).\n\n     Restarting it now...\n\n     If this keeps happening:  journalctl -u around-the-grounds-kiosk -n 40\n' "$status" > "$TTY"
fi
sleep 5
exit "$status"
