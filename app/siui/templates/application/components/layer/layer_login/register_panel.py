"""Register panel component with email verification."""

import re
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QLineEdit, QGraphicsDropShadowEffect

from siui.components.widgets.abstracts.widget import SiWidget
from siui.components.widgets.label import SiLabel
from siui.components.button import SiPushButtonRefactor as SiPushButton, SiFlatButton
from siui.components.editbox import SiCapsuleLineEdit
from siui.gui import SiFont


class RegisterPanel(SiWidget):
    """Registration form panel with two-step verification."""

    register_success = pyqtSignal()
    switch_to_login = pyqtSignal()

    # Registration steps
    STEP_INFO = 0
    STEP_VERIFY = 1

    def __init__(self, parent=None):
        super().__init__(parent)

        self.db_manager = None
        self.email_service = None
        self.user_repo = None

        self.current_step = self.STEP_INFO
        self.pending_email = ""
        self.pending_username = ""
        self.pending_password = ""

        self.setFixedSize(400, 520)

        self._initUI()
        self._initConnections()
        self._initCountdownTimer()

    def _initUI(self):
        """Initialize UI components."""
        # Background panel
        self.background = SiLabel(self)
        self.background.setFixedSize(self.size())
        self.background.setStyleSheet("background-color: #2D2B32; border-radius: 16px;")

        # Add shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 100))
        shadow.setOffset(0, 10)
        self.background.setGraphicsEffect(shadow)

        # Title
        self.title_label = SiLabel(self)
        self.title_label.setFont(SiFont.getFont(size=28, weight=QFont.Bold))
        self.title_label.setText("Create Account")
        self.title_label.setTextColor("#FFFFFF")
        self.title_label.adjustSize()
        self.title_label.move((self.width() - self.title_label.width()) // 2, 35)

        # Step indicator
        self.step_label = SiLabel(self)
        self.step_label.setFont(SiFont.getFont(size=13))
        self.step_label.setText("Step 1 of 2: Account Information")
        self.step_label.setTextColor("#918497")
        self.step_label.adjustSize()
        self.step_label.move((self.width() - self.step_label.width()) // 2, 75)

        # === Step 1: Info Container ===
        self.info_container = SiWidget(self)
        self.info_container.setFixedSize(320, 280)
        self.info_container.move(40, 110)

        # Username input
        self.username_edit = SiCapsuleLineEdit(self.info_container, title="Username")
        self.username_edit.setFixedSize(320, 48)
        self.username_edit.move(0, 0)
        self.username_edit.setPlaceholderText("Choose a username")
        self.username_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.username_edit.style_data.text_indicator_color_editing = QColor("#00000000")

        # Email input
        self.email_edit = SiCapsuleLineEdit(self.info_container, title="Email")
        self.email_edit.setFixedSize(320, 48)
        self.email_edit.move(0, 65)
        self.email_edit.setPlaceholderText("Enter your email")
        self.email_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.email_edit.style_data.text_indicator_color_editing = QColor("#00000000")

        # Password input
        self.password_edit = SiCapsuleLineEdit(self.info_container, title="Password")
        self.password_edit.setFixedSize(320, 48)
        self.password_edit.move(0, 130)
        self.password_edit.setPlaceholderText("Create a password")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.password_edit.style_data.text_indicator_color_editing = QColor("#00000000")

        # Confirm password input
        self.confirm_edit = SiCapsuleLineEdit(self.info_container, title="Confirm Password")
        self.confirm_edit.setFixedSize(320, 48)
        self.confirm_edit.move(0, 195)
        self.confirm_edit.setPlaceholderText("Confirm your password")
        self.confirm_edit.setEchoMode(QLineEdit.Password)
        self.confirm_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.confirm_edit.style_data.text_indicator_color_editing = QColor("#00000000")

        # === Step 2: Verify Container ===
        self.verify_container = SiWidget(self)
        self.verify_container.setFixedSize(320, 200)
        self.verify_container.move(40, 110)
        self.verify_container.hide()

        # Email display
        self.email_display = SiLabel(self.verify_container)
        self.email_display.setFont(SiFont.getFont(size=14))
        self.email_display.setTextColor("#D1CBD4")
        self.email_display.setFixedWidth(320)
        self.email_display.move(0, 0)

        # Verification code input
        self.code_edit = SiCapsuleLineEdit(self.verify_container, title="Verification Code")
        self.code_edit.setFixedSize(320, 48)
        self.code_edit.move(0, 40)
        self.code_edit.setPlaceholderText("Enter 6-digit code")
        self.code_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.code_edit.style_data.text_indicator_color_editing = QColor("#00000000")

        # Resend code button
        self.resend_button = SiFlatButton(self.verify_container)
        self.resend_button.setFixedSize(150, 36)
        self.resend_button.move(0, 105)
        self.resend_button.setText("Resend Code")

        # Countdown label
        self.countdown_label = SiLabel(self.verify_container)
        self.countdown_label.setFont(SiFont.getFont(size=12))
        self.countdown_label.setTextColor("#918497")
        self.countdown_label.move(160, 115)
        self.countdown_label.hide()

        # === Common Elements ===
        # Error label
        self.error_label = SiLabel(self)
        self.error_label.setFont(SiFont.getFont(size=12))
        self.error_label.setTextColor("#FF6B6B")
        self.error_label.setFixedWidth(320)
        self.error_label.move(40, 400)
        self.error_label.hide()

        # Next/Submit button
        self.submit_button = SiPushButton(self)
        self.submit_button.setFixedSize(320, 44)
        self.submit_button.move(40, 430)
        self.submit_button.setText("Continue")
        self.submit_button.setFont(SiFont.getFont(size=15, weight=QFont.Bold))

        # Back button
        self.back_button = SiFlatButton(self)
        self.back_button.setFixedSize(100, 36)
        self.back_button.move(40, 480)
        self.back_button.setText("← Back")
        self.back_button.hide()

        # Login link
        self.login_link = SiLabel(self)
        self.login_link.setFont(SiFont.getFont(size=13))
        self.login_link.setText("Already have an account? <a href='#' style='color: #D087DF;'>Sign in</a>")
        self.login_link.setTextColor("#918497")
        self.login_link.adjustSize()
        self.login_link.move((self.width() - self.login_link.width()) // 2, 480)
        self.login_link.setCursor(Qt.PointingHandCursor)

    def _initConnections(self):
        """Initialize signal connections."""
        self.submit_button.clicked.connect(self._onSubmitClicked)
        self.back_button.clicked.connect(self._onBackClicked)
        self.resend_button.clicked.connect(self._sendVerificationCode)
        self.login_link.mousePressEvent = lambda e: self.switch_to_login.emit()

    def _initCountdownTimer(self):
        """Initialize countdown timer for resend button."""
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._updateCountdown)
        self.countdown_seconds = 0

    def setAuthServices(self, db_manager, email_service):
        """Set authentication services."""
        self.db_manager = db_manager
        self.email_service = email_service

        from auth.models import UserRepository
        self.user_repo = UserRepository(db_manager)

    def _onSubmitClicked(self):
        """Handle submit button click based on current step."""
        if self.current_step == self.STEP_INFO:
            self._validateAndProceed()
        else:
            self._verifyAndRegister()

    def _validateAndProceed(self):
        """Validate info step and proceed to verification."""
        username = self.username_edit.text().strip()
        email = self.email_edit.text().strip()
        password = self.password_edit.text()
        confirm = self.confirm_edit.text()

        # Validate username
        if not username or len(username) < 3:
            self._showError("Username must be at least 3 characters")
            return

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            self._showError("Username can only contain letters, numbers, and underscores")
            return

        # Validate email
        if not email or not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            self._showError("Please enter a valid email address")
            return

        # Validate password
        if not password or len(password) < 6:
            self._showError("Password must be at least 6 characters")
            return

        if password != confirm:
            self._showError("Passwords do not match")
            return

        # Check if username/email exists
        if self.user_repo:
            if self.user_repo.username_exists(username):
                self._showError("Username already taken")
                return
            if self.user_repo.email_exists(email):
                self._showError("Email already registered")
                return

        # Store pending registration data
        self.pending_username = username
        self.pending_email = email
        self.pending_password = password

        # Send verification code
        self._sendVerificationCode()

        # Move to step 2
        self._goToStep(self.STEP_VERIFY)

    def _sendVerificationCode(self):
        """Send verification code to email."""
        if not self.email_service:
            self._showError("Email service not available")
            return

        success, result = self.email_service.send_verification_code(self.pending_email, "register")
        if success:
            self._hideError()
            self._startCountdown()
        else:
            self._showError(f"Failed to send code: {result}")

    def _verifyAndRegister(self):
        """Verify code and complete registration."""
        code = self.code_edit.text().strip()

        if not code or len(code) != 6:
            self._showError("Please enter the 6-digit code")
            return

        # Verify code
        if not self.email_service.verify_code(self.pending_email, code, "register"):
            self._showError("Invalid or expired verification code")
            return

        # Create user
        if self.user_repo:
            user_id = self.user_repo.create_user(
                self.pending_username,
                self.pending_email,
                self.pending_password
            )
            if user_id:
                self.register_success.emit()
            else:
                self._showError("Failed to create account")
        else:
            self._showError("Database service not available")

    def _goToStep(self, step: int):
        """Switch to specified step."""
        self.current_step = step
        self._hideError()

        if step == self.STEP_INFO:
            self.info_container.show()
            self.verify_container.hide()
            self.step_label.setText("Step 1 of 2: Account Information")
            self.submit_button.setText("Continue")
            self.back_button.hide()
            self.login_link.show()
        else:
            self.info_container.hide()
            self.verify_container.show()
            self.step_label.setText("Step 2 of 2: Email Verification")
            self.email_display.setText(f"Code sent to: {self.pending_email}")
            self.email_display.adjustSize()
            self.submit_button.setText("Create Account")
            self.back_button.show()
            self.login_link.hide()

        self.step_label.adjustSize()
        self.step_label.move((self.width() - self.step_label.width()) // 2, 75)

    def _onBackClicked(self):
        """Go back to previous step."""
        self._goToStep(self.STEP_INFO)

    def _startCountdown(self):
        """Start resend countdown."""
        self.countdown_seconds = 60
        self.resend_button.setEnabled(False)
        self.countdown_label.show()
        self.countdown_timer.start(1000)
        self._updateCountdown()

    def _updateCountdown(self):
        """Update countdown display."""
        if self.countdown_seconds > 0:
            self.countdown_label.setText(f"({self.countdown_seconds}s)")
            self.countdown_label.adjustSize()
            self.countdown_seconds -= 1
        else:
            self.countdown_timer.stop()
            self.resend_button.setEnabled(True)
            self.countdown_label.hide()

    def _showError(self, message: str):
        """Show error message."""
        self.error_label.setText(message)
        self.error_label.adjustSize()
        self.error_label.show()

    def _hideError(self):
        """Hide error message."""
        self.error_label.hide()

    def reset(self):
        """Reset panel to initial state."""
        self.username_edit.clear()
        self.email_edit.clear()
        self.password_edit.clear()
        self.confirm_edit.clear()
        self.code_edit.clear()
        self.pending_username = ""
        self.pending_email = ""
        self.pending_password = ""
        self._goToStep(self.STEP_INFO)
        self._hideError()
        self.countdown_timer.stop()
