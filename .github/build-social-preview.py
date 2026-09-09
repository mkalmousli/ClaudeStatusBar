"""Build the GitHub social preview card: 1280x640, PNG and SVG.

Content stays inside the 40pt safe border GitHub recommends, because the card
is cropped differently depending on where it is embedded.

Run it after changing the logo or the screenshots:

    python3 .github/build-social-preview.py

Then upload the PNG under repository Settings > Social preview — GitHub has no
API for that part.
"""
import base64
import io
import pathlib

import gi
from PIL import Image

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
S = ROOT / ".github"    # win.png lives here: the window crop from screenshots/gui.png
W, H = 1280, 640

def embed(img, width):
    """Downscale to the size it is displayed at, then inline it."""
    ratio = width / img.width
    img = img.resize((width, round(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{data}", img.width, img.height

win_uri, win_w, win_h = embed(Image.open(S / "win.png").convert("RGB"), 560)
strip_uri, strip_w, strip_h = embed(Image.open(ROOT / "screenshots/xfce4-plugin.png").convert("RGB"), 560)
logo_uri = "data:image/svg+xml;base64," + base64.b64encode((ROOT / "logo.svg").read_bytes()).decode()

FONT = "Ubuntu,DejaVu Sans,sans-serif"
INK, DIM, FAINT = "#f2f4f7", "#b9bfca", "#8b929e"
ORANGE, GREEN, AMBER = "#d97757", "#2ec27e", "#fab219"

RIGHT_X = 640
strip_y = 132
win_y = strip_y + strip_h + 26

# Kept short: the right-hand images start at x=640, so a line may not run
# past roughly 500px at this size.
bullets = [
    (GREEN,  "5-hour and weekly limits, with time to reset"),
    (AMBER,  "Xfce panel plugin · KDE · GNOME · Windows · macOS"),
    (ORANGE, "Redraws the moment a session writes"),
]
rows = "".join(
    f'<circle cx="92" cy="{332 + i*44 - 6}" r="5.5" fill="{c}"/>'
    f'<text x="112" y="{332 + i*44}" font-family="{FONT}" font-size="19" fill="{DIM}">{t}</text>'
    for i, (c, t) in enumerate(bullets))

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#212429"/>
      <stop offset="0.55" stop-color="#1a1c21"/>
      <stop offset="1" stop-color="#141519"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.13" cy="0.16" r="0.62">
      <stop offset="0" stop-color="{ORANGE}" stop-opacity="0.22"/>
      <stop offset="1" stop-color="{ORANGE}" stop-opacity="0"/>
    </radialGradient>
    <filter id="shadow" x="-12%" y="-12%" width="130%" height="140%">
      <feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#000" flood-opacity="0.55"/>
    </filter>
    <clipPath id="clipWin"><rect x="{RIGHT_X}" y="{win_y}" width="{win_w}" height="{win_h}" rx="12"/></clipPath>
    <clipPath id="clipStrip"><rect x="{RIGHT_X}" y="{strip_y}" width="{strip_w}" height="{strip_h}" rx="12"/></clipPath>
  </defs>

  <rect width="{W}" height="{H}" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" fill="url(#glow)"/>
  <rect x="0" y="0" width="{W}" height="5" fill="{ORANGE}"/>

  <!-- left: identity -->
  <image xlink:href="{logo_uri}" x="88" y="86" width="76" height="76"/>
  <text x="88" y="228" font-family="{FONT}" font-size="53" font-weight="bold" fill="{INK}">Claude Status Bar</text>
  <text x="88" y="272" font-family="{FONT}" font-size="23" fill="{FAINT}">Your Claude Code limits, always in sight.</text>
  {rows}
  <g font-family="{FONT}" font-size="17">
    <rect x="88" y="486" width="118" height="30" rx="15" fill="#ffffff" fill-opacity="0.07"/>
    <text x="147" y="506" fill="{DIM}" text-anchor="middle">GPL-3.0</text>
    <rect x="216" y="486" width="150" height="30" rx="15" fill="#ffffff" fill-opacity="0.07"/>
    <text x="291" y="506" fill="{DIM}" text-anchor="middle">Python + Qt</text>
    <text x="88" y="556" font-size="19" fill="{FAINT}">github.com/mkalmousli/ClaudeStatusBar</text>
  </g>

  <!-- right: the two surfaces -->
  <g filter="url(#shadow)">
    <rect x="{RIGHT_X}" y="{strip_y}" width="{strip_w}" height="{strip_h}" rx="12" fill="#353535"/>
    <image xlink:href="{strip_uri}" x="{RIGHT_X}" y="{strip_y}" width="{strip_w}" height="{strip_h}" clip-path="url(#clipStrip)"/>
    <rect x="{RIGHT_X}" y="{strip_y}" width="{strip_w}" height="{strip_h}" rx="12" fill="none" stroke="#ffffff" stroke-opacity="0.10"/>
  </g>
  <g filter="url(#shadow)">
    <rect x="{RIGHT_X}" y="{win_y}" width="{win_w}" height="{win_h}" rx="12" fill="#2b2b2b"/>
    <image xlink:href="{win_uri}" x="{RIGHT_X}" y="{win_y}" width="{win_w}" height="{win_h}" clip-path="url(#clipWin)"/>
    <rect x="{RIGHT_X}" y="{win_y}" width="{win_w}" height="{win_h}" rx="12" fill="none" stroke="#ffffff" stroke-opacity="0.10"/>
  </g>
</svg>
'''
(ROOT / ".github/social-preview.svg").write_text(svg)
pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(ROOT / ".github/social-preview.svg"))
pixbuf.savev(str(ROOT / ".github/social-preview.png"), "png", [], [])
print("strip", strip_w, strip_h, "| window", win_w, win_h, "| win_y", win_y, "bottom", win_y + win_h)
