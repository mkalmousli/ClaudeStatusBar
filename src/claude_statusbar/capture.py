"""Read Claude Code's statusline JSON and stash it for the panel.

Rate limits only exist inside a running session, so the hook in statusline.sh
pipes Claude's JSON through here.  stdin is echoed back untouched so the hook
can sit in the middle of an existing statusline without disturbing it.
"""

import json
import sys

from claude_statusbar import config
from claude_statusbar.locking import exclusive, replace_atomic
from claude_statusbar.paths import state_file
from claude_statusbar.util import as_epoch, dig, now, read_json

#: Fields carried forward when a payload omits them (Claude drops optional
#: blocks when a mode changes; losing them would blank the panel).
CARRIED = (
    "ts", "ctx_used", "ctx_in", "ctx_out", "ctx_win", "h5_used", "wk_used",
    "h5_reset", "wk_reset", "model", "cost", "credits", "credit_limit",
    "credit_use", "credit_currency",
)


def _rate_used(payload, bucket):
    """Percentage used for a rate-limit bucket, however it is spelled."""
    value = dig(payload, "rate_limits", bucket, "used_percentage", default=None)
    if value is None:
        value = dig(payload, "rate_limits", bucket, "utilization", default=None)
        if value is None:
            return None
        try:
            if float(value) <= 1:            # a 0-1 fraction, not a percentage
                value = float(value) * 100
        except (TypeError, ValueError):
            pass
    return value


def snapshot_from(payload):
    return {
        "ts": now(),
        "ctx_used": dig(payload, "context_window", "used_percentage", default=0),
        "ctx_in": dig(payload, "context_window", "total_input_tokens", default=0),
        "ctx_out": dig(payload, "context_window", "total_output_tokens", default=0),
        "ctx_win": dig(payload, "context_window", "context_window_size", default=0),
        "h5_used": _rate_used(payload, "five_hour"),
        "wk_used": _rate_used(payload, "seven_day"),
        "h5_reset": as_epoch(dig(payload, "rate_limits", "five_hour", "resets_at")),
        "wk_reset": as_epoch(dig(payload, "rate_limits", "seven_day", "resets_at")),
        "model": dig(payload, "model", "display_name", default=""),
        "cost": dig(payload, "cost", "total_cost_usd", default=0),
        "credits": dig(payload, "extra_usage", "credits_used", default=None),
        "credit_limit": dig(payload, "extra_usage", "monthly_limit", default=None),
        "credit_use": dig(payload, "extra_usage", "utilization", default=None),
        "credit_currency": dig(payload, "extra_usage", "currency", default="USD"),
    }


def store(payload):
    """Merge one statusline payload into the shared state file."""
    session_id = str(payload.get("session_id") or payload.get("sessionId") or "default")
    snapshot = snapshot_from(payload)
    state = state_file()

    try:
        state.parent.mkdir(parents=True, exist_ok=True)
        with exclusive(state.with_suffix(".lock")):
            stored = read_json(state, {}) or {}
            sessions = stored.get("sessions")
            sessions = sessions if isinstance(sessions, dict) else {}

            previous = sessions.get(session_id)
            if isinstance(previous, dict):
                for key, value in previous.items():
                    if snapshot.get(key) is None and value is not None:
                        snapshot[key] = value

            cutoff = now() - config.seconds("state_keep")
            sessions = {k: v for k, v in sessions.items()
                        if isinstance(v, dict) and int(v.get("ts") or 0) >= cutoff}
            sessions[session_id] = snapshot

            tmp = state.with_suffix(".tmp")
            tmp.write_text(json.dumps({"sessions": sessions}, indent=2))
            replace_atomic(tmp, state)
    except OSError:
        pass
    return snapshot


def _read_payload():
    raw = sys.stdin.read()
    try:
        return raw, json.loads(raw)
    except ValueError:
        return raw, None


def capture():
    """Chained mode: store, and echo stdin so an existing statusline is intact."""
    raw, payload = _read_payload()
    sys.stdout.write(raw)
    sys.stdout.flush()
    if payload is not None:
        store(payload)
    return 0


def statusline():
    """Standalone mode: store, and print a compact line for Claude to display.

    Used when Claude Code has no status line of its own, on any platform —
    there is no shell script to splice into on Windows.
    """
    _raw, payload = _read_payload()
    if payload is None:
        return 0
    store(payload)

    from claude_statusbar.data import Data
    from claude_statusbar.render import limit_rows
    from claude_statusbar.util import pct

    data = Data()
    print("  ".join(f"{label} {pct(used)}" for label, used, _cd in limit_rows(data)))
    return 0
