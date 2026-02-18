"""Vision Tracker - Admin Page with User Management"""

import re
from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer, QRectF
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QLinearGradient
from PyQt5.QtWidgets import QWidget, QGraphicsOpacityEffect, QVBoxLayout, QLineEdit

from siui.components import (
    SiDenseHContainer,
    SiDenseVContainer,
    SiLabel,
    SiOptionCardLinear,
    SiTitledWidgetGroup,
)
from siui.components.page import SiPage
from siui.components.button import SiFlatButton, SiPushButtonRefactor
from siui.components.container import SiTriSectionFlatCard
from siui.components.widgets.button import SiSwitch
from siui.components.widgets.table import SiTableView
from siui.components.widgets.abstracts.table import ABCSiTabelManager, SiRow
from siui.core import GlobalFont, Si, SiColor, SiGlobal
from siui.gui import SiFont


class FlatLongPressButton(SiFlatButton):
    """Flat button with long press functionality and gradient animation."""
    longPressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._is_pressing = False
        self._is_long_press = False

        self.mouse_pressed_timer = QTimer(self)
        self.mouse_pressed_timer.setInterval(1000 // 60)
        self.mouse_pressed_timer.timeout.connect(self._onMousePressed)

        self.go_backwards_timer = QTimer(self)
        self.go_backwards_timer.setSingleShot(True)
        self.go_backwards_timer.setInterval(500)
        self.go_backwards_timer.timeout.connect(self._goBackwards)

    def _stepLength(self):
        return (1 - self._progress) / 16 + 0.001

    def _isAlive(self):
        try:
            self.objectName()
            return True
        except RuntimeError:
            return False

    def _onMousePressed(self):
        self._progress = min(self._progress + self._stepLength(), 1.0)
        self.update()
        if self._progress >= 1.0:
            self.mouse_pressed_timer.stop()
            self.go_backwards_timer.stop()
            self._is_long_press = True
            self.longPressed.emit()
            QTimer.singleShot(200, lambda: self._goBackwards(0) if self._isAlive() else None)

    def _goBackwards(self, delay=0):
        if not self._isAlive():
            return
        if delay > 0:
            QTimer.singleShot(delay, lambda: self._resetProgress() if self._isAlive() else None)
        else:
            self._resetProgress()

    def _resetProgress(self):
        if not self._isAlive():
            return
        reset_timer = QTimer(self)
        reset_timer.setInterval(16)

        def animate_reset():
            if not self._isAlive():
                reset_timer.stop()
                return
            self._progress = max(0, self._progress - 0.1)
            self.update()
            if self._progress <= 0:
                reset_timer.stop()
                reset_timer.deleteLater()

        reset_timer.timeout.connect(animate_reset)
        reset_timer.start()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._is_pressing = True
            self._is_long_press = False
            self.mouse_pressed_timer.start()
            self.go_backwards_timer.stop()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._is_pressing = False
        self.mouse_pressed_timer.stop()
        if self._is_long_press:
            self._is_long_press = False
            event.accept()
            return
        else:
            if self._progress > 0 and self._progress < 1:
                self.go_backwards_timer.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        if self._progress > 0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            rect = self.rect().adjusted(1, 1, -1, -1)
            gradient = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
            progress_color = QColor(180, 30, 30)
            base_color = QColor(45, 43, 50)
            gradient.setColorAt(max(0, self._progress - 0.0001), progress_color)
            gradient.setColorAt(self._progress, base_color)
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            path = QPainterPath()
            path.addRoundedRect(QRectF(rect), 4, 4)
            painter.drawPath(path)
            painter.setPen(QColor(100, 72, 96))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            painter.end()
        super().paintEvent(event)


class RoundedDialog(QWidget):
    """Base class for rounded dialogs with fade animation."""
    closed = pyqtSignal()

    def __init__(self, parent, width, height):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0)
        self.setGraphicsEffect(self._opacity_effect)
        self._fade_ani = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_ani.setDuration(150)
        self._fade_ani.setEasingCurve(QEasingCurve.OutCubic)

    def showWithAnimation(self):
        self.show()
        self._fade_ani.setStartValue(0)
        self._fade_ani.setEndValue(1)
        self._fade_ani.start()

    def closeWithAnimation(self):
        self._fade_ani.setStartValue(1)
        self._fade_ani.setEndValue(0)
        self._fade_ani.finished.connect(self._onFadeOutFinished)
        self._fade_ani.start()

    def _onFadeOutFinished(self):
        self._fade_ani.finished.disconnect(self._onFadeOutFinished)
        self.closed.emit()
        self.close()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), 16, 16)
        painter.fillPath(path, QColor("#2D2B32"))


