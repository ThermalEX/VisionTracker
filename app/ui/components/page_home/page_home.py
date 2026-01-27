"""Vision Tracker - Home Page"""

import os
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QTextEdit

from siui.components import SiPixLabel, SiLabel, SiTitledWidgetGroup
from siui.components.combobox_ import SiCapsuleComboBox
from siui.components.page import SiPage
from siui.components.slider_ import SiScrollBar
from siui.components.button import SiCapsuleButton
from siui.core import GlobalFont, Si, SiColor, SiGlobal
from siui.gui import SiFont

# Get the directory of this file
current_dir = os.path.dirname(os.path.abspath(__file__))
img_dir = os.path.join(current_dir, '..', '..', 'img')


class HomePage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Scroll container
        self.scroll_container = SiTitledWidgetGroup(self)

        # === Header area with background ===
        self.head_area = SiLabel(self)
        self.head_area.setFixedHeight(280)

        # Background image
        self.background_image = SiPixLabel(self.head_area)
        self.background_image.setFixedSize(1366, 250)
        self.background_image.setBorderRadius(6)
        background_path = os.path.join(img_dir, 'homepage_background.png')
        self.background_image.load(background_path)

        # Gradient fade transition
        self.background_fading_transition = SiLabel(self.head_area)
        self.background_fading_transition.setGeometry(0, 100, 0, 150)
        self.background_fading_transition.setStyleSheet(
            """
            background-color: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 {}, stop:1 {})
            """.format(
                SiGlobal.siui.colors["INTERFACE_BG_B"],
                SiColor.trans(SiGlobal.siui.colors["INTERFACE_BG_B"], 0)
            )
        )

        # Welcome text
        self._username = "User"
        self.welcome_label = SiLabel(self.head_area)
        self.welcome_label.setGeometry(64, 50, 800, 80)
        self.welcome_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.welcome_label.setText(f"{self._username} Welcome!")
        self.welcome_label.setStyleSheet("color: #FFFFFF")
        # Use larger font size
        font = SiFont.tokenized(GlobalFont.XL_MEDIUM)
        font.setPointSize(36)
        self.welcome_label.setFont(font)
        # Add shadow effect
        welcome_shadow = QGraphicsDropShadowEffect()
        welcome_shadow.setBlurRadius(20)
        welcome_shadow.setColor(QColor(0, 0, 0, 200))
        welcome_shadow.setOffset(4, 4)
        self.welcome_label.setGraphicsEffect(welcome_shadow)

        # Project name subtitle
        self.project_label = SiLabel(self.head_area)
        self.project_label.setGeometry(64, 130, 700, 35)
        self.project_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.project_label.setText("Vision Tracker - Real-time Object Detection and Tracking System")
        self.project_label.setStyleSheet("color: rgba(255, 255, 255, 0.9)")
        font = SiFont.tokenized(GlobalFont.M_NORMAL)
        font.setPointSize(14)
        self.project_label.setFont(font)
        # Add shadow effect
        project_shadow = QGraphicsDropShadowEffect()
        project_shadow.setBlurRadius(15)
        project_shadow.setColor(QColor(0, 0, 0, 180))
        project_shadow.setOffset(3, 3)
        self.project_label.setGraphicsEffect(project_shadow)

        # Add header to scroll container
        self.scroll_container.addWidget(self.head_area)

        # === Body area for additional content ===
        self.body_area = SiLabel(self)
        self.body_area.setSiliconWidgetFlag(Si.EnableAnimationSignals)
        self.body_area.resized.connect(lambda _: self.scroll_container.adjustSize())
        self.body_area.setFixedHeight(320)

        # === Left Panel: Control Panel ===
        self.left_panel = SiLabel(self.body_area)
        self.left_panel.setFixedSize(280, 300)
        self.left_panel.setStyleSheet(
            f"background-color: {SiGlobal.siui.colors['INTERFACE_BG_C']};"
            "border-radius: 8px;"
        )

        # ComboBox for config selection
        self.config_combo = SiCapsuleComboBox(self.left_panel)
        self.config_combo.setGeometry(20, 20, 240, 36)
        self.config_combo.setTitle("Configuration")
        self.config_combo.setMinimumHeight(36)
        self.config_combo.setEditable(False)
        self.config_combo.addItems(["Default"])
        # Remove underline indicator
        self.config_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.config_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        # More configurations will be added from Settings page

        # Button management for exclusive toggle
        self._current_active_button = None

        # Start button (Green theme)
        self.start_button = SiCapsuleButton(self.left_panel)
        self.start_button.setGeometry(20, 96, 240, 44)
        self.start_button.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_play_filled"))
        self.start_button.setValue("Start")  # Value for right side
        self.start_button.setThemeColor(SiCapsuleButton.Theme.Green)
        self.start_button.toggled.connect(self._on_start_toggled)

        # Pause button (Yellow theme)
        self.pause_button = SiCapsuleButton(self.left_panel)
        self.pause_button.setGeometry(20, 152, 240, 44)
        self.pause_button.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_pause_filled"))
        self.pause_button.setValue("Pause")  # Value for right side
        self.pause_button.setThemeColor(SiCapsuleButton.Theme.Yellow)
        self.pause_button.toggled.connect(self._on_pause_toggled)

        # Stop button (Red theme)
        self.stop_button = SiCapsuleButton(self.left_panel)
        self.stop_button.setGeometry(20, 208, 240, 44)
        self.stop_button.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_stop_filled"))
        self.stop_button.setValue("Stop")  # Value for right side
        self.stop_button.setThemeColor(SiCapsuleButton.Theme.Red)
        self.stop_button.toggled.connect(self._on_stop_toggled)

        # === Right Panel: Console Output ===
        self.right_panel = SiLabel(self.body_area)
        self.right_panel.setFixedSize(550, 300)
        self.right_panel.setStyleSheet(
            f"background-color: {SiGlobal.siui.colors['INTERFACE_BG_C']};"
            "border-radius: 8px;"
        )

        # Console header
        self.terminal_header = SiLabel(self.right_panel)
        self.terminal_header.setFixedSize(550, 36)
        self.terminal_header.setText("   Console Output")
        self.terminal_header.setFont(SiFont.tokenized(GlobalFont.S_BOLD))
        self.terminal_header.setStyleSheet(
            f"background-color: {SiGlobal.siui.colors['INTERFACE_BG_D']};"
            f"color: {SiGlobal.siui.colors['TEXT_A']};"
            "border-top-left-radius: 8px;"
            "border-top-right-radius: 8px;"
            "border-bottom-left-radius: 0px;"
            "border-bottom-right-radius: 0px;"
            "padding-left: 12px;"
        )
        self.terminal_header.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        # Console output area
        self.terminal_output = QTextEdit(self.right_panel)
        self.terminal_output.setGeometry(1, 36, 548, 263)
        self.terminal_output.setReadOnly(True)
        self.terminal_output.setStyleSheet(
            f"""QTextEdit {{
                background-color: {SiGlobal.siui.colors['INTERFACE_BG_A']};
                color: {SiGlobal.siui.colors['TEXT_B']};
                border: none;
                border-top-left-radius: 0px;
                border-top-right-radius: 0px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 12px;
                padding: 12px;
            }}"""
        )

        # Use SiScrollBar for themed scrollbar
        self.terminal_scrollbar = SiScrollBar(self.terminal_output)
        self.terminal_scrollbar.setOrientation(Qt.Vertical)
        self.terminal_scrollbar.setFixedWidth(8)
        self.terminal_scrollbar.setStyleSheet(
            "QScrollBar:vertical {"
            "    background-color: transparent;"
            "    border: none;"
            "}"
        )
        self.terminal_output.setVerticalScrollBar(self.terminal_scrollbar)

        # Initialize with welcome message
        self._init_terminal_message()

        # Add body to scroll container
        self.scroll_container.addWidget(self.body_area)

        # Set attachment
        self.setAttachment(self.scroll_container)

    def setUsername(self, username: str):
        """Set the username displayed in welcome message."""
        self._username = username
        self.welcome_label.setText(f"{self._username} Welcome!")

    def _init_terminal_message(self):
        """Initialize the terminal with welcome message."""
        welcome_text = """===============================================
     Vision Tracker - Target Tracking System
===============================================

Welcome to Vision Tracker!

[Instructions]
  1. Select a configuration from the dropdown
  2. Click "Start" to begin target tracking
  3. Click "Pause" to pause tracking
  4. Click "Stop" to end tracking

[Hotkeys]
  [Space]  - Pause / Resume
  [Esc]    - Stop tracking
  [S]      - Save screenshot
  [R]      - Reset tracking target

[Status] Waiting to start...
"""
        self.terminal_output.setText(welcome_text)

    def log(self, message: str, level: str = "INFO"):
        """Add a log message to the terminal output."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        color_map = {
            "INFO": SiGlobal.siui.colors['TEXT_B'],
            "WARN": "#ffaa00",
            "ERROR": "#ff4444",
            "SUCCESS": "#44cc44",
        }
        color = color_map.get(level, SiGlobal.siui.colors['TEXT_B'])
        formatted = f'<span style="color: {SiGlobal.siui.colors["TEXT_D"]}">[{timestamp}]</span> <span style="color: {color}">[{level}]</span> {message}'
        self.terminal_output.append(formatted)
        # Auto scroll to bottom
        scrollbar = self.terminal_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _set_button_active(self, active_button):
        """Set the active button and deactivate others for exclusive toggle."""
        buttons = [self.start_button, self.pause_button, self.stop_button]
        for button in buttons:
            if button != active_button:
                button.setChecked(False)
        self._current_active_button = active_button

    def _on_start_toggled(self, checked):
        """Handle start button toggle."""
        if checked:
            self._set_button_active(self.start_button)
            config = self.config_combo.currentText() or "Default"
            self.log("Starting tracking system...", "INFO")
            self.log(f"Current configuration: {config}", "INFO")
            self.log("Tracking system started", "SUCCESS")

    def _on_pause_toggled(self, checked):
        """Handle pause button toggle."""
        if checked:
            self._set_button_active(self.pause_button)
            self.log("Tracking paused", "WARN")

    def _on_stop_toggled(self, checked):
        """Handle stop button toggle."""
        if checked:
            self._set_button_active(self.stop_button)
            self.log("Tracking stopped", "INFO")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = event.size().width()
        self.body_area.setFixedWidth(w)
        self.background_image.setFixedWidth(w)
        self.background_fading_transition.setFixedWidth(w)

        # Calculate panel positions for centering
        spacing = 24
        left_width = 280
        right_width = 550

        # Adjust right panel width dynamically if window is wide enough
        available_width = w - left_width - spacing - 64  # window - left_panel - spacing - margins
        if available_width > 550:
            right_width = min(available_width, 700)
            self.right_panel.setFixedWidth(right_width)
            self.terminal_header.setFixedWidth(right_width)
            self.terminal_output.setGeometry(1, 36, right_width - 2, 263)

        # Calculate center position
        total_content_width = left_width + spacing + right_width
        center_x = (w - total_content_width) // 2
        center_x = max(center_x, 32)  # Minimum margin

        # Position the panels
        self.left_panel.move(center_x, 0)
        self.right_panel.move(center_x + left_width + spacing, 0)
