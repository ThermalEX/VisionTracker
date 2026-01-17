"""
Demo11.1 - 混合方案：瞬移 + PID
远距离使用瞬移快速接近，近距离使用 PID 精细调整
F6 自动校准
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
CLICK_RADIUS_RATIO = 1.1  # 开火范围 = 头部半径 × 比例
CLICK_RADIUS_MIN = 5  # 最小开火范围（像素）
CLICK_RADIUS_MAX = 50  # 最大开火范围（像素）
AUTO_CLICK = True
CLICK_INTERVAL = 0.2 #开火间隔
TARGET_PRIORITY = 'nearest'
SHOW_OVERLAY = True
SHOW_BBOX = True  # 显示敌人检测框

# ==================== 瞬移参数 ====================
# SNAP_THRESHOLD (瞬移阈值):
#   - 作用：误差大于此值时使用瞬移，小于时用PID
#   - 调大：更多使用PID（更平滑但慢）
#   - 调小：更多使用瞬移（更快但可能超调）
#
# SNAP_SENSITIVITY (瞬移灵敏度):
#   - 作用：瞬移时 移动量 = 误差 * 灵敏度
#   - 校准后会自动更新
#   - 调大：移动更多
#   - 调小：移动更少
#
# SNAP_COOLDOWN (瞬移冷却):
#   - 作用：瞬移后等待画面更新的时间
#   - 调大：更稳定，但响应慢
#   - 调小：响应快，但可能还没更新就再次移动
# ==================================================

SNAP_THRESHOLD = 40     # 误差大于此值时使用瞬移（像素）
SNAP_SENSITIVITY = 2.2  # 瞬移灵敏度（校准后更新）
SNAP_COOLDOWN = 0.2    # 瞬移后冷却时间（秒）
SNAP_UPDATE_THRESHOLD = 20  # 瞬移后误差变化阈值

# ==================== PID 参数 ====================
# 当误差小于 SNAP_THRESHOLD 时使用 PID 微调
#
# PID_KP: 比例系数，校准后自动更新
# PID_KI: 积分系数（设为0）
# PID_KD: 微分系数
# DEADZONE: 死区，误差小于此值停止移动
# ==================================================

PID_KP = 0.3
PID_KI = 0.0
PID_KD = 0.001
DEADZONE = 0

# PID 冷却参数
PID_COOLDOWN = 0.05
PID_ERROR_THRESHOLD = 3

# 校准配置
CALIBRATE_SAMPLES = 3


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
        mode = data.get('mode', 'PID')  # 'SNAP' or 'PID'
        sens = data.get('sens', SNAP_SENSITIVITY)
        kp = data.get('kp', PID_KP)
        all_heads = data.get('all_heads', [])

        # ROI 框只画四个角（避免干扰检测）
        corner_len = 30  # 角的长度
        corner_thick = 1  # 角的粗细
        # 左上角
        cv2.line(overlay, (x1_roi, y1_roi), (x1_roi + corner_len, y1_roi), (255, 255, 255), corner_thick)
        cv2.line(overlay, (x1_roi, y1_roi), (x1_roi, y1_roi + corner_len), (255, 255, 255), corner_thick)
        # 右上角
        cv2.line(overlay, (x2_roi, y1_roi), (x2_roi - corner_len, y1_roi), (255, 255, 255), corner_thick)
        cv2.line(overlay, (x2_roi, y1_roi), (x2_roi, y1_roi + corner_len), (255, 255, 255), corner_thick)
        # 左下角
        cv2.line(overlay, (x1_roi, y2_roi), (x1_roi + corner_len, y2_roi), (255, 255, 255), corner_thick)
        cv2.line(overlay, (x1_roi, y2_roi), (x1_roi, y2_roi - corner_len), (255, 255, 255), corner_thick)
        # 右下角
        cv2.line(overlay, (x2_roi, y2_roi), (x2_roi - corner_len, y2_roi), (255, 255, 255), corner_thick)
        cv2.line(overlay, (x2_roi, y2_roi), (x2_roi, y2_roi - corner_len), (255, 255, 255), corner_thick)

        # 准星画在 ROI 外面（四个小点）
        dot_offset = FOV_WIDTH // 2 + 8
        cv2.circle(overlay, (center_x - dot_offset, center_y), 3, (255, 255, 255), -1)
        cv2.circle(overlay, (center_x + dot_offset, center_y), 3, (255, 255, 255), -1)
        cv2.circle(overlay, (center_x, center_y - dot_offset), 3, (255, 255, 255), -1)
        cv2.circle(overlay, (center_x, center_y + dot_offset), 3, (255, 255, 255), -1)

        # 检测框和目标圆不在 ROI 内绘制（避免干扰检测）
        # 只在 ROI 外显示目标方向指示
        if head_x is not None:
            color = (255, 100, 0) if mode == 'SNAP' else (0, 255, 0)
            # 在 ROI 边缘画方向指示线（从 ROI 边缘指向目标）
            # 计算从中心到目标的方向
            dx = head_x - center_x
            dy = head_y - center_y
            dist_to_head = math.sqrt(dx * dx + dy * dy)
            if dist_to_head > 1:
                # 归一化方向
                dx_norm = dx / dist_to_head
                dy_norm = dy / dist_to_head
                # 从 ROI 边缘外开始画
                start_dist = FOV_WIDTH // 2 + 5
                end_dist = FOV_WIDTH // 2 + 40  # 更长的指示线
                start_x = int(center_x + dx_norm * start_dist)
                start_y = int(center_y + dy_norm * start_dist)
                end_x = int(center_x + dx_norm * end_dist)
                end_y = int(center_y + dy_norm * end_dist)
                cv2.line(overlay, (start_x, start_y), (end_x, end_y), color, 3)  # 更粗

        aim_color = (0, 255, 0) if aim_active else (0, 0, 255)
        cv2.putText(overlay, f"FPS:{fps:.0f}", (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(overlay, f"AIM:{'ON' if aim_active else 'OFF'}", (100, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, aim_color, 2)
        cv2.putText(overlay, f"FIRE:{'ON' if AUTO_CLICK else 'OFF'}", (200, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # 显示当前模式
        mode_color = (255, 100, 0) if mode == 'SNAP' else (0, 255, 0)
        cv2.putText(overlay, f"Mode:{mode}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, mode_color, 1)
        cv2.putText(overlay, f"SENS:{sens:.2f} Kp:{kp:.2f}", (10, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

        if conf > 0:
            cv2.putText(overlay, f"Conf:{conf:.2f} Dist:{dist:.0f}px", (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

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
        heads.append({
            'cx': head_cx, 'cy': head_cy, 'r': head_r,
            'dist': dist, 'conf': conf, 'cls': cls,
            'bbox': (real_x1, real_y1, real_x2, real_y2)  # 添加检测框坐标
        })

    if not heads:
        return None, []
    heads.sort(key=lambda h: h['dist'] if TARGET_PRIORITY == 'nearest' else -h['conf'])
    best = heads[0]
    return (best['cx'], best['cy'], best['r'], best['cls'], best['conf'], best['bbox']), heads


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

    target, _ = find_nearest_head(boxes, cx, cy, x1, y1)
    if target:
        return target[0], target[1]  # cx, cy
    return None, None


def calibrate(model, use_trt, frame_queue, mouse, pid_controller, overlay_queue):
    """校准瞬移灵敏度和PID的Kp参数"""
    global SNAP_SENSITIVITY, PID_KP

    print("\n" + "=" * 50)
    print("开始校准 - 请将准心对准一个静止的目标")
    print(f"当前 SENS={SNAP_SENSITIVITY:.3f}, Kp={pid_controller.kp:.3f}")
    print("=" * 50)

    time.sleep(0.5)

    for iteration in range(CALIBRATE_SAMPLES):
        print(f"\n--- 迭代 {iteration + 1}/{CALIBRATE_SAMPLES} (SENS={SNAP_SENSITIVITY:.3f}) ---")

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

        error_x = target_x - cx
        error_y = target_y - cy
        error_dist = math.sqrt(error_x ** 2 + error_y ** 2)

        # 显示目标
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
                    'mode': 'CAL',
                    'sens': SNAP_SENSITIVITY,
                    'kp': pid_controller.kp
                })
            except:
                pass
        time.sleep(0.3)

        print(f"  目标位置: ({target_x}, {target_y})")
        print(f"  误差: ({error_x:.0f}, {error_y:.0f}), 距离: {error_dist:.1f}px")

        if error_dist < 15:
            print("  误差太小，自动移开准心...")
            mouse.move(100, 0)
            time.sleep(0.3)
            continue

        # 使用当前灵敏度移动
        move_x = int(error_x * SNAP_SENSITIVITY)
        move_y = int(error_y * SNAP_SENSITIVITY)
        print(f"  发送移动: ({move_x}, {move_y})")

        mouse.move(move_x, move_y)

        # 移动后清除显示（不显示圆和线）
        if overlay_queue:
            try:
                while not overlay_queue.empty():
                    overlay_queue.get_nowait()
                overlay_queue.put_nowait({
                    'roi': (cx - FOV_WIDTH//2, cy - FOV_HEIGHT//2,
                            cx + FOV_WIDTH//2, cy + FOV_HEIGHT//2),
                    'center': (cx, cy),
                    'head': (None, None),  # 不显示目标
                    'aim_active': True,
                    'conf': 0,
                    'dist': 0,
                    'fps': 0,
                    'click_radius': 15,
                    'mode': 'CAL',
                    'sens': SNAP_SENSITIVITY,
                    'kp': pid_controller.kp
                })
            except:
                pass

        time.sleep(0.2)

        # 获取移动后的帧
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

        # 计算实际移动效果
        actual_move_x = target_x - new_target_x
        actual_move_y = target_y - new_target_y

        print(f"  实际效果: 视角移动了 ({actual_move_x:.0f}, {actual_move_y:.0f})")

        # 调整灵敏度
        if abs(actual_move_x) > 5:
            adjust = error_x / actual_move_x
            SNAP_SENSITIVITY = SNAP_SENSITIVITY * adjust
            print(f"  调整系数: {adjust:.3f}, 新 SENS: {SNAP_SENSITIVITY:.3f}")
        elif abs(actual_move_y) > 5:
            adjust = error_y / actual_move_y
            SNAP_SENSITIVITY = SNAP_SENSITIVITY * adjust
            print(f"  调整系数: {adjust:.3f}, 新 SENS: {SNAP_SENSITIVITY:.3f}")

        SNAP_SENSITIVITY = max(0.1, min(5.0, SNAP_SENSITIVITY))

        # 移回初始位置（用发送的命令值反向移回）
        if iteration < CALIBRATE_SAMPLES - 1:
            back_x = -move_x
            back_y = -move_y
            print(f"  移回初始位置: ({back_x}, {back_y})")
            mouse.move(back_x, back_y)
            time.sleep(0.3)

    # 根据瞬移灵敏度计算 PID 的 Kp
    # PID 每帧都移动，所以需要更小的系数
    damping = 3.0
    pid_controller.kp = SNAP_SENSITIVITY / damping
    pid_controller.kp = max(0.1, min(2.0, pid_controller.kp))
    PID_KP = pid_controller.kp

    print("\n" + "=" * 50)
    print(f"校准完成！")
    print(f"  瞬移灵敏度 SENS: {SNAP_SENSITIVITY:.3f}")
    print(f"  PID Kp: {pid_controller.kp:.3f} (SENS / {damping})")
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

    # 扫描模型
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
        device = torch.device('cuda')
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
    print("Demo11.1 - 混合方案：瞬移 + PID")
    print(f"瞬移: SENS={SNAP_SENSITIVITY}, 阈值={SNAP_THRESHOLD}px")
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

    # 状态变量
    last_move_time = 0
    pre_move_error_x = 0
    pre_move_error_y = 0
    waiting_for_update = False
    current_mode = 'PID'  # 'SNAP' or 'PID'

    # 移动累积器（解决取整丢失小数的问题）
    move_acc_x = 0.0
    move_acc_y = 0.0

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
        all_heads = []  # 所有检测到的头部（用于显示检测框）

        if AIM_ENABLED and all_boxes and aim_active:
            target, all_heads = find_nearest_head(all_boxes, center_x, center_y, x1_roi, y1_roi)

            if target:
                head_x, head_y, head_r, head_cls, head_conf, head_bbox = target
                current_conf = head_conf

                click_radius = int(head_r * CLICK_RADIUS_RATIO)
                click_radius = max(CLICK_RADIUS_MIN, min(CLICK_RADIUS_MAX, click_radius))

                # 目标切换检测（只基于类别，避免瞬移后误判）
                # 注意：不重置 waiting_for_update，否则瞬移后位置变化会触发立即再次移动
                tid = head_cls  # 只用类别判断是否切换目标
                if last_target_id is not None and tid != last_target_id:
                    pid.reset()
                    # 不重置 waiting_for_update
                last_target_id = tid

                # 计算误差（目标是头部中心）
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

                # ========== 混合瞄准逻辑 ==========
                if current_dist <= DEADZONE:
                    # 在死区内，不移动
                    current_mode = 'PID'
                    waiting_for_update = False

                elif current_dist > SNAP_THRESHOLD:
                    # === 远距离：使用瞬移 ===
                    current_mode = 'SNAP'
                    now = time.time()
                    time_since_move = now - last_move_time

                    can_move = False
                    if not waiting_for_update:
                        can_move = True
                    else:
                        error_change = math.sqrt((error_x - pre_move_error_x) ** 2 +
                                                (error_y - pre_move_error_y) ** 2)
                        # 满足其一即可：画面更新 OR 冷却时间到
                        if error_change > SNAP_UPDATE_THRESHOLD:
                            can_move = True
                            waiting_for_update = False
                        elif time_since_move >= SNAP_COOLDOWN:
                            can_move = True
                            waiting_for_update = False

                    if can_move and mouse_driver.is_loaded():
                        move_x = int(error_x * SNAP_SENSITIVITY)
                        move_y = int(error_y * SNAP_SENSITIVITY)
                        mouse_driver.move(move_x, move_y)
                        last_move_time = now
                        pre_move_error_x = error_x
                        pre_move_error_y = error_y
                        waiting_for_update = True

                else:
                    # === 近距离：使用 PID ===
                    current_mode = 'PID'
                    now = time.time()
                    time_since_move = now - last_move_time

                    can_move = False
                    if not waiting_for_update:
                        can_move = True
                    else:
                        error_change = math.sqrt((error_x - pre_move_error_x) ** 2 +
                                                (error_y - pre_move_error_y) ** 2)
                        # 满足其一即可：画面更新 OR 冷却时间到
                        if error_change > PID_ERROR_THRESHOLD:
                            can_move = True
                            waiting_for_update = False
                        elif time_since_move >= PID_COOLDOWN:
                            can_move = True
                            waiting_for_update = False

                    if can_move and mouse_driver.is_loaded():
                        out_x, out_y = pid.compute(error_x, error_y)
                        # 使用累积器，解决小数取整丢失的问题
                        move_acc_x += out_x
                        move_acc_y += out_y
                        int_move_x = int(move_acc_x)
                        int_move_y = int(move_acc_y)
                        if int_move_x != 0 or int_move_y != 0:
                            mouse_driver.move(int_move_x, int_move_y)
                            move_acc_x -= int_move_x
                            move_acc_y -= int_move_y
                        last_move_time = now
                        pre_move_error_x = error_x
                        pre_move_error_y = error_y
                        waiting_for_update = True
        else:
            # 没有目标时重置累积器
            move_acc_x = 0.0
            move_acc_y = 0.0
            if last_target_id:
                pid.reset()
                last_target_id = None
            current_mode = 'PID'

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
                    'mode': current_mode,
                    'sens': SNAP_SENSITIVITY,
                    'kp': pid.kp,
                    'all_heads': all_heads  # 所有检测框
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
