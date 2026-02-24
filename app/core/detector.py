"""Object detection module using YOLO."""

import os
import glob
import math
import torch
from ultralytics import YOLO

from utils.config import Config


class Detector:
    """YOLO-based object detector."""

    def __init__(self, model_path: str = None):
        self.model = None
        self.using_tensorrt = False
        self.device = None

        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str):
        """Load a YOLO model from path."""
        if model_path.endswith('.engine'):
            try:
                import tensorrt  # noqa: F401
            except ImportError:
                raise ImportError(
                    "TensorRT is not installed. Cannot load .engine model. "
                    "Please use a .pt model, or install TensorRT."
                )
            self.model = YOLO(model_path)
            self.using_tensorrt = True
        else:
            self.model = YOLO(model_path)
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            self.model.to(self.device)
            self.model.fuse()
            if self.device.type == 'cuda':
                self.model.half()
            self.using_tensorrt = False

        print(f"[Detector] Loaded: {model_path} (TensorRT: {self.using_tensorrt})")

    def detect(self, frame, roi=None):
        """
        Run detection on frame.

        Args:
            frame: Input image (BGR)
            roi: Optional (x1, y1, x2, y2) region of interest

        Returns:
            List of detection boxes
        """
        if self.model is None:
            return []

        # Crop to ROI if specified
        if roi:
            x1, y1, x2, y2 = roi
            crop = frame[y1:y2, x1:x2]
        else:
            crop = frame

        # Run inference
        if self.using_tensorrt:
            results = self.model(crop, conf=Config.CONF_THRESHOLD, verbose=False)
        else:
            results = self.model(crop, conf=Config.CONF_THRESHOLD, imgsz=Config.IMGSZ, verbose=False)

        # Collect all boxes
        boxes = []
        for r in results:
            boxes.extend(r.boxes)

        return boxes

    def detect_target(self, frame):
        """
        Detect and return the nearest head target in frame coordinates.

        Returns:
            (target_x, target_y) or (None, None)
        """
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2

        x1 = max(0, cx - Config.FOV_WIDTH // 2)
        y1 = max(0, cy - Config.FOV_HEIGHT // 2)
        x2 = min(w, cx + Config.FOV_WIDTH // 2)
        y2 = min(h, cy + Config.FOV_HEIGHT // 2)

        boxes = self.detect(frame, roi=(x1, y1, x2, y2))
        target, _ = find_nearest_head(boxes, cx, cy, x1, y1)

        if target:
            return target[0], target[1]  # cx, cy
        return None, None


def find_nearest_head(boxes, center_x, center_y, x1_roi, y1_roi, priority='nearest', target_class_id=None, prefer_class_ids=None):
    """
    Find the nearest head from detection boxes.

    Args:
        boxes: List of detection boxes
        center_x, center_y: Screen center coordinates
        x1_roi, y1_roi: ROI offset
        priority: 'nearest' or 'confidence'
        target_class_id: int / list of ints / None for all classes
        prefer_class_ids: if set, prefer targets with these class IDs (head priority mode)

    Returns:
        (target_info, all_heads) or (None, [])
    """
    heads = []

    for box in boxes:
        cls = int(box.cls[0])
        # Filter by target class ID; None means accept all; list means accept any in list
        if target_class_id is not None:
            ids = target_class_id if isinstance(target_class_id, (list, tuple, set)) else (target_class_id,)
        if target_class_id is not None and cls not in ids:
            continue

        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])

        # Convert to screen coordinates
        real_x1 = bx1 + x1_roi
        real_y1 = by1 + y1_roi
        real_x2 = bx2 + x1_roi
        real_y2 = by2 + y1_roi

        head_cx = (real_x1 + real_x2) // 2
        aim_y_frac = getattr(Config, 'AIM_POINT_Y', 50) / 100.0
        head_cy = real_y1 + int((real_y2 - real_y1) * aim_y_frac)
        head_r = min(real_x2 - real_x1, real_y2 - real_y1) // 2

        dist = math.sqrt((head_cx - center_x) ** 2 + (head_cy - center_y) ** 2)

        heads.append({
            'cx': head_cx,
            'cy': head_cy,
            'r': head_r,
            'dist': dist,
            'conf': conf,
            'cls': cls,
            'bbox': (real_x1, real_y1, real_x2, real_y2)
        })

    if not heads:
        return None, []

    # Sort by priority
    if priority == 'nearest':
        heads.sort(key=lambda h: h['dist'])
    else:
        heads.sort(key=lambda h: -h['conf'])

    # Head priority mode: prefer preferred class IDs; fall back to others if none found
    if prefer_class_ids:
        preferred = [h for h in heads if h['cls'] in prefer_class_ids]
        best = preferred[0] if preferred else heads[0]
    else:
        best = heads[0]
    return (best['cx'], best['cy'], best['r'], best['cls'], best['conf'], best['bbox']), heads


def scan_models(models_dir: str = None) -> list:
    """
    Scan for available models in directory.

    Returns:
        List of {'name': str, 'path': str, 'type': 'pt' or 'engine'}
    """
    if models_dir is None:
        models_dir = os.path.join(os.path.dirname(__file__), '..', 'models')

    models = []

    for pt_file in glob.glob(os.path.join(models_dir, "*.pt")):
        name = os.path.basename(pt_file)
        models.append({'name': name, 'path': pt_file, 'type': 'pt'})

    for engine_file in glob.glob(os.path.join(models_dir, "*.engine")):
        name = os.path.basename(engine_file)
        models.append({'name': name, 'path': engine_file, 'type': 'engine'})

    models.sort(key=lambda m: m['name'])
    return models
