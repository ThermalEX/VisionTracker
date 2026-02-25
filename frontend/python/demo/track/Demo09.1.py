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

# 设置 DPI 感知，防止坐标偏移
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

# 检测管理员权限
def check_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# --- SendInput 结构体定义 ---
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("mi", MOUSEINPUT)
    ]

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

# --- 配置区域 ---
FOV_WIDTH = 300
FOV_HEIGHT = 200
CONF_THRESHOLD = 0.35
IMGSZ = 300
SHOW_PERF = True

# 鼠标控制配置
AIM_ENABLED = True
AIM_KEY = 'caps_lock'
CLICK_RADIUS = 10
AUTO_CLICK = True
AIM_SPEED = 2.5  # 速度设置: 0.1~0.9 为平滑移动, 1.0 为瞬间锁定
TARGET_PRIORITY = 'nearest'

# ----------------

def send_input(input_struct):
    """调用 Windows SendInput API"""
    ctypes.windll.user32.SendInput(1, ctypes.byref(input_struct), ctypes.sizeof(input_struct))

def move_mouse_rel(offset_x, offset_y):
    """使用 SendInput 相对移动鼠标"""
    if offset_x == 0 and offset_y == 0:
        return

    extra = ctypes.c_ulong(0)
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.mi = MOUSEINPUT(
        dx=int(offset_x),
        dy=int(offset_y),
        mouseData=0,
        dwFlags=MOUSEEVENTF_MOVE,
        time=0,
        dwExtraInfo=ctypes.pointer(extra)
    )
    send_input(inp)

def click_mouse():
    """使用 SendInput 模拟鼠标左键点击"""
    extra = ctypes.c_ulong(0)

    inp_down = INPUT()
    inp_down.type = INPUT_MOUSE
    inp_down.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
    send_input(inp_down)

    time.sleep(0.01)

    inp_up = INPUT()
    inp_up.type = INPUT_MOUSE
    inp_up.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
    send_input(inp_up)

def get_mouse_pos():
    return win32api.GetCursorPos()

def is_caps_lock_on():
    return win32api.GetKeyState(win32con.VK_CAPITAL) & 1


def capture_process(frame_queue, running_event, choice, all_windows):
    target_window_title = None
    target_window = None
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
                "top": rect[1],
                "left": rect[0],
                "width": rect[2],
                "height": rect[3]
            }
        else:
            monitor = {
                "top": target_window.top,
                "left": target_window.left,
                "width": target_window.width,
                "height": target_window.height
            }

    with mss.mss() as sct:
        while running_event.is_set():
            try:
                if choice != -1:
                    target_window = gw.getWindowsWithTitle(target_window_title)[0]
                    if not target_window:
                        running_event.clear()
                        break

                    rect = get_client_rect_screen(target_window._hWnd)
                    if rect:
                        monitor["left"], monitor["top"], monitor["width"], monitor["height"] = rect
                    else:
                        monitor["top"] = target_window.top
                        monitor["left"] = target_window.left
                        monitor["width"] = target_window.width
                        monitor["height"] = target_window.height

                    if monitor["width"] <= 0 or monitor["height"] <= 0:
                        time.sleep(0.1)
                        continue

                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

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
                print(f"capture error: {e}")
                time.sleep(0.5)


def make_window_transparent(window_name):
    hwnd = win32gui.FindWindow(None, window_name)

    if hwnd:
        ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE
        )
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
        )
        win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_COLORKEY)
        return hwnd
    return None


def keep_topmost(hwnd):
    if hwnd:
        try:
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_MINIMIZE | win32con.WS_MAXIMIZE | win32con.WS_SYSMENU)
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW | win32con.SWP_FRAMECHANGED
            )
        except:
            pass


