"""Vision Tracker - Main Application UI"""

import os
import sys
from PyQt5.QtCore import QTimer, QSettings
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDesktopWidget

import siui
from siui.core import SiColor, SiGlobal, GlobalFont, Si
from siui.gui import SiFont
from siui.components import SiLabel
from siui.components.button import SiPushButtonRefactor as SiPushButton
from siui.components.widgets.button import SiCheckBox
from siui.templates.application.application import SiliconApplication
from siui.templates.application.components.layer.layer_login import LayerLogin
from siui.templates.application.components.layer.layer_right_message_sidebar.messagebox import SiSideMessageBox

from . import icons
from .components import HomePage, AboutPage, AdminPage, UserPage, ConfigPage, SettingsPage, StatisticsPage, LogsPage, HelpPage, TrainingPage, CustomTrackerPage

from auth import DatabaseManager, SessionManager, EmailService
from auth.config import AuthConfig


def set_dark_titlebar(hwnd):
    """Set dark titlebar on Windows 10/11."""
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass

# Get the directory of this file
current_dir = os.path.dirname(os.path.abspath(__file__))

# Load icons
siui.core.globals.SiGlobal.siui.loadIcons(
    icons.IconDictionary(color=SiGlobal.siui.colors.fromToken(SiColor.SVG_NORMAL)).icons
)


