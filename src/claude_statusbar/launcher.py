"""Open a session in a terminal, and reveal files in a file manager.

Which terminal exists, and how it takes a command, differs on every desktop —
hence the table rather than one hardcoded call.
"""

import shutil
import subprocess
import sys
from pathlib import Path

#: (executable, argv builder).  Ordered by how likely the terminal is to be the
#: user's actual one; x-terminal-emulator is Debian's configured default.
TERMINALS = (
    ("x-terminal-emulator", lambda cmd, cwd: ["-e", *cmd]),
    ("xfce4-terminal", lambda cmd, cwd: [f"--working-directory={cwd}", "-e",
                                         " ".join(cmd)]),
    ("gnome-terminal", lambda cmd, cwd: [f"--working-directory={cwd}", "--", *cmd]),
    ("konsole", lambda cmd, cwd: ["--workdir", cwd, "-e", *cmd]),
    ("kitty", lambda cmd, cwd: ["--directory", cwd, *cmd]),
    ("alacritty", lambda cmd, cwd: ["--working-directory", cwd, "-e", *cmd]),
    ("wezterm", lambda cmd, cwd: ["start", "--cwd", cwd, "--", *cmd]),
    ("tilix", lambda cmd, cwd: ["--working-directory", cwd, "-e", " ".join(cmd)]),
    ("xterm", lambda cmd, cwd: ["-e", *cmd]),
)


def claude_command(session_id):
    claude = shutil.which("claude") or "claude"
    return [claude, "--resume", session_id]


def open_session(session_id, cwd=None):
    """Resume a session in a new terminal window.  Returns None, or an error."""
    cwd = str(cwd or Path.home())
    if not Path(cwd).is_dir():
        cwd = str(Path.home())
    command = claude_command(session_id)

    if sys.platform == "win32":
        quoted = " ".join(command)
        subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", quoted], cwd=cwd)
        return None

    if sys.platform == "darwin":
        script = (f'tell application "Terminal" to do script '
                  f'"cd {_quote(cwd)} && {" ".join(command)}"')
        subprocess.Popen(["osascript", "-e", script,
                          "-e", 'tell application "Terminal" to activate'])
        return None

    for name, build in TERMINALS:
        path = shutil.which(name)
        if not path:
            continue
        try:
            subprocess.Popen([path, *build(command, cwd)], cwd=cwd,
                             start_new_session=True)
            return None
        except OSError:
            continue
    return "No terminal emulator found (tried x-terminal-emulator, xfce4-terminal, gnome-terminal, konsole, kitty, alacritty, xterm)."


def open_folder(path):
    """Show a directory in the desktop's file manager."""
    path = str(path)
    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], start_new_session=True)
    except OSError as error:
        return str(error)
    return None


def _quote(text):
    return text.replace('"', '\\"')
