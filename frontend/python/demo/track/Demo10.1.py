"""
Demo09.5 - 瞬移版本 + 自动校准
按 F6 自动校准灵敏度
"""
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
import pygetwindow as gw
import os
import math
import ctypes
import glob

# DPI 感知
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except:
    ctypes.windll.user32.SetProcessDPIAware()

# ========== 配置 ==========
FOV_WIDTH = 200
FOV_HEIGHT = 200
CONF_THRESHOLD = 0.3
IMGSZ = 200

# 瞬移控制（校准后会自动更新）
SENSITIVITY = 1.0       # 灵敏度系数
DEADZONE = 2            # 死区
MOVE_COOLDOWN = 0.15    # 移动后冷却时间（秒）- 等待画面更新
UPDATE_THRESHOLD = 8    # 误差变化阈值：移动后误差变化超过此值认为画面已更新

# 校准配置
CALIBRATE_MOVE = 100    # 校准时移动的原始像素数
CALIBRATE_SAMPLES = 3   # 校准采样次数

# 瞄准开关
AIM_ENABLED = True
AIM_KEY = 'caps_lock'   # None=常开, 'caps_lock'=大写锁定键

# 自动开火
AUTO_CLICK = True
CLICK_RADIUS_RATIO = 1.0    # 开火范围 = 头部半径 * 比例
CLICK_RADIUS_MIN = 5        # 最小开火范围
CLICK_RADIUS_MAX = 50       # 最大开火范围
CLICK_INTERVAL = 0.1

# 目标优先级
TARGET_PRIORITY = 'nearest'

# 显示
SHOW_OVERLAY = True

# 调试
DEBUG_LOG = True        # 是否打印调试日志
LOG_FILE = "debug_log.txt"  # 日志文件名


def get_client_rect(hwnd):
    try:
        rect = win32gui.GetClientRect(hwnd)
        pt = win32gui.ClientToScreen(hwnd, (0, 0))
        return pt[0], pt[1], rect[2], rect[3]
    except:
        return None


def load_mouse_driver():
    dll_path = os.path.join(os.path.dirname(__file__),
                            "MouseControl.dll")
    if not os.path.exists(dll_path):
        print(f"ERROR: {dll_path} not found")
        return None
    try:
        return ctypes.CDLL(dll_path)
    except Exception as e:
        print(f"Failed to load DLL: {e}")
        return None


def is_caps_lock_on():
    return win32api.GetKeyState(win32con.VK_CAPITAL) & 1


def capture_process(frame_queue, running_event, monitor_info):
    with mss.mss() as sct:
        while running_event.is_set():
            try:
                img = sct.grab(monitor_info)
                frame = np.array(img)[:, :, :3]
                while not frame_queue.empty():
                    try:
                        frame_queue.get_nowait()
                    except:
                        break
                frame_queue.put_nowait(frame)
            except:
                time.sleep(0.01)


def find_best_head(boxes, center_x, center_y, roi_x, roi_y):
    heads = []
    for box in boxes:
        cls = int(box.cls[0])
        if cls not in [0, 2]:
            continue
        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        hx = (bx1 + bx2) // 2 + roi_x
        hy = (by1 + by2) // 2 + roi_y
        # 头部半径 = 检测框较小边的一半
        head_r = min(bx2 - bx1, by2 - by1) // 2
        dist = math.sqrt((hx - center_x) ** 2 + (hy - center_y) ** 2)
        heads.append({'x': hx, 'y': hy, 'r': head_r, 'dist': dist, 'conf': conf})

    if not heads:
        return None
    if TARGET_PRIORITY == 'nearest':
        heads.sort(key=lambda h: h['dist'])
    else:
        heads.sort(key=lambda h: -h['conf'])
    return heads[0]


def detect_target(model, frame, use_trt, win_x, win_y):
    """检测并返回最近的头部目标屏幕坐标"""
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

    head = find_best_head(boxes, cx, cy, x1, y1)
    if head:
        return win_x + head['x'], win_y + head['y']
    return None, None


