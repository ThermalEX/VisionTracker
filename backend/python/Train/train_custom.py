"""
自定义YOLO训练脚本
主入口文件

使用方法:
    python train_custom.py

说明:
    这是一个简化的YOLO训练实现,适合初学者理解训练流程
    基于ultralytics YOLO,但添加了详细注释和自定义配置
"""
import os
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
    print("   自定义YOLO训练程序")
    print("   基于ultralytics YOLO11")
    print("="*70 + "\n")

    # 1. 解析命令行参数
    args = parse_args()

    # 2. 加载配置
    print("加载配置...")
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
        print("已禁用所有数据增强")

    if args.no_mosaic:
        config.use_mosaic = False
        print("已禁用Mosaic增强")

    # 性能优化开关
    if args.no_amp:
        config.use_amp = False
        print("已禁用混合精度训练")

    if args.no_cache:
        config.cache_images = False
        print("已禁用图像缓存")

    # 4. 检查数据集是否存在
    print("\n检查数据集...")
    data_yaml = Path(config.data_yaml)
    if not data_yaml.exists():
        print(f"错误: 数据集配置文件不存在: {data_yaml}")
        print(f"请确保文件路径正确")
        sys.exit(1)

    print(f"数据集配置: {data_yaml}")

    # 5. 检查预训练权重
    print("\n检查预训练权重...")
    if config.pretrained_weights:
        weights_path = Path(config.pretrained_weights)
        if not weights_path.exists():
            print(f"警告: 预训练权重不存在: {weights_path}")
            print(f"将尝试自动下载 yolo11n.pt")
        else:
            print(f"预训练权重: {weights_path}")
    else:
        print("不使用预训练权重（从头训练）")

    # 6. 打印训练配置摘要
    print("\n" + "-"*70)
    print("训练配置摘要:")
    print("-"*70)
    print(f"训练轮数: {config.epochs}")
    print(f"批次大小: {config.batch_size}")
    print(f"图像大小: {config.img_size}")
    print(f"学习率: {config.learning_rate}")
    print(f"工作线程: {config.num_workers}")
    print(f"")
    print(f"数据增强:")
    print(f"  分辨率降低: {config.use_resolution_reduce}")
    print(f"  色彩增强: {config.use_color_jitter}")
    print(f"  几何变换: {config.use_geometric}")
    print(f"  噪声模糊: {config.use_noise_blur}")
    print(f"  Mosaic: {config.use_mosaic}")
    print(f"")
    print(f"性能优化:")
    print(f"  混合精度(AMP): {config.use_amp}")
    print(f"  图像缓存: {config.cache_images}")
    print(f"  梯度累积: {config.accumulate_grad}步")
    print(f"")
    print(f"保存目录: {config.exp_dir}")
    print("-"*70 + "\n")

    # 7. 确认开始训练
    print("确认以上配置无误后，训练将自动开始...")
    print("按 Ctrl+C 可以中断训练\n")

    # 8. 开始训练
    try:
        results = train_model(config)

        # 9. 训练完成
        print("\n" + "="*70)
        print("训练成功完成！")
        print("="*70)
        print(f"\n模型和日志保存在: {config.exp_dir}")
        print(f"")
        print(f"使用训练好的模型进行推理:")
        print(f"  python Demo05.py  # 或其他Demo脚本")
        print(f"")
        print(f"查看TensorBoard日志:")
        print(f"  tensorboard --logdir {Path(config.exp_dir).parent}")
        print("="*70 + "\n")

        return 0

    except KeyboardInterrupt:
        print("\n\n训练被用户中断")
        return 1

    except Exception as e:
        print(f"\n\n训练过程中发生错误:")
        print(f"  {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
