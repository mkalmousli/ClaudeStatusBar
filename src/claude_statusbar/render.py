"""Shared presentation: the colour bands and the meter rows."""

from claude_statusbar.config import cfg

#: Nominal length of each rate-limit window, used for the time-remaining bar.
WINDOW_SECONDS = {"5h": 5 * 3600, "wk": 7 * 86400}


def bands():
    """The configured (from-percentage, colour) stops, lowest first."""
    rows = []
    for entry in cfg.get("bands") or []:
        try:
            rows.append((float(entry[0]), str(entry[1])))
        except (TypeError, ValueError, IndexError):
            continue
    return sorted(rows)


def status_color(used):
    """Colour for a usage percentage: the last band it has reached.

    The exact number always sits beside the meter, so colour is a redundant
    urgency cue rather than the only thing carrying the reading.
    """
    if used is None:
        return cfg["img_label"]
    colour = cfg["img_label"]
    for start, value in bands():
        if used >= start:
            colour = value
    return colour


def limit_rows(data):
    """The two meters every view shows: (label, used%, countdown)."""
    rows = [("5h", data.h5_use, data.h5_cd)]
    if data.credits_mode:
        rows.append(("$", data.credit_use, ""))
    else:
        rows.append(("wk", data.wk_use, data.wk_cd))
    return rows


def time_left_pct(data, label):
    """How much of the window is still ahead, as a percentage.

    Pairs with the usage bar: one shows how much of the allowance is gone, the
    other how much of the window is left to spend it in.
    """
    window = WINDOW_SECONDS.get(label)
    reset = {"5h": data.h5_reset, "wk": data.wk_reset}.get(label, 0)
    if not window or not reset:
        return None
    remaining = (reset - data.now) / window * 100
    return max(0.0, min(100.0, remaining))
