"""Vision Tracker - Configuration Page"""

import os
import glob
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QRectF
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QLinearGradient
from PyQt5.QtWidgets import QWidget, QGraphicsOpacityEffect, QVBoxLayout, QLineEdit, QApplication

from siui.components import SiDenseHContainer, SiDenseVContainer, SiLabel, SiTitledWidgetGroup, SiOptionCardLinear
from siui.components.page import SiPage
from siui.components.widgets.button import SiSimpleButton
from siui.components.button import SiFlatButton, SiPushButtonRefactor, SiLongPressButtonRefactor
from siui.components.combobox.combobox import SiComboBox
from siui.components.combobox_ import SiCapsuleComboBox
from siui.components.editbox import SiSpinBox, SiDoubleSpinBox
from siui.components.spinbox.slider_spinbox import SiSliderSpinBox, SiSliderDoubleSpinBox
from siui.components.widgets.button import SiSwitch
from siui.components.container import SiTriSectionPanelCard
from siui.core import Si, SiColor, SiGlobal
from siui.gui import SiFont

from utils.config_manager import ConfigManager


class FlatLongPressButton(SiFlatButton):
    """Flat button with long press functionality and gradient animation."""
    longPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._is_pressing = False
        self._is_long_press = False

        # Timer for progress updates
        self.mouse_pressed_timer = QTimer(self)
        self.mouse_pressed_timer.setInterval(1000 // 60)  # 60 FPS
        self.mouse_pressed_timer.timeout.connect(self._onMousePressed)

        # Timer for backwards animation
        self.go_backwards_timer = QTimer(self)
        self.go_backwards_timer.setSingleShot(True)
        self.go_backwards_timer.setInterval(500)
        self.go_backwards_timer.timeout.connect(self._goBackwards)

    def _stepLength(self):
        """Calculate step length for progress increment."""
        return (1 - self._progress) / 16 + 0.001

    def _onMousePressed(self):
        """Update progress while mouse is pressed."""
        self._progress = min(self._progress + self._stepLength(), 1.0)
        self.update()

        if self._progress >= 1.0:
            self.mouse_pressed_timer.stop()
            self.go_backwards_timer.stop()
            self._is_long_press = True
            self.longPressed.emit()
            # Flash effect
            QTimer.singleShot(200, lambda: self._goBackwards(0))

    def _goBackwards(self, delay=0):
        """Reset progress with animation."""
        if delay > 0:
            QTimer.singleShot(delay, lambda: self._resetProgress())
        else:
            self._resetProgress()

    def _resetProgress(self):
        """Animate progress back to 0."""
        # Simple linear reset
        reset_timer = QTimer(self)
        reset_timer.setInterval(16)  # ~60 FPS

        def animate_reset():
            self._progress = max(0, self._progress - 0.1)
            self.update()
            if self._progress <= 0:
                reset_timer.stop()
                reset_timer.deleteLater()

        reset_timer.timeout.connect(animate_reset)
        reset_timer.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_pressing = True
            self._is_long_press = False
            self.mouse_pressed_timer.start()
            self.go_backwards_timer.stop()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_pressing = False
        self.mouse_pressed_timer.stop()

        if self._is_long_press:
            # Prevent normal click if it was a long press
            self._is_long_press = False
            event.accept()
            return
        else:
            if self._progress > 0 and self._progress < 1:
                self.go_backwards_timer.start()

        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        """Custom paint event to draw progress gradient."""
        if self._progress > 0:
            # Draw background with progress gradient first
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            # Draw progress background with gradient
            rect = self.rect().adjusted(1, 1, -1, -1)

            # Create gradient from left to right
            gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())

            # Red gradient for delete button background
            progress_color = QColor(180, 30, 30)  # Dark red
            base_color = QColor(45, 43, 50)  # Default button background

            gradient.setColorAt(max(0, self._progress - 0.0001), progress_color)
            gradient.setColorAt(self._progress, base_color)

            # Draw rounded rectangle with gradient as background
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)

            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 4, 4)
            painter.drawPath(path)

            # Draw border
            painter.setPen(QColor(100, 72, 96))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)

            painter.end()

        # Now draw the button content (icon, text) on top
        super().paintEvent(event)


