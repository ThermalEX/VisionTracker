"""Vision Tracker - Phone Camera page."""

from __future__ import annotations

import os
import socket

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPixmap
from PyQt5.QtWidgets import QCheckBox, QGridLayout, QHBoxLayout, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget, QSizePolicy

from siui.components import SiDenseHContainer, SiDenseVContainer, SiLabel, SiTitledWidgetGroup
from siui.components.button import SiFlatButton
from siui.components.combobox_ import SiCapsuleComboBox
from siui.components.container import SiTriSectionFlatCard
from siui.components.page import SiPage
from siui.components.spinbox.slider_spinbox import SiSliderDoubleSpinBox, SiSliderSpinBox
from siui.core import Si, SiColor, SiGlobal
from siui.gui import SiFont

from .camera_worker import (
    CameraWorker,
    adb_connect,
    adb_disconnect,
    adb_list_devices,
    adb_pair,
    find_exe,
    mdns_scan_adb,
    scrcpy_list_cameras,
)


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

BUTTON_STYLE = """
QPushButton {
    background-color: #201d23;
    border: 1px solid #3a3540;
    border-radius: 6px;
    color: #F0EEF2;
    padding: 0 14px;
    font-family: "Segoe UI", "Microsoft YaHei";
    font-size: 13px;
}
QPushButton:hover {
    background-color: #2b2630;
    border: 1px solid #D087DF;
}
QPushButton:pressed {
    background-color: #352f3c;
}
QPushButton:disabled {
    color: #6f6678;
    border: 1px solid #302b36;
    background-color: #1d1a21;
}
"""

CHECKBOX_STYLE = """
QCheckBox {
    color: #D1CBD4;
    font-family: "Segoe UI", "Microsoft YaHei";
    font-size: 12px;
    spacing: 6px;
    padding: 2px 4px;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid #5a5262;
    background: #201d23;
}
QCheckBox::indicator:hover { border: 1px solid #D087DF; }
QCheckBox::indicator:checked {
    background: #D087DF;
    border: 1px solid #D087DF;
    image: none;
}
"""

SCROLLBAR_STYLE = """
QScrollArea { background: transparent; border: 1px solid #3a3540; border-radius: 6px; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 8px; margin: 4px 2px 4px 0; }
QScrollBar::handle:vertical { background: #4a4452; min-height: 24px; border-radius: 3px; }
QScrollBar::handle:vertical:hover { background: #6b6078; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent; height: 0; border: none;
}
"""


def _local_ip_hint() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


class _MdnsScanThread(QThread):
    finished_scan = pyqtSignal(list, list, list)

    def __init__(self, timeout: float = 2.0, parent=None):
        super().__init__(parent)
        self._timeout = timeout

    def run(self):
        pair_hosts, conn_hosts = mdns_scan_adb(self._timeout)
        devices = adb_list_devices(find_exe("adb"))
        self.finished_scan.emit(pair_hosts, conn_hosts, devices)


