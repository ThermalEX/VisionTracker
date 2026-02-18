"""Dataset image browser with bounding box visualization."""

import os
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QRectF
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox

from siui.components import SiDenseHContainer, SiLabel
from siui.components.button import SiFlatButton
from siui.components.combobox.combobox import SiComboBox
from siui.core import Si, SiColor, SiGlobal
from siui.gui import SiFont

# Color palette for bounding box classes
CLASS_COLORS = [
    QColor(255, 77, 77),    # Red
    QColor(77, 166, 255),   # Blue
    QColor(77, 255, 120),   # Green
    QColor(255, 200, 50),   # Yellow
    QColor(200, 100, 255),  # Purple
    QColor(255, 140, 50),   # Orange
    QColor(50, 220, 220),   # Cyan
    QColor(255, 100, 180),  # Pink
    QColor(180, 255, 100),  # Lime
    QColor(255, 255, 100),  # Light Yellow
]

SPINBOX_STYLE = """
    QSpinBox {
        background-color: #201d23;
        border: 1px solid #3a3540;
        border-radius: 6px;
        color: #D1CBD4;
        padding: 0 8px;
        font-family: "Segoe UI", "Microsoft YaHei";
        font-size: 13px;
    }
    QSpinBox:focus { border: 1px solid #D087DF; }
    QSpinBox::up-button, QSpinBox::down-button { width: 0; height: 0; }
"""


class DatasetScanner(QThread):
    """Background thread to scan dataset and build class index."""
    scan_finished = pyqtSignal(dict)

    def __init__(self, image_dir, label_dir, parent=None):
        super().__init__(parent)
        self.image_dir = image_dir
        self.label_dir = label_dir

    def run(self):
        result = {
            "images": [],
            "class_index": {},  # class_id -> set of image indices
            "image_labels": {},  # image_index -> list of (cls, cx, cy, w, h)
        }

        if not self.image_dir or not os.path.isdir(self.image_dir):
            self.scan_finished.emit(result)
            return

        # Collect image files
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        images = sorted([
            f for f in os.listdir(self.image_dir)
            if os.path.splitext(f)[1].lower() in exts
        ])
        result["images"] = images

        # Scan labels
        for idx, img_name in enumerate(images):
            label_name = os.path.splitext(img_name)[0] + ".txt"
            label_path = os.path.join(self.label_dir, label_name) if self.label_dir else ""

            labels = []
            if label_path and os.path.isfile(label_path):
                try:
                    with open(label_path, 'r') as f:
                        for line in f:
                            parts = line.strip().split()
                            if len(parts) >= 5:
                                cls = int(parts[0])
                                cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                                labels.append((cls, cx, cy, w, h))
                                # Build class index
                                if cls not in result["class_index"]:
                                    result["class_index"][cls] = set()
                                result["class_index"][cls].add(idx)
                except Exception:
                    pass

            result["image_labels"][idx] = labels

        self.scan_finished.emit(result)


def _clear_menu(menu):
    """Remove all options from a SiComboBox menu."""
    body = menu.body()
    for opt in menu.options_[:]:
        # Remove from body container's internal widget list
        try:
            body.removeWidget(opt)
        except ValueError:
            pass
        opt.hide()
        opt.setParent(None)
        opt.deleteLater()
    menu.options_.clear()
    menu.current_index = None
    menu.current_value = None
    body.adjustSize()


