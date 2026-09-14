"""Perfect Use: never let the weekly allowance go to waste.

The week is spent in 5h chunks, and each one is a hard "use it or lose it" —
whatever a window's allowance doesn't get used before its reset is gone, not
carried over into the rest of the week. Two halves of keeping that from
happening:

  1. The moment a window looks fresh (nobody has sent it a message yet), fire
     one throwaway "Hi Claude" at the cheapest model. That is what actually
     starts its clock, so the 5h countdown begins right away instead of
     whenever you next happen to open Claude Code — every hour it sits
     unopened is weekly allowance that will never be spent.
  2. If a window is most of the way through its 5h and usage is still low,
     say so. That is the same waste arriving from the other end: once the
     reset hits, whatever was left unspent is forfeited for the week.

Both are no-ops unless the "Perfect Use" setting is on.
"""

import json
import shutil
import subprocess

from claude_statusbar.config import cfg
from claude_statusbar.paths import CACHE_DIR
from claude_statusbar.util import dur, read_json

STATE_FILE = CACHE_DIR / "perfect-use.json"

#: Cheapest current model — this call exists only to start the clock, so it
#: should cost as close to nothing as possible.
CHEAP_MODEL = "claude-haiku-4-5-20251001"

#: A real 5h window cannot roll over faster than this, so nothing legitimate
#: is missed by refusing to fire the starter again inside this gap — it just
#: stops a flaky reading from spawning a second process for the same window.
MIN_RESTART_GAP = 4 * 3600 + 30 * 60

#: "Critical" means both: little of the window's clock is left, AND little of
#: its allowance has been spent — the two facts together mean tokens are
#: about to be forfeited, not just that a session is old.
CRITICAL_SECONDS_LEFT = 30 * 60
CRITICAL_USE_BELOW = 20.0


def _state():
    return read_json(STATE_FILE, {}) or {}


def _save(state):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        tmp.replace(STATE_FILE)
    except OSError:
        pass


def _start_session():
    claude = shutil.which("claude")
    if not claude:
        return False
    try:
        subprocess.Popen(
            [claude, "-p", "Hi Claude", "--model", CHEAP_MODEL],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def maybe_autostart(data, notify=None):
    """Fire the starter the instant a fresh, unopened window is seen."""
    if not cfg["perfect_use"]:
        return
    # h5_use is 0.0-with-no-reset only for a window nobody has touched yet
    # (see Data.__init__); any real reading (used>0 or a known reset time)
    # means a window is already open and there is nothing to start.
    if data.h5_use != 0.0 or data.h5_reset:
        return
    state = _state()
    if data.now - int(state.get("last_started") or 0) < MIN_RESTART_GAP:
        return
    if not _start_session():
        return
    state["last_started"] = data.now
    _save(state)
    if notify:
        notify("Perfect Use",
              "Started a new 5h session automatically so its share of the "
              "week isn't sitting unspent — it's ticking now, use it before "
              "it resets.")


def maybe_warn_critical(data, notify=None):
    """Once per window: flag a nearly-over session that is still lightly used."""
    if not cfg["perfect_use"] or notify is None:
        return
    if data.h5_use is None or not data.h5_reset:
        return
    remaining = data.h5_reset - data.now
    if remaining > CRITICAL_SECONDS_LEFT or data.h5_use >= CRITICAL_USE_BELOW:
        return
    state = _state()
    if state.get("warned_reset") == data.h5_reset:
        return
    notify("Perfect Use — weekly usage about to go to waste",
          f"Only {dur(remaining)} left this 5h session and just "
          f"{round(data.h5_use)}% used — start using tokens now, or that "
          "share of the week's allowance is forfeited at the reset.")
    state["warned_reset"] = data.h5_reset
    _save(state)
