"""Vision Tracker - Configuration Page"""

from PyQt5.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QFont
from PyQt5.QtWidgets import QWidget, QGraphicsOpacityEffect, QVBoxLayout

from siui.components import SiDenseHContainer, SiDenseVContainer, SiLabel, SiTitledWidgetGroup
from siui.components.page import SiPage
from siui.components.button import SiPushButtonRefactor as SiPushButton, SiLongPressButtonRefactor as SiLongPressButton
from siui.components.combobox.combobox import SiComboBox
from siui.components.editbox import SiCapsuleLineEdit
from siui.core import GlobalFont, Si, SiColor
from siui.gui import SiFont

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

class AddConfigDialog(RoundedDialog):
    """Dialog to add a new configuration."""
    
    confirmed = pyqtSignal(str)

    def __init__(self, parent):
        super().__init__(parent, 400, 200)
        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        # Title
        self.title = SiLabel(self)
        self.title.setFont(SiFont.getFont(size=20, weight=QFont.Bold))
        self.title.setText("New Configuration")
        self.title.setStyleSheet("color: #E0E0E0")
        layout.addWidget(self.title)

        # Edit box
        self.edit = SiCapsuleLineEdit(self, title="Config Name")
        self.edit.setFixedHeight(32)
        self.edit.setPlaceholderText("Enter config name")
        layout.addWidget(self.edit)

        # Buttons
        btn_container = SiDenseHContainer(self)
        btn_container.setFixedHeight(32)
        
        self.btn_cancel = SiPushButton(self)
        self.btn_cancel.setText("Cancel")
        self.btn_cancel.setFixedSize(80, 32)
        self.btn_cancel.clicked.connect(self.closeWithAnimation)
        
        self.btn_confirm = SiPushButton(self)
        self.btn_confirm.setText("Create")
        self.btn_confirm.setFixedSize(80, 32)
        self.btn_confirm.clicked.connect(self._onConfirm)
        
        # Add to right side (First added is rightmost)
        btn_container.addWidget(self.btn_confirm, side="right")
        btn_container.addWidget(self.btn_cancel, side="right")
        layout.addWidget(btn_container)

    def _onConfirm(self):
        text = self.edit.text().strip()
        if text:
            self.confirmed.emit(text)
            self.closeWithAnimation()

class ConfigPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setPadding(64)
        self.setTitle("Configuration")
        
        self._overlay = None

        # Main container
        self.main_container = SiDenseVContainer(self)
        self.main_container.setSpacing(16)

        # --- Top Bar ---
        self.top_bar = SiDenseHContainer(self)
        self.top_bar.setFixedHeight(40)
        self.top_bar.setSpacing(12)

        # Config Selector
        self.config_selector = SiComboBox(self)
        self.config_selector.resize(250, 32)
        # Placeholder items
        self.config_selector.menu().addOption("Default Config")
        self.config_selector.menu().addOption("CS:GO Config")
        self.top_bar.addWidget(self.config_selector, side="left")
        
        # Add some space between selector and buttons
        self.top_bar.addPlaceholder(24, side="left")

        # Action Buttons
        # Delete (Long Press)
        self.btn_delete = SiLongPressButton(self)
        self.btn_delete.setText("Hold to Delete")
        self.btn_delete.setFixedSize(120, 32)
        self.btn_delete.style_data.button_color = QColor("#C54043") # Reddish
        self.btn_delete.style_data.progress_color = QColor("#8B2D2F")
        self.top_bar.addWidget(self.btn_delete, side="right")

        # Save
        self.btn_save = SiPushButton(self)
        self.btn_save.setText("Save")
        self.btn_save.setFixedSize(80, 32)
        self.top_bar.addWidget(self.btn_save, side="right")

        # Add
        self.btn_add = SiPushButton(self)
        self.btn_add.setText("New")
        self.btn_add.setFixedSize(80, 32)
        self.btn_add.clicked.connect(self._showAddConfigDialog)
        self.top_bar.addWidget(self.btn_add, side="right")

        self.main_container.addWidget(self.top_bar)

        # --- Settings Area (Bottom) ---
        self.parameters_container = SiDenseVContainer(self)
        self.parameters_container.setSpacing(12)

        # Simple plain text title
        self.params_title = SiLabel(self)
        self.params_title.setFont(SiFont.getFont(size=18, weight=QFont.Bold))
        self.params_title.setText("Parameters")
        self.params_title.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_B)}")
        self.parameters_container.addWidget(self.params_title)
        
        # Example plain text parameters
        params = ["Aim Smoothness", "Detection FOV", "Sensitivity", "Target Priority"]
        for param_name in params:
            item_label = SiLabel(self)
            item_label.setFont(SiFont.getFont(size=14))
            item_label.setText(param_name)
            item_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
            self.parameters_container.addWidget(item_label)
        
        self.main_container.addWidget(self.parameters_container)
        
        self.setAttachment(self.main_container)

    def _showAddConfigDialog(self):
        """Show dialog to add new config."""
        self._showOverlay()
        
        # Store as instance variable to prevent garbage collection
        self.add_config_dialog = AddConfigDialog(self.window())
        
        # Center the dialog
        geo = self.window().geometry()
        self.add_config_dialog.move(
            geo.width() // 2 - self.add_config_dialog.width() // 2,
            geo.height() // 2 - self.add_config_dialog.height() // 2
        )
        
        self.add_config_dialog.confirmed.connect(self._onConfigAdded)
        self.add_config_dialog.closed.connect(self._hideOverlay)
        self.add_config_dialog.showWithAnimation()

    def _onConfigAdded(self, name):
        """Handle new config added."""
        self.config_selector.menu().addOption(name)
        # Select the new option (logic needed to find index)
        # For now just print
        print(f"Added config: {name}")

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