INPUT_STYLE = """
    QLineEdit {
        background-color: #201d23;
        border: 1px solid #3a3540;
        border-radius: 6px;
        color: #D1CBD4;
        padding: 0 12px;
        font-family: "Segoe UI", "Microsoft YaHei";
        font-size: 14px;
    }
    QLineEdit:focus { border: 1px solid #D087DF; }
"""


class EditUserDialog(RoundedDialog):
    """Dialog to edit user fields."""
    confirmed = pyqtSignal(dict)

    def __init__(self, parent, user):
        super().__init__(parent, 440, 420)
        self.user = user
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = SiLabel(self)
        title.setFont(SiFont.getFont(size=18, weight=QFont.Bold))
        title.setText(f"Edit User #{self.user.id}")
        title.setStyleSheet("color: #E0E0E0")
        layout.addWidget(title)

        label_user = SiLabel(self)
        label_user.setFont(SiFont.getFont(size=13))
        label_user.setText("Username")
        label_user.setStyleSheet("color: #918497")
        layout.addWidget(label_user)

        self.edit_username = QLineEdit(self)
        self.edit_username.setFixedHeight(36)
        self.edit_username.setText(self.user.username)
        self.edit_username.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.edit_username)

        label_email = SiLabel(self)
        label_email.setFont(SiFont.getFont(size=13))
        label_email.setText("Email")
        label_email.setStyleSheet("color: #918497")
        layout.addWidget(label_email)

        self.edit_email = QLineEdit(self)
        self.edit_email.setFixedHeight(36)
        self.edit_email.setText(self.user.email)
        self.edit_email.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.edit_email)

        label_pwd = SiLabel(self)
        label_pwd.setFont(SiFont.getFont(size=13))
        label_pwd.setText("New Password (leave empty to keep current)")
        label_pwd.setStyleSheet("color: #918497")
        layout.addWidget(label_pwd)

        self.edit_password = QLineEdit(self)
        self.edit_password.setFixedHeight(36)
        self.edit_password.setPlaceholderText("Enter new password")
        self.edit_password.setEchoMode(QLineEdit.Password)
        self.edit_password.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.edit_password)

        verified_container = SiDenseHContainer(self)
        verified_container.setFixedHeight(36)

        verified_label = SiLabel(self)
        verified_label.setFont(SiFont.getFont(size=13))
        verified_label.setText("Verified")
        verified_label.setStyleSheet("color: #918497")

        self.verified_switch = SiSwitch(self)
        self.verified_switch.setChecked(self.user.is_verified)
        self.verified_switch.reloadStyleSheet()

        verified_container.addWidget(verified_label, side="left")
        verified_container.addWidget(self.verified_switch, side="right")
        layout.addWidget(verified_container)

        self.error_label = SiLabel(self)
        self.error_label.setFont(SiFont.getFont(size=12))
        self.error_label.setStyleSheet("color: #FF6B6B")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        btn_container = SiDenseHContainer(self)
        btn_container.setFixedHeight(32)

        self.btn_cancel = SiPushButtonRefactor(self)
        self.btn_cancel.setText("Cancel")
        self.btn_cancel.setFixedSize(80, 32)
        self.btn_cancel.clicked.connect(self.closeWithAnimation)

        self.btn_save = SiPushButtonRefactor(self)
        self.btn_save.setText("Save")
        self.btn_save.setFixedSize(80, 32)
        self.btn_save.clicked.connect(self._onSave)

        btn_container.addWidget(self.btn_save, side="right")
        btn_container.addWidget(self.btn_cancel, side="right")
        layout.addWidget(btn_container)

    def _onSave(self):
        username = self.edit_username.text().strip()
        email = self.edit_email.text().strip()
        password = self.edit_password.text()

        if not username or len(username) < 3:
            self._showError("Username must be at least 3 characters")
            return

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            self._showError("Username: only letters, numbers, underscores")
            return

        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            self._showError("Please enter a valid email address")
            return

        if password and len(password) < 6:
            self._showError("Password must be at least 6 characters")
            return

        result = {
            "username": username,
            "email": email,
            "is_verified": self.verified_switch.isChecked(),
        }
        if password:
            result["password"] = password

        self.confirmed.emit(result)
        self.closeWithAnimation()

    def _showError(self, msg):
        self.error_label.setText(msg)
        self.error_label.adjustSize()
        self.error_label.show()