def find_nearest_head(boxes, screen_center_x, screen_center_y, x1_roi, y1_roi):
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

        head_center_x = (real_x1 + real_x2) // 2
        head_center_y = (real_y1 + real_y2) // 2

        head_width = real_x2 - real_x1
        head_height = real_y2 - real_y1
        head_radius = min(head_width, head_height) // 2

        distance = math.sqrt((head_center_x - screen_center_x) ** 2 +
                            (head_center_y - screen_center_y) ** 2)

        heads.append({
            'center_x': head_center_x,
            'center_y': head_center_y,
            'radius': head_radius,
            'distance': distance,
            'conf': conf,
            'cls': cls
        })

    if not heads:
        return None

    if TARGET_PRIORITY == 'nearest':
        heads.sort(key=lambda h: h['distance'])
    else:
        heads.sort(key=lambda h: -h['conf'])

    best = heads[0]
    return (best['center_x'], best['center_y'], best['radius'], best['cls'], best['conf'])


if __name__ == '__main__':
    if not check_admin():
        print("WARNING: Not running as admin!")
        print("-" * 50)
    else:
        print("Running as admin")

    all_windows = [w for w in gw.getAllTitles() if w.strip()]
    print("windows:")
    for i, title in enumerate(all_windows):
        print(f"{i}: {title}")

    while True:
        try:
            choice = int(input("window number (-1 for fullscreen): "))
            if -1 <= choice < len(all_windows):
                break
        except ValueError:
            pass

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, "../../../.."))
    models_dir = os.path.join(project_root, "app", "models")

    model_name = "best 12.23"
    pt_path = os.path.join(models_dir, f"{model_name}.pt")

    import glob
    engine_files = glob.glob(os.path.join(models_dir, f"{model_name}*.engine"))

    if engine_files:
        def get_engine_size(path):
            if '_' in path:
                try:
                    size_str = path.split('_')[-1].replace('.engine', '')
                    return int(size_str)
                except:
                    return 640
            return 640

        engine_files.sort(key=get_engine_size)
        engine_path = engine_files[0]
        engine_size = get_engine_size(engine_path)

        print(f"Using TensorRT: {engine_path} (size: {engine_size}x{engine_size})")
        model = YOLO(engine_path)
        using_tensorrt = True
        model_input_size = engine_size
    elif os.path.exists(pt_path):
        print(f"Using PyTorch: {pt_path}")
        model = YOLO(pt_path)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model.to(device)
        model.fuse()
        if device.type == 'cuda':
            model.half()
        using_tensorrt = False
        model_input_size = IMGSZ
    else:
        raise FileNotFoundError(f"Model not found: {pt_path}")

    window_name = "Overlay"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    if choice != -1:
        target_window = gw.getWindowsWithTitle(all_windows[choice])[0]
        rect = get_client_rect_screen(target_window._hWnd)
        if rect:
            win_x, win_y, win_w, win_h = rect
        else:
            win_w = target_window.width
            win_h = target_window.height
            win_x = target_window.left
            win_y = target_window.top
    else:
        win_w, win_h = pyautogui.size()
        win_x, win_y = 0, 0

    cv2.resizeWindow(window_name, win_w, win_h)
    cv2.moveWindow(window_name, win_x, win_y)

    dummy_black = np.zeros((win_h, win_w, 3), dtype=np.uint8)
    cv2.imshow(window_name, dummy_black)
    cv2.waitKey(1)

    hwnd = make_window_transparent(window_name)

    frame_queue = Queue(maxsize=2)
    running_event = Event()
    running_event.set()

    capture_proc = Process(
        target=capture_process,
        args=(frame_queue, running_event, choice, all_windows)
    )
    capture_proc.start()

    print("started. ctrl+q to exit")
    key_desc = "Always" if AIM_KEY is None else ("Caps Lock ON" if AIM_KEY == 'caps_lock' else f"Hold {AIM_KEY}")
    print(f"Aim: {'ON' if AIM_ENABLED else 'OFF'}, Trigger: {key_desc}")

    def on_exit():
        running_event.clear()

    keyboard.add_hotkey('ctrl+q', on_exit)

    last_topmost = time.time()
    last_check = time.time()

    fps_start_time = time.time()
    fps_frame_count = 0
    current_fps = 0.0

    while running_event.is_set():
        try:
            frame = frame_queue.get(timeout=0.1)
        except:
            cv2.waitKey(1)
            continue

        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2

        half_w = FOV_WIDTH // 2
        half_h = FOV_HEIGHT // 2

        x1_roi = max(0, center_x - half_w)
        y1_roi = max(0, center_y - half_h)
        x2_roi = min(w, center_x + half_w)
        y2_roi = min(h, center_y + half_h)

        crop_frame = frame[y1_roi:y2_roi, x1_roi:x2_roi]

        if using_tensorrt:
            results = model(crop_frame, conf=CONF_THRESHOLD, verbose=False)
        else:
            results = model(crop_frame, conf=CONF_THRESHOLD, imgsz=IMGSZ, verbose=False)

        overlay = np.zeros((h, w, 3), dtype=np.uint8)
        cv2.rectangle(overlay, (x1_roi, y1_roi), (x2_roi, y2_roi), (255, 255, 255), 1)

        fps_frame_count += 1
        if fps_frame_count >= 30:
            current_time = time.time()
            current_fps = fps_frame_count / (current_time - fps_start_time)
            fps_start_time = current_time
            fps_frame_count = 0

        cv2.putText(overlay, f"FPS: {current_fps:.1f} | SendInput", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        all_boxes = []
        if isinstance(results, list) and len(results) > 0:
            for result in results:
                boxes = result.boxes
                all_boxes.extend(boxes)

                for box in boxes:
                    bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                    real_x1, real_y1 = bx1 + x1_roi, by1 + y1_roi
                    real_x2, real_y2 = bx2 + x1_roi, by2 + y1_roi
                    cls = int(box.cls[0])
                    color = (255, 0, 0) if cls in [0, 1] else (0, 0, 255)
                    cv2.rectangle(overlay, (real_x1, real_y1), (real_x2, real_y2), color, 2)

        if AIM_ENABLED and all_boxes:
            if AIM_KEY is None:
                aim_active = True
            elif AIM_KEY == 'caps_lock':
                aim_active = is_caps_lock_on()
            else:
                aim_active = keyboard.is_pressed(AIM_KEY)

            if aim_active:
                head_target = find_nearest_head(all_boxes, center_x, center_y, x1_roi, y1_roi)

                if head_target:
                    head_x, head_y, head_radius, head_cls, head_conf = head_target
                    target_screen_x = win_x + head_x
                    target_screen_y = win_y + head_y
                    mouse_x, mouse_y = get_mouse_pos()

                    offset_x = target_screen_x - mouse_x
                    offset_y = target_screen_y - mouse_y

                    if AIM_SPEED >= 1.0:
                        move_mouse_rel(offset_x, offset_y)
                    else:
                        move_mouse_rel(offset_x * AIM_SPEED, offset_y * AIM_SPEED)

                    dist_to_target = math.sqrt(offset_x ** 2 + offset_y ** 2)
                    if AUTO_CLICK and dist_to_target <= CLICK_RADIUS:
                        click_mouse()

        cv2.imshow(window_name, overlay)

        current = time.time()
        if current - last_topmost > 3.0:
            keep_topmost(hwnd)
            last_topmost = current

        if choice != -1 and current - last_check > 3.0:
            try:
                tw = gw.getWindowsWithTitle(all_windows[choice])[0]
                ow = gw.getWindowsWithTitle(window_name)[0]
                
                rect = get_client_rect_screen(tw._hWnd)
                if rect:
                    tx, ty, tw_w, tw_h = rect
                    if abs(ow.left - tx) > 2 or abs(ow.top - ty) > 2 or abs(ow.width - tw_w) > 2:
                        cv2.moveWindow(window_name, tx, ty)
                        cv2.resizeWindow(window_name, tw_w, tw_h)
                        win_x, win_y = tx, ty
                
                last_check = current
            except:
                pass

        cv2.waitKey(1)

    running_event.clear()
    capture_proc.join(timeout=2)
    if capture_proc.is_alive():
        capture_proc.terminate()

    cv2.destroyAllWindows()
    keyboard.unhook_all()
    print("exit")
