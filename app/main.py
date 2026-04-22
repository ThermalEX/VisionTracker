import torch

import os
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon

from ui import VisionTrackerApp


def _set_app_user_model_id():
    """Set a unique AppUserModelID so Windows taskbar uses our icon
    instead of grouping the process under python.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "VisionTracker.Desktop.App.1"
        )
    except Exception:
        pass


def main():
    _set_app_user_model_id()

    app = QApplication(sys.argv)

    # Apply icon at the QApplication level as well so all windows inherit it
    img_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "ui", "img"
    )
    ico_path = os.path.join(img_dir, "app_icon.ico")
    png_path = os.path.join(img_dir, "app_icon.png")
    icon_path = ico_path if os.path.exists(ico_path) else png_path
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = VisionTrackerApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