def calibrate(model, use_trt, frame_queue, mouse, win_x, win_y):
    """
    迭代校准灵敏度
    每次校准后立即验证，逐步收敛到正确值
    """
    global SENSITIVITY

    print("\n" + "=" * 50)
    print("开始迭代校准 - 请将准心对准一个静止的目标（bot）")
    print("确保目标在 FOV 范围内且不会移动")
    print("=" * 50)

    time.sleep(0.5)

    # 目标：让鼠标移动后，准心正好到达目标位置
    # 方法：测量误差，移动，测量剩余误差，调整系数

    for iteration in range(CALIBRATE_SAMPLES):
        print(f"\n--- 迭代 {iteration + 1}/{CALIBRATE_SAMPLES} (当前 SENS={SENSITIVITY:.3f}) ---")

        # 1. 检测目标，计算误差
        try:
            frame = frame_queue.get(timeout=1)
        except:
            print("  获取帧失败")
            continue

        target_x, target_y = detect_target(model, frame, use_trt, win_x, win_y)
        if target_x is None:
            print("  未检测到目标")
            continue

        # 当前鼠标位置（屏幕中心应该就是准心位置）
        h, w = frame.shape[:2]
        screen_cx = win_x + w // 2
        screen_cy = win_y + h // 2

        # 误差 = 目标位置 - 准心位置
        error_x = target_x - screen_cx
        error_y = target_y - screen_cy
        error_dist = math.sqrt(error_x ** 2 + error_y ** 2)

        print(f"  目标: ({target_x}, {target_y}), 准心: ({screen_cx}, {screen_cy})")
        print(f"  误差: ({error_x}, {error_y}), 距离: {error_dist:.1f}px")

        if error_dist < 10:
            print("  误差太小，无法校准。请手动移开准心再试")
            continue

        # 2. 用当前 SENSITIVITY 移动
        move_x = int(error_x * SENSITIVITY)
        move_y = int(error_y * SENSITIVITY)
        print(f"  发送移动: ({move_x}, {move_y})")

        mouse.move_R(move_x, move_y)
        time.sleep(0.15)

        # 3. 再次检测，测量剩余误差
        try:
            frame = frame_queue.get(timeout=1)
        except:
            print("  获取帧失败")
            continue

        new_target_x, new_target_y = detect_target(model, frame, use_trt, win_x, win_y)
        if new_target_x is None:
            print("  移动后未检测到目标")
            continue

        # 新的准心位置（可能窗口没变，但视角变了）
        new_error_x = new_target_x - screen_cx
        new_error_y = new_target_y - screen_cy
        new_error_dist = math.sqrt(new_error_x ** 2 + new_error_y ** 2)

        print(f"  移动后目标: ({new_target_x}, {new_target_y})")
        print(f"  剩余误差: ({new_error_x}, {new_error_y}), 距离: {new_error_dist:.1f}px")

        # 4. 计算实际移动效果
        # 目标从 (target_x, target_y) 移动到 (new_target_x, new_target_y)
        # 视角移动 = 目标位移的反方向
        actual_move_x = target_x - new_target_x  # 目标左移 = 视角右移
        actual_move_y = target_y - new_target_y

        print(f"  实际效果: 视角移动了 ({actual_move_x}, {actual_move_y})")

        # 5. 调整 SENSITIVITY
        # 我们想移动 error，实际移动了 actual_move
        # 新的 SENSITIVITY = 旧的 * (想要的 / 实际的)
        if abs(actual_move_x) > 5:
            adjust_x = error_x / actual_move_x
            SENSITIVITY = SENSITIVITY * adjust_x
            print(f"  调整系数: {adjust_x:.3f}, 新 SENS: {SENSITIVITY:.3f}")
        elif abs(actual_move_y) > 5:
            adjust_y = error_y / actual_move_y
            SENSITIVITY = SENSITIVITY * adjust_y
            print(f"  调整系数: {adjust_y:.3f}, 新 SENS: {SENSITIVITY:.3f}")
        else:
            print("  移动量太小，无法调整")

        # 限制范围，防止发散
        SENSITIVITY = max(0.1, min(10.0, SENSITIVITY))

        # 如果剩余误差很小，说明已经校准好了
        if new_error_dist < 15:
            print(f"\n校准成功！剩余误差 {new_error_dist:.1f}px < 15px")
            break

    print("\n" + "=" * 50)
    print(f"校准完成！最终灵敏度: {SENSITIVITY:.3f}")
    print("=" * 50 + "\n")


