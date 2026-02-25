"""
Demo09.2 - MouseControl.dll + PID Controller
瞄准和显示分离进程，互不影响
"""
import pygetwindow as gw
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from multiprocessing import Process, Queue, Event, Value
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


def load_mouse_driver():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dll_path = os.path.join(script_dir,
                            "MouseControl.dll")
    if not os.path.exists(dll_path):
        print(f"ERROR: MouseControl.dll not found")
        return None
    try:
        return ctypes.CDLL(dll_path)
    except Exception as e:
        print(f"Failed to load dll: {e}")
        return None


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
CLICK_RADIUS_RATIO = 1   # 开火范围 = 头部半径 * 此比例
CLICK_RADIUS_MIN = 5       # 最小开火范围（远处目标）
CLICK_RADIUS_MAX = 50      # 最大开火范围（近处目标）
AUTO_CLICK = True
CLICK_INTERVAL = 0.2       # 开火间隔（秒）
TARGET_PRIORITY = 'nearest'
SHOW_OVERLAY = True

# PID 控制器参数
PID_KP = 0.8    # 比例系数：值越大瞄准越快，但过大会抖动
PID_KI = 0.3   # 积分系数：消除静差，过大会超调振荡
PID_KD = 0.08   # 微分系数：抑制超调和抖动，过大会迟钝
DEADZONE = 1    # 死区（像素）：误差小于此值时停止移动，防止抖动5

# 目标预测参数
PREDICTION_ENABLED = False   # 是否启用移动预测
PREDICTION_FACTOR = 0.05    # 预测时间（秒）：预测目标多少秒后的位置，0.03-0.1 较合适
VELOCITY_SMOOTHING = 0.7    # 速度平滑系数：0-1，越大越平滑（抗抖动），越小越灵敏


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

                # 清空旧帧
                while not frame_queue.empty():
                    try:
                        frame_queue.get_nowait()
                    except:
                        break
                try:
                    frame_queue.put_nowait(frame)
                except:
                    pass
            except Exception as e:
                time.sleep(0.1)


