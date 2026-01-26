"""Login panel component."""

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QLineEdit, QGraphicsDropShadowEffect

from siui.components.widgets.abstracts.widget import SiWidget
from siui.components.widgets.label import SiLabel
from siui.components.widgets.button import SiCheckBox
from siui.components.button import SiPushButtonRefactor as SiPushButton
from siui.components.editbox import SiCapsuleLineEdit
from siui.gui import SiFont


class LoginPanel(SiWidget):
    """Login form panel."""

    login_success = pyqtSignal(object)  # Emits User object
    switch_to_register = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.db_manager = None
        self.session_manager = None
        self.user_repo = None

        self.setFixedSize(400, 420)

        self._initUI()
        self._initStyle()
        self._initConnections()

    def _initUI(self):
        """Initialize UI components."""
        # Background panel
        self.background = SiLabel(self)
        self.background.setFixedSize(self.size())
        self.background.setStyleSheet("background-color: #2D2B32; border-radius: 16px;")

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 10)
        self.background.setGraphicsEffect(shadow)

        # Title
        self.title_label = SiLabel(self)
        self.title_label.setFont(SiFont.getFont(size=28, weight=QFont.Bold))
        self.title_label.setText("Welcome Back")
        self.title_label.setTextColor("#FFFFFF")
        self.title_label.adjustSize()
        self.title_label.move((self.width() - self.title_label.width()) // 2, 40)

        # Subtitle
        self.subtitle_label = SiLabel(self)
        self.subtitle_label.setFont(SiFont.getFont(size=13))
        self.subtitle_label.setText("Sign in to continue")
        self.subtitle_label.setTextColor("#918497")
        self.subtitle_label.adjustSize()
        self.subtitle_label.move((self.width() - self.subtitle_label.width()) // 2, 80)

        # Username input
        self.username_edit = SiCapsuleLineEdit(self, title="Username")
        self.username_edit.setFixedSize(320, 48)
        self.username_edit.move(40, 130)
        self.username_edit.setPlaceholderText("Enter username or email")
        self.username_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.username_edit.style_data.text_indicator_color_editing = QColor("#00000000")

        # Password input
        self.password_edit = SiCapsuleLineEdit(self, title="Password")
        self.password_edit.setFixedSize(320, 48)
        self.password_edit.move(40, 195)
        self.password_edit.setPlaceholderText("Enter password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.password_edit.style_data.text_indicator_color_editing = QColor("#00000000")

        # Remember me checkbox
        self.remember_checkbox = SiCheckBox(self)
        self.remember_checkbox.setText("Keep me logged in")
        self.remember_checkbox.adjustSize()
        self.remember_checkbox.move(40, 255)

        # Error message label
        self.error_label = SiLabel(self)
        self.error_label.setFont(SiFont.getFont(size=12))
        self.error_label.setTextColor("#FF6B6B")
        self.error_label.setFixedWidth(320)
        self.error_label.move(40, 285)
        self.error_label.hide()

        # Login button
        self.login_button = SiPushButton(self)
        self.login_button.setFixedSize(320, 44)
        self.login_button.move(40, 315)
        self.login_button.setText("Sign In")
        self.login_button.setFont(SiFont.getFont(size=15, weight=QFont.Bold))

        # Register link
        self.register_link = SiLabel(self)
        self.register_link.setFont(SiFont.getFont(size=13))
        self.register_link.setText("Don't have an account? <a href='#' style='color: #D087DF;'>Sign up</a>")
        self.register_link.setTextColor("#918497")
        self.register_link.adjustSize()
        self.register_link.move((self.width() - self.register_link.width()) // 2, 375)
        self.register_link.setCursor(Qt.PointingHandCursor)

    def _initStyle(self):
        """Initialize styles."""
        pass

    def _initConnections(self):
        """Initialize signal connections."""
        self.login_button.clicked.connect(self._onLoginClicked)
        self.register_link.mousePressEvent = lambda e: self.switch_to_register.emit()
        self.password_edit.returnPressed.connect(self._onLoginClicked)

    def setAuthServices(self, db_manager, session_manager):
        """Set authentication services."""
        self.db_manager = db_manager
        self.session_manager = session_manager

        from auth.models import UserRepository
        self.user_repo = UserRepository(db_manager)

    def _onLoginClicked(self):
        """Handle login button click."""
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        # Validate input
        if not username:
            self._showError("Please enter username or email")
            return
        if not password:
            self._showError("Please enter password")
            return

        if not self.user_repo:
            self._showError("Authentication service not available")
            return

        # Verify credentials
        user = self.user_repo.verify_login(username, password)
        if user:
            # Create session
            remember = self.remember_checkbox.isChecked()
            self.session_manager.create_session(user.id, remember)
            self.login_success.emit(user)
        else:
            self._showError("Invalid username or password")

    def _showError(self, message: str):
        """Show error message."""
        self.error_label.setText(message)
        self.error_label.adjustSize()
        self.error_label.show()

    def _hideError(self):
        """Hide error message."""
        self.error_label.hide()

    def clearInputs(self):
        """Clear all input fields."""
        self.username_edit.clear()
        self.password_edit.clear()
        self.remember_checkbox.setChecked(False)
        self._hideError()
