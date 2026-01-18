import pygetwindow as gw
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from multiprocessing import Process, Queue, Event
import time
import win32gui
import win32con
import keyboard
import mss
import pyautogui
import os

# --- 配置区域 ---
# 在此处设置中心长方形的 宽 和 高 (像素)
FOV_WIDTH = 200  # 宽度
FOV_HEIGHT = 200  # 高度
CONF_THRESHOLD = 0.35  # 置信度阈值（提高可减少误检，降低延迟）
IMGSZ = 200  # 推理输入尺寸（仅对 PyTorch 模型有效，TensorRT 使用导出时的固定尺寸）
SHOW_PERF = True  # 是否显示性能统计（关闭可提升 2-3ms）

# ----------------

def capture_process(frame_queue,
                    running_event,
                    choice,
                    all_windows):
    # ... (保持不变) ...
    target_window_title = None
    target_window = None
    monitor = {}

    if choice == -1:
        with mss.mss() as sct:
            monitor = sct.monitors[1]
    else:
        target_window_title = all_windows[choice]
        target_window = gw.getWindowsWithTitle(target_window_title)[0]
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

                    monitor["top"] = target_window.top
                    monitor["left"] = target_window.left
                    monitor["width"] = target_window.width
                    monitor["height"] = target_window.height

                    if monitor["width"] <= 0 or monitor["height"] <= 0:
                        time.sleep(0.1)
                        continue

                sct_img = sct.grab(monitor)
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame,
                                     cv2.COLOR_BGRA2BGR)

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
    # ... (保持不变，使用颜色过滤版本) ...
    # time.sleep(0.1)
    hwnd = win32gui.FindWindow(None,
                               window_name)

    if hwnd:
        ex_style = win32gui.GetWindowLong(hwnd,
                                          win32con.GWL_EXSTYLE)
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE
        )
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
        )
        # 黑色背景变透明
        win32gui.SetLayeredWindowAttributes(
            hwnd,
            0,
            255,
            win32con.LWA_COLORKEY
        )
        return hwnd
    return None


def keep_topmost(hwnd):
    # ... (保持不变) ...
    if hwnd:
        try:
            style = win32gui.GetWindowLong(hwnd,
                                           win32con.GWL_STYLE)
            style &= ~(
                        win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_MINIMIZE | win32con.WS_MAXIMIZE | win32con.WS_SYSMENU)
            win32gui.SetWindowLong(hwnd,
                                   win32con.GWL_STYLE,
                                   style)
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
            pass


