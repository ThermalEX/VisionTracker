"""Vision Tracker - Custom Tracker Page"""

import glob
import json
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from siui.components import SiDenseHContainer, SiLabel, SiTitledWidgetGroup, SiOptionCardLinear
from siui.components.button import SiFlatButton, SiPushButtonRefactor
from siui.components.combobox.combobox import SiComboBox
from siui.components.combobox_ import SiCapsuleComboBox
from siui.components.container import SiTriSectionFlatCard
from siui.components.page import SiPage
from siui.components.slider.slider import SiSliderH
from siui.components.spinbox.slider_spinbox import SiSliderSpinBox, SiSliderDoubleSpinBox
from siui.components.widgets.button import SiSwitch
from siui.core import Si, SiColor, SiGlobal
from siui.gui import SiFont

from core.capture import get_available_windows
from utils.config_manager import ConfigManager


class CustomTrackerPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Custom Tracker")

        self._tracker_manager = None
        self._config_manager = ConfigManager()
        self._model_files = []

        # Locate app/data/ relative to this file (4 levels up to app/)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self._class_config_path = os.path.join(app_dir, "data", "class_config.json")
        self._system_models_dir = os.path.join(app_dir, "models", "system")
        self._user_models_dir = os.path.join(app_dir, "models", "user")

        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        self._createControlCard()
        self._createFovSection()
        self._createDisplaySection()
        self._createSnapSection()
        self._createPidSection()

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)

        self._loadDefaultConfig()

    def setTrackerManager(self, manager):
        self._tracker_manager = manager
        if manager and hasattr(manager, 'status_changed'):
            manager.status_changed.connect(self._onStatusChanged)

    # ── Control Card ───────────────────────────────────────────────

    def _createControlCard(self):
        control_card = SiTriSectionFlatCard(self)
        control_card.setTitle("Custom Tracker")

        # --- Row 1: Model selection ---
        model_row = SiDenseHContainer(self)
        model_row.setFixedHeight(40)
        model_row.setSpacing(8)
        model_row.setAlignment(Qt.AlignVCenter)

        model_label = SiLabel(self)
        model_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        model_label.setFont(SiFont.getFont(size=13))
        model_label.setTextColor(self.getColor(SiColor.TEXT_D))
        model_label.setText("Model")
        model_row.addWidget(model_label, side="left")
        model_row.addPlaceholder(4, side="left")

        self._scanModels()
        self.model_combo = SiCapsuleComboBox(self)
        self.model_combo.setFixedSize(260, 32)
        self.model_combo.setTitle("Model File")
        self.model_combo.setEditable(False)
        self.model_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.model_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        self._populateModelCombo()
        model_row.addWidget(self.model_combo, side="left")

        self.btn_refresh_models = SiFlatButton(self)
        self.btn_refresh_models.setFixedSize(28, 28)
        self.btn_refresh_models.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_arrow_sync_circle_filled"))
        self.btn_refresh_models.setToolTip("Refresh model list")
        self.btn_refresh_models.clicked.connect(self._refreshModels)
        model_row.addWidget(self.btn_refresh_models, side="left")

        control_card.body().addWidget(model_row)

        # --- Row 2: Target class + Window ---
        target_row = SiDenseHContainer(self)
        target_row.setFixedHeight(40)
        target_row.setSpacing(8)
        target_row.setAlignment(Qt.AlignVCenter)

        target_label = SiLabel(self)
        target_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        target_label.setFont(SiFont.getFont(size=13))
        target_label.setTextColor(self.getColor(SiColor.TEXT_D))
        target_label.setText("Target")
        target_row.addWidget(target_label, side="left")
        target_row.addPlaceholder(4, side="left")

        self.target_combo = SiComboBox(self)
        self.target_combo.resize(140, 32)
        self._loadClassConfig()
        target_row.addWidget(self.target_combo, side="left")
        target_row.addPlaceholder(20, side="left")

        window_label = SiLabel(self)
        window_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        window_label.setFont(SiFont.getFont(size=13))
        window_label.setTextColor(self.getColor(SiColor.TEXT_D))
        window_label.setText("Window")
        target_row.addWidget(window_label, side="left")
        target_row.addPlaceholder(4, side="left")

        self.window_combo = SiCapsuleComboBox(self)
        self.window_combo.setFixedSize(240, 32)
        self.window_combo.setTitle("Window")
        self.window_combo.setEditable(False)
        self.window_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.window_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        self._loadWindowList()
        target_row.addWidget(self.window_combo, side="left")

        self.btn_refresh_windows = SiFlatButton(self)
        self.btn_refresh_windows.setFixedSize(28, 28)
        self.btn_refresh_windows.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_arrow_sync_circle_filled"))
        self.btn_refresh_windows.setToolTip("Refresh window list")
        self.btn_refresh_windows.clicked.connect(self._loadWindowList)
        target_row.addWidget(self.btn_refresh_windows, side="left")

        control_card.body().addWidget(target_row)

        # --- Row 3: Start / Pause / Stop + status ---
        btn_row = SiDenseHContainer(self)
        btn_row.setFixedHeight(44)
        btn_row.setSpacing(8)
        btn_row.setAlignment(Qt.AlignVCenter)

        self.btn_start = SiPushButtonRefactor(self)
        self.btn_start.setText("Start")
        self.btn_start.setFixedSize(90, 36)
        self.btn_start.clicked.connect(self._startTracking)
        btn_row.addWidget(self.btn_start, side="left")

        self.btn_pause = SiPushButtonRefactor(self)
        self.btn_pause.setText("Pause")
        self.btn_pause.setFixedSize(90, 36)
        self.btn_pause.clicked.connect(self._pauseTracking)
        btn_row.addWidget(self.btn_pause, side="left")

        self.btn_stop = SiPushButtonRefactor(self)
        self.btn_stop.setText("Stop")
        self.btn_stop.setFixedSize(90, 36)
        self.btn_stop.clicked.connect(self._stopTracking)
        btn_row.addWidget(self.btn_stop, side="left")

        self.status_label = SiLabel(self)
        self.status_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.status_label.setFont(SiFont.getFont(size=12))
        self.status_label.setTextColor(self.getColor(SiColor.TEXT_D))
        self.status_label.setText("Idle")
        btn_row.addWidget(self.status_label, side="left")

        control_card.body().addWidget(btn_row)
        control_card.adjustSize()
        self.titled_group.addWidget(control_card)

    # ── FOV Settings ───────────────────────────────────────────────

    def _createFovSection(self):
        self.titled_group.addTitle("FOV Settings")

        fov_card = SiTriSectionFlatCard(self)
        fov_card.setTitle("Detection Area")

        fov_row = SiDenseHContainer(self)
        fov_row.setSpacing(24)
        fov_row.setFixedHeight(90)

        self.fov_width = SiSliderSpinBox(self)
        self.fov_width.setTitle("Width (px)")
        self.fov_width.setHint("Detection window width in pixels")
        self.fov_width.resize(200, 84)
        self.fov_width.setMinimum(50)
        self.fov_width.setMaximum(800)
        self.fov_width.setSingleStep(10)
        self.fov_width.setValue(200)
        fov_row.addWidget(self.fov_width, side="left")

        self.fov_height = SiSliderSpinBox(self)
        self.fov_height.setTitle("Height (px)")
        self.fov_height.setHint("Detection window height in pixels")
        self.fov_height.resize(200, 84)
        self.fov_height.setMinimum(50)
        self.fov_height.setMaximum(800)
        self.fov_height.setSingleStep(10)
        self.fov_height.setValue(200)
        fov_row.addWidget(self.fov_height, side="left")

        fov_card.body().addWidget(fov_row)
        fov_card.adjustSize()
        self.titled_group.addWidget(fov_card)

    # ── Display Settings ───────────────────────────────────────────

    def _createDisplaySection(self):
        self.titled_group.addTitle("Display Settings")

        self.overlay_card = SiOptionCardLinear(self)
        self.overlay_card.setTitle("Show Overlay", "Display overlay window with aim info")
        self.overlay_card.load(SiGlobal.siui.iconpack.get("ic_fluent_window_regular"))
        self.show_overlay = SiSwitch(self)
        self.show_overlay.setChecked(True)
        self.overlay_card.addWidget(self.show_overlay)
        self.titled_group.addWidget(self.overlay_card)

        self.opacity_card = SiOptionCardLinear(self)
        self.opacity_card.setTitle("Overlay Opacity", "Transparency of the overlay window")
        self.opacity_card.load(SiGlobal.siui.iconpack.get("ic_fluent_eye_regular"))
        self.overlay_opacity = SiSliderH(self)
        self.overlay_opacity.setFixedSize(180, 24)
        self.overlay_opacity.setMinimum(0)
        self.overlay_opacity.setMaximum(100)
        self.overlay_opacity.setSingleStep(1)
        self.overlay_opacity.setValue(100)
        self.opacity_card.addWidget(self.overlay_opacity)
        self.titled_group.addWidget(self.opacity_card)

        self.bbox_card = SiOptionCardLinear(self)
        self.bbox_card.setTitle("Show Detection Box", "Display bounding boxes around targets")
        self.bbox_card.load(SiGlobal.siui.iconpack.get("ic_fluent_checkbox_unchecked_regular"))
        self.show_bbox = SiSwitch(self)
        self.show_bbox.setChecked(True)
        self.bbox_card.addWidget(self.show_bbox)
        self.titled_group.addWidget(self.bbox_card)

    # ── Snap Settings ──────────────────────────────────────────────

    def _createSnapSection(self):
        self.titled_group.addTitle("Snap Settings (Instant Move)")

        snap_card = SiTriSectionFlatCard(self)
        snap_card.setTitle("Snap Parameters")

        snap_row = SiDenseHContainer(self)
        snap_row.setSpacing(24)
        snap_row.setFixedHeight(90)

        self.snap_threshold = SiSliderSpinBox(self)
        self.snap_threshold.setTitle("Threshold (px)")
        self.snap_threshold.setHint("Distance threshold for snap activation")
        self.snap_threshold.resize(180, 84)
        self.snap_threshold.setMinimum(5)
        self.snap_threshold.setMaximum(200)
        self.snap_threshold.setValue(40)
        snap_row.addWidget(self.snap_threshold, side="left")

        self.snap_sensitivity = SiSliderDoubleSpinBox(self)
        self.snap_sensitivity.setTitle("Sensitivity")
        self.snap_sensitivity.setHint("Mouse movement multiplier for snap")
        self.snap_sensitivity.resize(180, 84)
        self.snap_sensitivity.setMinimum(0.1)
        self.snap_sensitivity.setMaximum(5.0)
        self.snap_sensitivity.setSingleStep(0.1)
        self.snap_sensitivity.setDecimals(1)
        self.snap_sensitivity.setValue(2.2)
        snap_row.addWidget(self.snap_sensitivity, side="left")

        self.snap_cooldown = SiSliderDoubleSpinBox(self)
        self.snap_cooldown.setTitle("Cooldown (s)")
        self.snap_cooldown.setHint("Time between consecutive snaps")
        self.snap_cooldown.resize(180, 84)
        self.snap_cooldown.setMinimum(0.01)
        self.snap_cooldown.setMaximum(1.0)
        self.snap_cooldown.setSingleStep(0.05)
        self.snap_cooldown.setDecimals(2)
        self.snap_cooldown.setValue(0.2)
        snap_row.addWidget(self.snap_cooldown, side="left")

        self.snap_update_threshold = SiSliderSpinBox(self)
        self.snap_update_threshold.setTitle("Update Thr. (px)")
        self.snap_update_threshold.setHint("Minimum target movement to trigger update")
        self.snap_update_threshold.resize(180, 84)
        self.snap_update_threshold.setMinimum(1)
        self.snap_update_threshold.setMaximum(100)
        self.snap_update_threshold.setValue(20)
        snap_row.addWidget(self.snap_update_threshold, side="left")

        snap_card.body().addWidget(snap_row)
        snap_card.adjustSize()
        self.titled_group.addWidget(snap_card)

    # ── PID Settings ───────────────────────────────────────────────

    def _createPidSection(self):
        self.titled_group.addTitle("PID Settings (Smooth Move)")

        pid_card = SiTriSectionFlatCard(self)
        pid_card.setTitle("PID Parameters")

        pid_row1 = SiDenseHContainer(self)
        pid_row1.setSpacing(24)
        pid_row1.setFixedHeight(90)

        self.pid_kp = SiSliderDoubleSpinBox(self)
        self.pid_kp.setTitle("Kp")
        self.pid_kp.setHint("Proportional gain")
        self.pid_kp.resize(180, 84)
        self.pid_kp.setMinimum(0.01)
        self.pid_kp.setMaximum(2.0)
        self.pid_kp.setSingleStep(0.05)
        self.pid_kp.setDecimals(2)
        self.pid_kp.setValue(0.3)
        pid_row1.addWidget(self.pid_kp, side="left")

        self.pid_ki = SiSliderDoubleSpinBox(self)
        self.pid_ki.setTitle("Ki")
        self.pid_ki.setHint("Integral gain")
        self.pid_ki.resize(180, 84)
        self.pid_ki.setMinimum(0.0)
        self.pid_ki.setMaximum(1.0)
        self.pid_ki.setSingleStep(0.01)
        self.pid_ki.setDecimals(2)
        self.pid_ki.setValue(0.0)
        pid_row1.addWidget(self.pid_ki, side="left")

        self.pid_kd = SiSliderDoubleSpinBox(self)
        self.pid_kd.setTitle("Kd")
        self.pid_kd.setHint("Derivative gain")
        self.pid_kd.resize(180, 84)
        self.pid_kd.setMinimum(0.0)
        self.pid_kd.setMaximum(0.1)
        self.pid_kd.setSingleStep(0.001)
        self.pid_kd.setDecimals(3)
        self.pid_kd.setValue(0.001)
        pid_row1.addWidget(self.pid_kd, side="left")

        pid_card.body().addWidget(pid_row1)

        pid_row2 = SiDenseHContainer(self)
        pid_row2.setSpacing(24)
        pid_row2.setFixedHeight(90)

        self.deadzone = SiSliderSpinBox(self)
        self.deadzone.setTitle("Deadzone (px)")
        self.deadzone.setHint("Ignore movement smaller than this")
        self.deadzone.resize(180, 84)
        self.deadzone.setMinimum(0)
        self.deadzone.setMaximum(20)
        self.deadzone.setValue(0)
        pid_row2.addWidget(self.deadzone, side="left")

        self.pid_cooldown = SiSliderDoubleSpinBox(self)
        self.pid_cooldown.setTitle("Cooldown (s)")
        self.pid_cooldown.setHint("Time between PID updates")
        self.pid_cooldown.resize(180, 84)
        self.pid_cooldown.setMinimum(0.01)
        self.pid_cooldown.setMaximum(0.5)
        self.pid_cooldown.setSingleStep(0.01)
        self.pid_cooldown.setDecimals(2)
        self.pid_cooldown.setValue(0.05)
        pid_row2.addWidget(self.pid_cooldown, side="left")

        self.pid_error_threshold = SiSliderSpinBox(self)
        self.pid_error_threshold.setTitle("Error Thr. (px)")
        self.pid_error_threshold.setHint("Stop adjusting when error below this")
        self.pid_error_threshold.resize(180, 84)
        self.pid_error_threshold.setMinimum(1)
        self.pid_error_threshold.setMaximum(20)
        self.pid_error_threshold.setValue(3)
        pid_row2.addWidget(self.pid_error_threshold, side="left")

        pid_card.body().addWidget(pid_row2)
        pid_card.adjustSize()
        self.titled_group.addWidget(pid_card)

    # ── Data Loading ───────────────────────────────────────────────

    def _scanModels(self):
        """Scan system and user model directories, building a grouped list."""
        self._model_files = [{"label": "Select Model...", "value": "", "header": False}]

        exts = ("*.pt", "*.engine")
        system_models, user_models = [], []

        if os.path.exists(self._system_models_dir):
            for ext in exts:
                for f in sorted(glob.glob(os.path.join(self._system_models_dir, ext))):
                    system_models.append({"label": os.path.basename(f), "value": f, "header": False})

        os.makedirs(self._user_models_dir, exist_ok=True)
        for ext in exts:
            for f in sorted(glob.glob(os.path.join(self._user_models_dir, ext))):
                user_models.append({"label": os.path.basename(f), "value": f, "header": False})

        if system_models:
            self._model_files.append({"label": "System Models", "value": None, "header": True})
            self._model_files.extend(system_models)
        if user_models:
            self._model_files.append({"label": "User Models", "value": None, "header": True})
            self._model_files.extend(user_models)

    def _populateModelCombo(self, preserve_selection=None):
        """Fill model_combo from self._model_files, disabling header rows."""
        self.model_combo.clear()
        for item in self._model_files:
            self.model_combo.addItem(item["label"])
            if item["header"]:
                idx = self.model_combo.count() - 1
                self.model_combo.model().item(idx).setEnabled(False)
        if preserve_selection is not None:
            idx = self.model_combo.findText(preserve_selection)
            self.model_combo.setCurrentIndex(idx if idx >= 0 else 0)

    def _refreshModels(self):
        current = self.model_combo.currentText()
        self._scanModels()
        self._populateModelCombo(preserve_selection=current)

    def _loadClassConfig(self):
        menu = self.target_combo.menu()
        # Clear existing options by removing widgets from body and resetting list
        for opt in list(getattr(menu, 'options_', [])):
            menu.body().layout().removeWidget(opt)
            opt.deleteLater()
        if hasattr(menu, 'options_'):
            menu.options_.clear()

        try:
            if os.path.exists(self._class_config_path):
                with open(self._class_config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                names = data.get("class_names", [])
                if names:
                    for name in names:
                        menu.addOption(name, value=name)
                    menu.setIndex(0)
                    return
        except Exception:
            pass
        menu.addOption("All targets", value="all")
        menu.setIndex(0)

    def _loadWindowList(self):
        current = self.window_combo.currentText()
        self.window_combo.clear()
        self.window_combo.addItem("Fullscreen")
        windows = get_available_windows()
        self.window_combo.addItems(windows)
        idx = self.window_combo.findText(current)
        if idx >= 0:
            self.window_combo.setCurrentIndex(idx)
        else:
            self.window_combo.setCurrentIndex(0)

    def _loadDefaultConfig(self):
        """Load parameter defaults from current ConfigManager config."""
        try:
            config = self._config_manager.get_current_config()
            if not config:
                configs = self._config_manager.list_configs()
                if configs:
                    config = self._config_manager.load_config(configs[0])
            if config:
                self.fov_width.setValue(config.get("fov_width", 200))
                self.fov_height.setValue(config.get("fov_height", 200))
                self.show_overlay.setChecked(config.get("show_overlay", True))
                self.show_bbox.setChecked(config.get("show_bbox", True))
                self.overlay_opacity.setValue(config.get("overlay_opacity", 100))
                self.snap_threshold.setValue(config.get("snap_threshold", 40))
                self.snap_sensitivity.setValue(config.get("snap_sensitivity", 2.2))
                self.snap_cooldown.setValue(config.get("snap_cooldown", 0.2))
                self.snap_update_threshold.setValue(config.get("snap_update_threshold", 20))
                self.pid_kp.setValue(config.get("pid_kp", 0.3))
                self.pid_ki.setValue(config.get("pid_ki", 0.0))
                self.pid_kd.setValue(config.get("pid_kd", 0.001))
                self.deadzone.setValue(config.get("deadzone", 0))
                self.pid_cooldown.setValue(config.get("pid_cooldown", 0.05))
                self.pid_error_threshold.setValue(config.get("pid_error_threshold", 3))
        except Exception:
            pass

    # ── Tracking Control ───────────────────────────────────────────

    def _buildConfig(self) -> dict:
        model_idx = self.model_combo.currentIndex()
        if model_idx < len(self._model_files) and not self._model_files[model_idx]["header"]:
            model_path = self._model_files[model_idx]["value"] or ""
        else:
            model_path = ""

        target_idx = self.target_combo.menu().index()
        options = self.target_combo.menu().options_
        target_class = options[target_idx].value() if target_idx is not None and target_idx < len(options) else "all"

        return {
            "model_path": model_path,
            "operation_mode": "auto_aim",
            "aim_part": target_class,
            "fov_width": self.fov_width.value(),
            "fov_height": self.fov_height.value(),
            "show_overlay": self.show_overlay.isChecked(),
            "show_bbox": self.show_bbox.isChecked(),
            "overlay_opacity": self.overlay_opacity.value(),
            "auto_click": False,
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

    def _startTracking(self):
        if not self._tracker_manager:
            return
        config = self._buildConfig()
        window_title = None if self.window_combo.currentIndex() == 0 else self.window_combo.currentText()
        self._tracker_manager.start(config, window_title)
        self.status_label.setText("Running")

    def _pauseTracking(self):
        if not self._tracker_manager:
            return
        if self._tracker_manager.is_running():
            if self._tracker_manager.is_paused():
                self._tracker_manager.resume()
                self.status_label.setText("Running")
            else:
                self._tracker_manager.pause()
                self.status_label.setText("Paused")

    def _stopTracking(self):
        if not self._tracker_manager:
            return
        self._tracker_manager.stop()
        self.status_label.setText("Idle")

    def _onStatusChanged(self, status: str):
        self.status_label.setText(status)

    def refreshClassConfig(self):
        """Called externally when class config is updated."""
        self._loadClassConfig()
