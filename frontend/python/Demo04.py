# use kalman filter and EMA to track head position with ultralytics YOLO model
# 使用卡尔曼滤波和EMA混合版追踪头部位置，结合ultralytics YOLO模型进行检测

import pygetwindow as gw
import pyautogui
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import threading
import queue
import time

# 头部追踪滤波模块（卡尔曼 + EMA 混合版）
class HeadTracker:
    def __init__(self, fps=30, predict_time=0.2):
        self.kalman = cv2.KalmanFilter(4, 2)
        self.kalman.measurementMatrix = np.array([[1, 0, 0, 0],
                                                  [0, 1, 0, 0]], np.float32)
        self.kalman.transitionMatrix = np.array([[1, 0, 1, 0],
                                                 [0, 1, 0, 1],
                                                 [0, 0, 1, 0],
                                                 [0, 0, 0, 1]], np.float32)
        self.kalman.processNoiseCov = np.eye(4, dtype=np.float32) * 0.01
        self.kalman.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.5

        # EMA
        self.ema_alpha = 0.6
        self.ema_x, self.ema_y = None, None

        self.last_cx, self.last_cy = None, None
        self.direction_change_threshold = 50

        self.fps = fps
        self.predict_time = predict_time  # 预测未来时间（秒）
        self.dt = 1.0 / fps

    def update(self, cx, cy):
        measurement = np.array([[np.float32(cx)], [np.float32(cy)]])
        self.kalman.correct(measurement)

        #预测未来 n 帧
        n_steps = max(1, round(self.predict_time / self.dt))
        prediction = self.kalman.predict()
        for _ in range(n_steps - 1):
            prediction = self.kalman.predict()
        px, py = float(prediction[0]), float(prediction[1])

        #EMA快速贴合
        if self.ema_x is None:
            self.ema_x, self.ema_y = cx, cy
        else:
            self.ema_x = self.ema_alpha * cx + (1 - self.ema_alpha) * self.ema_x
            self.ema_y = self.ema_alpha * cy + (1 - self.ema_alpha) * self.ema_y

        #检测方向突变
        if self.last_cx is not None:
            dx, dy = cx - self.last_cx, cy - self.last_cy
            dist = np.hypot(dx, dy)
            if dist > self.direction_change_threshold:
                self.kalman.statePost[2:] = 0
                self.kalman.processNoiseCov = np.eye(4, dtype=np.float32) * 0.1
            else:
                self.kalman.processNoiseCov = np.eye(4, dtype=np.float32) * 0.01

        self.last_cx, self.last_cy = cx, cy

        #融合 Kalman 与 EMA
        blend_ratio = 0.7 if np.hypot(cx - px, cy - py) > 20 else 0.4
        fx = blend_ratio * self.ema_x + (1 - blend_ratio) * px
        fy = blend_ratio * self.ema_y + (1 - blend_ratio) * py

        return int(fx), int(fy)



# 屏幕捕获线程
def capture_thread(frame_queue, running_event, choice, all_windows):
    while running_event.is_set():
        try:
            if choice == -1:
                screenshot = pyautogui.screenshot()
                frame = np.array(screenshot)
            else:
                target_window_title = all_windows[choice]
                target_window = gw.getWindowsWithTitle(target_window_title)[0]
                if target_window:
                    left, top, width, height = target_window.left, target_window.top, target_window.width, target_window.height
                    screenshot = pyautogui.screenshot(region=(left, top, width, height))
                    frame = np.array(screenshot)
                else:
                    time.sleep(0.1)
                    continue

            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass

            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass

        except Exception as e:
            print(f"捕获线程出错: {e}")
            if choice != -1 and not gw.getWindowsWithTitle(all_windows[choice]):
                print(f"窗口 '{all_windows[choice]}' 已关闭。正在退出...")
                running_event.clear()
                break
        time.sleep(0.001)



if __name__ == "__main__":
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
        print("请输入有效编号！")

    print("正在加载 YOLO 模型...")
    model = YOLO("best.pt")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"使用设备: {device}")

    cv2.namedWindow("Window Capture", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Window Capture", 854, 480)

    frame_queue = queue.Queue(maxsize=1)
    running_event = threading.Event()
    running_event.set()

    capture_worker = threading.Thread(
        target=capture_thread,
        args=(frame_queue, running_event, choice, all_windows),
        daemon=True
    )
    capture_worker.start()

    print("捕获线程已启动...")

    tracker = HeadTracker()

    while running_event.is_set():
        try:
            frame = frame_queue.get(timeout=0.1)
        except queue.Empty:
            if cv2.waitKey(1) & 0xFF == ord("q"):
                running_event.clear()
                break
            continue

        results = model(frame)

        annotated_frame = frame.copy()

        for result in results:
            boxes = result.boxes
            names = result.names
            for box in boxes:
                cls_id = int(box.cls)
                label = names[cls_id]
                if "head" in label.lower():
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)

                    # 红框：检测到的头部
                    cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                    cv2.putText(annotated_frame, "Detected", (int(x1), int(y1) - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                    # 绿点：预测点
                    fx, fy = tracker.update(cx, cy)
                    cv2.circle(annotated_frame, (fx, fy), 6, (0, 255, 0), -1)
                    cv2.putText(annotated_frame, "Predicted", (fx + 10, fy),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        annotated_frame_resized = cv2.resize(annotated_frame, (854, 480))
        cv2.imshow("Window Capture", annotated_frame_resized)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            running_event.clear()
            break

    cv2.destroyAllWindows()
    print("程序已退出。")
