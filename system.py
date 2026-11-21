"""The Raspberry Pi side: Wi-Fi, the setup hotspot, updates and restarts.

The root-only jobs go through deploy/pi/admin.sh, which setup.sh allows the
scoreboard to run with sudo. On a laptop none of this is available and the
setup page simply leaves those sections out.
"""

import json
import shutil
import socket
import subprocess
from pathlib import Path

import config

STATE_DIR = Path("/run/around-the-grounds")
HOTSPOT_FILE = STATE_DIR / "hotspot.json"     # written by wifi-check.sh while the hotspot is on
SCAN_FILE = STATE_DIR / "wifi-scan.txt"       # networks seen just before the hotspot started
MARKER = Path("/etc/around-the-grounds.conf")  # written by setup.sh
ADMIN = config.ROOT / "deploy" / "pi" / "admin.sh"


def on_pi():
    return MARKER.exists() and shutil.which("nmcli") is not None


def hotspot():
    """{"ssid", "password", "address"} while the setup hotspot is on, else None."""
    try:
        return json.loads(HOTSPOT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def addresses():
    """Ways to reach this box from another device on the same network."""
    found = []
    host = socket.gethostname()
    if host:
        found.append(f"{host}.local")
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))  # no traffic is sent; this just picks the network's own address
        found.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass
    return found


def _nmcli_fields(line):
    """nmcli -t output: fields split on ':' with '\\:' meaning a real colon."""
    fields, current, escaped = [], "", False
    for char in line:
        if escaped:
            current, escaped = current + char, False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append(current)
            current = ""
        else:
            current += char
    return fields + [current]


def wifi_networks():
    """[{"ssid", "signal", "secure"}], strongest first."""
    if not on_pi():
        return []
    text = ""
    if hotspot() and SCAN_FILE.exists():
        text = SCAN_FILE.read_text(encoding="utf-8", errors="replace")
    else:
        try:
            text = subprocess.run(["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "dev", "wifi", "list"],
                                  capture_output=True, text=True, timeout=20).stdout
        except (OSError, subprocess.SubprocessError):
            return []
    best = {}
    for line in text.splitlines():
        fields = _nmcli_fields(line)
        if len(fields) < 3 or not fields[0]:
            continue
        try:
            signal = int(fields[1])
        except ValueError:
            signal = 0
        if fields[0] not in best or signal > best[fields[0]]["signal"]:
            best[fields[0]] = {"ssid": fields[0], "signal": signal, "secure": fields[2] not in ("", "--")}
    return sorted(best.values(), key=lambda n: -n["signal"])


def current_wifi():
    if not on_pi():
        return ""
    try:
        out = subprocess.run(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return ""
    for line in out.splitlines():
        fields = _nmcli_fields(line)
        if fields[0] == "yes" and len(fields) > 1:
            return fields[1]
    return ""


def _admin(*args):
    """Start a root job in the background (so the setup page can answer first)."""
    subprocess.Popen(["sudo", "-n", str(ADMIN), *args], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def connect_wifi(ssid, password):
    _admin("wifi", ssid, password)


def run(action):
    if action not in ("update", "restart", "reboot"):
        raise ValueError(action)
    _admin(action)
