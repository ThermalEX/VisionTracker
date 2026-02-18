"""Vision Tracker - Training Page"""

import json
import os
from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QFileDialog, QGridLayout, QLineEdit, QTextEdit, QWidget

from siui.components import SiDenseHContainer, SiDenseVContainer, SiLabel, SiTitledWidgetGroup, SiOptionCardLinear
from siui.components.page import SiPage
from siui.components.button import SiFlatButton
from siui.components.combobox.combobox import SiComboBox
from siui.components.spinbox.slider_spinbox import SiSliderSpinBox, SiSliderDoubleSpinBox
from siui.components.widgets.button import SiSwitch
from siui.components.container import SiTriSectionFlatCard
from siui.components.progress_bar.progress_bar import SiProgressBar
from siui.components.chart import SiTrendChart
from siui.core import Si, SiColor, SiGlobal
from siui.gui import SiFont

from .dataset_browser import DatasetBrowser
from .training_manager import TrainingManager

# Default values from TrainConfig
DEFAULTS = {
    "data_yaml": "",
    "img_size": 640,
    "batch_size": 8,
    "num_workers": 4,
    "num_classes": 4,
    "epochs": 1000,
    "learning_rate": 0.01,
    "weight_decay": 0.0005,
    "momentum": 0.937,
    "pretrained_weights": "",
    "use_resolution_reduce": True,
    "resolution_min_scale": 0.25,
    "resolution_max_scale": 1.0,
    "resolution_prob": 0.5,
    "use_color_jitter": True,
    "hsv_h": 0.015,
    "hsv_s": 0.7,
    "hsv_v": 0.4,
    "use_geometric": True,
    "flip_lr": 0.5,
    "flip_ud": 0.0,
    "rotate_degree": 15,
    "rotate_prob": 0.3,
    "scale_min": 0.8,
    "scale_max": 1.2,
    "scale_prob": 0.5,
    "use_noise_blur": True,
    "gaussian_noise_prob": 0.3,
    "gaussian_noise_std": 5.0,
    "motion_blur_prob": 0.3,
    "motion_blur_kernel_min": 3,
    "motion_blur_kernel_max": 7,
    "use_mosaic": True,
    "mosaic_prob": 0.5,
    "use_amp": True,
    "cache_images": False,
    "accumulate_grad": 4,
    "use_cos_lr": True,
    "warmup_epochs": 3,
    "patience": 50,
    "save_period": 10,
    "save_dir": "runs/custom_train",
    "exp_name": "exp",
}

INPUT_STYLE = """
    QLineEdit {
        background-color: #201d23;
        border: 1px solid #3a3540;
        border-radius: 6px;
        color: #D1CBD4;
        padding: 0 12px;
        font-family: "Segoe UI", "Microsoft YaHei";
        font-size: 13px;
    }
    QLineEdit:focus { border: 1px solid #D087DF; }
"""

CONSOLE_STYLE = """
    QTextEdit {
        background-color: #1a1720;
        border: 1px solid #3a3540;
        border-radius: 6px;
        color: #C8C0CC;
        padding: 8px;
        font-family: "Cascadia Code", "Consolas", monospace;
        font-size: 12px;
    }
"""


class TrainingPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1000)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Training")

        self._training_manager = TrainingManager(self)
        self._training_manager.progress_updated.connect(self._onProgressUpdated)
        self._training_manager.map_updated.connect(self._onMapUpdated)
        self._training_manager.log_output.connect(self._onLogOutput)
        self._training_manager.training_finished.connect(self._onTrainingFinished)
        self._training_manager.training_error.connect(self._onTrainingError)

        # Chart data
        self._loss_points = []
        self._map50_points = []
        self._last_epoch = 0

        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        self._class_name_inputs = []
        _app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self._class_config_path = os.path.join(_app_dir, "data", "class_config.json")
        self._user_models_dir = os.path.join(_app_dir, "models", "user")

        self._createDatasetSection()
        self._createModelSection()
        self._createClassConfigSection()
        self._createTrainingParamsSection()
        self._createAugmentationSection()
        self._createPerformanceSection()
        self._createTrainingControlSection()

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)

    # ── Section 1: Dataset ─────────────────────────────────────────

    def _createDatasetSection(self):
        self.titled_group.addTitle("Dataset")

        # Dataset YAML path
        self.dataset_card = SiOptionCardLinear(self)
        self.dataset_card.setTitle("Dataset YAML", "Select the dataset configuration file (.yaml)")
        self.dataset_card.load(SiGlobal.siui.iconpack.get("ic_fluent_folder_open_filled"))

        self.dataset_path_label = SiLabel(self)
        self.dataset_path_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.dataset_path_label.setFont(SiFont.getFont(size=12))
        self.dataset_path_label.setTextColor(self.getColor(SiColor.TEXT_D))
        self.dataset_path_label.setText("No dataset selected")
        self.dataset_card.addWidget(self.dataset_path_label)

        self.btn_browse_dataset = SiFlatButton(self)
        self.btn_browse_dataset.setFixedSize(32, 32)
        self.btn_browse_dataset.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_folder_open_filled"))
        self.btn_browse_dataset.setToolTip("Browse dataset YAML")
        self.btn_browse_dataset.clicked.connect(self._onBrowseDataset)
        self.dataset_card.addWidget(self.btn_browse_dataset)

        self.titled_group.addWidget(self.dataset_card)

        # Dataset stats
        self.stats_card = SiOptionCardLinear(self)
        self.stats_card.setTitle("Statistics", "Dataset overview after loading")
        self.stats_card.load(SiGlobal.siui.iconpack.get("ic_fluent_data_pie_filled"))

        self.stats_label = SiLabel(self)
        self.stats_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.stats_label.setFont(SiFont.getFont(size=12))
        self.stats_label.setTextColor(self.getColor(SiColor.TEXT_D))
        self.stats_label.setText("—")
        self.stats_card.addWidget(self.stats_label)
        self.titled_group.addWidget(self.stats_card)

        # Dataset browser
        self.dataset_browser = DatasetBrowser(self)
        self.dataset_browser.setFixedHeight(520)
        self.titled_group.addWidget(self.dataset_browser)

    # ── Section 2: Model Settings ──────────────────────────────────

    def _createModelSection(self):
        self.titled_group.addTitle("Model")

        # Pretrained weights
        self.weights_card = SiOptionCardLinear(self)
        self.weights_card.setTitle("Pretrained Weights", "Select .pt model file for transfer learning")
        self.weights_card.load(SiGlobal.siui.iconpack.get("ic_fluent_brain_circuit_regular"))

        self.weights_path_label = SiLabel(self)
        self.weights_path_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.weights_path_label.setFont(SiFont.getFont(size=12))
        self.weights_path_label.setTextColor(self.getColor(SiColor.TEXT_D))
        self.weights_path_label.setText("No weights selected")
        self.weights_card.addWidget(self.weights_path_label)

        self.btn_browse_weights = SiFlatButton(self)
        self.btn_browse_weights.setFixedSize(32, 32)
        self.btn_browse_weights.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_folder_open_filled"))
        self.btn_browse_weights.setToolTip("Browse pretrained weights")
        self.btn_browse_weights.clicked.connect(self._onBrowseWeights)
        self.weights_card.addWidget(self.btn_browse_weights)
        self.titled_group.addWidget(self.weights_card)

        # Image size and num_classes
        model_card = SiTriSectionFlatCard(self)
        model_card.setTitle("Model Parameters")

        model_container = SiDenseHContainer(self)
        model_container.setSpacing(24)
        model_container.setFixedHeight(90)

        self.img_size = SiSliderSpinBox(self)
        self.img_size.setTitle("Image Size (px)")
        self.img_size.resize(200, 84)
        self.img_size.setMinimum(128)
        self.img_size.setMaximum(1280)
        self.img_size.setSingleStep(32)
        self.img_size.setValue(DEFAULTS["img_size"])
        model_container.addWidget(self.img_size, side="left")

        self.num_classes = SiSliderSpinBox(self)
        self.num_classes.setTitle("Num Classes")
        self.num_classes.resize(200, 84)
        self.num_classes.setMinimum(1)
        self.num_classes.setMaximum(100)
        self.num_classes.setSingleStep(1)
        self.num_classes.setValue(DEFAULTS["num_classes"])
        model_container.addWidget(self.num_classes, side="left")

        model_card.body().addWidget(model_container)
        model_card.adjustSize()
        self.titled_group.addWidget(model_card)

    # ── Section 3: Class Configuration ─────────────────────────────

    def _createClassConfigSection(self):
        self.titled_group.addTitle("Class Configuration")

        # Header card with save button
        self.class_header_card = SiOptionCardLinear(self)
        self.class_header_card.setTitle("Class Names", "Define class names for training and custom tracker targeting")
        self.class_header_card.load(SiGlobal.siui.iconpack.get("ic_fluent_tag_multiple_filled"))

        self.btn_save_class = SiFlatButton(self)
        self.btn_save_class.setFixedSize(32, 32)
        self.btn_save_class.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_save_filled"))
        self.btn_save_class.setToolTip("Save class names")
        self.btn_save_class.clicked.connect(self._saveClassConfig)
        self.class_header_card.addWidget(self.btn_save_class)
        self.titled_group.addWidget(self.class_header_card)

        # Dynamic grid for class name inputs
        self._class_names_container = QWidget(self)
        self._class_names_grid = QGridLayout(self._class_names_container)
        self._class_names_grid.setContentsMargins(0, 4, 0, 4)
        self._class_names_grid.setHorizontalSpacing(12)
        self._class_names_grid.setVerticalSpacing(8)
        self.titled_group.addWidget(self._class_names_container)

        # Connect num_classes changes
        self.num_classes.valueChanged.connect(self._updateClassNameInputs)

        # Load saved config (this also initialises the grid)
        self._loadClassConfig()

    def _updateClassNameInputs(self, n, existing_names=None):
        """Rebuild class name input grid for n classes."""
        # Preserve existing text when not given explicit names
        if existing_names is None:
            existing_names = [inp.text() for inp in self._class_name_inputs]

        # Remove old widgets from grid
        for inp in self._class_name_inputs:
            self._class_names_grid.removeWidget(inp)
            inp.deleteLater()
        self._class_name_inputs.clear()

        # Create new inputs in a 2-column grid
        for i in range(n):
            inp = QLineEdit(self._class_names_container)
            inp.setPlaceholderText(f"class_{i}")
            inp.setFixedHeight(32)
            inp.setStyleSheet(INPUT_STYLE)
            if i < len(existing_names) and existing_names[i]:
                inp.setText(existing_names[i])
            row, col = divmod(i, 2)
            self._class_names_grid.addWidget(inp, row, col)
            self._class_name_inputs.append(inp)

        # Resize the container to fit the inputs
        rows = max(1, (n + 1) // 2)
        self._class_names_container.setFixedHeight(rows * 40 + 8)

    def _saveClassConfig(self):
        """Save class names to class_config.json."""
        names = [inp.text() or inp.placeholderText() for inp in self._class_name_inputs]
        data = {"num_classes": len(names), "class_names": names}
        try:
            os.makedirs(os.path.dirname(self._class_config_path), exist_ok=True)
            with open(self._class_config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._showNotification("Saved", "Class configuration saved.", 1)
        except Exception as e:
            self._showNotification("Error", f"Failed to save: {e}", 3)

    def _loadClassConfig(self):
        """Load class names from class_config.json."""
        try:
            if os.path.exists(self._class_config_path):
                with open(self._class_config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                n = data.get("num_classes", self.num_classes.value())
                names = data.get("class_names", [])
                self.num_classes.setValue(n)
                self._updateClassNameInputs(n, names)
                return
        except Exception:
            pass
        # Fallback: use current num_classes with empty names
        self._updateClassNameInputs(self.num_classes.value())

    def _showNotification(self, title: str, text: str, msg_type: int = 1):
        try:
            app = self.window()
            if hasattr(app, 'LayerRightMessageSidebar'):
                app.LayerRightMessageSidebar().send(title=title, text=text, msg_type=msg_type, fold_after=3000)
        except Exception:
            pass

    # ── Section 4: Training Parameters ─────────────────────────────

    def _createTrainingParamsSection(self):
        self.titled_group.addTitle("Training Parameters")

        # Core parameters
        core_card = SiTriSectionFlatCard(self)
        core_card.setTitle("Core")

        core_row = SiDenseHContainer(self)
        core_row.setSpacing(24)
        core_row.setFixedHeight(90)

        self.epochs = SiSliderSpinBox(self)
        self.epochs.setTitle("Epochs")
        self.epochs.resize(200, 84)
        self.epochs.setMinimum(1)
        self.epochs.setMaximum(5000)
        self.epochs.setSingleStep(10)
        self.epochs.setValue(DEFAULTS["epochs"])
        core_row.addWidget(self.epochs, side="left")

        self.batch_size = SiSliderSpinBox(self)
        self.batch_size.setTitle("Batch Size")
        self.batch_size.resize(200, 84)
        self.batch_size.setMinimum(1)
        self.batch_size.setMaximum(128)
        self.batch_size.setSingleStep(1)
        self.batch_size.setValue(DEFAULTS["batch_size"])
        core_row.addWidget(self.batch_size, side="left")

        self.num_workers = SiSliderSpinBox(self)
        self.num_workers.setTitle("Workers")
        self.num_workers.resize(200, 84)
        self.num_workers.setMinimum(0)
        self.num_workers.setMaximum(16)
        self.num_workers.setSingleStep(1)
        self.num_workers.setValue(DEFAULTS["num_workers"])
        core_row.addWidget(self.num_workers, side="left")

        self.learning_rate = SiSliderDoubleSpinBox(self)
        self.learning_rate.setTitle("Learning Rate")
        self.learning_rate.resize(200, 84)
        self.learning_rate.setMinimum(0.0001)
        self.learning_rate.setMaximum(0.1)
        self.learning_rate.setSingleStep(0.001)
        self.learning_rate.setDecimals(4)
        self.learning_rate.setValue(DEFAULTS["learning_rate"])
        core_row.addWidget(self.learning_rate, side="left")

        core_card.body().addWidget(core_row)
        core_card.adjustSize()
        self.titled_group.addWidget(core_card)

        # Optimizer parameters
        opt_card = SiTriSectionFlatCard(self)
        opt_card.setTitle("Optimizer (SGD)")

        opt_row = SiDenseHContainer(self)
        opt_row.setSpacing(24)
        opt_row.setFixedHeight(90)

        self.weight_decay = SiSliderDoubleSpinBox(self)
        self.weight_decay.setTitle("Weight Decay")
        self.weight_decay.resize(200, 84)
        self.weight_decay.setMinimum(0.0)
        self.weight_decay.setMaximum(0.01)
        self.weight_decay.setSingleStep(0.0001)
        self.weight_decay.setDecimals(4)
        self.weight_decay.setValue(DEFAULTS["weight_decay"])
        opt_row.addWidget(self.weight_decay, side="left")

        self.momentum = SiSliderDoubleSpinBox(self)
        self.momentum.setTitle("Momentum")
        self.momentum.resize(200, 84)
        self.momentum.setMinimum(0.8)
        self.momentum.setMaximum(0.999)
        self.momentum.setSingleStep(0.01)
        self.momentum.setDecimals(3)
        self.momentum.setValue(DEFAULTS["momentum"])
        opt_row.addWidget(self.momentum, side="left")

        opt_card.body().addWidget(opt_row)
        opt_card.adjustSize()
        self.titled_group.addWidget(opt_card)

        # LR Schedule & Early Stopping
        sched_card = SiTriSectionFlatCard(self)
        sched_card.setTitle("LR Schedule & Early Stopping")

        sched_row1 = SiDenseHContainer(self)
        sched_row1.setSpacing(16)
        sched_row1.setFixedHeight(36)

        cos_label = SiLabel(self)
        cos_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        cos_label.setFont(SiFont.getFont(size=13))
        cos_label.setTextColor(self.getColor(SiColor.TEXT_D))
        cos_label.setText("Cosine Annealing LR")
        sched_row1.addWidget(cos_label, side="left")

        self.use_cos_lr = SiSwitch(self)
        self.use_cos_lr.setChecked(DEFAULTS["use_cos_lr"])
        sched_row1.addWidget(self.use_cos_lr, side="right")

        sched_card.body().addWidget(sched_row1)

        sched_row2 = SiDenseHContainer(self)
        sched_row2.setSpacing(24)
        sched_row2.setFixedHeight(90)

        self.warmup_epochs = SiSliderSpinBox(self)
        self.warmup_epochs.setTitle("Warmup Epochs")
        self.warmup_epochs.resize(200, 84)
        self.warmup_epochs.setMinimum(0)
        self.warmup_epochs.setMaximum(20)
        self.warmup_epochs.setSingleStep(1)
        self.warmup_epochs.setValue(DEFAULTS["warmup_epochs"])
        sched_row2.addWidget(self.warmup_epochs, side="left")

        self.patience = SiSliderSpinBox(self)
        self.patience.setTitle("Early Stop Patience")
        self.patience.resize(200, 84)
        self.patience.setMinimum(0)
        self.patience.setMaximum(500)
        self.patience.setSingleStep(5)
        self.patience.setValue(DEFAULTS["patience"])
        sched_row2.addWidget(self.patience, side="left")

        self.save_period = SiSliderSpinBox(self)
        self.save_period.setTitle("Save Period (epochs)")
        self.save_period.resize(200, 84)
        self.save_period.setMinimum(1)
        self.save_period.setMaximum(100)
        self.save_period.setSingleStep(1)
        self.save_period.setValue(DEFAULTS["save_period"])
        sched_row2.addWidget(self.save_period, side="left")

        sched_card.body().addWidget(sched_row2)
        sched_card.adjustSize()
        self.titled_group.addWidget(sched_card)

    # ── Section 4: Data Augmentation ───────────────────────────────

    def _createAugmentationSection(self):
        self.titled_group.addTitle("Data Augmentation")

        # 1. Resolution Reduce
        res_card = SiTriSectionFlatCard(self)
        res_card.setTitle("Resolution Reduce")

        res_switch_row = SiDenseHContainer(self)
        res_switch_row.setSpacing(16)
        res_switch_row.setFixedHeight(36)
        res_en_label = SiLabel(self)
        res_en_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        res_en_label.setFont(SiFont.getFont(size=13))
        res_en_label.setTextColor(self.getColor(SiColor.TEXT_D))
        res_en_label.setText("Enable")
        res_switch_row.addWidget(res_en_label, side="left")
        self.use_resolution_reduce = SiSwitch(self)
        self.use_resolution_reduce.setChecked(DEFAULTS["use_resolution_reduce"])
        res_switch_row.addWidget(self.use_resolution_reduce, side="right")
        res_card.body().addWidget(res_switch_row)

        res_row = SiDenseHContainer(self)
        res_row.setSpacing(24)
        res_row.setFixedHeight(90)

        self.resolution_min_scale = SiSliderDoubleSpinBox(self)
        self.resolution_min_scale.setTitle("Min Scale")
        self.resolution_min_scale.resize(200, 84)
        self.resolution_min_scale.setMinimum(0.1)
        self.resolution_min_scale.setMaximum(1.0)
        self.resolution_min_scale.setSingleStep(0.05)
        self.resolution_min_scale.setDecimals(2)
        self.resolution_min_scale.setValue(DEFAULTS["resolution_min_scale"])
        res_row.addWidget(self.resolution_min_scale, side="left")

        self.resolution_max_scale = SiSliderDoubleSpinBox(self)
        self.resolution_max_scale.setTitle("Max Scale")
        self.resolution_max_scale.resize(200, 84)
        self.resolution_max_scale.setMinimum(0.1)
        self.resolution_max_scale.setMaximum(1.0)
        self.resolution_max_scale.setSingleStep(0.05)
        self.resolution_max_scale.setDecimals(2)
        self.resolution_max_scale.setValue(DEFAULTS["resolution_max_scale"])
        res_row.addWidget(self.resolution_max_scale, side="left")

        self.resolution_prob = SiSliderDoubleSpinBox(self)
        self.resolution_prob.setTitle("Probability")
        self.resolution_prob.resize(200, 84)
        self.resolution_prob.setMinimum(0.0)
        self.resolution_prob.setMaximum(1.0)
        self.resolution_prob.setSingleStep(0.05)
        self.resolution_prob.setDecimals(2)
        self.resolution_prob.setValue(DEFAULTS["resolution_prob"])
        res_row.addWidget(self.resolution_prob, side="left")

        res_card.body().addWidget(res_row)
        res_card.adjustSize()
        self.titled_group.addWidget(res_card)

        # 2. Color Jitter (HSV)
        color_card = SiTriSectionFlatCard(self)
        color_card.setTitle("Color Jitter (HSV)")

        color_switch_row = SiDenseHContainer(self)
        color_switch_row.setSpacing(16)
        color_switch_row.setFixedHeight(36)
        color_en_label = SiLabel(self)
        color_en_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        color_en_label.setFont(SiFont.getFont(size=13))
        color_en_label.setTextColor(self.getColor(SiColor.TEXT_D))
        color_en_label.setText("Enable")
        color_switch_row.addWidget(color_en_label, side="left")
        self.use_color_jitter = SiSwitch(self)
        self.use_color_jitter.setChecked(DEFAULTS["use_color_jitter"])
        color_switch_row.addWidget(self.use_color_jitter, side="right")
        color_card.body().addWidget(color_switch_row)

        color_row = SiDenseHContainer(self)
        color_row.setSpacing(24)
        color_row.setFixedHeight(90)

        self.hsv_h = SiSliderDoubleSpinBox(self)
        self.hsv_h.setTitle("Hue (H)")
        self.hsv_h.resize(200, 84)
        self.hsv_h.setMinimum(0.0)
        self.hsv_h.setMaximum(0.1)
        self.hsv_h.setSingleStep(0.005)
        self.hsv_h.setDecimals(3)
        self.hsv_h.setValue(DEFAULTS["hsv_h"])
        color_row.addWidget(self.hsv_h, side="left")

        self.hsv_s = SiSliderDoubleSpinBox(self)
        self.hsv_s.setTitle("Saturation (S)")
        self.hsv_s.resize(200, 84)
        self.hsv_s.setMinimum(0.0)
        self.hsv_s.setMaximum(1.0)
        self.hsv_s.setSingleStep(0.05)
        self.hsv_s.setDecimals(2)
        self.hsv_s.setValue(DEFAULTS["hsv_s"])
        color_row.addWidget(self.hsv_s, side="left")

        self.hsv_v = SiSliderDoubleSpinBox(self)
        self.hsv_v.setTitle("Value (V)")
        self.hsv_v.resize(200, 84)
        self.hsv_v.setMinimum(0.0)
        self.hsv_v.setMaximum(1.0)
        self.hsv_v.setSingleStep(0.05)
        self.hsv_v.setDecimals(2)
        self.hsv_v.setValue(DEFAULTS["hsv_v"])
        color_row.addWidget(self.hsv_v, side="left")

        color_card.body().addWidget(color_row)
        color_card.adjustSize()
        self.titled_group.addWidget(color_card)

        # 3. Geometric
        geo_card = SiTriSectionFlatCard(self)
        geo_card.setTitle("Geometric Transforms")

        geo_switch_row = SiDenseHContainer(self)
        geo_switch_row.setSpacing(16)
        geo_switch_row.setFixedHeight(36)
        geo_en_label = SiLabel(self)
        geo_en_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        geo_en_label.setFont(SiFont.getFont(size=13))
        geo_en_label.setTextColor(self.getColor(SiColor.TEXT_D))
        geo_en_label.setText("Enable")
        geo_switch_row.addWidget(geo_en_label, side="left")
        self.use_geometric = SiSwitch(self)
        self.use_geometric.setChecked(DEFAULTS["use_geometric"])
        geo_switch_row.addWidget(self.use_geometric, side="right")
        geo_card.body().addWidget(geo_switch_row)

        geo_row1 = SiDenseHContainer(self)
        geo_row1.setSpacing(24)
        geo_row1.setFixedHeight(90)

        self.flip_lr = SiSliderDoubleSpinBox(self)
        self.flip_lr.setTitle("Flip LR Prob")
        self.flip_lr.resize(180, 84)
        self.flip_lr.setMinimum(0.0)
        self.flip_lr.setMaximum(1.0)
        self.flip_lr.setSingleStep(0.05)
        self.flip_lr.setDecimals(2)
        self.flip_lr.setValue(DEFAULTS["flip_lr"])
        geo_row1.addWidget(self.flip_lr, side="left")

        self.flip_ud = SiSliderDoubleSpinBox(self)
        self.flip_ud.setTitle("Flip UD Prob")
        self.flip_ud.resize(180, 84)
        self.flip_ud.setMinimum(0.0)
        self.flip_ud.setMaximum(1.0)
        self.flip_ud.setSingleStep(0.05)
        self.flip_ud.setDecimals(2)
        self.flip_ud.setValue(DEFAULTS["flip_ud"])
        geo_row1.addWidget(self.flip_ud, side="left")

        self.rotate_degree = SiSliderSpinBox(self)
        self.rotate_degree.setTitle("Rotate Degree")
        self.rotate_degree.resize(180, 84)
        self.rotate_degree.setMinimum(0)
        self.rotate_degree.setMaximum(180)
        self.rotate_degree.setSingleStep(5)
        self.rotate_degree.setValue(DEFAULTS["rotate_degree"])
        geo_row1.addWidget(self.rotate_degree, side="left")

        self.rotate_prob = SiSliderDoubleSpinBox(self)
        self.rotate_prob.setTitle("Rotate Prob")
        self.rotate_prob.resize(180, 84)
        self.rotate_prob.setMinimum(0.0)
        self.rotate_prob.setMaximum(1.0)
        self.rotate_prob.setSingleStep(0.05)
        self.rotate_prob.setDecimals(2)
        self.rotate_prob.setValue(DEFAULTS["rotate_prob"])
        geo_row1.addWidget(self.rotate_prob, side="left")

        geo_card.body().addWidget(geo_row1)

        geo_row2 = SiDenseHContainer(self)
        geo_row2.setSpacing(24)
        geo_row2.setFixedHeight(90)

        self.scale_min = SiSliderDoubleSpinBox(self)
        self.scale_min.setTitle("Scale Min")
        self.scale_min.resize(200, 84)
        self.scale_min.setMinimum(0.1)
        self.scale_min.setMaximum(1.0)
        self.scale_min.setSingleStep(0.05)
        self.scale_min.setDecimals(2)
        self.scale_min.setValue(DEFAULTS["scale_min"])
        geo_row2.addWidget(self.scale_min, side="left")

        self.scale_max = SiSliderDoubleSpinBox(self)
        self.scale_max.setTitle("Scale Max")
        self.scale_max.resize(200, 84)
        self.scale_max.setMinimum(1.0)
        self.scale_max.setMaximum(2.0)
        self.scale_max.setSingleStep(0.05)
        self.scale_max.setDecimals(2)
        self.scale_max.setValue(DEFAULTS["scale_max"])
        geo_row2.addWidget(self.scale_max, side="left")

        self.scale_prob = SiSliderDoubleSpinBox(self)
        self.scale_prob.setTitle("Scale Prob")
        self.scale_prob.resize(200, 84)
        self.scale_prob.setMinimum(0.0)
        self.scale_prob.setMaximum(1.0)
        self.scale_prob.setSingleStep(0.05)
        self.scale_prob.setDecimals(2)
        self.scale_prob.setValue(DEFAULTS["scale_prob"])
        geo_row2.addWidget(self.scale_prob, side="left")

        geo_card.body().addWidget(geo_row2)
        geo_card.adjustSize()
        self.titled_group.addWidget(geo_card)

        # 4. Noise & Blur
        noise_card = SiTriSectionFlatCard(self)
        noise_card.setTitle("Noise & Blur")

        noise_switch_row = SiDenseHContainer(self)
        noise_switch_row.setSpacing(16)
        noise_switch_row.setFixedHeight(36)
        noise_en_label = SiLabel(self)
        noise_en_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        noise_en_label.setFont(SiFont.getFont(size=13))
        noise_en_label.setTextColor(self.getColor(SiColor.TEXT_D))
        noise_en_label.setText("Enable")
        noise_switch_row.addWidget(noise_en_label, side="left")
        self.use_noise_blur = SiSwitch(self)
        self.use_noise_blur.setChecked(DEFAULTS["use_noise_blur"])
        noise_switch_row.addWidget(self.use_noise_blur, side="right")
        noise_card.body().addWidget(noise_switch_row)

        noise_row = SiDenseHContainer(self)
        noise_row.setSpacing(24)
        noise_row.setFixedHeight(90)

        self.gaussian_noise_prob = SiSliderDoubleSpinBox(self)
        self.gaussian_noise_prob.setTitle("Gaussian Prob")
        self.gaussian_noise_prob.resize(180, 84)
        self.gaussian_noise_prob.setMinimum(0.0)
        self.gaussian_noise_prob.setMaximum(1.0)
        self.gaussian_noise_prob.setSingleStep(0.05)
        self.gaussian_noise_prob.setDecimals(2)
        self.gaussian_noise_prob.setValue(DEFAULTS["gaussian_noise_prob"])
        noise_row.addWidget(self.gaussian_noise_prob, side="left")

        self.gaussian_noise_std = SiSliderDoubleSpinBox(self)
        self.gaussian_noise_std.setTitle("Gaussian Std")
        self.gaussian_noise_std.resize(180, 84)
        self.gaussian_noise_std.setMinimum(0.0)
        self.gaussian_noise_std.setMaximum(50.0)
        self.gaussian_noise_std.setSingleStep(1.0)
        self.gaussian_noise_std.setDecimals(1)
        self.gaussian_noise_std.setValue(DEFAULTS["gaussian_noise_std"])
        noise_row.addWidget(self.gaussian_noise_std, side="left")

        self.motion_blur_prob = SiSliderDoubleSpinBox(self)
        self.motion_blur_prob.setTitle("Motion Blur Prob")
        self.motion_blur_prob.resize(180, 84)
        self.motion_blur_prob.setMinimum(0.0)
        self.motion_blur_prob.setMaximum(1.0)
        self.motion_blur_prob.setSingleStep(0.05)
        self.motion_blur_prob.setDecimals(2)
        self.motion_blur_prob.setValue(DEFAULTS["motion_blur_prob"])
        noise_row.addWidget(self.motion_blur_prob, side="left")

        noise_card.body().addWidget(noise_row)

        noise_row2 = SiDenseHContainer(self)
        noise_row2.setSpacing(24)
        noise_row2.setFixedHeight(90)

        self.motion_blur_kernel_min = SiSliderSpinBox(self)
        self.motion_blur_kernel_min.setTitle("Blur Kernel Min")
        self.motion_blur_kernel_min.resize(200, 84)
        self.motion_blur_kernel_min.setMinimum(3)
        self.motion_blur_kernel_min.setMaximum(15)
        self.motion_blur_kernel_min.setSingleStep(2)
        self.motion_blur_kernel_min.setValue(DEFAULTS["motion_blur_kernel_min"])
        noise_row2.addWidget(self.motion_blur_kernel_min, side="left")

        self.motion_blur_kernel_max = SiSliderSpinBox(self)
        self.motion_blur_kernel_max.setTitle("Blur Kernel Max")
        self.motion_blur_kernel_max.resize(200, 84)
        self.motion_blur_kernel_max.setMinimum(3)
        self.motion_blur_kernel_max.setMaximum(21)
        self.motion_blur_kernel_max.setSingleStep(2)
        self.motion_blur_kernel_max.setValue(DEFAULTS["motion_blur_kernel_max"])
        noise_row2.addWidget(self.motion_blur_kernel_max, side="left")

        noise_card.body().addWidget(noise_row2)
        noise_card.adjustSize()
        self.titled_group.addWidget(noise_card)

        # 5. Mosaic
        mosaic_card = SiTriSectionFlatCard(self)
        mosaic_card.setTitle("Mosaic")

        mosaic_switch_row = SiDenseHContainer(self)
        mosaic_switch_row.setSpacing(16)
        mosaic_switch_row.setFixedHeight(36)
        mosaic_en_label = SiLabel(self)
        mosaic_en_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        mosaic_en_label.setFont(SiFont.getFont(size=13))
        mosaic_en_label.setTextColor(self.getColor(SiColor.TEXT_D))
        mosaic_en_label.setText("Enable")
        mosaic_switch_row.addWidget(mosaic_en_label, side="left")
        self.use_mosaic = SiSwitch(self)
        self.use_mosaic.setChecked(DEFAULTS["use_mosaic"])
        mosaic_switch_row.addWidget(self.use_mosaic, side="right")
        mosaic_card.body().addWidget(mosaic_switch_row)

        mosaic_row = SiDenseHContainer(self)
        mosaic_row.setSpacing(24)
        mosaic_row.setFixedHeight(90)

        self.mosaic_prob = SiSliderDoubleSpinBox(self)
        self.mosaic_prob.setTitle("Probability")
        self.mosaic_prob.resize(200, 84)
        self.mosaic_prob.setMinimum(0.0)
        self.mosaic_prob.setMaximum(1.0)
        self.mosaic_prob.setSingleStep(0.05)
        self.mosaic_prob.setDecimals(2)
        self.mosaic_prob.setValue(DEFAULTS["mosaic_prob"])
        mosaic_row.addWidget(self.mosaic_prob, side="left")

        mosaic_card.body().addWidget(mosaic_row)
        mosaic_card.adjustSize()
        self.titled_group.addWidget(mosaic_card)

    # ── Section 5: Performance ─────────────────────────────────────

    def _createPerformanceSection(self):
        self.titled_group.addTitle("Performance")

        # AMP
        self.amp_card = SiOptionCardLinear(self)
        self.amp_card.setTitle("Mixed Precision (AMP)", "Faster training with lower memory usage")
        self.amp_card.load(SiGlobal.siui.iconpack.get("ic_fluent_flash_filled"))
        self.use_amp = SiSwitch(self)
        self.use_amp.setChecked(DEFAULTS["use_amp"])
        self.amp_card.addWidget(self.use_amp)
        self.titled_group.addWidget(self.amp_card)

        # Cache
        self.cache_card = SiOptionCardLinear(self)
        self.cache_card.setTitle("Image Cache", "Load all images into memory (small datasets only)")
        self.cache_card.load(SiGlobal.siui.iconpack.get("ic_fluent_database_filled"))
        self.cache_images = SiSwitch(self)
        self.cache_images.setChecked(DEFAULTS["cache_images"])
        self.cache_card.addWidget(self.cache_images)
        self.titled_group.addWidget(self.cache_card)

        # Grad accumulation
        perf_card = SiTriSectionFlatCard(self)
        perf_card.setTitle("Gradient Accumulation")

        perf_row = SiDenseHContainer(self)
        perf_row.setSpacing(24)
        perf_row.setFixedHeight(90)

        self.accumulate_grad = SiSliderSpinBox(self)
        self.accumulate_grad.setTitle("Accumulation Steps")
        self.accumulate_grad.resize(200, 84)
        self.accumulate_grad.setMinimum(1)
        self.accumulate_grad.setMaximum(16)
        self.accumulate_grad.setSingleStep(1)
        self.accumulate_grad.setValue(DEFAULTS["accumulate_grad"])
        perf_row.addWidget(self.accumulate_grad, side="left")

        perf_card.body().addWidget(perf_row)
        perf_card.adjustSize()
        self.titled_group.addWidget(perf_card)

    # ── Section 6: Training Control & Progress ─────────────────────

    def _createTrainingControlSection(self):
        self.titled_group.addTitle("Training")

        # Save directory
        self.save_dir_card = SiOptionCardLinear(self)
        self.save_dir_card.setTitle("Save Directory", "Where to save training results")
        self.save_dir_card.load(SiGlobal.siui.iconpack.get("ic_fluent_folder_filled"))

        self.save_dir_label = SiLabel(self)
        self.save_dir_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.save_dir_label.setFont(SiFont.getFont(size=12))
        self.save_dir_label.setTextColor(self.getColor(SiColor.TEXT_D))
        self.save_dir_label.setText(self._user_models_dir)
        self.save_dir_card.addWidget(self.save_dir_label)

        self.btn_browse_save_dir = SiFlatButton(self)
        self.btn_browse_save_dir.setFixedSize(32, 32)
        self.btn_browse_save_dir.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_folder_open_filled"))
        self.btn_browse_save_dir.setToolTip("Browse save directory")
        self.btn_browse_save_dir.clicked.connect(self._onBrowseSaveDir)
        self.save_dir_card.addWidget(self.btn_browse_save_dir)
        self.titled_group.addWidget(self.save_dir_card)

        # Start / Stop buttons
        btn_row = SiDenseHContainer(self)
        btn_row.setFixedHeight(40)
        btn_row.setSpacing(8)

        self.btn_start = SiFlatButton(self)
        self.btn_start.setFixedSize(32, 32)
        self.btn_start.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_play_filled"))
        self.btn_start.setToolTip("Start training")
        self.btn_start.clicked.connect(self._onStartTraining)
        btn_row.addWidget(self.btn_start, side="left")

        self.btn_stop = SiFlatButton(self)
        self.btn_stop.setFixedSize(32, 32)
        self.btn_stop.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_stop_filled"))
        self.btn_stop.setToolTip("Stop training")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._onStopTraining)
        btn_row.addWidget(self.btn_stop, side="left")

        self.status_label = SiLabel(self)
        self.status_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.status_label.setFont(SiFont.getFont(size=13))
        self.status_label.setTextColor(self.getColor(SiColor.TEXT_D))
        self.status_label.setText("Ready")
        btn_row.addWidget(self.status_label, side="left")

        self.titled_group.addWidget(btn_row)

        # Progress bar
        self.progress_bar = SiProgressBar(self)
        self.progress_bar.setFixedHeight(6)
        self.titled_group.addWidget(self.progress_bar)

        # Charts
        chart_card = SiTriSectionFlatCard(self)
        chart_card.setTitle("Training Progress")

        # Loss chart
        loss_label = SiLabel(self)
        loss_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        loss_label.setFont(SiFont.getFont(size=12))
        loss_label.setTextColor(self.getColor(SiColor.TEXT_D))
        loss_label.setText("Loss")
        chart_card.body().addWidget(loss_label)

        self.loss_chart = SiTrendChart(self)
        self.loss_chart.setFixedHeight(200)
        self.loss_chart.setXTickNameFunc(lambda x: f"{int(x)}")
        self.loss_chart.setYTickNameFunc(lambda y: f"{y:.3f}")
        self.loss_chart.setToolTipFunc(lambda x, y: f"Epoch {int(x)}\nLoss: {y:.4f}")
        self.loss_chart.setPointList([QPointF(0, 0)])
        self.loss_chart.setViewRect(QRectF(0, 0, 100, 1))
        chart_card.body().addWidget(self.loss_chart)

        # mAP chart
        map_label = SiLabel(self)
        map_label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        map_label.setFont(SiFont.getFont(size=12))
        map_label.setTextColor(self.getColor(SiColor.TEXT_D))
        map_label.setText("mAP@0.5")
        chart_card.body().addWidget(map_label)

        self.map_chart = SiTrendChart(self)
        self.map_chart.setFixedHeight(200)
        self.map_chart.setXTickNameFunc(lambda x: f"{int(x)}")
        self.map_chart.setYTickNameFunc(lambda y: f"{y:.2f}")
        self.map_chart.setToolTipFunc(lambda x, y: f"Epoch {int(x)}\nmAP@0.5: {y:.4f}")
        self.map_chart.setPointList([QPointF(0, 0)])
        self.map_chart.setViewRect(QRectF(0, 0, 100, 1))
        chart_card.body().addWidget(self.map_chart)

        chart_card.adjustSize()
        self.titled_group.addWidget(chart_card)

        # Console log
        self.console = QTextEdit(self)
        self.console.setReadOnly(True)
        self.console.setFixedHeight(250)
        self.console.setStyleSheet(CONSOLE_STYLE)
        self.titled_group.addWidget(self.console)

    # ── Browse Handlers ────────────────────────────────────────────

    def _onBrowseDataset(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Dataset YAML", "", "YAML Files (*.yaml *.yml)"
        )
        if path:
            self.dataset_path_label.setText(os.path.basename(path))
            self.dataset_path_label.setToolTip(path)
            self._dataset_yaml_path = path
            self.dataset_browser.loadDataset(path)
            self._updateDatasetStats()

    def _onBrowseWeights(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Pretrained Weights", "", "PyTorch Models (*.pt)"
        )
        if path:
            self.weights_path_label.setText(os.path.basename(path))
            self.weights_path_label.setToolTip(path)
            self._weights_path = path

    def _onBrowseSaveDir(self):
        path = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if path:
            self.save_dir_label.setText(path)
            self.save_dir_label.setToolTip(path)

    def _updateDatasetStats(self):
        info = self.dataset_browser.getDatasetInfo()
        if info:
            classes = ", ".join(info.get("class_names", []))
            total = info.get("total_images", 0)
            self.stats_label.setText(f"{total} images | Classes: {classes}")

            # Auto-set num_classes and class names from dataset
            dataset_class_names = info.get("class_names", [])
            nc = len(dataset_class_names)
            if nc > 0:
                self.num_classes.setValue(nc)
                self._updateClassNameInputs(nc, dataset_class_names)

    # ── Training Control ───────────────────────────────────────────

    def _collectConfig(self):
        """Collect all parameter values into a config dict."""
        config = {}

        # Dataset
        config["data_yaml"] = getattr(self, "_dataset_yaml_path", "")

        # Model
        config["pretrained_weights"] = getattr(self, "_weights_path", "")
        config["img_size"] = self.img_size.value()
        config["num_classes"] = self.num_classes.value()

        # Training
        config["epochs"] = self.epochs.value()
        config["batch_size"] = self.batch_size.value()
        config["num_workers"] = self.num_workers.value()
        config["learning_rate"] = self.learning_rate.value()
        config["weight_decay"] = self.weight_decay.value()
        config["momentum"] = self.momentum.value()

        # LR Schedule
        config["use_cos_lr"] = self.use_cos_lr.isChecked()
        config["warmup_epochs"] = self.warmup_epochs.value()
        config["patience"] = self.patience.value()
        config["save_period"] = self.save_period.value()

        # Augmentation
        config["use_resolution_reduce"] = self.use_resolution_reduce.isChecked()
        config["resolution_min_scale"] = self.resolution_min_scale.value()
        config["resolution_max_scale"] = self.resolution_max_scale.value()
        config["resolution_prob"] = self.resolution_prob.value()

        config["use_color_jitter"] = self.use_color_jitter.isChecked()
        config["hsv_h"] = self.hsv_h.value()
        config["hsv_s"] = self.hsv_s.value()
        config["hsv_v"] = self.hsv_v.value()

        config["use_geometric"] = self.use_geometric.isChecked()
        config["flip_lr"] = self.flip_lr.value()
        config["flip_ud"] = self.flip_ud.value()
        config["rotate_degree"] = self.rotate_degree.value()
        config["rotate_prob"] = self.rotate_prob.value()
        config["scale_min"] = self.scale_min.value()
        config["scale_max"] = self.scale_max.value()
        config["scale_prob"] = self.scale_prob.value()

        config["use_noise_blur"] = self.use_noise_blur.isChecked()
        config["gaussian_noise_prob"] = self.gaussian_noise_prob.value()
        config["gaussian_noise_std"] = self.gaussian_noise_std.value()
        config["motion_blur_prob"] = self.motion_blur_prob.value()
        config["motion_blur_kernel_min"] = self.motion_blur_kernel_min.value()
        config["motion_blur_kernel_max"] = self.motion_blur_kernel_max.value()

        config["use_mosaic"] = self.use_mosaic.isChecked()
        config["mosaic_prob"] = self.mosaic_prob.value()

        # Performance
        config["use_amp"] = self.use_amp.isChecked()
        config["cache_images"] = self.cache_images.isChecked()
        config["accumulate_grad"] = self.accumulate_grad.value()

        # Save
        config["save_dir"] = self.save_dir_label.text()
        config["exp_name"] = DEFAULTS["exp_name"]

        return config

    def _onStartTraining(self):
        config = self._collectConfig()

        if not config["data_yaml"]:
            self._showNotification("Error", "Please select a dataset YAML file.", 3)
            return

        # Reset charts
        self._loss_points.clear()
        self._map50_points.clear()
        self._last_epoch = 0
        self.loss_chart.setPointList([QPointF(0, 0)])
        self.map_chart.setPointList([QPointF(0, 0)])
        self.console.clear()

        # Update UI state
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_label.setText("Starting training...")
        self.progress_bar.setValue(0)
        self.progress_bar.setState("processing")

        self._training_manager.start_training(config)

    def _onStopTraining(self):
        self._training_manager.stop_training()
        self.status_label.setText("Stopping...")
        self.btn_stop.setEnabled(False)

    # ── Training Callbacks ─────────────────────────────────────────

    def _onProgressUpdated(self, data):
        epoch = data.get("epoch", 0)
        total = data.get("total", 1)
        loss = data.get("loss", 0)

        # Update progress bar (0-1 range)
        progress = epoch / total if total > 0 else 0
        self.progress_bar.setValue(progress)

        self.status_label.setText(f"Epoch {epoch}/{total} | Loss: {loss:.4f}")

        # Add loss point to chart
        if epoch > self._last_epoch:
            self._last_epoch = epoch
            self._loss_points.append(QPointF(epoch, loss))

            if len(self._loss_points) >= 2:
                self.loss_chart.setPointList(list(self._loss_points))
                self._autoAdjustChart(self.loss_chart, self._loss_points)

    def _onMapUpdated(self, data):
        epoch = self._last_epoch
        map50 = data.get("mAP50", 0)

        self._map50_points.append(QPointF(epoch, map50))

        if len(self._map50_points) >= 2:
            self.map_chart.setPointList(list(self._map50_points))
            self._autoAdjustChart(self.map_chart, self._map50_points)

    def _onLogOutput(self, line):
        self.console.append(line.rstrip())
        # Auto-scroll to bottom
        scrollbar = self.console.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _onTrainingFinished(self, exit_code):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        if exit_code == 0:
            self.status_label.setText("Training completed!")
            self.progress_bar.setState("completing")
            self._showNotification("Training Complete", "Model training finished successfully.", 1)
        else:
            self.status_label.setText(f"Training stopped (code: {exit_code})")
            self.progress_bar.setState("paused")

    def _onTrainingError(self, msg):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.status_label.setText("Training error!")
        self.progress_bar.setState("paused")
        self._showNotification("Training Error", msg, 3)

    # ── Helpers ────────────────────────────────────────────────────

    def _autoAdjustChart(self, chart, points):
        if len(points) < 2:
            return
        xs = [p.x() for p in points]
        ys = [p.y() for p in points]
        y_min, y_max = min(ys), max(ys)
        margin = (y_max - y_min) * 0.1 or 0.1
        chart.setViewRect(QRectF(
            min(xs), y_min - margin,
            max(xs) - min(xs) or 1,
            (y_max - y_min) + 2 * margin or 1
        ))

    def _showNotification(self, title, text, msg_type):
        try:
            self.window().LayerRightMessageSidebar().send(
                title=title, text=text, msg_type=msg_type, fold_after=4000
            )
        except Exception:
            pass
