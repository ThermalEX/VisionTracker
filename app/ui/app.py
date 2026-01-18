"""Vision Tracker - Main Application UI"""

import os
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QDesktopWidget

import siui
from siui.core import SiColor, SiGlobal
from siui.templates.application.application import SiliconApplication

from . import icons
from .components import HomePage, AboutPage

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
        self.layerMain().addPage(
            HomePage(self),
            icon=SiGlobal.siui.iconpack.get("ic_fluent_home_filled"),
            hint="Home",
            side="top"
        )

        # About page - bottom
        self.layerMain().addPage(
            AboutPage(self),
            icon=SiGlobal.siui.iconpack.get("ic_fluent_info_filled"),
            hint="About",
            side="bottom"
        )

        # Set default page
        self.layerMain().setPage(0)

        # Reload stylesheets
        SiGlobal.siui.reloadAllWindowsStyleSheet()
