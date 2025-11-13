# use multiprocessing for screen capture and YOLO inference
# 使用多进程进行屏幕捕获和YOLO推理

import cv2
import torch
import numpy as np
import multiprocessing as mp
import mss
import pygetwindow as gw
import time
from ultralytics import YOLO


def capture_process(frame_queue, running_event, choice, all_windows):
    # 捕获进程：负责不断截图并发送到队列
    sct = mss.mss()

    while running_event.is_set():
        try:
            if choice == -1:
                # 捕获整个屏幕
                monitor = sct.monitors[1]
                img = np.array(sct.grab(monitor))
            else:
                # 捕获指定窗口
                target_window_title = all_windows[choice]
                target_window = gw.getWindowsWithTitle(target_window_title)[0]
                if not target_window:
                    time.sleep(0.05)
                    continue

                left, top, width, height = (
                    target_window.left,
                    target_window.top,
                    target_window.width,
                    target_window.height,
                )
                monitor = {"left": left, "top": top, "width": width, "height": height}
                img = np.array(sct.grab(monitor))

            # BGRA → BGR
            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # 队列只保留最新一帧
            if not frame_queue.empty():
                try:
                    frame_queue.get_nowait()
                except Exception:
                    pass
            frame_queue.put_nowait(frame)

        except Exception as e:
            print(f"[捕获进程出错] {e}")
            time.sleep(0.05)
            continue


def inference_process(frame_queue, running_event):
    # 推理进程：负责YOLO检测和显示
    print("正在加载 YOLO 模型...")
    model = YOLO("best.pt")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"使用设备: {device}")

    cv2.namedWindow("YOLO Capture", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("YOLO Capture", 854, 480)

    while running_event.is_set():
        try:
            frame = frame_queue.get(timeout=0.1)
        except Exception:
            if cv2.waitKey(1) & 0xFF == ord("q"):
                running_event.clear()
                break
            continue

        # YOLO 推理
        results = model(frame)
        annotated = results[0].plot()

        cv2.imshow("YOLO Capture", annotated)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            running_event.clear()
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    mp.set_start_method("spawn")  # Windows 推荐使用 spawn

    all_windows = [w for w in gw.getAllTitles() if w.strip()]
    print("可用窗口列表：")
    for i, title in enumerate(all_windows):
        print(f"{i}: {title}")

    while True:
        try:
            choice = int(input("请输入窗口编号（或输入 -1 捕获整个桌面）："))
            if -1 <= choice < len(all_windows):
                break
        except ValueError:
            pass
        print("请输入有效数字！")

    frame_queue = mp.Queue(maxsize=1)  # 始终只保留最新一帧
    running_event = mp.Event()
    running_event.set()

    # 启动捕获与推理两个独立进程
    p1 = mp.Process(target=capture_process, args=(frame_queue, running_event, choice, all_windows))
    p2 = mp.Process(target=inference_process, args=(frame_queue, running_event))

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("程序已退出。")
