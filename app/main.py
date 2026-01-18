"""Vision Tracker - Main Application Entry Point"""

import sys
from PyQt5.QtWidgets import QApplication

from ui import VisionTrackerApp


def main():
    """Main entry point for the application."""
    app = QApplication(sys.argv)

    window = VisionTrackerApp()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
