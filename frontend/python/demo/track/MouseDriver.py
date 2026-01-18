"""
MouseDriver - 鼠标控制模块
封装 MouseControl.dll 的调用，提供简单的鼠标移动和点击接口
"""
import os
import ctypes
import time

# DPI 感知设置
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except:
        pass


class MouseDriver:
    """鼠标控制驱动"""

    def __init__(self, dll_path=None):
        """
        初始化鼠标驱动

        Args:
            dll_path: MouseControl.dll 的路径，默认为当前目录
        """
        self.dll = None
        self.loaded = False

        if dll_path is None:
            dll_path = os.path.join(os.path.dirname(__file__),
                                    "MouseControl.dll")

        if not os.path.exists(dll_path):
            print(f"[MouseDriver] ERROR: {dll_path} not found")
            return

        try:
            self.dll = ctypes.CDLL(dll_path)
            self.loaded = True
            print(f"[MouseDriver] Loaded: {dll_path}")
        except Exception as e:
            print(f"[MouseDriver] Failed to load: {e}")

    def is_loaded(self):
        """检查驱动是否加载成功"""
        return self.loaded and self.dll is not None

    # ==================== 鼠标移动 ====================

    def move(self, dx, dy):
        """
        相对移动鼠标

        Args:
            dx: X方向移动量（正=右，负=左）
            dy: Y方向移动量（正=下，负=上）

        Returns:
            bool: 是否成功
        """
        if not self.is_loaded():
            return False
        try:
            self.dll.move_R(int(dx), int(dy))
            return True
        except Exception as e:
            print(f"[MouseDriver] move error: {e}")
            return False

    def move_to(self, x, y):
        """
        移动鼠标到绝对位置

        Args:
            x: 目标X坐标
            y: 目标Y坐标

        Returns:
            bool: 是否成功
        """
        if not self.is_loaded():
            return False
        try:
            self.dll.move_Abs(int(x), int(y))
            return True
        except Exception as e:
            print(f"[MouseDriver] move_to error: {e}")
            return False

    # ==================== 鼠标点击 ====================

    def click_left(self, duration=0.01):
        """
        左键单击

        Args:
            duration: 按下持续时间（秒）

        Returns:
            bool: 是否成功
        """
        if not self.is_loaded():
            return False
        try:
            self.dll.click_Left_down()
            time.sleep(duration)
            self.dll.click_Left_up()
            return True
        except Exception as e:
            print(f"[MouseDriver] click_left error: {e}")
            return False

    def left_down(self):
        """左键按下"""
        if not self.is_loaded():
            return False
        try:
            self.dll.click_Left_down()
            return True
        except:
            return False

    def left_up(self):
        """左键释放"""
        if not self.is_loaded():
            return False
        try:
            self.dll.click_Left_up()
            return True
        except:
            return False

    def click_right(self, duration=0.01):
        """
        右键单击

        Args:
            duration: 按下持续时间（秒）

        Returns:
            bool: 是否成功
        """
        if not self.is_loaded():
            return False
        try:
            self.dll.click_Right_down()
            time.sleep(duration)
            self.dll.click_Right_up()
            return True
        except Exception as e:
            print(f"[MouseDriver] click_right error: {e}")
            return False

    def right_down(self):
        """右键按下"""
        if not self.is_loaded():
            return False
        try:
            self.dll.click_Right_down()
            return True
        except:
            return False

    def right_up(self):
        """右键释放"""
        if not self.is_loaded():
            return False
        try:
            self.dll.click_Right_up()
            return True
        except:
            return False


# 全局实例（方便直接导入使用）
_default_driver = None

def get_driver():
    """获取默认的鼠标驱动实例"""
    global _default_driver
    if _default_driver is None:
        _default_driver = MouseDriver()
    return _default_driver


# ==================== 便捷函数 ====================

def move(dx, dy):
    """相对移动鼠标"""
    return get_driver().move(dx, dy)

def move_to(x, y):
    """移动鼠标到绝对位置"""
    return get_driver().move_to(x, y)

def click_left(duration=0.01):
    """左键单击"""
    return get_driver().click_left(duration)

def click_right(duration=0.01):
    """右键单击"""
    return get_driver().click_right(duration)

def left_down():
    """左键按下"""
    return get_driver().left_down()

def left_up():
    """左键释放"""
    return get_driver().left_up()

def right_down():
    """右键按下"""
    return get_driver().right_down()

def right_up():
    """右键释放"""
    return get_driver().right_up()


# ==================== 测试 ====================

if __name__ == '__main__':
    print("=== MouseDriver 测试 ===")

    driver = MouseDriver()

    if driver.is_loaded():
        print("驱动加载成功")
        print("3秒后测试移动...")
        time.sleep(3)

        # 测试移动
        print("向右移动50像素")
        driver.move(50, 0)
        time.sleep(0.5)

        print("向左移动50像素")
        driver.move(-50, 0)
        time.sleep(0.5)

        print("测试完成")
    else:
        print("驱动加载失败")
