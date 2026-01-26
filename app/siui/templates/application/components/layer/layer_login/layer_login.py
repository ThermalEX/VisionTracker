"""Login layer with dark overlay."""

from PyQt5.QtCore import pyqtSignal

from siui.components.widgets.abstracts.widget import SiWidget
from siui.components.widgets.label import SiLabel
from siui.templates.application.components.layer.layer import SiLayer

from .login_panel import LoginPanel
from .register_panel import RegisterPanel


class LayerLogin(SiLayer):
    """Full-screen login layer with gaussian blur background."""

    login_successful = pyqtSignal(object)  # Emits User object on successful login

    def __init__(self, parent=None):
        super().__init__(parent)

        # Disable close on dim click - user must login
        self.setCloseOnDimClicked(False)

        # Hide the parent dim_ layer
        self.dim_.hide()

        # Dark overlay (0.9 opacity black)
        self.overlay = SiLabel(self)
        self.overlay.setStyleSheet("background-color: rgba(0, 0, 0, 0.92);")

        # Panel container
        self.panel_container = SiWidget(self)

        # Login panel
        self.login_panel = LoginPanel(self.panel_container)
        self.login_panel.switch_to_register.connect(self.showRegisterPanel)
        self.login_panel.login_success.connect(self._on_login_success)

        # Register panel
        self.register_panel = RegisterPanel(self.panel_container)
        self.register_panel.switch_to_login.connect(self.showLoginPanel)
        self.register_panel.register_success.connect(self._on_register_success)

        # Initially show login panel
        self.register_panel.hide()
        self.login_panel.show()

        # Animation for panel switching
        self._current_panel = self.login_panel

    def setAuthServices(self, db_manager, session_manager, email_service):
        """Set authentication services for panels."""
        self.login_panel.setAuthServices(db_manager, session_manager)
        self.register_panel.setAuthServices(db_manager, email_service)

    def showLayer(self):
        """Show the login layer."""
        self.show()
        self.raise_()
        self.overlay.raise_()
        self.panel_container.raise_()
        self._centerCurrentPanel()
        # Clear inputs when showing login layer (e.g. after logout)
        self.login_panel.clearInputs()

    def showLoginPanel(self):
        """Show login panel with animation."""
        self.register_panel.hide()
        self.login_panel.show()
        self._current_panel = self.login_panel
        self._centerCurrentPanel()
        self.login_panel.clearInputs()

    def showRegisterPanel(self):
        """Show register panel with animation."""
        self.login_panel.hide()
        self.register_panel.show()
        self._current_panel = self.register_panel
        self._centerCurrentPanel()
        self.register_panel.reset()

    def _centerCurrentPanel(self):
        """Center the current panel in the layer."""
        if self._current_panel:
            x = (self.width() - self._current_panel.width()) // 2
            y = (self.height() - self._current_panel.height()) // 2
            self._current_panel.move(x, y)

    def _on_login_success(self, user):
        """Handle successful login."""
        self.login_successful.emit(user)
        self.closeLayer()

    def _on_register_success(self):
        """Handle successful registration."""
        # Switch to login panel after registration
        self.showLoginPanel()

    def resizeEvent(self, event):
        """Handle resize to keep panels centered."""
        super().resizeEvent(event)
        size = event.size()

        self.overlay.resize(size)
        self.panel_container.resize(size)

        self._centerCurrentPanel()

    def closeLayer(self):
        """Override to add fade out animation."""
        self.hideDimMask()
        self.hide()
        self.closed.emit()
