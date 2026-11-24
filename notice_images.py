"""Pictures for notices: club posters as JPEG, PNG, GIF, WebP or PDF.

PDFs are turned into a picture of their first page with pdftoppm (the
poppler-utils package on the Pi), sized for a 1920-pixel-wide TV.
"""

import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import config
import sponsor_cards

FILE = re.compile(r"^[0-9a-f]{32}\.(png|jpg|gif|webp|svg)$")


def folder():
    return config.DATA_DIR / "notices"


def save(data):
    """Save an uploaded poster; returns its file name. Raises ValueError."""
    kind = sponsor_cards.image_type(data)
    name = f"{uuid.uuid4().hex}.{kind or 'png'}"
    folder().mkdir(parents=True, exist_ok=True)
    if kind:
        (folder() / name).write_bytes(data)
        return name
    if data[:5] != b"%PDF-":
        raise ValueError("That isn't a picture (JPEG, PNG, GIF, WebP) or a PDF.")
    tool = shutil.which("pdftoppm")
    if not tool:
        raise ValueError("This box can't open PDFs yet (it needs an update). Save the poster as a JPEG or PNG and "
                         "upload that instead.")
    with tempfile.TemporaryDirectory() as work:
        source = Path(work) / "poster.pdf"
        source.write_bytes(data)
        try:
            subprocess.run([tool, "-png", "-singlefile", "-f", "1", "-l", "1", "-scale-to", "1920",
                            str(source), str(Path(work) / "page")], check=True, capture_output=True, timeout=90)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            raise ValueError("That PDF couldn't be opened. Try saving the poster as a JPEG or PNG.") from error
        page = Path(work) / "page.png"
        if not page.exists():
            raise ValueError("That PDF couldn't be opened. Try saving the poster as a JPEG or PNG.")
        (folder() / name).write_bytes(page.read_bytes())
    return name


def remove(name):
    if name and FILE.match(name):
        (folder() / name).unlink(missing_ok=True)
