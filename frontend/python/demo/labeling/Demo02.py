# use multithreading for screen capture and YOLO inference
# 使用多线程进行屏幕捕获和YOLO推理

import pygetwindow as gw
import pyautogui
import cv2
import numpy as np
import torch
from ultralytics import YOLO
import threading  # 导入线程库
import queue  # 导入队列库
import time  # 导入时间库


# 生产者：屏幕捕获线程
# 这个函数将在一个单独的线程中运行
def capture_thread(frame_queue,
                   running_event,
                   choice,
                   all_windows):

    # 该函数不断捕获屏幕/窗口，并将最新帧放入队列中

    while running_event.is_set():
        try:
            if choice == -1:
                # 捕获整个屏幕
                screenshot = pyautogui.screenshot()
                frame = np.array(screenshot)
            else:
                # 捕获指定窗口
                target_window_title = all_windows[choice]
                # 重新获取窗口对象，以防窗口大小/位置变化
                target_window = gw.getWindowsWithTitle(target_window_title)[0]
                if target_window:
                    left, top, width, height = target_window.left, target_window.top, target_window.width, target_window.height
                    screenshot = pyautogui.screenshot(region=(left, top, width, height))
                    frame = np.array(screenshot)
                else:
                    # 如果窗口找不到了，就跳过
                    time.sleep(0.1)
                    continue

            # 将 RGB 格式转换为 BGR 格式（OpenCV 默认使用 BGR）
            frame = cv2.cvtColor(frame,
                                 cv2.COLOR_RGB2BGR)

            # 关键的队列操作
            # 队列中只保留最新的一帧
            # 1. 尝试清空队列（如果里面有旧帧）
            try:
                frame_queue.get_nowait()
            except queue.Empty:
                pass  # 队列本来就是空的，很好

            # 2. 尝试放入最新帧
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                pass  # 队列满了（不应该发生，因为我们刚清空了）

        except Exception as e:
            print(f"捕获线程出错: {e}")
            # 可能是窗口被关闭了
            if choice != -1 and not gw.getWindowsWithTitle(all_windows[choice]):
                print(f"窗口 '{all_windows[choice]}' 已关闭。正在退出...")
                running_event.clear()  # 通知主线程也退出
                break

        # 稍微暂停，避免CPU占用率过高
        time.sleep(0.001)

    # 2. 消费者：主线程设置


# 列出所有窗口标题
all_windows = gw.getAllTitles()
all_windows = [win for win in all_windows if win.strip()]  # 去除空标题

# 显示所有窗口标题
print("可用窗口列表：")
for i, title in enumerate(all_windows):
    print(f"{i}: {title}")

# 提示用户输入数字选择窗口
while True:
    try:
        choice = int(input("请输入窗口编号（或输入 -1 捕获整个桌面）："))
        if -1 <= choice < len(all_windows):
            break
        else:
            print("请输入有效编号！")
    except ValueError:
        print("请输入数字！")

# 初始化 YOLO 模型
print("正在加载 YOLO 模型...")
model = YOLO("../../models/best 12.10.pt")
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
print(f"使用设备: {device}")
model.to(device)

# 创建OpenCV窗口用于显示视频流
cv2.namedWindow("Window Capture",
                cv2.WINDOW_NORMAL)
cv2.resizeWindow("Window Capture",
                 854,
                 500)

# 3. 创建线程和队列

# maxsize=1 确保队列中最多只有一帧。
# 这可以防止"消费者"（YOLO）处理过时的帧，减少延迟。
frame_queue = queue.Queue(maxsize=1)

# 使用 Event 来安全地通知线程停止
running_event = threading.Event()
running_event.set()  # 设置 Event 为 "运行中" 状态

# 创建并启动捕获线程
# daemon=True 意味着当主线程退出时，这个线程也会自动退出
capture_worker = threading.Thread(
    target=capture_thread,
    args=(frame_queue, running_event, choice, all_windows),
    daemon=True
)
capture_worker.start()
print("捕获线程已启动...")

# 4. 主线程（消费者）循环
# 主线程现在只负责获取帧、推理和显示

while running_event.is_set():  # 循环直到 'q' 被按下或捕获线程出错
    try:
        # 尝试从队列中获取一帧，设置一个短超时
        # 这样即使没有新帧，循环也能继续并响应 'q' 键
        frame = frame_queue.get(timeout=0.1)
    except queue.Empty:
        # 队列中没有新帧，继续循环，等待 'q' 键
        if cv2.waitKey(1) & 0xFF == ord('q'):
            running_event.clear()  # 通知捕获线程停止
            break
        continue

    # 开始推理
    # 此时，捕获线程可能已经在抓取下一帧了
    results = model(frame)

    # 获取推理结果并渲染边界框
    if isinstance(results,
                  list) and len(results) > 0:
        annotated_frame = results[0].plot()  # 使用 plot() 获取带标注的图像
    else:
        annotated_frame = frame  # 如果没有检测到物体，使用原图像

    # 将标注后的画面缩放为 854x480
    annotated_frame_resized = cv2.resize(annotated_frame,
                                         (854, 480))

    # 显示标注结果
    cv2.imshow("Window Capture",
               annotated_frame_resized)

    # 按下 'q' 键退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        running_event.clear()  # 通知捕获线程停止
        break

# 释放资源
cv2.destroyAllWindows()
print("程序已退出。")