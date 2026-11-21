# Selling Around the Grounds to other clubs

## Before charging anyone

- **Get permission to use PlayCricket's data.** The scores come from the public
  feed behind play.cricket.com.au. It isn't an official, documented API, and
  PlayHQ / Cricket Australia could change or restrict it at any time. A draft
  request is in `docs/playhq-permission-request.md`. Their answer shapes the
  product: they may offer an official API key, ask for terms, or say no.
- **Names and logos.** Show clubs' own logos only with their agreement (the
  setup page offers PlayCricket's logo; the club chooses to use it). Don't use
  "PlayCricket", "PlayHQ" or Cricket Australia branding in your marketing
  without permission. "Scores from PlayCricket" as a source credit is normal.
- **Player names include juniors.** The scoreboard shows only what PlayCricket
  already shows publicly, and stores nothing. Keep it that way.
- **Business basics.** An ABN, GST once you pass the threshold, and simple
  terms of sale (what's included, updates, refunds, "scores depend on
  PlayCricket being available"). Product liability insurance is worth asking
  your insurer about if you sell hardware.

## The product

| Part | Notes |
|---|---|
| Raspberry Pi Zero 2 W, power supply, mini-HDMI cable, case, SD card | About $70–90 AUD in parts |
| Pre-loaded card (see `deploy/image/README.md`) | The club only needs Wi-Fi and a phone |
| Setup page | Club, colours, logo, sponsors, timings, Wi-Fi, PIN |
| Nightly updates from GitHub | Every club gets fixes automatically |

Possible pricing models: a one-off price for the box (parts plus your time),
or a lower box price plus a yearly subscription for updates and support.
Sponsor slides give clubs a way to cover the cost.

## Keeping the code private

Boxes update from your GitHub repo. If the repo is public, anyone can copy the
product. For a paid product, keep it private and give the master image a
read-only **deploy key** (GitHub: repo *Settings › Deploy keys*). Every box
made from the image then shares that read-only key. If one is ever misused,
remove the key on GitHub and issue a new image.

## Ideas for later

- Several clubs per box (for associations or shared grounds).
- A season ladder page per grade.
- Senior and junior season leaders separately (adding up each grade's games).
- A remote "fleet" page showing which sold boxes are online and up to date.
