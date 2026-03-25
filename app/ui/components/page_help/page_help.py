"""Vision Tracker - Help Page."""

from pathlib import Path

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QTextBrowser, QWidget

from siui.components import SiOptionCardLinear, SiSimpleButton, SiTitledWidgetGroup
from siui.components.combobox.combobox import SiComboBox
from siui.components.page import SiPage
from siui.components.slider_ import SiScrollBar
from siui.core import SiGlobal

try:
    import markdown
except ImportError:
    markdown = None


class HelpPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Help")

        base_dir = Path(__file__).resolve().parents[3]
        self._docs_dir = base_dir / "data" / "help"
        self._language = "en"
        self._doc_files = {
            "zh": self._docs_dir / "vision_tracker_help_zh.md",
            "en": self._docs_dir / "vision_tracker_help_en.md",
        }

        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        self._buildHeader()
        self._buildReader()
        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)

        self._loadDocument()

    def _buildHeader(self):
        self.header_card = SiOptionCardLinear(self)
        self.header_card.setFixedSize(932, 80)
        self.header_card.setTitle(
            "User Guide",
            "Bilingual operation manual with Markdown rendering support",
        )
        self.header_card.load(
            SiGlobal.siui.iconpack.get("ic_fluent_document_text_regular")
            or SiGlobal.siui.iconpack.get("ic_fluent_book_open_globe_regular")
        )

        self.language_combo = SiComboBox(self)
        self.language_combo.resize(100, 32)
        self.language_combo.menu().addOption("English", value="en")
        self.language_combo.menu().addOption("中文", value="zh")
        self.language_combo.menu().setIndex(0)
        self.language_combo.menu().indexChanged.connect(self._onLanguageChanged)
        self.header_card.addWidget(self.language_combo)

        self.open_folder_button = SiSimpleButton(self)
        self.open_folder_button.setFixedSize(32, 32)
        self.open_folder_button.attachment().load(
            SiGlobal.siui.iconpack.get("ic_fluent_folder_open_regular")
        )
        self.open_folder_button.setToolTip("Open help docs folder")
        self.open_folder_button.clicked.connect(self._openDocsFolder)
        self.header_card.addWidget(self.open_folder_button)

        self.reload_button = SiSimpleButton(self)
        self.reload_button.setFixedSize(32, 32)
        self.reload_button.attachment().load(
            SiGlobal.siui.iconpack.get("ic_fluent_arrow_sync_regular")
        )
        self.reload_button.setToolTip("Reload current help document")
        self.reload_button.clicked.connect(self._loadDocument)
        self.header_card.addWidget(self.reload_button)

        self.titled_group.addWidget(self.header_card)

    def _buildReader(self):
        self.reader_host = QWidget(self)
        self.reader_host.setFixedSize(932, 980)
        self.reader_host.setStyleSheet(
            f"background-color: {SiGlobal.siui.colors['INTERFACE_BG_C']};"
            "border-radius: 10px;"
        )

        self.browser = QTextBrowser(self.reader_host)
        self.browser.setGeometry(18, 18, 896, 944)
        self.browser.setOpenExternalLinks(True)
        self.browser.setOpenLinks(True)
        self.browser.setFrameShape(QTextBrowser.NoFrame)
        self.browser.setReadOnly(True)
        self.browser.setStyleSheet(self._browserStyleSheet())
        self.browser.anchorClicked.connect(self._handleAnchorClicked)

        self.browser_scrollbar = SiScrollBar(self.browser)
        self.browser_scrollbar.setOrientation(Qt.Vertical)
        self.browser_scrollbar.setFixedWidth(8)
        self.browser_scrollbar.setStyleSheet(
            "QScrollBar:vertical {"
            "    background-color: transparent;"
            "    border: none;"
            "}"
        )
        self.browser.setVerticalScrollBar(self.browser_scrollbar)

        self.titled_group.addWidget(self.reader_host)

    def _browserStyleSheet(self) -> str:
        return f"""
        QTextBrowser {{
            background-color: {SiGlobal.siui.colors['INTERFACE_BG_B']};
            color: #EDE7F2;
            border: none;
            border-radius: 8px;
            padding: 20px;
            selection-background-color: #6E56CF;
            selection-color: white;
            font-family: 'Segoe UI', 'Microsoft YaHei UI', sans-serif;
            font-size: 14px;
            line-height: 1.6;
        }}
        """

    def _switchLanguage(self, language: str):
        self._language = language if language in self._doc_files else "zh"
        self._loadDocument()

    def _onLanguageChanged(self, index: int):
        language = "en" if index == 0 else "zh"
        if language != self._language:
            self._switchLanguage(language)

    def _loadDocument(self):
        doc_path = self._doc_files.get(self._language, self._doc_files["zh"])
        self._syncLanguageSelector()

        if not doc_path.exists():
            self.browser.setPlainText(f"Document not found:\n{doc_path}")
            return

        text = doc_path.read_text(encoding="utf-8")
        self.browser.setSearchPaths([str(doc_path.parent), str(self._docs_dir)])

        if markdown is None:
            self.browser.setPlainText(
                "Markdown library is not installed.\n\n"
                "Please install dependencies:\n"
                "pip install -r requirements.txt\n\n"
                f"Requested file:\n{doc_path}\n\n"
                + text
            )
            return

        html_body = markdown.markdown(
            text,
            extensions=[
                "extra",
                "admonition",
                "toc",
                "codehilite",
                "nl2br",
                "sane_lists",
            ],
            output_format="html5",
        )
        self.browser.setHtml(self._wrapHtml(html_body))
        self.browser.verticalScrollBar().setValue(0)

    def _wrapHtml(self, body: str) -> str:
        return f"""
        <html>
        <head>
        <style>
        body {{
            background: {SiGlobal.siui.colors['INTERFACE_BG_B']};
            color: #EDE7F2;
            font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
            font-size: 14px;
            line-height: 1.75;
            margin: 0;
        }}
        h1, h2, h3, h4 {{
            color: #FAF5FF;
            margin-top: 1.3em;
            margin-bottom: 0.5em;
        }}
        h1 {{
            font-size: 28px;
            border-bottom: 1px solid #4A4452;
            padding-bottom: 10px;
        }}
        h2 {{
            font-size: 22px;
            border-left: 4px solid #8E79D9;
            padding-left: 10px;
        }}
        h3 {{ font-size: 18px; }}
        p, li {{
            color: #DED4E8;
        }}
        a {{
            color: #6CCBFF;
            text-decoration: none;
        }}
        code {{
            background: #2B2631;
            color: #FFE8A3;
            padding: 2px 6px;
            border-radius: 6px;
            font-family: Consolas, monospace;
        }}
        pre {{
            background: #221F27;
            border: 1px solid #3A3443;
            border-radius: 10px;
            padding: 14px;
            overflow-x: auto;
        }}
        pre code {{
            background: transparent;
            padding: 0;
            color: #EDE7F2;
        }}
        blockquote {{
            border-left: 4px solid #8E79D9;
            margin: 16px 0;
            padding: 8px 14px;
            background: #26222C;
            color: #D1C5DE;
            border-radius: 6px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 18px 0;
            background: #25212B;
        }}
        th, td {{
            border: 1px solid #463F50;
            padding: 10px 12px;
            text-align: left;
        }}
        th {{
            background: #302A38;
            color: #FAF5FF;
        }}
        tr:nth-child(even) {{
            background: #2A2530;
        }}
        img {{
            max-width: 100%;
            border-radius: 8px;
            margin: 10px 0;
            border: 1px solid #3E3848;
        }}
        ul, ol {{
            margin-top: 8px;
            margin-bottom: 12px;
        }}
        hr {{
            border: none;
            border-top: 1px solid #4A4452;
            margin: 20px 0;
        }}
        </style>
        </head>
        <body>{body}</body>
        </html>
        """

    def _syncLanguageSelector(self):
        target_index = 0 if self._language == "en" else 1
        if self.language_combo.menu().index() != target_index:
            self.language_combo.menu().blockSignals(True)
            self.language_combo.menu().setIndex(target_index)
            self.language_combo.menu().blockSignals(False)

    def _openDocsFolder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._docs_dir)))

    def _handleAnchorClicked(self, url: QUrl):
        if url.isLocalFile():
            QDesktopServices.openUrl(url)
            return
        QDesktopServices.openUrl(url)