class AddUserDialog(RoundedDialog):
    """Dialog to add a new user."""
    confirmed = pyqtSignal(str, str, str)

    def __init__(self, parent):
        super().__init__(parent, 440, 380)
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(12)

        title = SiLabel(self)
        title.setFont(SiFont.getFont(size=18, weight=QFont.Bold))
        title.setText("Add New User")
        title.setStyleSheet("color: #E0E0E0")
        layout.addWidget(title)

        label_user = SiLabel(self)
        label_user.setFont(SiFont.getFont(size=13))
        label_user.setText("Username")
        label_user.setStyleSheet("color: #918497")
        layout.addWidget(label_user)

        self.edit_username = QLineEdit(self)
        self.edit_username.setFixedHeight(36)
        self.edit_username.setPlaceholderText("Enter username")
        self.edit_username.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.edit_username)

        label_email = SiLabel(self)
        label_email.setFont(SiFont.getFont(size=13))
        label_email.setText("Email")
        label_email.setStyleSheet("color: #918497")
        layout.addWidget(label_email)

        self.edit_email = QLineEdit(self)
        self.edit_email.setFixedHeight(36)
        self.edit_email.setPlaceholderText("Enter email")
        self.edit_email.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.edit_email)

        label_pwd = SiLabel(self)
        label_pwd.setFont(SiFont.getFont(size=13))
        label_pwd.setText("Password")
        label_pwd.setStyleSheet("color: #918497")
        layout.addWidget(label_pwd)

        self.edit_password = QLineEdit(self)
        self.edit_password.setFixedHeight(36)
        self.edit_password.setPlaceholderText("Enter password")
        self.edit_password.setEchoMode(QLineEdit.Password)
        self.edit_password.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.edit_password)

        label_confirm = SiLabel(self)
        label_confirm.setFont(SiFont.getFont(size=13))
        label_confirm.setText("Confirm Password")
        label_confirm.setStyleSheet("color: #918497")
        layout.addWidget(label_confirm)

        self.edit_confirm = QLineEdit(self)
        self.edit_confirm.setFixedHeight(36)
        self.edit_confirm.setPlaceholderText("Confirm password")
        self.edit_confirm.setEchoMode(QLineEdit.Password)
        self.edit_confirm.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.edit_confirm)

        self.error_label = SiLabel(self)
        self.error_label.setFont(SiFont.getFont(size=12))
        self.error_label.setStyleSheet("color: #FF6B6B")
        self.error_label.hide()
        layout.addWidget(self.error_label)

        btn_container = SiDenseHContainer(self)
        btn_container.setFixedHeight(32)

        self.btn_cancel = SiPushButtonRefactor(self)
        self.btn_cancel.setText("Cancel")
        self.btn_cancel.setFixedSize(80, 32)
        self.btn_cancel.clicked.connect(self.closeWithAnimation)

        self.btn_create = SiPushButtonRefactor(self)
        self.btn_create.setText("Create")
        self.btn_create.setFixedSize(80, 32)
        self.btn_create.clicked.connect(self._onCreate)

        btn_container.addWidget(self.btn_create, side="right")
        btn_container.addWidget(self.btn_cancel, side="right")
        layout.addWidget(btn_container)

    def _onCreate(self):
        username = self.edit_username.text().strip()
        email = self.edit_email.text().strip()
        password = self.edit_password.text()
        confirm = self.edit_confirm.text()

        if not username or len(username) < 3:
            self._showError("Username must be at least 3 characters")
            return

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            self._showError("Username: only letters, numbers, underscores")
            return

        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            self._showError("Please enter a valid email address")
            return

        if len(password) < 6:
            self._showError("Password must be at least 6 characters")
            return

        if password != confirm:
            self._showError("Passwords do not match")
            return

        self.confirmed.emit(username, email, password)
        self.closeWithAnimation()

    def _showError(self, msg):
        self.error_label.setText(msg)
        self.error_label.adjustSize()
        self.error_label.show()


# ── Table Manager ─────────────────────────────────────────────────

