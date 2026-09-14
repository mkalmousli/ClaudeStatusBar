"""The meter drawing, as SVG.

One implementation feeds every surface: the Qt tray icon renders this through
QSvgRenderer, and the Xfce panel plugin renders the identical string through
gdk-pixbuf.  Keeping it as markup rather than per-toolkit paint calls is what
makes the panel item and the tray item look the same.
"""

from claude_statusbar.config import cfg
from claude_statusbar.render import limit_rows, status_color
from claude_statusbar.util import esc, human, pct, today

# Layout in viewBox units; the drawing scales to whatever height it is asked for.
PAD, LBL, BAR, GAP, PCTW, CDW = 5, 15, 64, 8, 31, 40
MARK_W = 16          # the logo's spark, drawn at the left of the strip
VB_W = PAD + MARK_W + PAD + LBL + BAR + GAP + PCTW + 6 + CDW + PAD
VB_H = 24
FONT = "DejaVu Sans,Segoe UI,Helvetica,sans-serif"
MARK_COLOR = "#d97757"   # the spark, matching logo.svg

# A square variant for trays, which want an icon rather than a wide strip.
SQUARE_VB = 24


def _mark(colour):
    """The logo's spark, so the panel item is recognisably this tool.

    Drawn rather than embedded: the strip is one SVG, and a nested <image>
    would need the file to still be there when the panel renders it.
    """
    cx, cy, arm = PAD + MARK_W / 2, VB_H / 2, 5.2
    strokes = "".join(
        f'<path d="M{cx - dx:.2f} {cy - dy:.2f}L{cx + dx:.2f} {cy + dy:.2f}"/>'
        for dx, dy in ((0, arm), (arm * 0.866, arm * 0.5), (arm * 0.866, -arm * 0.5)))
    return (f'<g stroke="{colour}" stroke-width="2.1" stroke-linecap="round">'
            f'{strokes}</g>')


def _row(y, label, used, countdown, label_color, width):
    fill = status_color(used)
    bar_x = PAD + MARK_W + PAD + LBL
    parts = [
        f'<text x="{PAD + MARK_W + PAD}" y="{y + 3.2}" fill="{label_color}" '
        f'font-size="9" font-family="{FONT}">{esc(label)}</text>',
        f'<rect x="{bar_x}" y="{y - 3}" width="{BAR}" height="6" rx="3" '
        f'fill="{cfg["img_track"]}"/>',
    ]
    if used:
        # Keep a sliver visible at a fraction of a percent so "barely used"
        # still reads as a bar rather than an empty track.
        filled = max(4, round(BAR * used / 100))
        parts.append(f'<rect x="{bar_x}" y="{y - 3}" width="{filled}" height="6" '
                     f'rx="3" fill="{fill}"/>')
    parts.append(
        f'<text x="{bar_x + BAR + GAP + PCTW}" y="{y + 3.2}" fill="{fill}" '
        f'font-size="9.5" font-weight="bold" text-anchor="end" '
        f'font-family="{FONT}">{pct(used)}</text>')
    if countdown:
        parts.append(f'<text x="{width - PAD}" y="{y + 3.2}" '
                     f'fill="{cfg["img_label"]}" font-size="9" text-anchor="end" '
                     f'font-family="{FONT}">{esc(countdown)}</text>')
    return "".join(parts)


def _waste_dot(cx, cy, radius, data):
    """A small colour-coded dot: is the current 5h window's pace being wasted?

    Green/amber/orange/red mirrors the usage bands, so the one dot reads at a
    glance without needing the tooltip open.
    """
    colour = getattr(data, "waste_color", None) or cfg["img_label"]
    return f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="{colour}"/>'


def wide_svg(data, height=None):
    """The panel strip: two labelled rows with percentages and countdowns."""
    height = height or cfg["img_height"]
    scale = height / VB_H
    # Amber labels flag "these numbers are suspect" — stale, or hook not firing.
    label_color = cfg["warn_color"] if data.note_warn else cfg["img_label"]
    body = (_mark(MARK_COLOR)
           + _waste_dot(VB_W - PAD - 2.5, PAD + 1.5, 2.5, data)
           + "".join(_row(y, label, used, countdown, label_color, VB_W)
                     for y, (label, used, countdown) in zip((7, 17), limit_rows(data))))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{round(VB_W * scale)}" '
            f'height="{round(VB_H * scale)}" viewBox="0 0 {VB_W} {VB_H}">{body}</svg>')


def square_svg(data, size=64):
    """A square badge for system trays: two stacked bars, no text.

    Tray icons are tiny and square; percentages would be unreadable, so the
    numbers move to the tooltip and the icon carries only the two levels.
    """
    rows = limit_rows(data)
    body = []
    for index, (_label, used, _cd) in enumerate(rows):
        y = 5 + index * 9
        body.append(f'<rect x="2" y="{y}" width="20" height="6" rx="3" '
                    f'fill="{cfg["img_track"]}"/>')
        if used:
            filled = max(2, round(20 * used / 100))
            body.append(f'<rect x="2" y="{y}" width="{filled}" height="6" rx="3" '
                        f'fill="{status_color(used)}"/>')
    body.append(_waste_dot(SQUARE_VB - 4, 4, 3, data))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
            f'viewBox="0 0 {SQUARE_VB} {SQUARE_VB}">{"".join(body)}</svg>')


def tooltip(data):
    """Plain-text summary shared by the tray tooltip and the panel plugin."""
    icon = cfg["icon"] + " " if cfg["icon"] else ""
    lines = [f"{icon}{data.model or 'Claude'} · {today()}"]
    if data.have_state:
        lines[0] += f" · ${float(data.cost):.2f}"
        if data.note:
            lines[0] += f" · {data.note}"
        if getattr(data, "waste_label", None):
            lines.append(f"5h pace: {data.waste_label}")
        for label, used, countdown in limit_rows(data):
            filled = 0 if used is None else round(used * 16 / 100)
            meter = "█" * filled + "░" * (16 - filled)
            line = f"{label:<4} {meter} {pct(used):>4} used"
            if countdown:
                line += f"  · resets in {countdown}"
            lines.append(line)
    else:
        lines.append(data.note or "no live data — run the installer")
    lines.append(f"today {human(data.today_tok)} tok · {data.today_msg} msg "
                 f"· {data.today_ses} ses")
    if not data.credits_mode:
        lines.append(f"7d    {human(data.week_tok)} tok   ·   all "
                     f"{data.total_msg} msg · {data.total_ses} ses")
    return "\n".join(lines)
