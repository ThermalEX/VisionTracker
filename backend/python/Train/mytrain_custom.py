"""
自定义目标检测训练程序主入口
Custom Object Detector Training - Main Entry Point

用法 Usage:
    python mytrain_custom.py                    # 使用默认配置 / Use default config
    python mytrain_custom.py --epochs 100       # 自定义epoch数 / Custom epochs
    python mytrain_custom.py --batch-size 32    # 自定义batch大小 / Custom batch size
    python mytrain_custom.py --no-augment       # 禁用数据增强 / Disable augmentation
"""

import argparse
import sys
import os

# 添加模块路径 / Add module path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from custom_detector.config import Config, ConfigSmall, ConfigLarge
from custom_detector.train import train_model


def parse_args():
    """
    解析命令行参数
    Parse command line arguments.
    """
    parser = argparse.ArgumentParser(
        description='自定义目标检测训练程序 / Custom Object Detector Training'
    )

    # 基本参数 / Basic parameters
    parser.add_argument('--epochs', type=int, default=None,
                        help='训练轮数 / Number of epochs (默认/default: 50)')
    parser.add_argument('--batch-size', type=int, default=None,
                        help='批次大小 / Batch size (默认/default: 16)')
    parser.add_argument('--lr', type=float, default=None,
                        help='学习率 / Learning rate (默认/default: 0.001)')
    parser.add_argument('--device', type=str, default='cuda',
                        choices=['cuda', 'cpu'], help='训练设备 / Training device')

    # 模型配置 / Model configuration
    parser.add_argument('--model-size', type=str, default='normal',
                        choices=['small', 'normal', 'large'],
                        help='模型大小 / Model size (默认/default: normal)')

    # 数据增强 / Data augmentation
    parser.add_argument('--no-augment', action='store_true',
                        help='禁用数据增强 / Disable data augmentation')

    # 随机降分辨率增强 / Random resolution reduction augmentation
    parser.add_argument('--resolution-augment', action='store_true', default=True,
                        help='启用随机降分辨率增强 / Enable random resolution reduction (默认开启/default on)')
    parser.add_argument('--no-resolution-augment', action='store_true',
                        help='禁用随机降分辨率增强 / Disable random resolution reduction')
    parser.add_argument('--min-resolution', type=float, default=0.25,
                        help='最小分辨率比例 / Min resolution scale (默认/default: 0.25)')
    parser.add_argument('--resolution-prob', type=float, default=0.5,
                        help='降分辨率概率 / Resolution reduction probability (默认/default: 0.5)')

    # 保存设置 / Save settings
    parser.add_argument('--save-dir', type=str, default=None,
                        help='模型保存目录 / Model save directory')
    parser.add_argument('--save-period', type=int, default=5,
                        help='每N个epoch保存一次 / Save every N epochs (默认/default: 5)')

    # 其他 / Others
    parser.add_argument('--workers', type=int, default=4,
                        help='数据加载线程数 / Number of data loading workers (默认/default: 4)')
    parser.add_argument('--resume', type=str, default=None,
                        help='从检查点恢复训练 / Resume from checkpoint')

    return parser.parse_args()


def main():
    """
    主函数
    Main function.
    """
    args = parse_args()

    # 选择配置 / Select configuration
    if args.model_size == 'small':
        config = ConfigSmall()
        print("使用小型模型配置 / Using small model configuration")
    elif args.model_size == 'large':
        config = ConfigLarge()
        print("使用大型模型配置 / Using large model configuration")
    else:
        config = Config()
        print("使用标准模型配置 / Using standard model configuration")

    # 应用命令行参数 / Apply command line arguments
    if args.epochs is not None:
        config.EPOCHS = args.epochs
    if args.batch_size is not None:
        config.BATCH_SIZE = args.batch_size
    if args.lr is not None:
        config.LEARNING_RATE = args.lr
    if args.device:
        config.DEVICE = args.device
    if args.workers:
        config.NUM_WORKERS = args.workers
    if args.save_dir:
        config.SAVE_DIR = args.save_dir
    if args.save_period:
        config.SAVE_PERIOD = args.save_period

    # 数据增强设置 / Data augmentation settings
    if args.no_augment:
        config.AUGMENT_ENABLED = False
        config.RANDOM_RESOLUTION_ENABLED = False
        print("数据增强已禁用 / Data augmentation disabled")
    else:
        # 随机降分辨率设置 / Random resolution reduction settings
        if args.no_resolution_augment:
            config.RANDOM_RESOLUTION_ENABLED = False
            print("随机降分辨率增强已禁用 / Random resolution reduction disabled")
        else:
            config.RANDOM_RESOLUTION_ENABLED = True
            config.MIN_RESOLUTION_SCALE = args.min_resolution
            config.RESOLUTION_REDUCTION_PROB = args.resolution_prob
            print(f"随机降分辨率增强已启用 / Random resolution reduction enabled: "
                  f"最小比例/min_scale={args.min_resolution}, 概率/prob={args.resolution_prob}")

    # 打印配置摘要 / Print configuration summary
    print("\n" + "="*60)
    print("训练配置摘要 / Training Configuration Summary")
    print("="*60)
    print(f"Epochs: {config.EPOCHS}")
    print(f"Batch size: {config.BATCH_SIZE}")
    print(f"Learning rate: {config.LEARNING_RATE}")
    print(f"Device: {config.DEVICE}")
    print(f"Input size: {config.INPUT_SIZE}x{config.INPUT_SIZE}")
    print(f"Number of classes: {config.NUM_CLASSES}")
    print(f"Class names: {config.CLASS_NAMES}")
    print(f"Save directory: {config.SAVE_DIR}")
    print("="*60 + "\n")

    # 开始训练 / Start training
    try:
        model = train_model(config)
        print("\n训练成功完成! / Training completed successfully!")

        # 打印模型使用说明 / Print model usage instructions
        print("\n" + "="*60)
        print("模型使用说明 / Model Usage Instructions")
        print("="*60)
        print("加载模型进行推理 / Load model for inference:")
        print("```python")
        print("from custom_detector.inference import load_detector")
        print("")
        print("detector = load_detector('runs/custom/best.pt')")
        print("result_image, detections = detector.predict_and_draw(image)")
        print("```")
        print("="*60)

    except KeyboardInterrupt:
        print("\n训练被用户中断 / Training interrupted by user")
    except Exception as e:
        print(f"\n训练出错 / Training error: {e}")
        raise


if __name__ == '__main__':
    main()
