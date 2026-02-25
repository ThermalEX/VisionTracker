"""
Demo12.1 - ADRC (Active Disturbance Rejection Control)
自抗扰控制器 - 主动估计并补偿目标运动，比PID更好地追踪运动目标

ADRC 优势：
- ESO (扩展状态观测器) 实时估计目标速度（扰动）
- 自动前馈补偿，预测目标运动方向
- 大误差和小误差均可良好处理，无需切换模式
- 对噪声和延迟更鲁棒

Overlay 新增显示：
- 橙色箭头：ESO 估计的目标速度方向（ADRC 的预测量）

F6 自动校准 b0
"""

import pygetwindow as gw
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from multiprocessing import Process, Queue, Event
import time
import win32gui
import win32con
import win32api
import keyboard
import mss
import pyautogui
import os
import math
import ctypes
import glob

from MouseDriver import MouseDriver

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()


def get_client_rect_screen(hwnd):
    try:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        pt_min = win32gui.ClientToScreen(hwnd, (0, 0))
        pt_max = win32gui.ClientToScreen(hwnd, (right, bottom))
        return (
            int(pt_min[0]),
            int(pt_min[1]),
            int(pt_max[0] - pt_min[0]),
            int(pt_max[1] - pt_min[1]),
        )
    except:
        return None


def check_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


# ==================== ADRC Controller ====================
class ADRCController:
    """
    Discrete ADRC for frame-by-frame tracking.

    Continuous-time ESO does NOT work well here because it misattributes
    control-caused error changes as disturbances, causing divergence.

    Instead, use a per-frame discrete disturbance estimator:

      System model (per frame):
        error_new = error_old - b0 * u_applied + target_motion

      Isolate target motion:
        raw_dist = (error_new - error_old) + b0 * u_applied

      Low-pass filter to reduce noise:
        z2 = alpha * raw_dist + (1 - alpha) * z2

      Control law:
        u = kp * error + z2 / b0
          - kp * error : proportional feedback (pull toward target)
          - z2 / b0    : feedforward (pre-compensate predicted target motion)

    Parameters:
      b0:    Control effectiveness. Calibrated by F6. When correct,
             raw_dist cleanly separates target motion from control effect.
      kp:    Proportional gain (same scale as PID Kp, ~0.2-0.5).
      alpha: ESO smoothing factor (0~1). Higher = faster disturbance
             tracking but more noise. Recommended: 0.2~0.4.
    """

    def __init__(self, b0=1.0, kp=0.3, alpha=0.3, max_output=200):
        self.b0 = b0
        self.kp = kp
        self.alpha = alpha
        self.max_output = max_output

        # Disturbance estimate (target velocity in pixels/frame)
        self.z2_x = 0.0
        self.z2_y = 0.0

        # Previous frame error and applied control
        self.prev_error_x = 0.0
        self.prev_error_y = 0.0
        self.prev_u_x = 0.0
        self.prev_u_y = 0.0

        self.first_run = True

    def reset(self):
        self.z2_x = 0.0
        self.z2_y = 0.0
        self.prev_error_x = 0.0
        self.prev_error_y = 0.0
        self.prev_u_x = 0.0
        self.prev_u_y = 0.0
        self.first_run = True

    def compute(self, error_x, error_y, u_applied_x=None, u_applied_y=None):
        """
        Update disturbance estimate and compute control output.

        Args:
            error_x, error_y:         Current pixel error (target - center).
            u_applied_x, u_applied_y: Mouse movement applied last frame.
                                       Pass 0 if no move was made (dead zone etc.).
                                       If None, uses internally stored prev_u.
        Returns:
            (output_x, output_y): Desired mouse movement (float pixels).
        """
        # Update stored applied control from external tracker
        if u_applied_x is not None:
            self.prev_u_x = float(u_applied_x)
            self.prev_u_y = float(u_applied_y)

        if self.first_run:
            self.prev_error_x = float(error_x)
            self.prev_error_y = float(error_y)
            self.z2_x = 0.0
            self.z2_y = 0.0
            self.first_run = False
            return 0.0, 0.0

        # Isolate target motion from control effect:
        #   raw_dist = (error_change) + b0 * u_applied
        #   When b0 is correct: raw_dist = pure target_motion
        raw_dist_x = (error_x - self.prev_error_x) + self.b0 * self.prev_u_x
        raw_dist_y = (error_y - self.prev_error_y) + self.b0 * self.prev_u_y

        # Low-pass filter disturbance estimate
        self.z2_x = self.alpha * raw_dist_x + (1.0 - self.alpha) * self.z2_x
        self.z2_y = self.alpha * raw_dist_y + (1.0 - self.alpha) * self.z2_y

        # Store current error for next frame
        self.prev_error_x = float(error_x)
        self.prev_error_y = float(error_y)

        # Control: proportional feedback + disturbance feedforward
        u_x = self.kp * error_x + self.z2_x / self.b0
        u_y = self.kp * error_y + self.z2_y / self.b0

        u_x = max(-self.max_output, min(self.max_output, u_x))
        u_y = max(-self.max_output, min(self.max_output, u_y))

        return u_x, u_y

    def get_disturbance(self):
        """Return estimated target velocity (pixels/frame) for display."""
        return self.z2_x, self.z2_y


