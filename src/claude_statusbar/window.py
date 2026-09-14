"""The details and settings window (Qt, so it is the same on every OS)."""

from PySide6.QtCore import (QFileSystemWatcher, QObject, QRunnable, Qt,
                            QThreadPool, QTimer, QUrl, Signal)
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont,
                           QGuiApplication, QIcon, QKeySequence, QPainter,
                           QPainterPath, QPalette, QPixmap, QShortcut)
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QColorDialog,
                               QComboBox, QFileDialog, QFrame, QGridLayout,
                               QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QPushButton, QMenu, QMessageBox, QScrollArea,
                               QSizePolicy, QSpinBox, QTabWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

from claude_statusbar import config
from claude_statusbar.config import cfg
from claude_statusbar import (AUTHOR, AUTHOR_URL, DONATE_URL, ISSUES_URL,
                              LICENSE, PROJECT_URL, SUMMARY, __version__,
                              launcher)
from claude_statusbar.data import Data, account
from pathlib import Path

from claude_statusbar.paths import LOGO, claude_dir, state_file
from claude_statusbar.update import cached as cached_update
from claude_statusbar.update import check as check_update
from claude_statusbar.update import describe as describe_update
from claude_statusbar.render import limit_rows, status_color, time_left_pct
from claude_statusbar.util import (clock, dur, format_duration, human,
                                   parse_duration, pct)

TITLES = {"5h": "5-hour limit", "wk": "Weekly limit", "$": "Extra usage"}


def muted(widget, opacity=0.72):
    """A dimmed version of the *actual* text colour.

    Qt's palette(mid) is a frame-shadow colour, not a text colour — on a dark
    theme it lands close to the background and the text disappears.  Fading the
    real foreground keeps it legible in both light and dark themes.
    """
    colour = widget.palette().color(QPalette.WindowText)
    return (f"color: rgba({colour.red()}, {colour.green()}, {colour.blue()}, "
            f"{opacity});")


class Meter(QWidget):
    """A rounded progress bar in the shared status colours."""

    def __init__(self, thickness=12):
        super().__init__()
        self.used = None
        self.thickness = thickness
        self.colour = None            # None = colour by the usage bands
        self.marks = []               # percentages to notch across the bar
        self.highlight = None          # one mark drawn bolder (session-end)
        self.setMinimumHeight(thickness + 2)
        self.setMaximumHeight(thickness + 2)

    def set_used(self, used):
        self.used = used
        self.update()

    def set_marks(self, marks, highlight=None):
        self.marks = list(marks or [])
        self.highlight = highlight
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        height = self.thickness
        top = (self.height() - height) / 2
        radius = height / 2

        path = QPainterPath()
        path.addRoundedRect(0, top, self.width(), height, radius, radius)
        painter.fillPath(path, QColor(cfg["img_track"]))

        if self.used:
            width = max(height, self.width() * self.used / 100)
            filled = QPainterPath()
            filled.addRoundedRect(0, top, width, height, radius, radius)
            painter.fillPath(filled,
                             QColor(self.colour or status_color(self.used)))

        # Notches showing where each further 5h session would land, with the
        # current session's end drawn bolder.  Clipped to the rounded track so
        # they never poke past the ends.
        if self.marks or self.highlight is not None:
            painter.setClipPath(path)
            on_track = QColor(cfg["img_label"])
            on_fill = self.palette().color(QPalette.Window)
            strong = self.palette().color(QPalette.WindowText)
            filled_end = max(height, self.width() * (self.used or 0) / 100)

            def notch(mark, weight, bold=False):
                x = self.width() * mark / 100
                colour = strong if bold else (
                    on_fill if x <= filled_end else on_track)
                painter.fillRect(int(round(x)) - weight // 2, int(top),
                                 weight, int(height), colour)

            for mark in self.marks:
                if 0 < mark < 100:
                    notch(mark, 2)
            if self.highlight is not None and 0 < self.highlight < 100:
                notch(self.highlight, 3, bold=True)
        painter.end()


