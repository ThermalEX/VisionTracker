"""Vision Tracker - Logs & Statistics Page"""

from datetime import datetime

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QTextCursor
from PyQt5.QtWidgets import QPushButton, QScrollBar, QWidget, QTextEdit

from siui.components import SiLabel, SiSimpleButton, SiTitledWidgetGroup
from siui.components.page import SiPage
from siui.core import SiColor, SiGlobal
from siui.gui import SiFont


LOG_LEVEL_COLORS = {
    "ERROR":   "#FF6767",
    "WARN":    "#FFD467",
    "SUCCESS": "#78E09A",
    "INFO":    "#5BA3F5",
}

BUTTON_STYLE = """
QPushButton {
    background-color: #201d23;
    border: 1px solid #3a3540;
    border-radius: 6px;
    color: #F0EEF2;
    padding: 0 14px;
    font-family: "Segoe UI", "Microsoft YaHei";
    font-size: 13px;
}
QPushButton:hover {
    background-color: #2b2630;
    border: 1px solid #D087DF;
}
QPushButton:pressed {
    background-color: #352f3c;
}
"""


# ── Shared card primitives ─────────────────────────────────────────────────────

class _PanelCard(QWidget):
    def __init__(self, parent=None, radius: int = 10):
        super().__init__(parent)
        self._radius = radius
        self._background = QColor(SiGlobal.siui.colors["INTERFACE_BG_C"])

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._background)
        painter.drawRoundedRect(self.rect(), self._radius, self._radius)


