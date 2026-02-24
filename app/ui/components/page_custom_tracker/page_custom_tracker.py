"""Vision Tracker - Custom Tracker Page"""

import glob
import os

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from siui.components import SiDenseHContainer, SiLabel, SiTitledWidgetGroup, SiOptionCardLinear
from siui.components.button import SiFlatButton, SiCapsuleButton
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

        # Locate app/ relative to this file (4 levels up)
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self._system_models_dir = os.path.join(app_dir, "models", "system")
        self._user_models_dir = os.path.join(app_dir, "models", "user")

        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        self._createControlCard()
        self._createFovSection()
        self._createDisplaySection()
        self._createCrosshairSection()
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
        self.model_combo.currentIndexChanged.connect(self._onModelSelected)
        model_row.addWidget(self.model_combo, side="left")

        self.btn_refresh_models = SiFlatButton(self)
        self.btn_refresh_models.setFixedSize(28, 28)
        self.btn_refresh_models.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_arrow_sync_circle_filled"))
        self.btn_refresh_models.setToolTip("Refresh model list")
        self.btn_refresh_models.clicked.connect(self._refreshModels)
        model_row.addWidget(self.btn_refresh_models, side="left")

        control_card.body().addWidget(model_row)

        # --- Row 2: Operation Mode ---
        mode_row = SiDenseHContainer(self)
        mode_row.setFixedHeight(40)
        mode_row.setSpacing(8)
        mode_row.setAlignment(Qt.AlignVCenter)

        mode_label = SiLabel(self)
        mode_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        mode_label.setFont(SiFont.getFont(size=13))
        mode_label.setTextColor(self.getColor(SiColor.TEXT_D))
        mode_label.setText("Mode")
        mode_row.addWidget(mode_label, side="left")
        mode_row.addPlaceholder(4, side="left")

        self._mode_values = ["auto_trigger", "auto_aim", "auto_aim_fire"]
        self.mode_combo = SiCapsuleComboBox(self)
        self.mode_combo.setFixedSize(240, 32)
        self.mode_combo.setTitle("Mode")
        self.mode_combo.setEditable(False)
        self.mode_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.mode_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        self.mode_combo.addItem("Auto Trigger")
        self.mode_combo.addItem("Auto Aim")
        self.mode_combo.addItem("Auto Aim + Fire")
        self.mode_combo.setCurrentIndex(1)  # Default: Auto Aim
        mode_row.addWidget(self.mode_combo, side="left")

        control_card.body().addWidget(mode_row)

        # --- Row 3: Target class + Window ---
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

        self._target_class_values = []  # parallel list of class IDs matching combo items
        self.target_combo = SiCapsuleComboBox(self)
        self.target_combo.setFixedSize(240, 32)
        self.target_combo.setTitle("Target")
        self.target_combo.setEditable(False)
        self.target_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.target_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        self._updateTargetCombo({})  # Start with only "All Classes"
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

        # --- Row 3: Start / Pause / Stop + Save ---
        btn_row = SiDenseHContainer(self)
        btn_row.setFixedHeight(48)
        btn_row.setSpacing(8)
        btn_row.setAlignment(Qt.AlignVCenter)

        self.btn_start = SiCapsuleButton(self)
        self.btn_start.setFixedSize(120, 40)
        self.btn_start.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_play_filled"))
        self.btn_start.setValue("Start")
        self.btn_start.setThemeColor(SiCapsuleButton.Theme.Green)
        self.btn_start.setCheckable(True)
        self.btn_start.clicked.connect(self._startTracking)
        btn_row.addWidget(self.btn_start, side="left")

        self.btn_pause = SiCapsuleButton(self)
        self.btn_pause.setFixedSize(120, 40)
        self.btn_pause.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_pause_filled"))
        self.btn_pause.setValue("Pause")
        self.btn_pause.setThemeColor(SiCapsuleButton.Theme.Yellow)
        self.btn_pause.setCheckable(True)
        self.btn_pause.clicked.connect(self._pauseTracking)
        btn_row.addWidget(self.btn_pause, side="left")

        self.btn_stop = SiCapsuleButton(self)
        self.btn_stop.setFixedSize(120, 40)
        self.btn_stop.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_stop_filled"))
        self.btn_stop.setValue("Stop")
        self.btn_stop.setThemeColor(SiCapsuleButton.Theme.Red)
        self.btn_stop.setCheckable(True)
        self.btn_stop.setChecked(True)
        self.btn_stop.clicked.connect(self._stopTracking)
        btn_row.addWidget(self.btn_stop, side="left")

        self.btn_save = SiFlatButton(self)
        self.btn_save.setFixedSize(28, 28)
        self.btn_save.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_save_filled"))
        self.btn_save.setToolTip("Save settings")
        self.btn_save.clicked.connect(self._saveConfig)
        btn_row.addWidget(self.btn_save, side="left")

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

        self.aim_point_y = SiSliderSpinBox(self)
        self.aim_point_y.setTitle("Aim Height (%)")
        self.aim_point_y.setHint("Vertical aim point within bbox: 0=top, 50=center, 100=bottom")
        self.aim_point_y.resize(200, 84)
        self.aim_point_y.setMinimum(0)
        self.aim_point_y.setMaximum(100)
        self.aim_point_y.setSingleStep(5)
        self.aim_point_y.setValue(50)
        fov_row.addWidget(self.aim_point_y, side="left")

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

    # ── Crosshair Settings ─────────────────────────────────────────

    def _createCrosshairSection(self):
        self.titled_group.addTitle("Crosshair Settings")

        self.crosshair_show_card = SiOptionCardLinear(self)
        self.crosshair_show_card.setTitle("Show Crosshair", "Display a crosshair on the overlay")
        self.crosshair_show_card.load(SiGlobal.siui.iconpack.get("ic_fluent_target_regular"))
        self.crosshair_show = SiSwitch(self)
        self.crosshair_show.setChecked(True)
        self.crosshair_show_card.addWidget(self.crosshair_show)
        self.titled_group.addWidget(self.crosshair_show_card)

        self.crosshair_dot_card = SiOptionCardLinear(self)
        self.crosshair_dot_card.setTitle("Center Dot", "Show a dot at the center of the crosshair")
        self.crosshair_dot_card.load(SiGlobal.siui.iconpack.get("ic_fluent_circle_small_filled"))
        self.crosshair_center_dot = SiSwitch(self)
        self.crosshair_center_dot.setChecked(True)
        self.crosshair_dot_card.addWidget(self.crosshair_center_dot)
        self.titled_group.addWidget(self.crosshair_dot_card)

        self.crosshair_color_card = SiOptionCardLinear(self)
        self.crosshair_color_card.setTitle("Crosshair Color", "Color of the crosshair lines")
        self.crosshair_color_card.load(SiGlobal.siui.iconpack.get("ic_fluent_color_regular"))
        self.crosshair_color = SiCapsuleComboBox(self)
        self.crosshair_color.setFixedSize(160, 32)
        self.crosshair_color.setTitle("Color")
        self.crosshair_color.setEditable(False)
        self.crosshair_color._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.crosshair_color._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        for color_name in ["green", "red", "yellow", "cyan", "white", "magenta"]:
            self.crosshair_color.addItem(color_name)
        self.crosshair_color.setCurrentIndex(0)
        self.crosshair_color_card.addWidget(self.crosshair_color)
        self.titled_group.addWidget(self.crosshair_color_card)

        ch_card = SiTriSectionFlatCard(self)
        ch_card.setTitle("Crosshair Parameters")

        ch_row = SiDenseHContainer(self)
        ch_row.setSpacing(24)
        ch_row.setFixedHeight(90)

        self.crosshair_length = SiSliderSpinBox(self)
        self.crosshair_length.setTitle("Length (px)")
        self.crosshair_length.setHint("Length of each crosshair line")
        self.crosshair_length.resize(180, 84)
        self.crosshair_length.setMinimum(0)
        self.crosshair_length.setMaximum(50)
        self.crosshair_length.setSingleStep(1)
        self.crosshair_length.setValue(10)
        ch_row.addWidget(self.crosshair_length, side="left")

        self.crosshair_thickness = SiSliderSpinBox(self)
        self.crosshair_thickness.setTitle("Thickness (px)")
        self.crosshair_thickness.setHint("Thickness of crosshair lines")
        self.crosshair_thickness.resize(180, 84)
        self.crosshair_thickness.setMinimum(1)
        self.crosshair_thickness.setMaximum(10)
        self.crosshair_thickness.setSingleStep(1)
        self.crosshair_thickness.setValue(2)
        ch_row.addWidget(self.crosshair_thickness, side="left")

        self.crosshair_gap = SiSliderSpinBox(self)
        self.crosshair_gap.setTitle("Gap (px)")
        self.crosshair_gap.setHint("Gap from center point")
        self.crosshair_gap.resize(180, 84)
        self.crosshair_gap.setMinimum(0)
        self.crosshair_gap.setMaximum(20)
        self.crosshair_gap.setSingleStep(1)
        self.crosshair_gap.setValue(4)
        ch_row.addWidget(self.crosshair_gap, side="left")

        self.crosshair_dot_size = SiSliderSpinBox(self)
        self.crosshair_dot_size.setTitle("Dot Size (px)")
        self.crosshair_dot_size.setHint("Radius of center dot")
        self.crosshair_dot_size.resize(180, 84)
        self.crosshair_dot_size.setMinimum(1)
        self.crosshair_dot_size.setMaximum(10)
        self.crosshair_dot_size.setSingleStep(1)
        self.crosshair_dot_size.setValue(2)
        ch_row.addWidget(self.crosshair_dot_size, side="left")

        ch_card.body().addWidget(ch_row)
        ch_card.adjustSize()
        self.titled_group.addWidget(ch_card)

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

    def _onModelSelected(self, idx):
        """Called when model selection changes; reload class names into target combo."""
        if idx < 0 or idx >= len(self._model_files):
            self._updateTargetCombo({})
            return
        item = self._model_files[idx]
        if item.get('header') or not item.get('value'):
            self._updateTargetCombo({})
            return
        names = self._readModelClassNames(item['value'])
        self._updateTargetCombo(names)

    def _readModelClassNames(self, model_path: str) -> dict:
        """Read class names dict {id: name} from a YOLO .pt model file."""
        if not model_path or not os.path.exists(model_path):
            return {}
        if not model_path.endswith('.pt'):
            return {}
        try:
            import torch
            ckpt = torch.load(model_path, map_location='cpu', weights_only=False)
            model_obj = ckpt.get('model') or ckpt.get('ema')
            if model_obj is not None and hasattr(model_obj, 'names'):
                return dict(model_obj.names)
        except Exception:
            pass
        return {}

    def _updateTargetCombo(self, names: dict):
        """Repopulate target combo: 'All Classes' + one item per class ID."""
        self.target_combo.clear()
        self._target_class_values = [None]  # index 0 → All Classes
        self.target_combo.addItem("All Classes")
        for class_id in sorted(names.keys()):
            self.target_combo.addItem(f"{class_id}: {names[class_id]}")
            self._target_class_values.append(class_id)
        self.target_combo.setCurrentIndex(0)

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
                mode = config.get("operation_mode", "auto_aim")
                mode_idx = self._mode_values.index(mode) if mode in self._mode_values else 1
                self.mode_combo.setCurrentIndex(mode_idx)
                self.fov_width.setValue(config.get("fov_width", 200))
                self.fov_height.setValue(config.get("fov_height", 200))
                self.aim_point_y.setValue(config.get("aim_point_y", 50))
                self.show_overlay.setChecked(config.get("show_overlay", True))
                self.show_bbox.setChecked(config.get("show_bbox", True))
                self.overlay_opacity.setValue(config.get("overlay_opacity", 100))
                self.crosshair_show.setChecked(config.get("crosshair_show", True))
                self.crosshair_center_dot.setChecked(config.get("crosshair_center_dot", True))
                color_idx = self.crosshair_color.findText(config.get("crosshair_color", "green"))
                self.crosshair_color.setCurrentIndex(color_idx if color_idx >= 0 else 0)
                self.crosshair_length.setValue(config.get("crosshair_length", 10))
                self.crosshair_thickness.setValue(config.get("crosshair_thickness", 2))
                self.crosshair_gap.setValue(config.get("crosshair_gap", 4))
                self.crosshair_dot_size.setValue(config.get("crosshair_dot_size", 2))
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

        target_idx = self.target_combo.currentIndex()
        target_class_id = self._target_class_values[target_idx] if 0 <= target_idx < len(self._target_class_values) else None

        mode_idx = self.mode_combo.currentIndex()
        operation_mode = self._mode_values[mode_idx] if 0 <= mode_idx < len(self._mode_values) else "auto_aim"

        return {
            "model_path": model_path,
            "operation_mode": operation_mode,
            "target_class_id": target_class_id,
            "fov_width": self.fov_width.value(),
            "fov_height": self.fov_height.value(),
            "aim_point_y": self.aim_point_y.value(),
            "show_overlay": self.show_overlay.isChecked(),
            "show_bbox": self.show_bbox.isChecked(),
            "overlay_opacity": self.overlay_opacity.value(),
            "crosshair_show": self.crosshair_show.isChecked(),
            "crosshair_center_dot": self.crosshair_center_dot.isChecked(),
            "crosshair_color": self.crosshair_color.currentText(),
            "crosshair_length": self.crosshair_length.value(),
            "crosshair_thickness": self.crosshair_thickness.value(),
            "crosshair_gap": self.crosshair_gap.value(),
            "crosshair_dot_size": self.crosshair_dot_size.value(),
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

    def _saveConfig(self):
        """Save current settings to config file."""
        config = self._buildConfig()
        config_name = self._config_manager.get_current_config_name() or "Default"
        self._config_manager.save_config(config_name, config)

    def _setButtonState(self, active_button):
        for btn in (self.btn_start, self.btn_pause, self.btn_stop):
            btn.setChecked(btn == active_button)

    def _startTracking(self):
        if not self._tracker_manager:
            return
        config = self._buildConfig()
        window_title = None if self.window_combo.currentIndex() == 0 else self.window_combo.currentText()
        self._tracker_manager.start(config, window_title)
        self._setButtonState(self.btn_start)

    def _pauseTracking(self):
        if not self._tracker_manager:
            return
        if self._tracker_manager.is_running():
            if self._tracker_manager.is_paused():
                self._tracker_manager.resume()
                self._setButtonState(self.btn_start)
            else:
                self._tracker_manager.pause()
                self._setButtonState(self.btn_pause)

    def _stopTracking(self):
        if not self._tracker_manager:
            return
        self._tracker_manager.stop()
        self._setButtonState(self.btn_stop)

    def _onStatusChanged(self, status: str):
        status_map = {
            "running": self.btn_start,
            "paused": self.btn_pause,
            "stopped": self.btn_stop,
        }
        btn = status_map.get(status.lower())
        if btn:
            self._setButtonState(btn)

    def refreshClassConfig(self):
        """Called externally to reload class names from the currently selected model."""
        self._onModelSelected(self.model_combo.currentIndex())
