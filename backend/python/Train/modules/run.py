# -*- coding: utf-8 -*-
"""
模型测试脚本
在测试集上评估训练好的 YOLO 模型性能
"""
import os
import sys
from pathlib import Path
from ultralytics import YOLO
import torch


def print_header(title):
    """打印格式化的标题"""
    print("\n" + "="*70)
    print(f"{title:^70}")
    print("="*70 + "\n")


def find_best_model():
    """自动查找最佳模型路径"""
    # 可能的模型路径列表（按优先级排序）
    possible_paths = [
        "../runs/custom_train/exp1/weights/last.pt",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None


def test_model(model_path=None, data_yaml=None, save_dir="runs/test", **kwargs):
    """
    在测试集上测试模型

    Args:
        model_path: 模型路径，如果为None则自动查找
        data_yaml: 数据集配置文件路径
        save_dir: 测试结果保存目录
        **kwargs: 其他传递给 model.val() 的参数
    """
    print_header("YOLO Model Testing")

    # 1. 查找模型
    if model_path is None:
        print("正在自动查找模型...")
        model_path = find_best_model()
        if model_path is None:
            print("错误: 未找到训练好的模型")
            print("请指定模型路径，例如: test_model('path/to/best.pt')")
            return None

    if not os.path.exists(model_path):
        print(f"错误: 模型文件不存在: {model_path}")
        return None

    print(f"找到模型: {model_path}")

    # 2. 设置数据集配置
    if data_yaml is None:
        data_yaml = "E:/BaiduNetdiskDownload/data/dataset.yaml"

    if not os.path.exists(data_yaml):
        print(f"错误: 数据集配置文件不存在: {data_yaml}")
        return None

    print(f"数据集配置: {data_yaml}")

    # 3. 加载模型
    print("\n正在加载模型...")
    try:
        model = YOLO(model_path)
        print(f"模型加载成功")

        # 打印模型信息
        if hasattr(model, 'device'):
            print(f"运行设备: {model.device}")
    except Exception as e:
        print(f"模型加载失败: {e}")
        return None

    # 4. 在测试集上进行评估
    print_header("Running Validation on Test Set")

    try:
        # 设置默认参数
        val_params = {
            'data': data_yaml,
            'split': 'val',  # 使用训练集
            'imgsz': 640,
            'batch': 16,
            'conf': 0.001,  # 置信度阈值
            'iou': 0.6,     # NMS IoU阈值
            'max_det': 300, # 每张图最大检测数
            'save_json': True,  # 保存COCO格式的结果
            'save_hybrid': True,  # 保存标签+预测的混合结果
            'project': save_dir,
            'name': 'test_results',
            'exist_ok': True,
        }

        # 更新用户提供的参数
        val_params.update(kwargs)

        print("测试参数:")
        for key, value in val_params.items():
            print(f"  {key:15s}: {value}")

        print("\n开始测试...")
        results = model.val(**val_params)

        # 5. 打印结果
        print_header("Test Results Summary")

        if hasattr(results, 'results_dict'):
            metrics = results.results_dict
            print(f"{'指标':<25s} {'值':>15s}")
            print("-"*42)

            # 显示主要指标
            metric_names = {
                'metrics/precision(B)': 'Precision',
                'metrics/recall(B)': 'Recall',
                'metrics/mAP50(B)': 'mAP@0.5',
                'metrics/mAP50-95(B)': 'mAP@0.5:0.95',
            }

            for key, name in metric_names.items():
                if key in metrics:
                    value = metrics[key]
                    print(f"{name:<25s} {value:>14.4f}")

        # 显示每个类别的指标
        if hasattr(results, 'box') and hasattr(results.box, 'maps'):
            print("\n" + "="*42)
            print("Per-Class mAP@0.5")
            print("="*42)

            class_names = ['ct_head', 'ct_body', 't_head', 't_body']
            maps = results.box.maps

            if hasattr(maps, '__iter__'):
                for i, (class_name, map_value) in enumerate(zip(class_names, maps)):
                    print(f"{class_name:<25s} {map_value:>14.4f}")

        # 6. 显示结果保存路径
        save_path = os.path.join(save_dir, 'test_results')
        print("\n" + "="*70)
        print(f"测试完成!")
        print(f"结果已保存到: {save_path}")
        print("="*70 + "\n")

        return results

    except Exception as e:
        print(f"\n测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_on_images(model_path=None, image_dir=None, save_dir="runs/predict", **kwargs):
    """
    在指定图片目录上进行推理并可视化结果

    Args:
        model_path: 模型路径
        image_dir: 图片目录路径
        save_dir: 结果保存目录
        **kwargs: 其他传递给 model.predict() 的参数
    """
    print_header("Inference on Images")

    # 查找模型
    if model_path is None:
        model_path = find_best_model()
        if model_path is None:
            print("错误: 未找到模型")
            return None

    print(f"模型: {model_path}")

    # 设置图片目录
    if image_dir is None:
        image_dir = "../../DataCollection/data/images/test"

    if not os.path.exists(image_dir):
        print(f"错误: 图片目录不存在: {image_dir}")
        return None

    print(f"图片目录: {image_dir}")

    # 加载模型
    model = YOLO(model_path)

    # 推理参数
    predict_params = {
        'source': image_dir,
        'imgsz': 640,
        'conf': 0.25,
        'iou': 0.6,
        'max_det': 300,
        'save': True,
        'save_txt': True,
        'save_conf': True,
        'project': save_dir,
        'name': 'predict_results',
        'exist_ok': True,
    }

    predict_params.update(kwargs)

    print("\n推理参数:")
    for key, value in predict_params.items():
        print(f"  {key:15s}: {value}")

    print("\n开始推理...")
    results = model.predict(**predict_params)

    save_path = os.path.join(save_dir, 'predict_results')
    print(f"\n推理完成! 结果已保存到: {save_path}")

    return results


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='YOLO 模型测试工具')
    parser.add_argument('--model', type=str, default=None,
                        help='模型路径 (默认自动查找)')
    parser.add_argument('--data', type=str,
                        default='../../DataCollection/data/dataset.yaml',
                        help='数据集配置文件')
    parser.add_argument('--mode', type=str, default='test',
                        choices=['test', 'predict'],
                        help='测试模式: test=在测试集上评估, predict=在图片上推理')
    parser.add_argument('--image-dir', type=str, default=None,
                        help='图片目录 (仅用于 predict 模式)')
    parser.add_argument('--save-dir', type=str, default='runs/test',
                        help='结果保存目录')
    parser.add_argument('--imgsz', type=int, default=640,
                        help='图像尺寸')
    parser.add_argument('--batch', type=int, default=16,
                        help='批次大小')
    parser.add_argument('--conf', type=float, default=0.001,
                        help='置信度阈值')
    parser.add_argument('--iou', type=float, default=0.6,
                        help='NMS IoU阈值')

    args = parser.parse_args()

    if args.mode == 'test':
        # 在测试集上评估
        test_model(
            model_path=args.model,
            data_yaml=args.data,
            save_dir=args.save_dir,
            imgsz=args.imgsz,
            batch=args.batch,
            conf=args.conf,
            iou=args.iou,
        )
    else:
        # 在图片上推理
        test_on_images(
            model_path=args.model,
            image_dir=args.image_dir,
            save_dir=args.save_dir,
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
        )


if __name__ == '__main__':
    main()
