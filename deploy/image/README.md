# Making ready-to-go SD cards

The aim: a club receives a box, plugs it into the TV and power, and sets it up
from a phone. No commands, no laptop.

## 1. Make one master Pi

1. Set up one Pi as in the main README (Raspberry Pi Imager → Pi OS Lite, then
   `sudo ./deploy/pi/setup.sh`). When Imager asks for a username, use a
   neutral one such as `scoreboard` with a strong password, and keep it safe:
   it's the same on every card you make.
2. Check it works with your own club, and try the setup page and a sponsor slide.
3. Wipe it back to a clean, unconfigured box:

   ```
   cd ~/around-the-grounds
   sudo ./deploy/image/prepare-image.sh
   ```

   Add `--keep-ssh` if you want to be able to log in to clubs' boxes remotely
   (only with their agreement). Without it, SSH is turned off.

   The Pi shuts down when it's finished.

## 2. Copy the card to an image file (Windows)

1. Put the master card in your laptop.
2. Install **Win32 Disk Imager** (free). Choose a file name such as
   `around-the-grounds-2026-11.img`, tick **Read Only Allocated Partitions**,
   and press **Read**.
3. Optional, to make the file smaller: compress it with 7-Zip (Raspberry Pi
   Imager can write `.img.xz` and `.zip` files directly). On Linux or WSL,
   PiShrink also shrinks the image and makes it grow back to fill each new card.

## 3. Make a card for each club

1. In **Raspberry Pi Imager**: *Choose OS* → **Use custom** → your image file.
2. Choose the card and write it. When Imager offers to apply OS customisation,
   choose **No**: the box sets up its Wi-Fi from a phone.
3. Label the box with the setup Wi-Fi name and password
   (`AroundTheGrounds-Setup` / `scoreboard`, unless you changed them in
   `settings.env` before making the master).

## Ready for a particular club (recommended)

After writing the card (step 3 above), with the card still in your laptop:

```
python tools/prepare_club_card.py --card E: --club "<link to the club's PlayCricket page>"
```

(`E:` is the card's **bootfs** drive.) This checks the club on PlayCricket and
writes its details onto the card, makes a setup PIN, and saves a **welcome
sheet** to print and send with the box. On first start-up the box becomes that
club (name, team names, logo, PIN). The club then scans the QR codes on the TV
to join it to their Wi-Fi: nobody else needs their Wi-Fi password.

## What the club does

With a ready-for-a-club card: plug the box into the TV and power, scan the two
QR codes, enter the PIN from the welcome sheet and choose the club's Wi-Fi.
The scoreboard starts straight away. With a plain card:


1. Plug the box into the TV (HDMI) and power. After about two minutes the TV
   shows **Connect me to Wi-Fi**.
2. On a phone, join the Wi-Fi network shown on the TV, then open the address
   shown (http://10.42.0.1:8080/setup).
3. Choose a setup PIN, then pick the club's Wi-Fi network and enter its password.
4. Reconnect the phone to the club's Wi-Fi and open the new address the TV shows.
5. Paste the link to the club's PlayCricket page, confirm the club, and choose
   colours, logo and sponsors.

The box updates itself from GitHub each night, so every club gets fixes and
new features automatically.

## Reset the setup PIN (if a club forgets it)

With a keyboard plugged into the box (or over SSH):

```
cd ~/around-the-grounds
python3 -c "import config; config.save(pin_hash='')"
```

The next visit to the setup page asks for a new PIN.

## Updates for boxes you've sold

Each box pulls the GitHub repo it was cloned from. Keep that repo's `main`
branch working at all times: develop on a branch, test on your own box, then
merge. For a private repo, each box needs read access (see "Updates" in the
main README).