# ========== 主程序 ==========
if __name__ == '__main__':
    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    print(f"Admin: {is_admin}")

    mouse = load_mouse_driver()
    if mouse:
        print("Mouse driver loaded")
    else:
        print("WARNING: Mouse driver not loaded")
        AIM_ENABLED = False

    # 选择窗口
    windows = [w for w in gw.getAllTitles() if w.strip()]
    print("\nWindows:")
    for i, title in enumerate(windows):
        print(f"  {i}: {title}")
    print("  -1: Fullscreen")

    choice = -1
    while True:
        try:
            choice = int(input("Select: "))
            if -1 <= choice < len(windows):
                break
        except:
            pass

    if choice == -1:
        screen = pyautogui.size()
        monitor = {"left": 0, "top": 0, "width": screen[0], "height": screen[1]}
        win_x, win_y = 0, 0
    else:
        win = gw.getWindowsWithTitle(windows[choice])[0]
        rect = get_client_rect(win._hWnd)
        if rect:
            win_x, win_y, w, h = rect
            monitor = {"left": win_x, "top": win_y, "width": w, "height": h}
        else:
            win_x, win_y = win.left, win.top
            monitor = {"left": win_x, "top": win_y, "width": win.width, "height": win.height}

    # 选择模型
    models_dir = os.path.join(
        os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../..")),
        "app", "models")
    model_files = glob.glob(os.path.join(models_dir, "*.engine")) + \
                  glob.glob(os.path.join(models_dir, "*.pt"))

    if not model_files:
        raise FileNotFoundError(f"No models in {models_dir}")

    model_files.sort()
    print("\nModels:")
    for i, f in enumerate(model_files):
        tag = "[TRT]" if f.endswith('.engine') else "[PT]"
        print(f"  {i}: {tag} {os.path.basename(f)}")

    model_idx = 0
    while True:
        try:
            model_idx = int(input("Select model: "))
            if 0 <= model_idx < len(model_files):
                break
        except:
            pass

    model_path = model_files[model_idx]
    print(f"Loading: {os.path.basename(model_path)}")

    model = YOLO(model_path)
    use_trt = model_path.endswith('.engine')

    if not use_trt:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model.to(device)
        model.fuse()
        if device == 'cuda':
            model.half()

    # 启动捕获进程
    frame_queue = Queue(maxsize=2)
    running = Event()
    running.set()

    cap_proc = Process(target=capture_process, args=(frame_queue, running, monitor))
    cap_proc.start()

    # Overlay
    overlay_hwnd = None
    if SHOW_OVERLAY:
        cv2.namedWindow("Overlay", cv2.WINDOW_NORMAL)

        # 先显示一帧黑色图像
        dummy = np.zeros((monitor["height"], monitor["width"], 3), dtype=np.uint8)
        cv2.imshow("Overlay", dummy)
        cv2.waitKey(1)

        time.sleep(0.05)
        overlay_hwnd = win32gui.FindWindow(None, "Overlay")
        if overlay_hwnd:
            # 移除所有边框和标题栏
            style = win32gui.GetWindowLong(overlay_hwnd, win32con.GWL_STYLE)
            style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_MINIMIZE |
                       win32con.WS_MAXIMIZE | win32con.WS_SYSMENU | win32con.WS_BORDER)
            win32gui.SetWindowLong(overlay_hwnd, win32con.GWL_STYLE, style)

            # 设置扩展样式：透明、穿透、置顶
            ex_style = win32gui.GetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE,
                ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT |
                win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE)

            # 设置位置和大小
            win32gui.SetWindowPos(overlay_hwnd, win32con.HWND_TOPMOST,
                                  monitor["left"], monitor["top"],
                                  monitor["width"], monitor["height"],
                                  win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)

            # 黑色透明
            win32gui.SetLayeredWindowAttributes(overlay_hwnd, 0, 255, win32con.LWA_COLORKEY)

    # 打开日志文件
    log_file = None
    if DEBUG_LOG:
        log_path = os.path.join(os.path.dirname(__file__), LOG_FILE)
        log_file = open(log_path, 'w', encoding='utf-8')
        log_file.write(f"=== Demo09.5 调试日志 ===\n")
        log_file.write(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"SENSITIVITY: {SENSITIVITY}\n")
        log_file.write(f"MOVE_COOLDOWN: {MOVE_COOLDOWN}\n")
        log_file.write(f"DEADZONE: {DEADZONE}\n")
        log_file.write(f"=" * 50 + "\n\n")
        print(f"日志文件: {log_path}")

    print("\n" + "=" * 40)
    print("Demo09.5 - Snap Aim + Auto Calibrate")
    print(f"Sensitivity: {SENSITIVITY:.3f}")
    print(f"AIM_KEY: {AIM_KEY}")
    print("-" * 40)
    print("F6 = 自动校准（对准静止目标后按）")
    print("Ctrl+Q = 退出")
    print("=" * 40)

    # 热键
    calibrating = [False]  # 用列表来在闭包中修改

    def start_calibrate():
        calibrating[0] = True

    keyboard.add_hotkey('f6', start_calibrate)
    keyboard.add_hotkey('ctrl+q', lambda: running.clear())

    fps_time = time.time()
    fps_count = 0
    current_fps = 0
    last_click = 0
    last_move_time = 0      # 上次移动时间
    pre_move_error_x = 0    # 移动前的误差（用于判断画面是否更新）
    pre_move_error_y = 0
    waiting_for_update = False  # 是否在等待画面更新
    last_topmost = time.time()  # 上次刷新topmost的时间

    # ========== 主循环 ==========
    while running.is_set():
        # 检查是否需要校准
        if calibrating[0]:
            calibrating[0] = False
            calibrate(model, use_trt, frame_queue, mouse, win_x, win_y)
            continue

        try:
            frame = frame_queue.get(timeout=0.05)
        except:
            continue

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

        fps_count += 1
        if fps_count >= 30:
            current_fps = fps_count / (time.time() - fps_time)
            fps_time = time.time()
            fps_count = 0

        boxes = []
        for r in results:
            boxes.extend(r.boxes)

        if AIM_KEY is None:
            aim_on = True
        elif AIM_KEY == 'caps_lock':
            aim_on = is_caps_lock_on()
        else:
            aim_on = keyboard.is_pressed(AIM_KEY)

        target_x, target_y = None, None
        current_dist = 0
        click_radius = CLICK_RADIUS_MIN  # 默认值

        if AIM_ENABLED and boxes and aim_on and mouse:
            head = find_best_head(boxes, cx, cy, x1, y1)

            if head:
                target_x, target_y = head['x'], head['y']

                # 根据头部大小计算开火范围
                head_r = head.get('r', 10)
                click_radius = int(head_r * CLICK_RADIUS_RATIO)
                click_radius = max(CLICK_RADIUS_MIN, min(CLICK_RADIUS_MAX, click_radius))

                # 误差 = 目标位置 - 准心位置（准心在帧中心）
                # 这和校准时的计算方式一致
                error_x = target_x - cx
                error_y = target_y - cy
                current_dist = math.sqrt(error_x ** 2 + error_y ** 2)

                # 瞬移逻辑：移动后等待画面更新再移动
                now = time.time()
                time_since_move = now - last_move_time

                # 判断是否可以移动
                can_move = False
                move_reason = ""

                if current_dist <= DEADZONE:
                    # 在死区内，不移动
                    move_reason = "SKIP(deadzone)"
                    waiting_for_update = False
                elif not waiting_for_update:
                    # 没在等待，可以移动
                    can_move = True
                    move_reason = "MOVE(ready)"
                else:
                    # 在等待画面更新
                    # 检查误差是否有变化（画面更新了）
                    error_change = math.sqrt((error_x - pre_move_error_x) ** 2 +
                                            (error_y - pre_move_error_y) ** 2)

                    if error_change > UPDATE_THRESHOLD:
                        # 误差变化了，说明画面更新了
                        can_move = True
                        waiting_for_update = False
                        move_reason = f"MOVE(updated, chg={error_change:.0f})"
                    elif time_since_move >= MOVE_COOLDOWN:
                        # 超时，强制允许移动
                        can_move = True
                        waiting_for_update = False
                        move_reason = "MOVE(timeout)"
                    else:
                        move_reason = f"SKIP(waiting, chg={error_change:.0f})"

                if DEBUG_LOG and log_file:
                    log_line = (f"[{now:.3f}] 误差:({error_x:.0f},{error_y:.0f}) "
                                f"距离:{current_dist:.0f} -> {move_reason}\n")
                    log_file.write(log_line)
                    log_file.flush()

                if can_move:
                    move_x = int(error_x * SENSITIVITY)
                    move_y = int(error_y * SENSITIVITY)
                    mouse.move_R(move_x, move_y)
                    last_move_time = now
                    pre_move_error_x = error_x
                    pre_move_error_y = error_y
                    waiting_for_update = True  # 开始等待画面更新

                # 自动开火
                if AUTO_CLICK and current_dist <= click_radius:
                    now = time.time()
                    if now - last_click >= CLICK_INTERVAL:
                        mouse.click_Left_down()
                        time.sleep(0.005)
                        mouse.click_Left_up()
                        last_click = now

        # Overlay
        if SHOW_OVERLAY:
            overlay = np.zeros((h, w, 3), dtype=np.uint8)

            # 绘制ROI矩形框
            cv2.rectangle(overlay, (x1, y1), (x2, y2), (255, 255, 255), 1)
            # 绘制准心（5像素长度，和Demo09.4一致）
            cv2.line(overlay, (cx - 5, cy), (cx + 5, cy), (255, 255, 255), 1)
            cv2.line(overlay, (cx, cy - 5), (cx, cy + 5), (255, 255, 255), 1)

            if target_x is not None:
                # 绘制目标圆（thickness=1，和Demo09.4一致）
                cv2.circle(overlay, (target_x, target_y), click_radius, (0, 255, 0), 1)
                # 绘制连接线
                cv2.line(overlay, (cx, cy), (target_x, target_y), (0, 255, 255), 1)

            aim_color = (0, 255, 0) if aim_on else (0, 0, 255)
            cv2.putText(overlay, f"FPS:{current_fps:.0f}", (10, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(overlay, f"AIM:{'ON' if aim_on else 'OFF'}", (100, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, aim_color, 2)
            cv2.putText(overlay, f"FIRE:{'ON' if AUTO_CLICK else 'OFF'}", (200, 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(overlay, f"SENS:{SENSITIVITY:.2f}", (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
            if current_dist > 0:
                cv2.putText(overlay, f"Dist:{current_dist:.0f}px", (10, 75),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

            cv2.imshow("Overlay", overlay)

            # 定期刷新topmost（和Demo09.4一致）
            if time.time() - last_topmost > 3.0:
                if overlay_hwnd:
                    try:
                        win32gui.SetWindowPos(overlay_hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                    except:
                        pass
                last_topmost = time.time()

            cv2.waitKey(1)

    running.clear()
    cap_proc.join(timeout=1)
    if cap_proc.is_alive():
        cap_proc.terminate()

    if SHOW_OVERLAY:
        cv2.destroyAllWindows()

    # 关闭日志文件
    if log_file:
        log_file.write(f"\n=== 程序结束 ===\n")
        log_file.write(f"最终 SENSITIVITY: {SENSITIVITY:.3f}\n")
        log_file.close()
        print(f"日志已保存到: {LOG_FILE}")

    keyboard.unhook_all()
    print("Exit")
