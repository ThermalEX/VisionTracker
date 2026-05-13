import argparse
from collections import Counter, defaultdict
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
DEFAULT_CLASS_NAMES = ["ct_head", "ct_body", "t_head", "t_body"]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Summarise a YOLO-style dataset directory."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(r"E:\cs2 dataset"),
        help="Dataset root containing images/ and labels/ folders.",
    )
    parser.add_argument(
        "--classes",
        nargs="*",
        default=DEFAULT_CLASS_NAMES,
        help="Optional class names in class-id order.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Only count files and splits. Skip reading every label file.",
    )
    return parser.parse_args()


def collect_files(root, extensions=None):
    if not root.exists():
        return []

    files = [p for p in root.rglob("*") if p.is_file()]
    if extensions is not None:
        files = [p for p in files if p.suffix.lower() in extensions]
    return sorted(files)


def collect_split_files(root, extensions=None):
    if not root.exists():
        return []

    common_splits = ["train", "val", "valid", "test"]
    split_files = []
    used_split_dirs = []

    for split in common_splits:
        split_dir = root / split
        if split_dir.exists():
            used_split_dirs.append(split_dir)
            split_files.extend(collect_files(split_dir, extensions))

    if split_files:
        return sorted(split_files)

    return collect_files(root, extensions)


def label_for_image(image_path, dataset_root):
    try:
        relative = image_path.relative_to(dataset_root / "images")
    except ValueError:
        return None
    return dataset_root / "labels" / relative.with_suffix(".txt")


def image_for_label(label_path, dataset_root, image_stems):
    try:
        relative = label_path.relative_to(dataset_root / "labels")
    except ValueError:
        return None

    key = str(relative.with_suffix(""))
    return image_stems.get(key)


def split_name(path, folder_name):
    parts = path.parts
    if folder_name not in parts:
        return "unknown"
    index = parts.index(folder_name)
    if index + 1 >= len(parts):
        return "root"
    return parts[index + 1]


def read_label_stats(label_files):
    class_counter = Counter()
    boxes_per_file = {}
    invalid_lines = defaultdict(list)

    for label_path in label_files:
        box_count = 0
        try:
            lines = label_path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            lines = label_path.read_text(encoding="utf-8", errors="ignore").splitlines()

        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            parts = stripped.split()
            if len(parts) != 5:
                invalid_lines[label_path].append((line_number, stripped))
                continue

            try:
                class_id = int(float(parts[0]))
                coords = [float(value) for value in parts[1:]]
            except ValueError:
                invalid_lines[label_path].append((line_number, stripped))
                continue

            if not all(0.0 <= value <= 1.0 for value in coords):
                invalid_lines[label_path].append((line_number, stripped))
                continue

            class_counter[class_id] += 1
            box_count += 1

        boxes_per_file[label_path] = box_count

    return class_counter, boxes_per_file, invalid_lines


def print_section(title):
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def main():
    args = parse_args()
    dataset = args.dataset

    images_root = dataset / "images"
    labels_root = dataset / "labels"

    image_files = collect_split_files(images_root, IMAGE_EXTENSIONS)
    label_files = collect_split_files(labels_root, {".txt"})

    image_stems = {}
    for image_path in image_files:
        relative = image_path.relative_to(images_root).with_suffix("")
        image_stems[str(relative)] = image_path

    missing_labels = []
    for image_path in image_files:
        label_path = label_for_image(image_path, dataset)
        if label_path is None or not label_path.exists():
            missing_labels.append(image_path)

    orphan_labels = [
        label_path
        for label_path in label_files
        if image_for_label(label_path, dataset, image_stems) is None
    ]

    images_by_split = Counter(split_name(path, "images") for path in image_files)
    labels_by_split = Counter(split_name(path, "labels") for path in label_files)
    boxes_by_split = Counter()

    if args.fast:
        class_counter = Counter()
        boxes_per_file = {}
        invalid_lines = {}
    else:
        class_counter, boxes_per_file, invalid_lines = read_label_stats(label_files)
        for label_path, count in boxes_per_file.items():
            boxes_by_split[split_name(label_path, "labels")] += count

    print_section("Dataset Summary")
    print(f"Dataset root : {dataset}")
    print(f"Images root  : {images_root}")
    print(f"Labels root  : {labels_root}")
    print(f"Image files  : {len(image_files)}")
    print(f"Label files  : {len(label_files)}")
    if args.fast:
        print("Total boxes  : skipped in --fast mode")
    else:
        print(f"Total boxes  : {sum(class_counter.values())}")

    print_section("Split Counts")
    all_splits = sorted(set(images_by_split) | set(labels_by_split) | set(boxes_by_split))
    if not all_splits:
        print("No images or labels found.")
    else:
        print(f"{'Split':<12} {'Images':>10} {'Labels':>10} {'Boxes':>10}")
        print("-" * 48)
        for split in all_splits:
            print(
                f"{split:<12} "
                f"{images_by_split[split]:>10} "
                f"{labels_by_split[split]:>10} "
                f"{boxes_by_split[split]:>10}"
            )

    print_section("Class Distribution")
    if args.fast:
        print("Skipped in --fast mode. Run without --fast to read label files.")
    elif not class_counter:
        print("No boxes found.")
    else:
        total_boxes = sum(class_counter.values())
        print(f"{'ID':<6} {'Class':<20} {'Boxes':>10} {'Percent':>10}")
        print("-" * 52)
        for class_id in sorted(class_counter):
            name = args.classes[class_id] if class_id < len(args.classes) else f"class_{class_id}"
            count = class_counter[class_id]
            percent = count / total_boxes * 100
            print(f"{class_id:<6} {name:<20} {count:>10} {percent:>9.2f}%")

    print_section("Pairing Checks")
    print(f"Images without labels : {len(missing_labels)}")
    print(f"Labels without images : {len(orphan_labels)}")
    if args.fast:
        print("Labels with bad lines : skipped in --fast mode")
    else:
        print(f"Labels with bad lines : {len(invalid_lines)}")

    if missing_labels[:10]:
        print()
        print("First missing labels:")
        for path in missing_labels[:10]:
            print(f"  {path}")

    if orphan_labels[:10]:
        print()
        print("First orphan labels:")
        for path in orphan_labels[:10]:
            print(f"  {path}")

    if not args.fast and invalid_lines:
        print()
        print("First invalid label lines:")
        shown = 0
        for path, issues in invalid_lines.items():
            for line_number, line in issues:
                print(f"  {path}:{line_number} -> {line}")
                shown += 1
                if shown >= 10:
                    return


if __name__ == "__main__":
    main()
