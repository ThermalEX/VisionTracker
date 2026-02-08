# Lazy imports to avoid PyTorch/PyQt5 DLL conflicts
# Import only what's needed at module level
from core.capture import CaptureProcess, get_available_windows

# These will be imported when needed:
# from core.detector import Detector, find_nearest_head
# from core.tracker import PIDController, AimController
# from core.overlay import OverlayProcess
# from core.tracker_manager import TrackerManager