# --- 显示进程（独立运行）---
def overlay_process(overlay_queue, running_event, win_x, win_y, win_w, win_h):
    """独立的 overlay 显示进程"""
    window_name = "Overlay"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    # 先显示一帧，让窗口创建
    dummy = np.zeros((win_h, win_w, 3), dtype=np.uint8)
    cv2.imshow(window_name, dummy)
    cv2.waitKey(1)

    # 获取窗口句柄并移除边框
    time.sleep(0.05)
    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd:
        # 移除标题栏和边框
        style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
        style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_MINIMIZE |
                   win32con.WS_MAXIMIZE | win32con.WS_SYSMENU | win32con.WS_BORDER)
        win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

        # 设置扩展样式（透明、置顶、穿透点击）
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
            ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT |
            win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE)

        # 设置窗口位置和大小（无边框后精确对齐）
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, win_x, win_y, win_w, win_h,
            win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)

        # 设置颜色键（黑色透明）
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

        # FOV 框
        cv2.rectangle(overlay, (x1_roi, y1_roi), (x2_roi, y2_roi), (255, 255, 255), 1)

        # 中心十字
        cv2.line(overlay, (center_x - 5, center_y), (center_x + 5, center_y), (255, 255, 255), 1)
        cv2.line(overlay, (center_x, center_y - 5), (center_x, center_y + 5), (255, 255, 255), 1)

        # 目标指示（使用动态 click_radius）
        if head_x is not None:
            cv2.circle(overlay, (head_x, head_y), click_radius, (0, 255, 0), 1)
            cv2.line(overlay, (center_x, center_y), (head_x, head_y), (0, 255, 255), 1)

        # 状态文字
        aim_color = (0, 255, 0) if aim_active else (0, 0, 255)
        cv2.putText(overlay, f"FPS:{fps:.0f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(overlay, f"AIM:{'ON' if aim_active else 'OFF'}", (100, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, aim_color, 2)
        cv2.putText(overlay, f"FIRE:{'ON' if AUTO_CLICK else 'OFF'}", (200, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(overlay, f"Kp:{PID_KP} Kd:{PID_KD} R:{click_radius}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        if conf > 0:
            cv2.putText(overlay, f"Conf:{conf:.2f} Dist:{dist:.0f}px", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

        cv2.imshow(window_name, overlay)

        # 保持置顶
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

        # 转换到帧坐标
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


if __name__ == '__main__':
    if not check_admin():
        print("WARNING: Not admin!")
    else:
        print("Running as admin")

    mouse_driver = load_mouse_driver()
    if mouse_driver:
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
    project_root = os.path.abspath(os.path.join(script_dir, "../../../.."))
    models_dir = os.path.join(project_root, "app", "models")

    import glob
    all_models = []

    # 查找所有 .pt 文件
    for pt_file in glob.glob(os.path.join(models_dir, "*.pt")):
        name = os.path.basename(pt_file)
        all_models.append({'name': name, 'path': pt_file, 'type': 'pt'})

    # 查找所有 .engine 文件
    for engine_file in glob.glob(os.path.join(models_dir, "*.engine")):
        name = os.path.basename(engine_file)
        all_models.append({'name': name, 'path': engine_file, 'type': 'engine'})

    if not all_models:
        raise FileNotFoundError(f"No models found in {models_dir}")

    # 按名称排序
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
    print("Demo09.2 - Separate Processes")
    print(f"PID: Kp={PID_KP}, Kd={PID_KD}")
    print("ctrl+q to exit")
    print("=" * 40)

    def on_exit():
        running_event.clear()
    keyboard.add_hotkey('ctrl+q', on_exit)

    fps_start = time.time()
    fps_count = 0
    current_fps = 0.0
    last_click_time = 0  # 上次开火时间

    # 目标预测变量
    prev_head_x, prev_head_y = None, None
    prev_target_time = 0
    smooth_vel_x, smooth_vel_y = 0, 0  # 平滑后的速度

    # === 主循环（纯瞄准，无显示阻塞）===
    while running_event.is_set():
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

        # FPS
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

        # 动态开火范围
        click_radius = CLICK_RADIUS_MIN

        if AIM_ENABLED and all_boxes and aim_active:
            target = find_nearest_head(all_boxes, center_x, center_y, x1_roi, y1_roi)

            if target:
                head_x, head_y, head_r, head_cls, head_conf = target
                current_conf = head_conf

                # 动态计算开火范围（基于头部大小）
                click_radius = int(head_r * CLICK_RADIUS_RATIO)
                click_radius = max(CLICK_RADIUS_MIN, min(CLICK_RADIUS_MAX, click_radius))

                # 目标切换检测
                tid = (head_x // 10, head_y // 10, head_cls)
                if last_target_id and tid != last_target_id:
                    pid.reset()
                    prev_head_x, prev_head_y = None, None  # 重置预测
                    smooth_vel_x, smooth_vel_y = 0, 0  # 重置速度
                last_target_id = tid

                # 目标位置预测（带速度平滑）
                predicted_x, predicted_y = head_x, head_y
                current_time = time.time()
                if PREDICTION_ENABLED and prev_head_x is not None:
                    dt = current_time - prev_target_time
                    if 0.001 < dt < 0.3:  # 合理时间范围（缩小上限，丢帧太久不预测）
                        # 计算瞬时速度
                        vel_x = (head_x - prev_head_x) / dt  # 像素/秒
                        vel_y = (head_y - prev_head_y) / dt
                        # 速度平滑（指数移动平均）
                        smooth_vel_x = VELOCITY_SMOOTHING * smooth_vel_x + (1 - VELOCITY_SMOOTHING) * vel_x
                        smooth_vel_y = VELOCITY_SMOOTHING * smooth_vel_y + (1 - VELOCITY_SMOOTHING) * vel_y
                        # 使用平滑速度预测
                        predicted_x = head_x + smooth_vel_x * PREDICTION_FACTOR
                        predicted_y = head_y + smooth_vel_y * PREDICTION_FACTOR
                elif prev_head_x is None:
                    # 新目标，重置速度
                    smooth_vel_x, smooth_vel_y = 0, 0
                prev_head_x, prev_head_y = head_x, head_y
                prev_target_time = current_time

                # 屏幕坐标（使用预测位置）
                target_sx = win_x + predicted_x
                target_sy = win_y + predicted_y
                mouse_x, mouse_y = win32api.GetCursorPos()

                error_x = target_sx - mouse_x
                error_y = target_sy - mouse_y
                current_dist = math.sqrt(error_x ** 2 + error_y ** 2)

                # 自动开火（使用动态范围 + 间隔控制）
                current_time = time.time()
                if AUTO_CLICK and current_dist <= click_radius and mouse_driver:
                    if current_time - last_click_time >= CLICK_INTERVAL:
                        mouse_driver.click_Left_down()
                        time.sleep(0.01)
                        mouse_driver.click_Left_up()
                        last_click_time = current_time

                # PID 移动
                if abs(error_x) >= DEADZONE or abs(error_y) >= DEADZONE:
                    out_x, out_y = pid.compute(error_x, error_y)
                    if mouse_driver:
                        mouse_driver.move_R(int(out_x), int(out_y))
        else:
            if last_target_id:
                pid.reset()
                last_target_id = None
                prev_head_x, prev_head_y = None, None  # 重置预测
                smooth_vel_x, smooth_vel_y = 0, 0  # 重置速度

        # 发送数据给显示进程（非阻塞）
        if SHOW_OVERLAY:
            try:
                # 清空旧数据
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
                    'click_radius': click_radius  # 动态开火范围
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
    print("exit")
