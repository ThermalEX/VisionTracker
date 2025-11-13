# Render directly to a transparent window without stealing focus
# Optimized capture thread using mss library for efficient screen capture
# 直接渲染到透明窗口，且不抢夺焦点
# 优化了捕获线程，使用 mss 库进行高效屏幕捕获

import pygetwindow as gw
import pyautogui
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import threading
import queue
import time
import win32gui
import win32con
import keyboard  # 用于全局快捷键监听
import mss  # 导入 mss
import mss.tools  # 导入 mss.tools


# -------------------------------------------------------------
# 优化的捕获线程 (使用 mss)
# -------------------------------------------------------------
def capture_thread(frame_queue,
                   running_event,
                   choice,
                   all_windows):
    """屏幕捕获线程 (已使用 mss 优化)"""

    target_window_title = None
    target_window = None
    monitor = {}  # 捕获区域

    try:
        if choice == -1:
            # 捕获整个桌面 (通常是第一个显示器)
            with mss.mss() as sct:
                # sct.monitors[0] 是包含所有显示器的总和
                # sct.monitors[1] 是主显示器
                monitor = sct.monitors[1]
            print(f"正在捕获主显示器: {monitor}")
        else:
            # 捕获特定窗口
            target_window_title = all_windows[choice]
            target_window = gw.getWindowsWithTitle(target_window_title)[0]
            monitor = {
                "top": target_window.top,
                "left": target_window.left,
                "width": target_window.width,
                "height": target_window.height
            }
            print(f"正在捕获窗口: '{target_window_title}' 于 {monitor}")

    except Exception as e:
        print(f"初始化捕获区域失败: {e}")
        running_event.clear()
        return

    # 关键：在循环外创建 mss 实例
    with mss.mss() as sct:
        while running_event.is_set():
            try:
                # --- 关键优化：如果捕获的是窗口，实时更新其位置 ---
                if choice != -1:
                    try:
                        # 重新获取窗口句柄以确保其有效
                        target_window = gw.getWindowsWithTitle(target_window_title)[0]
                        if not target_window:
                            raise Exception("窗口未找到")

                        # 更新监视器区域
                        monitor["top"] = target_window.top
                        monitor["left"] = target_window.left
                        monitor["width"] = target_window.width
                        monitor["height"] = target_window.height

                        # 如果窗口最小化或尺寸为0，则跳过
                        if monitor["width"] <= 0 or monitor["height"] <= 0:
                            time.sleep(0.1)  # 窗口最小化了，稍等
                            continue

                    except Exception as win_e:
                        print(f"窗口 '{target_window_title}' 已关闭或丢失。正在退出... ({win_e})")
                        running_event.clear()
                        break

                # --- 高速捕获 ---
                sct_img = sct.grab(monitor)

                # 将 mss 的 BGRA 格式 转换为 OpenCV 的 BGR 格式
                frame = np.array(sct_img)
                # 注意：mss 捕获的是 BGRA，我们转为 BGR 供 OpenCV 使用
                frame = cv2.cvtColor(frame,
                                     cv2.COLOR_BGRA2BGR)

                # --- 您的队列逻辑 (这个逻辑是正确的) ---
                try:
                    frame_queue.get_nowait()  # 清空旧帧
                except queue.Empty:
                    pass

                try:
                    frame_queue.put_nowait(frame)  # 放入新帧
                except queue.Full:
                    pass  # 队列满了（主线程忙），丢弃这一帧

            except Exception as e:
                print(f"捕获线程出错: {e}")
                # 如果捕获失败（例如分辨率更改），稍等片刻
                time.sleep(0.5)

            # mss 非常快，不再需要 time.sleep(0.001)
            # 删掉休眠，让捕获线程全速运行


# -------------------------------------------------------------
# 窗口设置函数 (来自您的原始代码)
# -------------------------------------------------------------

