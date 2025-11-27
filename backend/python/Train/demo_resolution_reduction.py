import cv2
import numpy as np
import random
from pathlib import Path


class RandomResolutionReduction:
    """随机降分辨率增强 - 模拟低画质输入"""

    def __init__(self, min_scale=0.25, max_scale=1.0, probability=0.5):
        self.min_scale = min_scale
        self.max_scale = max_scale
        self.probability = probability

    def __call__(self, image):
        if random.random() > self.probability:
            return image, 1.0

        h, w = image.shape[:2]
        scale = random.uniform(self.min_scale, self.max_scale)

        if scale < 1.0:
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))

            # 先缩小再放大，模拟模糊效果
            small = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            interpolation = random.choice([cv2.INTER_NEAREST, cv2.INTER_LINEAR])
            image = cv2.resize(small, (w, h), interpolation=interpolation)

        return image, scale


def add_text_with_background(image, text, position, font_scale=0.7, thickness=2,
                             text_color=(255, 255, 255), bg_color=(0, 0, 0)):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (text_width, text_height), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    x, y = position

    cv2.rectangle(image, (x - 5, y - text_height - 5),
                 (x + text_width + 5, y + baseline + 5), bg_color, -1)
    cv2.putText(image, text, (x, y), font, font_scale, text_color, thickness)


