"""Turn the stored snapshots into the numbers everything else displays."""

import json
import time
from datetime import date, datetime

from claude_statusbar import config, history
from claude_statusbar.config import cfg
from claude_statusbar.paths import (CACHE_DIR, projects_dir, state_file,
                                    stats_file, statusline_script)
from pathlib import Path

from claude_statusbar.util import (bucket_key, clamp_pct, countdown, dig, dur,
                                   now, read_json, today, week_ago)


def account():
    """Whatever Claude Code knows about the signed-in account.

    Read from ~/.claude.json, which is where the CLI caches the profile it
    fetched; there is nothing about the account in the statusline payload.
    """
    from pathlib import Path

    raw = read_json(Path.home() / ".claude.json", {}) or {}
    oauth = raw.get("oauthAccount") or {}
    if not oauth:
        return {}
    plan = (oauth.get("organizationType") or "").replace("claude_", "").replace("_", " ")
    return {
        "Name": oauth.get("fullName") or oauth.get("displayName") or "",
        "Email": oauth.get("emailAddress") or "",
        "Plan": plan.title(),
        "Organisation": oauth.get("organizationName") or "",
        "Role": (oauth.get("organizationRole") or "").title(),
        "Billing": (oauth.get("billingType") or "").replace("_", " ").title(),
        "Extra usage": "enabled" if oauth.get("hasExtraUsageEnabled") else "off",
        "Member since": (oauth.get("accountCreatedAt") or "")[:10],
    }


#: Parsed session logs, keyed by path -> (mtime, size, metadata).  Reading a
#: few hundred lines of every log on each refresh would be wasteful, and the
#: interesting fields are all near the top of the file.
_META_CACHE = {}
_META_LINES = 200
_NOISE_PREFIXES = ("<local-command-caveat>", "<command-name>", "<command-message>",
                   "<system-reminder>", "Caveat:")


def _first_prompt(record):
    """The text of a user turn, if it is one a person actually typed."""
    if record.get("type") != "user":
        return None
    content = (record.get("message") or {}).get("content")
    if isinstance(content, list):
        content = next((part.get("text") for part in content
                        if isinstance(part, dict) and part.get("type") == "text"), None)
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text or text.startswith(_NOISE_PREFIXES):
        return None
    return " ".join(text.split())[:70]


def session_meta(session_id):
    """Where a session ran, on what branch, and something to call it."""
    log = None
    try:
        log = next(projects_dir().rglob(f"{session_id}.jsonl"), None)
    except OSError:
        pass
    if log is None:
        return {"name": "", "cwd": "", "branch": "", "log": None}

    try:
        stat = log.stat()
        stamp = (stat.st_mtime, stat.st_size)
    except OSError:
        return {"name": "", "cwd": "", "branch": "", "log": None}

    cached = _META_CACHE.get(log)
    if cached and cached[0] == stamp:
        return cached[1]

    cwd = branch = summary = prompt = ""
    try:
        with open(log, errors="replace") as handle:
            for index, line in enumerate(handle):
                if index >= _META_LINES:
                    break
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                cwd = cwd or record.get("cwd") or ""
                branch = branch or record.get("gitBranch") or ""
                if not summary and record.get("type") == "summary":
                    summary = str(record.get("summary") or "")[:70]
                if not prompt:
                    prompt = _first_prompt(record) or ""
    except OSError:
        pass

    meta = {
        "name": summary or prompt or (Path(cwd).name if cwd else ""),
        "cwd": cwd,
        "branch": branch,
        "log": log,
    }
    _META_CACHE[log] = (stamp, meta)
    return meta


def hook_present():
    """Is capture wired up — either spliced into statusline.sh, or set as
    Claude Code's own statusLine command (the portable route)?"""
    try:
        if "claude-statusbar capture" in statusline_script().read_text():
            return True
    except OSError:
        pass
    try:
        from claude_statusbar.paths import claude_settings

        return "claude-statusbar" in claude_settings().read_text()
    except OSError:
        return False


