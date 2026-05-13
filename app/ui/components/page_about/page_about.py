"""Vision Tracker - About Page"""

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QFont

from siui.components import (
    SiDenseVContainer,
    SiLabel,
    SiOptionCardLinear,
    SiSimpleButton,
    SiTitledWidgetGroup,
)
from siui.components.page import SiPage
from siui.core import GlobalFont, Si, SiColor, SiGlobal
from siui.gui import SiFont


class AboutPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setPadding(64)
        self.setScrollMaximumWidth(950)
        self.setTitle("About")

        self.titled_widget_group = SiTitledWidgetGroup(self)
        self.titled_widget_group.setSiliconWidgetFlag(Si.EnableAnimationSignals)

        # App info section
        version_container = SiDenseVContainer(self)
        version_container.setAlignment(Qt.AlignCenter)
        version_container.setFixedHeight(180)

        # ASCII Art title
        ascii_title = (
            r"____   ____ __          __                  ___________                         __" + "\n"
            r"\   \ /   /|__|  ______|__|  ____    ____   \__    ___/_______ _____     ____  |  | __  ____ _______" + "\n"
            r" \   Y   / |  | /  ___/|  | /  _ \  /    \    |    |   \_  __ \\__  \  _/ ___\ |  |/ /_/ __ \\_  __ " + "\\\n"
            r"  \     /  |  | \___ \ |  |(  <_> )|   |  \   |    |    |  | \/ / __ \_\  \___ |    < \  ___/ |  | \/" + "\n"
            r"   \___/   |__|/____  >|__| \____/ |___|  /   |____|    |__|   (____  / \___  >|__|_ \ \___  >|__|" + "\n"
            r"                    \/                  \/                          \/      \/      \/     \/"
        )
        self.app_name_label = SiLabel(self)
        self.app_name_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.app_name_label.setFont(QFont("Consolas", 9))
        self.app_name_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_A)}")
        self.app_name_label.setText(ascii_title)

        self.version_label = SiLabel(self)
        self.version_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.version_label.setFont(SiFont.tokenized(GlobalFont.S_NORMAL))
        self.version_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        self.version_label.setText("Version 1.0.0")

        version_container.addWidget(self.app_name_label)
        version_container.addWidget(self.version_label)
        self.titled_widget_group.addWidget(version_container)

        # Project info
        with self.titled_widget_group as group:
            group.addTitle("Project")

            self.option_card_project = SiOptionCardLinear(self)
            self.option_card_project.setTitle(
                "Honours Stage Project",
                "A computer vision-based automatic target detection and tracking system"
            )
            self.option_card_project.load(SiGlobal.siui.iconpack.get("ic_fluent_target_regular"))

            self.option_card_tech = SiOptionCardLinear(self)
            self.option_card_tech.setTitle(
                "Technology Stack",
                "Python + PyTorch + Ultralytics YOLO + PyQt5 + SiliconUI"
            )
            self.option_card_tech.load(SiGlobal.siui.iconpack.get("ic_fluent_code_regular"))

            group.addWidget(self.option_card_project)
            group.addWidget(self.option_card_tech)

        # Author info
        with self.titled_widget_group as group:
            group.addTitle("Author")

            self.button_to_github = SiSimpleButton(self)
            self.button_to_github.resize(32, 32)
            self.button_to_github.attachment().load(SiGlobal.siui.iconpack.get("ic_fluent_open_regular"))
            self.button_to_github.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl("https://github.com/ThermalEX/HonoursStageProject"))
            )

            self.option_card_author = SiOptionCardLinear(self)
            self.option_card_author.setTitle(
                "Wang Shuhan",
                "Honours Stage Project - View on GitHub"
            )
            self.option_card_author.load(SiGlobal.siui.iconpack.get("ic_fluent_person_regular"))
            self.option_card_author.addWidget(self.button_to_github)

            group.addWidget(self.option_card_author)

        # Credits
        with self.titled_widget_group as group:
            group.addTitle("Credits")

            self.button_to_siui = SiSimpleButton(self)
            self.button_to_siui.resize(32, 32)
            self.button_to_siui.attachment().load(SiGlobal.siui.iconpack.get("ic_fluent_open_regular"))
            self.button_to_siui.clicked.connect(
                lambda: QDesktopServices.openUrl(QUrl("https://github.com/ChinaIceF/PyQt-SiliconUI"))
            )

            self.option_card_siui = SiOptionCardLinear(self)
            self.option_card_siui.setTitle(
                "PyQt-SiliconUI",
                "UI framework by ChinaIceF - GPLv3 License"
            )
            self.option_card_siui.load(SiGlobal.siui.iconpack.get("ic_fluent_heart_regular"))
            self.option_card_siui.addWidget(self.button_to_siui)

            group.addWidget(self.option_card_siui)

        self.titled_widget_group.addPlaceholder(64)

        self.setAttachment(self.titled_widget_group)
