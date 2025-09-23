import pygetwindow as gw
import pyautogui
import time
import os
import keyboard
from datetime import datetime

# 设置固定的保存路径
save_dir = "data/train/images"
os.makedirs(save_dir, exist_ok=True)  # 如果文件夹不存在，则创建

print(f"截图将保存到：{save_dir}")

# 列出所有窗口标题
all_windows = gw.getAllTitles()
all_windows = [win for win in all_windows if win.strip()]  # 去除空标题

# 显示所有窗口标题
print("可用窗口列表：")
for i, title in enumerate(all_windows):
    print(f"{i}: {title}")

# 选择窗口
while True:
    try:
        choice = int(input("请输入窗口编号（或输入 -1 捕获整个桌面）："))
        if -1 <= choice < len(all_windows):
            break
        else:
            print("请输入有效编号！")
    except ValueError:
        print("请输入数字！")

print("截图程序已启动，按 P 键截取图片，按 Ctrl+Q 退出程序")

p_pressed = False  # 用于防止重复触发

while True:
    if keyboard.is_pressed("ctrl+q"):  # 监听 Ctrl+Q 退出
        print("检测到 Ctrl+Q，程序已终止。")
        break

    # 检测 P 键按下
    if keyboard.is_pressed("p") and not p_pressed:
        p_pressed = True  # 标记为已按下，防止重复触发

        # 生成时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(save_dir, f"screenshot_{timestamp}.png")

        if choice == -1:
            screenshot = pyautogui.screenshot()
        else:
            window = gw.getWindowsWithTitle(all_windows[choice])[0]
            x, y, width, height = window.left, window.top, window.width, window.height
            screenshot = pyautogui.screenshot(region=(x, y, width, height))

        screenshot.save(filename)
        print(f"截图已保存：{filename}")

    # 检测 P 键释放
    elif not keyboard.is_pressed("p") and p_pressed:
        p_pressed = False  # 重置状态，允许下次按键触发

    time.sleep(0.1)  # 减少CPU占用
