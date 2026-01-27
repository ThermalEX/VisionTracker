"""Vision Tracker - Statistics Page"""

from PyQt5.QtCore import Qt

from siui.components import SiTitledWidgetGroup
from siui.components.page import SiPage


class StatisticsPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Statistics")

        # Main group
        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)
