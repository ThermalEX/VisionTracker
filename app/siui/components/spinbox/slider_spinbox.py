"""
SiSliderSpinBox - SpinBox with slider for both sliding and manual input
"""

from PyQt5.QtCore import Qt, pyqtSignal

from siui.components.widgets import SiLabel
from siui.components.widgets.abstracts import SiSimpleLineEdit, SiWidget
from siui.components.slider.slider import SiSliderH
from siui.core import SiColor, GlobalFont
from siui.gui import SiFont


class SiSliderSpinBox(SiWidget):
    """SpinBox with horizontal slider - vertical layout"""
    valueChanged = pyqtSignal(int)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._minimum = 0
        self._maximum = 100
        self._value = 0
        self._single_step = 1
        self._title = ""

        # Title label
        self.title_label = SiLabel(self)
        self.title_label.setFont(SiFont.tokenized(GlobalFont.S_NORMAL))
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setFixedHeight(20)

        # Slider
        self.slider = SiSliderH(self)
        self.slider.setFixedHeight(24)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setSingleStep(1)
        self.slider.valueChanged.connect(self._onSliderChanged)

        # Value input
        self.input_panel = SiLabel(self)
        self.input_panel.setFixedStyleSheet("border-radius: 4px")

        self.line_edit = SiSimpleLineEdit(self.input_panel)
        self.line_edit.setAlignment(Qt.AlignCenter)
        self.line_edit.setFont(SiFont.tokenized(GlobalFont.S_NORMAL))
        self.line_edit.editingFinished.connect(self._onEditFinished)

    def setTitle(self, title: str):
        self._title = title
        self.title_label.setText(title)

    def title(self) -> str:
        return self._title

    def setHint(self, hint: str):
        """Set tooltip for the title label"""
        self.title_label.setHint(hint)

    def setMinimum(self, minimum: int):
        self._minimum = minimum
        self.slider.setMinimum(minimum)
        # Keep slider singleStep as 1 to avoid SiSliderH position calculation bug
        self.slider.setSingleStep(1)

    def minimum(self) -> int:
        return self._minimum

    def setMaximum(self, maximum: int):
        self._maximum = maximum
        self.slider.setMaximum(maximum)
        # Keep slider singleStep as 1 to avoid SiSliderH position calculation bug
        self.slider.setSingleStep(1)

    def maximum(self) -> int:
        return self._maximum

    def setSingleStep(self, step: int):
        self._single_step = step
        # Note: We don't change slider's singleStep because SiSliderH has a bug
        # when singleStep != 1. The spinbox's singleStep is only for manual input.

    def singleStep(self) -> int:
        return self._single_step

    def setValue(self, value: int):
        value = max(self._minimum, min(self._maximum, value))
        old_value = self._value
        self._value = value
        # Always update slider and line_edit
        self.slider.setValue(value, move_to=False)
        self.line_edit.setText(str(value))
        if value != old_value:
            self.valueChanged.emit(value)

    def value(self) -> int:
        return self._value

    def _onSliderChanged(self, value: int):
        if value != self._value:
            self._value = value
            self.line_edit.setText(str(value))
            self.valueChanged.emit(value)

    def _onEditFinished(self):
        try:
            value = int(self.line_edit.text())
            value = max(self._minimum, min(self._maximum, value))
            if value != self._value:
                self._value = value
                self.slider.setValue(value, move_to=True)
                self.valueChanged.emit(value)
            self.line_edit.setText(str(self._value))
        except ValueError:
            self.line_edit.setText(str(self._value))

    def reloadStyleSheet(self):
        super().reloadStyleSheet()
        self.title_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        self.input_panel.setStyleSheet(
            f"background-color: {self.getColor(SiColor.INTERFACE_BG_B)};"
            f"border: 1px solid {self.getColor(SiColor.INTERFACE_BG_D)};"
        )
        self.line_edit.setStyleSheet(
            "QLineEdit {"
            "    selection-background-color: #493F4E;"
            "    background-color: transparent;"
            f"    color: {self.getColor(SiColor.TEXT_C)};"
            "    border: 0px"
            "}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = event.size().width(), event.size().height()

        # Layout: title at top, slider in middle, input at bottom
        self.title_label.setGeometry(0, 0, w, 20)
        self.slider.setGeometry(0, 24, w, 24)
        self.input_panel.setGeometry(0, 52, w, 28)
        self.line_edit.setGeometry(4, 4, w - 8, 20)


class SiSliderDoubleSpinBox(SiWidget):
    """Double SpinBox with horizontal slider - vertical layout"""
    valueChanged = pyqtSignal(float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._minimum = 0.0
        self._maximum = 1.0
        self._value = 0.0
        self._single_step = 0.1
        self._decimals = 2
        self._title = ""

        # Internal multiplier to convert float to int for slider
        self._multiplier = 100

        # Title label
        self.title_label = SiLabel(self)
        self.title_label.setFont(SiFont.tokenized(GlobalFont.S_NORMAL))
        self.title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.title_label.setFixedHeight(20)

        # Slider - initialize with default range
        self.slider = SiSliderH(self)
        self.slider.setFixedHeight(24)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setSingleStep(1)  # Must be 1 due to SiSliderH bug
        self.slider.valueChanged.connect(self._onSliderChanged)

        # Value input
        self.input_panel = SiLabel(self)
        self.input_panel.setFixedStyleSheet("border-radius: 4px")

        self.line_edit = SiSimpleLineEdit(self.input_panel)
        self.line_edit.setAlignment(Qt.AlignCenter)
        self.line_edit.setFont(SiFont.tokenized(GlobalFont.S_NORMAL))
        self.line_edit.editingFinished.connect(self._onEditFinished)

    def setTitle(self, title: str):
        self._title = title
        self.title_label.setText(title)

    def title(self) -> str:
        return self._title

    def setHint(self, hint: str):
        """Set tooltip for the title label"""
        self.title_label.setHint(hint)

    def setDecimals(self, decimals: int):
        self._decimals = decimals
        self._multiplier = 10 ** decimals
        self._updateSliderRange()

    def decimals(self) -> int:
        return self._decimals

    def _updateSliderRange(self):
        int_min = int(self._minimum * self._multiplier)
        int_max = int(self._maximum * self._multiplier)

        self.slider.setMinimum(int_min)
        self.slider.setMaximum(int_max)
        # Keep slider singleStep as 1 to avoid SiSliderH position calculation bug
        self.slider.setSingleStep(1)

    def setMinimum(self, minimum: float):
        self._minimum = minimum
        self._updateSliderRange()

    def minimum(self) -> float:
        return self._minimum

    def setMaximum(self, maximum: float):
        self._maximum = maximum
        self._updateSliderRange()

    def maximum(self) -> float:
        return self._maximum

    def setSingleStep(self, step: float):
        self._single_step = step
        self._updateSliderRange()

    def singleStep(self) -> float:
        return self._single_step

    def setValue(self, value: float):
        value = round(max(self._minimum, min(self._maximum, value)), self._decimals)
        old_value = self._value
        self._value = value
        # Always update slider and line_edit
        self.slider.setValue(int(value * self._multiplier), move_to=False)
        self.line_edit.setText(str(value))
        if value != old_value:
            self.valueChanged.emit(value)

    def value(self) -> float:
        return self._value

    def _onSliderChanged(self, int_value: int):
        value = round(int_value / self._multiplier, self._decimals)
        if value != self._value:
            self._value = value
            self.line_edit.setText(str(value))
            self.valueChanged.emit(value)

    def _onEditFinished(self):
        try:
            value = float(self.line_edit.text())
            value = round(max(self._minimum, min(self._maximum, value)), self._decimals)
            if value != self._value:
                self._value = value
                self.slider.setValue(int(value * self._multiplier), move_to=True)
                self.valueChanged.emit(value)
            self.line_edit.setText(str(self._value))
        except ValueError:
            self.line_edit.setText(str(self._value))

    def reloadStyleSheet(self):
        super().reloadStyleSheet()
        self.title_label.setStyleSheet(f"color: {self.getColor(SiColor.TEXT_D)}")
        self.input_panel.setStyleSheet(
            f"background-color: {self.getColor(SiColor.INTERFACE_BG_B)};"
            f"border: 1px solid {self.getColor(SiColor.INTERFACE_BG_D)};"
        )
        self.line_edit.setStyleSheet(
            "QLineEdit {"
            "    selection-background-color: #493F4E;"
            "    background-color: transparent;"
            f"    color: {self.getColor(SiColor.TEXT_C)};"
            "    border: 0px"
            "}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w, h = event.size().width(), event.size().height()

        # Layout: title at top, slider in middle, input at bottom
        self.title_label.setGeometry(0, 0, w, 20)
        self.slider.setGeometry(0, 24, w, 24)
        self.input_panel.setGeometry(0, 52, w, 28)
        self.line_edit.setGeometry(4, 4, w - 8, 20)