class Data:
    """Everything the panel, the terminal view and the GUI read."""

    def __init__(self):
        self.now = now()          # one clock reading, so the fields agree
        self._log_cache = None
        stored = read_json(state_file(), {}) or {}
        sessions = stored.get("sessions")
        self.sessions = sessions if isinstance(sessions, dict) else {}
        records = [r for r in self.sessions.values()
                   if isinstance(r, dict) and r.get("ts")]
        self.records = records

        newest = max(records, key=lambda r: int(r.get("ts") or 0), default={})
        self.ts = int(newest.get("ts") or 0)
        self.age = max(0, self.now - self.ts) if self.ts else 0
        self.have_state = self.ts > 0

        # Snapshots older than state_keep describe windows that reset long ago.
        # Kept only as a fallback so a long-idle setup can still report its age.
        self.recent = [r for r in records
                       if self.now - int(r.get("ts") or 0) < config.seconds("state_keep")] or records

        self.model = newest.get("model") or ""
        self.cost = self._highest("cost")
        self.ctx_in = self._highest("ctx_in")
        self.ctx_out = self._highest("ctx_out")
        self.ctx_win = self._highest("ctx_win", 200000)
        self.ctx_use = clamp_pct(self._highest("ctx_used", None)) if self.have_state else None
        self.ctx_rem = None if self.ctx_use is None else 100 - self.ctx_use

        self.credits = self._highest("credits", None)
        self.credit_limit = self._highest("credit_limit", None)
        self.credit_use = self._highest("credit_use", None)
        self.credit_currency = newest.get("credit_currency") or "USD"
        self.credits_mode = self.credits is not None or self.credit_limit is not None
        if self.credit_use is None and self.credits is not None and self.credit_limit:
            self.credit_use = float(self.credits) / float(self.credit_limit) * 100

        h5 = self.current(self.recent, "h5_used", "h5_reset")
        wk = self.current(self.recent, "wk_used", "wk_reset")
        self.h5_use = clamp_pct(h5.get("h5_used")) if h5 else None
        self.wk_use = clamp_pct(wk.get("wk_used")) if wk else None
        self.h5_rem = None if self.h5_use is None else 100 - self.h5_use
        self.wk_rem = None if self.wk_use is None else 100 - self.wk_use

        # The countdown comes from the same snapshot as its percentage, so the
        # two can never describe different windows.
        self.h5_reset = int(h5.get("h5_reset") or 0) if h5 else 0
        self.wk_reset = int(wk.get("wk_reset") or 0) if wk else 0
        self.h5_cd = countdown(self.h5_reset)
        self.wk_cd = countdown(self.wk_reset)

        self.wk_burn_5h = self._wk_burn_5h()
        self.wk_sessions_left = (
            self.wk_rem / self.wk_burn_5h
            if self.wk_burn_5h and self.wk_rem is not None else None)

        self.fresh = self.have_state and self.age < config.seconds("stale")
        self.live = self._session_live()
        self.note, self.note_warn = self._age_note()
        self._history()

    # -- aggregation ------------------------------------------------------
    def _highest(self, name, default=0):
        values = [r.get(name) for r in self.recent if r.get(name) is not None]
        return max(values, default=default)

    @staticmethod
    def current(records, used_key, reset_key):
        """The account's standing in the window we are in right now.

        Two things make this harder than reading the latest write.  Concurrent
        sessions re-render at different moments, so the newest *write* is not
        the newest *reading*: a session that hasn't refreshed reports an older,
        lower number, and taking it makes the meter jump backwards.  Within one
        window usage only ever climbs, so the highest reading in the current
        window is the freshest one.

        The other half is which window a snapshot belongs to.  Anything past
        its reset is discarded — that usage was wiped at the rollover, and
        letting such a record speak for the present would pin the meter at its
        old peak.  Of what remains, the latest reset time identifies the
        current window, and only its snapshots are compared, so a session still
        reporting the previous window cannot leak in.
        """
        usable = [
            r for r in records
            if r.get(used_key) is not None
            and not (int(r.get(reset_key) or 0) and int(r[reset_key]) <= now())
        ]
        if not usable:
            return None
        window = max(int(r.get(reset_key) or 0) for r in usable)
        if window:
            usable = [r for r in usable if int(r.get(reset_key) or 0) == window]
        return max(usable, key=lambda r: (float(r[used_key]), int(r.get("ts") or 0)))

    #: Look-back for the "how fast is the weekly limit burning" estimate — one
    #: 5-hour session — and the least elapsed time that makes the slope worth
    #: trusting (below this a few noisy minutes would dominate).
    BURN_WINDOW = 5 * 3600
    BURN_MIN_ELAPSED = 15 * 60

    def _wk_burn_5h(self):
        """Weekly limit a single 5h session burns, from the recent snapshots.

        Walks the weekly-meter readings in the current weekly window over the
        last five hours and scales the rise up to a full 5h session, so the
        overview can mark how many more sessions fit in what is left.
        """
        if self.wk_use is None or not self.wk_reset:
            return None
        points = sorted(
            (int(r["ts"]), clamp_pct(r.get("wk_used")))
            for r in self.records
            if r.get("wk_used") is not None and int(r.get("ts") or 0)
            and int(r.get("wk_reset") or 0) == self.wk_reset
        )
        if len(points) < 2:
            return None
        recent = [p for p in points if p[0] >= self.now - self.BURN_WINDOW] or points
        base_ts, base_use = recent[0]
        last_ts, last_use = points[-1]
        elapsed = last_ts - base_ts
        rise = last_use - base_use
        if elapsed < self.BURN_MIN_ELAPSED or rise <= 0:
            return None
        return min(100.0, rise * self.BURN_WINDOW / elapsed)

    # -- liveness ---------------------------------------------------------
    def _logs(self):
        """Every session log with its mtime, walked once and reused."""
        if self._log_cache is None:
            found = []
            try:
                for path in projects_dir().rglob("*.jsonl"):
                    try:
                        found.append((path, path.stat().st_mtime))
                    except OSError:
                        continue
            except OSError:
                pass
            self._log_cache = found
        return self._log_cache

    def _session_live(self):
        """A session log touched recently is the only honest liveness signal.

        Claude Code re-runs the statusline on conversation activity, not on a
        timer, so the state file's age says nothing on its own.
        """
        newest = max((mtime for _path, mtime in self._logs()), default=0)
        return bool(newest) and (self.now - newest) < config.seconds("session_active")

    def _age_note(self):
        """Caption for the numbers' age.  Only a real problem earns a warning."""
        stale = config.seconds("stale")
        if not self.have_state:
            if not hook_present():
                return "capture not wired up — run the installer", True
            return "", False
        if self.live and self.age >= stale and not hook_present():
            return "capture not wired up — run the installer", True
        if self.live:
            return (f"updated {dur(self.age)} ago", False) if self.age >= 90 else ("", False)
        if self.age >= stale:
            return f"no session open · {dur(self.age)} old", True
        if self.age >= 90:
            return f"updated {dur(self.age)} ago", False
        return "", False

    # -- history ----------------------------------------------------------
    def _history(self):
        self.today_tok = self.today_msg = self.today_ses = 0
        self.week_tok = self.total_msg = self.total_ses = 0
        self.today_by_model = {}

        stats = read_json(stats_file(), {}) or {}
        for row in stats.get("dailyActivity") or []:
            if row.get("date") == today():
                self.today_msg = row.get("messageCount", 0)
                self.today_ses = row.get("sessionCount", 0)
        for row in stats.get("dailyModelTokens") or []:
            by_model = row.get("tokensByModel") or {}
            total = sum(by_model.values())
            if row.get("date") == today():
                self.today_tok += total
                self.today_by_model = dict(by_model)
            if (row.get("date") or "") >= week_ago():
                self.week_tok += total
        self.total_msg = stats.get("totalMessages", 0)
        self.total_ses = stats.get("totalSessions", 0)
        self.stats_date = stats.get("lastComputedDate") or ""

        if cfg["live_tokens"]:
            live = self._live_tokens()
            if live > self.today_tok:
                self.today_tok = live

    #: Today's logs are megabytes of JSON.  Re-parsing them on every refresh
    #: dominated the panel's cost, and the number barely moves between ticks,
    #: so the total is cached and recomputed at most this often.
    LIVE_TOKEN_TTL = 60

    def _live_tokens(self):
        """Claude's stats cache refreshes lazily; today's logs are the truth."""
        cache_file = CACHE_DIR / "today-tokens.json"
        cached = read_json(cache_file, {}) or {}
        if (cached.get("date") == today()
                and self.now - int(cached.get("computed") or 0) < self.LIVE_TOKEN_TTL):
            return int(cached.get("tokens") or 0)

        total = self._scan_live_tokens()
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            tmp = cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps({"date": today(), "computed": self.now,
                                       "tokens": total}))
            tmp.replace(cache_file)
        except OSError:
            pass
        return total

    def _scan_live_tokens(self):
        midnight = time.mktime(date.today().timetuple())
        total = 0
        for path, mtime in self._logs():
            if mtime < midnight:
                continue
            try:
                with open(path, errors="replace") as fh:
                    for line in fh:
                        if today() not in line:
                            continue
                        try:
                            record = json.loads(line)
                        except ValueError:
                            continue
                        if not str(record.get("timestamp") or "").startswith(today()):
                            continue
                        usage = dig(record, "message", "usage", default={}) or {}
                        total += sum(
                            usage.get(k, 0) or 0
                            for k in ("input_tokens", "output_tokens",
                                      "cache_read_input_tokens",
                                      "cache_creation_input_tokens")
                        )
            except OSError:
                continue
        return total

    # -- for the History tab -----------------------------------------------
    def token_series(self, granularity="day"):
        """Total tokens per day/week/month/year, oldest first.

        [(sort_key, label, tokens)]. Sourced from Claude Code's own stats
        cache, which is the only place token counts survive longer than the
        state file's pruning window.
        """
        stats = read_json(stats_file(), {}) or {}
        buckets = {}
        for row in stats.get("dailyModelTokens") or []:
            raw = row.get("date")
            if not raw:
                continue
            try:
                day = date.fromisoformat(raw)
            except ValueError:
                continue
            key, label = bucket_key(day, granularity)
            total = sum((row.get("tokensByModel") or {}).values())
            entry = buckets.setdefault(key, [label, 0])
            entry[1] += total
        return [(key, label, tokens)
               for key, (label, tokens) in sorted(buckets.items())]

    def activity_series(self, granularity="day"):
        """Messages and sessions per bucket, oldest first.

        [(sort_key, label, messages, sessions)].
        """
        stats = read_json(stats_file(), {}) or {}
        buckets = {}
        for row in stats.get("dailyActivity") or []:
            raw = row.get("date")
            if not raw:
                continue
            try:
                day = date.fromisoformat(raw)
            except ValueError:
                continue
            key, label = bucket_key(day, granularity)
            entry = buckets.setdefault(key, [label, 0, 0])
            entry[1] += row.get("messageCount", 0) or 0
            entry[2] += row.get("sessionCount", 0) or 0
        return [(key, label, msgs, sessions)
               for key, (label, msgs, sessions) in sorted(buckets.items())]

    def waste_series(self, kind="h5", granularity="day"):
        """Unused allowance per bucket, oldest first, from closed windows.

        [(sort_key, label, avg_wasted_pct, windows_counted)]. A window only
        counts once it has actually closed (its reset has passed and a later
        snapshot proved it), so the current, still-open window never shows up
        as "wasted" — it just hasn't finished yet.
        """
        buckets = {}
        for window in history.closed_windows(kind):
            reset = window.get("reset")
            if not reset:
                continue
            day = datetime.fromtimestamp(int(reset)).date()
            key, label = bucket_key(day, granularity)
            wasted = max(0.0, 100.0 - float(window.get("peak") or 0))
            entry = buckets.setdefault(key, [label, 0.0, 0])
            entry[1] += wasted
            entry[2] += 1
        return [(key, label, total / count, count)
               for key, (label, total, count) in sorted(buckets.items())]

    # -- for the GUI's drill-down ----------------------------------------
    def session_rows(self, with_meta=True):
        """One row per stored snapshot, newest first."""
        rows = []
        for sid, record in self.sessions.items():
            if not isinstance(record, dict) or not record.get("ts"):
                continue
            reset = int(record.get("h5_reset") or 0)
            meta = session_meta(sid) if with_meta else {}
            rows.append({
                "id": sid,
                "name": meta.get("name", ""),
                "cwd": meta.get("cwd", ""),
                "branch": meta.get("branch", ""),
                "log": meta.get("log"),
                "model": record.get("model") or "",
                "h5": clamp_pct(record.get("h5_used")),
                "wk": clamp_pct(record.get("wk_used")),
                "ctx": clamp_pct(record.get("ctx_used")),
                "cost": float(record.get("cost") or 0),
                "age": max(0, self.now - int(record["ts"])),
                "window": "current" if reset > self.now else ("expired" if reset else "unknown"),
                "counted": record is self.current(self.recent, "h5_used", "h5_reset"),
            })
        rows.sort(key=lambda r: r["age"])
        return rows