class _MetricCard(_PanelCard):
    def __init__(self, title: str, accent: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 128)
        self._title = title
        self._value = "--"
        self._subtitle = ""
        self._accent = QColor(accent)
        self._history: list = [0.0] * 24

    def setData(self, value: str, subtitle: str, history=None):
        self._value = value
        self._subtitle = subtitle
        if history is not None:
            hist = list(history)[-24:]
            if hist:
                self._history = hist
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(0, 0, self.width(), self.height())
        c0 = QColor(self._accent)
        c0.setAlpha(70)
        c1 = QColor(self._accent)
        c1.setAlpha(10)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(1.0, c1)
        painter.setBrush(grad)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

        painter.setPen(QColor("#F2EDF7"))
        painter.setFont(SiFont.getFont(size=11))
        painter.drawText(QRectF(18, 14, self.width() - 36, 20),
                         Qt.AlignLeft | Qt.AlignVCenter, self._title)

        painter.setFont(SiFont.getFont(size=24, weight=QFont.Bold))
        painter.drawText(QRectF(18, 34, self.width() - 36, 36),
                         Qt.AlignLeft | Qt.AlignVCenter, self._value)

        painter.setPen(QColor("#B8ACC7"))
        painter.setFont(SiFont.getFont(size=10))
        painter.drawText(QRectF(18, 72, self.width() - 36, 22),
                         Qt.AlignLeft | Qt.AlignTop, self._subtitle)

        points = list(self._history)
        if len(points) >= 2:
            min_v, max_v = min(points), max(points)
            span = max(max_v - min_v, 1e-6)
            left, top = 18, self.height() - 28
            w, h = self.width() - 36, 14
            path = QPainterPath()
            for idx, v in enumerate(points):
                x = left + w * idx / max(1, len(points) - 1)
                y = top + h - ((v - min_v) / span) * h
                pt = QPointF(x, y)
                if idx == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
            painter.setPen(QPen(self._accent, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)


class _LineChartCard(_PanelCard):
    def __init__(self, title: str, subtitle: str, accent: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(456, 240)
        self._title = title
        self._subtitle = subtitle
        self._accent = QColor(accent)
        self._values: list = []
        self._current_label = ""

    def setSeries(self, values, current_label: str = ""):
        self._values = list(values)[-60:]
        self._current_label = current_label
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(QColor("#F5EEF9"))
        painter.setFont(SiFont.getFont(size=13, weight=QFont.Bold))
        painter.drawText(QRectF(20, 16, self.width() - 40, 22),
                         Qt.AlignLeft | Qt.AlignVCenter, self._title)
        painter.setPen(QColor("#AFA2BE"))
        painter.setFont(SiFont.getFont(size=10))
        painter.drawText(QRectF(20, 38, self.width() - 40, 18),
                         Qt.AlignLeft | Qt.AlignVCenter, self._subtitle)

        chart_rect = QRectF(20, 68, self.width() - 40, 132)
        painter.setPen(QPen(QColor("#4C4555"), 1))
        for i in range(4):
            y = chart_rect.top() + chart_rect.height() * i / 3
            painter.drawLine(QPointF(chart_rect.left(), y),
                             QPointF(chart_rect.right(), y))

        values = self._values or [0.0, 0.0]
        min_v, max_v = min(values), max(values)
        span = max(max_v - min_v, 1.0)
        path = QPainterPath()
        fill_path = QPainterPath()
        for idx, v in enumerate(values):
            x = chart_rect.left() + chart_rect.width() * idx / max(1, len(values) - 1)
            y = chart_rect.bottom() - ((v - min_v) / span) * chart_rect.height()
            pt = QPointF(x, y)
            if idx == 0:
                path.moveTo(pt)
                fill_path.moveTo(chart_rect.left(), chart_rect.bottom())
                fill_path.lineTo(pt)
            else:
                path.lineTo(pt)
                fill_path.lineTo(pt)
        fill_path.lineTo(chart_rect.right(), chart_rect.bottom())
        fill_path.closeSubpath()

        grad = QLinearGradient(chart_rect.left(), chart_rect.top(),
                               chart_rect.left(), chart_rect.bottom())
        a0 = QColor(self._accent)
        a0.setAlpha(90)
        a1 = QColor(self._accent)
        a1.setAlpha(8)
        grad.setColorAt(0.0, a0)
        grad.setColorAt(1.0, a1)
        painter.fillPath(fill_path, grad)
        painter.setPen(QPen(self._accent, 2.4))
        painter.drawPath(path)

        painter.setPen(QColor("#F5EEF9"))
        painter.setFont(SiFont.getFont(size=18, weight=QFont.Bold))
        painter.drawText(QRectF(20, 204, 160, 22),
                         Qt.AlignLeft | Qt.AlignVCenter, self._current_label)


# ── Scrollable chart (full history + pan) ─────────────────────────────────────

class _ScrollableLineChartCard(_PanelCard):
    """Line chart that stores all history and lets the user scroll back."""

    VIEWPORT = 60  # data points visible at once

    def __init__(self, title: str, subtitle: str, accent: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(456, 256)
        self._title = title
        self._subtitle = subtitle
        self._accent = QColor(accent)
        self._values: list = []
        self._current_label = ""

        self._scrollbar = QScrollBar(Qt.Horizontal, self)
        self._scrollbar.setGeometry(20, 238, self.width() - 40, 10)
        self._scrollbar.setRange(0, 0)
        self._scrollbar.setSingleStep(1)
        self._scrollbar.setPageStep(self.VIEWPORT)
        self._scrollbar.valueChanged.connect(self.update)
        self._scrollbar.setStyleSheet(
            "QScrollBar:horizontal {"
            "  background: #1E1A26; height: 8px; border-radius: 4px;"
            "}"
            "QScrollBar::handle:horizontal {"
            "  background: #5A5066; border-radius: 4px; min-width: 20px;"
            "}"
            "QScrollBar::add-line:horizontal,"
            "QScrollBar::sub-line:horizontal { width: 0; }"
        )

    def setSeries(self, values, current_label: str = ""):
        at_end = self._scrollbar.value() >= self._scrollbar.maximum()
        self._values = list(values)
        self._current_label = current_label
        max_scroll = max(0, len(self._values) - self.VIEWPORT)
        self._scrollbar.setRange(0, max_scroll)
        if at_end:
            self._scrollbar.setValue(max_scroll)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.setPen(QColor("#F5EEF9"))
        painter.setFont(SiFont.getFont(size=13, weight=QFont.Bold))
        painter.drawText(QRectF(20, 16, self.width() - 40, 22),
                         Qt.AlignLeft | Qt.AlignVCenter, self._title)
        painter.setPen(QColor("#AFA2BE"))
        painter.setFont(SiFont.getFont(size=10))
        painter.drawText(QRectF(20, 38, self.width() - 40, 18),
                         Qt.AlignLeft | Qt.AlignVCenter, self._subtitle)

        chart_rect = QRectF(20, 68, self.width() - 40, 124)
        painter.setPen(QPen(QColor("#4C4555"), 1))
        for i in range(4):
            y = chart_rect.top() + chart_rect.height() * i / 3
            painter.drawLine(QPointF(chart_rect.left(), y),
                             QPointF(chart_rect.right(), y))

        start = self._scrollbar.value()
        values = self._values[start:start + self.VIEWPORT] if self._values else [0.0, 0.0]
        if len(values) < 2:
            values = [0.0, 0.0]

        min_v, max_v = min(values), max(values)
        span = max(max_v - min_v, 1.0)
        path = QPainterPath()
        fill_path = QPainterPath()
        for idx, v in enumerate(values):
            x = chart_rect.left() + chart_rect.width() * idx / max(1, len(values) - 1)
            y = chart_rect.bottom() - ((v - min_v) / span) * chart_rect.height()
            pt = QPointF(x, y)
            if idx == 0:
                path.moveTo(pt)
                fill_path.moveTo(chart_rect.left(), chart_rect.bottom())
                fill_path.lineTo(pt)
            else:
                path.lineTo(pt)
                fill_path.lineTo(pt)
        fill_path.lineTo(chart_rect.right(), chart_rect.bottom())
        fill_path.closeSubpath()

        grad = QLinearGradient(chart_rect.left(), chart_rect.top(),
                               chart_rect.left(), chart_rect.bottom())
        a0 = QColor(self._accent); a0.setAlpha(90)
        a1 = QColor(self._accent); a1.setAlpha(8)
        grad.setColorAt(0.0, a0)
        grad.setColorAt(1.0, a1)
        painter.fillPath(fill_path, grad)
        painter.setPen(QPen(self._accent, 2.4))
        painter.drawPath(path)

        painter.setPen(QColor("#F5EEF9"))
        painter.setFont(SiFont.getFont(size=18, weight=QFont.Bold))
        painter.drawText(QRectF(20, 200, 160, 22),
                         Qt.AlignLeft | Qt.AlignVCenter, self._current_label)

        total = len(self._values)
        if total > self.VIEWPORT:
            end = min(start + self.VIEWPORT, total)
            painter.setPen(QColor("#AFA2BE"))
            painter.setFont(SiFont.getFont(size=10))
            painter.drawText(QRectF(0, 200, self.width() - 20, 22),
                             Qt.AlignRight | Qt.AlignVCenter, f"{start + 1}–{end} / {total}")


# ── Log panel ──────────────────────────────────────────────────────────────────

class _LogPanel(_PanelCard):
    """Scrollable log viewer with level-filter buttons."""

    _FILTER_DEFS = [
        ("ALL",     "#8E79D9", "rgba(142, 121, 217, 0.15)"),
        ("ERROR",   "#FF6767", "rgba(255, 103, 103, 0.15)"),
        ("WARN",    "#FFD467", "rgba(255, 212, 103, 0.15)"),
        ("INFO",    "#5BA3F5", "rgba(91,  163, 245, 0.15)"),
        ("SUCCESS", "#78E09A", "rgba(120, 224, 154, 0.15)"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(932, 340)
        self._active_filters: set = {"ALL", "ERROR", "WARN", "INFO", "SUCCESS"}
        self._messages: list = []

        # Filter buttons — neutral default, colored when active
        _DEFAULT_STYLE = (
            "QPushButton {"
            "  color: #6E6380;"
            "  background: #252030;"
            "  border: none;"
            "  border-radius: 6px;"
            "  font-size: 10px;"
            "  font-family: 'Segoe UI', sans-serif;"
            "}"
            "QPushButton:hover { background: #2C2738; }"
        )
        x_off = 16
        self._filter_btns: dict = {}
        for label, color, bg in self._FILTER_DEFS:
            btn = QPushButton(label, self)
            btn.setFixedSize(70, 26)
            btn.move(x_off, 12)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.setStyleSheet(
                _DEFAULT_STYLE +
                f"QPushButton:checked {{ color: {color}; background: {bg}; }}"
            )
            btn.clicked.connect(lambda _=False, lbl=label: self._toggleFilter(lbl))
            self._filter_btns[label] = btn
            x_off += 76

        # Clear button (icon)
        self._clear_btn = SiSimpleButton(self)
        self._clear_btn.setFixedSize(30, 26)
        self._clear_btn.move(self.width() - 46, 12)
        self._clear_btn.attachment().load(
            SiGlobal.siui.iconpack.get("ic_fluent_delete_regular")
        )
        self._clear_btn.setToolTip("Clear logs")
        self._clear_btn.clicked.connect(self.clear)

        # Text area
        self._text = QTextEdit(self)
        self._text.setGeometry(12, 50, 908, 278)
        self._text.setReadOnly(True)
        self._text.setStyleSheet(
            "QTextEdit {"
            "  background: transparent;"
            "  border: none;"
            "  color: #F5EEF9;"
            "  font-family: 'Consolas', 'Courier New', monospace;"
            "  font-size: 11px;"
            "}"
            "QScrollBar:vertical {"
            "  background: #1E1A26;"
            "  width: 5px;"
            "  border-radius: 2px;"
            "}"
            "QScrollBar::handle:vertical {"
            "  background: #5A5066;"
            "  border-radius: 2px;"
            "}"
            "QScrollBar::add-line:vertical,"
            "QScrollBar::sub-line:vertical { height: 0; }"
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(QColor("#3A3245"), 1))
        painter.drawLine(12, 47, self.width() - 12, 47)

    def _toggleFilter(self, label: str):
        if label == "ALL":
            # ALL toggles all on or all off
            all_on = all(lbl in self._active_filters for lbl, *_ in self._FILTER_DEFS)
            if all_on:
                self._active_filters.clear()
            else:
                self._active_filters = {lbl for lbl, *_ in self._FILTER_DEFS}
        else:
            if label in self._active_filters:
                self._active_filters.discard(label)
                self._active_filters.discard("ALL")
            else:
                self._active_filters.add(label)
                if all(lbl in self._active_filters for lbl, *_ in self._FILTER_DEFS if lbl != "ALL"):
                    self._active_filters.add("ALL")
        for lbl, btn in self._filter_btns.items():
            btn.setChecked(lbl in self._active_filters)
        self._rebuild()

    def addMessage(self, timestamp: str, level: str, message: str):
        self._messages.append((timestamp, level, message))
        if len(self._messages) > 1000:
            self._messages = self._messages[-1000:]
        if level in self._active_filters or "ALL" in self._active_filters:
            self._appendLine(timestamp, level, message)

    def _appendLine(self, timestamp: str, level: str, message: str):
        color = LOG_LEVEL_COLORS.get(level, "#D0C8E0")
        safe_msg = (message
                    .replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;"))
        html = (
            f'<span style="color:#6E6380;">[{timestamp}]</span>&nbsp;'
            f'<span style="color:{color};font-weight:bold;">{level:<7}</span>&nbsp;'
            f'<span style="color:#E8E0F0;">{safe_msg}</span><br>'
        )
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._text.setTextCursor(cursor)
        self._text.insertHtml(html)
        sb = self._text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _rebuild(self):
        self._text.clear()
        for ts, lvl, msg in self._messages:
            if lvl in self._active_filters or "ALL" in self._active_filters:
                self._appendLine(ts, lvl, msg)

    def clear(self):
        self._messages.clear()
        self._text.clear()


# ── Main page ──────────────────────────────────────────────────────────────────

class LogsPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Logs")

        self._tracker_manager = None
        self._recording = False
        self._latest_stats: dict = {}
        self._shots_history: list = []
        self._moves_history: list = []
        self._last_shots = 0
        self._last_moves = 0

        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(18)
        self.titled_group.setAdjustWidgetsSize(True)

        self._buildHero()
        self._buildMetricRow()
        self._buildCharts()
        self._buildLogPanel()
        self.titled_group.addPlaceholder(64)

        self.setAttachment(self.titled_group)

    # ── Build ──────────────────────────────────────────────────────────────────

    def _buildHero(self):
        self.hero = _PanelCard(self)
        self.hero.setFixedSize(932, 100)

        title_label = SiLabel(self.hero)
        title_label.setGeometry(24, 14, 450, 30)
        title_label.setFont(SiFont.getFont(size=20, weight=QFont.Bold))
        title_label.setTextColor(self.getColor(SiColor.TEXT_A))
        title_label.setText("Logs & Statistics")

        subtitle_label = SiLabel(self.hero)
        subtitle_label.setGeometry(24, 48, 600, 22)
        subtitle_label.setFont(SiFont.getFont(size=11))
        subtitle_label.setTextColor(self.getColor(SiColor.TEXT_D))
        subtitle_label.setText("Real-time tracking logs with session statistics and charts")

        self.record_button = QPushButton(self.hero)
        self.record_button.setGeometry(682, 30, 150, 40)
        self.record_button.setStyleSheet(BUTTON_STYLE)
        self.record_button.setText("Start Recording")
        self.record_button.clicked.connect(self._toggleRecording)

        self.status_badge = SiLabel(self.hero)
        self.status_badge.setGeometry(848, 30, 70, 40)
        self.status_badge.setAlignment(Qt.AlignCenter)
        self.status_badge.setFont(SiFont.getFont(size=10, weight=QFont.Bold))
        self.status_badge.setStyleSheet(
            f"background: {SiGlobal.siui.colors['INTERFACE_BG_B']};"
            "border-radius: 8px; color: #6E6380;"
        )
        self.status_badge.setText("IDLE")

        self.titled_group.addWidget(self.hero)

    def _buildMetricRow(self):
        self.metric_host = QWidget(self)
        self.metric_host.setFixedSize(932, 128)

        self.card_shots = _MetricCard("Shots Fired", "#F2687F", self.metric_host)
        self.card_shots.move(0, 0)
        self.card_moves = _MetricCard("Mouse Moves", "#57D4C3", self.metric_host)
        self.card_moves.move(237, 0)
        self.card_locks = _MetricCard("Target Locks", "#F3B95C", self.metric_host)
        self.card_locks.move(474, 0)
        self.card_frames = _MetricCard("Frames", "#8E79D9", self.metric_host)
        self.card_frames.move(711, 0)

        self.titled_group.addWidget(self.metric_host)

    def _buildCharts(self):
        self.chart_host = QWidget(self)
        self.chart_host.setFixedSize(932, 256)

        self.shots_chart = _ScrollableLineChartCard(
            "Shots / Interval",
            "Auto-fire events per update cycle",
            "#F2687F",
            self.chart_host,
        )
        self.shots_chart.move(0, 0)

        self.moves_chart = _ScrollableLineChartCard(
            "Mouse Moves / Interval",
            "Aim correction operations per update cycle",
            "#57D4C3",
            self.chart_host,
        )
        self.moves_chart.move(476, 0)

        self.titled_group.addWidget(self.chart_host)

    def _buildLogPanel(self):
        self.log_panel = _LogPanel(self)
        self.titled_group.addWidget(self.log_panel)

    # ── Public API ─────────────────────────────────────────────────────────────

    def setTrackerManager(self, manager):
        if not manager:
            return
        self._tracker_manager = manager
        if hasattr(manager, "runtime_stats_changed"):
            manager.runtime_stats_changed.connect(self._onRuntimeStatsChanged)
        if hasattr(manager, "log_message"):
            manager.log_message.connect(self._onLogMessage)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _toggleRecording(self):
        self._recording = not self._recording
        if self._recording:
            self.record_button.setText("Stop Recording")
            self.status_badge.setText("● REC")
            self.status_badge.setStyleSheet(
                "background: #3D1A20; border-radius: 8px; color: #F2687F;"
            )
            # Start fresh session
            self.log_panel.clear()
            self._latest_stats.clear()
            self._shots_history = []
            self._moves_history = []
            self._last_shots = 0
            self._last_moves = 0
            self._refreshMetrics()
        else:
            self.record_button.setText("Start Recording")
            self.status_badge.setText("IDLE")
            self.status_badge.setStyleSheet(
                f"background: {SiGlobal.siui.colors['INTERFACE_BG_B']};"
                "border-radius: 8px; color: #6E6380;"
            )

    def _onRuntimeStatsChanged(self, stats: dict):
        if not self._recording:
            return
        self._latest_stats.update(stats or {})

        shots = int(self._latest_stats.get("auto_clicks", 0))
        moves = int(self._latest_stats.get("mouse_moves", 0))
        self._shots_history.append(float(max(0, shots - self._last_shots)))
        self._moves_history.append(float(max(0, moves - self._last_moves)))
        self._last_shots = shots
        self._last_moves = moves

        self._refreshMetrics()

    def _onLogMessage(self, message: str, level: str):
        if not self._recording:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_panel.addMessage(ts, str(level).upper(), str(message))
        self.titled_group.adjustSize()

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _refreshMetrics(self):
        s = self._latest_stats
        shots  = int(s.get("auto_clicks", 0))
        moves  = int(s.get("mouse_moves", 0))
        locks  = int(s.get("target_locks", 0))
        frames = int(s.get("frames_processed", 0))

        shots_hist = list(self._shots_history)
        moves_hist = list(self._moves_history)

        self.card_shots.setData(str(shots),     "Total shots fired",      shots_hist)
        self.card_moves.setData(str(moves),     "Aim move operations",    moves_hist)
        self.card_locks.setData(str(locks),     "Target acquisitions",    [float(locks)] * 24)
        self.card_frames.setData(f"{frames:,}", "Frames processed",       [float(frames % 100)] * 24)

        self.shots_chart.setSeries(shots_hist, f"{shots} total")
        self.moves_chart.setSeries(moves_hist, f"{moves} total")
        self.titled_group.adjustSize()
