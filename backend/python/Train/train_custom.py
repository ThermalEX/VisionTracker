import sys
import argparse
from pathlib import Path

# 导入自定义模块
from config import TrainConfig
from modules.my_trainer import train_model


def parse_args():
    """
    解析命令行参数
    可以通过命令行覆盖配置文件中的参数
    """
    parser = argparse.ArgumentParser(
        description='自定义YOLO训练程序',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # 基本参数
    parser.add_argument('--epochs', type=int, default=None,
                        help='训练轮数')
    parser.add_argument('--batch-size', type=int, default=None,
                        help='批次大小')
    parser.add_argument('--img-size', type=int, default=None,
                        help='图像大小')

    # 数据增强
    parser.add_argument('--no-mosaic', action='store_true',
                        help='禁用Mosaic增强')
    parser.add_argument('--no-augment', action='store_true',
                        help='禁用所有数据增强')

    # 性能优化
    parser.add_argument('--no-amp', action='store_true',
                        help='禁用混合精度训练')
    parser.add_argument('--no-cache', action='store_true',
                        help='禁用图像缓存')

    # 其他
    parser.add_argument('--device', type=str, default=None,
                        help='训练设备 (如: 0, cpu)')
    parser.add_argument('--workers', type=int, default=None,
                        help='数据加载线程数')

    return parser.parse_args()


def main():
    """主函数"""

    print("\n" + "="*70)
    print(" "*22 + "Custom YOLO Training Program")
    print(" "*26 + "Based on YOLO11")
    print("="*70)

    # 1. 解析命令行参数
    args = parse_args()

    # 2. 加载配置
    print("\nLoading configuration...")
    config = TrainConfig()

    # 3. 应用命令行参数覆盖
    if args.epochs is not None:
        config.epochs = args.epochs
    if args.batch_size is not None:
        config.batch_size = args.batch_size
    if args.img_size is not None:
        config.img_size = args.img_size
    if args.workers is not None:
        config.num_workers = args.workers

    # 数据增强开关
    if args.no_augment:
        config.use_resolution_reduce = False
        config.use_color_jitter = False
        config.use_geometric = False
        config.use_noise_blur = False
        config.use_mosaic = False
        print("  All augmentation disabled")

    if args.no_mosaic:
        config.use_mosaic = False
        print("  Mosaic augmentation disabled")

    # 性能优化开关
    if args.no_amp:
        config.use_amp = False
        print("  AMP disabled")

    if args.no_cache:
        config.cache_images = False
        print("  Image cache disabled")

    # 4. 检查数据集是否存在
    print("\nChecking dataset...")
    data_yaml = Path(config.data_yaml)
    if not data_yaml.exists():
        print(f"Error: Dataset config not found: {data_yaml}")
        sys.exit(1)
    print(f"  Dataset config: {data_yaml}")

    # 5. 检查预训练权重
    print("\nChecking pretrained weights...")
    if config.pretrained_weights:
        weights_path = Path(config.pretrained_weights)
        if not weights_path.exists():
            print(f"  Warning: Weights not found, will try to download yolo11n.pt")
        else:
            print(f"  Pretrained weights: {weights_path}")
    else:
        print("  Training from scratch (no pretrained weights)")

    # 6. 确认开始训练
    print("\nPress Ctrl+C to interrupt training\n")

    # 8. 开始训练
    try:
        results = train_model(config)

        # 9. 训练完成
        normalized_path = config.exp_dir.replace('\\', '/')
        print("\n" + "="*70)
        print(" "*25 + "Training Successful!")
        print("="*70)
        print(f"\nModel saved      : {normalized_path}/weights/best.pt")
        print(f"TensorBoard      : tensorboard --logdir {Path(config.exp_dir).parent}")
        print("="*70 + "\n")

        return 0

    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user")
        return 1

    except Exception as e:
        print(f"\n\nTraining error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
