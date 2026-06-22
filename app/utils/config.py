"""Configuration management for Vision Tracker."""


class Config:
    """Global configuration settings."""

    # ROI (Region of Interest) settings
    FOV_WIDTH = 200
    FOV_HEIGHT = 200
    IMGSZ = 200

    # Aim point vertical offset: 0 = top of bbox, 50 = center, 100 = bottom
    AIM_POINT_Y = 50

    # Detection settings
    CONF_THRESHOLD = 0.3

    # Target class setting: int / list of ints / None for all classes
    TARGET_CLASS_ID = None
    # Preferred class IDs: when set, prefer these over other classes (head priority mode)
    PREFER_CLASS_IDS = None

    # Aim settings
    AIM_ENABLED = True
    AIM_KEY = 'caps_lock'  # None for always on

    # Operation mode settings
    AUTO_AIM = True   # Enable auto aim
    AUTO_FIRE = True  # Enable auto fire

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

    # Crosshair settings
    CROSSHAIR_SHOW = True
    CROSSHAIR_LENGTH = 10
    CROSSHAIR_THICKNESS = 2
    CROSSHAIR_GAP = 4
    CROSSHAIR_COLOR = "green"
    CROSSHAIR_CENTER_DOT = True
    CROSSHAIR_DOT_SIZE = 2
    OVERLAY_OPACITY = 100
    OVERLAY_FONT_SIZE = 14

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

    # Controller type: 'pid' or 'adrc'
    CONTROLLER_TYPE = 'adrc'

    # ADRC settings (discrete disturbance estimator)
    ADRC_KP = 0.3    # Proportional gain for ADRC (independent of PID Kp)
    ADRC_B0 = 1.0    # Control effectiveness (pixels of error reduced per mouse unit)
    ADRC_ALPHA = 0.3  # ESO smoothing factor (0~1): higher = faster but noisier

    # Calibration
    CALIBRATE_SAMPLES = 3
