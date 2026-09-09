"""The tray icon: KDE, GNOME, Xfce, Windows and macOS.

Qt talks StatusNotifierItem on Linux desktops that provide it and falls back to
the freedesktop system tray elsewhere, so one implementation covers every
desktop.  The icon is the same SVG the Xfce panel plugin draws.
"""

import sys

from PySide6.QtCore import QByteArray, QFileSystemWatcher, QTimer, Qt, QUrl
from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from claude_statusbar import PROJECT_URL, config
from claude_statusbar.config import cfg
from claude_statusbar.data import Data
from claude_statusbar.meter import square_svg, tooltip
from claude_statusbar.update import cached as cached_update
from claude_statusbar.paths import LOGO, state_file
from claude_statusbar.single import SingleInstance


def svg_icon(svg, size=64):
    """Render an SVG string into a QIcon."""
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


class Tray(QSystemTrayIcon):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.window = None

        menu = QMenu()
        self.summary = QAction("…", menu)
        self.summary.setEnabled(False)
        menu.addAction(self.summary)
        menu.addSeparator()
        for label, slot in (("Details and settings…", self.open_window),
                            ("Refresh now", self.refresh)):
            action = QAction(label, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        # Only shown once a check has found something newer.
        self.update_action = QAction("Update available", menu)
        self.update_action.setVisible(False)
        self.update_action.triggered.connect(self._open_release)
        menu.addAction(self.update_action)

        menu.addSeparator()
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(app.quit)
        menu.addAction(quit_action)
        self.setContextMenu(menu)

        self.activated.connect(self._activated)

        # Redraw as soon as a session writes, rather than waiting for the
        # next tick.  The directory is watched, not the file: the state is
        # saved by writing a temporary file and renaming it over the target,
        # which replaces the inode the watcher was holding.
        self.watcher = QFileSystemWatcher()
        self.watcher.addPath(str(state_file().parent))
        self.watcher.directoryChanged.connect(self._state_changed)

        # Coalesce the burst of events one save produces.
        self.settle = QTimer()
        self.settle.setSingleShot(True)
        self.settle.setInterval(120)
        self.settle.timeout.connect(self.refresh)

        # The periodic tick still matters for the clock-driven parts:
        # countdowns and "updated 3m ago" change with no file write at all.
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(max(1000, int(config.seconds("refresh") * 1000)))
        self.refresh()
        self._update_result(cached_update())
        self._start_update_check()

    def _state_changed(self, _path):
        self.settle.start()

    def _open_release(self):
        result = cached_update() or {}
        QDesktopServices.openUrl(QUrl(result.get("url") or PROJECT_URL))

    def _start_update_check(self):
        """Once per launch; update.check() caches for a day beyond that."""
        if not cfg["check_updates"]:
            return
        from claude_statusbar.window import UpdateTask

        task = UpdateTask(False)
        task.signals.done.connect(self._update_result)
        QThreadPool.globalInstance().start(task)

    def _update_result(self, result):
        newer = bool(result and result.get("newer"))
        self.update_action.setVisible(newer)
        if newer:
            self.update_action.setText(f"Update available: {result.get('latest', '')}")

    def _activated(self, reason):
        # A left click opens the window; the menu handles the rest.
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_window()

    def refresh(self):
        # Picking up a changed interval without a restart.
        wanted = max(1000, int(config.seconds("refresh") * 1000))
        if self.timer.interval() != wanted:
            self.timer.setInterval(wanted)

        data = Data()
        self.setIcon(svg_icon(square_svg(data)))
        text = tooltip(data)
        self.setToolTip(text)
        self.summary.setText(text.splitlines()[0])
        if self.window is not None and self.window.isVisible():
            self.window.refresh()

    def open_window(self):
        from claude_statusbar.window import MainWindow

        if self.window is None:
            self.window = MainWindow()
        self.window.refresh()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()


def run():
    """Entry point for the tray application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Claude Status Bar")
    app.setWindowIcon(QIcon(str(LOGO)))
    app.setQuitOnLastWindowClosed(False)     # closing the window keeps the tray

    # Already running?  Ask that instance to show itself and step aside.
    guard = SingleInstance()
    if guard.hand_over():
        return 0

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray is available on this desktop.\n"
              "On GNOME, install the AppIndicator extension, or use the Xfce "
              "panel plugin instead.", file=sys.stderr)
        return 1

    tray = Tray(app)
    guard.listen(tray.open_window)
    tray.show()
    if not cfg["start_minimised"]:
        tray.open_window()
    return app.exec()
