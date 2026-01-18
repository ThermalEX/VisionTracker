# use multiprocessing + kalman filter for YOLO head tracking
# 使用多进程 + 卡尔曼滤波追踪头部位置，结合ultralytics YOLO模型

import cv2
import torch
import numpy as np
import multiprocessing as mp
import mss
import pygetwindow as gw
import time
from ultralytics import YOLO


def capture_process(frame_queue, running_event, choice, all_windows):
    # 子进程：负责屏幕/窗口捕获
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
                win_list = gw.getWindowsWithTitle(target_window_title)
                if not win_list:
                    time.sleep(0.05)
                    continue
                target_window = win_list[0]
                left, top, width, height = (
                    target_window.left,
                    target_window.top,
                    target_window.width,
                    target_window.height,
                )
                monitor = {"left": left, "top": top, "width": width, "height": height}
                img = np.array(sct.grab(monitor))

            frame = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

            # 队列只保留最新一帧
            if not frame_queue.empty():
                try:
                    frame_queue.get_nowait()
                except Exception:
                    pass
            frame_queue.put_nowait(frame)

        except Exception as e:
            print(f"[捕获进程错误] {e}")
            time.sleep(0.05)
            continue


def inference_process(frame_queue, running_event):
    # 主进程：YOLO 推理 + Kalman 滤波 + 显示
    print("正在加载 YOLO 模型...")
    model = YOLO("../../models/best 12.10.pt")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"使用设备: {device}")

    # 初始化卡尔曼滤波器
    kalman = cv2.KalmanFilter(4, 2)
    dt = 1
    kalman.transitionMatrix = np.array(
        [[1, 0, dt, 0],
         [0, 1, 0, dt],
         [0, 0, 1, 0],
         [0, 0, 0, 1]], np.float32
    )
    kalman.measurementMatrix = np.array([[1, 0, 0, 0],
                                         [0, 1, 0, 0]], np.float32)
    kalman.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03
    kalman.measurementNoiseCov = np.eye(2, dtype=np.float32) * 10

    last_cx, last_cy = None, None
    direction_change_threshold = 50

    cv2.namedWindow("Head Tracking", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Head Tracking", 854, 500)

    while running_event.is_set():
        try:
            frame = frame_queue.get(timeout=0.1)
        except Exception:
            if cv2.waitKey(1) & 0xFF == ord("q"):
                running_event.clear()
                break
            continue

        annotated_frame = frame.copy()
        results = model(frame)

        if results and len(results) > 0:
            boxes = results[0].boxes
            names = results[0].names
            if boxes is not None and len(boxes) > 0:
                for box in boxes:
                    cls = int(box.cls)
                    label = names.get(cls, "")
                    if "head" in label.lower():
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)

                        # 检测方向突变
                        if last_cx is not None:
                            dx, dy = cx - last_cx, cy - last_cy
                            if np.hypot(dx, dy) > direction_change_threshold:
                                kalman.statePost[2:] = 0
                                print("方向突变，重置速度")

                        last_cx, last_cy = cx, cy

                        # Kalman 更新
                        measurement = np.array([[np.float32(cx)], [np.float32(cy)]])
                        kalman.correct(measurement)
                        prediction = kalman.predict()
                        px, py = int(prediction[0]), int(prediction[1])

                        # 绘制结果
                        cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                        cv2.putText(annotated_frame, "Head", (int(x1), int(y1) - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        cv2.circle(annotated_frame, (px, py), 10, (0, 255, 0), 3)
                        cv2.putText(annotated_frame, "Prediction", (px + 10, py),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        break
        else:
            # 没检测到头，也继续预测
            prediction = kalman.predict()
            px, py = int(prediction[0]), int(prediction[1])
            cv2.circle(annotated_frame, (px, py), 10, (0, 255, 0), 3)
            cv2.putText(annotated_frame, "Predict only", (px + 10, py),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        annotated_frame_resized = cv2.resize(annotated_frame, (854, 480))
        cv2.imshow("Head Tracking", annotated_frame_resized)

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

    frame_queue = mp.Queue(maxsize=1)
    running_event = mp.Event()
    running_event.set()

    p1 = mp.Process(target=capture_process, args=(frame_queue, running_event, choice, all_windows))
    p2 = mp.Process(target=inference_process, args=(frame_queue, running_event))

    p1.start()
    p2.start()

    p1.join()
    p2.join()

    print("程序已退出。")
