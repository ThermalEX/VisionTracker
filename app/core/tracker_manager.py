"""Tracker manager for integrating UI with tracking backend."""

import os
import time
import math
from multiprocessing import Queue, Event
import pygetwindow as gw
import pyautogui
import keyboard
import win32api
import win32con

from PyQt5.QtCore import QObject, pyqtSignal, QThread

from utils.config import Config
from utils.window import get_client_rect_screen

# Lazy imports to avoid PyTorch/PyQt5 DLL conflicts
# These are imported inside methods when needed:
# from core.capture import CaptureProcess, get_available_windows
# from core.detector import Detector, find_nearest_head
# from core.overlay import OverlayProcess
# from core.tracker import AimController
# from core.video_overlay import VideoOverlay

# Video path for intro
INTRO_VIDEO_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "assets", "intro.mp4")


# Default hotkey configuration
DEFAULT_HOTKEYS = {
    'aim_key': 'caps_lock',      # Key to enable aiming (None = always on, 'caps_lock' = toggle)
    'stop': 'ctrl+q',            # Stop tracking
    'pause_resume': 'space',     # Pause/Resume tracking
    'calibrate': 'f6',           # Start calibration
}


def is_caps_lock_on():
    """Check if Caps Lock is enabled."""
    return win32api.GetKeyState(win32con.VK_CAPITAL) & 1


class HotkeyManager:
    """Manages configurable hotkeys for tracking system."""

    def __init__(self, hotkeys: dict = None):
        self.hotkeys = hotkeys or DEFAULT_HOTKEYS.copy()
        self._registered_hotkeys = []

    def get_hotkey(self, action: str) -> str:
        """Get hotkey for an action."""
        return self.hotkeys.get(action)

    def set_hotkey(self, action: str, key: str):
        """Set hotkey for an action."""
        self.hotkeys[action] = key

    def register(self, action: str, callback):
        """Register a hotkey callback."""
        key = self.hotkeys.get(action)
        if key and key != 'caps_lock':  # caps_lock is handled separately
            keyboard.add_hotkey(key, callback)
            self._registered_hotkeys.append(key)

    def unregister_all(self):
        """Unregister all hotkeys."""
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        self._registered_hotkeys.clear()

    def is_aim_active(self) -> bool:
        """Check if aim key is active."""
        aim_key = self.hotkeys.get('aim_key')
        if aim_key is None:
            return True
        elif aim_key == 'caps_lock':
            return is_caps_lock_on()
        else:
            return keyboard.is_pressed(aim_key)

    @staticmethod
    def get_default_hotkeys() -> dict:
        """Get default hotkey configuration."""
        return DEFAULT_HOTKEYS.copy()


