"""
Demo09.4 - MouseControl.dll + 自适应非线性控制
根据误差距离动态调整响应强度，解决慢目标震荡、快目标跟不上的问题
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

# 自适应控制参数
# 非线性响应：output = base_speed * (error ^ curve_power)
# curve_power < 1: 小误差响应强（精细），大误差响应弱（平滑）
# curve_power > 1: 小误差响应弱（防抖），大误差响应强（快追）
CURVE_POWER = 1.0       # 响应曲线指数：1.0=线性，更直接的响应
BASE_SPEED = 0.5        # 基础速度系数（作为比例因子）
MAX_SPEED = 0.8         # 最大速度系数（远距离）
MIN_SPEED = 0.3         # 最小速度系数（近距离，防抖动）
SPEED_SCALE_DIST = 100  # 速度缩放参考距离（像素）

# 距离阈值
CLOSE_RANGE = 10        # 近距离阈值：低于此值用精细控制
FAR_RANGE = 50          # 远距离阈值：高于此值用快速追踪

DEADZONE = 2


# --- 自适应控制器 ---
def adaptive_move(error_x, error_y):
    """
    自适应非线性控制：
    - 近距离：响应弱，防止震荡
    - 远距离：响应强，快速追踪
    """
    dist = math.sqrt(error_x ** 2 + error_y ** 2)

    if dist < DEADZONE:
        return 0, 0

    # 归一化方向
    dir_x = error_x / dist
    dir_y = error_y / dist

    # 非线性响应曲线
    # 使用幂函数：小误差时输出小，大误差时输出大
    response = dist ** CURVE_POWER

    # 自适应速度系数
    if dist < CLOSE_RANGE:
        # 近距离：降低速度，精细控制
        speed = MIN_SPEED + (BASE_SPEED - MIN_SPEED) * (dist / CLOSE_RANGE)
    elif dist > FAR_RANGE:
        # 远距离：提高速度，快速追踪
        speed = BASE_SPEED + (MAX_SPEED - BASE_SPEED) * min(1.0, (dist - FAR_RANGE) / SPEED_SCALE_DIST)
    else:
        # 中距离：正常速度
        speed = BASE_SPEED

    # 计算输出
    output = response * speed

    # 限制最大移动量
    max_move = min(dist, 150)  # 不超过实际距离，也不超过150
    output = min(output, max_move)

    move_x = dir_x * output
    move_y = dir_y * output

    return move_x, move_y


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


# --- 显示进程 ---
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
        current_speed = data.get('speed', 0)

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
        cv2.putText(overlay, f"Curve:{CURVE_POWER} Speed:{current_speed:.2f}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
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


if __name__ == '__main__':
    if not check_admin():
        print("WARNING: Not admin!")
    else:
        print("Running as admin")

    mouse_driver = load_mouse_driver()
    if mouse_driver:
        print("Mouse driver loaded")

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
    models_dir = os.path.join(script_dir,
                              "../..", "models")

    import glob
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

    # 验证窗口尺寸
    if win_w <= 0 or win_h <= 0:
        print("Warning: Invalid window size, using screen size")
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
    print("Demo09.4 - Adaptive Non-linear Control")
    print(f"Curve: {CURVE_POWER}, BaseSpeed: {BASE_SPEED}")
    print(f"Close: <{CLOSE_RANGE}px (slow), Far: >{FAR_RANGE}px (fast)")
    print("ctrl+q to exit")
    print("=" * 40)

    def on_exit():
        running_event.clear()
    keyboard.add_hotkey('ctrl+q', on_exit)

    fps_start = time.time()
    fps_count = 0
    current_fps = 0.0
    last_click_time = 0
    current_speed = 0

    # === 主循环 ===
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

                # 屏幕坐标
                target_sx = win_x + head_x
                target_sy = win_y + head_y
                mouse_x, mouse_y = win32api.GetCursorPos()

                error_x = target_sx - mouse_x
                error_y = target_sy - mouse_y
                current_dist = math.sqrt(error_x ** 2 + error_y ** 2)

                # 计算当前速度系数（用于显示）
                if current_dist < CLOSE_RANGE:
                    current_speed = MIN_SPEED + (BASE_SPEED - MIN_SPEED) * (current_dist / CLOSE_RANGE)
                elif current_dist > FAR_RANGE:
                    current_speed = BASE_SPEED + (MAX_SPEED - BASE_SPEED) * min(1.0, (current_dist - FAR_RANGE) / SPEED_SCALE_DIST)
                else:
                    current_speed = BASE_SPEED

                # 自动开火
                current_time = time.time()
                if AUTO_CLICK and current_dist <= click_radius and mouse_driver:
                    if current_time - last_click_time >= CLICK_INTERVAL:
                        mouse_driver.click_Left_down()
                        time.sleep(0.01)
                        mouse_driver.click_Left_up()
                        last_click_time = current_time

                # 自适应非线性移动
                move_x, move_y = adaptive_move(error_x, error_y)
                if mouse_driver and (abs(move_x) >= 1 or abs(move_y) >= 1):
                    mouse_driver.move_R(int(move_x), int(move_y))

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
                    'speed': current_speed
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
