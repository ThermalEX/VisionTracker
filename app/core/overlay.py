"""Overlay display module for aim visualization."""

import time
import cv2
import numpy as np
import win32gui
import win32con
import math
from multiprocessing import Process, Queue, Event

from utils.config import Config

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
            conf = data.get('conf', 0)
            dist = data.get('dist', 0)
            fps = data.get('fps', 0)
            click_radius = data.get('click_radius', Config.CLICK_RADIUS_MIN)
            mode = data.get('mode', 'PID')
            sens = data.get('sens', Config.SNAP_SENSITIVITY)
            kp = data.get('kp', Config.PID_KP)
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

            # Draw status text
            aim_color = (0, 255, 0) if aim_active else (0, 0, 255)
            cv2.putText(overlay, f"FPS:{fps:.0f}", (10, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(overlay, f"AIM:{'ON' if aim_active else 'OFF'}", (100, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, aim_color, 2)
            cv2.putText(overlay, f"FIRE:{'ON' if Config.AUTO_FIRE else 'OFF'}", (200, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            mode_color = (255, 100, 0) if mode == 'SNAP' else (0, 255, 0)
            cv2.putText(overlay, f"Mode:{mode}", (10, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, mode_color, 1)
            cv2.putText(overlay, f"SENS:{sens:.2f} Kp:{kp:.2f}", (10, 75),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            if conf > 0:
                cv2.putText(overlay, f"Conf:{conf:.2f} Dist:{dist:.0f}px", (10, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

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
