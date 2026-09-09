"""Desktop integration: the Xfce panel plugin and the autostart entry.

Written in Python rather than a Makefile so Windows and macOS users get the
same `claude-statusbar --install` as everyone else.
"""

import os
import shutil
import stat
import subprocess
import sys

from pathlib import Path

from claude_statusbar.paths import (LOGO, AUTOSTART_DIR, AUTOSTART_FILE, DATA_DIR,
                                    LINUX, MACOS, WINDOWS, XFCE_PLUGIN_DESKTOP,
                                    XFCE_PLUGIN_SCRIPT, XFCE_STALE_USER_DESKTOP,
                                    XFCE_SYSTEM_PLUGIN_DIR)

AUTOSTART_DESKTOP = """[Desktop Entry]
Type=Application
Name=Claude Status Bar
Comment=Claude Code usage meter in the system tray
Exec={exec} --tray
Icon={icon}
Terminal=false
X-GNOME-Autostart-enabled=true
"""


def desktop_environment():
    """Best-effort name of the running desktop."""
    for variable in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        value = os.environ.get(variable, "")
        if value:
            return value.lower()
    return ""


def is_xfce():
    return "xfce" in desktop_environment()


def _tray_command():
    launcher = shutil.which("claude-statusbar")
    return launcher or f'"{sys.executable}" -m claude_statusbar'


def _copy_as_root(source, target):
    """Place a built file in a root-owned directory, asking for sudo if needed."""
    if os.access(target.parent, os.W_OK):
        shutil.copy2(source, target)
        return True
    if not shutil.which("sudo"):
        return False
    return subprocess.run(["sudo", "install", "-m", "0644",
                           str(source), str(target)]).returncode == 0


def _write_as_root(path, text):
    """Place a file in a root-owned directory, asking for sudo if needed."""
    if os.access(path.parent, os.W_OK):
        path.write_text(text)
        return True
    if not shutil.which("sudo"):
        return False
    print(f"Registering the panel plugin in {path.parent} needs root:")
    result = subprocess.run(["sudo", "tee", str(path)],
                            input=text.encode(), stdout=subprocess.DEVNULL)
    return result.returncode == 0


SOURCE_DIR = Path(__file__).resolve().parent.parent.parent / "native" / "xfce"
BUILD_PACKAGES = "gcc pkg-config libgtk-3-dev libxfce4panel-2.0-dev"


