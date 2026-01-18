"""Configuration management for Vision Tracker."""


class Config:
    """Global configuration settings."""

    # ROI (Region of Interest) settings
    FOV_WIDTH = 200
    FOV_HEIGHT = 200
    IMGSZ = 200

    # Detection settings
    CONF_THRESHOLD = 0.3

    # Aim settings
    AIM_ENABLED = True
    AIM_KEY = 'caps_lock'  # None for always on

    # Auto fire settings
    AUTO_CLICK = True
    CLICK_INTERVAL = 0.2  # seconds
    CLICK_RADIUS_RATIO = 1.1  # fire range = head radius * ratio
    CLICK_RADIUS_MIN = 5  # min fire range (pixels)
    CLICK_RADIUS_MAX = 50  # max fire range (pixels)

    # Target selection
    TARGET_PRIORITY = 'nearest'  # 'nearest' or 'confidence'

    # Display settings
    SHOW_OVERLAY = True
    SHOW_BBOX = True

    # Snap (teleport) settings
    SNAP_THRESHOLD = 40  # use snap when error > this (pixels)
    SNAP_SENSITIVITY = 2.2  # calibrated value
    SNAP_COOLDOWN = 0.2  # seconds after snap
    SNAP_UPDATE_THRESHOLD = 20  # error change threshold

    # PID settings
    PID_KP = 0.3
    PID_KI = 0.0
    PID_KD = 0.001
    PID_COOLDOWN = 0.05
    PID_ERROR_THRESHOLD = 3
    DEADZONE = 0

    # Calibration
    CALIBRATE_SAMPLES = 3
