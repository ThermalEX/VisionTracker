"""Screen capture module."""

import time
import cv2
import numpy as np
import mss
import pygetwindow as gw
from multiprocessing import Process, Queue, Event

from utils.window import get_client_rect_screen


class CaptureProcess:
    """Screen capture process manager."""

    def __init__(self, frame_queue: Queue, running_event: Event):
        self.frame_queue = frame_queue
        self.running_event = running_event
        self.process = None

    def start(self, window_choice: int, all_windows: list):
        """Start the capture process."""
        self.process = Process(
            target=self._capture_loop,
            args=(self.frame_queue, self.running_event, window_choice, all_windows)
        )
        self.process.start()

    def stop(self):
        """Stop the capture process."""
        if self.process:
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()

    @staticmethod
    def _capture_loop(frame_queue: Queue, running_event: Event, choice: int, all_windows: list):
        """Main capture loop (runs in separate process)."""
        target_window_title = None
        monitor = {}

        if choice == -1:
            # Fullscreen mode
            with mss.mss() as sct:
                monitor = sct.monitors[1]
        else:
            # Window mode
            target_window_title = all_windows[choice]
            target_window = gw.getWindowsWithTitle(target_window_title)[0]
            rect = get_client_rect_screen(target_window._hWnd)
            if rect:
                monitor = {"left": rect[0], "top": rect[1], "width": rect[2], "height": rect[3]}
            else:
                monitor = {
                    "top": target_window.top,
                    "left": target_window.left,
                    "width": target_window.width,
                    "height": target_window.height
                }

        with mss.mss() as sct:
            while running_event.is_set():
                try:
                    # Update window position if in window mode
                    if choice != -1:
                        target_window = gw.getWindowsWithTitle(target_window_title)[0]
                        if not target_window:
                            break
                        rect = get_client_rect_screen(target_window._hWnd)
                        if rect:
                            monitor["left"], monitor["top"], monitor["width"], monitor["height"] = rect
                        if monitor["width"] <= 0 or monitor["height"] <= 0:
                            time.sleep(0.1)
                            continue

                    # Capture frame
                    sct_img = sct.grab(monitor)
                    frame = cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR)

                    # Clear old frames and put new one
                    while not frame_queue.empty():
                        try:
                            frame_queue.get_nowait()
                        except:
                            break
                    try:
                        frame_queue.put_nowait(frame)
                    except:
                        pass
                except Exception:
                    time.sleep(0.1)


def get_available_windows() -> list:
    """Get list of available window titles."""
    return [w for w in gw.getAllTitles() if w.strip()]
