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


def capture_process(frame_queue,
                    running_event,
                    choice,
                    all_windows):
    # 捕获进程函数
    target_window_title = None
    target_window = None
    monitor = {}

    if choice == -1:
        # 全屏捕获
        with mss.mss() as sct:
            monitor = sct.monitors[1]
    else:
        # 窗口捕获
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
                    # 实时更新窗口位置和大小
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

                sct_img = sct.grab(monitor)  # 截取屏幕
                frame = np.array(sct_img)
                frame = cv2.cvtColor(frame,
                                     cv2.COLOR_BGRA2BGR)

                while not frame_queue.empty():
                    # 清空队列，保证低延迟
                    try:
                        frame_queue.get_nowait()
                    except:
                        break

                try:
                    frame_queue.put_nowait(frame)  # 将新帧放入队列
                except:
                    pass

            except Exception as e:
                print(f"capture error: {e}")
                time.sleep(0.5)


def make_window_transparent(window_name):
    # 使窗口透明和穿透
    time.sleep(0.5)
    hwnd = win32gui.FindWindow(None,
                               window_name)

    if hwnd:
        # 获取窗口扩展样式
        ex_style = win32gui.GetWindowLong(hwnd,
                                          win32con.GWL_EXSTYLE)
        # 设置窗口为分层、透明、置顶、无焦点
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE
        )

        # 保持窗口置顶
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0,
            0,
            0,
            0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
        )

        # 设置窗口透明度 (0-255)
        win32gui.SetLayeredWindowAttributes(hwnd,
                                            0,
                                            50,
                                            win32con.LWA_ALPHA)
        return hwnd
    return None


def keep_topmost(hwnd):
    # 保持窗口置顶并移除边框
    if hwnd:
        try:
            # 移除窗口标题栏和边框
            style = win32gui.GetWindowLong(hwnd,
                                           win32con.GWL_STYLE)
            style &= ~(
                        win32con.WS_CAPTION | win32con.WS_THICKFRAME | win32con.WS_MINIMIZE | win32con.WS_MAXIMIZE | win32con.WS_SYSMENU)
            win32gui.SetWindowLong(hwnd,
                                   win32con.GWL_STYLE,
                                   style)

            # 再次设置窗口置顶
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
    # 获取所有非空标题的窗口
    all_windows = [w for w in gw.getAllTitles() if w.strip()]

    print("windows:")
    for i, title in enumerate(all_windows):
        print(f"{i}: {title}")

    while True:
        try:
            # 用户选择要捕获的窗口
            choice = int(input("window number (-1 for fullscreen): "))
            if -1 <= choice < len(all_windows):
                break
        except ValueError:
            pass

    # 加载YOLO模型
    model = YOLO("../../models/best 12.10.pt")
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    model.fuse()

    if device.type == 'cuda':
        model.half()  # 使用半精度浮点数加速

    # 创建覆盖窗口
    window_name = "Overlay"
    cv2.namedWindow(window_name,
                    cv2.WINDOW_NORMAL)

    if choice != -1:
        # 调整覆盖窗口大小和位置以匹配目标窗口
        target_window = gw.getWindowsWithTitle(all_windows[choice])[0]
        cv2.resizeWindow(window_name,
                         target_window.width,
                         target_window.height)
        cv2.moveWindow(window_name,
                       target_window.left,
                       target_window.top)
    else:
        # 全屏模式
        import pyautogui

        w, h = pyautogui.size()
        cv2.resizeWindow(window_name,
                         w,
                         h)
        cv2.moveWindow(window_name,
                       0,
                       0)

    # 使覆盖窗口透明
    hwnd = make_window_transparent(window_name)

    # 设置多进程用于屏幕捕获
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
        # 退出函数
        running_event.clear()


    # 注册退出热键
    keyboard.add_hotkey('ctrl+q',
                        on_exit)

    last_topmost = time.time()
    last_check = time.time()

    while running_event.is_set():
        try:
            # 从队列中获取帧
            frame = frame_queue.get(timeout=0.1)
        except:
            cv2.waitKey(1)
            continue

        # 运行模型进行推理
        results = model(frame)

        # 创建一个黑色的覆盖层
        h, w = frame.shape[:2]
        overlay = np.zeros((h, w, 3),
                           dtype=np.uint8)

        if isinstance(results,
                      list) and len(results) > 0:
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # 绘制检测框和标签
                    x1, y1, x2, y2 = map(int,
                                         box.xyxy[0])
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])

                    cv2.rectangle(overlay,
                                  (x1, y1),
                                  (x2, y2),
                                  (0, 255, 0),
                                  4)

                    label = f"{model.names[cls]} {conf:.2f}"
                    (tw, th), _ = cv2.getTextSize(label,
                                                  cv2.FONT_HERSHEY_SIMPLEX,
                                                  0.6,
                                                  2)
                    cv2.rectangle(overlay,
                                  (x1, y1 - th - 10),
                                  (x1 + tw + 10, y1),
                                  (0, 255, 0),
                                  -1)
                    cv2.putText(overlay,
                                label,
                                (x1 + 5, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (0, 0, 0),
                                2)

        # 显示覆盖层
        cv2.imshow(window_name,
                   overlay)

        current = time.time()

        if current - last_topmost > 2.0:
            # 定期保持窗口置顶
            keep_topmost(hwnd)
            last_topmost = current

        if choice != -1 and current - last_check > 1.0:
            try:
                # 定期检查并同步目标窗口的位置和大小
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

        if cv2.waitKey(1) & 0xFF == ord('q'):
            running_event.clear()
            break

    # 清理资源
    running_event.clear()
    capture_proc.join(timeout=2)
    if capture_proc.is_alive():
        capture_proc.terminate()

    cv2.destroyAllWindows()
    keyboard.unhook_all()
    print("exit")