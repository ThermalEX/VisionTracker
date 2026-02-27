"""Overlay display module for aim visualization."""

import time
import cv2
import numpy as np
import win32gui
import win32con
import math
from multiprocessing import Process, Queue, Event

from utils.config import Config

try:
    from PIL import ImageFont, ImageDraw, Image as PILImage
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

# YaHei font paths to try (Windows)
_YAHEI_FONT_PATHS = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
]


def _load_yahei(size: int):
    """Load Microsoft YaHei font, fallback to PIL default."""
    if not _PIL_AVAILABLE:
        return None
    for path in _YAHEI_FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def _draw_status(overlay: np.ndarray, fps: float, aim_active: bool,
                 auto_fire: bool, mode: str, conf: float, dist: float,
                 font, font_s) -> np.ndarray:
    """Draw minimalist status overlay using YaHei font via PIL."""
    if not _PIL_AVAILABLE or font is None:
        # Fallback: plain cv2 text
        aim_col = (0, 255, 0) if aim_active else (0, 0, 255)
        cv2.putText(overlay, f"{fps:.0f}fps  {mode}", (12, 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (180, 180, 180), 1)
        cv2.putText(overlay, f"AIM {'ON' if aim_active else 'OFF'}", (12, 44),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, aim_col, 1)
        return overlay

    # Convert BGR numpy → PIL RGB
    pil_img = PILImage.fromarray(overlay[:, :, ::-1])
    draw = ImageDraw.Draw(pil_img)

    x, y = 12, 8
    row_h = 22  # line height

    # Row 1: FPS  MODE
    mode_col = (255, 130, 50) if mode == 'SNAP' else (100, 255, 100)
    draw.text((x, y), f"{fps:.0f} fps", font=font, fill=(180, 180, 180))
    draw.text((x + 72, y), mode, font=font, fill=mode_col)

    # Row 2: AIM●   FIRE●
    y += row_h
    aim_dot = (100, 255, 100) if aim_active else (255, 70, 70)
    fire_dot = (100, 230, 255) if auto_fire else (110, 110, 110)
    draw.text((x, y), "AIM", font=font, fill=(160, 160, 160))
    draw.text((x + 34, y), "●", font=font, fill=aim_dot)
    draw.text((x + 56, y), "FIRE", font=font, fill=(160, 160, 160))
    draw.text((x + 100, y), "●", font=font, fill=fire_dot)

    # Row 3 (only when target locked): conf + dist
    if conf > 0:
        y += row_h
        draw.text((x, y), f"{conf:.2f}  {dist:.0f}px", font=font_s, fill=(170, 100, 210))

    # Convert back to BGR numpy
    return np.array(pil_img)[:, :, ::-1]

# Crosshair color presets (BGR format for OpenCV)
COLOR_MAP = {
    'green': (0, 255, 0),
    'red': (0, 0, 255),
    'yellow': (0, 255, 255),
    'cyan': (255, 255, 0),
    'white': (255, 255, 255),
    'magenta': (255, 0, 255),
}


class OverlayProcess:
    """Overlay window process manager."""

    def __init__(self, overlay_queue: Queue, running_event: Event):
        self.overlay_queue = overlay_queue
        self.running_event = running_event
        self.process = None

    def start(self, win_x: int, win_y: int, win_w: int, win_h: int):
        """Start the overlay process."""
        self.process = Process(
            target=self._overlay_loop,
            args=(self.overlay_queue, self.running_event, win_x, win_y, win_w, win_h)
        )
        self.process.start()

    def stop(self):
        """Stop the overlay process."""
        if self.process:
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()

    @staticmethod
    def _overlay_loop(overlay_queue: Queue, running_event: Event,
                      win_x: int, win_y: int, win_w: int, win_h: int):
        """Main overlay loop (runs in separate process)."""
        window_name = "Overlay"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        # Load fonts for status text (once per process)
        _font = _load_yahei(14)
        _font_s = _load_yahei(12)

        # Create dummy window first
        dummy = np.zeros((win_h, win_w, 3), dtype=np.uint8)
        cv2.imshow(window_name, dummy)
        cv2.waitKey(1)
        time.sleep(0.05)

        # Configure window as transparent overlay
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd:
            # Remove window decorations
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME |
                      win32con.WS_MINIMIZE | win32con.WS_MAXIMIZE |
                      win32con.WS_SYSMENU | win32con.WS_BORDER)
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

            # Set extended styles for transparency and click-through
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT |
                win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE)

            # Position window
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST,
                win_x, win_y, win_w, win_h,
                win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)

            # Set color key + alpha for transparency (black = transparent, alpha = opacity)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_COLORKEY | win32con.LWA_ALPHA)

        while running_event.is_set():
            try:
                data = overlay_queue.get(timeout=0.05)
            except:
                # Re-assert topmost while idle so the window doesn't get buried
                if hwnd:
                    try:
                        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                    except Exception:
                        pass
                cv2.waitKey(1)
                continue

            overlay = np.zeros((win_h, win_w, 3), dtype=np.uint8)

            # Extract data
            x1_roi, y1_roi, x2_roi, y2_roi = data.get('roi', (0, 0, 0, 0))
            center_x, center_y = data.get('center', (win_w // 2, win_h // 2))
            head_x, head_y = data.get('head', (None, None))
            aim_active = data.get('aim_active', False)
            auto_fire = data.get('auto_fire', False)
            conf = data.get('conf', 0)
            dist = data.get('dist', 0)
            fps = data.get('fps', 0)
            click_radius = data.get('click_radius', Config.CLICK_RADIUS_MIN)
            mode = data.get('mode', 'PID')
            calibrating = data.get('calibrating', False)
            calib_move = data.get('calib_move', None)  # (dx, dy) for calibration move line
            show_bbox = data.get('show_bbox', False)
            boxes = data.get('boxes', [])

            # Update overlay window opacity dynamically
            overlay_opacity = int(data.get('overlay_opacity', 100) * 255 / 100)
            if hwnd:
                try:
                    win32gui.SetLayeredWindowAttributes(
                        hwnd, 0, overlay_opacity, win32con.LWA_COLORKEY | win32con.LWA_ALPHA)
                except Exception:
                    pass

            # Draw detection boxes if enabled
            if show_bbox and boxes:
                for box in boxes:
                    bbox = box.get('bbox')
                    if bbox:
                        bx1, by1, bx2, by2 = bbox
                        cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (0, 100, 0), 1)

            # Draw ROI corners
            corner_len = 30
            corner_thick = 1
            # Top-left
            cv2.line(overlay, (x1_roi, y1_roi), (x1_roi + corner_len, y1_roi), (255, 255, 255), corner_thick)
            cv2.line(overlay, (x1_roi, y1_roi), (x1_roi, y1_roi + corner_len), (255, 255, 255), corner_thick)
            # Top-right
            cv2.line(overlay, (x2_roi, y1_roi), (x2_roi - corner_len, y1_roi), (255, 255, 255), corner_thick)
            cv2.line(overlay, (x2_roi, y1_roi), (x2_roi, y1_roi + corner_len), (255, 255, 255), corner_thick)
            # Bottom-left
            cv2.line(overlay, (x1_roi, y2_roi), (x1_roi + corner_len, y2_roi), (255, 255, 255), corner_thick)
            cv2.line(overlay, (x1_roi, y2_roi), (x1_roi, y2_roi - corner_len), (255, 255, 255), corner_thick)
            # Bottom-right
            cv2.line(overlay, (x2_roi, y2_roi), (x2_roi - corner_len, y2_roi), (255, 255, 255), corner_thick)
            cv2.line(overlay, (x2_roi, y2_roi), (x2_roi, y2_roi - corner_len), (255, 255, 255), corner_thick)

            # Draw crosshair
            if data.get('crosshair_show', False):
                ch_len = data.get('crosshair_length', 10)
                ch_thick = data.get('crosshair_thickness', 2)
                ch_gap = data.get('crosshair_gap', 4)
                ch_color = COLOR_MAP.get(data.get('crosshair_color', 'green'), (0, 255, 0))
                cx, cy = center_x, center_y

                cv2.line(overlay, (cx, cy - ch_gap - ch_len), (cx, cy - ch_gap), ch_color, ch_thick)
                cv2.line(overlay, (cx, cy + ch_gap), (cx, cy + ch_gap + ch_len), ch_color, ch_thick)
                cv2.line(overlay, (cx - ch_gap - ch_len, cy), (cx - ch_gap, cy), ch_color, ch_thick)
                cv2.line(overlay, (cx + ch_gap, cy), (cx + ch_gap + ch_len, cy), ch_color, ch_thick)

                if data.get('crosshair_center_dot', True):
                    dot_size = data.get('crosshair_dot_size', 2)
                    cv2.circle(overlay, (cx, cy), dot_size, ch_color, -1)

            # Calculate diagonal radius from ROI (so line is always outside the box)
            fov_half_w = (x2_roi - x1_roi) // 2
            fov_half_h = (y2_roi - y1_roi) // 2
            fov_diagonal = math.sqrt(fov_half_w * fov_half_w + fov_half_h * fov_half_h)

            # Draw target indicator
            if head_x is not None:
                color = (255, 100, 0) if mode == 'SNAP' else (0, 255, 0)
                dx = head_x - center_x
                dy = head_y - center_y
                dist_to_head = math.sqrt(dx * dx + dy * dy)

                if dist_to_head > 1:
                    dx_norm = dx / dist_to_head
                    dy_norm = dy / dist_to_head

                    # Line always starts outside the box (using diagonal)
                    start_dist = fov_diagonal + 5
                    end_dist = start_dist + 35

                    start_x = int(center_x + dx_norm * start_dist)
                    start_y = int(center_y + dy_norm * start_dist)
                    end_x = int(center_x + dx_norm * end_dist)
                    end_y = int(center_y + dy_norm * end_dist)

                    cv2.line(overlay, (start_x, start_y), (end_x, end_y), color, 3)

            # Draw calibration move line (yellow)
            if calibrating and calib_move is not None:
                calib_dx, calib_dy = calib_move
                calib_dist = math.sqrt(calib_dx * calib_dx + calib_dy * calib_dy)
                if calib_dist > 1:
                    calib_dx_norm = calib_dx / calib_dist
                    calib_dy_norm = calib_dy / calib_dist

                    # Line always starts outside the box (using diagonal)
                    start_dist = fov_diagonal + 5
                    end_dist = start_dist + 35

                    calib_start_x = int(center_x + calib_dx_norm * start_dist)
                    calib_start_y = int(center_y + calib_dy_norm * start_dist)
                    calib_end_x = int(center_x + calib_dx_norm * end_dist)
                    calib_end_y = int(center_y + calib_dy_norm * end_dist)

                    cv2.line(overlay, (calib_start_x, calib_start_y), (calib_end_x, calib_end_y), (0, 255, 255), 3)

            # Draw minimalist status text (YaHei font via PIL)
            overlay = _draw_status(overlay, fps, aim_active, auto_fire,
                                   mode, conf, dist, _font, _font_s)

            # Re-assert topmost every frame so full-screen apps can't bury the overlay
            if hwnd:
                try:
                    win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                except Exception:
                    pass

            cv2.imshow(window_name, overlay)
            cv2.waitKey(1)

        cv2.destroyAllWindows()