class VisionTrackerApp(SiliconApplication):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Window setup
        screen_geo = QDesktopWidget().screenGeometry()
        self.setMinimumSize(1024, 600)
        self.resize(1200, 725)
        self.move((screen_geo.width() - self.width()) // 2, (screen_geo.height() - self.height()) // 2)

        # Window title and icon
        self.setWindowTitle("Vision Tracker")

        # Set window icon
        icon_path = os.path.join(current_dir, "img", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Pre-load PyTorch modules to avoid DLL conflicts in worker thread
        from core.detector import Detector
        from core.tracker import AimController

        # Initialize tracker manager
        from core.tracker_manager import TrackerManager
        self.tracker_manager = TrackerManager(self)

        # Add pages
        # Home page - top
        self.home_page = HomePage(self)
        self.home_page.setTrackerManager(self.tracker_manager)
        self.layerMain().addPage(
            self.home_page,
            icon=SiGlobal.siui.iconpack.get("ic_fluent_home_filled"),
            hint="Home",
            side="top"
        )

        # Config page - top
        self.config_page = ConfigPage(self)
        self.layerMain().addPage(
            self.config_page,
            icon=SiGlobal.siui.iconpack.get("ic_fluent_edit_settings_filled"),
            hint="Configuration",
            side="top"
        )

        # Statistics page - top
        self.layerMain().addPage(
            StatisticsPage(self),
            icon=SiGlobal.siui.iconpack.get("ic_fluent_data_pie_filled"),
            hint="Statistics",
            side="top"
        )

        # Logs page - top
        self.layerMain().addPage(
            LogsPage(self),
            icon=SiGlobal.siui.iconpack.get("ic_fluent_document_text_clock_filled"),
            hint="Logs",
            side="top"
        )

        # Training page - top (hidden by default, shown in advanced mode)
        self.training_page = TrainingPage(self)
        self.layerMain().addPage(
            self.training_page,
            icon=SiGlobal.siui.iconpack.get("ic_fluent_brain_circuit_filled"),
            hint="Training",
            side="top"
        )
        _nav = self.layerMain().page_view.page_navigator
        self.training_button_index = len(_nav.buttons) - 1
        _btn = _nav.buttons[self.training_button_index]
        _btn.hide()
        _nav.container.widgets_top.remove(_btn)

        # Custom Tracker page - top (hidden by default, shown in advanced mode)
        self.custom_tracker_page = CustomTrackerPage(self)
        self.custom_tracker_page.setTrackerManager(self.tracker_manager)
        self.layerMain().addPage(
            self.custom_tracker_page,
            icon=SiGlobal.siui.iconpack.get("ic_fluent_cursor_hover_filled"),
            hint="Custom Tracker",
            side="top"
        )
        self.custom_tracker_button_index = len(_nav.buttons) - 1
        _btn = _nav.buttons[self.custom_tracker_button_index]
        _btn.hide()
        _nav.container.widgets_top.remove(_btn)
        _nav.container.arrangeWidget()

        # Help page - top
        self.help_page_index = self.layerMain().page_view.stacked_container.widgetsAmount()
        self.layerMain().addPage(
            HelpPage(self),
            icon=SiGlobal.siui.iconpack.get("ic_fluent_chat_help_filled"),
            hint="Help",
            side="top"
        )
        self.help_button_index = len(_nav.buttons) - 1

        # Settings page - top (last in top section)
        self.settings_page = SettingsPage(self)
        self.layerMain().addPage(
            self.settings_page,
            icon=SiGlobal.siui.iconpack.get("ic_fluent_settings_filled"),
            hint="Settings",
            side="top"
        )

        # User page - 添加到page_view但不在侧边栏显示按钮
        self.user_page = UserPage(self)
        self.layerMain().page_view.stacked_container.addWidget(self.user_page)
        self.user_page_index = self.layerMain().page_view.stacked_container.widgetsAmount() - 1

        # About page - bottom (at the very bottom)
        self.layerMain().addPage(
            AboutPage(self),
            icon=SiGlobal.siui.iconpack.get("ic_fluent_info_filled"),
            hint="About",
            side="bottom"
        )

        # Admin page - bottom (above About)
        self.admin_page = AdminPage(self)
        self.admin_page_index = self.layerMain().page_view.stacked_container.widgetsAmount()
        self.layerMain().addPage(
            self.admin_page,
            icon=SiGlobal.siui.iconpack.get("ic_fluent_shield_filled"),
            hint="Admin",
            side="bottom"
        )
        # Store admin button index for later access
        self.admin_button_index = len(self.layerMain().page_view.page_navigator.buttons) - 1
        # Hide admin page button by default
        self.layerMain().page_view.page_navigator.buttons[self.admin_button_index].hide()

        # 设置标题栏用户按钮图标并连接点击事件
        self.layerMain().setUserButtonIcon(SiGlobal.siui.iconpack.get("ic_fluent_person_filled"))
        self.layerMain().user_button_clicked.connect(self._onUserButtonClicked)

        # Set default page
        self.layerMain().setPage(0)

        # Initialize authentication system
        self._initAuth()

        # Apply saved advanced mode setting
        self._loadAdvancedMode()

        # Reload stylesheets
        SiGlobal.siui.reloadAllWindowsStyleSheet()

    def setAdvancedMode(self, enabled: bool):
        """Show or hide the Training and Custom Tracker sidebar buttons with animation."""
        from PyQt5.QtCore import QVariantAnimation, QEasingCurve

        navigator = self.layerMain().page_view.page_navigator
        container = navigator.container
        buttons = navigator.buttons
        training_btn = buttons[self.training_button_index]
        custom_tracker_btn = buttons[self.custom_tracker_button_index]
        help_btn = buttons[self.help_button_index]

        # Stop any in-progress animation
        if hasattr(self, '_advanced_mode_anim') and self._advanced_mode_anim is not None:
            self._advanced_mode_anim.stop()
            self._advanced_mode_anim = None

        if enabled:
            # Insert into layout before Help button
            if training_btn not in container.widgets_top and help_btn in container.widgets_top:
                pos = container.widgets_top.index(help_btn)
                container.widgets_top.insert(pos, training_btn)
                container.widgets_top.insert(pos + 1, custom_tracker_btn)
            for btn in (training_btn, custom_tracker_btn):
                btn.setFixedHeight(0)
                btn.show()
            container.arrangeWidget()

            anim = QVariantAnimation(self)
            anim.setStartValue(0)
            anim.setEndValue(40)
            anim.setDuration(200)
            anim.setEasingCurve(QEasingCurve.OutCubic)

            def _on_value_show(val):
                h = int(val)
                training_btn.setFixedHeight(h)
                custom_tracker_btn.setFixedHeight(h)
                container.arrangeWidget()

            def _on_done_show():
                for b in (training_btn, custom_tracker_btn):
                    b.setMinimumHeight(0)
                    b.setMaximumHeight(16777215)
                    b.resize(40, 40)
                container.arrangeWidget()
                self._advanced_mode_anim = None

            anim.valueChanged.connect(_on_value_show)
            anim.finished.connect(_on_done_show)
            self._advanced_mode_anim = anim
            anim.start()

        else:
            start_h = training_btn.height() if training_btn in container.widgets_top else 40

            anim = QVariantAnimation(self)
            anim.setStartValue(start_h)
            anim.setEndValue(0)
            anim.setDuration(150)
            anim.setEasingCurve(QEasingCurve.InCubic)

            def _on_value_hide(val):
                h = int(val)
                training_btn.setFixedHeight(h)
                custom_tracker_btn.setFixedHeight(h)
                container.arrangeWidget()

            def _on_done_hide():
                for b in (training_btn, custom_tracker_btn):
                    if b in container.widgets_top:
                        container.widgets_top.remove(b)
                    b.hide()
                    b.setMinimumHeight(0)
                    b.setMaximumHeight(16777215)
                    b.resize(40, 40)
                container.arrangeWidget()
                self._advanced_mode_anim = None

            anim.valueChanged.connect(_on_value_hide)
            anim.finished.connect(_on_done_hide)
            self._advanced_mode_anim = anim
            anim.start()

    def _loadAdvancedMode(self):
        """Read app_settings.json and apply advanced mode on startup."""
        import json as _json
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        settings_path = os.path.join(app_dir, "data", "app_settings.json")
        try:
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = _json.load(f)
                if data.get("advanced_mode", False):
                    self.setAdvancedMode(True)
        except Exception:
            pass

    def _initAuth(self):
        """Initialize authentication system."""
        # Initialize database
        self.db_manager = DatabaseManager()
        self.db_manager.init_database()

        # Initialize session manager
        self.session_manager = SessionManager(self.db_manager)

        # Initialize email service
        auth_config = AuthConfig()
        smtp_config = auth_config.get_smtp_config()
        self.email_service = EmailService(smtp_config, self.db_manager)

        # Create login layer (initially hidden)
        self.layer_login = LayerLogin(self)
        self.layer_login.setAuthServices(self.db_manager, self.session_manager, self.email_service)
        self.layer_login.login_successful.connect(self._onLoginSuccess)
        self.layer_login.hide()

        # Setup user page
        self.user_page.setAuthServices(self.db_manager, self.session_manager, self.email_service)

        # Setup admin page
        self.admin_page.setAuthServices(self.db_manager)
        self.user_page.logout_requested.connect(self.logout)
        self.user_page.username_changed.connect(self._onUsernameChanged)

        # Current user
        self.current_user = None

        # Check auto-login
        self._checkAutoLogin()

    def _checkAutoLogin(self):
        """Check if auto-login is possible."""
        user = self.session_manager.check_auto_login()
        if user:
            self.current_user = user
            self.home_page.setUsername(user.username)
            self.user_page.setUser(user)
            # Show admin page button if user is admin (id == 1)
            if user.id == 1:
                self.layerMain().page_view.page_navigator.buttons[self.admin_button_index].show()
            else:
                self.layerMain().page_view.page_navigator.buttons[self.admin_button_index].hide()
            # Flag to show notifications after window is visible
            self._auto_login_user = user
        else:
            # Delay showing login layer until window is fully rendered
            self._need_login = True
            self._auto_login_user = None

    def _onLoginSuccess(self, user):
        """Handle successful login."""
        self.current_user = user
        self.home_page.setUsername(user.username)
        self.user_page.setUser(user)

        # Show admin page button if user is admin (id == 1)
        if user.id == 1:
            self.layerMain().page_view.page_navigator.buttons[self.admin_button_index].show()
        else:
            self.layerMain().page_view.page_navigator.buttons[self.admin_button_index].hide()

        # Reset "don't show again" setting on fresh login
        settings = QSettings("VisionTracker", "App")
        settings.setValue("hide_help_notification", False)

        # Send notifications
        self._sendLoginNotifications(user)

    def _sendLoginNotifications(self, user):
        """Send login success and help notifications."""
        # Send login success notification
        self.LayerRightMessageSidebar().send(
            title="Login Successful",
            text=f"Welcome back, {user.username}!",
            msg_type=1,  # SUCCESS (green)
            fold_after=3000
        )

        # Check if user wants to hide help notification
        settings = QSettings("VisionTracker", "App")
        if not settings.value("hide_help_notification", False, type=bool):
            self._sendHelpNotification()

    def _sendHelpNotification(self):
        """Send help notification with a button to navigate to Help page."""
        sidebar = self.LayerRightMessageSidebar()

        # Create custom message box
        msg_box = SiSideMessageBox(sidebar)
        msg_box.setMessageType(1)  # SUCCESS (green)
        msg_box.setFixedWidth(sidebar.width() - 20)

        container = msg_box.content().container()
        container.setSpacing(0)

        # Title label
        title_label = SiLabel(sidebar)
        title_label.setFixedWidth(380 - msg_box.content().theme_wing_width - 32)
        title_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        title_label.setWordWrap(True)
        title_label.setFont(SiFont.tokenized(GlobalFont.S_BOLD))
        title_label.setFixedStyleSheet(
            "padding-top: 16px;"
            "padding-bottom: 1px;"
            "padding-left: 12px;"
            "padding-right: 12px;"
            f"color: {sidebar.getColor(SiColor.TEXT_B)}"
        )
        title_label.setText("Getting Started")

        # Description label
        desc_label = SiLabel(sidebar)
        desc_label.setFixedWidth(380 - msg_box.content().theme_wing_width - 32)
        desc_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        desc_label.setWordWrap(True)
        desc_label.setFont(SiFont.tokenized(GlobalFont.S_NORMAL))
        desc_label.setFixedStyleSheet(
            "padding-top: 1px;"
            "padding-bottom: 8px;"
            "padding-left: 12px;"
            "padding-right: 12px;"
            f"color: {sidebar.getColor(SiColor.TEXT_D)}"
        )
        desc_label.setText("Check out the Help page to learn more.")

        # Button row container (for checkbox and button)
        btn_row = SiLabel(sidebar)
        content_width = 380 - msg_box.content().theme_wing_width - 32
        btn_row.setFixedSize(content_width, 32)

        # "Don't show again" checkbox
        dont_show_checkbox = SiCheckBox(btn_row)
        dont_show_checkbox.setText("Don't show again")
        dont_show_checkbox.text_label.setStyleSheet("color: #FFFFFF")
        dont_show_checkbox.adjustSize()
        dont_show_checkbox.move(12, (32 - dont_show_checkbox.height()) // 2)

        # Save preference when checkbox is toggled
        def on_checkbox_toggled(checked):
            settings = QSettings("VisionTracker", "App")
            settings.setValue("hide_help_notification", checked)

        dont_show_checkbox.toggled.connect(on_checkbox_toggled)

        # Button to navigate to Help page
        help_btn = SiPushButton(btn_row)
        help_btn.setFixedSize(120, 32)
        help_btn.setText("View Help")
        help_btn.clicked.connect(lambda: self.layerMain().setPage(self.help_page_index))
        help_btn.clicked.connect(msg_box.closeLater)
        # Position button on the right side
        help_btn.move(content_width - 120 - 24, 0)

        container.addWidget(title_label)
        container.addWidget(desc_label)
        container.addPlaceholder(4)
        container.addWidget(btn_row)
        container.addPlaceholder(12)

        msg_box.setFoldAfter(8000)
        msg_box.adjustSize()
        sidebar.sendMessageBox(msg_box)

    def _onUsernameChanged(self, new_username: str):
        """Handle username change from user page."""
        self.home_page.setUsername(new_username)

    def _onUserButtonClicked(self):
        """Handle user button click in title bar."""
        # 切换到用户页面
        self.layerMain().page_view.stacked_container.setCurrentIndex(self.user_page_index)
        # 取消侧边栏所有按钮的选中状态
        for btn in self.layerMain().page_view.page_navigator.buttons:
            btn.setActive(False)
        # 更新标题栏页面名称
        self.layerMain().setPageName("User")

    def logout(self):
        """Logout current user."""
        self.session_manager.clear_session()
        self.current_user = None
        self.layerMain().page_view.page_navigator.buttons[self.admin_button_index].hide()
        self.layer_login.showLayer()

    def showEvent(self, event):
        """Handle window show event."""
        super().showEvent(event)
        # Set dark titlebar
        set_dark_titlebar(int(self.winId()))
        # Show login layer after window is visible
        if hasattr(self, '_need_login') and self._need_login:
            self._need_login = False
            QTimer.singleShot(100, self.layer_login.showLayer)
        # Show notifications for auto-login
        elif hasattr(self, '_auto_login_user') and self._auto_login_user:
            user = self._auto_login_user
            self._auto_login_user = None
            QTimer.singleShot(300, lambda: self._sendLoginNotifications(user))

    def resizeEvent(self, event):
        """Handle window resize."""
        super().resizeEvent(event)
        if hasattr(self, 'layer_login'):
            self.layer_login.resize(event.size())

    def closeEvent(self, event):
        """Handle window close event."""
        # Stop tracking system if running
        if hasattr(self, 'tracker_manager') and self.tracker_manager:
            self.tracker_manager.stop()
        super().closeEvent(event)
