#!/usr/bin/env python3
"""The TV remote for the scoreboard, over HDMI-CEC (Samsung: Anynet+).

The Pi joins the TV's CEC network as a playback device called "Scoreboard".
While the TV is on the Pi's input, the TV passes remote buttons to it, and
this turns them into scoreboard actions:

    Right, Down, Fast forward  -> next page
    Left, Up, Rewind           -> previous page
    OK, Play, Pause            -> pause / resume

Run by the around-the-grounds-remote service (set up by setup.sh). Uses
cec-ctl from v4l-utils and only the Python standard library.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request

DEVICE = os.environ.get("ATG_CEC_DEVICE", "/dev/cec0")
URL = f"http://127.0.0.1:{os.environ.get('ATG_PORT', '8080')}/api/remote"

# CEC "user control" codes (HDMI-CEC specification, table 30).
NEXT = {0x02, 0x04, 0x49, 0x4B}      # down, right, fast forward, forward
PREVIOUS = {0x01, 0x03, 0x48, 0x4C}  # up, left, rewind, backward
PAUSE = {0x00, 0x44, 0x46, 0x61}     # select (OK), play, pause, play/pause
UI_COMMAND = re.compile(r"ui-cmd:.*\((0x[0-9a-fA-F]+)\)")


def action_for(code):
    if code in NEXT:
        return "next"
    if code in PREVIOUS:
        return "previous"
    if code in PAUSE:
        return "pause"
    return None


def presses(lines):
    """Actions from `cec-ctl --monitor` output: a USER_CONTROL_PRESSED line, then its ui-cmd line."""
    pressed = False
    for line in lines:
        if "USER_CONTROL_PRESSED" in line:
            pressed = True
            continue
        if pressed:
            pressed = False
            match = UI_COMMAND.search(line)
            action = action_for(int(match.group(1), 16)) if match else None
            if action:
                yield action


def send(action):
    request = urllib.request.Request(URL, data=json.dumps({"action": action}).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(request, timeout=3).close()
    except OSError as error:
        print(f"Couldn't pass '{action}' to the scoreboard: {error}", file=sys.stderr)


def cec(*args):
    return subprocess.run(["cec-ctl", "-d", DEVICE, *args], capture_output=True, text=True, check=False)


def join_tv():
    """Become a playback device and tell the TV we're here, so it sends us the remote's buttons."""
    cec("--playback", "--osd-name", "Scoreboard", "--vendor-id", "0x000000")
    found = re.search(r"Physical Address\s*:\s*([0-9a-f]\.[0-9a-f]\.[0-9a-f]\.[0-9a-f])", cec().stdout)
    if found and found.group(1) != "f.f.f.f":
        cec("--to", "0", "--active-source", f"phys-addr={found.group(1)}")
        print(f"Joined the TV's CEC network at {found.group(1)}.")
    else:
        print("The TV isn't answering over HDMI-CEC yet (is Anynet+ on?). Listening anyway.")


def main():
    if not os.path.exists(DEVICE):
        print(f"No HDMI-CEC device at {DEVICE}: the TV remote can't be used on this box.")
        return 0
    join_tv()
    monitor = subprocess.Popen(["cec-ctl", "-d", DEVICE, "--monitor"], stdout=subprocess.PIPE, text=True, bufsize=1)
    for action in presses(monitor.stdout):
        print(f"Remote: {action}")
        send(action)
    status = monitor.wait()
    time.sleep(5)  # the service restarts us
    return status or 1


if __name__ == "__main__":
    sys.exit(main())
