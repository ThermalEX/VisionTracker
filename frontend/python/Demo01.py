import pygetwindow as gw
import pyautogui
import cv2
import numpy as np
import torch
from ultralytics import YOLO

# 列出所有窗口标题
all_windows = gw.getAllTitles()
all_windows = [win for win in all_windows if win.strip()]  # 去除空标题
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

model = YOLO("best.pt")
device = torch.device('cuda')
model.to(device)
cv2.namedWindow("Window Capture", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Window Capture", 854, 500)

while True:
    if choice == -1:
        # 捕获整个屏幕
        screenshot = pyautogui.screenshot()
        frame = np.array(screenshot)
    else:
        # 捕获指定窗口
        target_window_title = all_windows[choice]
        target_window = gw.getWindowsWithTitle(target_window_title)[0]
        left, top, width, height = target_window.left, target_window.top, target_window.width, target_window.height
        screenshot = pyautogui.screenshot(region=(left, top, width, height))
        frame = np.array(screenshot)

    # 将 RGB 格式转换为 BGR 格式（OpenCV 默认使用 BGR）
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # 使用 YOLO 进行推理
    results = model(frame)

    # 获取推理结果并渲染边界框
    if isinstance(results, list) and len(results) > 0:
        annotated_frame = results[0].plot()  # 使用 plot() 获取带标注的图像
    else:
        annotated_frame = frame  # 如果没有检测到物体，使用原图像

    annotated_frame_resized = cv2.resize(annotated_frame, (854, 480))

    # 显示标注结果
    cv2.imshow("Window Capture", annotated_frame_resized)

    # 按下 'q' 键退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