class UserTableManager(ABCSiTabelManager):
    """Manager for user table with styled columns and action buttons."""

    def __init__(self, parent):
        super().__init__(parent)
        self.users = []
        self.admin_page = None
        self.select_mode = False
        self.selected_ids = set()
        # Column indices are set dynamically based on select_mode
        self._update_columns()

    def _update_columns(self):
        if self.select_mode:
            self.COL_CHECK = 0
            self.COL_NUM = 1
            self.COL_ID = 2
            self.COL_USERNAME = 3
            self.COL_EMAIL = 4
            self.COL_VERIFIED = 5
            self.COL_CREATED = 6
            self.COL_LAST_LOGIN = 7
            self.COL_EDIT = 8
            self.COL_DELETE = 9
        else:
            self.COL_CHECK = -1
            self.COL_NUM = 0
            self.COL_ID = 1
            self.COL_USERNAME = 2
            self.COL_EMAIL = 3
            self.COL_VERIFIED = 4
            self.COL_CREATED = 5
            self.COL_LAST_LOGIN = 6
            self.COL_EDIT = 7
            self.COL_DELETE = 8

    def _value_read_parser(self, row_index, col_index):
        if col_index == self.COL_CHECK:
            return ""
        if col_index <= self.COL_LAST_LOGIN:
            return self.parent().getRowWidget(row_index)[col_index].text()
        return ""

    def _value_write_parser(self, row_index, col_index, value):
        widget = self.parent().getRowWidget(row_index)[col_index]

        if col_index == self.COL_CHECK:
            user = self.users[row_index]
            is_selected = user.id in self.selected_ids
            if user.id == 1:
                widget.hide()
            else:
                self._setCheckIcon(widget, is_selected)
                widget.clicked.connect(
                    lambda checked=False, uid=user.id, w=widget: self._onCheckClicked(uid, w)
                )

        elif col_index == self.COL_NUM:
            widget.setTextColor(self.parent().getColor(SiColor.TEXT_E))
            widget.setText(value)

        elif col_index == self.COL_ID:
            widget.setFont(SiFont.tokenized(GlobalFont.S_BOLD))
            widget.setTextColor(self.parent().getColor(SiColor.TEXT_D))
            widget.setText(value)

        elif col_index == self.COL_USERNAME:
            widget.setTextColor(self.parent().getColor(SiColor.TEXT_THEME))
            widget.setText(value)

        elif col_index == self.COL_EMAIL:
            widget.setTextColor(self.parent().getColor(SiColor.TEXT_B))
            widget.setText(value)

        elif col_index == self.COL_VERIFIED:
            if value == "Yes":
                widget.setTextColor("#B2D844")
            else:
                widget.setTextColor("#FF6B6B")
            widget.setText(value)

        elif col_index in (self.COL_CREATED, self.COL_LAST_LOGIN):
            widget.setTextColor(self.parent().getColor(SiColor.TEXT_D))
            widget.setText(value)

        elif col_index == self.COL_EDIT:
            user = self.users[row_index]
            page = self.admin_page
            widget.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_edit_filled"))
            widget.clicked.connect(
                lambda checked=False, u=user: QTimer.singleShot(0, lambda: page._showEditUserDialog(u))
            )

        elif col_index == self.COL_DELETE:
            user = self.users[row_index]
            page = self.admin_page
            if user.id == 1:
                widget.hide()
            else:
                widget.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_delete_filled"))
                widget.longPressed.connect(
                    lambda u=user: QTimer.singleShot(0, lambda: page._onDeleteUser(u))
                )

    def _setCheckIcon(self, widget, selected):
        if selected:
            widget.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_checkmark_circle_filled"))
        else:
            widget.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_circle_regular"))

    def _onCheckClicked(self, user_id, widget):
        if user_id in self.selected_ids:
            self.selected_ids.discard(user_id)
            self._setCheckIcon(widget, False)
        else:
            self.selected_ids.add(user_id)
            self._setCheckIcon(widget, True)
        if self.admin_page:
            self.admin_page._updateDeleteSelectedBtn()

    def _widget_creator(self, col_index):
        if col_index == self.COL_CHECK:
            btn = SiFlatButton(self.parent())
            btn.setFixedSize(28, 28)
            return btn
        if col_index <= self.COL_LAST_LOGIN:
            label = SiLabel(self.parent())
            label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
            return label
        if col_index == self.COL_EDIT:
            btn = SiFlatButton(self.parent())
            btn.setFixedSize(28, 28)
            return btn
        if col_index == self.COL_DELETE:
            btn = FlatLongPressButton(self.parent())
            btn.setFixedSize(28, 28)
            return btn

    def on_header_created(self, header: SiRow):
        for name in self.parent().column_names:
            new_label = SiLabel(self.parent())
            new_label.setFont(SiFont.tokenized(GlobalFont.S_BOLD))
            new_label.setTextColor(self.parent().getColor(SiColor.TEXT_D))
            new_label.setText(name)
            new_label.adjustSize()
            header.container().addWidget(new_label)
        header.container().arrangeWidgets()


# ── Table Host (resize propagation wrapper) ───────────────────────

class _TableHost(SiLabel):
    """Wraps SiTableView and propagates width changes to it."""

    def __init__(self, parent):
        super().__init__(parent)
        self.table = None

    def setTable(self, table):
        if self.table:
            old = self.table
            self.table = None
            old.hide()
            old.setParent(None)
            old.deleteLater()
        self.table = table
        table.setParent(self)
        table.resize(self.width(), self.height())
        table.reloadStyleSheet()
        table.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.table:
            self.table.resize(event.size().width(), event.size().height())


