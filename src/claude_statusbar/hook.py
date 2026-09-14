"""Wire capture into Claude Code, on any platform.

Two routes.  Where Claude Code already runs a POSIX statusline script we splice
a line into it, so the user keeps the status line they had.  Otherwise — no
script, or Windows, where there is none — we become Claude's statusLine command
ourselves and print a compact line.
"""

import json
import re
import sys
from pathlib import Path

from claude_statusbar.paths import (HOOK_END, HOOK_MARK, WINDOWS,
                                    claude_settings, statusline_script)


def executable():
    """How to invoke this install from a config file."""
    script = Path(sys.argv[0]).resolve()
    if script.suffix == ".py":          # running from a checkout
        return f'"{sys.executable}" -m claude_statusbar'
    return f'"{script}"' if " " in str(script) else str(script)


def _hook_block():
    return (f"{HOOK_MARK}\n"
            f'[ -n "${{input:-}}" ] && printf \'%s\' "$input" | {executable()} '
            f"--capture >/dev/null 2>&1 || true\n"
            f"{HOOK_END}\n")


def spliced():
    try:
        return HOOK_MARK in statusline_script().read_text()
    except OSError:
        return False


def _read_settings():
    path = claude_settings()
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _write_settings(data):
    path = claude_settings()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def claimed():
    """Are we Claude Code's statusLine command?"""
    command = (_read_settings().get("statusLine") or {}).get("command") or ""
    return "claude-statusbar" in command


def install():
    """Splice into an existing POSIX statusline, else claim statusLine."""
    script = statusline_script()

    if not WINDOWS and script.exists():
        text = script.read_text()
        if HOOK_MARK in text:
            pattern = re.compile(re.escape(HOOK_MARK) + r".*?" + re.escape(HOOK_END) + r"\n?",
                                 re.S)
            fresh = _hook_block()
            current = pattern.search(text)
            if current and current.group(0) == fresh:
                print(f"capture: already hooked into {script}")
                return 0
            # The path baked into the existing block (e.g. a venv that moved)
            # no longer matches what we would install now — refresh it in
            # place rather than silently leaving the stale command behind.
            script.write_text(pattern.sub(fresh, text))
            print(f"capture: refreshed the hook in {script}")
            return 0
        if re.search(r"^\s*input=\$\(cat\)", text, re.M):
            backup = script.with_suffix(".sh.csb-bak")
            backup.write_text(text)
            lines = text.splitlines(keepends=True)
            for index, line in enumerate(lines):
                if re.match(r"\s*input=\$\(cat\)", line):
                    lines.insert(index + 1, _hook_block())
                    break
            script.write_text("".join(lines))
            script.chmod(0o755)
            print(f"capture: hooked into {script}  (backup: {backup.name})")
            return 0

    # No script to splice into (or Windows): become the status line.
    settings = _read_settings()
    existing = settings.get("statusLine") or {}
    command = existing.get("command") or ""
    fresh_command = f"{executable()} --statusline"
    if "claude-statusbar" in command:
        if command == fresh_command:
            print("capture: already set as Claude Code's statusLine command")
            return 0
        # Same situation as the spliced case: the command points at a path
        # (e.g. a venv) that no longer matches this install.
        settings["statusLine"] = {"type": "command", "command": fresh_command,
                                  "refreshInterval": 3}
        _write_settings(settings)
        print(f"capture: refreshed the statusLine command in {claude_settings()}")
        return 0
    if command:
        settings["statusLineBackupByClaudeStatusbar"] = existing
        print(f"capture: replacing the existing statusLine command\n"
              f"         (saved as statusLineBackupByClaudeStatusbar)")
    settings["statusLine"] = {"type": "command", "command": fresh_command,
                              "refreshInterval": 3}
    _write_settings(settings)
    print(f"capture: set as Claude Code's statusLine command in {claude_settings()}")
    return 0


def remove():
    removed = False
    script = statusline_script()
    if spliced():
        kept, skipping = [], False
        for line in script.read_text().splitlines(keepends=True):
            if line.strip() == HOOK_MARK:
                skipping = True
                continue
            if line.strip() == HOOK_END:
                skipping = False
                continue
            if not skipping:
                kept.append(line)
        script.write_text("".join(kept))
        print(f"capture: unhooked from {script}")
        removed = True

    if claimed():
        settings = _read_settings()
        restored = settings.pop("statusLineBackupByClaudeStatusbar", None)
        if restored:
            settings["statusLine"] = restored
            print("capture: restored the previous statusLine command")
        else:
            settings.pop("statusLine", None)
            print("capture: removed our statusLine command")
        _write_settings(settings)
        removed = True

    if not removed:
        print("capture: nothing wired up")
    return 0
