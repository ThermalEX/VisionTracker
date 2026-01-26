"""Vision Tracker - User Settings Page"""

import os
import re
import shutil
from pathlib import Path
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QFont, QColor, QPixmap, QImage, QPainter, QPainterPath
from PyQt5.QtWidgets import QFileDialog, QLineEdit, QWidget, QVBoxLayout, QGraphicsOpacityEffect

from siui.components import (
    SiDenseHContainer,
    SiDenseVContainer,
    SiLabel,
    SiOptionCardLinear,
    SiPixLabel,
    SiTitledWidgetGroup,
)
from siui.components.page import SiPage
from siui.components.button import SiPushButtonRefactor as SiPushButton, SiFlatButton, SiLongPressButtonRefactor as SiLongPressButton
from siui.components.editbox import SiCapsuleLineEdit
from siui.core import Si, SiColor, SiGlobal
from siui.gui import SiFont

# Path configuration
current_dir = Path(__file__).resolve().parent
app_dir = current_dir.parent.parent.parent
data_dir = app_dir / 'data'
avatars_dir = data_dir / 'avatars'


class RoundedDialog(QWidget):
    """Base class for rounded dialogs with fade animation."""

    closed = pyqtSignal()

    def __init__(self, parent, width, height):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Opacity effect for fade animation
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0)
        self.setGraphicsEffect(self._opacity_effect)

        # Fade animation
        self._fade_ani = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_ani.setDuration(150)
        self._fade_ani.setEasingCurve(QEasingCurve.OutCubic)

    def showWithAnimation(self):
        """Show dialog with fade in animation."""
        self.show()
        self._fade_ani.setStartValue(0)
        self._fade_ani.setEndValue(1)
        self._fade_ani.start()

    def closeWithAnimation(self):
        """Close dialog with fade out animation."""
        self._fade_ani.setStartValue(1)
        self._fade_ani.setEndValue(0)
        self._fade_ani.finished.connect(self._onFadeOutFinished)
        self._fade_ani.start()

    def _onFadeOutFinished(self):
        self._fade_ani.finished.disconnect(self._onFadeOutFinished)
        self.closed.emit()
        self.close()

    def paintEvent(self, event):
        """Draw rounded rectangle background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 16, 16)
        painter.fillPath(path, QColor("#2D2B32"))


class ChangeUsernameDialog(RoundedDialog):
    """Change username dialog."""

    confirmed = pyqtSignal(str)  # Emits new username

    def __init__(self, parent, current_username: str):
        super().__init__(parent, 420, 280)
        self.current_username = current_username
        self.user_repo = None
        self.user_id = None

        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Title
        self.title = SiLabel(self)
        self.title.setFont(SiFont.getFont(size=20, weight=QFont.Bold))
        self.title.setText("Change Username")
        self.title.setTextColor("#FFFFFF")
        layout.addWidget(self.title)

        # Current username
        self.current_label = SiLabel(self)
        self.current_label.setFont(SiFont.getFont(size=13))
        self.current_label.setText(f"Current: {self.current_username}")
        self.current_label.setTextColor("#918497")
        layout.addWidget(self.current_label)

        # New username input
        self.username_edit = SiCapsuleLineEdit(self, title="New")
        self.username_edit.setFixedSize(356, 48)
        self.username_edit.setPlaceholderText("Enter new username")
        self.username_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.username_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        layout.addWidget(self.username_edit)

        # Error label
        self.error_label = SiLabel(self)
        self.error_label.setFont(SiFont.getFont(size=12))
        self.error_label.setTextColor("#FF6B6B")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Buttons
        btn_container = SiDenseHContainer(self)
        btn_container.setSpacing(12)

        self.cancel_btn = SiFlatButton(self)
        self.cancel_btn.setText("Cancel")
        self.cancel_btn.setFixedSize(100, 40)
        self.cancel_btn.clicked.connect(self.closeWithAnimation)

        self.confirm_btn = SiPushButton(self)
        self.confirm_btn.setText("Confirm")
        self.confirm_btn.setFixedSize(100, 40)
        self.confirm_btn.clicked.connect(self._onConfirm)

        btn_container.addWidget(self.cancel_btn)
        btn_container.addWidget(self.confirm_btn)
        layout.addWidget(btn_container, alignment=Qt.AlignRight)

    def setAuthServices(self, user_repo, user_id):
        self.user_repo = user_repo
        self.user_id = user_id

    def _onConfirm(self):
        new_username = self.username_edit.text().strip()

        if not new_username or len(new_username) < 3:
            self._showError("Username must be at least 3 characters")
            return

        if not re.match(r'^[a-zA-Z0-9_]+$', new_username):
            self._showError("Only letters, numbers, and underscores allowed")
            return

        if new_username == self.current_username:
            self._showError("New username is same as current")
            return

        if self.user_repo and self.user_repo.username_exists(new_username):
            self._showError("Username already taken")
            return

        if self.user_repo and self.user_repo.update_username(self.user_id, new_username):
            self.confirmed.emit(new_username)
            self.closeWithAnimation()
        else:
            self._showError("Failed to update username")

    def _showError(self, msg):
        self.error_label.setText(msg)
        self.error_label.adjustSize()
        self.error_label.show()


class ChangePasswordDialog(RoundedDialog):
    """Change password dialog."""

    confirmed = pyqtSignal()

    def __init__(self, parent):
        super().__init__(parent, 420, 340)
        self.user_repo = None
        self.user_id = None

        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        # Title
        self.title = SiLabel(self)
        self.title.setFont(SiFont.getFont(size=20, weight=QFont.Bold))
        self.title.setText("Change Password")
        self.title.setTextColor("#FFFFFF")
        layout.addWidget(self.title)

        # Current password
        self.old_password_edit = SiCapsuleLineEdit(self, title="Current")
        self.old_password_edit.setFixedSize(356, 48)
        self.old_password_edit.setPlaceholderText("Current password")
        self.old_password_edit.setEchoMode(QLineEdit.Password)
        self.old_password_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.old_password_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        layout.addWidget(self.old_password_edit)

        # New password
        self.new_password_edit = SiCapsuleLineEdit(self, title="New")
        self.new_password_edit.setFixedSize(356, 48)
        self.new_password_edit.setPlaceholderText("New password")
        self.new_password_edit.setEchoMode(QLineEdit.Password)
        self.new_password_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.new_password_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        layout.addWidget(self.new_password_edit)

        # Confirm password
        self.confirm_password_edit = SiCapsuleLineEdit(self, title="Confirm")
        self.confirm_password_edit.setFixedSize(356, 48)
        self.confirm_password_edit.setPlaceholderText("Confirm new password")
        self.confirm_password_edit.setEchoMode(QLineEdit.Password)
        self.confirm_password_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.confirm_password_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        layout.addWidget(self.confirm_password_edit)

        # Error label
        self.error_label = SiLabel(self)
        self.error_label.setFont(SiFont.getFont(size=12))
        self.error_label.setTextColor("#FF6B6B")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Buttons
        btn_container = SiDenseHContainer(self)
        btn_container.setSpacing(12)

        self.cancel_btn = SiFlatButton(self)
        self.cancel_btn.setText("Cancel")
        self.cancel_btn.setFixedSize(100, 40)
        self.cancel_btn.clicked.connect(self.closeWithAnimation)

        self.confirm_btn = SiPushButton(self)
        self.confirm_btn.setText("Confirm")
        self.confirm_btn.setFixedSize(100, 40)
        self.confirm_btn.clicked.connect(self._onConfirm)

        btn_container.addWidget(self.cancel_btn)
        btn_container.addWidget(self.confirm_btn)
        layout.addWidget(btn_container, alignment=Qt.AlignRight)

    def setAuthServices(self, user_repo, user_id):
        self.user_repo = user_repo
        self.user_id = user_id

    def _onConfirm(self):
        old_pwd = self.old_password_edit.text()
        new_pwd = self.new_password_edit.text()
        confirm_pwd = self.confirm_password_edit.text()

        if not self.user_repo.verify_password(self.user_id, old_pwd):
            self._showError("Current password is incorrect")
            return

        if len(new_pwd) < 6:
            self._showError("Password must be at least 6 characters")
            return

        if new_pwd != confirm_pwd:
            self._showError("Passwords do not match")
            return

        if self.user_repo.update_password(self.user_id, new_pwd):
            self.confirmed.emit()
            self.closeWithAnimation()
        else:
            self._showError("Failed to update password")

    def _showError(self, msg):
        self.error_label.setText(msg)
        self.error_label.adjustSize()
        self.error_label.show()


class ChangeEmailDialog(RoundedDialog):
    """Change email dialog with verification."""

    confirmed = pyqtSignal(str)  # Emits new email

    STEP_INPUT = 0
    STEP_VERIFY = 1

    def __init__(self, parent, current_email: str):
        super().__init__(parent, 420, 320)
        self.current_email = current_email
        self.user_repo = None
        self.email_service = None
        self.user_id = None
        self.pending_email = ""
        self.current_step = self.STEP_INPUT

        self._initUI()
        self._initCountdownTimer()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        # Title
        self.title = SiLabel(self)
        self.title.setFont(SiFont.getFont(size=20, weight=QFont.Bold))
        self.title.setText("Change Email")
        self.title.setTextColor("#FFFFFF")
        layout.addWidget(self.title)

        # Current email
        self.current_label = SiLabel(self)
        self.current_label.setFont(SiFont.getFont(size=13))
        self.current_label.setText(f"Current: {self.current_email}")
        self.current_label.setTextColor("#918497")
        layout.addWidget(self.current_label)

        # New email input
        self.email_edit = SiCapsuleLineEdit(self, title="New")
        self.email_edit.setFixedSize(356, 48)
        self.email_edit.setPlaceholderText("Enter new email address")
        self.email_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.email_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        layout.addWidget(self.email_edit)

        # Verification code input
        self.code_edit = SiCapsuleLineEdit(self, title="Code")
        self.code_edit.setFixedSize(356, 48)
        self.code_edit.setPlaceholderText("Enter 6-digit code")
        self.code_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.code_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        self.code_edit.hide()
        layout.addWidget(self.code_edit)

        # Resend container
        self.resend_container = SiDenseHContainer(self)
        self.resend_btn = SiFlatButton(self)
        self.resend_btn.setText("Resend Code")
        self.resend_btn.setFixedSize(120, 32)
        self.resend_btn.clicked.connect(self._sendCode)
        self.countdown_label = SiLabel(self)
        self.countdown_label.setFont(SiFont.getFont(size=12))
        self.countdown_label.setTextColor("#918497")
        self.resend_container.addWidget(self.resend_btn)
        self.resend_container.addWidget(self.countdown_label)
        self.resend_container.hide()
        layout.addWidget(self.resend_container)

        # Error label
        self.error_label = SiLabel(self)
        self.error_label.setFont(SiFont.getFont(size=12))
        self.error_label.setTextColor("#FF6B6B")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        # Buttons
        btn_container = SiDenseHContainer(self)
        btn_container.setSpacing(12)

        self.cancel_btn = SiFlatButton(self)
        self.cancel_btn.setText("Cancel")
        self.cancel_btn.setFixedSize(100, 40)
        self.cancel_btn.clicked.connect(self.closeWithAnimation)

        self.action_btn = SiPushButton(self)
        self.action_btn.setText("Send Code")
        self.action_btn.setFixedSize(120, 40)
        self.action_btn.clicked.connect(self._onAction)

        btn_container.addWidget(self.cancel_btn)
        btn_container.addWidget(self.action_btn)
        layout.addWidget(btn_container, alignment=Qt.AlignRight)

    def _initCountdownTimer(self):
        self.countdown_timer = QTimer(self)
        self.countdown_timer.timeout.connect(self._updateCountdown)
        self.countdown_seconds = 0

    def setAuthServices(self, user_repo, email_service, user_id):
        self.user_repo = user_repo
        self.email_service = email_service
        self.user_id = user_id

    def _onAction(self):
        if self.current_step == self.STEP_INPUT:
            self._validateAndSendCode()
        else:
            self._verifyAndUpdate()

    def _validateAndSendCode(self):
        email = self.email_edit.text().strip()

        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            self._showError("Please enter a valid email address")
            return

        if email == self.current_email:
            self._showError("New email is same as current")
            return

        if self.user_repo and self.user_repo.email_exists(email):
            self._showError("Email already registered")
            return

        self.pending_email = email
        self._sendCode()
        self._goToStep(self.STEP_VERIFY)

    def _sendCode(self):
        if not self.email_service:
            self._showError("Email service not available")
            return

        success, result = self.email_service.send_verification_code(
            self.pending_email, "change_email"
        )
        if success:
            self._startCountdown()
            self._hideError()
        else:
            self._showError(f"Failed to send code: {result}")

    def _verifyAndUpdate(self):
        code = self.code_edit.text().strip()

        if len(code) != 6:
            self._showError("Please enter the 6-digit code")
            return

        if not self.email_service.verify_code(self.pending_email, code, "change_email"):
            self._showError("Invalid or expired verification code")
            return

        if self.user_repo.update_email(self.user_id, self.pending_email):
            self.confirmed.emit(self.pending_email)
            self.closeWithAnimation()
        else:
            self._showError("Failed to update email")

    def _goToStep(self, step):
        self.current_step = step
        if step == self.STEP_VERIFY:
            self.email_edit.setEnabled(False)
            self.code_edit.show()
            self.resend_container.show()
            self.action_btn.setText("Verify")

    def _startCountdown(self):
        self.countdown_seconds = 60
        self.resend_btn.setEnabled(False)
        self.countdown_timer.start(1000)

    def _updateCountdown(self):
        if self.countdown_seconds > 0:
            self.countdown_label.setText(f"({self.countdown_seconds}s)")
            self.countdown_label.adjustSize()
            self.countdown_seconds -= 1
        else:
            self.countdown_timer.stop()
            self.resend_btn.setEnabled(True)
            self.countdown_label.setText("")

    def _showError(self, msg):
        self.error_label.setText(msg)
        self.error_label.adjustSize()
        self.error_label.show()

    def _hideError(self):
        self.error_label.hide()


class UserPage(SiPage):
    """User settings page."""

    logout_requested = pyqtSignal()
    username_changed = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.current_user = None
        self.db_manager = None
        self.user_repo = None
        self.session_manager = None
        self.email_service = None
        self._overlay = None  # Dialog overlay
        self._current_dialog = None  # Current open dialog

        self.setPadding(64)
        self.setScrollMaximumWidth(900)
        self.setTitle("User Settings")

        self._initUI()

    def _initUI(self):
        """Initialize UI components."""
        self.titled_widget_group = SiTitledWidgetGroup(self)
        self.titled_widget_group.setSiliconWidgetFlag(Si.EnableAnimationSignals)

        # Profile Section
        self._initProfileSection()

        # Account Settings Section
        self._initAccountSection()

        # Security Section
        self._initSecuritySection()

        self.titled_widget_group.addPlaceholder(64)
        self.setAttachment(self.titled_widget_group)

    def _initProfileSection(self):
        """Initialize profile section."""
        with self.titled_widget_group as group:
            group.addTitle("Profile")

            # Profile card using SiOptionCardLinear as base
            self.profile_card = SiLabel(self)
            self.profile_card.setFixedHeight(120)
            self.profile_card.setStyleSheet(
                "background-color: #2D2932; border-radius: 8px;"
            )

            # Left: Avatar - clickable (manually positioned)
            self.avatar_container = SiLabel(self.profile_card)
            self.avatar_container.setFixedSize(80, 80)
            self.avatar_container.setCursor(Qt.PointingHandCursor)
            self.avatar_container.setStyleSheet(
                "background-color: #D087DF; border-radius: 40px;"
            )
            self.avatar_container.mousePressEvent = lambda e: self._onChangeAvatar()

            self.avatar_label = SiPixLabel(self.avatar_container)
            self.avatar_label.setFixedSize(80, 80)
            self.avatar_label.setBorderRadius(40)
            self.avatar_label.setCursor(Qt.PointingHandCursor)
            self.avatar_label.setHint("Click to change avatar")
            self.avatar_label.mousePressEvent = lambda e: self._onChangeAvatar()

            # Middle: User info
            self.username_display = SiLabel(self.profile_card)
            self.username_display.setFont(SiFont.getFont(size=18, weight=QFont.Bold))
            self.username_display.setTextColor("#FFFFFF")
            self.username_display.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
            self.username_display.setText("Username")

            self.email_display = SiLabel(self.profile_card)
            self.email_display.setFont(SiFont.getFont(size=13))
            self.email_display.setTextColor("#918497")
            self.email_display.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
            self.email_display.setText("user@email.com")

            # Right: Change avatar button
            self.change_avatar_btn = SiPushButton(self.profile_card)
            self.change_avatar_btn.setText("Change Avatar")
            self.change_avatar_btn.setFixedSize(130, 36)
            self.change_avatar_btn.clicked.connect(self._onChangeAvatar)

            group.addWidget(self.profile_card)

            # Initial layout after a short delay
            QTimer.singleShot(100, self._layoutProfileCard)

    def _layoutProfileCard(self):
        """Layout profile card elements."""
        if not hasattr(self, 'profile_card'):
            return
        card_width = self.profile_card.width()
        card_height = self.profile_card.height()

        # Retry if card width is not ready yet
        if card_width < 200:
            QTimer.singleShot(50, self._layoutProfileCard)
            return

        # Avatar: left side, vertically centered
        avatar_x = 20
        avatar_y = (card_height - 80) // 2
        self.avatar_container.move(avatar_x, avatar_y)

        # Username and email: next to avatar
        info_x = avatar_x + 80 + 20
        self.username_display.move(info_x, card_height // 2 - 28)
        self.username_display.adjustSize()
        self.email_display.move(info_x, card_height // 2 + 4)
        self.email_display.adjustSize()

        # Button: right side, vertically centered
        btn_x = card_width - 130 - 20
        btn_y = (card_height - 36) // 2
        self.change_avatar_btn.move(btn_x, btn_y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layoutProfileCard()

    def _initAccountSection(self):
        """Initialize account settings section."""
        with self.titled_widget_group as group:
            group.addTitle("Account Settings")

            # Change username card
            self.card_username = SiOptionCardLinear(self)
            self.card_username.setTitle("Change Username", "Update your display name")
            self.card_username.load(SiGlobal.siui.iconpack.get("ic_fluent_person_regular"))

            self.btn_change_username = SiPushButton(self)
            self.btn_change_username.setText("Change")
            self.btn_change_username.setFixedSize(90, 32)
            self.btn_change_username.clicked.connect(self._showChangeUsernameDialog)
            self.card_username.addWidget(self.btn_change_username)

            # Change password card
            self.card_password = SiOptionCardLinear(self)
            self.card_password.setTitle("Change Password", "Update your account password")
            self.card_password.load(SiGlobal.siui.iconpack.get("ic_fluent_key_regular"))

            self.btn_change_password = SiPushButton(self)
            self.btn_change_password.setText("Change")
            self.btn_change_password.setFixedSize(90, 32)
            self.btn_change_password.clicked.connect(self._showChangePasswordDialog)
            self.card_password.addWidget(self.btn_change_password)

            # Change email card
            self.card_email = SiOptionCardLinear(self)
            self.card_email.setTitle("Change Email", "Update your email address")
            self.card_email.load(SiGlobal.siui.iconpack.get("ic_fluent_mail_regular"))

            self.btn_change_email = SiPushButton(self)
            self.btn_change_email.setText("Change")
            self.btn_change_email.setFixedSize(90, 32)
            self.btn_change_email.clicked.connect(self._showChangeEmailDialog)
            self.card_email.addWidget(self.btn_change_email)

            group.addWidget(self.card_username)
            group.addWidget(self.card_password)
            group.addWidget(self.card_email)

    def _initSecuritySection(self):
        """Initialize security section."""
        with self.titled_widget_group as group:
            group.addTitle("Security")

            # Logout button container
            logout_container = SiDenseHContainer(self)
            logout_container.setAlignment(Qt.AlignCenter)
            logout_container.setFixedHeight(60)

            self.logout_button = SiLongPressButton(self)
            self.logout_button.setText("Hold to Logout")
            self.logout_button.setFixedSize(200, 44)
            self.logout_button.longPressed.connect(self._onLogout)
            # Red color style
            self.logout_button.style_data.button_color = QColor("#C54043")
            self.logout_button.style_data.progress_color = QColor("#8B2D2F")
            self.logout_button.update()

            logout_container.addWidget(self.logout_button)
            group.addWidget(logout_container)

    def setAuthServices(self, db_manager, session_manager, email_service):
        """Set authentication services."""
        self.db_manager = db_manager
        self.session_manager = session_manager
        self.email_service = email_service

        from auth.models import UserRepository
        self.user_repo = UserRepository(db_manager)

    def setUser(self, user):
        """Set current user and update display."""
        self.current_user = user
        self._updateDisplay()

    def _updateDisplay(self):
        """Update user info display."""
        if not self.current_user:
            return

        self.username_display.setText(self.current_user.username)
        self.email_display.setText(self.current_user.email)
        self._loadAvatar()

    def _loadAvatar(self):
        """Load user avatar."""
        # Ensure avatars directory exists
        avatars_dir.mkdir(parents=True, exist_ok=True)

        if self.current_user and self.current_user.avatar_path:
            avatar_path = avatars_dir / self.current_user.avatar_path
            if avatar_path.exists():
                self.avatar_label.load(str(avatar_path))
                return

        # Load default avatar or create placeholder
        default_avatar = avatars_dir / 'default.png'
        if default_avatar.exists():
            self.avatar_label.load(str(default_avatar))
        else:
            # Create a simple colored circle as default
            self._createDefaultAvatar()

    def _createDefaultAvatar(self):
        """Create a default avatar placeholder."""
        # Just set a colored background
        self.avatar_container.setStyleSheet(
            "background-color: #D087DF; border-radius: 40px;"
        )

    def _onChangeAvatar(self):
        """Handle change avatar button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Avatar",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )

        if file_path:
            self._saveAvatar(file_path)

    def _saveAvatar(self, source_path: str):
        """Save avatar image."""
        if not self.current_user:
            return

        try:
            # Ensure avatars directory exists
            avatars_dir.mkdir(parents=True, exist_ok=True)

            # Load and resize image
            image = QImage(source_path)
            if image.isNull():
                return

            # Scale to 128x128
            scaled = image.scaled(128, 128, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)

            # Crop to center if needed
            if scaled.width() > 128 or scaled.height() > 128:
                x = (scaled.width() - 128) // 2
                y = (scaled.height() - 128) // 2
                scaled = scaled.copy(x, y, 128, 128)

            # Save to avatars directory
            avatar_filename = f"user_{self.current_user.id}.png"
            avatar_path = avatars_dir / avatar_filename
            scaled.save(str(avatar_path), "PNG")

            # Update database
            if self.user_repo:
                self.user_repo.update_avatar(self.current_user.id, avatar_filename)
                self.current_user.avatar_path = avatar_filename

            # Reload avatar display
            self.avatar_label.load(str(avatar_path))

        except Exception as e:
            print(f"Error saving avatar: {e}")

    def _showOverlay(self):
        """Show dark overlay behind dialog with fade animation."""
        main_window = self.window()
        if not self._overlay:
            self._overlay = SiLabel(main_window)
            self._overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);")
            # Add opacity effect for animation
            self._overlay_effect = QGraphicsOpacityEffect(self._overlay)
            self._overlay.setGraphicsEffect(self._overlay_effect)
            self._overlay_ani = QPropertyAnimation(self._overlay_effect, b"opacity")
            self._overlay_ani.setDuration(150)
            self._overlay_ani.setEasingCurve(QEasingCurve.OutCubic)

        self._overlay.resize(main_window.size())
        self._overlay.raise_()
        self._overlay.show()
        self._overlay_effect.setOpacity(0)
        self._overlay_ani.setStartValue(0)
        self._overlay_ani.setEndValue(1)
        self._overlay_ani.start()

    def _hideOverlay(self):
        """Hide dark overlay with fade animation."""
        if self._overlay and hasattr(self, '_overlay_ani'):
            self._overlay_ani.setStartValue(1)
            self._overlay_ani.setEndValue(0)
            self._overlay_ani.finished.connect(self._onOverlayFadeOut)
            self._overlay_ani.start()

    def _onOverlayFadeOut(self):
        """Handle overlay fade out finished."""
        if hasattr(self, '_overlay_ani'):
            try:
                self._overlay_ani.finished.disconnect(self._onOverlayFadeOut)
            except:
                pass
        if self._overlay:
            self._overlay.hide()

    def _onDialogClosed(self):
        """Handle dialog close event."""
        self._hideOverlay()
        self._current_dialog = None

    def _showChangeUsernameDialog(self):
        """Show change username dialog."""
        if not self.current_user:
            return

        self._showOverlay()

        dialog = ChangeUsernameDialog(self.window(), self.current_user.username)
        dialog.setAuthServices(self.user_repo, self.current_user.id)
        dialog.confirmed.connect(self._onUsernameChanged)
        dialog.closed.connect(self._onDialogClosed)
        self._current_dialog = dialog

        # Center dialog in window
        main_window = self.window()
        x = (main_window.width() - dialog.width()) // 2
        y = (main_window.height() - dialog.height()) // 2
        dialog.move(x, y)
        dialog.raise_()
        dialog.showWithAnimation()

    def _onUsernameChanged(self, new_username: str):
        """Handle username change."""
        if self.current_user:
            self.current_user.username = new_username
            self.username_display.setText(new_username)
            self.username_changed.emit(new_username)

    def _showChangePasswordDialog(self):
        """Show change password dialog."""
        if not self.current_user:
            return

        self._showOverlay()

        dialog = ChangePasswordDialog(self.window())
        dialog.setAuthServices(self.user_repo, self.current_user.id)
        dialog.closed.connect(self._onDialogClosed)
        self._current_dialog = dialog

        # Center dialog in window
        main_window = self.window()
        x = (main_window.width() - dialog.width()) // 2
        y = (main_window.height() - dialog.height()) // 2
        dialog.move(x, y)
        dialog.raise_()
        dialog.showWithAnimation()

    def _showChangeEmailDialog(self):
        """Show change email dialog."""
        if not self.current_user:
            return

        self._showOverlay()

        dialog = ChangeEmailDialog(self.window(), self.current_user.email)
        dialog.setAuthServices(self.user_repo, self.email_service, self.current_user.id)
        dialog.confirmed.connect(self._onEmailChanged)
        dialog.closed.connect(self._onDialogClosed)
        self._current_dialog = dialog

        # Center dialog in window
        main_window = self.window()
        x = (main_window.width() - dialog.width()) // 2
        y = (main_window.height() - dialog.height()) // 2
        dialog.move(x, y)
        dialog.raise_()
        dialog.showWithAnimation()

    def _onEmailChanged(self, new_email: str):
        """Handle email change."""
        if self.current_user:
            self.current_user.email = new_email
            self.email_display.setText(new_email)

    def _onLogout(self):
        """Handle logout button click."""
        self.logout_requested.emit()