# ==================== Configuration ====================
FOV_WIDTH = 200
FOV_HEIGHT = 200
CONF_THRESHOLD = 0.3
IMGSZ = 200

AIM_ENABLED = True
AIM_KEY = "caps_lock"

CLICK_RADIUS_RATIO = 1.1
CLICK_RADIUS_MIN = 5
CLICK_RADIUS_MAX = 50
AUTO_CLICK = True
CLICK_INTERVAL = 0.2
TARGET_PRIORITY = "nearest"
SHOW_OVERLAY = True

# ==================== ADRC Parameters ====================
# ADRC_KP (Proportional gain):
#   - Same meaning as PID Kp. Recommended: 0.2~0.5.
#
# ADRC_B0 (Control effectiveness):
#   - Pixels of error reduced per mouse unit sent.
#   - Calibrated automatically by F6.
#   - When correct, disturbance estimate = pure target motion.
#
# ADRC_ALPHA (ESO smoothing factor, 0~1):
#   - How much weight to give the new disturbance estimate each frame.
#   - Higher: faster disturbance tracking, more noise-sensitive.
#   - Lower: smoother but slower to react to changing target velocity.
#   - Recommended: 0.2~0.4
#
# DEADZONE: Stop moving when error < this value (pixels)
# =========================================================

ADRC_KP = 0.3      # Proportional gain (same scale as PID Kp)
ADRC_B0 = 1.0      # Control effectiveness (calibrated by F6)
ADRC_ALPHA = 0.3   # ESO smoothing factor (0~1)
DEADZONE = 3

CALIBRATE_SAMPLES = 3


# --- Capture process ---
def capture_process(frame_queue, running_event, choice, all_windows):
    target_window_title = None
    monitor = {}

    if choice == -1:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
    else:
        target_window_title = all_windows[choice]
        target_window = gw.getWindowsWithTitle(target_window_title)[0]
        rect = get_client_rect_screen(target_window._hWnd)
        if rect:
            monitor = {
                "left": rect[0],
                "top": rect[1],
                "width": rect[2],
                "height": rect[3],
            }
        else:
            monitor = {
                "top": target_window.top,
                "left": target_window.left,
                "width": target_window.width,
                "height": target_window.height,
            }

    with mss.mss() as sct:
        while running_event.is_set():
            try:
                if choice != -1:
                    target_window = gw.getWindowsWithTitle(target_window_title)[0]
                    if not target_window:
                        break
                    rect = get_client_rect_screen(target_window._hWnd)
                    if rect:
                        (
                            monitor["left"],
                            monitor["top"],
                            monitor["width"],
                            monitor["height"],
                        ) = rect
                    if monitor["width"] <= 0 or monitor["height"] <= 0:
                        time.sleep(0.1)
                        continue

                sct_img = sct.grab(monitor)
                frame = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)

                while not frame_queue.empty():
                    try:
                        frame_queue.get_nowait()
                    except:
                        break
                try:
                    frame_queue.put_nowait(frame)
                except:
                    pass
            except Exception:
                time.sleep(0.1)


