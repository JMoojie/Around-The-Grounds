"""Sponsor slides made from a website address.

``from_website`` reads a sponsor's home page for its name, a one-line
description, brand colour and logo. Setup shows the result to check and edit,
then ``card_html`` draws the slide on the TV. Only public websites are read
(never addresses on the club's own network), with size limits and timeouts.
"""

import ipaddress
import json
import re
import socket
from html import escape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests
from urllib.parse import parse_qsl, urlencode, urlunparse

PAGE_LIMIT = 2 * 1024 * 1024
IMAGE_LIMIT = 4 * 1024 * 1024
TIMEOUT = 15
TAGLINE_LIMIT = 400  # the whole description; only something enormous is cut, at a sentence
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AroundTheGrounds scoreboard; sponsor slide)"}
COLOUR = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")
# Pages some websites show automated visitors instead of their home page.
BOT_CHECKS = ("recaptcha", "just a moment", "attention required", "access denied", "are you a robot",
              "security check", "captcha", "cloudflare", "403 forbidden", "pardon our interruption")


class _Page(HTMLParser):
    """Collects what a sponsor slide needs from a home page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.meta, self.icons, self.logos, self.json_ld = {}, [], [], []
        self.title, self._in_title, self._in_ld, self._logo_wrap = "", False, False, 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        marked = "logo" in f"{a.get('class', '')} {a.get('id', '')}".lower()
        if tag == "meta":
            key = (a.get("property") or a.get("name") or a.get("itemprop") or "").lower()
            if key and a.get("content") and key not in self.meta:
                self.meta[key] = a["content"].strip()
        elif tag == "link" and "icon" in a.get("rel", "").lower() and a.get("href"):
            self.icons.append((a.get("rel", "").lower(), a.get("sizes", ""), a["href"]))
        elif tag == "img":
            src = a.get("src") or a.get("data-src") or ""
            text = f"{a.get('class', '')} {a.get('id', '')} {a.get('alt', '')} {src}".lower()
            if src and not src.startswith("data:") and ("logo" in text or self._logo_wrap):
                self.logos.append(src)
            self._logo_wrap = 0
        elif tag == "title":
            self._in_title = True
        elif tag == "script" and "ld+json" in a.get("type", "").lower():
            self._in_ld = True
        if marked and tag != "img":
            self._logo_wrap = 6  # an <img> inside something called "logo" is probably the logo
        elif self._logo_wrap:
            self._logo_wrap -= 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_ld = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_ld:
            self.json_ld.append(data)


def _check_public(url):
    """Only http(s) addresses on the public internet."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("That isn't a website address.")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as error:
        raise ValueError(f"Couldn't find {parts.hostname}.") from error
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("Only public websites can be used.")


def _get(url, limit):
    """GET with a size limit, checking every redirect too. Returns (final url, bytes, content type)."""
    for _ in range(6):
        _check_public(url)
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=False)
        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            url = urljoin(url, response.headers.get("Location", ""))
            response.close()
            continue
        response.raise_for_status()
        data = b""
        for chunk in response.iter_content(65536):
            data += chunk
            if len(data) > limit:
                response.close()
                raise ValueError("That's too big to use.")
        return url, data, response.headers.get("Content-Type", "")
    raise ValueError("That website redirects too many times.")