class BarChart(QWidget):
    """A small, hoverable vertical bar chart, drawn straight with QPainter.

    Kept dependency-free (no plotting library) so the app stays light; the
    same style of hand-rolled QPainter widget as Meter above.
    """

    def __init__(self, height=160, unit="", value_fmt=None):
        super().__init__()
        self.bars = []                # [(label, value, colour, tooltip)]
        self.max_value = 1.0
        self.unit = unit
        self.value_fmt = value_fmt or (lambda v: f"{v:.0f}{self.unit}")
        self.setMinimumHeight(height)
        self.setMouseTracking(True)
        self._hover = -1

    def set_bars(self, bars, max_value=None):
        self.bars = bars
        self.max_value = max_value or max((b[1] for b in bars), default=0) or 1.0
        self._hover = -1
        self.update()

    def _bar_rects(self):
        if not self.bars:
            return []
        margin_bottom = 22
        top = 6
        usable_h = max(1, self.height() - margin_bottom - top)
        n = len(self.bars)
        gap = 3
        width = max(2.0, (self.width() - gap * (n - 1)) / n)
        rects = []
        for index, (_label, value, _colour, _tip) in enumerate(self.bars):
            x = index * (width + gap)
            h = usable_h * min(1.0, value / self.max_value) if self.max_value else 0
            rects.append((x, top + (usable_h - h), width, max(1.0, h)))
        return rects

    def mouseMoveEvent(self, event):
        rects = self._bar_rects()
        pos = event.position() if hasattr(event, "position") else event.pos()
        hover = -1
        for index, (x, _y, w, _h) in enumerate(rects):
            if x <= pos.x() <= x + w:
                hover = index
                break
        if hover != self._hover:
            self._hover = hover
            if hover >= 0:
                label, value, _colour, tip = self.bars[hover]
                from PySide6.QtWidgets import QToolTip
                QToolTip.showText(event.globalPosition().toPoint()
                                  if hasattr(event, "globalPosition")
                                  else self.mapToGlobal(event.pos()),
                                  tip or f"{label}: {self.value_fmt(value)}", self)
            self.update()

    def leaveEvent(self, _event):
        self._hover = -1
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        track = QColor(cfg["img_track"])
        label_colour = QColor(cfg["img_label"])

        if not self.bars:
            painter.setPen(label_colour)
            painter.drawText(self.rect(), Qt.AlignCenter, "No data yet")
            painter.end()
            return

        baseline = self.height() - 22
        painter.setPen(track)
        painter.drawLine(0, baseline, self.width(), baseline)

        rects = self._bar_rects()
        n = len(self.bars)
        # Thin out x-axis labels so they never overlap.
        stride = max(1, n // max(1, self.width() // 56))
        for index, ((x, y, w, h), (label, _value, colour, _tip)) in enumerate(
                zip(rects, self.bars)):
            colour_q = QColor(colour)
            if index == self._hover:
                colour_q = colour_q.lighter(125)
            path = QPainterPath()
            radius = min(3, w / 2)
            path.addRoundedRect(x, y, w, h, radius, radius)
            painter.fillPath(path, colour_q)

            if index % stride == 0 or index == self._hover:
                painter.save()
                painter.setPen(label_colour)
                font = QFont(painter.font())
                font.setPointSize(max(7, font.pointSize() - 2))
                painter.setFont(font)
                painter.translate(x + w / 2, baseline + 4)
                painter.rotate(45)
                painter.drawText(0, 0, label)
                painter.restore()
        painter.end()


class LimitCard(QWidget):
    """One limit: name, big percentage, meter, and when it resets."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(3)

        top = QHBoxLayout()
        self.name = QLabel()
        font = QFont(self.name.font())
        font.setBold(True)
        self.name.setFont(font)
        self.figure = QLabel()
        figure_font = QFont(self.figure.font())
        figure_font.setPointSize(figure_font.pointSize() + 8)
        figure_font.setBold(True)
        self.figure.setFont(figure_font)
        self.figure.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        top.addWidget(self.name)
        top.addStretch(1)
        top.addWidget(self.figure)

        self.meter = Meter(12)
        # A slimmer companion: how much of the window is still ahead.
        self.time_meter = Meter(5)
        self.time_meter.colour = cfg["img_label"]
        self.caption = QLabel()
        self.caption.setWordWrap(True)
        caption_font = QFont(self.caption.font())
        caption_font.setPointSize(max(1, caption_font.pointSize() - 1))
        self.caption.setFont(caption_font)
        self.caption.setStyleSheet(muted(self.caption))
        # A second, dimmer line for the 5h-session projection.
        self.projection = QLabel()
        self.projection.setWordWrap(True)
        self.projection.setFont(caption_font)
        self.projection.setStyleSheet(muted(self.projection, 0.6))

        layout.addLayout(top)
        layout.addWidget(self.meter)
        layout.addWidget(self.time_meter)
        layout.addWidget(self.caption)
        layout.addWidget(self.projection)

    #: Nominal length of a 5h session, for turning a span of time into a
    #: count of sessions that fit inside it.
    SESSION_SECONDS = 5 * 3600

    def update_values(self, label, used, countdown, time_left=None, reset_at=0,
                      burn=None, h5_reset=0):
        self.name.setText(TITLES.get(label, label))
        colour = status_color(used) if used is not None else cfg["img_label"]
        self.figure.setText(
            f'<span style="color:{colour}">{pct(used)}</span>'
            f'<span style="font-size:small; {muted(self.figure)}"> used</span>')
        self.meter.set_used(used)

        # Notch the weekly bar at each 5h-session boundary: the bold notch is
        # where the session running now ends, the thin ones every session after
        # it, all at the current burn rate.
        #
        # Simple weekly-percentage division: `burn` is what one fully-used 5h
        # session costs against the weekly allowance, so how many more fit is
        # just the remaining allowance divided by that — no assumption about
        # how much of the *current* session's 5h is still ahead. Two
        # independent limits apply, and the tighter one wins:
        #  - the weekly *allowance* runs out after this many sessions;
        #  - the weekly *clock*: no further session can start unless a full
        #    5h fits before the week itself resets.
        marks, session_end, sessions_left, clock_limited = [], None, None, False
        if burn and used is not None:
            session_end = min(100.0, used + burn)
            sessions_left = max(0.0, (100 - used) / burn)

            if h5_reset and reset_at:
                # Sessions run back-to-back after the current one ends, so
                # the current session's own tail end (h5_reset) is where the
                # clock starts counting, not "now".
                spare_seconds = max(0, reset_at - h5_reset)
                by_clock = spare_seconds // self.SESSION_SECONDS
                if by_clock < sessions_left:
                    sessions_left = float(by_clock)
                    clock_limited = True

            # One notch per full session actually counted in sessions_left, so
            # the bar never shows a boundary the text doesn't back up (e.g.
            # allowance would in principle allow more, but the week resets
            # first — draw no further than that).
            mark = session_end + burn
            while mark < 100 and len(marks) < int(sessions_left) - 1:
                marks.append(mark)
                mark += burn
        self.meter.set_marks(marks, session_end)

        self.time_meter.colour = cfg["img_label"]
        self.time_meter.set_used(time_left)
        self.time_meter.setVisible(time_left is not None)

        if used is None:
            self.caption.setText("no reading for the current window")
        elif countdown:
            parts = [f"{pct(100 - used)} left", f"resets {countdown}"]
            at = clock(reset_at)
            if at:
                parts.append(at)
            if time_left is not None:
                parts.append(f"{pct(time_left)} window")
            self.caption.setText(" · ".join(parts))
        else:
            self.caption.setText(f"{pct(100 - used)} left")

        if sessions_left is not None:
            limiter = "the week ends first" if clock_limited else "the allowance runs out first"
            self.projection.setText(
                f"≈{pct(burn)}/5h session · this session ends near "
                f"{round(session_end)}% · {sessions_left:.1f} more full 5h "
                f"sessions possible before the week resets ({limiter})")
        else:
            self.projection.setText("")
        self.projection.setVisible(bool(self.projection.text()))


class ColorField(QWidget):
    """A colour swatch button next to its hex value."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setMaximumWidth(100)
        self.button = QPushButton("Pick…")
        self.button.clicked.connect(self._pick)
        layout.addWidget(self.edit)
        layout.addWidget(self.button)
        self.edit.textChanged.connect(self._paint_button)

    def _paint_button(self):
        colour = QColor(self.edit.text())
        if colour.isValid():
            self.button.setStyleSheet(f"background-color: {colour.name()};")

    def _pick(self):
        colour = QColorDialog.getColor(QColor(self.edit.text()), self)
        if colour.isValid():
            self.edit.setText(colour.name())

    def text(self):
        return self.edit.text()

    def setText(self, value):
        self.edit.setText(value)


class PathField(QWidget):
    """A text field with a folder picker beside it."""

    def __init__(self, on_change):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("~/.claude")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(browse)
        self.edit.editingFinished.connect(on_change)
        self._on_change = on_change

    def _browse(self):
        start = self.edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Claude data directory", start)
        if chosen:
            self.edit.setText(chosen)
            self._on_change()

    def text(self):
        return self.edit.text()

    def setText(self, value):
        self.edit.setText(value)


class BandTable(QWidget):
    """Edit the usage colour bands as a table you can add to and remove from."""

    def __init__(self, on_change):
        super().__init__()
        self._on_change = on_change
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["From % used", "Colour"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setMinimumHeight(150)
        self.table.itemChanged.connect(self._changed)
        self.table.cellDoubleClicked.connect(self._maybe_pick)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        for text, slot in (("Add band", self.add_row), ("Remove", self.remove_row)):
            button = QPushButton(text)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def _maybe_pick(self, row, column):
        if column != 1:
            return
        item = self.table.item(row, 1)
        chosen = QColorDialog.getColor(QColor(item.text()), self)
        if chosen.isValid():
            item.setText(chosen.name())

    def _changed(self, _item=None):
        if not self._loading:
            self._paint()
            self._on_change()

    def _paint(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item is None:
                continue
            colour = QColor(item.text())
            if colour.isValid():
                item.setBackground(colour)
                # Keep the hex readable on top of its own colour.
                luma = 0.299 * colour.red() + 0.587 * colour.green() + 0.114 * colour.blue()
                item.setForeground(QColor("#000000" if luma > 140 else "#ffffff"))

    def add_row(self):
        rows = self.value()
        highest = max((band[0] for band in rows), default=0)
        rows.append([min(100, int(highest) + 10), "#888888"])
        self.setValue(rows)
        self._changed()

    def remove_row(self):
        row = self.table.currentRow()
        if row >= 0 and self.table.rowCount() > 1:
            self.table.removeRow(row)
            self._changed()

    def value(self):
        rows = []
        for row in range(self.table.rowCount()):
            start = self.table.item(row, 0)
            colour = self.table.item(row, 1)
            if start is None or colour is None:
                continue
            try:
                percent = max(0, min(100, int(float(start.text()))))
            except ValueError:
                continue
            rows.append([percent, colour.text().strip()])
        return sorted(rows)

    def setValue(self, bands):
        self._loading = True
        rows = sorted(bands or [])
        self.table.setRowCount(len(rows))
        for index, (start, colour) in enumerate(rows):
            self.table.setItem(index, 0, QTableWidgetItem(str(int(start))))
            self.table.setItem(index, 1, QTableWidgetItem(str(colour)))
        self._loading = False
        self._paint()


class _UpdateSignals(QObject):
    done = Signal(dict)


class UpdateTask(QRunnable):
    """Runs the update check on a worker thread; it does network I/O."""

    def __init__(self, force=False):
        super().__init__()
        self.force = force
        self.signals = _UpdateSignals()

    def run(self):
        try:
            self.signals.done.emit(check_update(self.force))
        except Exception as error:            # never take the UI down
            self.signals.done.emit({"error": str(error)})


class SortableItem(QTableWidgetItem):
    """Sorts on a supplied key, so '9%' does not sort after '85%'."""

    def __init__(self, text, key):
        super().__init__(text)
        self.key = key

    def __lt__(self, other):
        if isinstance(other, SortableItem):
            try:
                return self.key < other.key
            except TypeError:
                pass
        return super().__lt__(other)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Claude Status Bar")
        self.setWindowIcon(QIcon(str(LOGO)))
        self.resize(780, 620)

        self._last_data = None
        self.tabs = QTabWidget()
        self.tabs.addTab(self._overview_tab(), "Overview")
        self.tabs.addTab(self._sessions_tab(), "Sessions")
        self.tabs.addTab(self._history_tab(), "History")
        self.tabs.addTab(self._settings_tab(), "Settings")
        self.tabs.addTab(self._about_tab(), "About")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        close_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        close_shortcut.activated.connect(self.close)

        self.watcher = QFileSystemWatcher(self)
        self.watcher.addPath(str(state_file().parent))
        self.watcher.directoryChanged.connect(lambda _p: self.settle.start())
        self.settle = QTimer(self)
        self.settle.setSingleShot(True)
        self.settle.setInterval(120)
        self.settle.timeout.connect(self.refresh)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(max(1000, int(config.seconds("refresh") * 1000)))
        self.refresh()

    # -- Overview ---------------------------------------------------------
    def _overview_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)

        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)

        self.cards = [LimitCard(), LimitCard()]
        for card in self.cards:
            layout.addWidget(card)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        self.details = QGridLayout()
        self.details.setColumnStretch(1, 1)
        layout.addLayout(self.details)

        self.account_heading = QLabel("Account")
        heading_font = QFont(self.account_heading.font())
        heading_font.setBold(True)
        self.account_heading.setFont(heading_font)
        self.account_heading.setContentsMargins(0, 12, 0, 2)
        layout.addWidget(self.account_heading)

        self.account_grid = QGridLayout()
        self.account_grid.setColumnStretch(1, 1)
        layout.addLayout(self.account_grid)
        layout.addStretch(1)
        return page

    def _set_grid(self, grid, rows):
        while grid.count():
            item = grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, (name, value) in enumerate(rows):
            label = QLabel(name)
            label.setStyleSheet(muted(label))
            value_label = QLabel(str(value))
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            grid.addWidget(label, index, 0, Qt.AlignTop)
            grid.addWidget(value_label, index, 1)

    # -- Sessions (the drill-down) ---------------------------------------
    SESSION_COLUMNS = ["", "Session", "Name", "Model", "5h", "Weekly",
                       "Context", "Cost", "Updated", "Directory"]

    def _sessions_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)

        blurb = QLabel(
            "Every session writes its own snapshot. Rate limits are "
            "account-wide, so the highest reading in the current window is the "
            "freshest one — that is the row marked ✓. Snapshots whose window "
            "has already reset are ignored entirely.\n"
            "Click a heading to sort. Double-click a row to resume that session "
            "in a terminal; right-click for more, Ctrl+C copies the selection.")
        blurb.setWordWrap(True)
        blurb.setStyleSheet(muted(blurb))
        layout.addWidget(blurb)

        self.table = QTableWidget(0, len(self.SESSION_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.SESSION_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(8, Qt.AscendingOrder)   # newest first
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._session_menu)
        self.table.doubleClicked.connect(lambda *_: self._resume_selected())
        layout.addWidget(self.table)

        copy = QShortcut(QKeySequence.Copy, self.table)
        copy.activated.connect(self._copy_selection)

        self.window_note = QLabel()
        self.window_note.setStyleSheet(muted(self.window_note))
        self.window_note.setWordWrap(True)
        layout.addWidget(self.window_note)
        return page

    def _fill_sessions(self, data):
        rows = data.session_rows()
        # Sorting has to be off while filling, or rows shuffle mid-insert.
        self.table.setSortingEnabled(False)
        order = self.table.horizontalHeader().sortIndicatorSection()
        direction = self.table.horizontalHeader().sortIndicatorOrder()

        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            marker = "✓" if row["counted"] else ("" if row["window"] == "current" else "·")
            updated = f"{dur(row['age'])} ago"
            if row["window"] != "current":
                updated += f"  ({row['window']} window)"
            name = row["name"] or "—"
            if row["branch"] and row["branch"] != "HEAD":
                name += f"  [{row['branch']}]"

            cells = [
                SortableItem(marker, 0 if row["counted"] else 1),
                SortableItem(row["id"][:8], row["id"]),
                SortableItem(name, name.lower()),
                SortableItem(row["model"] or "—", row["model"] or ""),
                SortableItem(pct(row["h5"]), row["h5"] if row["h5"] is not None else -1),
                SortableItem(pct(row["wk"]), row["wk"] if row["wk"] is not None else -1),
                SortableItem(pct(row["ctx"]), row["ctx"] if row["ctx"] is not None else -1),
                SortableItem(f"${row['cost']:.2f}", row["cost"]),
                SortableItem(updated, row["age"]),
                SortableItem(row["cwd"] or "—", row["cwd"] or ""),
            ]
            for column, item in enumerate(cells):
                if column in (4, 5, 6, 7):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                item.setToolTip(item.text())
                self.table.setItem(index, column, item)
            # The full record travels with the row, for the context menu.
            self.table.item(index, 1).setData(Qt.UserRole, row)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(order, direction)

        expired = sum(1 for r in rows if r["window"] != "current")
        self.window_note.setText(
            f"{len(rows)} snapshots · {expired} from a window that has already "
            f"reset (ignored) · ✓ is the reading shown on the panel"
            if rows else "No snapshots yet.")

    def _selected_row(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)
        return item.data(Qt.UserRole) if item else None

    def _session_menu(self, position):
        record = self._selected_row()
        if record is None:
            return
        menu = QMenu(self)
        actions = [
            ("Resume in terminal", lambda: self._resume_selected()),
            ("Open folder", lambda: self._open_folder(record)),
            (None, None),
            ("Copy selection", self._copy_selection),
            ("Copy session ID", lambda: self._to_clipboard(record["id"])),
            ("Copy directory", lambda: self._to_clipboard(record["cwd"])),
            ("Copy row as text", lambda: self._copy_rows([self.table.currentRow()])),
        ]
        for label, slot in actions:
            if label is None:
                menu.addSeparator()
                continue
            action = QAction(label, menu)
            action.triggered.connect(slot)
            if label in ("Open folder", "Copy directory") and not record["cwd"]:
                action.setEnabled(False)
            menu.addAction(action)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _resume_selected(self):
        record = self._selected_row()
        if record is None:
            return
        error = launcher.open_session(record["id"], record["cwd"])
        if error:
            QMessageBox.warning(self, "Could not open a terminal", error)

    def _open_folder(self, record):
        if record["cwd"]:
            launcher.open_folder(record["cwd"])

    def _to_clipboard(self, text):
        QGuiApplication.clipboard().setText(str(text or ""))
        self.window_note.setText(f"Copied: {text}")

    def _copy_rows(self, rows):
        lines = []
        for row in rows:
            lines.append("\t".join(
                self.table.item(row, column).text()
                for column in range(1, self.table.columnCount())
                if self.table.item(row, column)))
        self._to_clipboard("\n".join(lines))

    def _copy_selection(self):
        """Copy whatever is selected as tab-separated text."""
        ranges = self.table.selectedRanges()
        if not ranges:
            return
        lines = []
        for block in ranges:
            for row in range(block.topRow(), block.bottomRow() + 1):
                cells = []
                for column in range(block.leftColumn(), block.rightColumn() + 1):
                    item = self.table.item(row, column)
                    cells.append(item.text() if item else "")
                lines.append("\t".join(cells).strip())
        self._to_clipboard("\n".join(lines))

    # -- History (usage over time, and what went unused) ------------------
    GRANULARITIES = [("day", "Day"), ("week", "Week"), ("month", "Month"),
                     ("year", "Year")]
    MAX_BARS = 36

    def _history_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(10)

        top = QHBoxLayout()
        blurb = QLabel(
            "Token usage over time, and how much of each rate-limit window "
            "reset unused — the allowance that simply expired.")
        blurb.setWordWrap(True)
        blurb.setStyleSheet(muted(blurb))
        top.addWidget(blurb, 1)
        top.addWidget(QLabel("Group by"))
        self.history_granularity = QComboBox()
        for key, label in self.GRANULARITIES:
            self.history_granularity.addItem(label, key)
        self.history_granularity.setCurrentIndex(1)   # Week is a sane default
        self.history_granularity.currentIndexChanged.connect(self._fill_history)
        top.addWidget(self.history_granularity)
        outer.addLayout(top)

        outer.addWidget(self._section_heading("Token usage"))
        self.token_chart = BarChart(150, value_fmt=human)
        self.token_chart.setToolTip("")
        outer.addWidget(self.token_chart)
        self.token_summary = QLabel()
        self.token_summary.setStyleSheet(muted(self.token_summary))
        outer.addWidget(self.token_summary)

        waste_row = QHBoxLayout()
        waste_row.addWidget(self._section_heading("Unused allowance per window"))
        waste_row.addStretch(1)
        self.waste_kind = QComboBox()
        self.waste_kind.addItem("5-hour windows", "h5")
        self.waste_kind.addItem("Weekly windows", "wk")
        self.waste_kind.currentIndexChanged.connect(self._fill_history)
        waste_row.addWidget(self.waste_kind)
        outer.addLayout(waste_row)
        self.waste_chart = BarChart(150, unit="%")
        outer.addWidget(self.waste_chart)
        self.waste_summary = QLabel()
        self.waste_summary.setWordWrap(True)
        self.waste_summary.setStyleSheet(muted(self.waste_summary))
        outer.addWidget(self.waste_summary)

        outer.addStretch(1)
        return page

    @staticmethod
    def _section_heading(text):
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        return label

    def _fill_history(self, *_args):
        if self._last_data is None:
            return
        granularity = self.history_granularity.currentData()
        data = self._last_data

        tokens = data.token_series(granularity)[-self.MAX_BARS:]
        # A single, calmer colour for a token-volume series — the traffic-light
        # bands mean "danger", which does not apply to raw token counts.
        accent = QColor(cfg["warn_color"]).darker(115).name()
        bars = [(label, value, accent, f"{label}: {human(value)} tokens")
               for _key, label, value in tokens]
        self.token_chart.set_bars(bars)
        total = sum(t[2] for t in tokens)
        self.token_summary.setText(
            f"{human(total)} tokens across {len(tokens)} {granularity}(s)"
            if tokens else "No token history yet — check back after a session or two.")

        kind = self.waste_kind.currentData()
        waste = data.waste_series(kind, granularity)[-self.MAX_BARS:]
        waste_bars = [(label, pct_value, status_color(pct_value),
                      f"{label}: {pct_value:.0f}% left unused ({count} window"
                      f"{'s' if count != 1 else ''})")
                     for _key, label, pct_value, count in waste]
        self.waste_chart.set_bars(waste_bars, max_value=100)

        if waste:
            windows = sum(count for *_r, count in waste)
            weighted = sum(p * c for *_r, p, c in waste) / windows if windows else 0
            fully_wasted = sum(1 for *_r, p, c in waste if p >= 95)
            noun = "5h session" if kind == "h5" else "weekly"
            self.waste_summary.setText(
                f"{windows} {noun} window(s) closed in this range · on average "
                f"{weighted:.0f}% of each was never used"
                + (f" · {fully_wasted} window(s) barely touched (≤5% used)"
                   if fully_wasted else ""))
        else:
            self.waste_summary.setText(
                "No windows have closed yet — this fills in once a 5h or "
                "weekly limit actually resets while the app is capturing.")

    # -- Settings ---------------------------------------------------------
    def _settings_tab(self):
        """One grid, so every field lines up; changes apply as you make them."""
        page = QWidget()
        outer = QVBoxLayout(page)

        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setContentsMargins(18, 18, 18, 18)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)

        self.widgets = {}
        self._loading = True
        row = 0
        section = None
        for setting in config.SETTINGS:
            if setting.section != section:
                section = setting.section
                heading = QLabel(section)
                font = QFont(heading.font())
                font.setBold(True)
                heading.setFont(font)
                heading.setContentsMargins(0, 14 if row else 0, 0, 2)
                grid.addWidget(heading, row, 0, 1, 2)
                row += 1

            label = QLabel(setting.label)
            label.setWordWrap(True)
            label.setMinimumWidth(200)
            # Without this the label keeps its one-line height hint and the
            # wrapped text is clipped instead of growing the row.
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
            widget = self._widget_for(setting)

            if setting.kind == "bands":
                grid.addWidget(label, row, 0, 1, 2)
                row += 1
                grid.addWidget(widget, row, 0, 1, 2)
            else:
                grid.addWidget(label, row, 0, Qt.AlignLeft | Qt.AlignVCenter)
                grid.addWidget(widget, row, 1, Qt.AlignLeft | Qt.AlignVCenter)
            row += 1

            if setting.help:
                note = QLabel(setting.help)
                note.setWordWrap(True)
                note.setMinimumWidth(200)
                note.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
                note.setStyleSheet(muted(note, 0.62) + " font-size: 11px;")
                note.setContentsMargins(0, 0, 0, 8)
                grid.addWidget(note, row, 0, 1, 2)
                row += 1

        grid.setRowStretch(row, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Wrap rather than scroll sideways, which is what clipped the text.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        actions = QHBoxLayout()
        self.save_note = QLabel()
        self.save_note.setStyleSheet(muted(self.save_note))
        self.save_note.setWordWrap(True)
        actions.addWidget(self.save_note, 1)
        defaults = QPushButton("Reset to defaults")
        defaults.clicked.connect(self._on_defaults)
        actions.addWidget(defaults)
        outer.addLayout(actions)

        self._load(cfg)
        self._loading = False
        return page

    FIELD_WIDTH = 220

    def _widget_for(self, setting):
        """Build the editor and connect it straight to the auto-save."""
        apply_now = self._apply

        if setting.kind == "bool":
            widget = QCheckBox()
            widget.toggled.connect(apply_now)
        elif setting.kind == "int":
            widget = QSpinBox()
            widget.setRange(setting.minimum, setting.maximum)
            widget.setFixedWidth(self.FIELD_WIDTH)
            widget.valueChanged.connect(apply_now)
        elif setting.kind == "color":
            widget = ColorField()
            widget.setFixedWidth(self.FIELD_WIDTH)
            widget.edit.editingFinished.connect(apply_now)
        elif setting.kind == "bands":
            widget = BandTable(apply_now)
        elif setting.kind == "path":
            widget = PathField(apply_now)
        elif setting.kind == "duration":
            widget = QLineEdit()
            widget.setPlaceholderText("e.g. 20s, 5m, 1h30m, 20m20s100ms")
            widget.setFixedWidth(self.FIELD_WIDTH)
            widget.editingFinished.connect(
                lambda w=widget: (w.setText(format_duration(parse_duration(w.text()))),
                                  apply_now()))
        else:
            widget = QLineEdit()
            widget.setFixedWidth(self.FIELD_WIDTH)
            widget.editingFinished.connect(apply_now)

        self.widgets[setting.key] = widget
        return widget

    def _load(self, values):
        self._loading = True
        for setting in config.SETTINGS:
            widget = self.widgets[setting.key]
            value = values.get(setting.key, setting.default)
            if setting.kind == "bool":
                widget.setChecked(bool(value))
            elif setting.kind == "int":
                widget.setValue(int(value))
            elif setting.kind == "bands":
                widget.setValue(value)
            else:
                widget.setText(str(value))
        self._loading = False

    def _collect(self):
        values = {}
        for setting in config.SETTINGS:
            widget = self.widgets[setting.key]
            if setting.kind == "bool":
                values[setting.key] = widget.isChecked()
            elif setting.kind == "int":
                values[setting.key] = int(widget.value())
            elif setting.kind == "bands":
                values[setting.key] = widget.value()
            else:
                values[setting.key] = widget.text()
        return values

    def _apply(self, *_args):
        """Persist and redraw immediately — there is no Save button."""
        if self._loading:
            return
        overrides = config.save(self._collect())
        config.reload()
        self.save_note.setText(
            f"Saved · {len(overrides)} setting(s) differ from the defaults"
            if overrides else "Saved · everything is at its default")
        self.refresh()

    def _on_defaults(self):
        self._load(config.DEFAULTS)
        self._apply()

    # -- About ------------------------------------------------------------
    def _about_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(10)

        header = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(QIcon(str(LOGO)).pixmap(72, 72))
        header.addWidget(logo)

        titles = QVBoxLayout()
        name = QLabel("Claude Status Bar")
        title_font = QFont(name.font())
        title_font.setPointSize(title_font.pointSize() + 6)
        title_font.setBold(True)
        name.setFont(title_font)
        version = QLabel(f"Version {__version__} · by {AUTHOR}")
        version.setStyleSheet(muted(version))
        titles.addWidget(name)
        titles.addWidget(version)
        titles.addStretch(1)
        header.addLayout(titles, 1)
        outer.addLayout(header)

        summary = QLabel(SUMMARY)
        summary.setWordWrap(True)
        outer.addWidget(summary)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        outer.addWidget(line)

        links = QGridLayout()
        links.setColumnStretch(1, 1)
        links.setHorizontalSpacing(16)
        links.setVerticalSpacing(8)
        rows = [
            ("Repository", PROJECT_URL, "Source, releases and documentation"),
            ("Report an issue", ISSUES_URL, "Bugs and feature requests"),
            ("Donate", DONATE_URL, "Support development"),
            ("Author", AUTHOR_URL, f"{AUTHOR} on GitHub"),
        ]
        for index, (label, url, note) in enumerate(rows):
            button = QPushButton(label)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
            links.addWidget(button, index, 0)

            detail = QLabel(f'{note}<br/><a href="{url}">{url}</a>')
            detail.setOpenExternalLinks(True)
            detail.setTextInteractionFlags(Qt.TextBrowserInteraction)
            detail.setStyleSheet(muted(detail))
            links.addWidget(detail, index, 1)
        outer.addLayout(links)

        line2 = QFrame()
        line2.setFrameShape(QFrame.HLine)
        line2.setFrameShadow(QFrame.Sunken)
        outer.addWidget(line2)

        licence = QLabel(
            f"<b>License</b><br/>{LICENSE} — the GNU General Public License, "
            "version 3 or later.<br/>This program comes with absolutely no "
            "warranty. It is free software, and you are welcome to "
            "redistribute it under the terms of the GPL.<br/>"
            '<a href="https://www.gnu.org/licenses/gpl-3.0.html">'
            "Read the full license</a>")
        licence.setWordWrap(True)
        licence.setOpenExternalLinks(True)
        outer.addWidget(licence)

        self.account_note = QLabel()
        self.account_note.setWordWrap(True)
        self.account_note.setStyleSheet(muted(self.account_note))
        outer.addWidget(self.account_note)

        updates = QHBoxLayout()
        self.update_note = QLabel()
        self.update_note.setWordWrap(True)
        self.update_note.setOpenExternalLinks(True)
        self.update_note.setStyleSheet(muted(self.update_note))
        updates.addWidget(self.update_note, 1)
        self.update_button = QPushButton("Check for updates")
        self.update_button.clicked.connect(lambda: self._check_updates(force=True))
        updates.addWidget(self.update_button)
        outer.addLayout(updates)

        self._show_update(cached_update())
        if cfg["check_updates"]:
            self._check_updates(force=False)

        outer.addStretch(1)
        return page

    def _check_updates(self, force=False):
        self.update_button.setEnabled(False)
        self.update_note.setText("Checking…")
        task = UpdateTask(force)
        task.signals.done.connect(self._show_update)
        QThreadPool.globalInstance().start(task)

    def _show_update(self, result):
        self.update_button.setEnabled(True)
        if not result:
            self.update_note.setText("Updates have not been checked yet.")
            return
        text = describe_update(result)
        if result.get("newer"):
            url = result.get("url") or PROJECT_URL
            text += f' <a href="{url}">Open the release</a>'
        self.update_note.setText(text)

    # -- refresh ----------------------------------------------------------
    def refresh(self):
        wanted = max(1000, int(config.seconds("refresh") * 1000))
        if self.timer.interval() != wanted:
            self.timer.setInterval(wanted)

        data = self._last_data = Data()
        resets = {"5h": data.h5_reset, "wk": data.wk_reset}
        for card, (label, used, countdown) in zip(self.cards, limit_rows(data)):
            card.update_values(label, used, countdown,
                               time_left_pct(data, label), resets.get(label, 0),
                               burn=data.wk_burn_5h if label == "wk" else None,
                               h5_reset=data.h5_reset if label == "wk" else 0)

        subtitle = f"{data.model or 'Claude'} · reading {claude_dir()}"
        if data.note:
            subtitle += f" · {data.note}"
        self.subtitle.setText(subtitle)
        self.subtitle.setStyleSheet(
            f"color: {cfg['warn_color']};" if data.note_warn else muted(self.subtitle))

        context = f"{human(data.ctx_in)}+{human(data.ctx_out)} / {human(data.ctx_win)}"
        rows = [
            ("Model", data.model or "—"),
            ("Session cost", f"${float(data.cost):.2f}"),
            ("Context", f"{pct(data.ctx_use)} used   ({context})"),
            ("Today", f"{human(data.today_tok)} tokens · {data.today_msg} messages "
                      f"· {data.today_ses} sessions"),
            ("Last 7 days", f"{human(data.week_tok)} tokens"),
            ("All time", f"{data.total_msg} messages · {data.total_ses} sessions"),
            ("Snapshots", f"{len(data.records)} stored · newest {dur(data.age)} old"),
            ("State file", str(state_file())),
        ]
        if data.credits_mode:
            rows.insert(2, ("Extra usage", f"{pct(data.credit_use)} of the monthly limit"))
        self._set_grid(self.details, rows)

        details = account()
        info = [(name, value) for name, value in details.items() if value]
        signed_in = details.get("Email") or details.get("Name") or ""
        self.account_note.setText(
            f"Signed in to Claude as {signed_in}." if signed_in
            else "No Claude account details found in ~/.claude.json.")
        self.account_heading.setVisible(bool(info))
        self._set_grid(self.account_grid, info)

        self._fill_sessions(data)
        self._fill_history()


def run():
    """Entry point for `claude-statusbar --gui` (window without the tray).

    The Xfce plugin runs this on every click, so a second launch has to reach
    the window that is already open rather than opening another one.
    """
    import sys

    from PySide6.QtWidgets import QApplication

    from claude_statusbar.single import SingleInstance

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Claude Status Bar")
    app.setWindowIcon(QIcon(str(LOGO)))

    guard = SingleInstance()
    if guard.hand_over():
        return 0

    window = MainWindow()

    def present():
        window.refresh()
        window.showNormal()
        window.raise_()
        window.activateWindow()

    guard.listen(present)
    window.show()
    return app.exec()
