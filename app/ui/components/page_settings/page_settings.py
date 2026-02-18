"""Vision Tracker - Settings Page"""

import os
import json

from PyQt5.QtCore import Qt

from siui.components import SiTitledWidgetGroup, SiOptionCardLinear
from siui.components.page import SiPage
from siui.components.widgets.button import SiSwitch
from siui.core import SiGlobal


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

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)

        # Sync switch with saved setting (no callback)
        self._syncSwitch()

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
                json.dump(data, f, indent=2)
        except Exception:
            pass

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
