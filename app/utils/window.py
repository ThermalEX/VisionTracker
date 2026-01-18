"""Window utility functions."""

import ctypes
import win32gui


def get_client_rect_screen(hwnd):
    """Get the client area rectangle in screen coordinates."""
    try:
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        pt_min = win32gui.ClientToScreen(hwnd, (0, 0))
        pt_max = win32gui.ClientToScreen(hwnd, (right, bottom))
        return int(pt_min[0]), int(pt_min[1]), int(pt_max[0] - pt_min[0]), int(pt_max[1] - pt_min[1])
    except:
        return None


def check_admin():
    """Check if running with admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def set_dpi_awareness():
    """Set DPI awareness for the process."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        ctypes.windll.user32.SetProcessDPIAware()
