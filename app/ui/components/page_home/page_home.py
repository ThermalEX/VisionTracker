"""Vision Tracker - Home Page"""

import os
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QGraphicsDropShadowEffect

from siui.components import SiPixLabel, SiLabel, SiTitledWidgetGroup, SiDenseVContainer
from siui.components.page import SiPage
from siui.core import GlobalFont, Si, SiColor, SiGlobal
from siui.gui import SiFont

# Get the directory of this file
current_dir = os.path.dirname(os.path.abspath(__file__))
img_dir = os.path.join(current_dir, '..', '..', 'img')


class HomePage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Scroll container
        self.scroll_container = SiTitledWidgetGroup(self)

        # === Header area with background ===
        self.head_area = SiLabel(self)
        self.head_area.setFixedHeight(350)

        # Background image
        self.background_image = SiPixLabel(self.head_area)
        self.background_image.setFixedSize(1366, 250)
        self.background_image.setBorderRadius(6)
        background_path = os.path.join(img_dir, 'homepage_background.jpg')
        self.background_image.load(background_path)

        # Gradient fade transition
        self.background_fading_transition = SiLabel(self.head_area)
        self.background_fading_transition.setGeometry(0, 100, 0, 150)
        self.background_fading_transition.setStyleSheet(
            """
            background-color: qlineargradient(x1:0, y1:1, x2:0, y2:0, stop:0 {}, stop:1 {})
            """.format(
                SiGlobal.siui.colors["INTERFACE_BG_B"],
                SiColor.trans(SiGlobal.siui.colors["INTERFACE_BG_B"], 0)
            )
        )

        # Welcome text - "ThermalEX Welcome!" in one line
        self.welcome_label = SiLabel(self.head_area)
        self.welcome_label.setGeometry(64, 50, 800, 80)
        self.welcome_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.welcome_label.setText("ThermalEX Welcome!")
        self.welcome_label.setStyleSheet("color: #FFFFFF")
        # Use larger font size
        font = SiFont.tokenized(GlobalFont.XL_MEDIUM)
        font.setPointSize(36)
        self.welcome_label.setFont(font)
        # Add shadow effect
        welcome_shadow = QGraphicsDropShadowEffect()
        welcome_shadow.setBlurRadius(8)
        welcome_shadow.setColor(QColor(0, 0, 0, 180))
        welcome_shadow.setOffset(2, 2)
        self.welcome_label.setGraphicsEffect(welcome_shadow)

        # Project name subtitle
        self.project_label = SiLabel(self.head_area)
        self.project_label.setGeometry(64, 130, 700, 35)
        self.project_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self.project_label.setText("Vision Tracker - Real-time Object Detection and Tracking System")
        self.project_label.setStyleSheet("color: rgba(255, 255, 255, 0.9)")
        font = SiFont.tokenized(GlobalFont.M_NORMAL)
        font.setPointSize(14)
        self.project_label.setFont(font)
        # Add shadow effect
        project_shadow = QGraphicsDropShadowEffect()
        project_shadow.setBlurRadius(6)
        project_shadow.setColor(QColor(0, 0, 0, 160))
        project_shadow.setOffset(1, 1)
        self.project_label.setGraphicsEffect(project_shadow)

        # Add header to scroll container
        self.scroll_container.addWidget(self.head_area)

        # === Body area for additional content ===
        self.body_area = SiLabel(self)
        self.body_area.setSiliconWidgetFlag(Si.EnableAnimationSignals)
        self.body_area.resized.connect(lambda _: self.scroll_container.adjustSize())

        # Content group
        self.content_group = SiTitledWidgetGroup(self.body_area)
        self.content_group.setSiliconWidgetFlag(Si.EnableAnimationSignals)
        self.content_group.resized.connect(lambda size: self.body_area.setFixedHeight(size[1]))
        self.content_group.move(64, 0)
        self.content_group.setSpacing(16)

        # Placeholder for future content
        self.content_group.addPlaceholder(32)

        # Add body to scroll container
        self.body_area.setFixedHeight(self.content_group.height())
        self.scroll_container.addWidget(self.body_area)

        # Set attachment
        self.setAttachment(self.scroll_container)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = event.size().width()
        self.body_area.setFixedWidth(w)
        self.background_image.setFixedWidth(w)
        self.content_group.setFixedWidth(min(w - 128, 900))
        self.background_fading_transition.setFixedWidth(w)
