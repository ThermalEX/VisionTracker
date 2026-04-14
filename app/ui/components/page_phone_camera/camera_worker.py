"""Phone camera streaming worker and ADB helpers."""

from __future__ import annotations

import glob
import os
import re
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal


LOCAL_PORT = 27183
DEVICE_SERVER_PATH = "/data/local/tmp/scrcpy-server.jar"


def _creation_flags() -> int:
    return 0x08000000 if os.name == "nt" else 0


def run_cmd(cmd: list[str], timeout: int = 20, check: bool = False):
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
        creationflags=_creation_flags(),
    )


def find_exe(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    for pattern in (
        f"C:/Users/*/AppData/Local/Microsoft/WinGet/Links/{name}.exe",
        f"C:/Users/*/AppData/Local/Microsoft/WinGet/Packages/**/{name}.exe",
    ):
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return matches[0]
    return name


def find_scrcpy_server(scrcpy_path: str) -> Path | None:
    env_path = os.environ.get("SCRCPY_SERVER_PATH")
    if env_path and Path(env_path).exists():
        return Path(env_path)

    exe_path = Path(scrcpy_path)
    for root in (exe_path.parent, exe_path.parent.parent):
        for name in ("scrcpy-server", "scrcpy-server.jar"):
            direct = root / name
            if direct.exists():
                return direct
            matches = list(root.rglob(name)) if root.exists() else []
            if matches:
                return matches[0]
    return None


def get_scrcpy_version(scrcpy_path: str) -> str:
    proc = run_cmd([scrcpy_path, "--version"], timeout=10, check=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    match = re.search(r"scrcpy\s+([0-9]+(?:\.[0-9]+)+)", output)
    if not match:
        raise RuntimeError("Could not parse scrcpy version")
    return match.group(1)


def adb_list_devices(adb_path: str) -> list[str]:
    try:
        proc = run_cmd([adb_path, "devices"], timeout=10)
    except Exception:
        return []
    devices: list[str] = []
    for line in proc.stdout.splitlines()[1:]:
        line = line.strip()
        if line and "\tdevice" in line:
            devices.append(line.split("\t", 1)[0])
    return devices


def adb_pair(adb_path: str, host_port: str, code: str) -> tuple[bool, str]:
    try:
        proc = run_cmd([adb_path, "pair", host_port, code], timeout=15)
    except Exception as exc:
        return False, str(exc)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    ok = proc.returncode == 0 and "failed" not in out.lower()
    return ok, out


def adb_connect(adb_path: str, host_port: str) -> tuple[bool, str]:
    try:
        proc = run_cmd([adb_path, "connect", host_port], timeout=15)
    except Exception as exc:
        return False, str(exc)
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    low = out.lower()
    ok = "connected to" in low and "failed" not in low and "cannot" not in low
    return ok, out


def adb_disconnect(adb_path: str, host_port: str | None = None) -> str:
    cmd = [adb_path, "disconnect"]
    if host_port:
        cmd.append(host_port)
    try:
        proc = run_cmd(cmd, timeout=10)
    except Exception as exc:
        return str(exc)
    return ((proc.stdout or "") + (proc.stderr or "")).strip()


def _scan_adb_mdns_services(adb_path: str) -> tuple[list[str], list[str]]:
    try:
        proc = run_cmd([adb_path, "mdns", "services"], timeout=8)
    except Exception:
        return [], []

    pair_hosts: list[str] = []
    conn_hosts: list[str] = []
    for line in ((proc.stdout or "") + "\n" + (proc.stderr or "")).splitlines():
        match = re.search(r"(_adb-tls-(?:pairing|connect)\._tcp)\s+([0-9.]+:\d+)", line)
        if not match:
            continue
        service_type, host = match.groups()
        bucket = pair_hosts if "pairing" in service_type else conn_hosts
        if host not in bucket:
            bucket.append(host)
    return pair_hosts, conn_hosts


def mdns_scan_adb(timeout: float = 2.0) -> tuple[list[str], list[str]]:
    adb_pair_hosts, adb_conn_hosts = _scan_adb_mdns_services(find_exe("adb"))

    try:
        from zeroconf import ServiceBrowser, ServiceListener, Zeroconf
    except Exception:
        return adb_pair_hosts, adb_conn_hosts

    pair_hosts: list[str] = []
    conn_hosts: list[str] = []

    class Listener(ServiceListener):
        def __init__(self, bucket: list[str]):
            self.bucket = bucket

        def add_service(self, zc, stype, name):
            try:
                info = zc.get_service_info(stype, name, timeout=1500)
            except Exception:
                return
            if not info:
                return
            try:
                addrs = info.parsed_scoped_addresses() or []
            except Exception:
                addrs = []
            for ip in addrs:
                if ":" in ip:
                    continue
                host = f"{ip}:{info.port}"
                if host not in self.bucket:
                    self.bucket.append(host)

        def update_service(self, *args, **kwargs):
            pass

        def remove_service(self, *args, **kwargs):
            pass

    zc = None
    try:
        zc = Zeroconf()
        ServiceBrowser(zc, "_adb-tls-pairing._tcp.local.", Listener(pair_hosts))
        ServiceBrowser(zc, "_adb-tls-connect._tcp.local.", Listener(conn_hosts))
        time.sleep(timeout)
    except Exception:
        pass
    finally:
        if zc is not None:
            zc.close()
    for host in adb_pair_hosts:
        if host not in pair_hosts:
            pair_hosts.append(host)
    for host in adb_conn_hosts:
        if host not in conn_hosts:
            conn_hosts.append(host)
    return pair_hosts, conn_hosts


def scrcpy_list_cameras(scrcpy_path: str, serial: str | None = None) -> list[tuple[str, str]]:
    cmd = [scrcpy_path, "--list-cameras"]
    if serial:
        cmd.extend(["-s", serial])
    try:
        proc = run_cmd(cmd, timeout=12)
    except Exception:
        return []
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    found: list[tuple[str, str]] = []
    seen = set()
    for line in out.splitlines():
        match = re.search(r"--camera-id=(\S+)\s*(.*)", line)
        if not match:
            continue
        cid, desc = match.group(1).strip(), match.group(2).strip()
        if cid not in seen:
            seen.add(cid)
            found.append((cid, desc))
    return found


class CameraWorker(QObject):
    frame_ready = pyqtSignal(object)
    crops_ready = pyqtSignal(list)
    log = pyqtSignal(str, str)
    status_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._detector = None
        self._class_filter: set[int] = set()
        self._conf_threshold = 0.4
        self._serial: str | None = None
        self._camera_id = "0"
        self._camera_size = "1280x720"
        self._camera_fps = 30

    def configure(self, *, serial: str | None, camera_id: str, camera_size: str, camera_fps: int, conf: float):
        with self._lock:
            self._serial = serial
            self._camera_id = str(camera_id)
            self._camera_size = camera_size
            self._camera_fps = int(camera_fps)
            self._conf_threshold = float(conf)

    def set_detector(self, detector):
        with self._lock:
            self._detector = detector

    def set_class_filter(self, ids: list[int] | set[int]):
        with self._lock:
            self._class_filter = set(ids) if ids else set()

    def set_conf(self, value: float):
        with self._lock:
            self._conf_threshold = float(value)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=4)
            self._thread = None

    def _adb_base(self, adb_path: str) -> list[str]:
        cmd = [adb_path]
        if self._serial:
            cmd.extend(["-s", self._serial])
        return cmd

    def _build_server_args(self, version: str) -> list[str]:
        return [
            version, "log_level=info", "video=true", "audio=false",
            "video_codec=h264", "video_source=camera", "audio_source=mic",
            "audio_dup=false", "max_size=0", "video_bit_rate=8000000",
            f"max_fps={float(self._camera_fps)}", "angle=0",
            "tunnel_forward=true", "crop=", "control=false", "display_id=0",
            f"camera_id={self._camera_id}", "camera_facing=", "camera_ar=",
            f"camera_fps={self._camera_fps}", "camera_high_speed=false",
            "show_touches=false", "stay_awake=false", "screen_off_timeout=-1",
            "video_codec_options=", "audio_codec_options=", "video_encoder=",
            "audio_encoder=", "power_off_on_close=false",
            "clipboard_autosync=false", "downsize_on_error=true",
            "cleanup=false", "power_on=true", "new_display=",
            "vd_destroy_content=true", "vd_system_decorations=true",
            "capture_orientation=@0", "display_ime_policy=hide",
            "raw_stream=true", f"camera_size={self._camera_size}",
        ]

    def _run(self):
        adb_path = find_exe("adb")
        scrcpy_path = find_exe("scrcpy")
        server_path = find_scrcpy_server(scrcpy_path)
        if not server_path:
            self.log.emit("Could not find scrcpy-server. Install scrcpy.", "ERROR")
            self.status_changed.emit("error")
            return

        try:
            version = get_scrcpy_version(scrcpy_path)
        except Exception as exc:
            self.log.emit(f"scrcpy version error: {exc}", "ERROR")
            self.status_changed.emit("error")
            return

        server_proc = None
        cap = None
        reader_thread = None
        try:
            self.log.emit(f"Starting camera (id={self._camera_id}, size={self._camera_size})", "INFO")
            subprocess.run(self._adb_base(adb_path) + ["push", str(server_path), DEVICE_SERVER_PATH],
                           capture_output=True, text=True, timeout=30, creationflags=_creation_flags())
            subprocess.run(self._adb_base(adb_path) + ["forward", "--remove", f"tcp:{LOCAL_PORT}"],
                           capture_output=True, text=True, timeout=10, creationflags=_creation_flags())
            subprocess.run(self._adb_base(adb_path) + ["forward", f"tcp:{LOCAL_PORT}", "localabstract:scrcpy"],
                           capture_output=True, text=True, timeout=10, check=True, creationflags=_creation_flags())

            shell_cmd = ["shell", f"CLASSPATH={DEVICE_SERVER_PATH}", "app_process", "/", "com.genymobile.scrcpy.Server",
                         *self._build_server_args(version)]
            server_proc = subprocess.Popen(self._adb_base(adb_path) + shell_cmd,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           creationflags=_creation_flags())
            time.sleep(1.0)

            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "hwaccel;d3d11va|video_codec;h264"
            deadline = time.time() + 8.0
            cap = cv2.VideoCapture(f"tcp://127.0.0.1:{LOCAL_PORT}", cv2.CAP_FFMPEG)
            while not cap.isOpened() and time.time() < deadline:
                time.sleep(0.2)
                cap = cv2.VideoCapture(f"tcp://127.0.0.1:{LOCAL_PORT}", cv2.CAP_FFMPEG)
            if not cap.isOpened():
                raise RuntimeError("Could not open scrcpy stream")
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            self.status_changed.emit("running")
            self.log.emit("Camera stream opened", "SUCCESS")
            latest_lock = threading.Lock()
            latest_frame = None
            latest_id = 0

            def _read_latest_frame():
                nonlocal latest_frame, latest_id
                while not self._stop_event.is_set():
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        with latest_lock:
                            latest_frame = frame
                            latest_id += 1
                    else:
                        time.sleep(0.005)

            reader_thread = threading.Thread(target=_read_latest_frame, daemon=True)
            reader_thread.start()
            processed_id = -1
            while not self._stop_event.is_set():
                if server_proc.poll() is not None:
                    raise RuntimeError("scrcpy-server exited")
                with latest_lock:
                    frame = latest_frame
                    frame_id = latest_id
                if frame is None or frame_id == processed_id:
                    time.sleep(0.005)
                    continue
                processed_id = frame_id
                self._process_frame(frame)
        except Exception as exc:
            self.log.emit(f"Camera stream error: {exc}", "ERROR")
            self.status_changed.emit("error")
        finally:
            self._stop_event.set()
            if reader_thread is not None and reader_thread.is_alive():
                reader_thread.join(timeout=1)
            if cap is not None:
                cap.release()
            if server_proc is not None:
                try:
                    server_proc.terminate()
                    server_proc.wait(timeout=2)
                except Exception:
                    try:
                        server_proc.kill()
                    except Exception:
                        pass
            try:
                subprocess.run(self._adb_base(adb_path) + ["forward", "--remove", f"tcp:{LOCAL_PORT}"],
                               capture_output=True, text=True, timeout=5, creationflags=_creation_flags())
            except Exception:
                pass
            self.status_changed.emit("stopped")
            self.log.emit("Camera stream stopped", "INFO")

    def _process_frame(self, frame: np.ndarray):
        annotated = frame.copy()
        crops: list[tuple[str, np.ndarray]] = []
        with self._lock:
            detector = self._detector
            class_filter = set(self._class_filter)
            conf = self._conf_threshold

        if detector is not None and getattr(detector, "model", None) is not None:
            try:
                results = detector.model(frame, conf=conf, verbose=False)
                names = getattr(detector.model, "names", {})
                h, w = frame.shape[:2]
                for result in results:
                    if result.boxes is None:
                        continue
                    for box in result.boxes:
                        cls_id = int(box.cls[0]) if box.cls is not None else -1
                        if class_filter and cls_id not in class_filter:
                            continue
                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                        x1, y1 = max(0, x1), max(0, y1)
                        x2, y2 = min(w, x2), min(h, y2)
                        label = str(names.get(cls_id, cls_id)) if isinstance(names, dict) else str(cls_id)
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        crops.append((label, frame[y1:y2, x1:x2].copy()))
            except Exception as exc:
                self.log.emit(f"Inference error: {exc}", "ERROR")

        self.frame_ready.emit(annotated)
        self.crops_ready.emit(crops[:20])