class DatasetBrowser(QWidget):
    """Image browser with bbox visualization, pagination, and class filter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._yaml_path = ""
        self._dataset_info = {}
        self._class_names = []
        self._splits = {}  # split_name -> {images_dir, labels_dir}
        self._current_split = ""

        self._images = []
        self._filtered_indices = []
        self._class_index = {}
        self._image_labels = {}
        self._current_index = 0

        self._scanner = None

        self._initUI()

    def _initUI(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Top controls: split selector + class filter
        self.top_bar = SiDenseHContainer(self)
        self.top_bar.setFixedHeight(36)
        self.top_bar.setSpacing(8)

        self.split_combo = SiComboBox(self)
        self.split_combo.resize(120, 32)
        self.split_combo.menu().indexChanged.connect(self._onSplitChanged)
        self.top_bar.addWidget(self.split_combo, side="left")

        self.class_combo = SiComboBox(self)
        self.class_combo.resize(160, 32)
        self.class_combo.menu().indexChanged.connect(self._onClassFilterChanged)
        self.top_bar.addWidget(self.class_combo, side="left")

        self.info_label = SiLabel(self)
        self.info_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.info_label.setFont(SiFont.getFont(size=11))
        self.info_label.setTextColor("#918497")
        self.info_label.setText("")
        self.top_bar.addWidget(self.info_label, side="right")

        layout.addWidget(self.top_bar)

        # Image display area
        self.image_label = QLabel(self)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(380)
        self.image_label.setText("Select a dataset to browse images")
        self.image_label.setStyleSheet(
            "QLabel { background-color: #1a1720; border: 1px solid #3a3540; "
            "border-radius: 6px; color: #918497; font-size: 14px; }"
        )
        layout.addWidget(self.image_label, stretch=1)

        # Bottom navigation (QHBoxLayout for proper elastic spacing)
        nav_bar = QWidget(self)
        nav_bar.setFixedHeight(36)
        nav_layout = QHBoxLayout(nav_bar)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)

        # Left side: Go to + spinbox + jump button
        jump_label = SiLabel(self)
        jump_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        jump_label.setFont(SiFont.getFont(size=12))
        jump_label.setTextColor("#918497")
        jump_label.setFixedHeight(32)
        jump_label.setText("Go to:")
        nav_layout.addWidget(jump_label)

        self.jump_spinbox = QSpinBox(self)
        self.jump_spinbox.setFixedSize(72, 32)
        self.jump_spinbox.setMinimum(1)
        self.jump_spinbox.setMaximum(1)
        self.jump_spinbox.setValue(1)
        self.jump_spinbox.setStyleSheet(SPINBOX_STYLE)
        nav_layout.addWidget(self.jump_spinbox)

        self.btn_jump = SiFlatButton(self)
        self.btn_jump.setFixedSize(32, 32)
        self.btn_jump.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_arrow_enter_filled"))
        self.btn_jump.setToolTip("Jump to image")
        self.btn_jump.clicked.connect(self._onJump)
        nav_layout.addWidget(self.btn_jump)

        # Elastic spacer
        nav_layout.addStretch(1)

        # Right side: prev | page label | next
        self.btn_prev = SiFlatButton(self)
        self.btn_prev.setFixedSize(32, 32)
        self.btn_prev.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_chevron_left_filled"))
        self.btn_prev.setToolTip("Previous image")
        self.btn_prev.clicked.connect(self._onPrev)
        nav_layout.addWidget(self.btn_prev)

        self.page_label = SiLabel(self)
        self.page_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.page_label.setFont(SiFont.getFont(size=12))
        self.page_label.setTextColor("#918497")
        self.page_label.setFixedHeight(32)
        self.page_label.setText("0 / 0")
        nav_layout.addWidget(self.page_label)

        self.btn_next = SiFlatButton(self)
        self.btn_next.setFixedSize(32, 32)
        self.btn_next.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_chevron_right_filled"))
        self.btn_next.setToolTip("Next image")
        self.btn_next.clicked.connect(self._onNext)
        nav_layout.addWidget(self.btn_next)

        layout.addWidget(nav_bar)

    def _replaceCombo(self, old_combo, width, side):
        """Create a new SiComboBox to replace an existing one in the top bar."""
        new_combo = SiComboBox(self)
        new_combo.resize(width, 32)
        # Replace in the top bar's widget list
        if side == "left":
            widgets = self.top_bar.widgets_left
        else:
            widgets = self.top_bar.widgets_right
        idx = widgets.index(old_combo)
        widgets[idx] = new_combo
        new_combo.setParent(self.top_bar)
        old_combo.hide()
        old_combo.setParent(None)
        old_combo.deleteLater()
        self.top_bar.arrangeWidget()
        return new_combo

    def loadDataset(self, yaml_path):
        """Load a dataset YAML and start scanning."""
        self._yaml_path = yaml_path

        try:
            import yaml
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            self.image_label.setText(f"Failed to load YAML: {e}")
            return

        self._dataset_info = data
        yaml_dir = os.path.dirname(os.path.abspath(yaml_path))

        # Parse class names
        names = data.get("names", {})
        if isinstance(names, dict):
            self._class_names = [names[k] for k in sorted(names.keys())]
        elif isinstance(names, list):
            self._class_names = names
        else:
            self._class_names = []

        # Recreate class filter combo with new options
        self.class_combo = self._replaceCombo(self.class_combo, 160, "left")
        self.class_combo.menu().addOption("All Classes", value=-1)
        for i, name in enumerate(self._class_names):
            self.class_combo.menu().addOption(name, value=i)
        self.class_combo.menu().setIndex(0)
        self.class_combo.menu().indexChanged.connect(self._onClassFilterChanged)

        # Parse splits (train/val/test paths)
        self._splits = {}
        path_root = data.get("path", yaml_dir)
        if not os.path.isabs(path_root):
            path_root = os.path.join(yaml_dir, path_root)

        # Recreate split combo with new options
        self.split_combo = self._replaceCombo(self.split_combo, 120, "left")
        for split_name in ["train", "val", "test"]:
            split_val = data.get(split_name, "")
            if not split_val:
                continue
            img_dir = split_val if os.path.isabs(split_val) else os.path.join(path_root, split_val)
            if os.path.isdir(img_dir):
                # Infer label dir from image dir (images/ -> labels/)
                label_dir = img_dir.replace("images", "labels")
                self._splits[split_name] = {
                    "images_dir": img_dir,
                    "labels_dir": label_dir if os.path.isdir(label_dir) else "",
                }
                self.split_combo.menu().addOption(split_name.capitalize(), value=split_name)

        if self._splits:
            self.split_combo.menu().setIndex(0)
            self.split_combo.menu().indexChanged.connect(self._onSplitChanged)
            first_split = list(self._splits.keys())[0]
            self._loadSplit(first_split)

    def getDatasetInfo(self):
        """Return dataset overview info."""
        if not self._dataset_info:
            return None
        total = sum(len(os.listdir(s["images_dir"])) for s in self._splits.values()
                     if os.path.isdir(s["images_dir"]))
        return {
            "class_names": self._class_names,
            "total_images": total,
            "splits": list(self._splits.keys()),
        }

    def _loadSplit(self, split_name):
        """Load a specific split (train/val/test)."""
        if split_name not in self._splits:
            return

        self._current_split = split_name
        split = self._splits[split_name]
        self.image_label.setText("Scanning dataset...")

        # Start background scanning
        self._scanner = DatasetScanner(split["images_dir"], split["labels_dir"], self)
        self._scanner.scan_finished.connect(self._onScanFinished)
        self._scanner.start()

    def _onScanFinished(self, result):
        """Handle scan completion."""
        self._images = result["images"]
        self._class_index = result["class_index"]
        self._image_labels = result["image_labels"]
        self._current_index = 0

        # Build stats
        total_labels = sum(len(v) for v in self._image_labels.values())
        self.info_label.setText(f"{len(self._images)} images | {total_labels} annotations")

        self._applyFilter()
        self._showCurrentImage()

    def _applyFilter(self):
        """Apply class filter to get filtered image indices."""
        idx = self.class_combo.menu().index()
        if idx is None or idx == 0:
            # "All Classes" selected
            self._filtered_indices = list(range(len(self._images)))
        else:
            class_id = idx - 1  # offset by 1 for "All Classes" option
            self._filtered_indices = sorted(self._class_index.get(class_id, []))

        self._current_index = 0
        total = len(self._filtered_indices)
        self.jump_spinbox.setMaximum(max(1, total))
        self._updatePageLabel()

    def _showCurrentImage(self):
        """Display the current image with bounding boxes."""
        if not self._filtered_indices:
            self.image_label.setText("No images match the filter")
            self._updatePageLabel()
            return

        img_idx = self._filtered_indices[self._current_index]
        img_name = self._images[img_idx]
        split = self._splits.get(self._current_split, {})
        img_path = os.path.join(split.get("images_dir", ""), img_name)

        if not os.path.isfile(img_path):
            self.image_label.setText(f"Image not found: {img_name}")
            return

        # Load image
        pixmap = QPixmap(img_path)
        if pixmap.isNull():
            self.image_label.setText(f"Failed to load: {img_name}")
            return

        img_w, img_h = pixmap.width(), pixmap.height()

        # Draw bounding boxes
        labels = self._image_labels.get(img_idx, [])
        if labels:
            pixmap = pixmap.copy()  # Make a mutable copy
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            font = QFont("Segoe UI", 10, QFont.Bold)
            painter.setFont(font)

            for cls, cx, cy, w, h in labels:
                color = CLASS_COLORS[cls % len(CLASS_COLORS)]
                x1 = int((cx - w / 2) * img_w)
                y1 = int((cy - h / 2) * img_h)
                bw = int(w * img_w)
                bh = int(h * img_h)

                # Draw box
                pen = QPen(color, 2)
                painter.setPen(pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(x1, y1, bw, bh)

                # Draw class label background
                class_name = self._class_names[cls] if cls < len(self._class_names) else str(cls)
                fm = painter.fontMetrics()
                text_w = fm.horizontalAdvance(class_name) + 8
                text_h = fm.height() + 4
                label_bg = QColor(color)
                label_bg.setAlpha(180)
                painter.setPen(Qt.NoPen)
                painter.setBrush(label_bg)
                painter.drawRect(x1, y1 - text_h, text_w, text_h)

                # Draw class label text
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(x1 + 4, y1 - 4, class_name)

            painter.end()

        # Scale to fit display area
        display_w = self.image_label.width() - 4
        display_h = self.image_label.height() - 4
        scaled = pixmap.scaled(display_w, display_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self._updatePageLabel()

    def _updatePageLabel(self):
        total = len(self._filtered_indices)
        current = self._current_index + 1 if total > 0 else 0

        self.page_label.setText(f"{current} / {total}")

        # Show filename in top info area
        img_name = ""
        if total > 0 and self._current_index < total:
            idx = self._filtered_indices[self._current_index]
            img_name = self._images[idx] if idx < len(self._images) else ""

        total_labels = sum(len(v) for v in self._image_labels.values())
        stats = f"{len(self._images)} images | {total_labels} labels"
        if img_name:
            self.info_label.setText(f"{img_name}  |  {stats}")
        else:
            self.info_label.setText(stats)

    # ── Navigation ─────────────────────────────────────────────────

    def _onPrev(self):
        if self._filtered_indices and self._current_index > 0:
            self._current_index -= 1
            self._showCurrentImage()

    def _onNext(self):
        if self._filtered_indices and self._current_index < len(self._filtered_indices) - 1:
            self._current_index += 1
            self._showCurrentImage()

    def _onJump(self):
        val = self.jump_spinbox.value()
        if 1 <= val <= len(self._filtered_indices):
            self._current_index = val - 1
            self._showCurrentImage()

    def _onSplitChanged(self, index):
        splits = list(self._splits.keys())
        if 0 <= index < len(splits):
            self._loadSplit(splits[index])

    def _onClassFilterChanged(self, index):
        self._applyFilter()
        self._showCurrentImage()