def _pkg_config(*args):
    result = subprocess.run(["pkg-config", *args], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def _plugin_dirs():
    """Where this distribution keeps panel modules and their .desktop files."""
    libdir = _pkg_config("--variable=libdir", "libxfce4panel-2.0")
    if not libdir:
        return None, None
    datadir = _pkg_config("--variable=datadir", "libxfce4panel-2.0") or "/usr/share"
    return (Path(libdir) / "xfce4/panel/plugins",
            Path(datadir) / "xfce4/panel/plugins")


def build_xfce_plugin(output):
    """Compile the panel module.  Returns True on success."""
    flags = _pkg_config("--cflags", "--libs", "libxfce4panel-2.0", "gtk+-3.0")
    if not flags:
        print("Missing build dependencies for the Xfce panel plugin.")
        print(f"  sudo apt install {BUILD_PACKAGES}")
        return False
    source = SOURCE_DIR / "claude-statusbar-plugin.c"
    if not source.exists():
        print(f"Plugin source not found: {source}")
        return False
    command = ["gcc", "-shared", "-fPIC", "-O2", "-Wall",
               str(source), "-o", str(output), *flags.split()]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print("Compiling the Xfce panel plugin failed:")
        print(result.stderr.strip()[:2000])
        return False
    return True


def _install_icon():
    """Put the logo where icon themes look, so the .desktop can name it."""
    if not LINUX:
        return
    target = (Path.home() / ".local/share/icons/hicolor/scalable/apps"
              / "claude-statusbar.svg")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(LOGO, target)
    except OSError:
        pass


def install_xfce_plugin():
    """Compile and register a real xfce4-panel module.

    The panel dlopens lib<module>.so and calls xfce_panel_module_construct(),
    so this genuinely has to be compiled C; the plugin itself is a thin shell
    that asks `claude-statusbar --panel` for an SVG and a tooltip.
    """
    if not LINUX:
        print("The Xfce panel plugin is Linux-only; use the tray icon instead.")
        return 1

    lib_dir, data_dir = _plugin_dirs()
    if lib_dir is None:
        print("libxfce4panel-2.0 development files not found.")
        print(f"  sudo apt install {BUILD_PACKAGES}")
        return 1

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _install_icon()
    built = DATA_DIR / "libclaude-statusbar.so"
    if not build_xfce_plugin(built):
        return 1
    print(f"compiled {built}")

    # An early version put a .desktop here; the panel never read it.
    try:
        XFCE_STALE_USER_DESKTOP.unlink()
    except OSError:
        pass

    desktop = data_dir / "claude-statusbar.desktop"
    module = lib_dir / "libclaude-statusbar.so"
    if not (_copy_as_root(built, module)
            and _write_as_root(desktop,
                               (SOURCE_DIR / "claude-statusbar.desktop").read_text())):
        print("Installing the plugin needs root for these two files:")
        print(f"  {module}")
        print(f"  {desktop}")
        print("Re-run where sudo can prompt, or use the tray icon instead:")
        print("  claude-statusbar --install-autostart && claude-statusbar --tray")
        return 1

    print(f"installed {module}")
    print(f"installed {desktop}")
    subprocess.run(["xfce4-panel", "-r"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print()
    print("Add it with: right-click the panel > Panel > Add New Items… > "
          "\"Claude Status Bar\"")
    return 0


def remove_xfce_plugin():
    for path in (XFCE_PLUGIN_SCRIPT, XFCE_STALE_USER_DESKTOP):
        try:
            path.unlink()
        except OSError:
            pass
    lib_dir, data_dir = _plugin_dirs()
    targets = [p for p in (data_dir / "claude-statusbar.desktop" if data_dir else None,
                           lib_dir / "libclaude-statusbar.so" if lib_dir else None)
               if p is not None and p.exists()]
    for target in targets:
        if os.access(target.parent, os.W_OK):
            target.unlink()
        elif shutil.which("sudo"):
            subprocess.run(["sudo", "rm", "-f", str(target)], check=False)
    print("Xfce panel plugin removed (take the item off the panel by hand).")
    return 0


def install_autostart():
    """Start the tray icon at login (Linux desktops)."""
    _install_icon()
    if not LINUX:
        print("Autostart is handled by the OS on Windows and macOS; add "
              "claude-statusbar --tray to your login items.")
        return 0
    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    AUTOSTART_FILE.write_text(AUTOSTART_DESKTOP.format(exec=_tray_command(), icon=LOGO))
    print(f"tray autostart installed: {AUTOSTART_FILE}")
    return 0


def remove_autostart():
    try:
        AUTOSTART_FILE.unlink()
        print(f"tray autostart removed: {AUTOSTART_FILE}")
    except OSError:
        print("tray autostart: nothing to remove")
    return 0


def install_all():
    """Wire up capture, then whichever desktop integration fits this machine."""
    from claude_statusbar import hook

    hook.install()
    print()

    if LINUX and is_xfce():
        if install_xfce_plugin() == 0:
            print()
            print("Prefer a tray icon instead? "
                  "Run: claude-statusbar --install-autostart")
            return 0
        print("\nFalling back to the tray icon.")
    install_autostart()
    if True:
        where = ("the menu bar" if MACOS else
                 "the notification area" if WINDOWS else "your system tray")
        print(f"Start it now with: claude-statusbar --tray   (it appears in {where})")
        if LINUX:
            print("On GNOME the tray needs the AppIndicator extension.")
    return 0


def uninstall_all():
    from claude_statusbar import hook

    hook.remove()
    remove_xfce_plugin()
    remove_autostart()
    return 0
