from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

from siui.components import SiDenseHContainer, SiDenseVContainer, SiLabel
from siui.components.widgets import SiSimpleButton
from siui.core import GlobalFont, Si, SiColor, SiGlobal
from siui.gui import SiFont
from siui.templates.application.components.page_view import PageView

from ..layer import SiLayer


class LayerMain(SiLayer):
    user_button_clicked = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # 整个窗口的垫底标签
        self.background_label = SiLabel(self)
        self.background_label.setFixedStyleSheet("border-radius: 0px")

        # 标题栏背景（圆角矩形）- 放在最底层
        self.title_bar_bg = SiLabel(self)
        self.title_bar_bg.setFixedHeight(44)

        # -> 垂直容器，上方是标题，下方是窗口内容
        self.container_title_and_content = SiDenseVContainer(self)
        self.container_title_and_content.setSpacing(0)
        self.container_title_and_content.setAdjustWidgetsSize(True)

        # -> 标题栏处的水平容器，左侧是图标和标题，右侧是操作按钮
        self.container_title = SiDenseHContainer(self)
        self.container_title.setSpacing(0)
        self.container_title.setAlignment(Qt.AlignCenter)
        self.container_title.setFixedHeight(64)

        # 当前页面名称标签
        self.page_name_label = SiLabel(self)
        self.page_name_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        page_name_font = SiFont.getFont(size=15, weight=QFont.Normal)
        self.page_name_label.setFont(page_name_font)
        self.page_name_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.page_name_label.setText("Home")
        self._pending_page_name = None  # 用于动画过渡时存储新页面名称

        # 时间日期标签（标题栏中间）
        self.datetime_label = SiLabel(self)
        self.datetime_label.setAlignment(Qt.AlignCenter)
        datetime_font = SiFont.getFont(size=14, weight=QFont.Normal)
        self.datetime_label.setFont(datetime_font)

        # 定时器更新时间
        self.datetime_timer = QTimer(self)
        self.datetime_timer.timeout.connect(self._updateDateTime)
        self.datetime_timer.start(1000)  # 每秒更新
        self._updateDateTime()  # 初始化显示

        # 用户按钮（标题栏右侧）
        self.user_button = SiSimpleButton(self)
        self.user_button.resize(32, 32)
        self.user_button.attachment().setSvgSize(20, 20)
        self.user_button.clicked.connect(self.user_button_clicked.emit)

        self.container_title.addPlaceholder(80)  # 往右移动，避开侧边栏
        self.container_title.addWidget(self.page_name_label)

        self.page_view = PageView(self)
        self.page_view.pageChanged.connect(self.setPageName)

        # 存储页面名称
        self._page_names = []

        # <- 添加到垂直容器
        self.container_title_and_content.addWidget(self.container_title)
        self.container_title_and_content.addWidget(self.page_view)

        # 隐藏阴影层，因为没有任何用
        self.dim_.hide()

    def reloadStyleSheet(self):
        self.background_label.setStyleSheet(
            f"background-color: {self.getColor(SiColor.INTERFACE_BG_A)};"
            f"border: 1px solid {self.getColor(SiColor.INTERFACE_BG_B)};"
        )
        self.page_name_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_B)}")
        self.datetime_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_C)}")
        # 标题栏圆角矩形样式 - 深紫色背景，无边框
        self.title_bar_bg.setStyleSheet(
            "background-color: #322838;"
            "border-radius: 20px;"
        )

    def _updateDateTime(self):
        """更新时间日期显示"""
        now = datetime.now()
        # 格式: Sat, Jan 18, 2026  14:30:25
        text = now.strftime("%a, %b %d, %Y  %H:%M:%S")
        self.datetime_label.setText(text)

    def setUserButtonIcon(self, icon_data):
        """Set user button icon."""
        self.user_button.attachment().load(icon_data)

    def setPageName(self, name: str):
        """Set the current page name displayed in title bar with fade animation."""
        # 如果名称相同，不做任何操作
        if self.page_name_label.text() == name:
            return

        # 存储新名称
        self._pending_page_name = name

        # 淡出动画
        self.page_name_label.setOpacityTo(0)

        # 淡出完成后更新文字并淡入
        QTimer.singleShot(150, self._updatePageNameText)

    def _updatePageNameText(self):
        """Update page name text and fade in."""
        if self._pending_page_name:
            self.page_name_label.setText(self._pending_page_name)
            self._pending_page_name = None
        self.page_name_label.setOpacityTo(1)

    def addPage(self, page, icon, hint: str, side="top"):
        """
        添加新页面
        :param page: 页面控件
        :param icon: 页面按钮的 svg 数据或路径
        :param hint: 页面按钮的工具提示（也用作页面名称）
        :param side: 页面按钮置于哪一侧
        """
        # 存储页面名称（使用 hint 作为页面名称）
        self._page_names.append(hint)
        self.page_view.addPage(page, icon, hint, side)

    def setPage(self, index):
        """ Set current page by index and activate corresponding button """
        self.page_view.stacked_container.setCurrentIndex(index)
        # Activate the corresponding navigation button
        if index < len(self.page_view.page_navigator.buttons):
            self.page_view.page_navigator.buttons[index].setActive(True)
        # Update page name in title bar
        if index < len(self._page_names):
            self.setPageName(self._page_names[index])

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = event.size().width(), event.size().height()
        self.background_label.resize(event.size())
        self.container_title_and_content.resize(event.size())
        self.page_view.resize(w, h - 64)
        self.dim_.resize(event.size())

        # 布局标题栏背景（圆角矩形）- 与页面内容区域左边对齐
        title_bar_x = 56  # 与页面内容左边对齐
        title_bar_width = w - 56 - 12  # 减去左边侧边栏和右边边距
        self.title_bar_bg.setFixedWidth(title_bar_width)
        self.title_bar_bg.move(title_bar_x, 10)  # 垂直居中在标题栏区域

        # 布局页面名称标签（往中间移动一点）
        page_name_x = 56 + 24  # 比原来多偏移一些
        page_name_y = (64 - self.page_name_label.height()) // 2  # 垂直居中
        self.page_name_label.move(page_name_x, page_name_y)

        # 布局时间日期标签（标题栏中间）
        self.datetime_label.setFixedSize(280, 30)
        datetime_x = (w - 280) // 2  # 水平居中
        datetime_y = (64 - 30) // 2  # 垂直居中
        self.datetime_label.move(datetime_x, datetime_y)

        # 布局用户按钮（标题栏右侧，往中间移动一点）
        user_btn_x = w - 36 - 32  # 右边距36（原来16），按钮宽32
        user_btn_y = (64 - 32) // 2  # 标题栏高64，按钮高32，垂直居中
        self.user_button.move(user_btn_x, user_btn_y)
