"""Vision Tracker - Settings Page"""

import os
import json

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from siui.components import SiDenseHContainer, SiLabel, SiTitledWidgetGroup, SiOptionCardLinear
from siui.components.page import SiPage
from siui.components.widgets.button import SiSwitch
from siui.components.button import SiPushButtonRefactor
from siui.core import SiColor, SiGlobal
from siui.gui import SiFont


class KeyCaptureButton(SiPushButtonRefactor):
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

        # === Advanced Features ===
        self.titled_group.addTitle("Advanced Features")

        self.advanced_mode_card = SiOptionCardLinear(self)
        self.advanced_mode_card.setTitle("Advanced Mode", "Show Training and Custom Tracker pages in the sidebar")
        self.advanced_mode_card.load(SiGlobal.siui.iconpack.get("ic_fluent_developer_board_regular"))
        self.advanced_mode_switch = SiSwitch(self)
        self.advanced_mode_switch.toggled.connect(self._onAdvancedModeToggled)
        self.advanced_mode_card.addWidget(self.advanced_mode_switch)
        self.titled_group.addWidget(self.advanced_mode_card)

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
        oi_hint.setText("Takes effect on next tracking start.")
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

        self.oi_fps   = _mk_oi_card("Show FPS",
            "Display frames per second counter",
            "ic_fluent_timer_regular", "show_fps")
        self.oi_mode  = _mk_oi_card("Show Mode",
            "Display current controller mode (LADRC / SNAP)",
            "ic_fluent_target_regular", "show_mode")
        self.oi_status = _mk_oi_card("Show AIM / FIRE",
            "Display aim and auto-fire status dots",
            "ic_fluent_cursor_hover_filled", "show_status")
        self.oi_target = _mk_oi_card("Show Target Info",
            "Display confidence and distance when a target is locked",
            "ic_fluent_eye_regular", "show_target_info")
        self.oi_ctrl  = _mk_oi_card("Show Controller Params",
            "Display Kp and sensitivity values",
            "ic_fluent_settings_regular", "show_ctrl_params")

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)

        # Sync stored values
        self._syncSwitch()
        self._loadHotkeys()
        self._loadOverlayInfo()

    def setTrackerManager(self, manager):
        self._tracker_manager = manager

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
        "show_target_info": True, "show_ctrl_params": False,
    }
    _OI_SWITCHES = {}  # populated after __init__

    def _loadOverlayInfo(self):
        """Sync overlay display switches from saved settings."""
        data = self._loadSettings()
        oi = data.get("overlay_info", {})
        switches = {
            "show_fps":         self.oi_fps,
            "show_mode":        self.oi_mode,
            "show_status":      self.oi_status,
            "show_target_info": self.oi_target,
            "show_ctrl_params": self.oi_ctrl,
        }
        for key, sw in switches.items():
            sw.blockSignals(True)
            sw.setChecked(oi.get(key, self._OI_DEFAULTS.get(key, True)))
            sw.blockSignals(False)

    def _onOverlayInfoChanged(self, action: str, checked: bool):
        """Persist overlay display flag change."""
        data = self._loadSettings()
        data.setdefault("overlay_info", {})[action] = checked
        self._saveSettings(data)
