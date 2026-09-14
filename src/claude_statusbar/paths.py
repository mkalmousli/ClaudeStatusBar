"""Where everything lives, on every OS.

Claude Code itself keeps ~/.claude on all three platforms, so that path is not
per-OS; our own config and cache follow the platform convention via
platformdirs (%LOCALAPPDATA% on Windows, ~/Library/... on macOS, XDG on Linux).
"""

import os
import sys
from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir, user_data_dir

APP_NAME = "claude-statusbar"
APP_ID = "io.github.mkalmousli.ClaudeStatusBar"

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"
LINUX = not WINDOWS and not MACOS

CONFIG_DIR = Path(user_config_dir(APP_NAME, roaming=True))
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR = Path(user_cache_dir(APP_NAME))
DATA_DIR = Path(user_data_dir(APP_NAME, roaming=True))


def claude_dir():
    """Claude Code's data directory; CLAUDE_DIR wins, then the setting."""
    from claude_statusbar.config import cfg

    return Path(os.environ.get("CLAUDE_DIR") or cfg["claude_dir"]
                or (Path.home() / ".claude"))


def state_file():
    return claude_dir() / "statusbar-state.json"


def stats_file():
    return claude_dir() / "stats-cache.json"


def statusline_script():
    return claude_dir() / "statusline.sh"


def claude_settings():
    return claude_dir() / "settings.json"


def projects_dir():
    return claude_dir() / "projects"


def _find_logo():
    """logo.svg lives at the repository root, where the README can show it.

    A built install gets a copy inside the package, so look there first and
    fall back to the checkout — which is how `make install` sets things up.
    """
    here = Path(__file__).resolve().parent
    for candidate in (here / "assets" / "logo.svg",
                      here.parent.parent / "logo.svg"):
        if candidate.is_file():
            return candidate
    return here / "assets" / "logo.svg"


LOGO = _find_logo()

HOOK_MARK = "# >>> claude-statusbar capture >>>"
HOOK_END = "# <<< claude-statusbar capture <<<"

# xfce4-panel compiles its plugin search path in (see panel-module-factory.c)
# and never consults XDG_DATA_HOME, so the .desktop has to land in a system
# directory — that part needs root.  The launcher it points at does not.
XFCE_SYSTEM_PLUGIN_DIR = Path("/usr/share/xfce4/panel/plugins")
XFCE_PLUGIN_DESKTOP = XFCE_SYSTEM_PLUGIN_DIR / "claude-statusbar.desktop"
XFCE_STALE_USER_DESKTOP = (Path.home()
                           / ".local/share/xfce4/panel/plugins/claude-statusbar.desktop")
XFCE_PLUGIN_SCRIPT = DATA_DIR / "xfce-panel-launcher"

AUTOSTART_DIR = Path.home() / ".config/autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "claude-statusbar.desktop"

APPLICATIONS_DIR = Path.home() / ".local/share/applications"
APPLICATIONS_FILE = APPLICATIONS_DIR / "claude-statusbar.desktop"
DESKTOP_FILE = Path.home() / "Desktop" / "claude-statusbar.desktop"
