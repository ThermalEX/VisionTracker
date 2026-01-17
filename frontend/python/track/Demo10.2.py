"""
Demo10.2 - PID Controller + Auto Calibration
基于Demo09.2的PID算法，加入自动校准机制
显示和瞄准分离进程，互不影响
按F6自动校准灵敏度
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

# 设置 DPI 感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    ctypes.windll.user32.SetProcessDPIAware()


def get_client_rect_screen(hwnd):
    try:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        pt_min = win32gui.ClientToScreen(hwnd, (0, 0))
        pt_max = win32gui.ClientToScreen(hwnd, (right, bottom))
        return int(pt_min[0]), int(pt_min[1]), int(pt_max[0] - pt_min[0]), int(pt_max[1] - pt_min[1])
    except:
        return None


def check_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False




# --- PID 控制器 ---
class PIDController:
    def __init__(self, kp=0.5, ki=0.0, kd=0.1, max_output=100):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_output = max_output
        self.prev_error_x = 0
        self.prev_error_y = 0
        self.integral_x = 0
        self.integral_y = 0
        self.last_time = time.time()
        self.first_run = True

    def reset(self):
        self.prev_error_x = 0
        self.prev_error_y = 0
        self.integral_x = 0
        self.integral_y = 0
        self.last_time = time.time()
        self.first_run = True

    def compute(self, error_x, error_y):
        current_time = time.time()
        dt = max(0.001, min(current_time - self.last_time, 0.1))

        p_x = self.kp * error_x
        p_y = self.kp * error_y

        self.integral_x = max(-100, min(100, self.integral_x + error_x * dt))
        self.integral_y = max(-100, min(100, self.integral_y + error_y * dt))
        i_x = self.ki * self.integral_x
        i_y = self.ki * self.integral_y

        if self.first_run:
            d_x, d_y = 0, 0
            self.first_run = False
        else:
            d_x = max(-50, min(50, self.kd * (error_x - self.prev_error_x) / dt))
            d_y = max(-50, min(50, self.kd * (error_y - self.prev_error_y) / dt))

        self.prev_error_x = error_x
        self.prev_error_y = error_y
        self.last_time = current_time

        output_x = max(-self.max_output, min(self.max_output, p_x + i_x + d_x))
        output_y = max(-self.max_output, min(self.max_output, p_y + i_y + d_y))
        return output_x, output_y


# --- 配置 ---
FOV_WIDTH = 200
FOV_HEIGHT = 200
CONF_THRESHOLD = 0.3
IMGSZ = 200

AIM_ENABLED = True
AIM_KEY = 'caps_lock'

# 动态开火范围配置
CLICK_RADIUS_RATIO = 1
CLICK_RADIUS_MIN = 5
CLICK_RADIUS_MAX = 50
AUTO_CLICK = True
CLICK_INTERVAL = 0.1
TARGET_PRIORITY = 'nearest'
SHOW_OVERLAY = True

# ==================== PID 参数说明 ====================
# PID输出 = Kp*误差 + Ki*积分 + Kd*微分
#
# PID_KP (比例系数):
#   - 作用：误差越大，移动越多
#   - 调大：响应更快，但容易超调/震荡
#   - 调小：响应更慢，更稳定
#   - 会被校准自动调整
#
# PID_KI (积分系数):
#   - 作用：累积误差，消除静态偏差
#   - 调大：能消除小误差，但容易超调震荡
#   - 建议：设为0，因为我们有冷却机制
#
# PID_KD (微分系数):
#   - 作用：根据误差变化率调整，抑制超调
#   - 调大：更抗抖动，但响应变慢
#   - 调小：响应更快，但可能震荡
#
# DEADZONE (死区):
#   - 作用：误差小于此值时停止移动
#   - 调大：更稳定，但精度降低（最后一段不动）
#   - 调小：精度更高，但可能抖动
#   - 【最后一段慢？试试调小这个值】
#
# ===========================================================

PID_KP = 0.3      # 初始比例系数，校准后会自动更新
PID_KI = 0.0      # 积分系数（设为0）
PID_KD = 0.001     # 微分系数
DEADZONE = 3      # 死区（像素）- 调小可提高精度

# ==================== 冷却参数说明 ====================
# 防止画面延迟导致的多次移动→震荡
#
# MOVE_COOLDOWN (冷却时间):
#   - 作用：移动后等待多久才能再次移动
#   - 调大：更稳定，但响应变慢
#   - 调小：响应更快，但可能震荡
#   - 【最后一段慢？试试调小这个值到0.05】
#
# ERROR_THRESHOLD (误差变化阈值):
#   - 作用：误差变化超过此值认为画面已更新，可以移动
#   - 调大：更稳定，等待更久
#   - 调小：响应更快，画面稍有变化就移动
#   - 【最后一段慢？试试调小这个值到5】
#
# ===========================================================

MOVE_COOLDOWN = 0.06    # 冷却时间（秒）
ERROR_THRESHOLD = 3     # 误差变化阈值（像素）

# 校准配置
CALIBRATE_SAMPLES = 3   # 校准迭代次数


# --- 捕获进程 ---
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
            monitor = {"left": rect[0], "top": rect[1], "width": rect[2], "height": rect[3]}
        else:
            monitor = {"top": target_window.top, "left": target_window.left,
                      "width": target_window.width, "height": target_window.height}

    with mss.mss() as sct:
        while running_event.is_set():
            try:
                if choice != -1:
                    target_window = gw.getWindowsWithTitle(target_window_title)[0]
                    if not target_window:
                        break
                    rect = get_client_rect_screen(target_window._hWnd)
                    if rect:
                        monitor["left"], monitor["top"], monitor["width"], monitor["height"] = rect
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


# --- 显示进程（独立运行）---
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
        style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_MINIMIZE |
                   win32con.WS_MAXIMIZE | win32con.WS_SYSMENU | win32con.WS_BORDER)
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
            ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT |
            win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE)

        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, win_x, win_y, win_w, win_h,
            win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)

        win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_COLORKEY)

    last_topmost = time.time()

    while running_event.is_set():
        try:
            data = overlay_queue.get(timeout=0.05)
        except:
            cv2.waitKey(1)
            continue

        overlay = np.zeros((win_h, win_w, 3), dtype=np.uint8)

        x1_roi, y1_roi, x2_roi, y2_roi = data.get('roi', (0, 0, 0, 0))
        center_x, center_y = data.get('center', (win_w // 2, win_h // 2))
        head_x, head_y = data.get('head', (None, None))
        aim_active = data.get('aim_active', False)
        conf = data.get('conf', 0)
        dist = data.get('dist', 0)
        fps = data.get('fps', 0)
        click_radius = data.get('click_radius', CLICK_RADIUS_MIN)
        kp = data.get('kp', PID_KP)

        cv2.rectangle(overlay, (x1_roi, y1_roi), (x2_roi, y2_roi), (255, 255, 255), 1)
        cv2.line(overlay, (center_x - 5, center_y), (center_x + 5, center_y), (255, 255, 255), 1)
        cv2.line(overlay, (center_x, center_y - 5), (center_x, center_y + 5), (255, 255, 255), 1)

        if head_x is not None:
            cv2.circle(overlay, (head_x, head_y), click_radius, (0, 255, 0), 1)
            cv2.line(overlay, (center_x, center_y), (head_x, head_y), (0, 255, 255), 1)

        aim_color = (0, 255, 0) if aim_active else (0, 0, 255)
        cv2.putText(overlay, f"FPS:{fps:.0f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(overlay, f"AIM:{'ON' if aim_active else 'OFF'}", (100, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, aim_color, 2)
        cv2.putText(overlay, f"FIRE:{'ON' if AUTO_CLICK else 'OFF'}", (200, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(overlay, f"Kp:{kp:.2f}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        if conf > 0:
            cv2.putText(overlay, f"Conf:{conf:.2f} Dist:{dist:.0f}px", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

        cv2.imshow(window_name, overlay)

        if time.time() - last_topmost > 3.0:
            if hwnd:
                try:
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
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
        heads.append({'cx': head_cx, 'cy': head_cy, 'r': head_r, 'dist': dist, 'conf': conf, 'cls': cls})

    if not heads:
        return None
    heads.sort(key=lambda h: h['dist'] if TARGET_PRIORITY == 'nearest' else -h['conf'])
    best = heads[0]
    return (best['cx'], best['cy'], best['r'], best['cls'], best['conf'])


def is_caps_lock_on():
    return win32api.GetKeyState(win32con.VK_CAPITAL) & 1


def detect_target(model, use_trt, frame):
    """检测并返回最近的头部目标（帧坐标）"""
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

    head = find_nearest_head(boxes, cx, cy, x1, y1)
    if head:
        return head[0], head[1]  # cx, cy in frame coords
    return None, None


def calibrate(model, use_trt, frame_queue, mouse, pid_controller, overlay_queue):
    """校准PID的Kp参数"""
    global PID_KP

    print("\n" + "=" * 50)
    print("开始校准 - 请将准心对准一个静止的目标")
    print(f"当前 Kp = {pid_controller.kp:.3f}")
    print("=" * 50)

    time.sleep(0.5)

    for iteration in range(CALIBRATE_SAMPLES):
        print(f"\n--- 迭代 {iteration + 1}/{CALIBRATE_SAMPLES} (当前 Kp={pid_controller.kp:.3f}) ---")

        # 清空队列获取最新帧
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

        # 误差（帧坐标）
        error_x = target_x - cx
        error_y = target_y - cy
        error_dist = math.sqrt(error_x ** 2 + error_y ** 2)

        # 【移动前】显示目标点
        if overlay_queue:
            try:
                while not overlay_queue.empty():
                    overlay_queue.get_nowait()
                overlay_queue.put_nowait({
                    'roi': (cx - FOV_WIDTH//2, cy - FOV_HEIGHT//2,
                            cx + FOV_WIDTH//2, cy + FOV_HEIGHT//2),
                    'center': (cx, cy),
                    'head': (target_x, target_y),
                    'aim_active': True,
                    'conf': 1.0,
                    'dist': error_dist,
                    'fps': 0,
                    'click_radius': 15,
                    'kp': pid_controller.kp
                })
            except:
                pass
        time.sleep(0.1)  # 让overlay有时间显示

        print(f"  目标位置: ({target_x}, {target_y})")
        print(f"  误差: ({error_x:.0f}, {error_y:.0f}), 距离: {error_dist:.1f}px")

        if error_dist < 15:
            print("  误差太小，自动移开准心...")
            mouse.move(50, 0)
            time.sleep(0.3)
            continue

        # 使用当前Kp直接移动（一步到位）
        move_x = int(error_x * pid_controller.kp)
        move_y = int(error_y * pid_controller.kp)
        print(f"  发送移动: ({move_x}, {move_y})")

        mouse.move(move_x, move_y)
        time.sleep(0.2)

        # 清空队列获取移动后的最新帧
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

        new_error_x = new_target_x - cx
        new_error_y = new_target_y - cy
        new_error_dist = math.sqrt(new_error_x ** 2 + new_error_y ** 2)

        print(f"  移动后目标: ({new_target_x}, {new_target_y})")
        print(f"  剩余误差: ({new_error_x:.0f}, {new_error_y:.0f}), 距离: {new_error_dist:.1f}px")

        # 计算实际移动效果（目标在画面中移动了多少）
        actual_move_x = target_x - new_target_x
        actual_move_y = target_y - new_target_y

        print(f"  实际效果: 视角移动了 ({actual_move_x:.0f}, {actual_move_y:.0f})")

        # 调整Kp：想移动error，实际移动了actual_move
        if abs(actual_move_x) > 5:
            adjust = error_x / actual_move_x
            pid_controller.kp = pid_controller.kp * adjust
            print(f"  调整系数: {adjust:.3f}, 新 Kp: {pid_controller.kp:.3f}")
        elif abs(actual_move_y) > 5:
            adjust = error_y / actual_move_y
            pid_controller.kp = pid_controller.kp * adjust
            print(f"  调整系数: {adjust:.3f}, 新 Kp: {pid_controller.kp:.3f}")

        # 限制Kp范围
        pid_controller.kp = max(0.1, min(5.0, pid_controller.kp))

        # 【关键】自动移回：用实际移动的距离移回去，这样下次能定位到同一目标
        if iteration < CALIBRATE_SAMPLES - 1:
            # 移回去的距离 = 实际移动的距离（反方向）
            back_x = -int(actual_move_x)
            back_y = -int(actual_move_y)
            print(f"  移回准心: ({back_x}, {back_y})")
            mouse.move(back_x, back_y)
            time.sleep(0.3)

    # 校准得到的是"一步到位"的Kp，但PID每帧都移动
    # 所以需要除以一个系数，让PID分多次到达目标
    damping = 3.0
    final_kp = pid_controller.kp / damping
    final_kp = max(0.1, min(2.0, final_kp))
    pid_controller.kp = final_kp
    PID_KP = final_kp

    print("\n" + "=" * 50)
    print(f"校准完成！最终 Kp: {pid_controller.kp:.3f} (已除以{damping}衰减)")
    print("=" * 50 + "\n")


if __name__ == '__main__':
    if not check_admin():
        print("WARNING: Not admin!")
    else:
        print("Running as admin")

    mouse_driver = MouseDriver()
    if mouse_driver.is_loaded():
        print("Mouse driver loaded")

    pid = PIDController(kp=PID_KP, ki=PID_KI, kd=PID_KD)
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

    # 扫描可用模型
    script_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(script_dir, "..", "models")

    all_models = []
    for pt_file in glob.glob(os.path.join(models_dir, "*.pt")):
        name = os.path.basename(pt_file)
        all_models.append({'name': name, 'path': pt_file, 'type': 'pt'})

    for engine_file in glob.glob(os.path.join(models_dir, "*.engine")):
        name = os.path.basename(engine_file)
        all_models.append({'name': name, 'path': engine_file, 'type': 'engine'})

    if not all_models:
        raise FileNotFoundError(f"No models found in {models_dir}")

    all_models.sort(key=lambda m: m['name'])

    print("\nModels:")
    for i, m in enumerate(all_models):
        tag = "[TRT]" if m['type'] == 'engine' else "[PT]"
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

    if selected['type'] == 'engine':
        model = YOLO(selected['path'])
        using_tensorrt = True
    else:
        model = YOLO(selected['path'])
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model.to(device)
        model.fuse()
        if device.type == 'cuda':
            model.half()
        using_tensorrt = False

    # 获取窗口位置
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

    # 启动进程
    frame_queue = Queue(maxsize=2)
    overlay_queue = Queue(maxsize=2)
    running_event = Event()
    running_event.set()

    capture_proc = Process(target=capture_process, args=(frame_queue, running_event, choice, all_windows))
    capture_proc.start()

    overlay_proc = None
    if SHOW_OVERLAY:
        overlay_proc = Process(target=overlay_process, args=(overlay_queue, running_event, win_x, win_y, win_w, win_h))
        overlay_proc.start()

    print("=" * 40)
    print("Demo10.2 - PID + Auto Calibration")
    print(f"PID: Kp={PID_KP}, Ki={PID_KI}, Kd={PID_KD}")
    print("-" * 40)
    print("F6 = 自动校准（对准静止目标后按）")
    print("Ctrl+Q = 退出")
    print("=" * 40)

    # 热键
    calibrating = [False]

    def start_calibrate():
        calibrating[0] = True

    keyboard.add_hotkey('f6', start_calibrate)
    keyboard.add_hotkey('ctrl+q', lambda: running_event.clear())

    fps_start = time.time()
    fps_count = 0
    current_fps = 0.0
    last_click_time = 0

    # 移动冷却变量
    last_move_time = 0
    pre_move_error_x = 0
    pre_move_error_y = 0
    waiting_for_update = False

    # === 主循环 ===
    while running_event.is_set():
        # 检查校准
        if calibrating[0]:
            calibrating[0] = False
            calibrate(model, using_tensorrt, frame_queue, mouse_driver, pid, overlay_queue)
            pid.reset()
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

        fps_count += 1
        if fps_count >= 30:
            current_fps = fps_count / (time.time() - fps_start)
            fps_start = time.time()
            fps_count = 0

        all_boxes = []
        if isinstance(results, list) and len(results) > 0:
            for r in results:
                all_boxes.extend(r.boxes)

        # 瞄准键
        if AIM_KEY is None:
            aim_active = True
        elif AIM_KEY == 'caps_lock':
            aim_active = is_caps_lock_on()
        else:
            aim_active = keyboard.is_pressed(AIM_KEY)

        head_x, head_y = None, None
        current_conf, current_dist = 0, 0
        click_radius = CLICK_RADIUS_MIN

        if AIM_ENABLED and all_boxes and aim_active:
            target = find_nearest_head(all_boxes, center_x, center_y, x1_roi, y1_roi)

            if target:
                head_x, head_y, head_r, head_cls, head_conf = target
                current_conf = head_conf

                click_radius = int(head_r * CLICK_RADIUS_RATIO)
                click_radius = max(CLICK_RADIUS_MIN, min(CLICK_RADIUS_MAX, click_radius))

                # 目标切换检测
                tid = (head_x // 10, head_y // 10, head_cls)
                if last_target_id and tid != last_target_id:
                    pid.reset()
                last_target_id = tid

                # 计算误差（帧坐标）
                error_x = head_x - center_x
                error_y = head_y - center_y
                current_dist = math.sqrt(error_x ** 2 + error_y ** 2)

                # 自动开火
                current_time = time.time()
                if AUTO_CLICK and current_dist <= click_radius and mouse_driver.is_loaded():
                    if current_time - last_click_time >= CLICK_INTERVAL:
                        mouse_driver.left_down()
                        time.sleep(0.005)
                        mouse_driver.left_up()
                        last_click_time = current_time

                # PID 移动（带冷却机制防止震荡）
                if abs(error_x) >= DEADZONE or abs(error_y) >= DEADZONE:
                    now = time.time()
                    time_since_move = now - last_move_time

                    # 判断是否可以移动
                    can_move = False
                    if not waiting_for_update:
                        # 没在等待，可以移动
                        can_move = True
                    else:
                        # 检查误差是否变化（画面更新了）
                        error_change = math.sqrt((error_x - pre_move_error_x) ** 2 +
                                                (error_y - pre_move_error_y) ** 2)
                        if error_change > ERROR_THRESHOLD:
                            # 画面更新了
                            can_move = True
                            waiting_for_update = False
                        elif time_since_move >= MOVE_COOLDOWN:
                            # 超时
                            can_move = True
                            waiting_for_update = False

                    if can_move and mouse_driver.is_loaded():
                        out_x, out_y = pid.compute(error_x, error_y)
                        mouse_driver.move(int(out_x), int(out_y))
                        last_move_time = now
                        pre_move_error_x = error_x
                        pre_move_error_y = error_y
                        waiting_for_update = True
                else:
                    # 进入死区，重置等待状态
                    waiting_for_update = False
        else:
            if last_target_id:
                pid.reset()
                last_target_id = None

        # 发送数据给显示进程
        if SHOW_OVERLAY:
            try:
                while not overlay_queue.empty():
                    overlay_queue.get_nowait()
                overlay_queue.put_nowait({
                    'roi': (x1_roi, y1_roi, x2_roi, y2_roi),
                    'center': (center_x, center_y),
                    'head': (head_x, head_y),
                    'aim_active': aim_active,
                    'conf': current_conf,
                    'dist': current_dist,
                    'fps': current_fps,
                    'click_radius': click_radius,
                    'kp': pid.kp
                })
            except:
                pass

    # 清理
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
