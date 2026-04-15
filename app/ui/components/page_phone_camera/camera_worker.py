"""Phone camera streaming worker and ADB helpers."""

from __future__ import annotations

import glob
import os
import re
import shutil
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
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._detector = None
        self._class_filter: set[int] = set()
        self._conf_threshold = 0.4
        self._serial: str | None = None
        self._camera_id = "0"
        self._camera_size: str | None = "1280x720"
        self._camera_fps = 30

    def configure(self, *, serial: str | None, camera_id: str, camera_size: str, camera_fps: int, conf: float):
        with self._lock:
            self._serial = serial
            self._camera_id = str(camera_id)
            self._camera_size = (camera_size or "").strip() or "1280x720"
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

    def is_running(self) -> bool:
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return False
            self._stop_event = threading.Event()
            thread = threading.Thread(target=self._run, args=(self._stop_event,), daemon=True)
            self._thread = thread
        thread.start()
        return True

    def stop(self, timeout: float = 6.0) -> bool:
        with self._lock:
            stop_event = self._stop_event
            thread = self._thread
        if stop_event is not None:
            stop_event.set()
        if thread is not None:
            thread.join(timeout=timeout)
            alive = thread.is_alive()
            if not alive:
                with self._lock:
                    if self._thread is thread:
                        self._thread = None
                    if self._stop_event is stop_event:
                        self._stop_event = None
            return not alive
        return True

    def _adb_base(self, adb_path: str) -> list[str]:
        cmd = [adb_path]
        if self._serial:
            cmd.extend(["-s", self._serial])
        return cmd

    def _build_server_args(self, version: str, camera_size: str | None, camera_fps: int | None) -> list[str]:
        args = [
            version, "log_level=info", "video=true", "audio=false",
            "video_codec=h264", "video_source=camera", "audio_source=mic",
            "audio_dup=false", "max_size=0", "video_bit_rate=8000000",
            "angle=0",
            "tunnel_forward=true", "crop=", "control=false", "display_id=0",
            f"camera_id={self._camera_id}", "camera_facing=", "camera_ar=",
            "camera_high_speed=false",
            "show_touches=false", "stay_awake=false", "screen_off_timeout=-1",
            "video_codec_options=", "audio_codec_options=", "video_encoder=",
            "audio_encoder=", "power_off_on_close=false",
            "clipboard_autosync=false", "downsize_on_error=true",
            "cleanup=false", "power_on=true", "new_display=",
            "vd_destroy_content=true", "vd_system_decorations=true",
            "capture_orientation=@0", "display_ime_policy=hide",
            "raw_stream=true",
        ]
        if camera_fps is not None and camera_fps > 0:
            args.append(f"max_fps={float(camera_fps)}")
            args.append(f"camera_fps={int(camera_fps)}")
        # Leave camera_size unset to let scrcpy use the camera's native/default resolution.
        if camera_size:
            args.append(f"camera_size={camera_size}")
        return args

    def _run(self, stop_event: threading.Event):
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
            requested_size = self._camera_size
            requested_fps = int(self._camera_fps)
            size_text = requested_size or "1280x720"
            self.log.emit(
                f"Starting camera (id={self._camera_id}, size={size_text}, fps={requested_fps})",
                "INFO",
            )
            subprocess.run(self._adb_base(adb_path) + ["push", str(server_path), DEVICE_SERVER_PATH],
                           capture_output=True, text=True, timeout=30, creationflags=_creation_flags())
            subprocess.run(self._adb_base(adb_path) + ["forward", "--remove", f"tcp:{LOCAL_PORT}"],
                           capture_output=True, text=True, timeout=10, creationflags=_creation_flags())
            subprocess.run(self._adb_base(adb_path) + ["forward", f"tcp:{LOCAL_PORT}", "localabstract:scrcpy"],
                           capture_output=True, text=True, timeout=10, check=True, creationflags=_creation_flags())

            shell_cmd = [
                "shell", f"CLASSPATH={DEVICE_SERVER_PATH}", "app_process", "/", "com.genymobile.scrcpy.Server",
                *self._build_server_args(version, requested_size, requested_fps),
            ]
            server_proc = subprocess.Popen(
                self._adb_base(adb_path) + shell_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=_creation_flags(),
            )
            time.sleep(1.0)

            os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "hwaccel;d3d11va|video_codec;h264"
            deadline = time.time() + 6.0
            cap = cv2.VideoCapture(f"tcp://127.0.0.1:{LOCAL_PORT}", cv2.CAP_FFMPEG)
            while not cap.isOpened() and time.time() < deadline and not stop_event.is_set():
                if server_proc.poll() is not None:
                    err = ""
                    try:
                        err = (server_proc.stderr.read() or b"").decode(errors="ignore").strip()
                    except Exception:
                        pass
                    raise RuntimeError(f"scrcpy-server exited: {err or 'no output'}")
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
                while not stop_event.is_set():
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
            while not stop_event.is_set():
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
            stop_event.set()
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
            with self._lock:
                current = threading.current_thread()
                if self._thread is current:
                    self._thread = None
                if self._stop_event is stop_event:
                    self._stop_event = None

    def _process_frame(self, frame: np.ndarray):
        crops: list[tuple[str, np.ndarray, tuple[int, int, int, int]]] = []
        preview_max = 960
        fh, fw = frame.shape[:2]
        preview_scale = min(1.0, preview_max / max(fh, fw))
        if preview_scale < 1.0:
            ph, pw = max(1, int(fh * preview_scale)), max(1, int(fw * preview_scale))
            annotated = cv2.resize(frame, (pw, ph), interpolation=cv2.INTER_AREA)
        else:
            annotated = frame.copy()
        with self._lock:
            detector = self._detector
            class_filter = set(self._class_filter)
            conf = self._conf_threshold

        if detector is not None and getattr(detector, "model", None) is not None:
            try:
                results = detector.model(frame, conf=conf, imgsz=640, verbose=False)
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
                        if x2 <= x1 or y2 <= y1:
                            continue
                        label = str(names.get(cls_id, cls_id)) if isinstance(names, dict) else str(cls_id)
                        px1 = int(x1 * preview_scale); py1 = int(y1 * preview_scale)
                        px2 = int(x2 * preview_scale); py2 = int(y2 * preview_scale)
                        cv2.rectangle(annotated, (px1, py1), (px2, py2), (0, 255, 0), 2)
                        crop = frame[y1:y2, x1:x2]
                        ch, cw = crop.shape[:2]
                        scale = 110.0 / max(ch, cw)
                        if scale < 1.0:
                            crop = cv2.resize(crop, (max(1, int(cw * scale)), max(1, int(ch * scale))), interpolation=cv2.INTER_AREA)
                        else:
                            crop = crop.copy()
                        crops.append((label, crop, (x1, y1, x2, y2)))
            except Exception as exc:
                self.log.emit(f"Inference error: {exc}", "ERROR")

        self.frame_ready.emit(annotated)
        self.crops_ready.emit(crops[:20])