def draw_boxes_on_image(image, label_path):
    """绘制YOLO格式的标注框"""
    img = image.copy()
    if not Path(label_path).exists():
        return img

    h, w = image.shape[:2]
    colors = [(0, 255, 0), (255, 255, 0), (0, 0, 255), (255, 0, 255)]
    class_names = ["ct_head", "ct_body", "t_head", "t_body"]

    with open(label_path, 'r') as f:
        for line in f:
            data = line.strip().split()
            if len(data) == 5:
                cls = int(data[0])
                x_center, y_center = float(data[1]) * w, float(data[2]) * h
                box_w, box_h = float(data[3]) * w, float(data[4]) * h

                x1 = int(x_center - box_w / 2)
                y1 = int(y_center - box_h / 2)
                x2 = int(x_center + box_w / 2)
                y2 = int(y_center + box_h / 2)

                cv2.rectangle(img, (x1, y1), (x2, y2), colors[cls], 2)
                cv2.putText(img, class_names[cls], (x1, y1-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[cls], 2)
    return img


def create_comparison_display(original, augmented, scale_factor, show_boxes=False, label_path=None):
    h, w = original.shape[:2]

    if show_boxes and label_path:
        original = draw_boxes_on_image(original, label_path)
        augmented = draw_boxes_on_image(augmented, label_path)

    title_height = 80
    gap = 20
    display = np.ones((h + title_height, w * 2 + gap, 3), dtype=np.uint8) * 255

    display[title_height:, :w] = original
    display[title_height:, w+gap:] = augmented

    add_text_with_background(display, "Original (640x640)", (20, 40),
                            font_scale=1.0, thickness=2, bg_color=(0, 128, 0))

    res_text = f"Reduced: {scale_factor:.0%} ({int(640*scale_factor)}x{int(640*scale_factor)})"
    add_text_with_background(display, res_text, (w + gap + 20, 40),
                            font_scale=1.0, thickness=2, bg_color=(0, 0, 128))

    return display


def create_multi_scale_comparison(image, resize_for_display=True):
    scales = [1.0, 0.75, 0.5, 0.25]
    results = []

    for scale in scales:
        h, w = image.shape[:2]
        new_w = max(1, int(w * scale))
        new_h = max(1, int(h * scale))

        small = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        enlarged = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)

        title_h = 50
        display = np.ones((h + title_h, w, 3), dtype=np.uint8) * 255
        display[title_h:, :] = enlarged

        add_text_with_background(display, f"{scale:.0%} Resolution", (10, 25),
                                font_scale=0.8, thickness=2, bg_color=(50, 50, 150))
        cv2.putText(display, f"({new_w}x{new_h})", (10, 45),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
        results.append(display)

    row1 = np.hstack([results[0], results[1]])
    row2 = np.hstack([results[2], results[3]])
    grid = np.vstack([row1, row2])

    title_area = np.ones((60, grid.shape[1], 3), dtype=np.uint8) * 240
    add_text_with_background(title_area, "Multi-Scale Resolution Comparison",
                            (20, 40), font_scale=1.2, thickness=2, bg_color=(0, 100, 0))
    final = np.vstack([title_area, grid])

    if resize_for_display:
        new_h = int(final.shape[0] * 0.7)
        new_w = int(final.shape[1] * 0.7)
        final = cv2.resize(final, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    return final


def demo_interactive():
    print("="*60)
    print("分辨率降低增强演示")
    print("="*60)
    print("\n选择图像来源:")
    print("1. 训练数据集")
    print("2. 自定义图像")

    choice = input("\n输入 (1/2): ").strip()

    if choice == '1':
        data_dir = Path(__file__).parent.parent / "DataCollection" / "data" / "images" / "train"

        if not data_dir.exists():
            print(f"错误: 未找到数据目录 {data_dir}")
            return

        image_files = sorted([f for f in data_dir.iterdir()
                            if f.suffix.lower() in ['.jpg', '.jpeg', '.png']])

        if len(image_files) == 0:
            print("错误: 没有找到图像")
            return

        print(f"\n找到 {len(image_files)} 张图像")
        augmentor = RandomResolutionReduction(min_scale=0.25, max_scale=1.0, probability=1.0)

        print("\n按键说明: 任意键=下一张 | q=退出 | m=多尺度对比 | b=切换标注框\n")

        show_boxes = False
        labels_dir = Path(__file__).parent.parent / "DataCollection" / "data" / "labels" / "train"

        for idx, img_path in enumerate(image_files):
            image = cv2.imread(str(img_path))
            if image is None:
                continue

            image = cv2.resize(image, (640, 640))
            augmented, scale = augmentor(image.copy())
            label_path = labels_dir / (img_path.stem + ".txt")

            while True:
                display = create_comparison_display(image, augmented, scale, show_boxes, label_path)

                cv2.namedWindow('Demo', cv2.WINDOW_NORMAL)
                cv2.resizeWindow('Demo', 1400, 800)
                cv2.imshow('Demo', display)

                print(f"[{idx+1}/{len(image_files)}] {img_path.name} | Scale: {scale:.0%} | Boxes: {'ON' if show_boxes else 'OFF'}")

                key = cv2.waitKey(0) & 0xFF

                if key == ord('q') or key == 27:
                    cv2.destroyAllWindows()
                    return
                elif key == ord('b'):
                    show_boxes = not show_boxes
                    continue
                elif key == ord('m'):
                    multi_scale = create_multi_scale_comparison(image, resize_for_display=True)
                    cv2.namedWindow('Multi-Scale', cv2.WINDOW_NORMAL)
                    cv2.resizeWindow('Multi-Scale', 1400, 1000)
                    cv2.imshow('Multi-Scale', multi_scale)
                    cv2.waitKey(0)
                    cv2.destroyWindow('Multi-Scale')
                    continue
                else:
                    break

    else:
        img_path = input("\n图像路径: ").strip().strip('"')

        if not Path(img_path).exists():
            print("错误: 文件不存在")
            return

        image = cv2.imread(img_path)
        if image is None:
            print("错误: 无法加载图像")
            return

        image = cv2.resize(image, (640, 640))
        multi_scale = create_multi_scale_comparison(image, resize_for_display=True)

        cv2.namedWindow('Multi-Scale', cv2.WINDOW_NORMAL)
        cv2.imshow('Multi-Scale', multi_scale)
        cv2.waitKey(0)

    cv2.destroyAllWindows()
    print("\n完成")


def demo_automatic():
    print("="*60)
    print("自动生成对比图")
    print("="*60)

    data_dir = Path(__file__).parent.parent / "DataCollection" / "data" / "images" / "train"

    if not data_dir.exists():
        print(f"错误: 未找到数据目录")
        return

    image_files = sorted([f for f in data_dir.iterdir()
                         if f.suffix.lower() in ['.jpg', '.jpeg', '.png']])

    if len(image_files) == 0:
        print("错误: 没有找到图像")
        return

    img_path = image_files[0]
    print(f"\n使用图像: {img_path.name}")

    image = cv2.imread(str(img_path))
    image = cv2.resize(image, (640, 640))

    comparison_full = create_multi_scale_comparison(image, resize_for_display=False)

    output_dir = Path(__file__).parent / "demo_output"
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / "resolution_demo.jpg"
    cv2.imwrite(str(output_path), comparison_full)
    print(f"已保存: {output_path.absolute()}")

    augmentor = RandomResolutionReduction(min_scale=0.25, max_scale=0.25, probability=1.0)
    augmented, scale = augmentor(image.copy())
    single_comparison = create_comparison_display(image, augmented, scale)

    single_output = output_dir / "single_demo.jpg"
    cv2.imwrite(str(single_output), single_comparison)
    print(f"已保存: {single_output.absolute()}")

    comparison_display = create_multi_scale_comparison(image, resize_for_display=True)
    cv2.namedWindow('Preview', cv2.WINDOW_NORMAL)
    cv2.imshow('Preview', comparison_display)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

    print("\n完成")


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  降分辨率增强演示程序")
    print("="*60)

    print("\n选择模式:")
    print("1. 交互式查看")
    print("2. 生成对比图")

    mode = input("\n输入 (1/2): ").strip()

    if mode == '2':
        demo_automatic()
    else:
        demo_interactive()
