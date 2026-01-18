"""Vision Tracker - Main Application UI"""

import os
import sys
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDesktopWidget

import siui
from siui.core import SiColor, SiGlobal
from siui.templates.application.application import SiliconApplication
from siui.templates.application.components.layer.layer_login import LayerLogin

from . import icons
from .components import HomePage, AboutPage, UserPage

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
        self.resize(1200, 800)
        self.move((screen_geo.width() - self.width()) // 2, (screen_geo.height() - self.height()) // 2)

        # Title
        self.layerMain().setTitle("Vision Tracker")
        self.setWindowTitle("Vision Tracker")

        # Set window icon if exists
        icon_path = os.path.join(current_dir, "..", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Add pages
        # Home page - top
        self.home_page = HomePage(self)
        self.layerMain().addPage(
            self.home_page,
            icon=SiGlobal.siui.iconpack.get("ic_fluent_home_filled"),
            hint="Home",
            side="top"
        )

        # User page - 添加到page_view但不在侧边栏显示按钮
        self.user_page = UserPage(self)
        self.layerMain().page_view.stacked_container.addWidget(self.user_page)
        self.user_page_index = self.layerMain().page_view.stacked_container.widgetsAmount() - 1

        # About page - bottom
        self.layerMain().addPage(
            AboutPage(self),
            icon=SiGlobal.siui.iconpack.get("ic_fluent_info_filled"),
            hint="About",
            side="bottom"
        )

        # 设置标题栏用户按钮图标并连接点击事件
        self.layerMain().setUserButtonIcon(SiGlobal.siui.iconpack.get("ic_fluent_person_filled"))
        self.layerMain().user_button_clicked.connect(self._onUserButtonClicked)

        # Set default page
        self.layerMain().setPage(0)

        # Initialize authentication system
        self._initAuth()

        # Reload stylesheets
        SiGlobal.siui.reloadAllWindowsStyleSheet()

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
        else:
            # Delay showing login layer until window is fully rendered
            self._need_login = True

    def _onLoginSuccess(self, user):
        """Handle successful login."""
        self.current_user = user
        self.home_page.setUsername(user.username)
        self.user_page.setUser(user)

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

    def logout(self):
        """Logout current user."""
        self.session_manager.clear_session()
        self.current_user = None
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

    def resizeEvent(self, event):
        """Handle window resize."""
        super().resizeEvent(event)
        if hasattr(self, 'layer_login'):
            self.layer_login.resize(event.size())