def make_window_transparent_and_clickthrough(window_name):
    """
    将OpenCV窗口设置为透明且鼠标穿透
    """
    # 等待窗口创建
    time.sleep(0.5)

    # 获取窗口句柄
    hwnd = win32gui.FindWindow(None,
                               window_name)

    if hwnd:
        # 获取当前窗口样式
        ex_style = win32gui.GetWindowLong(hwnd,
                                          win32con.GWL_EXSTYLE)

        # 添加透明和鼠标穿透属性
        # WS_EX_LAYERED: 允许窗口透明
        # WS_EX_TRANSPARENT: 鼠标事件穿透窗口
        # WS_EX_TOPMOST: 窗口置顶
        # WS_EX_NOACTIVATE: 窗口不会被激活（不抢焦点）
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE
        )

        # 使用 SetWindowPos 强制窗口置顶（比 WS_EX_TOPMOST 更强）
        # HWND_TOPMOST: 置顶
        # SWP_NOACTIVATE: 不激活窗口（关键！保证不抢焦点）
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
        )

        # 设置窗口整体半透明，alpha值越小越透明
        win32gui.SetLayeredWindowAttributes(
            hwnd,
            0,
            50,  # alpha透明度: 0-255，改为50让背景几乎完全透明
            win32con.LWA_ALPHA
        )

        print("窗口已设置为透明和鼠标穿透模式（不会抢夺焦点）")
        return hwnd
    else:
        print("未找到窗口句柄")
        return None


def keep_window_topmost(hwnd):
    """
    持续保持窗口在最顶层，并移除边框
    """
    if hwnd:
        try:
            # 移除标题栏和边框
            style = win32gui.GetWindowLong(hwnd,
                                           win32con.GWL_STYLE)
            style &= ~(
                    win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_MINIMIZE | win32con.WS_MAXIMIZE | win32con.WS_SYSMENU)
            win32gui.SetWindowLong(hwnd,
                                   win32con.GWL_STYLE,
                                   style)

            # 保持置顶
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0,
                0,
                0,
                0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW | win32con.SWP_FRAMECHANGED
            )
        except:
            pass  # 忽略 win32gui 异常 (例如窗口关闭时)


# -------------------------------------------------------------
# 主程序
# -------------------------------------------------------------

# 列出所有窗口
all_windows = gw.getAllTitles()
all_windows = [win for win in all_windows if win.strip()]

print("可用窗口列表：")
for i, title in enumerate(all_windows):
    print(f"{i}: {title}")

while True:
    try:
        choice = int(input("请输入窗口编号（或输入 -1 捕获整个桌面）："))
        if -1 <= choice < len(all_windows):
            break
        else:
            print("请输入有效编号！")
    except ValueError:
        print("请输入数字！")

model = YOLO("10w v8.pt")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"使用设备: {device}")
model.to(device)

print("正在手动融合模型 (在 FP32 模式下)...")
model.fuse() # 关键：在 FP32 模式下先执行 FUSE

# ----------------- 优化建议 (可选) -----------------
if device.type == 'cuda':
    print("启用半精度 (FP16) 加速")
    model.half() # 然后再将已经融合的模型转换为 FP16
# ---------------------------------------------------

# 创建OpenCV窗口
window_name = "Overlay"
cv2.namedWindow(window_name,
                cv2.WINDOW_NORMAL)

# 获取目标窗口的位置和大小（如果选择了特定窗口）
if choice != -1:
    target_window = gw.getWindowsWithTitle(all_windows[choice])[0]
    cv2.resizeWindow(window_name,
                     target_window.width,
                     target_window.height)
    cv2.moveWindow(window_name,
                   target_window.left,
                   target_window.top)
else:
    # 全屏模式
    screen_width, screen_height = pyautogui.size()
    cv2.resizeWindow(window_name,
                     screen_width,
                     screen_height)
    cv2.moveWindow(window_name,
                   0,
                   0)

# 设置窗口透明和鼠标穿透
hwnd = make_window_transparent_and_clickthrough(window_name)

# 创建线程和队列
frame_queue = queue.Queue(maxsize=1)
running_event = threading.Event()
running_event.set()

capture_worker = threading.Thread(
    target=capture_thread,  # 使用我们新的 mss 捕获函数
    args=(frame_queue, running_event, choice, all_windows),
    daemon=True
)
capture_worker.start()
print("捕获线程已启动...")
print("=" * 50)
print("覆盖窗口已激活 - 可以直接用鼠标和键盘控制游戏！")
print("按 'Ctrl+Q' 退出程序（全局快捷键，随时可用）")
print("=" * 50)


# 注册全局快捷键
def on_exit():
    print("\n正在退出...")
    running_event.clear()


keyboard.add_hotkey('ctrl+q',
                    on_exit)

last_window_check_time = time.time()
last_topmost_time = time.time()