# --- Overlay process ---
def overlay_process(overlay_queue, running_event, win_x, win_y, win_w, win_h):
    window_name = "Overlay"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    dummy = np.zeros((win_h, win_w, 3), dtype=np.uint8)
    cv2.imshow(window_name, dummy)
    cv2.waitKey(1)

    time.sleep(0.05)
    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd:
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style &= ~(
            win32con.WS_CAPTION
            | win32con.WS_THICKFRAME
            | win32con.WS_MINIMIZE
            | win32con.WS_MAXIMIZE
            | win32con.WS_SYSMENU
            | win32con.WS_BORDER
        )
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style
            | win32con.WS_EX_LAYERED
            | win32con.WS_EX_TRANSPARENT
            | win32con.WS_EX_TOPMOST
            | win32con.WS_EX_NOACTIVATE,
        )

        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            win_x,
            win_y,
            win_w,
            win_h,
            win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW,
        )

        win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_COLORKEY)

    last_topmost = time.time()

    while running_event.is_set():
        try:
            data = overlay_queue.get(timeout=0.05)
        except:
            cv2.waitKey(1)
            continue

        overlay = np.zeros((win_h, win_w, 3), dtype=np.uint8)

        x1_roi, y1_roi, x2_roi, y2_roi = data.get("roi", (0, 0, 0, 0))
        center_x, center_y = data.get("center", (win_w // 2, win_h // 2))
        head_x, head_y = data.get("head", (None, None))
        aim_active = data.get("aim_active", False)
        conf = data.get("conf", 0)
        dist = data.get("dist", 0)
        click_radius = data.get("click_radius", CLICK_RADIUS_MIN)
        b0 = data.get("b0", ADRC_B0)

        # FOV corners (same style as Demo11.1)
        corner_len = 30
        cv2.line(
            overlay, (x1_roi, y1_roi), (x1_roi + corner_len, y1_roi), (255, 255, 255), 1
        )
        cv2.line(
            overlay, (x1_roi, y1_roi), (x1_roi, y1_roi + corner_len), (255, 255, 255), 1
        )
        cv2.line(
            overlay, (x2_roi, y1_roi), (x2_roi - corner_len, y1_roi), (255, 255, 255), 1
        )
        cv2.line(
            overlay, (x2_roi, y1_roi), (x2_roi, y1_roi + corner_len), (255, 255, 255), 1
        )
        cv2.line(
            overlay, (x1_roi, y2_roi), (x1_roi + corner_len, y2_roi), (255, 255, 255), 1
        )
        cv2.line(
            overlay, (x1_roi, y2_roi), (x1_roi, y2_roi - corner_len), (255, 255, 255), 1
        )
        cv2.line(
            overlay, (x2_roi, y2_roi), (x2_roi - corner_len, y2_roi), (255, 255, 255), 1
        )
        cv2.line(
            overlay, (x2_roi, y2_roi), (x2_roi, y2_roi - corner_len), (255, 255, 255), 1
        )

        # Crosshair dots (outside FOV)
        dot_offset = FOV_WIDTH // 2 + 8
        cv2.circle(overlay, (center_x - dot_offset, center_y), 3, (255, 255, 255), -1)
        cv2.circle(overlay, (center_x + dot_offset, center_y), 3, (255, 255, 255), -1)
        cv2.circle(overlay, (center_x, center_y - dot_offset), 3, (255, 255, 255), -1)
        cv2.circle(overlay, (center_x, center_y + dot_offset), 3, (255, 255, 255), -1)

        if head_x is not None:
            # Target direction line (cyan for ADRC)
            dx = head_x - center_x
            dy = head_y - center_y
            dist_to_head = math.sqrt(dx * dx + dy * dy)
            if dist_to_head > 1:
                dx_n = dx / dist_to_head
                dy_n = dy / dist_to_head
                start_dist = FOV_WIDTH // 2 + 5
                end_dist = FOV_WIDTH // 2 + 40
                sx = int(center_x + dx_n * start_dist)
                sy = int(center_y + dy_n * start_dist)
                ex = int(center_x + dx_n * end_dist)
                ey = int(center_y + dy_n * end_dist)
                cv2.line(overlay, (sx, sy), (ex, ey), (0, 255, 255), 3)


        # HUD text
        aim_color = (0, 255, 0) if aim_active else (0, 0, 255)
        cv2.putText(
            overlay,
            f"AIM:{'ON' if aim_active else 'OFF'}",
            (10, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            aim_color,
            2,
        )
        cv2.putText(
            overlay,
            f"FIRE:{'ON' if AUTO_CLICK else 'OFF'}",
            (120, 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2,
        )
        cv2.putText(
            overlay,
            "Mode:ADRC",
            (10, 50),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 255),
            1,
        )
        cv2.putText(
            overlay,
            f"b0:{b0:.3f} kp:{ADRC_KP:.2f} a:{ADRC_ALPHA:.2f}",
            (10, 75),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 0),
            1,
        )
        if conf > 0:
            cv2.putText(
                overlay,
                f"Conf:{conf:.2f} Dist:{dist:.0f}px",
                (10, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 0, 255),
                1,
            )

        cv2.imshow(window_name, overlay)

        if time.time() - last_topmost > 3.0:
            if hwnd:
                try:
                    win32gui.SetWindowPos(
                        hwnd,
                        win32con.HWND_TOPMOST,
                        0,
                        0,
                        0,
                        0,
                        win32con.SWP_NOMOVE
                        | win32con.SWP_NOSIZE
                        | win32con.SWP_NOACTIVATE,
                    )
                except:
                    pass
            last_topmost = time.time()

        cv2.waitKey(1)

    cv2.destroyAllWindows()


def find_nearest_head(boxes, center_x, center_y, x1_roi, y1_roi):
    heads = []
    for box in boxes:
        cls = int(box.cls[0])
        if cls not in [0, 2]:
            continue
        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])

        real_x1 = bx1 + x1_roi
        real_y1 = by1 + y1_roi
        real_x2 = bx2 + x1_roi
        real_y2 = by2 + y1_roi

        head_cx = (real_x1 + real_x2) // 2
        head_cy = (real_y1 + real_y2) // 2
        head_r = min(real_x2 - real_x1, real_y2 - real_y1) // 2

        dist = math.sqrt((head_cx - center_x) ** 2 + (head_cy - center_y) ** 2)
        heads.append(
            {
                "cx": head_cx,
                "cy": head_cy,
                "r": head_r,
                "dist": dist,
                "conf": conf,
                "cls": cls,
                "bbox": (real_x1, real_y1, real_x2, real_y2),
            }
        )

    if not heads:
        return None, []
    heads.sort(key=lambda h: h["dist"] if TARGET_PRIORITY == "nearest" else -h["conf"])
    best = heads[0]
    return (
        best["cx"],
        best["cy"],
        best["r"],
        best["cls"],
        best["conf"],
        best["bbox"],
    ), heads


