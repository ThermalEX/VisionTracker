"""Vision Tracker - Settings Page"""

import os
import json

from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from siui.components import SiDenseHContainer, SiLabel, SiTitledWidgetGroup, SiOptionCardLinear
from siui.components.page import SiPage
from siui.components.widgets.button import SiSwitch
from siui.components.widgets.label import SiSvgLabel
from siui.core import Si, SiColor, SiGlobal
from siui.gui import SiFont


# Icons used by the environment-check cards
_ICON_OK    = "ic_fluent_checkmark_circle_filled"
_ICON_WARN  = "ic_fluent_warning_filled"
_ICON_FAIL  = "ic_fluent_dismiss_circle_filled"
_ICON_UNKN  = "ic_fluent_question_circle_regular"

_STATUS_COLORS = {
    "ok":   "#44cc44",
    "warn": "#ffaa00",
    "fail": "#ff4444",
    "unknown": "#9e8fa8",
}


class EnvironmentCheckWorker(QObject):
    """Runs the environment checks off the UI thread.

    Emits itemReady for each individual check so the panel can update as
    results arrive. Emits finished once every check has been attempted.
    """
    itemReady = pyqtSignal(str, str, str)  # key, status, detail
    finished  = pyqtSignal()

    def run(self):
        # Python
        import sys as _sys
        self.itemReady.emit(
            "python", "ok",
            f"{_sys.version_info.major}.{_sys.version_info.minor}.{_sys.version_info.micro}"
        )

        # PyTorch + CUDA
        torch_ver = None
        cuda_runtime = None
        cuda_available = False
        gpu_name = None
        try:
            import torch
            torch_ver = torch.__version__
            cuda_available = torch.cuda.is_available()
            cuda_runtime = torch.version.cuda
            if cuda_available:
                try:
                    gpu_name = torch.cuda.get_device_name(0)
                except Exception:
                    gpu_name = None
        except Exception as e:
            self.itemReady.emit("torch", "fail", f"import failed: {e}")

        if torch_ver is not None:
            cuda_suffix = f" (CUDA {cuda_runtime})" if cuda_runtime else " (CPU build)"
            self.itemReady.emit("torch", "ok", f"{torch_ver}{cuda_suffix}")

        if cuda_available:
            self.itemReady.emit("cuda", "ok", f"{gpu_name or 'available'} - runtime {cuda_runtime or '?'}")
        else:
            self.itemReady.emit(
                "cuda", "fail",
                "CUDA not available - inference will fall back to CPU and the TensorRT export cannot run"
            )

        # TensorRT
        trt_ver = None
        try:
            import tensorrt as trt
            trt_ver = trt.__version__
        except Exception as e:
            self.itemReady.emit("tensorrt", "fail", f"not importable: {e}")
        if trt_ver is not None:
            if cuda_available:
                self.itemReady.emit("tensorrt", "ok", trt_ver)
            else:
                self.itemReady.emit(
                    "tensorrt", "warn",
                    f"{trt_ver} installed, but CUDA is missing - engine export will fail"
                )

        # Ultralytics
        try:
            import ultralytics
            self.itemReady.emit("ultralytics", "ok", getattr(ultralytics, "__version__", "installed"))
        except Exception as e:
            self.itemReady.emit("ultralytics", "fail", f"not importable: {e}")

        # OpenCV (used by capture / overlay)
        try:
            import cv2
            self.itemReady.emit("opencv", "ok", cv2.__version__)
        except Exception as e:
            self.itemReady.emit("opencv", "fail", f"not importable: {e}")

        # MSS (screen capture backend)
        try:
            import mss as _mss  # noqa: F401
            ver = getattr(_mss, "__version__", "installed")
            self.itemReady.emit("mss", "ok", ver)
        except Exception as e:
            self.itemReady.emit("mss", "fail", f"not importable: {e}")

        self.finished.emit()


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


