"""Vision Tracker - Performance Monitor Page"""

from collections import deque
from datetime import datetime

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QApplication, QWidget

from siui.components import SiLabel, SiSimpleButton, SiTitledWidgetGroup
from siui.components.page import SiPage
from siui.core import Si, SiColor, SiGlobal
from siui.gui import SiFont


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
        self._history = deque([0.0] * 24, maxlen=24)

    def setData(self, value: str, subtitle: str, history=None):
        self._value = value
        self._subtitle = subtitle
        if history:
            hist = list(history)[-24:]
            if hist:
                self._history = deque(hist, maxlen=24)
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
        painter.drawText(QRectF(18, 14, self.width() - 36, 20), Qt.AlignLeft | Qt.AlignVCenter, self._title)

        painter.setFont(SiFont.getFont(size=24, weight=QFont.Bold))
        painter.drawText(QRectF(18, 34, self.width() - 36, 36), Qt.AlignLeft | Qt.AlignVCenter, self._value)

        painter.setPen(QColor("#B8ACC7"))
        painter.setFont(SiFont.getFont(size=10))
        painter.drawText(QRectF(18, 72, self.width() - 36, 22), Qt.AlignLeft | Qt.AlignTop, self._subtitle)

        points = list(self._history)
        if len(points) >= 2:
            min_v = min(points)
            max_v = max(points)
            span = max(max_v - min_v, 1e-6)
            left, top, width, height = 18, self.height() - 28, self.width() - 36, 14
            path = QPainterPath()
            for idx, value in enumerate(points):
                x = left + width * idx / max(1, len(points) - 1)
                y = top + height - ((value - min_v) / span) * height
                point = QPointF(x, y)
                if idx == 0:
                    path.moveTo(point)
                else:
                    path.lineTo(point)
            painter.setPen(QPen(self._accent, 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)


class _ChartCard(_PanelCard):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(456, 240)
        self._title = title
        self._subtitle = subtitle

    def _draw_header(self, painter: QPainter):
        painter.setPen(QColor("#F5EEF9"))
        painter.setFont(SiFont.getFont(size=13, weight=QFont.Bold))
        painter.drawText(QRectF(20, 16, self.width() - 40, 22), Qt.AlignLeft | Qt.AlignVCenter, self._title)
        painter.setPen(QColor("#AFA2BE"))
        painter.setFont(SiFont.getFont(size=10))
        painter.drawText(QRectF(20, 38, self.width() - 40, 18), Qt.AlignLeft | Qt.AlignVCenter, self._subtitle)


class _LineChartCard(_ChartCard):
    def __init__(self, title: str, subtitle: str, accent: str, parent=None):
        super().__init__(title, subtitle, parent)
        self._accent = QColor(accent)
        self._values = []
        self._current_label = ""

    def setSeries(self, values, current_label: str):
        self._values = list(values)[-60:]
        self._current_label = current_label
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_header(painter)

        chart_rect = QRectF(20, 68, self.width() - 40, 132)
        painter.setPen(QPen(QColor("#4C4555"), 1))
        for i in range(4):
            y = chart_rect.top() + chart_rect.height() * i / 3
            painter.drawLine(
                QPointF(chart_rect.left(), y),
                QPointF(chart_rect.right(), y),
            )

        values = self._values or [0.0, 0.0]
        min_v = min(values)
        max_v = max(values)
        span = max(max_v - min_v, 1.0)
        path = QPainterPath()
        fill_path = QPainterPath()
        for idx, value in enumerate(values):
            x = chart_rect.left() + chart_rect.width() * idx / max(1, len(values) - 1)
            y = chart_rect.bottom() - ((value - min_v) / span) * chart_rect.height()
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

        grad = QLinearGradient(chart_rect.left(), chart_rect.top(), chart_rect.left(), chart_rect.bottom())
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
        painter.drawText(QRectF(20, 204, 120, 22), Qt.AlignLeft | Qt.AlignVCenter, self._current_label)


class _BarChartCard(_ChartCard):
    def __init__(self, title: str, subtitle: str, parent=None):
        super().__init__(title, subtitle, parent)
        self._bars = []

    def setBars(self, bars):
        self._bars = bars
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self._draw_header(painter)

        chart_rect = QRectF(20, 74, self.width() - 40, 112)
        painter.setPen(QPen(QColor("#4C4555"), 1))
        painter.drawLine(
            QPointF(chart_rect.left(), chart_rect.bottom()),
            QPointF(chart_rect.right(), chart_rect.bottom()),
        )

        if not self._bars:
            return

        max_v = max(max(v, 1) for _, v, _ in self._bars)
        gap = 18
        bar_w = (chart_rect.width() - gap * (len(self._bars) - 1)) / len(self._bars)
        for idx, (label, value, color_hex) in enumerate(self._bars):
            x = chart_rect.left() + idx * (bar_w + gap)
            height = chart_rect.height() * (value / max_v if max_v else 0)
            bar_rect = QRectF(x, chart_rect.bottom() - height, bar_w, height)
            color = QColor(color_hex)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#2A2630"))
            painter.drawRoundedRect(QRectF(x, chart_rect.top(), bar_w, chart_rect.height()), 6, 6)
            painter.setBrush(color)
            painter.drawRoundedRect(bar_rect, 6, 6)

            painter.setPen(QColor("#F5EEF9"))
            painter.setFont(SiFont.getFont(size=11, weight=QFont.Bold))
            painter.drawText(QRectF(x, chart_rect.bottom() + 4, bar_w, 18), Qt.AlignCenter, str(value))
            painter.setPen(QColor("#AEA3BC"))
            painter.setFont(SiFont.getFont(size=10))
            painter.drawText(QRectF(x, chart_rect.bottom() + 20, bar_w, 16), Qt.AlignCenter, label)


class _TimelineCard(_PanelCard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(932, 224)
        self._events = []

    def setEvents(self, events):
        self._events = list(events)[-6:]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#F5EEF9"))
        painter.setFont(SiFont.getFont(size=13, weight=QFont.Bold))
        painter.drawText(QRectF(20, 16, self.width() - 40, 22), Qt.AlignLeft | Qt.AlignVCenter, "Recent Events")
        painter.setPen(QColor("#AFA2BE"))
        painter.setFont(SiFont.getFont(size=10))
        painter.drawText(QRectF(20, 38, self.width() - 40, 18), Qt.AlignLeft | Qt.AlignVCenter,
                         "Latest runtime events, calibration records and tracker state changes")

        if not self._events:
            painter.setPen(QColor("#AFA2BE"))
            painter.drawText(QRectF(20, 90, self.width() - 40, 24), Qt.AlignCenter, "No events yet.")
            return

        start_y = 78
        row_h = 22
        line_x = 30
        painter.setPen(QPen(QColor("#655674"), 2))
        painter.drawLine(
            QPointF(line_x, start_y),
            QPointF(line_x, start_y + row_h * (len(self._events) - 1)),
        )
        for idx, (timestamp, level, message) in enumerate(reversed(self._events)):
            y = start_y + idx * row_h
            level_color = {
                "ERROR": "#F2687F",
                "WARN": "#F5C35B",
                "SUCCESS": "#5FD69A",
            }.get(level, "#8E79D9")
            painter.setBrush(QColor(level_color))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(line_x, y), 4, 4)
            painter.setPen(QColor("#D8D0E2"))
            painter.setFont(SiFont.getFont(size=10, weight=QFont.Bold))
            painter.drawText(QRectF(44, y - 10, 92, 18), Qt.AlignLeft | Qt.AlignVCenter, timestamp)
            painter.setPen(QColor(level_color))
            painter.drawText(QRectF(134, y - 10, 74, 18), Qt.AlignLeft | Qt.AlignVCenter, level)
            painter.setPen(QColor("#F5EEF9"))
            painter.setFont(SiFont.getFont(size=10))
            painter.drawText(QRectF(208, y - 10, self.width() - 228, 18), Qt.AlignLeft | Qt.AlignVCenter, message)


class StatisticsPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Performance Monitor")

        self._tracker_manager = None
        self._recent_events = []
        self._latest_stats = {
            "status": "stopped",
            "config_name": "Unknown",
            "window_title": "Fullscreen",
            "target_team": "T",
            "operation_mode": "auto_aim_fire",
            "target_class": "All",
            "current_mode": "ADRC",
            "current_fps": 0.0,
            "current_conf": 0.0,
            "current_dist": 0.0,
            "target_locked": False,
            "frames_processed": 0,
            "target_locks": 0,
            "auto_clicks": 0,
            "pause_count": 0,
            "resume_count": 0,
            "calibration_count": 0,
            "uptime_seconds": 0,
            "current_sensitivity": 0.0,
            "last_calibrated_sensitivity": None,
            "pid_kp": 0.0,
        }
        self._fps_history = deque([0.0] * 24, maxlen=60)
        self._lock_history = deque([0.0] * 24, maxlen=24)

        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(18)
        self.titled_group.setAdjustWidgetsSize(True)

        self._buildHero()
        self._buildMetricRow()
        self._buildCharts()
        self._buildCalibrationRow()
        self._buildTimeline()
        self.titled_group.addPlaceholder(64)

        self.setAttachment(self.titled_group)
        self._refreshUi()

    def _buildHero(self):
        self.hero = _PanelCard(self)
        self.hero.setFixedSize(932, 118)

        self.hero_title = SiLabel(self.hero)
        self.hero_title.setGeometry(24, 18, 420, 28)
        self.hero_title.setFont(SiFont.getFont(size=20, weight=QFont.Bold))
        self.hero_title.setTextColor(self.getColor(SiColor.TEXT_A))
        self.hero_title.setText("Performance Monitor")

        self.hero_subtitle = SiLabel(self.hero)
        self.hero_subtitle.setGeometry(24, 52, 600, 24)
        self.hero_subtitle.setFont(SiFont.getFont(size=11))
        self.hero_subtitle.setTextColor(self.getColor(SiColor.TEXT_D))
        self.hero_subtitle.setText("Visual trends for lock state, runtime performance and calibration output")

        self.hero_badge = SiLabel(self.hero)
        self.hero_badge.setGeometry(700, 26, 208, 50)
        self.hero_badge.setAlignment(Qt.AlignCenter)
        self.hero_badge.setStyleSheet(
            f"background-color: {SiGlobal.siui.colors['INTERFACE_BG_B']};"
            "border-radius: 10px;"
            "color: #F5EEF9;"
        )
        self.hero_badge.setFont(SiFont.getFont(size=11, weight=QFont.Bold))
        self.hero_badge.setText("STOPPED\nNo active session")

        self.titled_group.addWidget(self.hero)

    def _buildMetricRow(self):
        self.metric_host = QWidget(self)
        self.metric_host.setFixedSize(932, 128)

        self.metric_status = _MetricCard("Tracker Status", "#8E79D9", self.metric_host)
        self.metric_status.move(0, 0)
        self.metric_fps = _MetricCard("FPS", "#57D4C3", self.metric_host)
        self.metric_fps.move(237, 0)
        self.metric_lock = _MetricCard("Lock State", "#F3B95C", self.metric_host)
        self.metric_lock.move(474, 0)
        self.metric_uptime = _MetricCard("Runtime", "#F17CA8", self.metric_host)
        self.metric_uptime.move(711, 0)

        self.titled_group.addWidget(self.metric_host)

    def _buildCharts(self):
        self.chart_host = QWidget(self)
        self.chart_host.setFixedSize(932, 240)

        self.fps_chart = _LineChartCard("FPS Trend", "Recent frame-rate history", "#57D4C3", self.chart_host)
        self.fps_chart.move(0, 0)
        self.activity_chart = _BarChartCard("Session Activity", "Locks, clicks, pauses and calibrations", self.chart_host)
        self.activity_chart.move(476, 0)

        self.titled_group.addWidget(self.chart_host)

    def _buildCalibrationRow(self):
        self.calibration_host = _PanelCard(self)
        self.calibration_host.setFixedSize(932, 98)

        self.calibration_title = SiLabel(self.calibration_host)
        self.calibration_title.setGeometry(20, 16, 280, 24)
        self.calibration_title.setFont(SiFont.getFont(size=13, weight=QFont.Bold))
        self.calibration_title.setTextColor(self.getColor(SiColor.TEXT_A))
        self.calibration_title.setText("Calibration Output")

        self.calibration_desc = SiLabel(self.calibration_host)
        self.calibration_desc.setGeometry(20, 42, 500, 18)
        self.calibration_desc.setFont(SiFont.getFont(size=10))
        self.calibration_desc.setTextColor(self.getColor(SiColor.TEXT_D))
        self.calibration_desc.setText("Latest calibrated sensitivity and current controller gain")

        self.sensitivity_value_label = SiLabel(self.calibration_host)
        self.sensitivity_value_label.setGeometry(660, 22, 120, 34)
        self.sensitivity_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sensitivity_value_label.setFont(SiFont.getFont(size=22, weight=QFont.Bold))
        self.sensitivity_value_label.setTextColor("#F5EEF9")
        self.sensitivity_value_label.setText("--")

        self.sensitivity_meta_label = SiLabel(self.calibration_host)
        self.sensitivity_meta_label.setGeometry(470, 58, 310, 18)
        self.sensitivity_meta_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sensitivity_meta_label.setFont(SiFont.getFont(size=10))
        self.sensitivity_meta_label.setTextColor(self.getColor(SiColor.TEXT_D))
        self.sensitivity_meta_label.setText("PID Kp 0.000")

        self.copy_sensitivity_button = SiSimpleButton(self.calibration_host)
        self.copy_sensitivity_button.setGeometry(798, 22, 36, 36)
        self.copy_sensitivity_button.attachment().load(
            SiGlobal.siui.iconpack.get("ic_fluent_copy_regular")
        )
        self.copy_sensitivity_button.setToolTip("Copy sensitivity")
        self.copy_sensitivity_button.clicked.connect(self._copySensitivity)

        self.titled_group.addWidget(self.calibration_host)

    def _buildTimeline(self):
        self.timeline_card = _TimelineCard(self)
        self.titled_group.addWidget(self.timeline_card)

    def setTrackerManager(self, manager):
        if not manager:
            return
        self._tracker_manager = manager
        if hasattr(manager, "runtime_stats_changed"):
            manager.runtime_stats_changed.connect(self._onRuntimeStatsChanged)
        if hasattr(manager, "log_message"):
            manager.log_message.connect(self._onLogMessage)
        if hasattr(manager, "get_runtime_stats"):
            self._latest_stats.update(manager.get_runtime_stats())
            self._refreshUi()

    def _onRuntimeStatsChanged(self, stats: dict):
        self._latest_stats.update(stats or {})
        self._fps_history.append(float(self._latest_stats.get("current_fps", 0.0)))
        self._lock_history.append(1.0 if self._latest_stats.get("target_locked") else 0.0)
        self._refreshUi()

    def _onLogMessage(self, message: str, level: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self._recent_events.append((timestamp, str(level), str(message)))
        self._recent_events = self._recent_events[-8:]
        self.timeline_card.setEvents(self._recent_events)
        self.titled_group.adjustSize()

    def _refreshUi(self):
        stats = self._latest_stats

        status_text = str(stats.get("status", "stopped")).upper()
        target_locked = bool(stats.get("target_locked"))
        lock_text = "LOCKED" if target_locked else "IDLE"
        current_fps = float(stats.get("current_fps", 0.0))
        uptime_text = self._formatDuration(int(stats.get("uptime_seconds", 0)))
        conf_pct = float(stats.get("current_conf", 0.0)) * 100.0
        dist = float(stats.get("current_dist", 0.0))
        current_mode = str(stats.get("current_mode", "ADRC")).upper()

        config_name = str(stats.get("config_name", "Unknown"))
        window_title = str(stats.get("window_title", "Fullscreen"))
        operation_mode = str(stats.get("operation_mode", "auto_aim_fire")).replace("_", " ").title()
        target_team = str(stats.get("target_team", "T"))

        self.hero_badge.setText(f"{status_text}\n{config_name} | {target_team}")

        self.metric_status.setData(
            status_text,
            f"{operation_mode} | {window_title}",
            [1.0 if status_text == "RUNNING" else 0.0] * 24,
        )
        self.metric_fps.setData(
            f"{current_fps:.1f}",
            f"Mode {current_mode}",
            self._fps_history,
        )
        self.metric_lock.setData(
            lock_text,
            f"Confidence {conf_pct:.1f}% | Distance {dist:.1f}px",
            self._lock_history,
        )
        self.metric_uptime.setData(
            uptime_text,
            f"Team {target_team} | Frames {int(stats.get('frames_processed', 0)):,}",
            [float(stats.get("uptime_seconds", 0)) % 60 for _ in range(24)],
        )

        self.fps_chart.setSeries(self._fps_history, f"{current_fps:.1f} fps")
        self.activity_chart.setBars([
            ("Locks",  int(stats.get("target_locks", 0)),      "#8E79D9"),
            ("Clicks", int(stats.get("auto_clicks", 0)),       "#57D4C3"),
            ("Pauses", int(stats.get("pause_count", 0)),       "#F5C35B"),
            ("Calib",  int(stats.get("calibration_count", 0)), "#F17CA8"),
        ])

        calibrated = stats.get("last_calibrated_sensitivity")
        current_sens = float(stats.get("current_sensitivity", 0.0))
        pid_kp = float(stats.get("pid_kp", 0.0))
        display_sens = float(calibrated) if calibrated is not None else current_sens
        self.sensitivity_value_label.setText(f"{display_sens:.3f}")
        self.sensitivity_meta_label.setText(
            f"{'Calibrated' if calibrated is not None else 'Current'} sensitivity | PID Kp {pid_kp:.3f}"
        )

        if self._recent_events:
            self.timeline_card.setEvents(self._recent_events)
        self.titled_group.adjustSize()

    def _copySensitivity(self):
        calibrated = self._latest_stats.get("last_calibrated_sensitivity")
        value = float(calibrated) if calibrated is not None else float(self._latest_stats.get("current_sensitivity", 0.0))
        text = f"{value:.3f}"
        QApplication.clipboard().setText(text)
        self._showNotification("Copied", f"Sensitivity copied: {text}", 1)

    def _showNotification(self, title: str, text: str, msg_type: int = 1):
        try:
            app = self.window()
            if hasattr(app, "LayerRightMessageSidebar"):
                app.LayerRightMessageSidebar().send(
                    title=title,
                    text=text,
                    msg_type=msg_type,
                    fold_after=3000,
                )
        except Exception:
            pass

    @staticmethod
    def _formatDuration(seconds: int) -> str:
        hours, remainder = divmod(max(0, int(seconds)), 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