def is_caps_lock_on():
    return win32api.GetKeyState(win32con.VK_CAPITAL) & 1


def detect_target(model, use_trt, frame):
    """Detect nearest head and return (cx, cy) in frame coordinates."""
    h, w = frame.shape[:2]
    cx, cy = w // 2, h // 2
    x1 = max(0, cx - FOV_WIDTH // 2)
    y1 = max(0, cy - FOV_HEIGHT // 2)
    x2 = min(w, cx + FOV_WIDTH // 2)
    y2 = min(h, cy + FOV_HEIGHT // 2)
    crop = frame[y1:y2, x1:x2]
    if use_trt:
        results = model(crop, conf=CONF_THRESHOLD, verbose=False)
    else:
        results = model(crop, conf=CONF_THRESHOLD, imgsz=IMGSZ, verbose=False)
    boxes = []
    for r in results:
        boxes.extend(r.boxes)
    target, _ = find_nearest_head(boxes, cx, cy, x1, y1)
    if target:
        return target[0], target[1]
    return None, None


def calibrate(model, use_trt, frame_queue, mouse, adrc, overlay_queue):
    """Calibrate ADRC b0 (control effectiveness) using one-shot move method."""
    global ADRC_B0

    print("\n" + "=" * 50)
    print("开始校准 b0 - 请将准心对准一个静止目标")
    print(f"当前 b0 = {adrc.b0:.3f}")
    print("=" * 50)

    time.sleep(0.5)

    for iteration in range(CALIBRATE_SAMPLES):
        print(f"\n--- 迭代 {iteration + 1}/{CALIBRATE_SAMPLES} (b0={adrc.b0:.3f}) ---")

        while not frame_queue.empty():
            try:
                frame_queue.get_nowait()
            except:
                break
        time.sleep(0.1)

        try:
            frame = frame_queue.get(timeout=1)
        except:
            print("  获取帧失败")
            continue

        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2

        target_x, target_y = detect_target(model, use_trt, frame)
        if target_x is None:
            print("  未检测到目标")
            continue

        error_x = target_x - cx
        error_y = target_y - cy
        error_dist = math.sqrt(error_x**2 + error_y**2)

        if overlay_queue:
            try:
                while not overlay_queue.empty():
                    overlay_queue.get_nowait()
                overlay_queue.put_nowait(
                    {
                        "roi": (
                            cx - FOV_WIDTH // 2,
                            cy - FOV_HEIGHT // 2,
                            cx + FOV_WIDTH // 2,
                            cy + FOV_HEIGHT // 2,
                        ),
                        "center": (cx, cy),
                        "head": (target_x, target_y),
                        "aim_active": True,
                        "conf": 1.0,
                        "dist": error_dist,
                        "click_radius": 15,
                        "b0": adrc.b0,
                        "z2_x": 0.0,
                        "z2_y": 0.0,
                    }
                )
            except:
                pass
        time.sleep(0.3)

        print(
            f"  目标: ({target_x}, {target_y}), 误差: ({error_x:.0f}, {error_y:.0f}), 距离: {error_dist:.1f}px"
        )

        if error_dist < 15:
            print("  误差太小，移开准心...")
            mouse.move(100, 0)
            time.sleep(0.3)
            continue

        # One-shot move: send error * b0
        # If b0 is correct, this should bring error to ~0
        move_x = int(error_x * adrc.b0)
        move_y = int(error_y * adrc.b0)
        print(f"  发送移动: ({move_x}, {move_y})")
        mouse.move(move_x, move_y)
        time.sleep(0.2)

        while not frame_queue.empty():
            try:
                frame_queue.get_nowait()
            except:
                break
        time.sleep(0.1)

        try:
            frame = frame_queue.get(timeout=1)
        except:
            print("  获取帧失败")
            continue

        new_target_x, new_target_y = detect_target(model, use_trt, frame)
        if new_target_x is None:
            print("  移动后未检测到目标")
            continue

        actual_move_x = target_x - new_target_x
        actual_move_y = target_y - new_target_y
        print(f"  实际视角移动: ({actual_move_x:.0f}, {actual_move_y:.0f})")

        # Adjust b0: we wanted to move error_x, actually moved actual_move_x
        if abs(actual_move_x) > 5:
            adjust = error_x / actual_move_x
            adrc.b0 = max(0.05, min(10.0, adrc.b0 * adjust))
            print(f"  调整系数: {adjust:.3f}, 新 b0: {adrc.b0:.3f}")
        elif abs(actual_move_y) > 5:
            adjust = error_y / actual_move_y
            adrc.b0 = max(0.05, min(10.0, adrc.b0 * adjust))
            print(f"  调整系数: {adjust:.3f}, 新 b0: {adrc.b0:.3f}")

        if iteration < CALIBRATE_SAMPLES - 1:
            mouse.move(-move_x, -move_y)
            time.sleep(0.3)

    # Apply damping: calibrated b0 is for one-shot moves,
    # ADRC runs continuously so needs a smaller effective gain
    damping = 3.0
    adrc.b0 = max(0.05, min(5.0, adrc.b0 / damping))
    ADRC_B0 = adrc.b0

    print("\n" + "=" * 50)
    print(f"校准完成！b0 = {adrc.b0:.3f} (已除以 {damping} 衰减)")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    if not check_admin():
        print("WARNING: Not admin!")
    else:
        print("Running as admin")

    mouse_driver = MouseDriver()
    if mouse_driver.is_loaded():
        print("Mouse driver loaded")

    adrc = ADRCController(b0=ADRC_B0, kp=ADRC_KP, alpha=ADRC_ALPHA)
    last_target_id = None

    all_windows = [w for w in gw.getAllTitles() if w.strip()]
    print("Windows:")
    for i, title in enumerate(all_windows):
        print(f"{i}: {title}")

    while True:
        try:
            choice = int(input("Window (-1 fullscreen): "))
            if -1 <= choice < len(all_windows):
                break
        except:
            pass

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../../../.."))
    models_dir = os.path.join(project_root, "app", "models")

    all_models = []
    for pt_file in glob.glob(os.path.join(models_dir, "*.pt")):
        all_models.append(
            {"name": os.path.basename(pt_file), "path": pt_file, "type": "pt"}
        )
    for engine_file in glob.glob(os.path.join(models_dir, "*.engine")):
        all_models.append(
            {
                "name": os.path.basename(engine_file),
                "path": engine_file,
                "type": "engine",
            }
        )

    if not all_models:
        raise FileNotFoundError(f"No models found in {models_dir}")
    all_models.sort(key=lambda m: m["name"])

    print("\nModels:")
    for i, m in enumerate(all_models):
        tag = "[TRT]" if m["type"] == "engine" else "[PT]"
        print(f"  {i}: {tag} {m['name']}")

    while True:
        try:
            model_choice = int(input("Select model: "))
            if 0 <= model_choice < len(all_models):
                break
        except:
            pass

    selected = all_models[model_choice]
    print(f"Loading: {selected['name']}")

    if selected["type"] == "engine":
        model = YOLO(selected["path"])
        using_tensorrt = True
    else:
        model = YOLO(selected["path"])
        device = torch.device("cuda")
        model.to(device)
        model.fuse()
        if device.type == "cuda":
            model.half()
        using_tensorrt = False

    if choice != -1:
        target_window = gw.getWindowsWithTitle(all_windows[choice])[0]
        rect = get_client_rect_screen(target_window._hWnd)
        if rect:
            win_x, win_y, win_w, win_h = rect
        else:
            win_x, win_y = target_window.left, target_window.top
            win_w, win_h = target_window.width, target_window.height
    else:
        win_w, win_h = pyautogui.size()
        win_x, win_y = 0, 0

    frame_queue = Queue(maxsize=2)
    overlay_queue = Queue(maxsize=2)
    running_event = Event()
    running_event.set()

    capture_proc = Process(
        target=capture_process, args=(frame_queue, running_event, choice, all_windows)
    )
    capture_proc.start()

    overlay_proc = None
    if SHOW_OVERLAY:
        overlay_proc = Process(
            target=overlay_process,
            args=(overlay_queue, running_event, win_x, win_y, win_w, win_h),
        )
        overlay_proc.start()

    print("=" * 50)
    print("Demo12.1 - ADRC (Active Disturbance Rejection Control)")
    print(f"b0={ADRC_B0}, kp={ADRC_KP}, alpha={ADRC_ALPHA}")
    print("-" * 50)
    print("F6       = 自动校准 b0（对准静止目标后按）")
    print("Caps Lock = 开启瞄准")
    print("Ctrl+Q   = 退出")
    print("=" * 50)

    calibrating = [False]

    def start_calibrate():
        calibrating[0] = True

    keyboard.add_hotkey("f6", start_calibrate)
    keyboard.add_hotkey("ctrl+q", lambda: running_event.clear())

    last_click_time = 0

    # Sub-pixel accumulator (prevents rounding from losing small moves)
    move_acc_x = 0.0
    move_acc_y = 0.0

    # Track actually applied control for correct ESO feedback
    last_applied_x = 0.0
    last_applied_y = 0.0

    # === Main loop ===
    while running_event.is_set():
        if calibrating[0]:
            calibrating[0] = False
            calibrate(
                model, using_tensorrt, frame_queue, mouse_driver, adrc, overlay_queue
            )
            adrc.reset()
            last_applied_x = 0.0
            last_applied_y = 0.0
            move_acc_x = 0.0
            move_acc_y = 0.0
            continue

        try:
            frame = frame_queue.get(timeout=0.05)
        except:
            continue

        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2

        half_w, half_h = FOV_WIDTH // 2, FOV_HEIGHT // 2
        x1_roi = max(0, center_x - half_w)
        y1_roi = max(0, center_y - half_h)
        x2_roi = min(w, center_x + half_w)
        y2_roi = min(h, center_y + half_h)

        crop = frame[y1_roi:y2_roi, x1_roi:x2_roi]

        if using_tensorrt:
            results = model(crop, conf=CONF_THRESHOLD, verbose=False)
        else:
            results = model(crop, conf=CONF_THRESHOLD, imgsz=IMGSZ, verbose=False)

        all_boxes = []
        if isinstance(results, list) and len(results) > 0:
            for r in results:
                all_boxes.extend(r.boxes)

        if AIM_KEY is None:
            aim_active = True
        elif AIM_KEY == "caps_lock":
            aim_active = is_caps_lock_on()
        else:
            aim_active = keyboard.is_pressed(AIM_KEY)

        head_x, head_y = None, None
        current_conf, current_dist = 0, 0
        click_radius = CLICK_RADIUS_MIN
        z2_x, z2_y = adrc.get_disturbance()

        if AIM_ENABLED and all_boxes and aim_active:
            target, _ = find_nearest_head(all_boxes, center_x, center_y, x1_roi, y1_roi)

            if target:
                head_x, head_y, head_r, head_cls, head_conf, head_bbox = target
                current_conf = head_conf

                click_radius = int(head_r * CLICK_RADIUS_RATIO)
                click_radius = max(
                    CLICK_RADIUS_MIN, min(CLICK_RADIUS_MAX, click_radius)
                )

                tid = head_cls
                if last_target_id is not None and tid != last_target_id:
                    adrc.reset()
                    last_applied_x = 0.0
                    last_applied_y = 0.0
                last_target_id = tid

                error_x = head_x - center_x
                error_y = head_y - center_y
                current_dist = math.sqrt(error_x**2 + error_y**2)

                # Auto fire
                current_time = time.time()
                if (
                    AUTO_CLICK
                    and current_dist <= click_radius
                    and mouse_driver.is_loaded()
                ):
                    if current_time - last_click_time >= CLICK_INTERVAL:
                        mouse_driver.left_down()
                        time.sleep(0.005)
                        mouse_driver.left_up()
                        last_click_time = current_time

                # ADRC control: pass actually applied control for correct ESO
                u_x, u_y = adrc.compute(
                    error_x,
                    error_y,
                    u_applied_x=last_applied_x,
                    u_applied_y=last_applied_y,
                )
                z2_x, z2_y = adrc.get_disturbance()

                if current_dist > DEADZONE and mouse_driver.is_loaded():
                    move_acc_x += u_x
                    move_acc_y += u_y
                    int_move_x = int(move_acc_x)
                    int_move_y = int(move_acc_y)
                    if int_move_x != 0 or int_move_y != 0:
                        mouse_driver.move(int_move_x, int_move_y)
                        move_acc_x -= int_move_x
                        move_acc_y -= int_move_y
                    last_applied_x = float(int_move_x)
                    last_applied_y = float(int_move_y)
                else:
                    # Dead zone: no movement applied
                    last_applied_x = 0.0
                    last_applied_y = 0.0
        else:
            # No target: reset controller
            move_acc_x = 0.0
            move_acc_y = 0.0
            last_applied_x = 0.0
            last_applied_y = 0.0
            if last_target_id is not None:
                adrc.reset()
                last_target_id = None

        if SHOW_OVERLAY:
            try:
                while not overlay_queue.empty():
                    overlay_queue.get_nowait()
                overlay_queue.put_nowait(
                    {
                        "roi": (x1_roi, y1_roi, x2_roi, y2_roi),
                        "center": (center_x, center_y),
                        "head": (head_x, head_y),
                        "aim_active": aim_active,
                        "conf": current_conf,
                        "dist": current_dist,
                        "click_radius": click_radius,
                        "b0": adrc.b0,
                        "z2_x": z2_x,
                        "z2_y": z2_y,
                    }
                )
            except:
                pass

    # Cleanup
    running_event.clear()
    capture_proc.join(timeout=1)
    if capture_proc.is_alive():
        capture_proc.terminate()
    if overlay_proc:
        overlay_proc.join(timeout=1)
        if overlay_proc.is_alive():
            overlay_proc.terminate()

    keyboard.unhook_all()
    print("Exit")