if __name__ == '__main__':
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

    # 自动检测并使用 TensorRT 引擎（如果存在）
    model_name = "best 12.23"
    pt_path = f"../models/{model_name}.pt"

    # 查找所有可用的引擎文件（包括带尺寸标识的）
    import glob
    engine_files = glob.glob(f"../models/{model_name}*.engine")

    if engine_files:
        # 优先使用较小尺寸的引擎（更快）
        # 从文件名提取尺寸，格式如 "best 12.12_384.engine"
        def get_engine_size(path):
            # 提取尺寸，如果没有则返回 640（默认）
            if '_' in path:
                try:
                    size_str = path.split('_')[-1].replace('.engine', '')
                    return int(size_str)
                except:
                    return 640
            return 640

        # 按尺寸排序，优先使用较小的
        engine_files.sort(key=get_engine_size)
        engine_path = engine_files[0]
        engine_size = get_engine_size(engine_path)

        print(f"🚀 使用 TensorRT 引擎: {engine_path} (输入尺寸: {engine_size}x{engine_size})")
        if len(engine_files) > 1:
            print(f"   检测到其他引擎: {', '.join(engine_files[1:])}")

        model = YOLO(engine_path)
        using_tensorrt = True
        model_input_size = engine_size
    elif os.path.exists(pt_path):
        print(f"⚙️  使用 PyTorch 模型: {pt_path}")
        model = YOLO(pt_path)
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model.to(device)
        model.fuse()
        if device.type == 'cuda':
            model.half()
        using_tensorrt = False
        model_input_size = IMGSZ
        print("💡 提示: 运行 'python export_tensorrt.py' 可导出 TensorRT 引擎以获得更快速度")
    else:
        raise FileNotFoundError(f"找不到模型文件: {pt_path} 或 ../models/{model_name}*.engine")

    window_name = "Overlay"
    cv2.namedWindow(window_name,
                    cv2.WINDOW_NORMAL)

    if choice != -1:
        target_window = gw.getWindowsWithTitle(all_windows[choice])[0]
        win_w = target_window.width
        win_h = target_window.height
        win_x = target_window.left
        win_y = target_window.top
    else:
        win_w, win_h = pyautogui.size()
        win_x, win_y = 0, 0

    cv2.resizeWindow(window_name, win_w, win_h)
    cv2.moveWindow(window_name, win_x, win_y)

    # --- 修复启动闪烁问题 ---
    # 在设置透明属性前，先显示一帧全黑图像，确保窗口背景为黑色
    # 这样 LWA_COLORKEY 生效时，窗口即刻变为全透明
    dummy_black = np.zeros((win_h, win_w, 3), dtype=np.uint8)
    cv2.imshow(window_name, dummy_black)
    cv2.waitKey(1)  # 强制刷新窗口内容
    # ----------------------

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


    def on_exit():
        running_event.clear()


    keyboard.add_hotkey('ctrl+q',
                        on_exit)

    last_topmost = time.time()
    last_check = time.time()

    # FPS 统计
    fps_start_time = time.time()
    fps_frame_count = 0
    current_fps = 0.0

    # 性能分析
    perf_stats = {
        'crop': 0.0,
        'inference': 0.0,
        'draw': 0.0,
        'total': 0.0
    }

    while running_event.is_set():
        frame_start = time.time()

        try:
            frame = frame_queue.get(timeout=0.1)
        except:
            cv2.waitKey(1)
            continue

        h, w = frame.shape[:2]

        # --- 修改核心逻辑：使用长方形 ---

        # 1. 计算中心长方形的坐标
        center_x, center_y = w // 2, h // 2

        # 分别计算宽度和高度的一半
        half_w = FOV_WIDTH // 2
        half_h = FOV_HEIGHT // 2

        # 确保裁剪区域不超出屏幕边界
        x1_roi = max(0,
                     center_x - half_w)
        y1_roi = max(0,
                     center_y - half_h)
        x2_roi = min(w,
                     center_x + half_w)
        y2_roi = min(h,
                     center_y + half_h)

        # 2. 裁剪图像
        t1 = time.time()
        crop_frame = frame[y1_roi:y2_roi, x1_roi:x2_roi]
        perf_stats['crop'] = time.time() - t1

        # 3. 推理（应用置信度阈值过滤）
        # 注意：TensorRT 引擎使用固定输入尺寸，PyTorch 模型可以动态调整
        t2 = time.time()
        if using_tensorrt:
            # TensorRT 引擎已固化输入尺寸，不需要 imgsz 参数
            results = model(crop_frame,
                            conf=CONF_THRESHOLD,
                            verbose=False)
        else:
            # PyTorch 模型可以动态调整输入尺寸
            results = model(crop_frame,
                            conf=CONF_THRESHOLD,
                            imgsz=IMGSZ,
                            verbose=False)
        perf_stats['inference'] = time.time() - t2

        # 创建黑色覆盖层 (后续会被变透明)
        t3 = time.time()
        overlay = np.zeros((h, w, 3),
                           dtype=np.uint8)

        # 4. 绘制中心长方形框 (白色边框)
        cv2.rectangle(overlay,
                      (x1_roi, y1_roi),
                      (x2_roi, y2_roi),
                      (255, 255, 255),
                      1)

        # 计算并显示 FPS
        fps_frame_count += 1
        if fps_frame_count >= 30:  # 每 30 帧更新一次 FPS
            current_time = time.time()
            current_fps = fps_frame_count / (current_time - fps_start_time)
            fps_start_time = current_time
            fps_frame_count = 0

        # 显示 FPS 和模型类型（左上角）
        fps_text = f"FPS: {current_fps:.1f}"
        if using_tensorrt:
            model_text = f"TRT-{model_input_size}"
        else:
            model_text = "PyTorch"
        crop_h, crop_w = crop_frame.shape[:2]
        status_text = f"{fps_text} | {model_text} | ROI:{crop_w}x{crop_h}"

        cv2.putText(overlay,
                    status_text,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2)

        if isinstance(results,
                      list) and len(results) > 0:
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # 获取相对于 crop_frame 的坐标
                    bx1, by1, bx2, by2 = map(int,
                                             box.xyxy[0])

                    # 5. 坐标映射
                    real_x1 = bx1 + x1_roi
                    real_y1 = by1 + y1_roi
                    real_x2 = bx2 + x1_roi
                    real_y2 = by2 + y1_roi

                    conf = float(box.conf[0])
                    cls = int(box.cls[0])

                    # 根据阵营设置颜色 (BGR格式)
                    # ct_head(0), ct_body(1) -> 蓝色
                    # t_head(2), t_body(3) -> 红色
                    if cls in [0, 1]:  # CT
                        color = (255, 0, 0)  # 蓝色
                    else:  # T
                        color = (0, 0, 255)  # 红色

                    # 绘制检测框
                    cv2.rectangle(overlay,
                                  (real_x1, real_y1),
                                  (real_x2, real_y2),
                                  color,
                                  2)

                    label = f"{model.names[cls]} {conf:.2f}"
                    (tw, th), _ = cv2.getTextSize(label,
                                                  cv2.FONT_HERSHEY_SIMPLEX,
                                                  0.6,
                                                  2)
                    cv2.rectangle(overlay,
                                  (real_x1, real_y1 - th - 10),
                                  (real_x1 + tw + 10, real_y1),
                                  color,
                                  -1)
                    cv2.putText(overlay,
                                label,
                                (real_x1 + 5, real_y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (0, 0, 0),
                                2)

        perf_stats['draw'] = time.time() - t3
        perf_stats['total'] = time.time() - frame_start

        # --- 修改结束 ---

        # 显示详细性能信息（右上角）- 仅在开启时显示
        if SHOW_PERF:
            perf_y = 30
            perf_texts = [
                f"C:{perf_stats['crop']*1000:.1f} I:{perf_stats['inference']*1000:.1f} D:{perf_stats['draw']*1000:.1f} T:{perf_stats['total']*1000:.1f}ms"
            ]
            for perf_text in perf_texts:
                cv2.putText(overlay,
                            perf_text,
                            (w - 280, perf_y),  # 固定位置，避免 getTextSize 开销
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (255, 255, 0),
                            1)
                perf_y += 20

        cv2.imshow(window_name,
                   overlay)

        current = time.time()

        if current - last_topmost > 3.0:
            keep_topmost(hwnd)
            last_topmost = current

        if choice != -1 and current - last_check > 3.0:
            try:
                tw = gw.getWindowsWithTitle(all_windows[choice])[0]
                ow = gw.getWindowsWithTitle(window_name)[0]
                if ow.left != tw.left or ow.top != tw.top or ow.width != tw.width or ow.height != tw.height:
                    cv2.moveWindow(window_name,
                                   tw.left,
                                   tw.top)
                    cv2.resizeWindow(window_name,
                                     tw.width,
                                     tw.height)
                last_check = current
            except:
                pass

        # 减少 waitKey 调用（已由 keyboard 监听退出）
        cv2.waitKey(1)

    running_event.clear()
    capture_proc.join(timeout=2)
    if capture_proc.is_alive():
        capture_proc.terminate()

    cv2.destroyAllWindows()
    keyboard.unhook_all()
    print("exit")