class KeyCaptureButton(QPushButton):
    """Button that captures a keyboard shortcut when clicked.

    Click to enter capture mode, press any key (or combo) to bind it.
    Press Esc to cancel without changing the binding.
    """
    keyChanged = pyqtSignal(str)

    _QT_KEY_MAP = {
        Qt.Key_F1: 'f1',   Qt.Key_F2: 'f2',   Qt.Key_F3: 'f3',   Qt.Key_F4: 'f4',
        Qt.Key_F5: 'f5',   Qt.Key_F6: 'f6',   Qt.Key_F7: 'f7',   Qt.Key_F8: 'f8',
        Qt.Key_F9: 'f9',   Qt.Key_F10: 'f10', Qt.Key_F11: 'f11', Qt.Key_F12: 'f12',
        Qt.Key_Space: 'space',        Qt.Key_Return: 'enter',
        Qt.Key_Tab: 'tab',            Qt.Key_Backspace: 'backspace',
        Qt.Key_Delete: 'delete',      Qt.Key_Insert: 'insert',
        Qt.Key_Home: 'home',          Qt.Key_End: 'end',
        Qt.Key_PageUp: 'page up',     Qt.Key_PageDown: 'page down',
        Qt.Key_Left: 'left',          Qt.Key_Right: 'right',
        Qt.Key_Up: 'up',              Qt.Key_Down: 'down',
        Qt.Key_CapsLock: 'caps_lock',
        Qt.Key_NumLock: 'num lock',   Qt.Key_ScrollLock: 'scroll lock',
        Qt.Key_Print: 'print screen', Qt.Key_Pause: 'pause',
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_key = ""
        self._capturing = False
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet(BUTTON_STYLE)
        self.clicked.connect(self._startCapture)
        self.setText("None")

    def setKey(self, key: str):
        self._current_key = key or ""
        self._capturing = False
        self.setText(self._formatDisplay(key))

    def getKey(self) -> str:
        return self._current_key

    def _formatDisplay(self, key: str) -> str:
        if not key:
            return "None"
        return key.upper().replace("_", " ").replace("+", " + ")

    def _startCapture(self):
        self._capturing = True
        self.setText("Press key...")
        self.setFocus()
        self.grabKeyboard()

    def focusOutEvent(self, event):
        if self._capturing:
            self._capturing = False
            self.releaseKeyboard()
            self.setText(self._formatDisplay(self._current_key))
        super().focusOutEvent(event)

    def keyPressEvent(self, event):
        if not self._capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        modifiers = event.modifiers()

        # Esc cancels without changing
        if key == Qt.Key_Escape:
            self._capturing = False
            self.releaseKeyboard()
            self.setText(self._formatDisplay(self._current_key))
            return

        # Ignore bare modifier keys
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta):
            return

        key_str = self._buildKeyString(key, modifiers)
        if key_str:
            self._current_key = key_str
            self._capturing = False
            self.releaseKeyboard()
            self.setText(self._formatDisplay(key_str))
            self.keyChanged.emit(key_str)

    def _buildKeyString(self, key, modifiers) -> str:
        parts = []
        if modifiers & Qt.ControlModifier:
            parts.append("ctrl")
        if modifiers & Qt.ShiftModifier:
            parts.append("shift")
        if modifiers & Qt.AltModifier:
            parts.append("alt")

        if key in self._QT_KEY_MAP:
            parts.append(self._QT_KEY_MAP[key])
        elif Qt.Key_A <= key <= Qt.Key_Z:
            parts.append(chr(key).lower())
        elif Qt.Key_0 <= key <= Qt.Key_9:
            parts.append(str(key - Qt.Key_0))
        else:
            return ""

        return "+".join(parts)


class SettingsPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Settings")

        self._settings_path = os.path.normpath(
            os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data', 'app_settings.json')
        )
        self._tracker_manager = None

        # Main group
        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        # === Hotkey Settings ===
        self.titled_group.addTitle("Hotkey Settings")

        # Hint label
        hint_label = SiLabel(self)
        hint_label.setText("Click a button to rebind. Press Esc to cancel.")
        hint_label.setFont(SiFont.getFont(size=13))
        hint_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        hint_label.setFixedHeight(22)
        self.titled_group.addWidget(hint_label)

        # --- Aim Toggle ---
        self.hotkey_aim_card = SiOptionCardLinear(self)
        self.hotkey_aim_card.setTitle("Aim Toggle", "Hold or toggle this key to enable aiming (CapsLock = toggle state)")
        self.hotkey_aim_card.load(SiGlobal.siui.iconpack.get("ic_fluent_target_regular"))
        self.hotkey_aim = KeyCaptureButton(self)
        self.hotkey_aim.setFixedSize(140, 32)
        self.hotkey_aim.setKey("caps_lock")
        self.hotkey_aim.keyChanged.connect(lambda key: self._onHotkeyChanged('aim_key', key))
        self.hotkey_aim_card.addWidget(self.hotkey_aim)
        self.titled_group.addWidget(self.hotkey_aim_card)

        # --- Calibrate ---
        self.hotkey_calib_card = SiOptionCardLinear(self)
        self.hotkey_calib_card.setTitle("Calibrate", "Start sensitivity auto-calibration while tracking")
        self.hotkey_calib_card.load(SiGlobal.siui.iconpack.get("ic_fluent_ruler_regular"))
        self.hotkey_calib = KeyCaptureButton(self)
        self.hotkey_calib.setFixedSize(140, 32)
        self.hotkey_calib.setKey("f6")
        self.hotkey_calib.keyChanged.connect(lambda key: self._onHotkeyChanged('calibrate', key))
        self.hotkey_calib_card.addWidget(self.hotkey_calib)
        self.titled_group.addWidget(self.hotkey_calib_card)

        # --- Lineup Switch ---
        self.hotkey_lineup_card = SiOptionCardLinear(self)
        self.hotkey_lineup_card.setTitle("Lineup Switch", "Switch between T/CT configurations during tracking")
        self.hotkey_lineup_card.load(SiGlobal.siui.iconpack.get("ic_fluent_arrow_swap_regular"))
        self.hotkey_lineup = KeyCaptureButton(self)
        self.hotkey_lineup.setFixedSize(140, 32)
        self.hotkey_lineup.setKey("f5")
        self.hotkey_lineup.keyChanged.connect(lambda key: self._onHotkeyChanged('lineup_switch', key))
        self.hotkey_lineup_card.addWidget(self.hotkey_lineup)
        self.titled_group.addWidget(self.hotkey_lineup_card)

        # === Overlay Display ===
        self.titled_group.addTitle("Overlay Display")

        oi_hint = SiLabel(self)
        oi_hint.setText("Changes take effect immediately during tracking.")
        oi_hint.setFont(SiFont.getFont(size=13))
        oi_hint.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        oi_hint.setFixedHeight(22)
        self.titled_group.addWidget(oi_hint)

        def _mk_oi_card(title, desc, icon_key, action):
            card = SiOptionCardLinear(self)
            card.setTitle(title, desc)
            card.load(SiGlobal.siui.iconpack.get(icon_key))
            sw = SiSwitch(self)
            sw.toggled.connect(lambda checked, a=action: self._onOverlayInfoChanged(a, checked))
            card.addWidget(sw)
            self.titled_group.addWidget(card)
            return sw

        self.oi_fps    = _mk_oi_card("Show FPS",
            "Display frames per second counter",
            "ic_fluent_timer_regular", "show_fps")
        self.oi_mode   = _mk_oi_card("Show Mode",
            "Display current controller mode (LADRC / SNAP)",
            "ic_fluent_target_regular", "show_mode")
        self.oi_status = _mk_oi_card("Show AIM / FIRE",
            "Display aim and auto-fire status dots",
            "ic_fluent_cursor_hover_filled", "show_status")
        self.oi_target = _mk_oi_card("Show Target Info",
            "Display confidence and distance when a target is locked",
            "ic_fluent_eye_regular", "show_target_info")
        self.oi_errvec = _mk_oi_card("Show Error Vector",
            "Display directional offset (→← ↑↓) to locked target",
            "ic_fluent_arrow_trending_regular", "show_error_vector")
        self.oi_ctrl   = _mk_oi_card("Show Controller Params",
            "Display Kp and sensitivity values",
            "ic_fluent_settings_regular", "show_ctrl_params")

        # === Advanced Features (at the bottom) ===
        self.titled_group.addTitle("Advanced Features")

        self.advanced_mode_card = SiOptionCardLinear(self)
        self.advanced_mode_card.setTitle("Advanced Mode", "Show Training and Custom Tracker pages in the sidebar")
        self.advanced_mode_card.load(SiGlobal.siui.iconpack.get("ic_fluent_developer_board_regular"))
        self.advanced_mode_switch = SiSwitch(self)
        self.advanced_mode_switch.toggled.connect(self._onAdvancedModeToggled)
        self.advanced_mode_card.addWidget(self.advanced_mode_switch)
        self.titled_group.addWidget(self.advanced_mode_card)

        # === Environment Check (placed last - verifies system readiness) ===
        self._createEnvironmentSection()

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)

        # Sync stored values
        self._syncSwitch()
        self._loadHotkeys()
        self._loadOverlayInfo()

    def setTrackerManager(self, manager):
        self._tracker_manager = manager

    # ─── Environment check ───────────────────────────────────────────────────

    # Check key -> (title, subtitle shown before first run)
    _ENV_ITEMS = [
        ("python",      "Python",              "Interpreter version"),
        ("torch",       "PyTorch",             "Deep learning framework"),
        ("cuda",        "CUDA Runtime / GPU",  "Required for GPU inference and engine export"),
        ("tensorrt",    "TensorRT",            "Accelerates YOLO inference via .engine files"),
        ("ultralytics", "Ultralytics",         "Provides the YOLO training / export API"),
        ("opencv",      "OpenCV",              "Used for image processing and overlay rendering"),
        ("mss",         "mss",                 "Screen-capture backend"),
    ]

    def _createEnvironmentSection(self):
        self.titled_group.addTitle("Environment")

        env_hint = SiLabel(self)
        env_hint.setText("Check that CUDA, TensorRT and required Python packages are available before training or exporting engines.")
        env_hint.setFont(SiFont.getFont(size=13))
        env_hint.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        env_hint.setFixedHeight(22)
        self.titled_group.addWidget(env_hint)

        # Action card with the Run Check button
        self.env_action_card = SiOptionCardLinear(self)
        self.env_action_card.setTitle(
            "Run Environment Check",
            "Verifies interpreter, GPU, TensorRT and required libraries"
        )
        self.env_action_card.load(SiGlobal.siui.iconpack.get("ic_fluent_play_filled"))

        self.env_status_label = SiLabel(self)
        self.env_status_label.setText("Not checked yet")
        self.env_status_label.setFont(SiFont.getFont(size=13))
        self.env_status_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        self.env_status_label.setFixedHeight(22)
        self.env_action_card.addWidget(self.env_status_label)

        self.env_run_btn = QPushButton("Run Check", self)
        self.env_run_btn.setFixedSize(120, 32)
        self.env_run_btn.setStyleSheet(BUTTON_STYLE)
        self.env_run_btn.clicked.connect(self._runEnvironmentCheck)
        self.env_action_card.addWidget(self.env_run_btn)
        self.titled_group.addWidget(self.env_action_card)

        # One compact row per check item (slimmer than the action card)
        self._env_rows = {}
        self._env_icon_widgets = {}
        self._env_value_labels = {}
        for key, title, subtitle in self._ENV_ITEMS:
            row, icon_widget, value_label = self._buildEnvItemRow(title, subtitle)
            self.titled_group.addWidget(row)
            self._env_rows[key] = row
            self._env_icon_widgets[key] = icon_widget
            self._env_value_labels[key] = value_label

        self._env_worker = None
        self._env_thread = None

    def _buildEnvItemRow(self, title: str, subtitle: str):
        """Build a compact (~40px) check-item row: [icon] [title] ............ [value]."""
        def _col(key: str, fallback: str) -> str:
            try:
                return SiGlobal.siui.colors[key]
            except Exception:
                return fallback

        bg = _col("INTERFACE_BG_C", "#201d23")
        text_a = _col("TEXT_A", "#F0EEF2")
        text_c = _col("TEXT_C", "#9e8fa8")

        row = QWidget(self)
        row.setMinimumHeight(44)
        row.setObjectName("EnvRow")
        row.setStyleSheet(
            f"QWidget#EnvRow {{ background-color: {bg}; border-radius: 4px; }}"
            f"QLabel {{ background: transparent; }}"
        )

        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 8, 16, 8)
        layout.setSpacing(12)

        # Icon - use SiSvgLabel but wrap it in a container with fixed size
        icon = SiSvgLabel(row)
        icon.setFixedSize(22, 22)
        icon.setSvgSize(18, 18)
        icon.load(SiGlobal.siui.iconpack.get(_ICON_UNKN))
        layout.addWidget(icon, 0)

        # Title - plain QLabel with HTML rich text works reliably with layouts
        title_label = QLabel(row)
        title_label.setFont(SiFont.getFont(size=14))
        title_label.setTextFormat(Qt.RichText)
        title_label.setText(
            f"<span style='color:{text_a}; font-weight:600;'>{title}</span>"
            f"<span style='color:{text_c};'>  ·  {subtitle}</span>"
        )
        title_label.setStyleSheet("background: transparent;")
        title_label.setMinimumWidth(140)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        layout.addWidget(title_label, 1)

        # Value - single line, ellipsize on overflow, full text in tooltip
        value_label = QLabel(row)
        value_label.setFont(SiFont.getFont(size=14))
        value_label.setText("—")
        value_label.setWordWrap(False)
        value_label.setStyleSheet(f"color: {_STATUS_COLORS['unknown']}; background: transparent;")
        value_label.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
        value_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        value_label.setMinimumWidth(120)
        value_label.setMaximumWidth(420)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(value_label, 0)

        return row, icon, value_label

    def _runEnvironmentCheck(self):
        if self._env_thread is not None and self._env_thread.isRunning():
            return

        # Reset all rows
        for key in self._env_icon_widgets:
            self._env_icon_widgets[key].load(SiGlobal.siui.iconpack.get(_ICON_UNKN))
            self._env_value_labels[key].setText("Checking...")
            self._env_value_labels[key].setStyleSheet(f"color: {_STATUS_COLORS['unknown']}")

        self.env_status_label.setText("Running checks...")
        self.env_run_btn.setEnabled(False)

        self._env_thread = QThread(self)
        self._env_worker = EnvironmentCheckWorker()
        self._env_worker.moveToThread(self._env_thread)
        self._env_thread.started.connect(self._env_worker.run)
        self._env_worker.itemReady.connect(self._onEnvItemReady)
        self._env_worker.finished.connect(self._onEnvCheckFinished)
        self._env_worker.finished.connect(self._env_thread.quit)
        self._env_worker.finished.connect(self._env_worker.deleteLater)
        self._env_thread.finished.connect(self._env_thread.deleteLater)
        self._env_thread.start()

    def _onEnvItemReady(self, key: str, status: str, detail: str):
        icon = self._env_icon_widgets.get(key)
        label = self._env_value_labels.get(key)
        if icon is None or label is None:
            return
        icon_key = {"ok": _ICON_OK, "warn": _ICON_WARN, "fail": _ICON_FAIL}.get(status, _ICON_UNKN)
        icon.load(SiGlobal.siui.iconpack.get(icon_key))
        # Collapse any newlines so the value stays on one row; full text in tooltip
        one_line = " ".join(detail.split())
        label.setText(one_line)
        label.setToolTip(detail)
        label.setStyleSheet(f"color: {_STATUS_COLORS.get(status, _STATUS_COLORS['unknown'])}")

    def _onEnvCheckFinished(self):
        self._env_thread = None
        self._env_worker = None
        self.env_run_btn.setEnabled(True)

        # Summarise: count fails / warns by inspecting current label colours
        fails = sum(1 for lbl in self._env_value_labels.values()
                    if _STATUS_COLORS["fail"] in lbl.styleSheet())
        warns = sum(1 for lbl in self._env_value_labels.values()
                    if _STATUS_COLORS["warn"] in lbl.styleSheet())
        if fails == 0 and warns == 0:
            self.env_status_label.setText("All checks passed - the application is ready to run.")
            self.env_status_label.setStyleSheet(f"color: {_STATUS_COLORS['ok']}")
        elif fails == 0:
            self.env_status_label.setText(f"Completed with {warns} warning(s).")
            self.env_status_label.setStyleSheet(f"color: {_STATUS_COLORS['warn']}")
        else:
            self.env_status_label.setText(
                f"{fails} component(s) failed - training or engine export will not work until resolved."
            )
            self.env_status_label.setStyleSheet(f"color: {_STATUS_COLORS['fail']}")

    # ─── Settings helpers ────────────────────────────────────────────────────

    def _loadSettings(self) -> dict:
        try:
            if os.path.exists(self._settings_path):
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _saveSettings(self, data: dict):
        try:
            os.makedirs(os.path.dirname(self._settings_path), exist_ok=True)
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ─── Advanced mode ───────────────────────────────────────────────────────

    def _syncSwitch(self):
        data = self._loadSettings()
        self.advanced_mode_switch.blockSignals(True)
        self.advanced_mode_switch.setChecked(data.get('advanced_mode', False))
        self.advanced_mode_switch.blockSignals(False)

    def _onAdvancedModeToggled(self, checked: bool):
        win = self.window()
        if hasattr(win, 'setAdvancedMode'):
            win.setAdvancedMode(checked)
        data = self._loadSettings()
        data['advanced_mode'] = checked
        self._saveSettings(data)

    # ─── Hotkeys ─────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._loadHotkeys()
        self._loadOverlayInfo()

    def _loadHotkeys(self):
        """Refresh button labels from saved hotkeys."""
        data = self._loadSettings()
        hotkeys = data.get("hotkeys", {})
        self.hotkey_aim.setKey(hotkeys.get('aim_key', 'caps_lock'))
        self.hotkey_calib.setKey(hotkeys.get('calibrate', 'f6'))
        self.hotkey_lineup.setKey(hotkeys.get('lineup_switch', 'f5'))

    def _onHotkeyChanged(self, action: str, key: str):
        """Persist and propagate a hotkey change."""
        data = self._loadSettings()
        data.setdefault("hotkeys", {})[action] = key
        self._saveSettings(data)
        if self._tracker_manager:
            self._tracker_manager.set_hotkey(action, key)

    # ─── Overlay info ─────────────────────────────────────────────────────────

    _OI_DEFAULTS = {
        "show_fps": True, "show_mode": True, "show_status": True,
        "show_target_info": True, "show_error_vector": True, "show_ctrl_params": False,
    }
    _OI_SWITCHES = {}  # populated after __init__

    def _loadOverlayInfo(self):
        """Sync overlay display switches from saved settings."""
        data = self._loadSettings()
        oi = data.get("overlay_info", {})
        switches = {
            "show_fps":          self.oi_fps,
            "show_mode":         self.oi_mode,
            "show_status":       self.oi_status,
            "show_target_info":  self.oi_target,
            "show_error_vector": self.oi_errvec,
            "show_ctrl_params":  self.oi_ctrl,
        }
        for key, sw in switches.items():
            sw.blockSignals(True)
            sw.setChecked(oi.get(key, self._OI_DEFAULTS.get(key, True)))
            sw.blockSignals(False)

    def _onOverlayInfoChanged(self, action: str, checked: bool):
        """Persist overlay display flag change and push to tracker in real-time."""
        data = self._loadSettings()
        data.setdefault("overlay_info", {})[action] = checked
        self._saveSettings(data)
        if self._tracker_manager:
            self._tracker_manager.set_overlay_flag(action, checked)
