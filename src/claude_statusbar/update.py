"""Check GitHub for a newer release.

This is the only thing in the program that touches the network, so it is a
setting, it is cached, and it never blocks the interface: callers run `check`
on a worker thread and the result is stored for a day.
"""

import json
import time
import urllib.error
import urllib.request

from claude_statusbar import PROJECT_URL, __version__
from claude_statusbar.paths import CACHE_DIR

RELEASES_API = "https://api.github.com/repos/mkalmousli/ClaudeStatusBar/releases/latest"
CACHE_FILE = CACHE_DIR / "update.json"
CACHE_SECONDS = 24 * 3600
TIMEOUT = 6


def _version_tuple(text):
    """'v2.1.0' -> (2, 1, 0); anything unparsable sorts lowest."""
    parts = []
    for chunk in str(text or "").lstrip("vV").split("."):
        digits = "".join(c for c in chunk if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts or [0])


def is_newer(latest, current=__version__):
    return _version_tuple(latest) > _version_tuple(current)


def cached():
    """The last result, or None.  Cheap; safe on the UI thread."""
    try:
        with open(CACHE_FILE) as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _store(result):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(result, indent=2))
    except OSError:
        pass
    return result


def check(force=False):
    """Ask GitHub for the latest release.  Blocking — call it off the UI thread.

    Returns {"latest", "url", "newer", "checked", "error"}.  A repository with
    no releases yet answers 404, which is not an error worth showing.
    """
    previous = cached()
    if not force and previous and time.time() - previous.get("checked", 0) < CACHE_SECONDS:
        return previous

    request = urllib.request.Request(
        RELEASES_API,
        headers={"Accept": "application/vnd.github+json",
                 "User-Agent": f"claude-statusbar/{__version__}"})
    result = {"checked": time.time(), "latest": "", "url": PROJECT_URL,
              "newer": False, "error": ""}
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = json.load(response)
        result["latest"] = payload.get("tag_name") or payload.get("name") or ""
        result["url"] = payload.get("html_url") or PROJECT_URL
        result["newer"] = is_newer(result["latest"])
    except urllib.error.HTTPError as error:
        result["error"] = ("no releases published yet" if error.code == 404
                           else f"GitHub returned {error.code}")
    except (urllib.error.URLError, ValueError, TimeoutError, OSError) as error:
        result["error"] = f"could not reach GitHub ({error})"
    return _store(result)


def describe(result):
    """A sentence for the About tab."""
    if not result:
        return "Not checked yet."
    if result.get("newer"):
        return f"Version {result['latest']} is available — you have {__version__}."
    if result.get("error"):
        return f"Update check failed: {result['error']}."
    if result.get("latest"):
        return f"Up to date — {__version__} is the latest release."
    return f"Up to date as far as we can tell (running {__version__})."
