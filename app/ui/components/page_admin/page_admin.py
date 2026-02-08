"""Vision Tracker - Admin Page"""

from PyQt5.QtCore import Qt
from siui.components import (
    SiDenseVContainer,
    SiLabel,
    SiOptionCardLinear,
    SiTitledWidgetGroup,
    SiPushButton,
)
from siui.components.page import SiPage
from siui.core import GlobalFont, Si, SiColor, SiGlobal
from siui.gui import SiFont


class AdminPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.setPadding(64)
        self.setScrollMaximumWidth(950)
        self.setTitle("Admin Panel")

        self.titled_widget_group = SiTitledWidgetGroup(self)
        self.titled_widget_group.setSiliconWidgetFlag(Si.EnableAnimationSignals)

        # Admin info section
        admin_container = SiDenseVContainer(self)
        admin_container.setAlignment(Qt.AlignCenter)
        admin_container.setFixedHeight(120)

        admin_label = SiLabel(self)
        admin_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        admin_label.setFont(SiFont.tokenized(GlobalFont.S_BOLD))
        admin_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_A)}")
        admin_label.setText("👤 Administrator Dashboard")

        admin_desc = SiLabel(self)
        admin_desc.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        admin_desc.setFont(SiFont.tokenized(GlobalFont.S_NORMAL))
        admin_desc.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        admin_desc.setText("Manage system users and view statistics")

        admin_container.addWidget(admin_label)
        admin_container.addWidget(admin_desc)
        self.titled_widget_group.addWidget(admin_container)

        # User Management section
        with self.titled_widget_group as group:
            group.addTitle("User Management")

            self.option_card_users = SiOptionCardLinear(self)
            self.option_card_users.setTitle(
                "View All Users",
                "Browse and manage registered users in the system"
            )
            self.option_card_users.load(SiGlobal.siui.iconpack.get("ic_fluent_people_filled"))

            # Add view button
            self.btn_view_users = SiPushButton(self)
            self.btn_view_users.setText("View Users")
            self.btn_view_users.setFixedWidth(100)
            self.option_card_users.addWidget(self.btn_view_users)

            group.addWidget(self.option_card_users)

        # System Statistics section
        with self.titled_widget_group as group:
            group.addTitle("System Statistics")

            self.option_card_stats = SiOptionCardLinear(self)
            self.option_card_stats.setTitle(
                "System Overview",
                "Total users, sessions, and system health metrics"
            )
            self.option_card_stats.load(SiGlobal.siui.iconpack.get("ic_fluent_data_pie_filled"))

            group.addWidget(self.option_card_stats)

        # Danger Zone section
        with self.titled_widget_group as group:
            group.addTitle("Danger Zone")

            self.option_card_danger = SiOptionCardLinear(self)
            self.option_card_danger.setTitle(
                "Database Management",
                "Advanced database operations (use with caution)"
            )
            self.option_card_danger.load(SiGlobal.siui.iconpack.get("ic_fluent_warning_filled"))

            self.btn_refresh_db = SiPushButton(self)
            self.btn_refresh_db.setText("Refresh")
            self.btn_refresh_db.setFixedWidth(100)
            self.option_card_danger.addWidget(self.btn_refresh_db)

            group.addWidget(self.option_card_danger)

        # Add placeholder
        self.titled_widget_group.addPlaceholder(64)

        # Set attachment
        self.setAttachment(self.titled_widget_group)