class RoundedDialog(QWidget):
    """Base class for rounded dialogs with fade animation."""
    closed = pyqtSignal()

    def __init__(self, parent, width, height):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_ani = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_ani.setDuration(150)
        self._fade_ani.setEasingCurve(QEasingCurve.OutCubic)

    def showWithAnimation(self):
        self.show()
        self._fade_ani.setStartValue(0)
        self._fade_ani.setEndValue(1)
        self._fade_ani.start()

    def closeWithAnimation(self):
        self._fade_ani.setStartValue(1)
        self._fade_ani.setEndValue(0)
        self._fade_ani.finished.connect(self._onFadeOutFinished)
        self._fade_ani.start()

    def _onFadeOutFinished(self):
        self._fade_ani.finished.disconnect(self._onFadeOutFinished)
        self.closed.emit()
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 16, 16)
        painter.fillPath(path, QColor("#2D2B32"))


class AddConfigDialog(RoundedDialog):
    """Dialog to add a new configuration."""
    confirmed = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent, 400, 180)
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        self.title = SiLabel(self)
        self.title.setFont(SiFont.getFont(size=18, weight=QFont.Bold))
        self.title.setText("New Configuration")
        self.title.setStyleSheet("color: #E0E0E0")
        layout.addWidget(self.title)

        self.edit = QLineEdit(self)
        self.edit.setFixedHeight(36)
        self.edit.setPlaceholderText("Enter config name")
        self.edit.setStyleSheet("""
            QLineEdit {
                background-color: #201d23;
                border: 1px solid #3a3540;
                border-radius: 6px;
                color: #D1CBD4;
                padding: 0 12px;
                font-family: "Segoe UI", "Microsoft YaHei";
                font-size: 14px;
            }
            QLineEdit:focus { border: 1px solid #D087DF; }
        """)
        layout.addWidget(self.edit)

        btn_container = SiDenseHContainer(self)
        btn_container.setFixedHeight(32)

        self.btn_cancel = SiPushButtonRefactor(self)
        self.btn_cancel.setText("Cancel")
        self.btn_cancel.setFixedSize(80, 32)
        self.btn_cancel.clicked.connect(self.closeWithAnimation)

        self.btn_confirm = SiPushButtonRefactor(self)
        self.btn_confirm.setText("Create")
        self.btn_confirm.setFixedSize(80, 32)
        self.btn_confirm.clicked.connect(self._onConfirm)

        btn_container.addWidget(self.btn_confirm, side="right")
        btn_container.addWidget(self.btn_cancel, side="right")
        layout.addWidget(btn_container)

    def _onConfirm(self):
        text = self.edit.text().strip()
        if text:
            self.confirmed.emit(text)
            self.closeWithAnimation()


class ConfigPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Configuration")
        self._overlay = None
        self._config_manager = ConfigManager()
        self._model_files = []

        # Main group
        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        self._createTopBar()
        self._createSettingsUI()

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)

        # Load first config (Default)
        configs = self._config_manager.list_configs()
        if configs:
            default_idx = configs.index("Default") if "Default" in configs else 0
            self.config_selector.setCurrentIndex(default_idx)
            self._loadConfig(configs[default_idx])

    def _createTopBar(self):
        self.top_bar = SiDenseHContainer(self)
        self.top_bar.setFixedHeight(40)
        self.top_bar.setSpacing(4)

        # Use SiCapsuleComboBox like in home page
        self.config_selector = SiCapsuleComboBox(self)
        self.config_selector.setFixedSize(280, 36)  # Increased width to show longer names
        self.config_selector.setTitle("Configuration")
        self.config_selector.setEditable(False)
        # Remove underline indicator
        self.config_selector._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.config_selector._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        self._loadConfigList()
        self.config_selector.currentIndexChanged.connect(self._onConfigSelected)
        self.top_bar.addWidget(self.config_selector, side="left")

        # Refresh button
        self.btn_refresh = SiFlatButton(self)
        self.btn_refresh.setFixedSize(32, 32)
        self.btn_refresh.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_arrow_sync_circle_filled"))
        self.btn_refresh.setToolTip("Refresh config list")
        self.btn_refresh.clicked.connect(self._onRefreshConfigList)
        self.top_bar.addWidget(self.btn_refresh, side="left")

        # Delete button (long press for safety)
        self.btn_delete = FlatLongPressButton(self)
        self.btn_delete.setFixedSize(32, 32)
        self.btn_delete.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_delete_filled"))
        self.btn_delete.setToolTip("Delete config (long press)")
        self.btn_delete.longPressed.connect(self._onDeleteConfig)
        self.top_bar.addWidget(self.btn_delete, side="right")

        # Save button
        self.btn_save = SiFlatButton(self)
        self.btn_save.setFixedSize(32, 32)
        self.btn_save.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_save_filled"))
        self.btn_save.setToolTip("Save config")
        self.btn_save.clicked.connect(self._onSaveConfig)
        self.top_bar.addWidget(self.btn_save, side="right")

        # New button
        self.btn_add = SiFlatButton(self)
        self.btn_add.setFixedSize(32, 32)
        self.btn_add.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_document_add_filled"))
        self.btn_add.setToolTip("Create new config")
        self.btn_add.clicked.connect(self._showAddConfigDialog)
        self.top_bar.addWidget(self.btn_add, side="right")

        self.titled_group.addWidget(self.top_bar)

    def _scanModels(self):
        """Scan for model files in app/models/"""
        self._model_files = [{"label": "Select Model...", "value": ""}]
        # page_config.py is at app/ui/components/page_config/
        # so we need to go up 4 levels to get to app/
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        models_dir = os.path.join(app_dir, "models")

        if os.path.exists(models_dir):
            for f in glob.glob(os.path.join(models_dir, "*.pt")):
                name = os.path.basename(f)
                self._model_files.append({"label": name, "value": f})
            for f in glob.glob(os.path.join(models_dir, "*.engine")):
                name = os.path.basename(f)
                self._model_files.append({"label": name, "value": f})

    def _createSettingsUI(self):
        # === Basic Settings ===
        self.titled_group.addTitle("Basic Settings")

        # Model Card
        self._scanModels()
        self.model_card = SiOptionCardLinear(self)
        self.model_card.setTitle("Model", "Select detection model file (.pt / .engine)")
        self.model_card.load(SiGlobal.siui.iconpack.get("ic_fluent_brain_circuit_regular"))
        self.model_combo = SiComboBox(self)
        self.model_combo.resize(200, 32)
        for opt in self._model_files:
            self.model_combo.menu().addOption(opt["label"], value=opt["value"])
        self.model_card.addWidget(self.model_combo)
        self.titled_group.addWidget(self.model_card)

        # Mode Card
        self.mode_card = SiOptionCardLinear(self)
        self.mode_card.setTitle("Operation Mode", "Auto Trigger / Auto Aim / Auto Aim + Fire")
        self.mode_card.load(SiGlobal.siui.iconpack.get("ic_fluent_target_regular"))
        self.mode_combo = SiComboBox(self)
        self.mode_combo.resize(180, 32)
        self.mode_combo.menu().addOption("Auto Trigger", value="auto_trigger")
        self.mode_combo.menu().addOption("Auto Aim", value="auto_aim")
        self.mode_combo.menu().addOption("Auto Aim + Fire", value="auto_aim_fire")
        self.mode_combo.menu().setIndex(2)  # Default to "Auto Aim + Fire"
        self.mode_combo.value_label.setText("Auto Aim + Fire")  # Ensure label is updated
        self.mode_card.addWidget(self.mode_combo)
        self.titled_group.addWidget(self.mode_card)

        # === FOV Settings ===
        self.titled_group.addTitle("FOV Settings")

        fov_card = SiTriSectionPanelCard(self)
        fov_card.setTitle("Detection Area")

        fov_container = SiDenseHContainer(self)
        fov_container.setSpacing(24)
        fov_container.setFixedHeight(90)

        self.fov_width = SiSliderSpinBox(self)
        self.fov_width.setTitle("Width (px)")
        self.fov_width.setHint("Detection window width in pixels")
        self.fov_width.resize(200, 84)
        self.fov_width.setMinimum(50)
        self.fov_width.setMaximum(800)
        self.fov_width.setSingleStep(10)

        self.fov_height = SiSliderSpinBox(self)
        self.fov_height.setTitle("Height (px)")
        self.fov_height.setHint("Detection window height in pixels")
        self.fov_height.resize(200, 84)
        self.fov_height.setMinimum(50)
        self.fov_height.setMaximum(800)
        self.fov_height.setSingleStep(10)

        fov_container.addWidget(self.fov_width, side="left")
        fov_container.addWidget(self.fov_height, side="left")
        fov_card.body().addWidget(fov_container)
        fov_card.adjustSize()
        self.titled_group.addWidget(fov_card)

        # === Display Settings ===
        self.titled_group.addTitle("Display Settings")

        self.overlay_card = SiOptionCardLinear(self)
        self.overlay_card.setTitle("Show Overlay", "Display overlay window with aim info")
        self.overlay_card.load(SiGlobal.siui.iconpack.get("ic_fluent_window_regular"))
        self.show_overlay = SiSwitch(self)
        self.overlay_card.addWidget(self.show_overlay)
        self.titled_group.addWidget(self.overlay_card)

        self.bbox_card = SiOptionCardLinear(self)
        self.bbox_card.setTitle("Show Detection Box", "Display bounding boxes around enemies")
        self.bbox_card.load(SiGlobal.siui.iconpack.get("ic_fluent_checkbox_unchecked_regular"))
        self.show_bbox = SiSwitch(self)
        self.bbox_card.addWidget(self.show_bbox)
        self.titled_group.addWidget(self.bbox_card)

        # === Fire Settings ===
        self.titled_group.addTitle("Fire Settings")

        fire_card = SiTriSectionPanelCard(self)
        fire_card.setTitle("Fire Parameters")

        fire_container = SiDenseHContainer(self)
        fire_container.setSpacing(24)
        fire_container.setFixedHeight(90)

        self.click_interval = SiSliderDoubleSpinBox(self)
        self.click_interval.setTitle("Interval (s)")
        self.click_interval.setHint("Time between auto-fire clicks")
        self.click_interval.resize(180, 84)
        self.click_interval.setMinimum(0.01)
        self.click_interval.setMaximum(2.0)
        self.click_interval.setSingleStep(0.05)
        self.click_interval.setDecimals(2)

        self.click_radius_ratio = SiSliderDoubleSpinBox(self)
        self.click_radius_ratio.setTitle("Range Ratio")
        self.click_radius_ratio.setHint("Click range ratio relative to target size")
        self.click_radius_ratio.resize(180, 84)
        self.click_radius_ratio.setMinimum(0.5)
        self.click_radius_ratio.setMaximum(3.0)
        self.click_radius_ratio.setSingleStep(0.1)
        self.click_radius_ratio.setDecimals(1)

        self.click_radius_min = SiSliderSpinBox(self)
        self.click_radius_min.setTitle("Min Range")
        self.click_radius_min.setHint("Minimum click range in pixels")
        self.click_radius_min.resize(180, 84)
        self.click_radius_min.setMinimum(1)
        self.click_radius_min.setMaximum(100)

        self.click_radius_max = SiSliderSpinBox(self)
        self.click_radius_max.setTitle("Max Range")
        self.click_radius_max.setHint("Maximum click range in pixels")
        self.click_radius_max.resize(180, 84)
        self.click_radius_max.setMinimum(10)
        self.click_radius_max.setMaximum(200)

        fire_container.addWidget(self.click_interval, side="left")
        fire_container.addWidget(self.click_radius_ratio, side="left")
        fire_container.addWidget(self.click_radius_min, side="left")
        fire_container.addWidget(self.click_radius_max, side="left")
        fire_card.body().addWidget(fire_container)

        # Target Priority
        priority_container = SiDenseHContainer(self)
        priority_container.setFixedHeight(40)
        priority_label = SiLabel(self)
        priority_label.setText("Target Priority")
        priority_label.setFont(SiFont.getFont(size=14))
        priority_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        priority_label.setHint("How to select target when multiple detected")
        self.target_priority = SiComboBox(self)
        self.target_priority.resize(180, 32)
        self.target_priority.menu().addOption("Nearest", value="nearest")
        self.target_priority.menu().addOption("Largest", value="largest")
        self.target_priority.menu().addOption("Highest Confidence", value="highest_conf")
        self.target_priority.menu().setIndex(0)  # Default to "Nearest"
        priority_container.addWidget(priority_label, side="left")
        priority_container.addPlaceholder(16, side="left")
        priority_container.addWidget(self.target_priority, side="left")
        fire_card.body().addWidget(priority_container)

        fire_card.adjustSize()
        self.titled_group.addWidget(fire_card)

        # === Snap Settings ===
        self.titled_group.addTitle("Snap Settings (Instant Move)")

        snap_card = SiTriSectionPanelCard(self)
        snap_card.setTitle("Snap Parameters")

        snap_container = SiDenseHContainer(self)
        snap_container.setSpacing(24)
        snap_container.setFixedHeight(90)

        self.snap_threshold = SiSliderSpinBox(self)
        self.snap_threshold.setTitle("Threshold")
        self.snap_threshold.setHint("Distance threshold for snap activation (px)")
        self.snap_threshold.resize(180, 84)
        self.snap_threshold.setMinimum(5)
        self.snap_threshold.setMaximum(200)

        self.snap_sensitivity = SiSliderDoubleSpinBox(self)
        self.snap_sensitivity.setTitle("Sensitivity")
        self.snap_sensitivity.setHint("Mouse movement multiplier for snap")
        self.snap_sensitivity.resize(180, 84)
        self.snap_sensitivity.setMinimum(0.1)
        self.snap_sensitivity.setMaximum(5.0)
        self.snap_sensitivity.setSingleStep(0.1)
        self.snap_sensitivity.setDecimals(1)

        self.snap_cooldown = SiSliderDoubleSpinBox(self)
        self.snap_cooldown.setTitle("Cooldown (s)")
        self.snap_cooldown.setHint("Time between consecutive snaps")
        self.snap_cooldown.resize(180, 84)
        self.snap_cooldown.setMinimum(0.01)
        self.snap_cooldown.setMaximum(1.0)
        self.snap_cooldown.setSingleStep(0.05)
        self.snap_cooldown.setDecimals(2)

        self.snap_update_threshold = SiSliderSpinBox(self)
        self.snap_update_threshold.setTitle("Update Thr.")
        self.snap_update_threshold.setHint("Minimum target movement to trigger update (px)")
        self.snap_update_threshold.resize(180, 84)
        self.snap_update_threshold.setMinimum(1)
        self.snap_update_threshold.setMaximum(100)

        snap_container.addWidget(self.snap_threshold, side="left")
        snap_container.addWidget(self.snap_sensitivity, side="left")
        snap_container.addWidget(self.snap_cooldown, side="left")
        snap_container.addWidget(self.snap_update_threshold, side="left")
        snap_card.body().addWidget(snap_container)
        snap_card.adjustSize()
        self.titled_group.addWidget(snap_card)

        # === PID Settings ===
        self.titled_group.addTitle("PID Settings (Smooth Move)")

        pid_card = SiTriSectionPanelCard(self)
        pid_card.setTitle("PID Parameters")

        # First row: Kp, Ki, Kd
        pid_row1 = SiDenseHContainer(self)
        pid_row1.setSpacing(24)
        pid_row1.setFixedHeight(90)

        self.pid_kp = SiSliderDoubleSpinBox(self)
        self.pid_kp.setTitle("Kp")
        self.pid_kp.setHint("Proportional gain - main control strength")
        self.pid_kp.resize(180, 84)
        self.pid_kp.setMinimum(0.01)
        self.pid_kp.setMaximum(2.0)
        self.pid_kp.setSingleStep(0.05)
        self.pid_kp.setDecimals(2)

        self.pid_ki = SiSliderDoubleSpinBox(self)
        self.pid_ki.setTitle("Ki")
        self.pid_ki.setHint("Integral gain - accumulated error correction")
        self.pid_ki.resize(180, 84)
        self.pid_ki.setMinimum(0.0)
        self.pid_ki.setMaximum(1.0)
        self.pid_ki.setSingleStep(0.01)
        self.pid_ki.setDecimals(2)

        self.pid_kd = SiSliderDoubleSpinBox(self)
        self.pid_kd.setTitle("Kd")
        self.pid_kd.setHint("Derivative gain - dampening/smoothing")
        self.pid_kd.resize(180, 84)
        self.pid_kd.setMinimum(0.0)
        self.pid_kd.setMaximum(0.1)
        self.pid_kd.setSingleStep(0.001)
        self.pid_kd.setDecimals(3)

        pid_row1.addWidget(self.pid_kp, side="left")
        pid_row1.addWidget(self.pid_ki, side="left")
        pid_row1.addWidget(self.pid_kd, side="left")
        pid_card.body().addWidget(pid_row1)

        # Second row: Deadzone, Cooldown, Error Threshold
        pid_row2 = SiDenseHContainer(self)
        pid_row2.setSpacing(24)
        pid_row2.setFixedHeight(90)

        self.deadzone = SiSliderSpinBox(self)
        self.deadzone.setTitle("Deadzone")
        self.deadzone.setHint("Ignore movement smaller than this (px)")
        self.deadzone.resize(180, 84)
        self.deadzone.setMinimum(0)
        self.deadzone.setMaximum(20)

        self.pid_cooldown = SiSliderDoubleSpinBox(self)
        self.pid_cooldown.setTitle("Cooldown")
        self.pid_cooldown.setHint("Time between PID updates (s)")
        self.pid_cooldown.resize(180, 84)
        self.pid_cooldown.setMinimum(0.01)
        self.pid_cooldown.setMaximum(0.5)
        self.pid_cooldown.setSingleStep(0.01)
        self.pid_cooldown.setDecimals(2)

        self.pid_error_threshold = SiSliderSpinBox(self)
        self.pid_error_threshold.setTitle("Error Thr.")
        self.pid_error_threshold.setHint("Stop adjusting when error below this (px)")
        self.pid_error_threshold.resize(180, 84)
        self.pid_error_threshold.setMinimum(1)
        self.pid_error_threshold.setMaximum(20)

        pid_row2.addWidget(self.deadzone, side="left")
        pid_row2.addWidget(self.pid_cooldown, side="left")
        pid_row2.addWidget(self.pid_error_threshold, side="left")
        pid_card.body().addWidget(pid_row2)

        pid_card.adjustSize()
        self.titled_group.addWidget(pid_card)

    def _loadConfigList(self):
        """Load config list into the selector."""
        configs = self._config_manager.list_configs()
        self.config_selector.clear()
        self.config_selector.addItems(configs)

    def _loadConfig(self, name: str):
        config = self._config_manager.load_config(name)
        if config:
            # Model
            model_path = config.get("model_path", "")
            for i, opt in enumerate(self._model_files):
                if opt["value"] == model_path:
                    self.model_combo.menu().setIndex(i)
                    break

            # Mode
            mode = config.get("operation_mode", "auto_aim_fire")
            mode_map = {"auto_trigger": 0, "auto_aim": 1, "auto_aim_fire": 2}
            self.mode_combo.menu().setIndex(mode_map.get(mode, 2))

            # FOV
            self.fov_width.setValue(config.get("fov_width", 200))
            self.fov_height.setValue(config.get("fov_height", 200))

            # Display
            self.show_overlay.setChecked(config.get("show_overlay", True))
            self.show_bbox.setChecked(config.get("show_bbox", True))

            # Fire
            self.click_interval.setValue(config.get("click_interval", 0.2))
            self.click_radius_ratio.setValue(config.get("click_radius_ratio", 1.1))
            self.click_radius_min.setValue(config.get("click_radius_min", 5))
            self.click_radius_max.setValue(config.get("click_radius_max", 50))
            priority = config.get("target_priority", "nearest")
            priority_map = {"nearest": 0, "largest": 1, "highest_conf": 2}
            self.target_priority.menu().setIndex(priority_map.get(priority, 0))

            # Snap
            self.snap_threshold.setValue(config.get("snap_threshold", 40))
            self.snap_sensitivity.setValue(config.get("snap_sensitivity", 2.2))
            self.snap_cooldown.setValue(config.get("snap_cooldown", 0.2))
            self.snap_update_threshold.setValue(config.get("snap_update_threshold", 20))

            # PID
            self.pid_kp.setValue(config.get("pid_kp", 0.3))
            self.pid_ki.setValue(config.get("pid_ki", 0.0))
            self.pid_kd.setValue(config.get("pid_kd", 0.001))
            self.deadzone.setValue(config.get("deadzone", 0))
            self.pid_cooldown.setValue(config.get("pid_cooldown", 0.05))
            self.pid_error_threshold.setValue(config.get("pid_error_threshold", 3))

    def _getCurrentConfig(self) -> dict:
        # Model
        model_idx = self.model_combo.menu().index()
        model_path = self._model_files[model_idx]["value"] if model_idx is not None and model_idx < len(self._model_files) else ""

        # Mode
        mode_values = ["auto_trigger", "auto_aim", "auto_aim_fire"]
        mode_idx = self.mode_combo.menu().index()
        mode = mode_values[mode_idx] if mode_idx is not None else "auto_aim"

        # Priority
        priority_values = ["nearest", "largest", "highest_conf"]
        priority_idx = self.target_priority.menu().index()
        priority = priority_values[priority_idx] if priority_idx is not None else "nearest"

        return {
            "model_path": model_path,
            "operation_mode": mode,
            "fov_width": self.fov_width.value(),
            "fov_height": self.fov_height.value(),
            "show_overlay": self.show_overlay.isChecked(),
            "show_bbox": self.show_bbox.isChecked(),
            "auto_click": True,
            "click_interval": self.click_interval.value(),
            "click_radius_ratio": self.click_radius_ratio.value(),
            "click_radius_min": self.click_radius_min.value(),
            "click_radius_max": self.click_radius_max.value(),
            "target_priority": priority,
            "snap_threshold": self.snap_threshold.value(),
            "snap_sensitivity": self.snap_sensitivity.value(),
            "snap_cooldown": self.snap_cooldown.value(),
            "snap_update_threshold": self.snap_update_threshold.value(),
            "pid_kp": self.pid_kp.value(),
            "pid_ki": self.pid_ki.value(),
            "pid_kd": self.pid_kd.value(),
            "deadzone": self.deadzone.value(),
            "pid_cooldown": self.pid_cooldown.value(),
            "pid_error_threshold": self.pid_error_threshold.value(),
        }

    def _onConfigSelected(self, index: int):
        configs = self._config_manager.list_configs()
        if 0 <= index < len(configs):
            self._loadConfig(configs[index])

    def _onSaveConfig(self):
        name = self._config_manager.get_current_config_name()
        if name:
            config = self._getCurrentConfig()
            if self._config_manager.save_config(name, config):
                self._showNotification("Saved", f"'{name}' saved.", 1)
            else:
                self._showNotification("Failed", "Could not save.", 3)

    def _onDeleteConfig(self):
        name = self._config_manager.get_current_config_name()
        if name:
            # Protect Default config from deletion
            if name == "Default":
                self._showNotification("Protected", "Cannot delete Default config.", 2)
                return
            if self._config_manager.delete_config(name):
                self._showNotification("Deleted", f"'{name}' deleted.", 1)
                self._loadConfigList()
                configs = self._config_manager.list_configs()
                if configs:
                    self.config_selector.setCurrentIndex(0)
                    self._loadConfig(configs[0])
                # Sync with home page
                self._syncHomePageConfig()
            else:
                self._showNotification("Failed", "Cannot delete last config.", 3)

    def _onRefreshConfigList(self):
        """Refresh the config list from disk."""
        current_name = self._config_manager.get_current_config_name()
        self._loadConfigList()
        configs = self._config_manager.list_configs()
        if current_name in configs:
            self.config_selector.setCurrentIndex(configs.index(current_name))
        elif configs:
            self.config_selector.setCurrentIndex(0)
            self._loadConfig(configs[0])
        self._showNotification("Refreshed", "Config list refreshed.", 1)
        # Sync with home page
        self._syncHomePageConfig()

    def _showNotification(self, title: str, text: str, msg_type: int = 1):
        try:
            app = self.window()
            if hasattr(app, 'LayerRightMessageSidebar'):
                app.LayerRightMessageSidebar().send(title=title, text=text, msg_type=msg_type, fold_after=3000)
        except Exception:
            pass

    def _showAddConfigDialog(self):
        self._showOverlay()
        self.add_config_dialog = AddConfigDialog(self.window())
        geo = self.window().geometry()
        self.add_config_dialog.move(
            geo.width() // 2 - self.add_config_dialog.width() // 2,
            geo.height() // 2 - self.add_config_dialog.height() // 2
        )
        self.add_config_dialog.confirmed.connect(self._onConfigAdded)
        self.add_config_dialog.closed.connect(self._hideOverlay)
        self.add_config_dialog.showWithAnimation()

    def _onConfigAdded(self, name: str):
        if self._config_manager.create_config(name):
            self._loadConfigList()
            configs = self._config_manager.list_configs()
            if name in configs:
                self.config_selector.setCurrentIndex(configs.index(name))
                self._loadConfig(name)
            self._showNotification("Created", f"'{name}' created.", 1)
            # Sync with home page
            self._syncHomePageConfig()
        else:
            self._showNotification("Failed", "Name exists.", 3)

    def _showOverlay(self):
        main_window = self.window()
        if not self._overlay:
            self._overlay = SiLabel(main_window)
            self._overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);")
            self._overlay_effect = QGraphicsOpacityEffect(self._overlay)
            self._overlay.setGraphicsEffect(self._overlay_effect)
            self._overlay_ani = QPropertyAnimation(self._overlay_effect, b"opacity")
            self._overlay_ani.setDuration(150)
            self._overlay_ani.setEasingCurve(QEasingCurve.OutCubic)
        self._overlay.resize(main_window.size())
        self._overlay.raise_()
        self._overlay.show()
        self._overlay_effect.setOpacity(0)
        self._overlay_ani.setStartValue(0)
        self._overlay_ani.setEndValue(1)
        self._overlay_ani.start()

    def _hideOverlay(self):
        if self._overlay and hasattr(self, '_overlay_ani'):
            self._overlay_ani.setStartValue(1)
            self._overlay_ani.setEndValue(0)
            self._overlay_ani.finished.connect(self._onOverlayFadeOut)
            self._overlay_ani.start()

    def _onOverlayFadeOut(self):
        if hasattr(self, '_overlay_ani'):
            try:
                self._overlay_ani.finished.disconnect(self._onOverlayFadeOut)
            except Exception:
                pass
        if self._overlay:
            self._overlay.hide()

    def _syncHomePageConfig(self):
        """Sync config list with home page."""
        try:
            app = self.window()
            if hasattr(app, 'home_page'):
                app.home_page.refresh_config_list()
        except Exception:
            pass
