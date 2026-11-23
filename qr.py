"""QR codes for the TV's setup screens: scan to join the setup Wi-Fi, scan to open setup.

Drawn as crisp SVG squares (any size on any TV). Uses the qrcode package
(python3-qrcode on the Pi); without it the screens simply show the written steps.
"""

def _escape_wifi(text):
    """Wi-Fi QR fields escape \\ ; , : and " with a backslash."""
    return "".join("\\" + c if c in '\\;,:"' else c for c in str(text))


def wifi_text(ssid, password):
    """What a phone camera reads to join a WPA Wi-Fi network."""
    return f"WIFI:T:WPA;S:{_escape_wifi(ssid)};P:{_escape_wifi(password)};;"


def svg(text, size=330):
    """A QR code as an SVG (on a white tile with a quiet border), or "" if qrcode isn't installed."""
    try:
        import qrcode
    except ImportError:
        return ""
    code = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    code.add_data(text)
    code.make(fit=True)
    matrix = code.get_matrix()
    count = len(matrix)
    quiet = 4  # the white margin scanners need
    full = count + quiet * 2
    squares = "".join(f"M{x + quiet} {y + quiet}h1v1h-1z"
                      for y, row in enumerate(matrix) for x, dark in enumerate(row) if dark)
    return (f'<svg class="qr" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {full} {full}" '
            f'width="{size}" height="{size}" shape-rendering="crispEdges" role="img" '
            f'aria-label="QR code"><rect width="{full}" height="{full}" fill="#fff"/>'
            f'<path d="{squares}" fill="#000"/></svg>')
