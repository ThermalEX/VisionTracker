import argparse
import random
import sys
from pathlib import Path

import cv2
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
TRAIN_DIR = SCRIPT_DIR.parent
PROJECT_ROOT = TRAIN_DIR.parent.parent.parent

if str(TRAIN_DIR) not in sys.path:
    sys.path.insert(0, str(TRAIN_DIR))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from config import TrainConfig
from my_augment import create_augment_pipeline


CLASS_NAMES = ["ct_head", "ct_body", "t_head", "t_body"]
BOX_COLORS = [
    (72, 220, 120),
    (60, 200, 255),
    (90, 120, 255),
    (220, 110, 255),
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Show one original image and two augmented versions in a single window."
    )
    parser.add_argument(
        "--image",
        type=Path,
        help="Path to the source image. If omitted, the script tries to find a training preview image.",
    )
    parser.add_argument(
        "--label",
        type=Path,
        help="Optional YOLO label file for drawing boxes.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "augmentation_triptych.jpg",
        help="Where to save the combined image.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=640,
        help="Image size used for each panel.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional random seed for repeatable previews.",
    )
    parser.add_argument(
        "--project-settings",
        action="store_true",
        help="Use the normal training probabilities. By default the preview forces visible augmentation.",
    )
    parser.add_argument(
        "--no-boxes",
        action="store_true",
        help="Do not draw YOLO boxes even if a label file is provided.",
    )
    return parser.parse_args()


def find_default_image():
    candidates = [
        Path(r"E:\cs2 dataset\images\train"),
        PROJECT_ROOT / "app" / "models" / "user",
    ]

    for directory in candidates:
        if not directory.exists():
            continue
        images = sorted(
            p
            for p in directory.rglob("*")
            if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
            and "curve" not in p.name.lower()
            and "matrix" not in p.name.lower()
            and "results" not in p.name.lower()
        )
        if images:
            return images[0]

    return None


def matching_label_path(image_path):
    parts = list(image_path.parts)
    if "images" not in parts:
        return None

    image_index = parts.index("images")
    parts[image_index] = "labels"
    label_path = Path(*parts).with_suffix(".txt")
    return label_path if label_path.exists() else None


def load_labels(label_path):
    if label_path is None or not label_path.exists():
        return np.zeros((0, 5), dtype=np.float32)

    labels = []
    with label_path.open("r", encoding="utf-8") as file:
        for line in file:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            labels.append([float(value) for value in parts])

    if not labels:
        return np.zeros((0, 5), dtype=np.float32)
    return np.array(labels, dtype=np.float32)


def draw_panel_title(image, title, subtitle=None):
    output = image.copy()
    cv2.rectangle(output, (0, 0), (output.shape[1], 52), (18, 18, 18), -1)
    cv2.putText(
        output,
        title,
        (18, 28),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.75,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    if subtitle:
        cv2.putText(
            output,
            subtitle,
            (18, 46),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (210, 210, 210),
            1,
            cv2.LINE_AA,
        )
    return output


def draw_boxes(image, labels):
    output = image.copy()
    h, w = output.shape[:2]

    for label in labels:
        cls = int(label[0])
        x_c, y_c, box_w, box_h = label[1:5]
        x1 = int((x_c - box_w / 2) * w)
        y1 = int((y_c - box_h / 2) * h)
        x2 = int((x_c + box_w / 2) * w)
        y2 = int((y_c + box_h / 2) * h)

        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w - 1, x2), min(h - 1, y2)
        color = BOX_COLORS[cls % len(BOX_COLORS)]
        name = CLASS_NAMES[cls] if cls < len(CLASS_NAMES) else str(cls)

        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            output,
            name,
            (x1, max(18, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )

    return output


def make_preview_config(use_project_settings):
    config = TrainConfig(create_dirs=False)

    if use_project_settings:
        return config

    # Force visible effects for a report figure while keeping the same augmentation types.
    config.use_geometric = False
    config.use_color_jitter = True
    config.use_resolution_reduce = True
    config.use_noise_blur = True
    config.resolution_min_scale = 0.25
    config.resolution_max_scale = 0.45
    config.resolution_prob = 1.0
    config.gaussian_noise_prob = 1.0
    config.gaussian_noise_std = 8.0
    config.motion_blur_prob = 1.0
    config.motion_blur_kernel_min = 3
    config.motion_blur_kernel_max = 7
    return config


def create_triptych(image, labels, draw_yolo_boxes, use_project_settings):
    config = make_preview_config(use_project_settings)
    augment = create_augment_pipeline(config)

    aug1, labels1 = augment(image.copy(), labels.copy())
    aug2, labels2 = augment(image.copy(), labels.copy())

    panels = [
        ("Original", "source image", image, labels),
        ("Augmented 1", "custom training augmentation", aug1, labels1),
        ("Augmented 2", "same pipeline, different random sample", aug2, labels2),
    ]

    rendered = []
    for title, subtitle, panel, panel_labels in panels:
        if draw_yolo_boxes:
            panel = draw_boxes(panel, panel_labels)
        rendered.append(draw_panel_title(panel, title, subtitle))

    gap = np.full((image.shape[0], 18, 3), 245, dtype=np.uint8)
    return np.hstack([rendered[0], gap, rendered[1], gap, rendered[2]])


def main():
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)
        np.random.seed(args.seed)

    image_path = args.image or find_default_image()
    if image_path is None:
        raise FileNotFoundError(
            "No image was found. Pass one with --image path/to/image.jpg"
        )

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Unable to read image: {image_path}")

    image = cv2.resize(image, (args.size, args.size), interpolation=cv2.INTER_LINEAR)
    label_path = args.label or matching_label_path(image_path)
    labels = load_labels(label_path)

    triptych = create_triptych(
        image=image,
        labels=labels,
        draw_yolo_boxes=not args.no_boxes and len(labels) > 0,
        use_project_settings=args.project_settings,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output), triptych)

    print(f"Source image: {image_path}")
    if label_path:
        print(f"Label file: {label_path}")
    print(f"Saved preview: {args.output}")
    print("Press any key in the preview window to close it.")

    cv2.namedWindow("Augmentation Triptych", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Augmentation Triptych", 1500, 620)
    cv2.imshow("Augmentation Triptych", triptych)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
