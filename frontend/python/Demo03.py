# use kalman filter to track head position with ultralytics YOLO model
# 使用卡尔曼滤波追踪头部位置，结合ultralytics YOLO模型进行检测

import pygetwindow as gw
import pyautogui
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import threading
import queue
import time

# 1. 捕获线程
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
            frame_queue.put_nowait(frame)

        except Exception as e:
            print(f"捕获线程出错: {e}")
            if choice != -1 and not gw.getWindowsWithTitle(all_windows[choice]):
                print(f"窗口 '{all_windows[choice]}' 已关闭。正在退出...")
                running_event.clear()
                break
        time.sleep(0.001)

# 2. 初始化窗口选择
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
    except ValueError:
        pass
    print("请输入有效编号！")

# 3. 初始化 YOLO 模型
print("正在加载 YOLO 模型...")
model = YOLO("best.pt")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model.to(device)
print(f"使用设备: {device}")

cv2.namedWindow("Head Tracking", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Head Tracking", 854, 500)

# 4. 创建捕获线程
frame_queue = queue.Queue(maxsize=1)
running_event = threading.Event()
running_event.set()
capture_worker = threading.Thread(target=capture_thread, args=(frame_queue, running_event, choice, all_windows), daemon=True)
capture_worker.start()
print("捕获线程已启动...")

# 5. 卡尔曼滤波器初始化
kalman = cv2.KalmanFilter(4, 2)
dt = 1
kalman.transitionMatrix = np.array([[1, 0, dt, 0],
                                    [0, 1, 0, dt],
                                    [0, 0, 1, 0],
                                    [0, 0, 0, 1]], np.float32)
kalman.measurementMatrix = np.array([[1, 0, 0, 0],
                                     [0, 1, 0, 0]], np.float32)
kalman.processNoiseCov = np.eye(4, dtype=np.float32) * 0.03
kalman.measurementNoiseCov = np.eye(2, dtype=np.float32) * 10

# 6. 主线程（检测 + 预测 + 显示）
while running_event.is_set():
    try:
        frame = frame_queue.get(timeout=0.1)
    except queue.Empty:
        if cv2.waitKey(1) & 0xFF == ord('q'):
            running_event.clear()
            break
        continue

    results = model(frame)
    annotated_frame = frame.copy()

    # 只检测头部（假设类别名中有 "head"）
    if results and len(results) > 0:
        boxes = results[0].boxes
        names = results[0].names
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                cls = int(box.cls)
                label = names.get(cls, "")
                # 保存上一次中心点，用于检测方向变化
                last_cx, last_cy = None, None
                direction_change_threshold = 50  # 方向变化阈值，像素距离可调

                # 每次检测到头部时：
                if "head" in label.lower():
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)

                    # 检测方向变化
                    if last_cx is not None and last_cy is not None:
                        dx = cx - last_cx
                        dy = cy - last_cy

                        # 如果方向突变（速度方向反转或移动方向突变）
                        if np.hypot(dx,
                                    dy) > direction_change_threshold:
                            print("检测到方向突变，重置速度")
                            kalman.statePost[2] = 0  # vx 清零
                            kalman.statePost[3] = 0  # vy 清零

                    last_cx, last_cy = cx, cy

                    # 正常卡尔曼更新
                    measurement = np.array([[np.float32(cx)], [np.float32(cy)]])
                    kalman.correct(measurement)
                    prediction = kalman.predict()
                    px, py = int(prediction[0]), int(prediction[1])

                    # 红框：YOLO检测头部
                    cv2.rectangle(annotated_frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                    cv2.putText(annotated_frame, "Head", (int(x1), int(y1) - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

                    # 绿点：预测位置
                    cv2.circle(annotated_frame, (px, py), 10, (0, 255, 0), 3)
                    cv2.putText(annotated_frame, "Prediction", (px + 10, py),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    break  # 只显示一个头
    else:
        # 没检测到头，也继续预测
        prediction = kalman.predict()
        px, py = int(prediction[0]), int(prediction[1])
        cv2.circle(annotated_frame, (px, py), 10, (0, 255, 0), 3)
        cv2.putText(annotated_frame, "Predict only", (px + 10, py),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    annotated_frame_resized = cv2.resize(annotated_frame, (854, 480))
    cv2.imshow("Head Tracking", annotated_frame_resized)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        running_event.clear()
        break

cv2.destroyAllWindows()
print("程序已退出。")
