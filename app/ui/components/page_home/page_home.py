"""Vision Tracker - Home Page"""

import os
from datetime import datetime
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QTextEdit

from siui.components import SiPixLabel, SiLabel, SiTitledWidgetGroup, SiDenseHContainer
from siui.components.combobox_ import SiCapsuleComboBox
from siui.components.page import SiPage
from siui.components.slider_ import SiScrollBar
from siui.components.button import SiCapsuleButton, SiFlatButtonWithIndicator
from siui.components.widgets.button import SiSimpleButton
from siui.core import GlobalFont, Si, SiColor, SiGlobal
from siui.gui import SiFont
from PyQt5.QtWidgets import QButtonGroup

from utils.config_manager import ConfigManager
from core.capture import get_available_windows

# Get the directory of this file
current_dir = os.path.dirname(os.path.abspath(__file__))
img_dir = os.path.join(current_dir, '..', '..', 'img')


class HomePage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Config manager instance
        self._config_manager = ConfigManager()

        # Tracker manager (will be set by app)
        self._tracker_manager = None

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
        self.body_area.setFixedHeight(340)

        # === Left Panel: Control Panel ===
        self.left_panel = SiLabel(self.body_area)
        self.left_panel.setFixedSize(320, 320)
        self.left_panel.setStyleSheet(
            f"background-color: {SiGlobal.siui.colors['INTERFACE_BG_C']};"
            "border-radius: 8px;"
        )

        # ComboBox for config selection
        self.config_combo = SiCapsuleComboBox(self.left_panel)
        self.config_combo.setGeometry(20, 20, 280, 36)
        self.config_combo.setTitle("Configuration")
        self.config_combo.setMinimumHeight(36)
        self.config_combo.setEditable(False)
        # Remove underline indicator
        self.config_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.config_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        # Load configurations from ConfigManager
        self._load_config_list()

        # ComboBox for window selection
        self.window_combo = SiCapsuleComboBox(self.left_panel)
        self.window_combo.setGeometry(20, 66, 240, 36)
        self.window_combo.setTitle("Windows")
        self.window_combo.setMinimumHeight(36)
        self.window_combo.setEditable(False)
        # Remove underline indicator
        self.window_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.window_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        # Update tooltip when selection changes
        self.window_combo.currentTextChanged.connect(self._update_window_tooltip)
        # Load available windows
        self._load_window_list()

        # Refresh button for window list
        self.refresh_window_button = SiSimpleButton(self.left_panel)
        self.refresh_window_button.setGeometry(264, 66, 36, 36)
        self.refresh_window_button.attachment().load(SiGlobal.siui.iconpack.get("ic_fluent_arrow_sync_filled"))
        self.refresh_window_button.setToolTip("Refresh window list")
        self.refresh_window_button.clicked.connect(self._load_window_list)

        # === Team Toggle (CT / T) with indicator buttons ===
        # Target team: which team to aim at
        self._target_team = 'T'  # Default: target T

        # Team button container
        self.team_container = SiDenseHContainer(self.left_panel)
        self.team_container.setGeometry(20, 112, 280, 36)
        self.team_container.setSpacing(8)

        # CT button (lock on CT targets)
        self.ct_button = SiFlatButtonWithIndicator(self.left_panel)
        self.ct_button.setText("CT")
        self.ct_button.setFixedSize(88, 36)
        self.ct_button.setToolTip("Lock on CT targets")

        # ALL button (lock on all targets)
        self.all_button = SiFlatButtonWithIndicator(self.left_panel)
        self.all_button.setText("ALL")
        self.all_button.setFixedSize(88, 36)
        self.all_button.setToolTip("Lock on all targets")

        # T button (lock on T targets)
        self.t_button = SiFlatButtonWithIndicator(self.left_panel)
        self.t_button.setText("T")
        self.t_button.setFixedSize(88, 36)
        self.t_button.setToolTip("Lock on T targets")

        self.team_container.addWidget(self.ct_button, side="left")
        self.team_container.addWidget(self.all_button, side="left")
        self.team_container.addWidget(self.t_button, side="left")

        # Team button group for exclusive selection
        self.team_button_group = QButtonGroup(self)
        self.team_button_group.addButton(self.ct_button)
        self.team_button_group.addButton(self.all_button)
        self.team_button_group.addButton(self.t_button)
        self.team_button_group.setExclusive(True)
        self.team_button_group.buttonClicked.connect(self._on_team_button_clicked)

        # Set default selection AFTER adding to group (default: target T)
        self.t_button.setChecked(True)

        # Button management for exclusive toggle
        self._current_active_button = None

        # Start button (Green theme)
        self.start_button = SiCapsuleButton(self.left_panel)
        self.start_button.setGeometry(20, 156, 280, 44)
        self.start_button.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_play_filled"))
        self.start_button.setValue("Start")  # Value for right side
        self.start_button.setThemeColor(SiCapsuleButton.Theme.Green)
        self.start_button.setCheckable(True)  # Make sure it's checkable
        self.start_button.clicked.connect(lambda: self._on_button_clicked(self.start_button))

        # Pause button (Yellow theme)
        self.pause_button = SiCapsuleButton(self.left_panel)
        self.pause_button.setGeometry(20, 208, 280, 44)
        self.pause_button.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_pause_filled"))
        self.pause_button.setValue("Pause")  # Value for right side
        self.pause_button.setThemeColor(SiCapsuleButton.Theme.Yellow)
        self.pause_button.setCheckable(True)  # Make sure it's checkable
        self.pause_button.clicked.connect(lambda: self._on_button_clicked(self.pause_button))

        # Stop button (Red theme)
        self.stop_button = SiCapsuleButton(self.left_panel)
        self.stop_button.setGeometry(20, 260, 280, 44)
        self.stop_button.setIcon(SiGlobal.siui.iconpack.get("ic_fluent_stop_filled"))
        self.stop_button.setValue("Stop")  # Value for right side
        self.stop_button.setThemeColor(SiCapsuleButton.Theme.Red)
        self.stop_button.setCheckable(True)  # Make sure it's checkable
        self.stop_button.clicked.connect(lambda: self._on_button_clicked(self.stop_button))

        # === Right Panel: Console Output ===
        self.right_panel = SiLabel(self.body_area)
        self.right_panel.setFixedSize(550, 320)
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
        self.terminal_output.setGeometry(1, 36, 548, 283)
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

    def _load_config_list(self):
        """Load configuration list from ConfigManager."""
        configs = self._config_manager.list_configs()
        self.config_combo.clear()
        self.config_combo.addItems(configs)
        # Set default config as selected
        if "Default" in configs:
            self.config_combo.setCurrentIndex(configs.index("Default"))
        elif configs:
            self.config_combo.setCurrentIndex(0)

    def refresh_config_list(self):
        """Public method to refresh the config list (called from config page)."""
        self._load_config_list()

    def _load_window_list(self):
        """Load available windows list."""
        current_text = self.window_combo.currentText()
        self.window_combo.clear()
        self.window_combo.addItem("Fullscreen")
        windows = get_available_windows()
        self.window_combo.addItems(windows)

        # Try to restore previous selection
        index = self.window_combo.findText(current_text)
        if index >= 0:
            self.window_combo.setCurrentIndex(index)
        else:
            # Default to Counter-Strike 2 if available
            for i in range(self.window_combo.count()):
                if "Counter-Strike 2" in self.window_combo.itemText(i):
                    self.window_combo.setCurrentIndex(i)
                    break
            else:
                self.window_combo.setCurrentIndex(0)

        self._update_window_tooltip(self.window_combo.currentText())

    def refresh_window_list(self):
        """Public method to refresh the window list."""
        self._load_window_list()

    def _update_window_tooltip(self, text: str):
        """Update tooltip to show full window name."""
        self.window_combo.setToolTip(text)

    def _on_team_button_clicked(self, button):
        """Handle team button click."""
        if button == self.ct_button:
            self._target_team = 'CT'
            self.log("Target switched to: CT", "INFO")
        elif button == self.all_button:
            self._target_team = 'ALL'
            self.log("Target switched to: ALL", "INFO")
        else:
            self._target_team = 'T'
            self.log("Target switched to: T", "INFO")

        # Update tracker if running
        if self._tracker_manager and self._tracker_manager.is_running():
            self._tracker_manager.set_target_team(self._target_team)

    def setTrackerManager(self, tracker_manager):
        """Set the tracker manager instance."""
        self._tracker_manager = tracker_manager
        # Connect signals
        self._tracker_manager.log_message.connect(self.log)
        self._tracker_manager.status_changed.connect(self._on_status_changed)

    def _on_status_changed(self, status: str):
        """Handle tracker status changes."""
        if status == "running":
            self._set_button_state(self.start_button)
        elif status == "paused":
            self._set_button_state(self.pause_button)
        elif status == "stopped":
            self._set_button_state(self.stop_button)

    def _set_button_state(self, active_button):
        """Set button checked states."""
        buttons = [self.start_button, self.pause_button, self.stop_button]
        for button in buttons:
            button.setChecked(button == active_button)
        self._current_active_button = active_button

    def _init_terminal_message(self):
        """Initialize the terminal with welcome message."""
        welcome_text = """===============================================
     Vision Tracker - Target Tracking System
===============================================

Welcome to Vision Tracker!

[Instructions]
  1. Select a configuration from the dropdown
  2. Select target window (or Fullscreen)
  3. Click "Start" to begin target tracking
  4. Click "Pause" to pause tracking
  5. Click "Stop" to end tracking

[Hotkeys] (when tracking is running)
  [Caps Lock] - Enable/Disable aiming
  [Space]     - Pause / Resume
  [Ctrl+Q]    - Stop tracking
  [F6]        - Calibration

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

    def _on_button_clicked(self, clicked_button):
        """Handle button clicks for exclusive selection."""
        if not self._tracker_manager:
            self.log("Tracker manager not initialized", "ERROR")
            return

        # Handle each button action
        if clicked_button == self.start_button:
            if self._tracker_manager.is_running():
                if self._tracker_manager.is_paused():
                    # Resume from pause
                    self._tracker_manager.resume()
                else:
                    # Already running, keep checked
                    clicked_button.setChecked(True)
                return

            # Start new tracking session
            config_name = self.config_combo.currentText() or "Default"
            config = self._config_manager.load_config(config_name)
            if not config:
                self.log(f"Failed to load config: {config_name}", "ERROR")
                return

            # Apply target team from UI
            config['target_team'] = self._target_team

            # Get window title (None for fullscreen)
            if self.window_combo.currentIndex() == 0:
                window_title = None  # Fullscreen
            else:
                window_title = self.window_combo.currentText()

            self.log("Starting tracking system...", "INFO")
            self.log(f"Configuration: {config_name}", "INFO")
            self._tracker_manager.start(config, window_title)

        elif clicked_button == self.pause_button:
            if self._tracker_manager.is_running():
                if self._tracker_manager.is_paused():
                    # Already paused, keep checked
                    clicked_button.setChecked(True)
                else:
                    self._tracker_manager.pause()
            else:
                self.log("Tracking is not running", "WARN")
                clicked_button.setChecked(False)

        elif clicked_button == self.stop_button:
            if self._tracker_manager.is_running():
                self._tracker_manager.stop()
            else:
                self.log("Tracking is not running", "WARN")
                clicked_button.setChecked(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = event.size().width()
        self.body_area.setFixedWidth(w)
        self.background_image.setFixedWidth(w)
        self.background_fading_transition.setFixedWidth(w)

        # Calculate panel positions for centering
        spacing = 24
        left_width = 320
        right_width = 550

        # Adjust right panel width dynamically if window is wide enough
        available_width = w - left_width - spacing - 64  # window - left_panel - spacing - margins
        if available_width > 550:
            right_width = min(available_width, 700)
            self.right_panel.setFixedWidth(right_width)
            self.terminal_header.setFixedWidth(right_width)
            self.terminal_output.setGeometry(1, 36, right_width - 2, 283)

        # Calculate center position
        total_content_width = left_width + spacing + right_width
        center_x = (w - total_content_width) // 2
        center_x = max(center_x, 32)  # Minimum margin

        # Position the panels
        self.left_panel.move(center_x, 0)
        self.right_panel.move(center_x + left_width + spacing, 0)
