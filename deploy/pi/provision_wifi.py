#!/usr/bin/env python3
"""Join the club's Wi-Fi from a ready-for-a-club card (run as root by wifi-check.sh).

If the card's aroundthegrounds.json has Wi-Fi details, they're saved as a
NetworkManager connection (so it connects now and after every restart), and
the password is then removed from the card. Wrong details are no problem:
the setup hotspot still opens when the box can't get online.
"""

import json
import subprocess
from pathlib import Path

PATHS = (Path("/boot/firmware/aroundthegrounds.json"), Path("/boot/aroundthegrounds.json"))
CONNECTION = "club-wifi"


def main():
    for path in PATHS:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            print(f"Couldn't read {path}: {error}")
            return
        wifi = data.get("wifi") or {}
        if wifi.get("saved"):
            return  # done on an earlier start-up
        ssid, password = str(wifi.get("ssid") or ""), str(wifi.get("password") or "")
        if not ssid:
            return
        subprocess.run(["nmcli", "connection", "delete", CONNECTION], capture_output=True)
        command = ["nmcli", "connection", "add", "type", "wifi", "ifname", "wlan0", "con-name", CONNECTION,
                   "ssid", ssid, "connection.autoconnect", "yes"]
        if password:
            command += ["wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Couldn't save the Wi-Fi {ssid}: {result.stderr.strip()}")
            return
        subprocess.run(["nmcli", "connection", "up", CONNECTION], capture_output=True, timeout=60)
        # Don't leave the password lying on the card.
        data["wifi"] = {"ssid": ssid, "saved": True}
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"Saved the club's Wi-Fi ({ssid}) from the card.")
        return


if __name__ == "__main__":
    main()