class MouseDriver:
    """Mouse control driver wrapper."""

    def __init__(self, dll_path=None, log_callback=None):
        self.dll = None
        self.loaded = False
        self._log = log_callback

        if dll_path is None:
            # Look for DLL in multiple locations
            possible_paths = [
                os.path.join(os.path.dirname(__file__), "..", "drivers", "MouseControl.dll"),
                os.path.join(os.path.dirname(__file__), "MouseControl.dll"),
                os.path.join(os.path.dirname(__file__), "..", "MouseControl.dll"),
                os.path.join(os.path.dirname(__file__), "..", "..", "MouseControl.dll"),
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    dll_path = path
                    break

        if dll_path is None or not os.path.exists(dll_path):
            if self._log:
                self._log(f"MouseControl.dll not found", "ERROR")
            return

        try:
            import ctypes
            self.dll = ctypes.CDLL(dll_path)
            self.loaded = True
            if self._log:
                self._log(f"Mouse driver loaded: {dll_path}", "SUCCESS")
        except Exception as e:
            if self._log:
                self._log(f"Failed to load mouse driver: {e}", "ERROR")

    def is_loaded(self):
        return self.loaded and self.dll is not None

    def move(self, dx, dy):
        if not self.is_loaded():
            return False
        try:
            self.dll.move_R(int(dx), int(dy))
            return True
        except Exception:
            return False

    def left_down(self):
        if not self.is_loaded():
            return False
        try:
            self.dll.click_Left_down()
            return True
        except Exception:
            return False

    def left_up(self):
        if not self.is_loaded():
            return False
        try:
            self.dll.click_Left_up()
            return True
        except Exception:
            return False


class TrackerWorker(QThread):
    """Worker thread for tracking loop."""

    log_message = pyqtSignal(str, str)  # (message, level)
    status_changed = pyqtSignal(str)  # (status)

    def __init__(self, config: dict, window_title: str = None, hotkeys: dict = None, parent=None):
        super().__init__(parent)
        self.config = config
        self.window_title = window_title  # None for fullscreen

        self._running = False
        self._paused = False
        self._stop_requested = False
        self._calibrating = False

        # Hotkey manager
        self._hotkey_manager = HotkeyManager(hotkeys)

        # Components
        self._frame_queue = None
        self._overlay_queue = None
        self._running_event = None
        self._capture_process = None
        self._overlay_process = None
        self._detector = None
        self._aim_controller = None
        self._mouse_driver = None

    def run(self):
        """Main tracking loop."""
        self._running = True
        self._stop_requested = False

        try:
            # Apply configuration
            self._apply_config()

            # Initialize components
            if not self._init_components():
                self.log_message.emit("Failed to initialize components", "ERROR")
                self._running = False
                self.status_changed.emit("stopped")
                return

            # Setup hotkeys
            self._setup_hotkeys()

            self.log_message.emit("Tracking system started", "SUCCESS")
            self.log_message.emit("Hotkeys: [Space] Pause/Resume, [Esc] Stop", "INFO")
            self.status_changed.emit("running")

            # Main detection loop
            self._detection_loop()

        except Exception as e:
            self.log_message.emit(f"Error: {str(e)}", "ERROR")
        finally:
            self._cleanup()
            self._running = False
            self.status_changed.emit("stopped")

    def _apply_config(self):
        """Apply configuration to Config class."""
        Config.FOV_WIDTH = self.config.get('fov_width', 200)
        Config.FOV_HEIGHT = self.config.get('fov_height', 200)
        Config.IMGSZ = max(Config.FOV_WIDTH, Config.FOV_HEIGHT)

        Config.SHOW_OVERLAY = self.config.get('show_overlay', True)
        Config.SHOW_BBOX = self.config.get('show_bbox', True)

        Config.AUTO_CLICK = self.config.get('auto_click', True)
        Config.CLICK_INTERVAL = self.config.get('click_interval', 0.2)
        Config.CLICK_RADIUS_RATIO = self.config.get('click_radius_ratio', 1.1)
        Config.CLICK_RADIUS_MIN = self.config.get('click_radius_min', 5)
        Config.CLICK_RADIUS_MAX = self.config.get('click_radius_max', 50)
        Config.TARGET_PRIORITY = self.config.get('target_priority', 'nearest')

        Config.SNAP_THRESHOLD = self.config.get('snap_threshold', 40)
        Config.SNAP_SENSITIVITY = self.config.get('snap_sensitivity', 2.2)
        Config.SNAP_COOLDOWN = self.config.get('snap_cooldown', 0.2)
        Config.SNAP_UPDATE_THRESHOLD = self.config.get('snap_update_threshold', 20)

        Config.PID_KP = self.config.get('pid_kp', 0.3)
        Config.PID_KI = self.config.get('pid_ki', 0.0)
        Config.PID_KD = self.config.get('pid_kd', 0.001)
        Config.DEADZONE = self.config.get('deadzone', 0)
        Config.PID_COOLDOWN = self.config.get('pid_cooldown', 0.05)
        Config.PID_ERROR_THRESHOLD = self.config.get('pid_error_threshold', 3)

        # Crosshair settings
        Config.CROSSHAIR_SHOW = self.config.get('crosshair_show', True)
        Config.CROSSHAIR_LENGTH = self.config.get('crosshair_length', 10)
        Config.CROSSHAIR_THICKNESS = self.config.get('crosshair_thickness', 2)
        Config.CROSSHAIR_GAP = self.config.get('crosshair_gap', 4)
        Config.CROSSHAIR_COLOR = self.config.get('crosshair_color', 'green')
        Config.CROSSHAIR_CENTER_DOT = self.config.get('crosshair_center_dot', True)
        Config.CROSSHAIR_DOT_SIZE = self.config.get('crosshair_dot_size', 2)
        Config.OVERLAY_OPACITY = self.config.get('overlay_opacity', 100)

        # Team setting
        Config.TARGET_TEAM = self.config.get('target_team', 'T')

        # Operation mode: auto_trigger, auto_aim, auto_aim_fire
        operation_mode = self.config.get('operation_mode', 'auto_aim_fire')
        Config.AUTO_AIM = operation_mode in ['auto_aim', 'auto_aim_fire']
        Config.AUTO_FIRE = operation_mode in ['auto_trigger', 'auto_aim_fire']
        self.log_message.emit(f"Mode: {operation_mode}", "INFO")

        self.log_message.emit(f"Configuration applied: {self.config.get('name', 'Unknown')}", "INFO")
        self.log_message.emit(f"Target team: {Config.TARGET_TEAM}", "INFO")

    def _init_components(self):
        """Initialize all tracking components."""
        # Lazy imports
        import threading
        from core.capture import CaptureProcess
        from core.detector import Detector
        from core.overlay import OverlayProcess
        from core.tracker import AimController
        from core.video_overlay import VideoOverlay

        try:
            # Get window dimensions
            if self.window_title is None:
                # Fullscreen
                win_w, win_h = pyautogui.size()
                win_x, win_y = 0, 0
                window_choice = -1
                all_windows = []
                self.log_message.emit("Target: Fullscreen", "INFO")
            else:
                # Specific window
                windows = gw.getWindowsWithTitle(self.window_title)
                if not windows:
                    self.log_message.emit(f"Window not found: {self.window_title}", "ERROR")
                    return False
                target_window = windows[0]
                rect = get_client_rect_screen(target_window._hWnd)
                if rect:
                    win_x, win_y, win_w, win_h = rect
                else:
                    win_x, win_y = target_window.left, target_window.top
                    win_w, win_h = target_window.width, target_window.height
                # For CaptureProcess compatibility
                all_windows = [self.window_title]
                window_choice = 0
                self.log_message.emit(f"Target: {self.window_title}", "INFO")


            # Initialize queues and events first
            self._frame_queue = Queue(maxsize=2)
            self._overlay_queue = Queue(maxsize=2) if Config.SHOW_OVERLAY else None
            self._running_event = Event()
            self._running_event.set()

            # Start all initialization in parallel with video
            video_overlay = None
            init_error = [None]  # Use list to capture error from thread

            def load_all_components():
                """Load model and start all processes in background."""
                try:
                    # Initialize detector
                    model_path = self.config.get('model_path', '')
                    if model_path and os.path.exists(model_path):
                        self._detector = Detector(model_path)
                        self.log_message.emit(f"Model loaded: {os.path.basename(model_path)}", "SUCCESS")
                    else:
                        self.log_message.emit("No model specified or model not found", "WARN")
                        self._detector = Detector()

                    # Check admin privileges
                    import ctypes
                    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                    if not is_admin:
                        self.log_message.emit("WARNING: Not running as admin!", "WARN")

                    # Initialize mouse driver and aim controller
                    self._mouse_driver = MouseDriver(log_callback=self.log_message.emit)
                    if self._mouse_driver.is_loaded():
                        self._aim_controller = AimController(self._mouse_driver)
                    else:
                        self.log_message.emit("Mouse driver not available", "WARN")
                        self._aim_controller = None

                    # Start capture process
                    self._capture_process = CaptureProcess(self._frame_queue, self._running_event)
                    self._capture_process.start(window_choice, all_windows)

                    # Start overlay process (will be hidden behind video)
                    if Config.SHOW_OVERLAY:
                        self._overlay_process = OverlayProcess(self._overlay_queue, self._running_event)
                        self._overlay_process.start(win_x, win_y, win_w, win_h)
                except Exception as e:
                    init_error[0] = str(e)

            # Start initialization thread
            init_thread = threading.Thread(target=load_all_components)
            init_thread.start()

            # Play intro video while everything initializes
            if os.path.exists(INTRO_VIDEO_PATH):
                video_overlay = VideoOverlay(INTRO_VIDEO_PATH)
                video_overlay.play(win_x, win_y, win_w, win_h)
                video_overlay.wait()

            # Wait for initialization to complete
            init_thread.join()

            if init_error[0]:
                self.log_message.emit(f"Init error: {init_error[0]}", "ERROR")
                return False

            return True

        except Exception as e:
            self.log_message.emit(f"Init error: {str(e)}", "ERROR")
            return False

    def _detection_loop(self):
        """Main detection and tracking loop."""
        # Lazy import
        from core.detector import find_nearest_head

        last_click_time = 0
        last_target_id = None
        fps_counter = 0
        fps_start_time = time.time()
        current_fps = 0

        while not self._stop_requested:
            # Handle pause
            if self._paused:
                time.sleep(0.1)
                continue

            # Handle calibration
            if self._calibrating:
                self._run_calibration(find_nearest_head)
                self._calibrating = False
                continue

            # Get frame
            try:
                frame = self._frame_queue.get(timeout=0.1)
            except Exception:
                continue

            # Calculate FPS
            fps_counter += 1
            elapsed = time.time() - fps_start_time
            if elapsed >= 1.0:
                current_fps = fps_counter / elapsed
                fps_counter = 0
                fps_start_time = time.time()

            h, w = frame.shape[:2]
            center_x, center_y = w // 2, h // 2

            half_w, half_h = Config.FOV_WIDTH // 2, Config.FOV_HEIGHT // 2
            x1_roi = max(0, center_x - half_w)
            y1_roi = max(0, center_y - half_h)
            x2_roi = min(w, center_x + half_w)
            y2_roi = min(h, center_y + half_h)

            # Check if aim key is active
            aim_active = self._hotkey_manager.is_aim_active()

            # Detect targets (always detect for display, control based on aim_active)
            head_x, head_y = None, None
            current_conf, current_dist = 0, 0
            click_radius = Config.CLICK_RADIUS_MIN
            current_mode = 'PID'

            all_boxes = []
            if self._detector and self._detector.model:
                boxes = self._detector.detect(frame, roi=(x1_roi, y1_roi, x2_roi, y2_roi))
                # Collect all boxes for overlay display (always)
                for box in boxes:
                    cls = int(box.cls[0])
                    bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                    # Convert to screen coordinates
                    all_boxes.append({
                        'bbox': (bx1 + x1_roi, by1 + y1_roi, bx2 + x1_roi, by2 + y1_roi),
                        'cls': cls
                    })

                # Only process targeting when aim is active
                if aim_active:
                    target, _ = find_nearest_head(boxes, center_x, center_y, x1_roi, y1_roi,
                                                  priority=Config.TARGET_PRIORITY,
                                                  target_team=Config.TARGET_TEAM)

                    if target:
                        head_x, head_y, head_r, head_cls, head_conf, head_bbox = target
                        current_conf = head_conf

                        click_radius = int(head_r * Config.CLICK_RADIUS_RATIO)
                        click_radius = max(Config.CLICK_RADIUS_MIN, min(Config.CLICK_RADIUS_MAX, click_radius))

                        # Calculate error
                        error_x = head_x - center_x
                        error_y = head_y - center_y
                        current_dist = math.sqrt(error_x ** 2 + error_y ** 2)

                        # Target tracking
                        target_id = head_cls
                        if last_target_id is not None and target_id != last_target_id:
                            if self._aim_controller:
                                self._aim_controller.reset()
                        last_target_id = target_id

                        # Auto fire (check AUTO_FIRE config)
                        current_time = time.time()
                        if Config.AUTO_FIRE and current_dist <= click_radius:
                            if self._mouse_driver and self._mouse_driver.is_loaded():
                                if current_time - last_click_time >= Config.CLICK_INTERVAL:
                                    self._mouse_driver.left_down()
                                    time.sleep(0.005)
                                    self._mouse_driver.left_up()
                                    last_click_time = current_time

                        # Aim control (check AUTO_AIM config)
                        if Config.AUTO_AIM and self._aim_controller:
                            current_mode = self._aim_controller.update(error_x, error_y, target_id)
                    else:
                        # No target
                        if last_target_id:
                            if self._aim_controller:
                                self._aim_controller.reset()
                            last_target_id = None
                else:
                    # Reset when aim is disabled
                    if last_target_id:
                        if self._aim_controller:
                            self._aim_controller.reset()
                        last_target_id = None

            # Send overlay data
            if self._overlay_queue and Config.SHOW_OVERLAY:
                try:
                    while not self._overlay_queue.empty():
                        self._overlay_queue.get_nowait()
                    self._overlay_queue.put_nowait({
                        'roi': (x1_roi, y1_roi, x2_roi, y2_roi),
                        'center': (center_x, center_y),
                        'head': (head_x, head_y),
                        'aim_active': aim_active,
                        'conf': current_conf,
                        'dist': current_dist,
                        'fps': current_fps,
                        'click_radius': click_radius,
                        'mode': current_mode,
                        'sens': Config.SNAP_SENSITIVITY,
                        'kp': Config.PID_KP,
                        'show_bbox': Config.SHOW_BBOX,
                        'boxes': all_boxes,
                        'crosshair_show': Config.CROSSHAIR_SHOW,
                        'crosshair_length': Config.CROSSHAIR_LENGTH,
                        'crosshair_thickness': Config.CROSSHAIR_THICKNESS,
                        'crosshair_gap': Config.CROSSHAIR_GAP,
                        'crosshair_color': Config.CROSSHAIR_COLOR,
                        'crosshair_center_dot': Config.CROSSHAIR_CENTER_DOT,
                        'crosshair_dot_size': Config.CROSSHAIR_DOT_SIZE,
                        'overlay_opacity': Config.OVERLAY_OPACITY,
                    })
                except Exception:
                    pass

    def _setup_hotkeys(self):
        """Setup keyboard hotkeys."""
        self._hotkey_manager.register('pause_resume', self._on_hotkey_pause_resume)
        self._hotkey_manager.register('stop', self._on_hotkey_stop)
        self._hotkey_manager.register('calibrate', self._on_hotkey_calibrate)

        # Log hotkey info
        aim_key = self._hotkey_manager.get_hotkey('aim_key')
        stop_key = self._hotkey_manager.get_hotkey('stop')
        pause_key = self._hotkey_manager.get_hotkey('pause_resume')
        self.log_message.emit(f"Aim key: [{aim_key or 'Always On'}]", "INFO")
        self.log_message.emit(f"Hotkeys: [{pause_key}] Pause/Resume, [{stop_key}] Stop", "INFO")

    def _on_hotkey_pause_resume(self):
        """Handle pause/resume hotkey."""
        if self._paused:
            self.resume()
        else:
            self.pause()

    def _on_hotkey_stop(self):
        """Handle stop hotkey."""
        self.stop()

    def _on_hotkey_calibrate(self):
        """Handle calibrate hotkey."""
        if not self._detector or not self._detector.model:
            self.log_message.emit("Cannot calibrate: no model loaded", "ERROR")
            return
        if not self._mouse_driver or not self._mouse_driver.is_loaded():
            self.log_message.emit("Cannot calibrate: mouse driver not loaded", "ERROR")
            return
        self._calibrating = True
        self.log_message.emit("Starting calibration - aim at a static target", "INFO")

    def _send_calibration_overlay(self, cx, cy, x1, y1, x2, y2, calib_move=None):
        """Send overlay data during calibration."""
        if self._overlay_queue and Config.SHOW_OVERLAY:
            try:
                while not self._overlay_queue.empty():
                    self._overlay_queue.get_nowait()
                self._overlay_queue.put_nowait({
                    'roi': (x1, y1, x2, y2),
                    'center': (cx, cy),
                    'head': (None, None),
                    'aim_active': True,
                    'conf': 0,
                    'dist': 0,
                    'fps': 0,
                    'click_radius': Config.CLICK_RADIUS_MIN,
                    'mode': 'CALIB',
                    'sens': Config.SNAP_SENSITIVITY,
                    'kp': Config.PID_KP,
                    'calibrating': True,
                    'calib_move': calib_move,
                    'crosshair_show': Config.CROSSHAIR_SHOW,
                    'crosshair_length': Config.CROSSHAIR_LENGTH,
                    'crosshair_thickness': Config.CROSSHAIR_THICKNESS,
                    'crosshair_gap': Config.CROSSHAIR_GAP,
                    'crosshair_color': Config.CROSSHAIR_COLOR,
                    'crosshair_center_dot': Config.CROSSHAIR_CENTER_DOT,
                    'crosshair_dot_size': Config.CROSSHAIR_DOT_SIZE,
                    'overlay_opacity': Config.OVERLAY_OPACITY,
                })
            except Exception:
                pass

    def _run_calibration(self, find_nearest_head):
        """Run calibration to determine snap sensitivity."""
        CALIBRATE_SAMPLES = 3
        current_sens = Config.SNAP_SENSITIVITY

        self.log_message.emit(f"Calibration: current SENS={current_sens:.3f}", "INFO")
        time.sleep(0.5)

        for iteration in range(CALIBRATE_SAMPLES):
            self.log_message.emit(f"Calibration iteration {iteration + 1}/{CALIBRATE_SAMPLES}", "INFO")

            # Clear queue and get fresh frame
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except:
                    break
            time.sleep(0.1)

            try:
                frame = self._frame_queue.get(timeout=1)
            except:
                self.log_message.emit("Failed to get frame", "ERROR")
                continue

            h, w = frame.shape[:2]
            cx, cy = w // 2, h // 2

            # Detect target
            x1 = max(0, cx - Config.FOV_WIDTH // 2)
            y1 = max(0, cy - Config.FOV_HEIGHT // 2)
            x2 = min(w, cx + Config.FOV_WIDTH // 2)
            y2 = min(h, cy + Config.FOV_HEIGHT // 2)

            boxes = self._detector.detect(frame, roi=(x1, y1, x2, y2))
            # Use 'ALL' to target both teams during calibration
            target, _ = find_nearest_head(boxes, cx, cy, x1, y1, target_team='ALL')

            if not target:
                self.log_message.emit("No target detected", "WARN")
                self._send_calibration_overlay(cx, cy, x1, y1, x2, y2)
                continue

            target_x, target_y = target[0], target[1]
            error_x = target_x - cx
            error_y = target_y - cy
            error_dist = math.sqrt(error_x ** 2 + error_y ** 2)

            self.log_message.emit(f"Target at ({target_x}, {target_y}), error: {error_dist:.1f}px", "INFO")

            if error_dist < 15:
                self.log_message.emit("Error too small, moving crosshair...", "INFO")
                # Show calibration move line
                self._send_calibration_overlay(cx, cy, x1, y1, x2, y2, calib_move=(100, 0))
                self._mouse_driver.move(100, 0)
                time.sleep(0.3)
                continue

            # Move using current sensitivity
            move_x = int(error_x * current_sens)
            move_y = int(error_y * current_sens)

            # Show calibration move line
            self._send_calibration_overlay(cx, cy, x1, y1, x2, y2, calib_move=(error_x, error_y))

            self._mouse_driver.move(move_x, move_y)
            time.sleep(0.2)

            # Get frame after move
            while not self._frame_queue.empty():
                try:
                    self._frame_queue.get_nowait()
                except:
                    break
            time.sleep(0.1)

            try:
                frame = self._frame_queue.get(timeout=1)
            except:
                self.log_message.emit("Failed to get frame after move", "ERROR")
                continue

            # Detect new position
            boxes = self._detector.detect(frame, roi=(x1, y1, x2, y2))
            new_target, _ = find_nearest_head(boxes, cx, cy, x1, y1, target_team='ALL')

            if not new_target:
                self.log_message.emit("Lost target after move", "WARN")
                continue

            new_target_x, new_target_y = new_target[0], new_target[1]
            actual_move_x = target_x - new_target_x
            actual_move_y = target_y - new_target_y

            self.log_message.emit(f"Actual move: ({actual_move_x:.0f}, {actual_move_y:.0f})", "INFO")

            # Adjust sensitivity
            if abs(actual_move_x) > 5:
                adjust = error_x / actual_move_x
                current_sens = current_sens * adjust
            elif abs(actual_move_y) > 5:
                adjust = error_y / actual_move_y
                current_sens = current_sens * adjust

            current_sens = max(0.1, min(5.0, current_sens))

            # Move back for next iteration
            if iteration < CALIBRATE_SAMPLES - 1:
                self._mouse_driver.move(-move_x, -move_y)
                time.sleep(0.3)

        # Update config
        Config.SNAP_SENSITIVITY = current_sens
        Config.PID_KP = max(0.1, min(2.0, current_sens / 3.0))

        if self._aim_controller:
            self._aim_controller.snap_sensitivity = Config.SNAP_SENSITIVITY
            self._aim_controller.pid.kp = Config.PID_KP

        self.log_message.emit(f"Calibration complete! SENS={Config.SNAP_SENSITIVITY:.3f}, Kp={Config.PID_KP:.3f}", "SUCCESS")

    def _cleanup(self):
        """Clean up all resources."""
        self.log_message.emit("Stopping tracking system...", "INFO")

        # Remove hotkeys
        self._hotkey_manager.unregister_all()

        if self._running_event:
            self._running_event.clear()

        if self._capture_process:
            self._capture_process.stop()

        if self._overlay_process:
            self._overlay_process.stop()

        self.log_message.emit("Tracking system stopped", "INFO")

    def pause(self):
        """Pause the tracking loop."""
        self._paused = True
        self.log_message.emit("Tracking paused", "WARN")
        self.status_changed.emit("paused")

    def resume(self):
        """Resume the tracking loop."""
        self._paused = False
        self.log_message.emit("Tracking resumed", "SUCCESS")
        self.status_changed.emit("running")

    def stop(self):
        """Stop the tracking loop."""
        self._stop_requested = True
        if self._running_event:
            self._running_event.clear()

    def is_running(self):
        return self._running

    def is_paused(self):
        return self._paused


class TrackerManager(QObject):
    """Manager for tracking system."""

    log_message = pyqtSignal(str, str)  # (message, level)
    status_changed = pyqtSignal(str)  # (status: running/paused/stopped)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        self._hotkeys = DEFAULT_HOTKEYS.copy()

    def start(self, config: dict, window_title: str = None):
        """Start the tracking system.

        Args:
            config: Configuration dictionary
            window_title: Target window title, or None for fullscreen
        """
        if self._worker and self._worker.is_running():
            self.log_message.emit("Tracking is already running", "WARN")
            return

        self._worker = TrackerWorker(config, window_title, self._hotkeys, self)
        self._worker.log_message.connect(self.log_message)
        self._worker.status_changed.connect(self.status_changed)
        self._worker.start()

    def pause(self):
        """Pause the tracking system."""
        if self._worker and self._worker.is_running():
            if not self._worker.is_paused():
                self._worker.pause()

    def resume(self):
        """Resume the tracking system."""
        if self._worker and self._worker.is_running():
            if self._worker.is_paused():
                self._worker.resume()

    def stop(self):
        """Stop the tracking system."""
        if self._worker:
            self._worker.stop()
            self._worker.wait(5000)  # Wait up to 5 seconds
            self._worker = None

    def is_running(self) -> bool:
        """Check if tracking is running."""
        return self._worker is not None and self._worker.is_running()

    def is_paused(self) -> bool:
        """Check if tracking is paused."""
        return self._worker is not None and self._worker.is_paused()

    def set_target_team(self, team: str):
        """Set target team during runtime."""
        Config.TARGET_TEAM = team
        self.log_message.emit(f"Target team changed to: {team}", "INFO")

    # === Hotkey configuration interface ===

    def get_hotkeys(self) -> dict:
        """Get current hotkey configuration."""
        return self._hotkeys.copy()

    def set_hotkeys(self, hotkeys: dict):
        """Set hotkey configuration. Takes effect on next start."""
        self._hotkeys.update(hotkeys)

    def set_hotkey(self, action: str, key: str):
        """Set a single hotkey. Takes effect on next start."""
        self._hotkeys[action] = key

    def get_hotkey(self, action: str) -> str:
        """Get a single hotkey."""
        return self._hotkeys.get(action)

    @staticmethod
    def get_default_hotkeys() -> dict:
        """Get default hotkey configuration."""
        return DEFAULT_HOTKEYS.copy()
