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

- **Any club:** each box is set up from a phone at `/setup`: paste the link
  to the club's PlayCricket page and it finds the club, its team names and logo.
  Then choose colours, heading, logo, which pages to show, and **sponsor
  slides** that come up between pages: upload an image, or type the sponsor's
  website address and the box makes a slide from it (name, logo, brand colour
  and a line about them), to check and adjust before it's added.
- **No Wi-Fi yet?** The box opens its own setup Wi-Fi and the TV says how to
  connect to it and choose the club's network.

Scores are checked every minute (PlayCricket's live scores themselves update
as the scorer's app sends them). It began as the Live scores screen of the
Altona Roosters' Cricket Archive app.

Selling it to other clubs: see `docs/SELLING.md`, the ready-made SD card kit in
`deploy/image/README.md`, and the draft request to PlayHQ in
`docs/playhq-permission-request.md`.

## Try it on a laptop

```
pip install -r requirements.txt
python server.py
```

Then open http://localhost:8080/setup to choose a PIN and the club, and
http://localhost:8080 for the scoreboard. On Windows, if that port is blocked,
set another first, e.g. `set ATG_PORT=5055` (PowerShell: `$env:ATG_PORT="5055"`).

Tests: `python -m unittest discover -s tests`

## Settings

Almost everything is chosen on the setup page and saved in the `data` folder
(the club, colours, logo, sponsors, timings and the setup PIN). The data folder
is never committed. `settings.env` (copied from `settings.example.env`) only
holds the web server's port and the setup hotspot's name and password.

Forgotten the setup PIN? On the box: `python3 -c "import config; config.save(pin_hash='')"`
in the project folder, then open `/setup` to choose a new one.

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
git clone https://github.com/JMoojie/Around-The-Grounds.git around-the-grounds
cd around-the-grounds
sudo ./deploy/pi/setup.sh
```

Setup takes 10–20 minutes on a Zero. The TV then shows **Let's get set up**
with the address of the setup page: open it on a phone on the same Wi-Fi,
choose a PIN, and paste the link to the club's PlayCricket page. The
scoreboard starts by itself every time the Pi is powered on.

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
and clone with `git clone git@github.com:JMoojie/Around-The-Grounds.git around-the-grounds`.

### Handy commands (on the Pi)

| To | Run |
|---|---|
| Change the Wi-Fi | the setup page, or `sudo nmtui` |
| Change the club, look, sponsors or timings | the setup page: http://aroundthegrounds.local:8080/setup |
| See what the scoreboard is doing | `journalctl -u around-the-grounds -n 50` |
| See what the TV browser is doing | `journalctl -u around-the-grounds-kiosk -n 50` |
| See what the Wi-Fi watcher is doing | `journalctl -u around-the-grounds-wifi -n 50` |
| Restart everything | `sudo reboot` |

Phones and laptops on the same Wi-Fi can open the scoreboard too:
http://aroundthegrounds.local:8080

**Wi-Fi gone?** If the box can't reach a network for about a minute and a half
after starting, it opens a setup Wi-Fi called `AroundTheGrounds-Setup`
(password `scoreboard`; both can be changed in `settings.env`) and the TV
explains how to use it. While the setup Wi-Fi is on, the box tries the club's
saved network again every 10 minutes.

**If the picture is sluggish on a Zero:** run the TV output at 720p (the page
scales to fit). Add ` video=HDMI-A-1:1280x720@60` to the end of the single line
in `/boot/firmware/cmdline.txt` (`sudo nano /boot/firmware/cmdline.txt`), then
`sudo reboot`.