def image_type(data):
    for magic, kind in ((b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpg"), (b"GIF8", "gif")):
        if data.startswith(magic):
            return kind
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    head = data[:600].lstrip().lower()
    if head.startswith((b"<svg", b"<?xml")) and b"<svg" in data[:4000].lower():
        return "svg"
    return None


def _json_ld_logo(blocks):
    for block in blocks:
        try:
            data = json.loads(block)
        except ValueError:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                logo = item.get("logo")
                if isinstance(logo, str):
                    return logo
                if isinstance(logo, dict) and isinstance(logo.get("url"), str):
                    return logo["url"]
                stack.extend(v for v in item.values() if isinstance(v, (dict, list)))
    return ""


def _full_size(url):
    """Online shops resize images by address (?width=40): ask for the full-size logo."""
    parts = urlparse(url)
    if "shopify" in parts.netloc or "/cdn/shop/" in parts.path or "wp-content" in parts.path:
        query = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() not in ("width", "height", "w", "h", "crop")]
        return urlunparse(parts._replace(query=urlencode(query)))
    return url


def _name(page, host):
    name = page.meta.get("og:site_name") or page.meta.get("application-name") or ""
    if not name:
        title = re.sub(r"\s+", " ", page.title).strip()
        parts = [p.strip() for p in re.split(r"\s+[|–—·:-]\s+", title) if p.strip()]
        # "Home | Westside Bakery": skip generic words.
        parts = [p for p in parts if p.lower() not in ("home", "homepage", "welcome")] or parts
        name = min(parts, key=len) if len(parts) > 1 else (parts[0] if parts else "")
    return name[:60] or host


def from_website(address):
    """{"name", "tagline", "colour", "web", "logo_url", "logo_options"} for a sponsor's website. Raises ValueError."""
    address = str(address or "").strip()
    if not address:
        raise ValueError("Enter the sponsor's website address.")
    if "://" not in address:
        address = "https://" + address
    try:
        url, data, _kind = _get(address, PAGE_LIMIT)
    except requests.RequestException as error:
        raise ValueError(f"Couldn't open that website ({type(error).__name__}).") from error
    page = _Page()
    page.feed(data.decode("utf-8", errors="replace"))
    host = (urlparse(url).hostname or "").removeprefix("www.")
    title = re.sub(r"\s+", " ", page.title).strip().lower()
    if any(check in title for check in BOT_CHECKS) and not page.meta.get("og:site_name"):
        raise ValueError(f"{host} doesn't let the scoreboard read its page automatically. "
                         "Upload an image of the sponsor's logo or advert instead.")

    tagline = re.sub(r"\s+", " ", page.meta.get("og:description") or page.meta.get("description") or "").strip()
    tagline = clip_tagline(tagline)
    colour = page.meta.get("theme-color", "")
    colour = colour.lower() if COLOUR.match(colour) else ""
    if len(colour) == 4:
        colour = "#" + "".join(c * 2 for c in colour[1:])

    def icon_size(icon):
        rel, sizes, _href = icon
        match = re.match(r"(\d+)", sizes)
        return int(match.group(1)) if match else (180 if "apple" in rel else 16)

    # Big icons only: a 16-pixel favicon would be a blur on a TV.
    icons = [icon[2] for icon in sorted(page.icons, key=icon_size, reverse=True) if icon_size(icon) >= 96]
    candidates = page.logos[:3] + [_json_ld_logo(page.json_ld), page.meta.get("og:image", "")] + icons
    options = []
    for candidate in candidates:
        if candidate:
            absolute = _full_size(urljoin(url, candidate))
            if absolute.startswith(("http://", "https://")) and absolute not in options:
                options.append(absolute)
    return {"name": _name(page, host), "tagline": tagline, "colour": colour or "#ffffff",
            "web": host, "logo_url": options[0] if options else "", "logo_options": options[:4]}


def clip_tagline(text):
    """The full description, unless it's enormous: then up to the last full sentence that fits."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(text) <= TAGLINE_LIMIT:
        return text
    cut = text[:TAGLINE_LIMIT]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return cut[:end + 1] if end > 80 else cut.rsplit(" ", 1)[0].rstrip(" .,;:-") + "…"


def download_logo(url):
    """(bytes, kind) of a logo image, or raises ValueError."""
    try:
        _url, data, _kind = _get(url, IMAGE_LIMIT)
    except requests.RequestException as error:
        raise ValueError(f"Couldn't download the logo ({type(error).__name__}).") from error
    kind = image_type(data)
    if not kind:
        raise ValueError("The logo isn't an image the scoreboard can show.")
    return data, kind


def _text_colour(background):
    """Black or white text, whichever reads better on the background."""
    try:
        r, g, b = (int(background[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except (ValueError, TypeError, IndexError):
        return "#111111"

    def linear(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    luminance = 0.2126 * linear(r) + 0.7152 * linear(g) + 0.0722 * linear(b)
    return "#111111" if luminance > 0.45 else "#ffffff"


def _tag_size(text):
    """Longer descriptions use smaller text, so all of it fits on the card."""
    return " sc-tag-longer" if len(text) > 260 else " sc-tag-long" if len(text) > 160 else ""


def card_html(sponsor, image_url):
    """The sponsor's slide: an uploaded image, or a card made from their website."""
    name = escape(sponsor.get("name", ""))
    if sponsor.get("kind") != "card":
        return (f'<img class="sponsor-image" src="{escape(image_url, quote=True)}" alt="">'
                f'<p class="sponsor-name">{name}</p>')
    colour = sponsor.get("colour") if COLOUR.match(sponsor.get("colour", "")) else "#ffffff"
    logo = (f'<img class="sc-logo" src="{escape(image_url, quote=True)}" alt="">' if sponsor.get("file") else "")
    return (f'<div class="sponsor-card" style="background:{colour};color:{_text_colour(colour)}">{logo}'
            + (f'<div class="sc-name{" sc-name-big" if not logo else ""}">{name}</div>'
               if not logo or sponsor.get("show_name", True) else "")
            + f'<div class="sc-tag{_tag_size(sponsor.get("tagline", ""))}">{escape(sponsor.get("tagline", ""))}</div>'
            f'<div class="sc-web">{escape(sponsor.get("web", ""))}</div></div>')
