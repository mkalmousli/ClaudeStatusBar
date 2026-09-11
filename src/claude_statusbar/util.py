"""Small formatting and parsing helpers."""

import json
import re
import time
from datetime import date, datetime, timedelta

# Evaluated per call, never cached at import: the GUI is long-running and
# refreshes on a timer, so a frozen "now" produced negative ages and would
# have pinned the date across midnight.


def now():
    return int(time.time())


def today():
    return date.today().isoformat()


def week_ago():
    return (date.today() - timedelta(days=6)).isoformat()


def human(n):
    """1234567 -> '1.2M'"""
    n = float(n or 0)
    for limit, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if n >= limit:
            return f"{n / limit:.1f}{suffix}"
    return f"{int(n)}"


def dur(seconds):
    """Seconds -> '45s' / '16m' / '2h3m' / '1d4h', dropping a trailing zero unit."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes >= 1440:
        days, hours = minutes // 1440, (minutes % 1440) // 60
        return f"{days}d{hours}h" if hours else f"{days}d"
    if minutes >= 60:
        hours, mins = minutes // 60, minutes % 60
        return f"{hours}h{mins}m" if mins else f"{hours}h"
    return f"{minutes}m"


def countdown(epoch):
    """Time until an absolute epoch: '4h29m', 'now', or '' when unset."""
    if not epoch:
        return ""
    delta = int(epoch) - now()
    return dur(delta) if delta > 0 else "now"


def clock(epoch):
    """An absolute reset time, spelled for how far away it is.

    Within a day the hour is enough; further out the day has to be named or
    "resets at 08:00" is ambiguous.
    """
    if not epoch:
        return ""
    when = datetime.fromtimestamp(int(epoch))
    if when.date() == date.today():
        return when.strftime("%H:%M")
    if (when.date() - date.today()).days == 1:
        return when.strftime("tomorrow %H:%M")
    return when.strftime("%a %d %b, %H:%M")


def pct(value):
    """None -> '—', 36.8 -> '37%'"""
    return "—" if value is None else f"{round(float(value))}%"


def as_epoch(value):
    """Accept an ISO-8601 string or a raw epoch; return int or None."""
    if value in (None, "", "null"):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


DURATION_UNITS = (("d", 86400.0), ("h", 3600.0), ("m", 60.0),
                  ("s", 1.0), ("ms", 0.001))
# "ms" must precede "m" or "20ms" parses as 20 minutes.
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|s|m|h|d)", re.IGNORECASE)


def parse_duration(text, default=0.0):
    """'20m20s100ms' -> seconds.  A bare number is read as seconds."""
    if isinstance(text, (int, float)):
        return float(text)
    text = str(text).strip()
    if not text:
        return float(default)
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        return float(text)
    units = dict(DURATION_UNITS)
    total, matched = 0.0, False
    for value, unit in _DURATION_PART.findall(text):
        total += float(value) * units[unit.lower()]
        matched = True
    return total if matched else float(default)


def format_duration(seconds):
    """seconds -> '20m20s100ms', the shortest exact spelling."""
    remaining = float(seconds)
    if remaining <= 0:
        return "0s"
    parts = []
    for unit, size in DURATION_UNITS:
        if remaining < size - 1e-9:
            continue
        count = int(remaining / size + 1e-9)
        if count:
            parts.append(f"{count}{unit}")
            remaining -= count * size
    return "".join(parts) or "0s"


def bucket_key(day, granularity):
    """A `date` bucketed by day/week/month/year -> (sort key, short label)."""
    if granularity == "week":
        start = day - timedelta(days=day.weekday())
        return start.isoformat(), start.strftime("%d %b")
    if granularity == "month":
        return day.strftime("%Y-%m"), day.strftime("%b %Y")
    if granularity == "year":
        return day.strftime("%Y"), day.strftime("%Y")
    return day.isoformat(), day.strftime("%d %b")


def read_json(path, default=None):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def dig(data, *keys, default=None):
    """Nested .get() that tolerates missing branches and nulls."""
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
    return default if data is None else data


def clamp_pct(value):
    """Clamp a percentage to 0-100, keeping two decimals.  None stays None.

    Claude reports fractions of a percent, so rounding to whole numbers threw
    away detail that matters when a limit is nearly spent.
    """
    if value is None:
        return None
    try:
        return max(0.0, min(100.0, round(float(value), 2)))
    except (TypeError, ValueError):
        return None


def esc(text):
    """Escape for Pango / SVG markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
