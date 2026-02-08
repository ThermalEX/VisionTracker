"""Video overlay module for playing intro video on game window."""

import os
import time
import cv2
import numpy as np
import win32gui
import win32con
import win32api
from multiprocessing import Process, Event


class VideoOverlay:
    """Play a video overlay on top of the game window."""

    def __init__(self, video_path: str):
        self.video_path = video_path
        self.process = None
        self._finished_event = Event()

    def play(self, win_x: int, win_y: int, win_w: int, win_h: int):
        """Start playing the video overlay."""
        if not os.path.exists(self.video_path):
            return False

        self._finished_event.clear()
        self.process = Process(
            target=self._video_loop,
            args=(self.video_path, self._finished_event, win_x, win_y, win_w, win_h)
        )
        self.process.start()
        return True

    def wait(self, timeout: float = None):
        """Wait for video to finish."""
        if self.process:
            self.process.join(timeout=timeout)

    def is_playing(self) -> bool:
        """Check if video is still playing."""
        return self.process is not None and self.process.is_alive()

    def stop(self):
        """Force stop the video."""
        self._finished_event.set()
        if self.process:
            self.process.join(timeout=1)
            if self.process.is_alive():
                self.process.terminate()

    @staticmethod
    def _video_loop(video_path: str, finished_event: Event,
                    win_x: int, win_y: int, win_w: int, win_h: int):
        """Video playback loop (runs in separate process)."""
        window_name = "IntroVideo"

        # Open video file
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            finished_event.set()
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_delay = 1.0 / fps

        # Create window
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

        # Show first frame to get window handle
        ret, frame = cap.read()
        if not ret:
            cap.release()
            finished_event.set()
            return

        # Resize frame to window size
        frame = cv2.resize(frame, (win_w, win_h))
        cv2.imshow(window_name, frame)
        cv2.waitKey(1)
        time.sleep(0.05)

        # Configure window
        hwnd = win32gui.FindWindow(None, window_name)
        if hwnd:
            # Remove window decorations
            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
            style &= ~(win32con.WS_CAPTION | win32con.WS_THICKFRAME |
                       win32con.WS_MINIMIZE | win32con.WS_MAXIMIZE |
                       win32con.WS_SYSMENU | win32con.WS_BORDER)
            win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)

            # Set extended styles (topmost, layered for transparency)
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                                   ex_style | win32con.WS_EX_TOPMOST | win32con.WS_EX_NOACTIVATE | win32con.WS_EX_LAYERED)

            # Set window transparency (0=transparent, 255=opaque)
            win32gui.SetLayeredWindowAttributes(hwnd, 0, 180, win32con.LWA_ALPHA)

            # Position window
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST,
                                  win_x, win_y, win_w, win_h,
                                  win32con.SWP_FRAMECHANGED | win32con.SWP_SHOWWINDOW)

        # Reset to beginning
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # Hide cursor during video playback
        win32api.ShowCursor(False)

        # Playback loop
        while not finished_event.is_set():
            start_time = time.time()

            ret, frame = cap.read()
            if not ret:
                break  # Video ended

            # Resize and display
            frame = cv2.resize(frame, (win_w, win_h))
            cv2.imshow(window_name, frame)

            # Check for skip (any key or mouse click)
            key = cv2.waitKey(1) & 0xFF
            if key != 255:  # Any key pressed
                break

            # Frame rate control
            elapsed = time.time() - start_time
            sleep_time = frame_delay - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Cleanup
        win32api.ShowCursor(True)  # Restore cursor
        cap.release()
        cv2.destroyWindow(window_name)
        finished_event.set()