class PhoneCameraPage(SiPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPadding(64)
        self.setScrollMaximumWidth(1200)
        self.setScrollAlignment(Qt.AlignLeft)
        self.setTitle("Phone Camera")

        self._worker = CameraWorker(self)
        self._worker.frame_ready.connect(self._onFrame)
        self._worker.crops_ready.connect(self._onCrops)
        self._worker.status_changed.connect(self._onStatus)
        self._worker.log.connect(self._onLog)

        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self._models_root = os.path.join(app_dir, "models")
        self._detector = None
        self._found_models: list[str] = []
        self._camera_ids: list[str] = []
        self._class_checkboxes: list[tuple[QCheckBox, int]] = []

        self.titled_group = SiTitledWidgetGroup(self)
        self.titled_group.setSpacing(16)
        self.titled_group.setAdjustWidgetsSize(True)

        self._createAdbCard()
        self._createCameraCard()
        self._createModelCard()
        self._createViewerCard()

        self.titled_group.addPlaceholder(64)
        self.setAttachment(self.titled_group)
        QTimer.singleShot(200, self._refreshDevices)

    def _mkLabel(self, text: str) -> SiLabel:
        label = SiLabel(self)
        label.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        label.setFont(SiFont.getFont(size=13))
        label.setTextColor(self.getColor(SiColor.TEXT_D))
        label.setText(text)
        return label

    def _mkButton(self, text: str, width: int) -> QPushButton:
        button = QPushButton(text, self)
        button.setFixedSize(width, 32)
        button.setStyleSheet(BUTTON_STYLE)
        return button

    def _hideComboTitle(self, combo: SiCapsuleComboBox):
        combo.setTitle("")
        combo._line_edit.setTitleWidthMode(combo._line_edit.TitleWidthMode.Fixed)
        combo._line_edit.setTitleFixedWidth(0)
        combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")

    def _createAdbCard(self):
        self.titled_group.addTitle("Wireless ADB")
        card = SiTriSectionFlatCard(self)
        card.setTitle("Connect to Phone (Wi-Fi)")

        form = QWidget(self)
        layout = QGridLayout(form)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(10)
        layout.setColumnMinimumWidth(0, 72)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)
        layout.setRowMinimumHeight(3, 36)

        layout.addWidget(self._mkLabel("Device"), 0, 0, Qt.AlignVCenter)
        self.device_combo = SiCapsuleComboBox(self)
        self.device_combo.setMinimumSize(320, 32)
        self.device_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.device_combo.setTitle("ADB Device")
        self.device_combo.setEditable(False)
        self.device_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.device_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        layout.addWidget(self.device_combo, 0, 1, 1, 2)

        self.btn_refresh_devices = self._mkButton("Refresh", 120)
        self.btn_refresh_devices.clicked.connect(self._refreshDevices)
        layout.addWidget(self.btn_refresh_devices, 0, 3)

        layout.addWidget(self._mkLabel("Pair"), 1, 0, Qt.AlignVCenter)
        self.edit_pair_host = QLineEdit(self)
        self.edit_pair_host.setMinimumSize(260, 32)
        self.edit_pair_host.setStyleSheet(INPUT_STYLE)
        self.edit_pair_host.setPlaceholderText("pair address from refresh")
        layout.addWidget(self.edit_pair_host, 1, 1)

        self.edit_pair_code = QLineEdit(self)
        self.edit_pair_code.setFixedSize(120, 32)
        self.edit_pair_code.setStyleSheet(INPUT_STYLE)
        self.edit_pair_code.setPlaceholderText("6-digit code")
        self.edit_pair_code.setMaxLength(6)
        layout.addWidget(self.edit_pair_code, 1, 2)

        self.btn_pair = self._mkButton("Pair", 120)
        self.btn_pair.clicked.connect(self._doPair)
        layout.addWidget(self.btn_pair, 1, 3)

        layout.addWidget(self._mkLabel("Connect"), 2, 0, Qt.AlignVCenter)
        self.edit_conn_host = QLineEdit(self)
        self.edit_conn_host.setMinimumSize(260, 32)
        self.edit_conn_host.setStyleSheet(INPUT_STYLE)
        self.edit_conn_host.setPlaceholderText("connect address from refresh")
        layout.addWidget(self.edit_conn_host, 2, 1)

        self.btn_connect = self._mkButton("Connect", 120)
        self.btn_connect.clicked.connect(self._doConnect)
        layout.addWidget(self.btn_connect, 2, 2)

        self.btn_disconnect = self._mkButton("Disconnect", 120)
        self.btn_disconnect.clicked.connect(self._doDisconnect)
        layout.addWidget(self.btn_disconnect, 2, 3)

        layout.addWidget(self._mkLabel("Found"), 3, 0, Qt.AlignVCenter)
        self.host_list = QWidget(self)
        self.host_list.setFixedHeight(36)
        self.host_list_layout = QHBoxLayout(self.host_list)
        self.host_list_layout.setContentsMargins(0, 2, 0, 2)
        self.host_list_layout.setSpacing(8)
        layout.addWidget(self.host_list, 3, 1, 1, 3)

        layout.addWidget(self._mkLabel("Status"), 4, 0, Qt.AlignVCenter)
        self.conn_status = SiLabel(self)
        self.conn_status.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.conn_status.setFont(SiFont.getFont(size=13))
        layout.addWidget(self.conn_status, 4, 1, 1, 3)

        card.body().addWidget(form)

        self.adb_status = SiLabel(self)
        self.adb_status.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.adb_status.setFont(SiFont.getFont(size=12))
        self.adb_status.setTextColor(self.getColor(SiColor.TEXT_D))
        hint = _local_ip_hint()
        self.adb_status.setText(f"Tip: enable Developer options -> Wireless debugging on phone." + (f" (PC LAN: {hint})" if hint else ""))
        card.body().addWidget(self.adb_status)

        self._setDiscoveredHosts([])
        self._setConnState(False)
        card.adjustSize()
        self.titled_group.addWidget(card)

    def _createCameraCard(self):
        self.titled_group.addTitle("Camera")
        card = SiTriSectionFlatCard(self)
        card.setTitle("Camera Settings")

        row = SiDenseHContainer(self)
        row.setFixedHeight(84)
        row.setSpacing(24)

        cam_box = SiDenseVContainer(self)
        cam_box.setFixedSize(280, 84)
        cam_box.setSpacing(4)
        cam_box.addWidget(self._mkLabel("Camera"), side="top")
        cam_row = SiDenseHContainer(self)
        cam_row.setFixedHeight(32)
        cam_row.setSpacing(6)
        self.cam_combo = SiCapsuleComboBox(self)
        self.cam_combo.setFixedSize(240, 32)
        self._hideComboTitle(self.cam_combo)
        self.cam_combo.setEditable(False)
        cam_row.addWidget(self.cam_combo, side="left")
        self.btn_scan_cams = SiFlatButton(self)
        self.btn_scan_cams.setFixedSize(28, 28)
        self.btn_scan_cams.setSvgIcon(SiGlobal.siui.iconpack.get("ic_fluent_arrow_sync_circle_filled"))
        self.btn_scan_cams.clicked.connect(self._scanCameras)
        cam_row.addWidget(self.btn_scan_cams, side="left")
        cam_box.addWidget(cam_row, side="top")
        row.addWidget(cam_box, side="left")

        size_box = SiDenseVContainer(self)
        size_box.setFixedSize(220, 84)
        size_box.setSpacing(4)
        size_box.addWidget(self._mkLabel("Resolution"), side="top")
        self.size_combo = SiCapsuleComboBox(self)
        self.size_combo.setFixedSize(200, 32)
        self._hideComboTitle(self.size_combo)
        self.size_combo.setEditable(False)
        for item in ("1920x1080", "1280x720", "960x540", "640x480"):
            self.size_combo.addItem(item)
        self.size_combo.setCurrentIndex(1)
        size_box.addWidget(self.size_combo, side="top")
        row.addWidget(size_box, side="left")
        card.body().addWidget(row)

        tuning_row = SiDenseHContainer(self)
        tuning_row.setFixedHeight(84)
        tuning_row.setSpacing(24)
        self.cam_fps = SiSliderSpinBox(self)
        self.cam_fps.setTitle("FPS")
        self.cam_fps.setHint("Target camera frame rate")
        self.cam_fps.resize(180, 84)
        self.cam_fps.setMinimum(5)
        self.cam_fps.setMaximum(60)
        self.cam_fps.setValue(30)
        tuning_row.addWidget(self.cam_fps, side="left")
        self.conf_spin = SiSliderDoubleSpinBox(self)
        self.conf_spin.setTitle("Confidence")
        self.conf_spin.setHint("Minimum YOLO confidence threshold")
        self.conf_spin.resize(180, 84)
        self.conf_spin.setMinimum(0.05)
        self.conf_spin.setMaximum(0.95)
        self.conf_spin.setSingleStep(0.05)
        self.conf_spin.setDecimals(2)
        self.conf_spin.setValue(0.40)
        self.conf_spin.valueChanged.connect(lambda value: self._worker.set_conf(float(value)))
        tuning_row.addWidget(self.conf_spin, side="left")
        card.body().addWidget(tuning_row)

        btn_row = SiDenseHContainer(self)
        btn_row.setFixedHeight(44)
        btn_row.setSpacing(12)
        self.btn_start = self._mkButton("Start", 120)
        self.btn_start.setFixedHeight(40)
        self.btn_start.clicked.connect(self._startStream)
        btn_row.addWidget(self.btn_start, side="left")
        self.btn_stop = self._mkButton("Stop", 120)
        self.btn_stop.setFixedHeight(40)
        self.btn_stop.clicked.connect(self._stopStream)
        btn_row.addWidget(self.btn_stop, side="left")
        card.body().addWidget(btn_row)

        status_row = SiDenseHContainer(self)
        status_row.setFixedHeight(28)
        status_row.setSpacing(8)
        status_row.addWidget(self._mkLabel("Status"), side="left")
        self.stream_status = SiLabel(self)
        self.stream_status.setSiliconWidgetFlag(Si.AdjustSizeOnTextChanged)
        self.stream_status.setFont(SiFont.getFont(size=13))
        status_row.addWidget(self.stream_status, side="left")
        card.body().addWidget(status_row)

        self._setStreamState("stopped")
        card.adjustSize()
        self.titled_group.addWidget(card)

    def _createModelCard(self):
        self.titled_group.addTitle("Detection")
        card = SiTriSectionFlatCard(self)
        card.setTitle("YOLO Model & Classes")

        row = SiDenseHContainer(self)
        row.setFixedHeight(40)
        row.setSpacing(8)
        row.addWidget(self._mkLabel("Model"), side="left")
        self.model_combo = SiCapsuleComboBox(self)
        self.model_combo.setFixedSize(320, 32)
        self.model_combo.setTitle("Model File")
        self.model_combo.setEditable(False)
        self.model_combo._line_edit.style_data.text_indicator_color_idle = QColor("#00000000")
        self.model_combo._line_edit.style_data.text_indicator_color_editing = QColor("#00000000")
        row.addWidget(self.model_combo, side="left")
        self.btn_refresh_models = self._mkButton("Refresh", 112)
        self.btn_refresh_models.clicked.connect(self._scanModels)
        row.addWidget(self.btn_refresh_models, side="left")
        self.btn_load_model = self._mkButton("Load", 112)
        self.btn_load_model.clicked.connect(self._loadSelectedModel)
        row.addWidget(self.btn_load_model, side="left")
        card.body().addWidget(row)

        card.body().addWidget(self._mkLabel("Classes (check to include; empty = all)"))
        self.classes_host = QWidget(self)
        self.classes_layout = QGridLayout(self.classes_host)
        self.classes_layout.setContentsMargins(0, 4, 0, 4)
        self.classes_layout.setHorizontalSpacing(12)
        self.classes_layout.setVerticalSpacing(6)
        self.classes_scroll = QScrollArea(self)
        self.classes_scroll.setWidget(self.classes_host)
        self.classes_scroll.setWidgetResizable(True)
        self.classes_scroll.setFixedHeight(200)
        self.classes_scroll.setStyleSheet(SCROLLBAR_STYLE)
        card.body().addWidget(self.classes_scroll)

        sel_row = SiDenseHContainer(self)
        sel_row.setFixedHeight(36)
        sel_row.setSpacing(8)
        self.btn_sel_all = self._mkButton("Select All", 112)
        self.btn_sel_all.setFixedHeight(30)
        self.btn_sel_all.clicked.connect(lambda: self._toggleAllClasses(True))
        sel_row.addWidget(self.btn_sel_all, side="left")
        self.btn_sel_none = self._mkButton("Clear", 112)
        self.btn_sel_none.setFixedHeight(30)
        self.btn_sel_none.clicked.connect(lambda: self._toggleAllClasses(False))
        sel_row.addWidget(self.btn_sel_none, side="left")
        card.body().addWidget(sel_row)

        card.adjustSize()
        self.titled_group.addWidget(card)
        self._scanModels()

    def _createViewerCard(self):
        self.titled_group.addTitle("Live View")
        card = SiTriSectionFlatCard(self)
        card.setTitle("Phone Camera Preview")
        wrapper = QWidget(self)
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(12)

        self.preview_label = SiLabel(wrapper)
        self.preview_label.setFixedSize(720, 405)
        self.preview_label.setStyleSheet(
            "background-color: #000000;"
            "border: 1px solid #4a4452;"
            "border-radius: 6px;"
        )
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setTextColor("#FFFFFF")
        self.preview_label.setText("No signal")
        vbox.addWidget(self.preview_label)

        crops_container = QWidget(wrapper)
        crops_container.setFixedWidth(720)
        crops_vbox = QVBoxLayout(crops_container)
        crops_vbox.setContentsMargins(0, 0, 0, 0)
        crops_vbox.setSpacing(6)
        crops_title = self._mkLabel("Detected Crops")
        crops_vbox.addWidget(crops_title)
        self.crops_host = QWidget(crops_container)
        self.crops_host_layout = QGridLayout(self.crops_host)
        self.crops_host_layout.setContentsMargins(4, 4, 4, 4)
        self.crops_host_layout.setSpacing(6)
        crops_scroll = QScrollArea(crops_container)
        crops_scroll.setWidget(self.crops_host)
        crops_scroll.setWidgetResizable(True)
        crops_scroll.setFixedHeight(180)
        crops_scroll.setStyleSheet(SCROLLBAR_STYLE)
        crops_vbox.addWidget(crops_scroll)
        vbox.addWidget(crops_container)

        wrapper.setFixedHeight(620)
        card.body().addWidget(wrapper)
        card.adjustSize()
        self.titled_group.addWidget(card)

    def _setDiscoveredHosts(self, hosts: list[str]):
        while self.host_list_layout.count():
            item = self.host_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        if not hosts:
            self.host_list_layout.addWidget(self._mkLabel("No connect addresses found"))
            self.host_list_layout.addStretch(1)
            return
        for host in hosts:
            button = QPushButton(host, self.host_list)
            button.setFixedSize(154, 30)
            button.setStyleSheet(BUTTON_STYLE)
            button.clicked.connect(lambda _=False, value=host: self._selectDiscoveredHost(value))
            self.host_list_layout.addWidget(button, alignment=Qt.AlignVCenter)
        self.host_list_layout.addStretch(1)

    def _selectDiscoveredHost(self, host: str):
        self.edit_conn_host.setText(host)
        self.adb_status.setText(f"Selected connect address: {host}")

    def _refreshDevices(self):
        if getattr(self, "_scan_thread", None) is not None and self._scan_thread.isRunning():
            return
        self.adb_status.setText("Scanning LAN via mDNS...")
        self.btn_refresh_devices.setEnabled(False)
        self._scan_thread = _MdnsScanThread(timeout=2.0, parent=self)
        self._scan_thread.finished_scan.connect(self._onScanFinished)
        self._scan_thread.start()

    def _onScanFinished(self, pair_hosts: list, conn_hosts: list, devices: list):
        self.btn_refresh_devices.setEnabled(True)
        self.device_combo.clear()
        for device in devices:
            self.device_combo.addItem(device)

        wireless_devices = [device for device in devices if ":" in device]
        merged_conn: list[str] = []
        for host in [*wireless_devices, *conn_hosts]:
            if host not in merged_conn:
                merged_conn.append(host)

        self._setConnState(bool(wireless_devices))
        self._setDiscoveredHosts(merged_conn)
        self.edit_pair_host.setText(pair_hosts[0] if pair_hosts else "")
        self.edit_conn_host.setText(wireless_devices[0] if wireless_devices else (merged_conn[0] if len(merged_conn) == 1 else ""))

        msgs = []
        if pair_hosts:
            msgs.append(f"Pair: {', '.join(pair_hosts)}")
        if merged_conn:
            msgs.append(f"Found {len(merged_conn)} connect address(es). Click one to fill Connect.")
        self.adb_status.setText(" | ".join(msgs) if msgs else "No wireless ADB found on LAN.")

    def _setConnState(self, connected: bool):
        self.btn_connect.setEnabled(not connected)
        self.btn_disconnect.setEnabled(connected)
        self.conn_status.setText("Connected" if connected else "Disconnected")
        self.conn_status.setTextColor("#7BD88F" if connected else self.getColor(SiColor.TEXT_D))

    def _setStreamState(self, status: str):
        status = (status or "stopped").lower()
        is_running = status == "running"
        is_starting = status == "starting"
        is_stopping = status == "stopping"
        self.btn_start.setEnabled(not is_running and not is_starting and not is_stopping)
        self.btn_stop.setEnabled((is_running or is_starting) and not is_stopping)
        colors = {"running": "#7BD88F", "starting": "#FFD467", "stopping": "#FFD467", "error": "#FF6767"}
        self.stream_status.setText(status.capitalize())
        self.stream_status.setTextColor(colors.get(status, self.getColor(SiColor.TEXT_D)))

    def _doPair(self):
        host = self.edit_pair_host.text().strip()
        code = self.edit_pair_code.text().strip()
        if not host or not code:
            self.adb_status.setText("Refresh to auto-fill Pair Addr, then enter the 6-digit code.")
            return
        ok, out = adb_pair(find_exe("adb"), host, code)
        self.adb_status.setText(out or ("Paired." if ok else "Pair failed."))
        if ok:
            QTimer.singleShot(500, self._refreshDevices)

    def _doConnect(self):
        host = self.edit_conn_host.text().strip()
        if not host:
            self.adb_status.setText("Select or enter a connect address first.")
            self._setConnState(False)
            return
        ok, out = adb_connect(find_exe("adb"), host)
        self.adb_status.setText(out or ("Connected." if ok else "Connect failed."))
        self._setConnState(ok)
        QTimer.singleShot(300, self._refreshDevices)

    def _doDisconnect(self):
        current = self.device_combo.currentText().strip() or self.edit_conn_host.text().strip()
        out = adb_disconnect(find_exe("adb"), current if ":" in current else None)
        self.adb_status.setText(out or "Disconnected.")
        self._setConnState(False)
        QTimer.singleShot(300, self._refreshDevices)

    def _scanCameras(self):
        serial = self.device_combo.currentText().strip() or None
        cams = scrcpy_list_cameras(find_exe("scrcpy"), serial)
        self.cam_combo.clear()
        self._camera_ids = []
        if not cams:
            self.cam_combo.addItem("(no cameras)")
            self._onLog("No cameras found. Connect a device first.", "WARN")
            return
        for cid, desc in cams:
            self.cam_combo.addItem(f"{cid}  {desc}" if desc else cid)
            self._camera_ids.append(cid)
        self.cam_combo.setCurrentIndex(0)
        self._onLog(f"Found {len(cams)} camera(s).", "SUCCESS")

    def _scanModels(self):
        self.model_combo.clear()
        self._found_models = []
        if os.path.isdir(self._models_root):
            for name in sorted(os.listdir(self._models_root)):
                full = os.path.join(self._models_root, name)
                if os.path.isfile(full) and name.lower().endswith((".pt", ".onnx", ".engine")):
                    self._found_models.append(full)
        for path in self._found_models:
            self.model_combo.addItem(os.path.basename(path))
        if not self._found_models:
            self.model_combo.addItem("(no models in app/models/)")

    def _loadSelectedModel(self):
        idx = self.model_combo.currentIndex()
        if idx < 0 or idx >= len(self._found_models):
            self._onLog("No model available to load.", "WARN")
            return
        try:
            from core.detector import Detector
            self._detector = Detector(self._found_models[idx])
            self._worker.set_detector(self._detector)
            self._rebuildClassCheckboxes()
            self._onLog(f"Model loaded: {os.path.basename(self._found_models[idx])}", "SUCCESS")
        except Exception as exc:
            self._detector = None
            self._worker.set_detector(None)
            self._onLog(f"Model load failed: {exc}", "ERROR")

    def _rebuildClassCheckboxes(self):
        for i in reversed(range(self.classes_layout.count())):
            item = self.classes_layout.takeAt(i)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._class_checkboxes.clear()

        names = getattr(getattr(self._detector, "model", None), "names", {}) if self._detector else {}
        if not isinstance(names, dict):
            names = {i: value for i, value in enumerate(list(names))}
        for i, (cid, cname) in enumerate(sorted(names.items(), key=lambda pair: int(pair[0]))):
            cb = QCheckBox(f"{cid}: {cname}", self.classes_host)
            cb.setStyleSheet(CHECKBOX_STYLE)
            cb.toggled.connect(self._onClassToggled)
            self.classes_layout.addWidget(cb, i // 4, i % 4, Qt.AlignLeft)
            self._class_checkboxes.append((cb, int(cid)))
        self._onClassToggled()

    def _toggleAllClasses(self, checked: bool):
        for checkbox, _ in self._class_checkboxes:
            checkbox.setChecked(checked)
        self._onClassToggled()

    def _onClassToggled(self, *_):
        self._worker.set_class_filter([cid for checkbox, cid in self._class_checkboxes if checkbox.isChecked()])

    def _startStream(self):
        serial = self.device_combo.currentText().strip() or self.edit_conn_host.text().strip() or None
        idx = self.cam_combo.currentIndex()
        cam_id = self._camera_ids[idx] if 0 <= idx < len(self._camera_ids) else "0"
        self._worker.configure(
            serial=serial,
            camera_id=cam_id,
            camera_size=self.size_combo.currentText(),
            camera_fps=int(self.cam_fps.value()),
            conf=float(self.conf_spin.value()),
        )
        self._setStreamState("starting")
        self._worker.start()

    def _stopStream(self):
        self._setStreamState("stopping")
        self._worker.stop()

    def _onStatus(self, status: str):
        self._setStreamState(status)

    def _onLog(self, msg: str, level: str):
        self.adb_status.setText(f"[{level}] {msg}")

    def _onFrame(self, frame: np.ndarray):
        if frame is None or frame.size == 0:
            return
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(self.preview_label.width(), self.preview_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(pix)

    def _onCrops(self, crops: list):
        for i in reversed(range(self.crops_host_layout.count())):
            item = self.crops_host_layout.takeAt(i)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for i, (cname, crop) in enumerate(crops):
            try:
                if crop is None or crop.size == 0:
                    continue
                rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888)
                pix = QPixmap.fromImage(qimg).scaled(110, 110, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                holder = QWidget(self.crops_host)
                vbox = QVBoxLayout(holder)
                vbox.setContentsMargins(0, 0, 0, 0)
                vbox.setSpacing(2)
                img_lbl = SiLabel(holder)
                img_lbl.setFixedSize(110, 110)
                img_lbl.setAlignment(Qt.AlignCenter)
                img_lbl.setStyleSheet(f"background-color: {SiGlobal.siui.colors['INTERFACE_BG_A']}; border-radius: 4px;")
                img_lbl.setPixmap(pix)
                vbox.addWidget(img_lbl)
                text_lbl = SiLabel(holder)
                text_lbl.setFixedWidth(110)
                text_lbl.setAlignment(Qt.AlignCenter)
                text_lbl.setFont(SiFont.getFont(size=11))
                text_lbl.setTextColor(self.getColor(SiColor.TEXT_D))
                text_lbl.setText(str(cname))
                vbox.addWidget(text_lbl)
                self.crops_host_layout.addWidget(holder, i // 5, i % 5, Qt.AlignLeft)
            except Exception:
                continue

    def closeEvent(self, event):
        try:
            self._worker.stop()
        except Exception:
            pass
        super().closeEvent(event)
