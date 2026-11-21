"""Around the Grounds web server.

    python server.py            # then open http://localhost:8080

/        the full-screen scoreboard (for the TV)
/board   the current pages as JSON (the scoreboard asks for this every minute)
/health  "ok" (the Pi's kiosk waits for this before opening the browser)
"""

from flask import Flask, jsonify, make_response

import config
import scores
import screen

app = Flask(__name__)


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def scoreboard():
    return _no_store(make_response(screen.render_page()))


@app.get("/board")
def board():
    result = scores.live_board()
    playing = sum(1 for g in result.get("games") or [] if g["state"] == "live")
    return _no_store(jsonify({
        "html": screen.render_board(result),
        "checked": result.get("checked", ""),
        "error": result.get("error"),
        "playing": playing,
    }))


@app.get("/health")
def health():
    return "ok"


def main():
    try:
        from waitress import serve  # a proper server when it's installed (it is on the Pi)
    except ImportError:
        app.run(host=config.HOST, port=config.PORT, threaded=True)
    else:
        print(f"Around the Grounds on http://{config.HOST}:{config.PORT}")
        serve(app, host=config.HOST, port=config.PORT, threads=4)


if __name__ == "__main__":
    main()
