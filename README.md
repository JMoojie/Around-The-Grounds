# Around the Grounds

A read-only scoreboard for the clubrooms TV. It shows the club's games and
scores straight from PlayCricket. It stores nothing and needs only Wi-Fi.

- **Match day, games being played:** each live game fills the screen with a
  big scoreboard, the batting and bowling card for the current innings, the
  last wicket, extras, run rate, and a summary of the innings before. With one
  or two games being played they share the screen; with three or more, each
  gets its own page in turn. Every other game is a small score along the bottom.
- **Match day, nothing live:** today's games as cards (start times, results, and
  "No live score" for games nobody is scoring on PlayCricket).
- **Other days:** the latest results, the season leaders (top 10 run scorers,
  wicket takers and catchers across all the club's grades, from PlayCricket's
  season statistics), then the next match day's fixtures.

Scores are checked every minute (PlayCricket's live scores themselves update
as the scorer's app sends them). It began as the Live scores screen of the
club's Cricket Archive app.

## Try it on a laptop

```
pip install -r requirements.txt
python server.py
```

Then open http://localhost:8080. On Windows, if that port is blocked, set
another first, e.g. `set ATG_PORT=5055` (PowerShell: `$env:ATG_PORT="5055"`).

Tests: `python -m unittest discover -s tests`

## Settings

`settings.example.env` lists them all: the club's PlayCricket ID and names,
the port, and how often the screen refreshes and turns pages. On the Pi they
live in `settings.env`.

## Setting up the Raspberry Pi

### What you need

| Item | Notes |
|---|---|
| Raspberry Pi **Zero 2 W** | Must be the **2 W**. The original Zero W is too slow. Any Pi 3, 4 or 5 also works. |
| microSD card, 16–32 GB | A good brand (SanDisk, Samsung). |
| 5 V 2.5 A micro-USB power supply | The official Pi Zero supply is best. A TV's USB port often isn't strong enough. |
| **Mini-HDMI** to HDMI cable or adapter | The Zero has a mini-HDMI socket. |
| A case | Optional, but it protects the board behind the TV. |

### 1. Prepare the card (on your laptop)

1. Install **Raspberry Pi Imager** from raspberrypi.com/software.
2. Choose: *Device* **Raspberry Pi Zero 2 W**, *OS* **Raspberry Pi OS (other) › Raspberry Pi OS Lite (64-bit)**, then your card.
3. When it offers to customise settings, choose **Edit settings**:
   - Hostname: `aroundthegrounds`
   - Username and password: your choice (write them down)
   - Wireless LAN: the clubrooms Wi-Fi name and password, country **AU**
   - Time zone `Australia/Melbourne`
   - Services tab: **Enable SSH** (use password authentication)
4. Write the card, put it in the Pi, connect the TV and power. The first start takes a few minutes.

### 2. Install Around the Grounds (from your laptop, over Wi-Fi)

In PowerShell or Terminal on a laptop on the **same Wi-Fi**:

```
ssh <username>@aroundthegrounds.local
```

Then on the Pi:

```
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/<your-account>/around-the-grounds.git
cd around-the-grounds
sudo ./deploy/pi/setup.sh
```

Setup takes 10–20 minutes on a Zero. The scoreboard then appears on the TV, and
it starts by itself every time the Pi is powered on.

(No laptop handy? Plug a USB keyboard into the Pi with a micro-USB OTG adapter,
log in on the TV screen, and type the same commands.)

### 3. The Samsung TV

- Set the TV's input to the Pi's HDMI port.
- **Settings › General › Eco Solution / Power**: turn off *Auto Power Off* and anything that dims the picture.
- Optional: turn on **Anynet+ (HDMI-CEC)** to let the Pi switch the TV on and off by the clock. Edit the times in `/etc/cron.d/around-the-grounds-tv` (`sudo nano /etc/cron.d/around-the-grounds-tv`) and remove the `#` at the start of the two lines.

### Updates

The Pi checks GitHub every day at 5 am and a few minutes after it starts, and
restarts the scoreboard when there's a new version. To update straight away:
`sudo ./deploy/pi/update.sh` (in the `around-the-grounds` folder).

If the GitHub repo is **private**, the Pi needs permission to read it. Either:
make the repo public (it holds no personal data), or add a read-only deploy key:
on the Pi run `ssh-keygen -t ed25519` (press Enter to everything), add the
contents of `~/.ssh/id_ed25519.pub` under the repo's *Settings › Deploy keys*,
and clone with `git clone git@github.com:<your-account>/around-the-grounds.git`.

### Handy commands (on the Pi)

| To | Run |
|---|---|
| Change the Wi-Fi | `sudo nmtui` |
| Change settings | `nano settings.env`, then `sudo systemctl restart around-the-grounds around-the-grounds-kiosk` |
| See what the scoreboard is doing | `journalctl -u around-the-grounds -n 50` |
| See what the TV browser is doing | `journalctl -u around-the-grounds-kiosk -n 50` |
| Restart everything | `sudo reboot` |

Phones and laptops on the same Wi-Fi can open the scoreboard too:
http://aroundthegrounds.local:8080

**If the picture is sluggish on a Zero:** run the TV output at 720p (the page
scales to fit). Add ` video=HDMI-A-1:1280x720@60` to the end of the single line
in `/boot/firmware/cmdline.txt` (`sudo nano /boot/firmware/cmdline.txt`), then
`sudo reboot`.
