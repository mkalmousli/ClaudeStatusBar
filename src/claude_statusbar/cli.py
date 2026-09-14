"""Command dispatch.

    claude-statusbar                    start the tray icon (default)
    claude-statusbar --tray             the same, explicitly
    claude-statusbar --gui              just the details and settings window

    claude-statusbar --install          wire up capture + this desktop
    claude-statusbar --uninstall        undo all of it

    claude-statusbar --install-hook     capture only
    claude-statusbar --remove-hook
    claude-statusbar --install-xfce-plugin / --remove-xfce-plugin
    claude-statusbar --install-autostart / --remove-autostart
    claude-statusbar --install-app-entry / --remove-app-entry
                                         application menu entry + desktop icon

    claude-statusbar --statusline       Claude Code's status line (stores + prints)
    claude-statusbar --capture          store only, echo stdin (for chaining)
    claude-statusbar --panel [height]   data feed for the Xfce panel plugin
"""

import sys

from claude_statusbar import __version__

USAGE = __doc__.strip()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv else "--tray"

    if command in ("-h", "--help"):
        print(USAGE)
        return 0
    if command in ("-V", "--version"):
        print(f"claude-statusbar {__version__}")
        return 0

    # --- capture (no GUI toolkit needed; keep these first and cheap) ------
    if command == "--capture":
        from claude_statusbar.capture import capture
        return capture()
    if command == "--statusline":
        from claude_statusbar.capture import statusline
        return statusline()

    # --- installation ----------------------------------------------------
    from claude_statusbar import install as installer

    actions = {
        "--install": installer.install_all,
        "--uninstall": installer.uninstall_all,
        "--install-xfce-plugin": installer.install_xfce_plugin,
        "--remove-xfce-plugin": installer.remove_xfce_plugin,
        "--install-autostart": installer.install_autostart,
        "--remove-autostart": installer.remove_autostart,
        "--install-app-entry": installer.install_app_entry,
        "--remove-app-entry": installer.remove_app_entry,
    }
    if command in actions:
        return actions[command]()
    if command in ("--install-hook", "--remove-hook"):
        from claude_statusbar import hook
        return hook.install() if command == "--install-hook" else hook.remove()

    # --- the native Xfce plugin's data feed ------------------------------
    # Four fields, newline separated:
    #   1. the SVG (always a single line)
    #   2. the refresh interval in milliseconds
    #   3. the state file to watch, so the panel can react to writes at once
    #   4. the tooltip (everything after, may span lines)
    # Config lives on this side, so the plugin picks up setting changes without
    # being rebuilt or restarted.
    if command == "--panel":
        from claude_statusbar import config
        from claude_statusbar.data import Data
        from claude_statusbar.meter import tooltip, wide_svg
        from claude_statusbar.paths import state_file

        height = None
        if len(argv) > 1:
            try:
                height = int(argv[1])
            except ValueError:
                pass
        data = Data()
        print(wide_svg(data, height))
        print(int(max(0.5, config.seconds("refresh")) * 1000))
        print(state_file())
        print(tooltip(data))
        return 0

    # --- user interfaces -------------------------------------------------
    if command == "--gui":
        from claude_statusbar.window import run
        return run()
    if command == "--tray":
        from claude_statusbar.tray import run
        return run()

    print(f"unknown option: {command}\n\n{USAGE}", file=sys.stderr)
    return 2


def entry():
    try:
        sys.exit(main())
    except BrokenPipeError:
        pass
    except KeyboardInterrupt:
        sys.exit(130)