# ── Admin Page ────────────────────────────────────────────────────

class AdminPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Admin Panel")

        self._overlay = None
        self._current_dialog = None
        self.user_repo = None
        self._users = []
        self._filtered_users = []
        self._search_text = ""
        self._current_page = 0
        self._page_size = 10
        self._select_mode = False
        self._selected_ids = set()

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._applySearch)

        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        self._createStatsSection()
        self._createUserManagementSection()
        self._createDangerZone()

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)

    def setAuthServices(self, db_manager):
        """Set database manager and initialize user repository."""
        from auth.models import UserRepository
        self.user_repo = UserRepository(db_manager)
        QTimer.singleShot(200, self._refreshUsers)

    # ── Stats Section ──────────────────────────────────────────────

    def _createStatsSection(self):
        self.titled_group.addTitle("System Statistics")

        self.stats_card = SiTriSectionFlatCard(self)
        self.stats_card.setTitle("Overview")

        stats_container = SiDenseHContainer(self)
        stats_container.setSpacing(32)
        stats_container.setFixedHeight(60)

        self.total_users_label = self._createStatWidget(stats_container, "Total Users", "0")
        self.verified_users_label = self._createStatWidget(stats_container, "Verified", "0")
        self.unverified_users_label = self._createStatWidget(stats_container, "Unverified", "0")

        self.stats_card.body().addWidget(stats_container)
        self.stats_card.adjustSize()
        self.titled_group.addWidget(self.stats_card)

    def _createStatWidget(self, parent_container, title, value):
        container = SiDenseVContainer(self)
        container.setFixedSize(120, 60)

        value_label = SiLabel(self)
        value_label.setFont(SiFont.getFont(size=24, weight=QFont.Bold))
        value_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_A)}")
        value_label.setText(value)
        value_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)

        title_label = SiLabel(self)
        title_label.setFont(SiFont.getFont(size=12))
        title_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        title_label.setText(title)
        title_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)

        container.addWidget(value_label)
        container.addWidget(title_label)
        parent_container.addWidget(container, side="left")

        return value_label

    # ── User Management Section ────────────────────────────────────

    def _createUserManagementSection(self):
        self.titled_group.addTitle("User Management")

        # Top bar: action buttons
        top_bar = SiDenseHContainer(self)
        top_bar.setFixedHeight(40)
        top_bar.setSpacing(4)

        self.btn_refresh = SiFlatButton(self)
        self.btn_refresh.setFixedSize(32, 32)
        self.btn_refresh.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_arrow_sync_circle_filled"))
        self.btn_refresh.setToolTip("Refresh user list")
        self.btn_refresh.clicked.connect(self._refreshUsers)
        top_bar.addWidget(self.btn_refresh, side="left")

        self.btn_reset_ids = SiFlatButton(self)
        self.btn_reset_ids.setFixedSize(32, 32)
        self.btn_reset_ids.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_layer_diagonal_person_filled"))
        self.btn_reset_ids.setToolTip("Reset user IDs to sequential")
        self.btn_reset_ids.clicked.connect(self._onResetIds)
        top_bar.addWidget(self.btn_reset_ids, side="left")

        self.btn_add_user = SiFlatButton(self)
        self.btn_add_user.setFixedSize(32, 32)
        self.btn_add_user.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_person_add_filled"))
        self.btn_add_user.setToolTip("Add new user")
        self.btn_add_user.clicked.connect(self._showAddUserDialog)
        top_bar.addWidget(self.btn_add_user, side="right")

        self.titled_group.addWidget(top_bar)

        # Search bar
        search_bar = SiDenseHContainer(self)
        search_bar.setFixedHeight(36)
        search_bar.setSpacing(8)

        self.search_input = QLineEdit(self)
        self.search_input.setFixedHeight(32)
        self.search_input.setPlaceholderText("Search by username or email...")
        self.search_input.setStyleSheet(INPUT_STYLE)
        self.search_input.textChanged.connect(self._onSearchChanged)
        search_bar.addWidget(self.search_input, side="left")

        self.btn_select_mode = SiFlatButton(self)
        self.btn_select_mode.setFixedSize(32, 32)
        self.btn_select_mode.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_multiselect_ltr_filled"))
        self.btn_select_mode.setToolTip("Toggle selection mode")
        self.btn_select_mode.clicked.connect(self._toggleSelectMode)
        search_bar.addWidget(self.btn_select_mode, side="right")

        self.btn_delete_selected = FlatLongPressButton(self)
        self.btn_delete_selected.setFixedSize(32, 32)
        self.btn_delete_selected.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_delete_filled"))
        self.btn_delete_selected.setToolTip("Delete selected users (long press)")
        self.btn_delete_selected.longPressed.connect(self._onDeleteSelected)
        self.btn_delete_selected.hide()
        search_bar.addWidget(self.btn_delete_selected, side="right")

        self.titled_group.addWidget(search_bar)

        # Table host
        self.table_host = _TableHost(self)
        self.table_host.setFixedHeight(360)
        self.titled_group.addWidget(self.table_host)

        # Pagination bar
        page_bar = SiDenseHContainer(self)
        page_bar.setFixedHeight(36)
        page_bar.setSpacing(8)

        self.total_label = SiLabel(self)
        self.total_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.total_label.setFont(SiFont.getFont(size=12))
        self.total_label.setTextColor(self.getColor(SiColor.TEXT_E))
        self.total_label.setText("")
        page_bar.addWidget(self.total_label, side="left")

        self.btn_next_page = SiFlatButton(self)
        self.btn_next_page.setFixedSize(32, 32)
        self.btn_next_page.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_chevron_right_filled"))
        self.btn_next_page.setToolTip("Next page")
        self.btn_next_page.clicked.connect(self._onNextPage)
        page_bar.addWidget(self.btn_next_page, side="right")

        self.page_label = SiLabel(self)
        self.page_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.page_label.setFont(SiFont.getFont(size=12))
        self.page_label.setTextColor(self.getColor(SiColor.TEXT_D))
        self.page_label.setFixedHeight(32)
        self.page_label.setText("Page 1 / 1")
        page_bar.addWidget(self.page_label, side="right")

        self.btn_prev_page = SiFlatButton(self)
        self.btn_prev_page.setFixedSize(32, 32)
        self.btn_prev_page.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_chevron_left_filled"))
        self.btn_prev_page.setToolTip("Previous page")
        self.btn_prev_page.clicked.connect(self._onPrevPage)
        page_bar.addWidget(self.btn_prev_page, side="right")

        self.titled_group.addWidget(page_bar)

    def _buildTable(self, users, start_idx=0):
        """Create a new SiTableView populated with user data."""
        table = SiTableView(self)
        table.resize(self.table_host.width(), self.table_host.height())

        manager = UserTableManager(table)
        manager.users = users
        manager.admin_page = self
        manager.select_mode = self._select_mode
        manager.selected_ids = self._selected_ids
        manager._update_columns()
        table.setManager(manager)

        if self._select_mode:
            table.addColumn("", 44, 40, Qt.AlignHCenter | Qt.AlignVCenter)

        table.addColumn("#", 30, 40, Qt.AlignRight | Qt.AlignVCenter)
        table.addColumn("ID", 40, 40, Qt.AlignRight | Qt.AlignVCenter)
        table.addColumn("Username", 130, 40, Qt.AlignLeft | Qt.AlignVCenter)
        table.addColumn("Email", 200, 40, Qt.AlignLeft | Qt.AlignVCenter)
        table.addColumn("Verified", 70, 40, Qt.AlignLeft | Qt.AlignVCenter)
        table.addColumn("Created", 120, 40, Qt.AlignLeft | Qt.AlignVCenter)
        table.addColumn("Last Login", 130, 40, Qt.AlignLeft | Qt.AlignVCenter)
        table.addColumn("", 36, 40, Qt.AlignHCenter | Qt.AlignVCenter)
        table.addColumn("", 36, 40, Qt.AlignHCenter | Qt.AlignVCenter)

        for idx, user in enumerate(users, start=start_idx + 1):
            created = user.created_at.strftime("%Y-%m-%d") if user.created_at else "N/A"
            last_login = user.last_login.strftime("%m-%d %H:%M") if user.last_login else "Never"
            verified = "Yes" if user.is_verified else "No"

            row_data = []
            if self._select_mode:
                row_data.append("")  # checkbox
            row_data.extend([
                str(idx),
                str(user.id),
                user.username,
                user.email,
                verified,
                created,
                last_login,
                "",  # edit button
                "",  # delete button
            ])
            table.addRow(data=row_data)

        return table

    # ── Danger Zone ────────────────────────────────────────────────

    def _createDangerZone(self):
        self.titled_group.addTitle("Danger Zone")

        self.danger_card = SiOptionCardLinear(self)
        self.danger_card.setTitle(
            "Delete All Non-Admin Users",
            "This will permanently delete all users except the admin account (long press)"
        )
        self.danger_card.load(SiGlobal.siui.iconpack.get("ic_fluent_warning_filled"))

        self.btn_delete_all = FlatLongPressButton(self)
        self.btn_delete_all.setFixedSize(32, 32)
        self.btn_delete_all.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_delete_filled"))
        self.btn_delete_all.setToolTip("Delete all non-admin users (long press)")
        self.btn_delete_all.longPressed.connect(self._onDeleteAllUsers)
        self.danger_card.addWidget(self.btn_delete_all)

        self.titled_group.addWidget(self.danger_card)

    # ── Data Operations ────────────────────────────────────────────

    def _filterUsers(self):
        """Apply search filter to user list."""
        query = self._search_text.lower().strip()
        if not query:
            self._filtered_users = list(self._users)
        else:
            self._filtered_users = [
                u for u in self._users
                if query in u.username.lower() or query in u.email.lower()
                   or query in str(u.id)
            ]

    def _getPageUsers(self):
        """Get users for the current page."""
        start = self._current_page * self._page_size
        end = start + self._page_size
        return self._filtered_users[start:end]

    def _totalPages(self):
        """Total number of pages."""
        total = len(self._filtered_users)
        return max(1, (total + self._page_size - 1) // self._page_size)

    def _updatePagination(self):
        """Update pagination label and button states."""
        total_pages = self._totalPages()
        self._current_page = max(0, min(self._current_page, total_pages - 1))
        self.page_label.setText(f"Page {self._current_page + 1} / {total_pages}")
        total = len(self._filtered_users)
        showing = len(self._getPageUsers())
        self.total_label.setText(f"Showing {showing} of {total} users")

    def _rebuildTable(self):
        """Rebuild table with current filter and page."""
        page_users = self._getPageUsers()
        start_idx = self._current_page * self._page_size

        table = self._buildTable(page_users, start_idx)
        self.table_host.setTable(table)

        row_height = 48 + len(page_users) * 40 + 10
        self.table_host.setFixedHeight(max(120, min(row_height, 500)))

        self._updatePagination()
        self.titled_group.adjustSize()
        self.titled_group.arrangeWidget()

    def _refreshUsers(self):
        """Reload user list from database."""
        if not self.user_repo:
            return

        self._users = self.user_repo.get_all_users()

        # Update stats
        total = len(self._users)
        verified = sum(1 for u in self._users if u.is_verified)
        self.total_users_label.setText(str(total))
        self.verified_users_label.setText(str(verified))
        self.unverified_users_label.setText(str(total - verified))

        self._filterUsers()
        self._rebuildTable()

    # ── Search & Pagination & Batch ──────────────────────────────

    def _onSearchChanged(self, text):
        """Handle search input change with debounce."""
        self._search_text = text
        self._search_timer.start()

    def _onPrevPage(self):
        if self._current_page > 0:
            self._current_page -= 1
            self._rebuildTable()

    def _onNextPage(self):
        if self._current_page < self._totalPages() - 1:
            self._current_page += 1
            self._rebuildTable()

    def _applySearch(self):
        """Apply search after debounce delay."""
        self._current_page = 0
        self._filterUsers()
        self._rebuildTable()

    def _toggleSelectMode(self):
        """Toggle selection mode on/off."""
        self._select_mode = not self._select_mode
        if not self._select_mode:
            self._selected_ids.clear()
            self.btn_delete_selected.hide()
        else:
            self.btn_delete_selected.show()
            self._updateDeleteSelectedBtn()
        self._rebuildTable()

    def _updateDeleteSelectedBtn(self):
        """Update delete button tooltip with count."""
        count = len(self._selected_ids)
        self.btn_delete_selected.setToolTip(f"Delete {count} selected user(s) (long press)")

    def _onDeleteSelected(self):
        """Delete all selected users."""
        if not self.user_repo or not self._selected_ids:
            self._showNotification("Info", "No users selected.", 2)
            return

        count = 0
        for uid in list(self._selected_ids):
            if uid == 1:
                continue
            if self.user_repo.delete_user(uid):
                count += 1

        self._selected_ids.clear()
        self._showNotification("Deleted", f"Deleted {count} user(s).", 1)
        QTimer.singleShot(50, self._refreshUsers)

    def _onDeleteUser(self, user):
        """Delete a single user."""
        if user.id == 1:
            self._showNotification("Protected", "Cannot delete the admin account.", 2)
            return

        if self.user_repo.delete_user(user.id):
            self._showNotification("Deleted", f"User '{user.username}' has been deleted.", 1)
            QTimer.singleShot(50, self._refreshUsers)
        else:
            self._showNotification("Error", f"Failed to delete user '{user.username}'.", 3)

    def _onDeleteAllUsers(self):
        """Delete all non-admin users."""
        if not self.user_repo:
            return

        users = self.user_repo.get_all_users()
        deleted = 0
        for user in users:
            if user.id != 1:
                if self.user_repo.delete_user(user.id):
                    deleted += 1

        self._showNotification("Deleted", f"Deleted {deleted} user(s).", 1)
        QTimer.singleShot(50, self._refreshUsers)

    def _onResetIds(self):
        """Reset all user IDs to sequential numbers."""
        if not self.user_repo:
            return

        if self.user_repo.reset_user_ids():
            self._showNotification("Reset", "User IDs have been reset to sequential.", 1)
            QTimer.singleShot(50, self._refreshUsers)
        else:
            self._showNotification("Error", "Failed to reset user IDs.", 3)

    # ── Edit User Dialog ───────────────────────────────────────────

    def _showEditUserDialog(self, user):
        self._showOverlay()

        dialog = EditUserDialog(self.window(), user)
        dialog.confirmed.connect(lambda fields: self._onEditUserConfirmed(user, fields))
        dialog.closed.connect(self._onDialogClosed)
        self._current_dialog = dialog

        main_window = self.window()
        x = (main_window.width() - dialog.width()) // 2
        y = (main_window.height() - dialog.height()) // 2
        dialog.move(x, y)
        dialog.raise_()
        dialog.showWithAnimation()

    def _onEditUserConfirmed(self, user, fields):
        if not self.user_repo:
            return

        errors = []

        new_username = fields.get("username", user.username)
        if new_username != user.username:
            if self.user_repo.username_exists(new_username):
                errors.append("Username already taken")
            elif not self.user_repo.update_username(user.id, new_username):
                errors.append("Failed to update username")

        new_email = fields.get("email", user.email)
        if new_email != user.email:
            if self.user_repo.email_exists(new_email):
                errors.append("Email already registered")
            elif not self.user_repo.update_email(user.id, new_email):
                errors.append("Failed to update email")

        new_password = fields.get("password")
        if new_password:
            if not self.user_repo.update_password(user.id, new_password):
                errors.append("Failed to update password")

        new_verified = fields.get("is_verified", user.is_verified)
        if new_verified != user.is_verified:
            if not self.user_repo.update_verification_status(user.id, new_verified):
                errors.append("Failed to update verification status")

        if errors:
            self._showNotification("Warning", "; ".join(errors), 2)
        else:
            self._showNotification("Updated", f"User '{new_username}' updated successfully.", 1)

        QTimer.singleShot(50, self._refreshUsers)

    # ── Add User Dialog ────────────────────────────────────────────

    def _showAddUserDialog(self):
        self._showOverlay()

        dialog = AddUserDialog(self.window())
        dialog.confirmed.connect(self._onAddUserConfirmed)
        dialog.closed.connect(self._onDialogClosed)
        self._current_dialog = dialog

        main_window = self.window()
        x = (main_window.width() - dialog.width()) // 2
        y = (main_window.height() - dialog.height()) // 2
        dialog.move(x, y)
        dialog.raise_()
        dialog.showWithAnimation()

    def _onAddUserConfirmed(self, username, email, password):
        if not self.user_repo:
            return

        if self.user_repo.username_exists(username):
            self._showNotification("Error", "Username already exists.", 3)
            return

        if self.user_repo.email_exists(email):
            self._showNotification("Error", "Email already registered.", 3)
            return

        user_id = self.user_repo.create_user(username, email, password)
        if user_id:
            self._showNotification("Created", f"User '{username}' created (ID: {user_id}).", 1)
            QTimer.singleShot(50, self._refreshUsers)
        else:
            self._showNotification("Error", "Failed to create user.", 3)

    # ── Overlay & Dialog Helpers ───────────────────────────────────

    def _showOverlay(self):
        main_window = self.window()
        if not self._overlay:
            self._overlay = SiLabel(main_window)
            self._overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);")
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
        if self._overlay and hasattr(self, '_overlay_ani'):
            self._overlay_ani.setStartValue(1)
            self._overlay_ani.setEndValue(0)
            self._overlay_ani.finished.connect(self._onOverlayFadeOut)
            self._overlay_ani.start()

    def _onOverlayFadeOut(self):
        if hasattr(self, '_overlay_ani'):
            try:
                self._overlay_ani.finished.disconnect(self._onOverlayFadeOut)
            except Exception:
                pass
        if self._overlay:
            self._overlay.hide()

    def _onDialogClosed(self):
        self._hideOverlay()
        self._current_dialog = None

    def _showNotification(self, title, text, msg_type=1):
        try:
            app = self.window()
            if hasattr(app, 'LayerRightMessageSidebar'):
                app.LayerRightMessageSidebar().send(
                    title=title, text=text, msg_type=msg_type, fold_after=3000
                )
        except Exception:
            pass
