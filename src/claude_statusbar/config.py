"""Settings: the defaults live here, user overrides live in a JSON file.

Every setting is declared once, in SETTINGS.  That single declaration supplies
the default, the type, and the label/help text, so the settings window builds
itself from this list — adding a setting here makes it appear in the GUI with
no further work.

Only values that differ from the default are written to the override file, so
upgrades keep picking up new defaults.
"""

import json

from claude_statusbar.paths import CONFIG_DIR, CONFIG_FILE


class Setting:
    """One user-facing option."""

    def __init__(self, key, default, kind, label, help="", section="General",
                 minimum=0, maximum=100):
        self.key = key
        self.default = default
        self.kind = kind          # bool | int | color | text
        self.label = label
        self.help = help
        self.section = section
        self.minimum = minimum
        self.maximum = maximum


SETTINGS = [
    # ---- Panel ----------------------------------------------------------
    Setting("img_height", 22, "int", "Meter height (px)",
            "For the Xfce panel plugin, match your panel's row size minus "
            "about 2px. The tray icon scales itself to the tray.",
            "Panel", 8, 128),
    Setting("icon", "\u2733", "text", "Icon",
            "Leading glyph for the tooltip. Empty hides it.", "Panel"),
    Setting("show_tray", True, "bool", "Show the tray icon",
            "Turn off if you use the Xfce panel plugin and don't want a "
            "second icon in the system tray. Takes effect immediately; the "
            "Xfce plugin and \"Details and settings\" keep working either "
            "way.", "Panel"),

    # ---- Colours --------------------------------------------------------
    Setting("bands", [[0, "#0ca30c"], [50, "#fab219"],
                      [75, "#ec835a"], [90, "#f2555a"]],
            "bands", "Usage colours",
            "Each row paints from that percentage upward, until the next row "
            "takes over. Add or remove rows to suit.",
            "Colours"),
    Setting("warn_color", "#fab219", "color", "Attention colour",
            "Used when the numbers are stale or capture isn't running.",
            "Colours"),
    Setting("img_label", "#a3a3a3", "color", "Labels and countdowns",
            "", "Colours"),
    Setting("img_track", "#4d4d4d", "color", "Meter track", "", "Colours"),

    # ---- Behaviour ------------------------------------------------------
    Setting("start_minimised", True, "bool", "Start in the tray only",
            "Off opens the window as well when the tray app starts.",
            "Behaviour"),
    Setting("refresh", "20s", "duration", "Refresh every",
            "How often the tray icon and open windows re-read the state. "
            "Write durations as 20s, 5m, 1h30m, or 20m20s100ms.",
            "Behaviour"),
    Setting("stale", "5m", "duration", "Call the numbers old after",
            "", "Behaviour"),
    Setting("state_keep", "1d", "duration", "Forget a session's snapshot after",
            "Old snapshots describe windows that have already reset.",
            "Behaviour"),
    Setting("session_active", "3m", "duration",
            "A session counts as live if its log moved within", "", "Behaviour"),
    Setting("live_tokens", True, "bool", "Count today's tokens from session logs",
            "Claude's own stats cache refreshes lazily and can lag by days.",
            "Behaviour"),
    Setting("check_updates", True, "bool", "Check for updates",
            "Asks GitHub once a day whether a newer release exists. This is "
            "the only time the program uses the network; nothing about your "
            "usage is ever sent.",
            "Behaviour"),
    Setting("claude_dir", "", "path", "Claude data directory",
            "Empty means ~/.claude. Takes effect when the app restarts.",
            "Behaviour"),
    Setting("wk_session_number", 0, "int",
            "Current 5h session number this week",
            "The weekly-burn projection prefers real closed 5h windows, and "
            "falls back to a slope estimate that needs two snapshots 15+ "
            "minutes apart. Early in the week — or early in a session — "
            "neither may exist yet, so the projection stays blank. Set this "
            "to which 5h session you're in right now since the weekly "
            "window last reset (1 = the first) and the projection divides "
            "your current weekly usage by the number completed before this "
            "one, so it works from the first reading instead of waiting. "
            "Updates itself from here on as real sessions close — the "
            "Overview tab shows the live count. Leave at 0, or just ignore "
            "it, to use the automatic estimate only.",
            "Behaviour", 0, 50),
    Setting("wk_session_percent", 0, "int",
            "Weekly % one 5h session costs (0 = auto)",
            "Overrides the burn-rate estimate outright: if you already know "
            "roughly what a fully-used 5h session costs against the weekly "
            "allowance — from experience, or because usage varies by model "
            "or task in a way the automatic estimate can't see — put that "
            "number here and every projection (sessions left, the weekly "
            "boundary marks, the waste meter) uses it directly instead of "
            "guessing from history. Leave at 0 to use the automatic figure "
            "shown live on the Overview tab.",
            "Behaviour", 0, 100),
    Setting("perfect_use", False, "bool",
            "Perfect Use — never let weekly usage go to waste",
            "The weekly allowance is spent in 5h chunks, so every hour a "
            "window sits unopened is allowance that will never be spent —"
            "the moment one looks fresh and unopened, this runs one "
            "throwaway \"Hi Claude\" against the cheapest model in the "
            "background, purely to start its clock right away instead of "
            "whenever you next happen to open Claude Code. Critical: when a "
            "window is deep into its 5h with little of it spent, you get a "
            "tray notification telling you to start using tokens right "
            "away, because whatever is unspent at the reset is forfeited, "
            "not carried over to the week. Needs the `claude` CLI on PATH.",
            "Behaviour"),
]


_BY_KEY = {s.key: s for s in SETTINGS}
DEFAULTS = {s.key: s.default for s in SETTINGS}


def load():
    """Defaults with the user's overrides applied on top."""
    values = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE) as fh:
            saved = json.load(fh)
        if isinstance(saved, dict):
            for key, value in saved.items():
                if key not in values:
                    continue
                if type(value) is type(values[key]):
                    values[key] = value
                elif _BY_KEY[key].kind == "duration":
                    values[key] = str(value)
    except (OSError, ValueError):
        pass
    return values


def save(values):
    """Persist only what differs from the defaults."""
    overrides = {k: v for k, v in values.items()
                 if k in DEFAULTS and v != DEFAULTS[k]}
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(overrides, indent=2, ensure_ascii=False))
    tmp.replace(CONFIG_FILE)
    return overrides


def setting(key):
    return _BY_KEY[key]


def seconds(key):
    """A duration setting as a number of seconds."""
    from claude_statusbar.util import parse_duration

    return parse_duration(cfg.get(key), parse_duration(DEFAULTS[key]))


#: The live configuration, read once per process.
cfg = load()


def reload():
    """Re-read the file in place (the GUI calls this after saving)."""
    cfg.clear()
    cfg.update(load())
    return cfg
