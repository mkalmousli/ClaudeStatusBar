"""Tracks how much of each 5h/weekly window was actually used before it reset.

The state file only keeps recent session snapshots (state_keep prunes the
rest), so by the time a window resets its peak reading would otherwise be
lost.  This keeps a small, append-only log of closed windows instead: one
entry per reset, with the highest usage percentage ever seen in it.  That is
what lets the History tab show, over months or years, how much allowance was
left unused at each reset — "wasted" usage.
"""

import json

from claude_statusbar.locking import exclusive, replace_atomic
from claude_statusbar.paths import claude_dir
from claude_statusbar.util import read_json

#: Windows this old are dropped from the closed log, so it cannot grow
#: forever.  5h windows roll over ~4380 times a year; two years of them is a
#: file of a few hundred KB at most.
KEEP_CLOSED = 2 * 365 * 86400


def history_file():
    return claude_dir() / "statusbar-history.json"


def _empty():
    return {"open": {}, "closed": []}


def record(snapshot, now):
    """Fold one snapshot into the tracked windows, closing any that rolled.

    `snapshot` is whatever capture.store() just wrote for a session: it may
    carry h5/wk usage for either or both windows.  Called on every capture,
    so windows close the moment a later snapshot proves the reset happened.
    """
    path = history_file()
    try:
        with exclusive(path.with_suffix(".lock")):
            state = read_json(path, None)
            if not isinstance(state, dict) or "open" not in state:
                state = _empty()
            open_windows = state.setdefault("open", {})
            closed = state.setdefault("closed", [])

            changed = False
            for kind, used_key, reset_key in (
                ("h5", "h5_used", "h5_reset"),
                ("wk", "wk_used", "wk_reset"),
            ):
                used = snapshot.get(used_key)
                reset = snapshot.get(reset_key)
                if used is None or not reset:
                    continue
                reset = int(reset)
                current = open_windows.get(kind)
                if current and int(current["reset"]) != reset:
                    if int(current["reset"]) <= now:
                        entry = {
                            "kind": kind,
                            "reset": int(current["reset"]),
                            "peak": float(current["peak"]),
                        }
                        # For a closed 5h window, also note where the weekly
                        # meter stood at that moment: this is what lets the
                        # Overview draw a fixed line at each real session
                        # boundary instead of an evenly-spaced guess.
                        if kind == "h5" and snapshot.get("wk_used") is not None:
                            entry["wk_at_close"] = float(snapshot["wk_used"])
                        closed.append(entry)
                    current = None
                if current is None:
                    current = {"reset": reset, "peak": float(used)}
                    open_windows[kind] = current
                    changed = True
                elif float(used) > current["peak"]:
                    current["peak"] = float(used)
                    changed = True

            if changed:
                cutoff = now - KEEP_CLOSED
                closed[:] = [c for c in closed if c["reset"] >= cutoff]
                closed.sort(key=lambda c: c["reset"])
                tmp = path.with_suffix(".tmp")
                tmp.write_text(json.dumps(state))
                replace_atomic(tmp, path)
    except OSError:
        pass


#: A weekly window is exactly this long, so its start is `wk_reset` minus one.
WEEK_SECONDS = 7 * 86400


def session_boundaries(wk_reset):
    """Cumulative weekly-% reading at each 5h session that has closed this week.

    Sorted oldest first, e.g. [23.0, 41.0] means the first session of the
    week ended at 23% of the weekly allowance and the second at 41% — fixed
    points from what actually happened, not a projection.
    """
    if not wk_reset:
        return []
    week_start = wk_reset - WEEK_SECONDS
    rows = [
        r for r in closed_windows("h5")
        if r.get("wk_at_close") is not None and week_start <= r.get("reset", 0) <= wk_reset
    ]
    return [float(r["wk_at_close"]) for r in rows]


def closed_windows(kind=None):
    """Every window that has finished, oldest first: [{kind, reset, peak}]."""
    state = read_json(history_file(), None)
    if not isinstance(state, dict):
        return []
    rows = state.get("closed") or []
    if kind:
        rows = [r for r in rows if r.get("kind") == kind]
    return sorted(rows, key=lambda r: r.get("reset", 0))
