import multiprocessing as mp
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import time
import mss
import pygetwindow as gw


# 屏幕捕获进程
def capture_process(frame_queue, running, choice, all_windows):
    import mss, numpy as np, pygetwindow as gw
    sct = mss.mss()

    monitor = None
    if choice == -1:
        monitor = sct.monitors[1]  # 全屏捕获
    else:
        title = all_windows[choice]
        target = gw.getWindowsWithTitle(title)[0]
        monitor = {
            "top": target.top,
            "left": target.left,
            "width": target.width,
            "height": target.height
        }

    while running.value:
        img = np.array(sct.grab(monitor))
        frame = img[..., :3]  # 去掉 alpha 通道
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

        if not frame_queue.full():
            frame_queue.put(frame)
        else:
            # 丢弃旧帧，只保留最新的
            try:
                frame_queue.get_nowait()
                frame_queue.put_nowait(frame)
            except:
                pass
        time.sleep(0.001)


# YOLO 推理进程
def yolo_process(frame_queue, result_queue, running):
    import torch
    from ultralytics import YOLO

    model = YOLO("best.pt")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f"[YOLO] 使用设备: {device}")

    while running.value:
        if not frame_queue.empty():
            frame = frame_queue.get()
            results = model(frame)
            result_queue.put((frame, results))
        else:
            time.sleep(0.001)


# 卡尔曼 + EMA 追踪
class HeadTracker:
    def __init__(self):
        self.kalman = cv2.KalmanFilter(4, 2)
        self.kalman.measurementMatrix = np.array([[1, 0, 0, 0],
                                                  [0, 1, 0, 0]], np.float32)
        self.kalman.transitionMatrix = np.array([[1, 0, 1, 0],
                                                 [0, 1, 0, 1],
                                                 [0, 0, 1, 0],
                                                 [0, 0, 0, 1]], np.float32)
        self.kalman.processNoiseCov = np.eye(4, dtype=np.float32) * 0.01
        self.kalman.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.5

        self.ema_x, self.ema_y = None, None
        self.alpha = 0.6
        self.last_cx, self.last_cy = None, None
        self.direction_threshold = 60

    def update(self, cx, cy):
        # 突变检测
        if self.last_cx is not None:
            dx, dy = cx - self.last_cx, cy - self.last_cy
            if np.hypot(dx, dy) > self.direction_threshold:
                print("方向突变 -> 重置速度")
                self.kalman.statePost[2:] = 0

        self.last_cx, self.last_cy = cx, cy

        m = np.array([[np.float32(cx)], [np.float32(cy)]])
        self.kalman.correct(m)
        p = self.kalman.predict()
        px, py = float(p[0]), float(p[1])

        if self.ema_x is None:
            self.ema_x, self.ema_y = cx, cy
        else:
            self.ema_x = self.alpha * cx + (1 - self.alpha) * self.ema_x
            self.ema_y = self.alpha * cy + (1 - self.alpha) * self.ema_y

        fx = 0.5 * self.ema_x + 0.5 * px
        fy = 0.5 * self.ema_y + 0.5 * py
        return int(fx), int(fy)


# 主进程
if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)

    all_windows = [w for w in gw.getAllTitles() if w.strip()]
    print("可用窗口列表：")
    for i, title in enumerate(all_windows):
        print(f"{i}: {title}")

    choice = int(input("请输入窗口编号（-1 捕获整个桌面）："))

    frame_queue = mp.Queue(maxsize=4)
    result_queue = mp.Queue(maxsize=4)
    running = mp.Value('b', True)

    # 启动子进程
    p1 = mp.Process(target=capture_process, args=(frame_queue, running, choice, all_windows))
    p2 = mp.Process(target=yolo_process, args=(frame_queue, result_queue, running))
    p1.start()
    p2.start()

    tracker = HeadTracker()

    cv2.namedWindow("Head Tracking", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Head Tracking", 854, 480)

    while running.value:
        if not result_queue.empty():
            frame, results = result_queue.get()
            annotated = frame.copy()
            for r in results:
                for box in r.boxes:
                    label = r.names[int(box.cls)]
                    if "head" in label.lower():
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                        fx, fy = tracker.update(cx, cy)

                        # 红框 = 检测，绿点 = 预测
                        cv2.rectangle(annotated, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 2)
                        cv2.circle(annotated, (fx, fy), 6, (0, 255, 0), -1)
                        cv2.putText(annotated, "Head", (int(x1), int(y1) - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                        break

            cv2.imshow("Head Tracking", cv2.resize(annotated, (854, 480)))

        if cv2.waitKey(1) & 0xFF == ord('q'):
            running.value = False
            break

    p1.join()
    p2.join()
    cv2.destroyAllWindows()
    print("程序退出")
