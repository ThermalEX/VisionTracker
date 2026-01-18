"""Overlay display module for aim visualization."""

import time
import cv2
import numpy as np
import win32gui
import win32con
import math
from multiprocessing import Process, Queue, Event

from ..utils.config import Config


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

            # Set color key for transparency (black = transparent)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 255, win32con.LWA_COLORKEY)

        last_topmost = time.time()

        while running_event.is_set():
            try:
                data = overlay_queue.get(timeout=0.05)
            except:
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

            # Draw crosshair dots outside ROI
            dot_offset = Config.FOV_WIDTH // 2 + 8
            cv2.circle(overlay, (center_x - dot_offset, center_y), 3, (255, 255, 255), -1)
            cv2.circle(overlay, (center_x + dot_offset, center_y), 3, (255, 255, 255), -1)
            cv2.circle(overlay, (center_x, center_y - dot_offset), 3, (255, 255, 255), -1)
            cv2.circle(overlay, (center_x, center_y + dot_offset), 3, (255, 255, 255), -1)

            # Draw target indicator
            if head_x is not None:
                color = (255, 100, 0) if mode == 'SNAP' else (0, 255, 0)
                dx = head_x - center_x
                dy = head_y - center_y
                dist_to_head = math.sqrt(dx * dx + dy * dy)

                if dist_to_head > 1:
                    dx_norm = dx / dist_to_head
                    dy_norm = dy / dist_to_head
                    start_dist = Config.FOV_WIDTH // 2 + 5
                    end_dist = Config.FOV_WIDTH // 2 + 40

                    start_x = int(center_x + dx_norm * start_dist)
                    start_y = int(center_y + dy_norm * start_dist)
                    end_x = int(center_x + dx_norm * end_dist)
                    end_y = int(center_y + dy_norm * end_dist)

                    cv2.line(overlay, (start_x, start_y), (end_x, end_y), color, 3)

            # Draw status text
            aim_color = (0, 255, 0) if aim_active else (0, 0, 255)
            cv2.putText(overlay, f"FPS:{fps:.0f}", (10, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv2.putText(overlay, f"AIM:{'ON' if aim_active else 'OFF'}", (100, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, aim_color, 2)
            cv2.putText(overlay, f"FIRE:{'ON' if Config.AUTO_CLICK else 'OFF'}", (200, 25),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            mode_color = (255, 100, 0) if mode == 'SNAP' else (0, 255, 0)
            cv2.putText(overlay, f"Mode:{mode}", (10, 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, mode_color, 1)
            cv2.putText(overlay, f"SENS:{sens:.2f} Kp:{kp:.2f}", (10, 75),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

            if conf > 0:
                cv2.putText(overlay, f"Conf:{conf:.2f} Dist:{dist:.0f}px", (10, 100),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

            cv2.imshow(window_name, overlay)

            # Keep window on top
            if time.time() - last_topmost > 3.0:
                if hwnd:
                    try:
                        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE)
                    except:
                        pass
                last_topmost = time.time()

            cv2.waitKey(1)

        cv2.destroyAllWindows()