while running_event.is_set():
    try:
        # 从队列获取最新帧
        frame = frame_queue.get(timeout=0.1)
    except queue.Empty:
        # 如果队列为空 (捕获线程跟不上或暂停)，继续循环
        # 这也允许 'ctrl+q' 即使在没有新帧时也能被检测到
        if cv2.waitKey(1) & 0xFF == ord('q'):  # 保留一个备用退出键
            running_event.clear()
            break
        continue

    # ---------------------------------------------------
    # YOLO推理 (这里是主线程的瓶颈)
    # ---------------------------------------------------
    # --- 可选优化：缩小图像以加快推理 ---
    # original_height, original_width = frame.shape[:2]
    # inference_size = (640, 640) # 或您日志中的 (384, 640)
    # small_frame = cv2.resize(frame, (inference_size[1], inference_size[0]))
    # results = model(small_frame)
    # ---------------------------------

    # 不缩小的原始推理：
    results = model(frame)

    # ---------------------------------------------------

    # 创建黑色背景（黑色在alpha模式下会显示为透明）
    height, width = frame.shape[:2]
    overlay = np.zeros((height, width, 3),
                       dtype=np.uint8)

    # 绘制检测框 - 使用鲜艳的颜色确保可见
    if isinstance(results,
                  list) and len(results) > 0:
        for result in results:
            boxes = result.boxes
            for box in boxes:
                # 获取边界框坐标
                x1, y1, x2, y2 = map(int,
                                     box.xyxy[0])

                # --- 如果您使用了上面的缩放优化，需要在这里把坐标缩放回去 ---
                # scale_x = original_width / inference_size[1]
                # scale_y = original_height / inference_size[0]
                # x1, y1 = int(x1 * scale_x), int(y1 * scale_y)
                # x2, y2 = int(x2 * scale_x), int(y2 * scale_y)
                # -------------------------------------------------------

                conf = float(box.conf[0])
                cls = int(box.cls[0])

                # 绘制边界框（使用鲜艳的颜色，线条加粗）
                color = (0, 255, 0)  # 亮绿色
                thickness = 4  # 加粗线条让它在透明背景下更明显
                cv2.rectangle(overlay,
                              (x1, y1),
                              (x2, y2),
                              color,
                              thickness)

                # 绘制标签背景
                label = f"{model.names[cls]} {conf:.2f}"
                (text_width, text_height), _ = cv2.getTextSize(
                    label,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    2
                )
                # 标签背景用亮色
                cv2.rectangle(
                    overlay,
                    (x1, y1 - text_height - 10),
                    (x1 + text_width + 10, y1),
                    (0, 255, 0),  # 亮绿色背景
                    -1
                )
                # 标签文字用黑色（在亮色背景上清晰可见）
                cv2.putText(
                    overlay,
                    label,
                    (x1 + 5, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,  # 字体稍大一点
                    (0, 0, 0),  # 黑色文字
                    2
                )

    # 显示覆盖层
    cv2.imshow(window_name,
               overlay)

    current_time = time.time()

    # --- 优化：减少 win32 调用频率 ---
    # 每 2 秒检查一次窗口置顶
    if current_time - last_topmost_time > 2.0:
        keep_window_topmost(hwnd)
        last_topmost_time = current_time

    # 保持窗口位置同步（如果目标窗口移动）
    # 捕获线程已经在处理位置更新，但保险起见，主线程也低频检查一下
    if choice != -1 and (current_time - last_window_check_time > 1.0):
        try:
            target_window = gw.getWindowsWithTitle(all_windows[choice])[0]
            # 仅在检测到不一致时才移动，减少调用
            overlay_win = gw.getWindowsWithTitle(window_name)[0]
            if (overlay_win.left != target_window.left or
                    overlay_win.top != target_window.top or
                    overlay_win.width != target_window.width or
                    overlay_win.height != target_window.height):
                cv2.moveWindow(window_name,
                               target_window.left,
                               target_window.top)
                cv2.resizeWindow(window_name,
                                 target_window.width,
                                 target_window.height)
            last_window_check_time = current_time
        except Exception:
            # 窗口可能已关闭，捕获线程会处理退出
            pass

    if cv2.waitKey(1) & 0xFF == ord('q'):
        running_event.clear()
        break

cv2.destroyAllWindows()
keyboard.unhook_all()  # 确保快捷键被卸载
print("程序已退出。")