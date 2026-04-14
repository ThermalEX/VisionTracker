"""
训练器模块
整合数据加载、模型训练、验证和日志记录
"""
import torch
import time
from pathlib import Path

# 支持相对导入和直接运行
try:
    from .my_model import create_model
    from .my_dataset import load_dataset_config
    from .my_utils import (
        CheckpointManager,
        TensorBoardLogger,
        EarlyStopping,
        MetricsTracker,
        print_training_progress
    )
except ImportError:
    from my_model import create_model
    from my_dataset import load_dataset_config
    from my_utils import (
        CheckpointManager,
        TensorBoardLogger,
        EarlyStopping,
        MetricsTracker,
        print_training_progress
    )


class YOLOTrainer:
    """
    YOLO训练器
    整合所有训练相关功能
    """

    def __init__(self, config):
        """
        初始化训练器
        Args:
            config: TrainConfig配置对象
        """
        self.cfg = config

        # 设备
        requested_device = str(getattr(config, "device", "auto") or "auto").strip().lower()
        if requested_device in ("", "auto"):
            self.device = "0" if torch.cuda.is_available() else "cpu"
        else:
            self.device = requested_device
        print(f"Device           : {self.device}")

        # 创建模型
        print("Model            : Creating...")
        self.model = create_model(
            num_classes=config.num_classes,
            pretrained=config.pretrained_weights
        )

        # 移动到设备
        self.model = self.model.to(torch.device("cuda:0" if self.device == "0" else self.device))

        # 加载数据集配置
        print("Dataset Config   : Loading...")
        self.dataset_config = load_dataset_config(config.data_yaml)

        # 初始化工具
        self.checkpoint_mgr = CheckpointManager(
            config.exp_dir,
            save_period=config.save_period
        )

        self.logger = TensorBoardLogger(
            Path(config.exp_dir) / 'logs',
            enabled=config.use_tensorboard
        )

        self.early_stopping = EarlyStopping(
            patience=config.patience
        )

        self.metrics_tracker = MetricsTracker(config.exp_dir)

        # 训练状态
        self.start_epoch = 0
        self.best_map = 0.0

        print("Trainer          : Ready\n")

    def train(self):
        """
        开始训练
        使用ultralytics的训练功能，但添加自定义的管理
        """
        # 打印配置
        self.cfg.print_config()

        # 使用ultralytics的训练接口
        try:
            # 配置训练参数
            train_args = {
                # 数据
                'data': self.cfg.data_yaml,
                'imgsz': self.cfg.img_size,
                'batch': self.cfg.batch_size,
                'workers': self.cfg.num_workers,

                # 训练
                'epochs': self.cfg.epochs,
                'optimizer': 'SGD',
                'lr0': self.cfg.learning_rate,
                'momentum': self.cfg.momentum,
                'weight_decay': self.cfg.weight_decay,

                # 数据增强
                'hsv_h': self.cfg.hsv_h,
                'hsv_s': self.cfg.hsv_s,
                'hsv_v': self.cfg.hsv_v,
                'degrees': self.cfg.rotate_degree if self.cfg.use_geometric else 0,
                'flipud': self.cfg.flip_ud,
                'fliplr': self.cfg.flip_lr,
                'scale': self.cfg.scale_max - 1.0 if self.cfg.use_geometric else 0,
                'mosaic': 1.0 if self.cfg.use_mosaic else 0.0,

                # 性能优化
                'amp': self.cfg.use_amp,
                'cache': self.cfg.cache_images,

                # 保存和日志
                'project': self.cfg.save_dir,
                'name': Path(self.cfg.exp_dir).name,
                'exist_ok': True,
                'save_period': self.cfg.save_period,
                'patience': self.cfg.patience,

                # 其他
                'verbose': True,
                'plots': self.cfg.save_plots,
                'device': self.device,
            }

            # 开始计时
            start_time = time.time()

            # 调用ultralytics的训练方法
            print("Starting training with ultralytics...\n")

            results = self.model.yolo.train(**train_args)

            # 训练完成
            total_time = time.time() - start_time
            hours = int(total_time // 3600)
            minutes = int((total_time % 3600) // 60)
            seconds = int(total_time % 60)

            normalized_path = self.cfg.exp_dir.replace('\\', '/')

            print("\n" + "="*70)
            print(" "*27 + "Training Complete")
            print("="*70)
            print(f"Total Time       : {hours:02d}:{minutes:02d}:{seconds:02d}")
            print(f"Model Saved      : {normalized_path}")
            print("="*70 + "\n")

            return results

        except Exception as e:
            print(f"\nTraining error: {e}")
            import traceback
            traceback.print_exc()
            raise

    def validate(self):
        """
        在验证集上评估模型
        Returns:
            metrics: 验证指标字典
        """
        print("\nValidating model...")

        try:
            # 使用ultralytics的验证功能
            metrics = self.model.yolo.val(
                data=self.cfg.data_yaml,
                imgsz=self.cfg.img_size,
                batch=self.cfg.batch_size,
                device=self.device,
                verbose=True
            )

            # 提取关键指标
            results = {
                'mAP50': metrics.box.map50 if hasattr(metrics, 'box') else 0.0,
                'mAP50-95': metrics.box.map if hasattr(metrics, 'box') else 0.0,
            }

            print(f"\nValidation Results:")
            print(f"  mAP50        : {results['mAP50']:.4f}")
            print(f"  mAP50-95     : {results['mAP50-95']:.4f}")

            return results

        except Exception as e:
            print(f"\nValidation error: {e}")
            return {'mAP50': 0.0, 'mAP50-95': 0.0}


def train_model(config):
    """
    训练模型的主函数
    Args:
        config: TrainConfig配置对象
    Returns:
        训练结果
    """
    # 创建训练器
    trainer = YOLOTrainer(config)

    # 开始训练
    results = trainer.train()

    return results


if __name__ == '__main__':
    # 测试训练器
    import sys
    from pathlib import Path

    # 添加父目录到路径以便导入 config
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from config import TrainConfig

    print("\n" + "="*70)
    print(" "*28 + "Trainer Test Mode")
    print("="*70 + "\n")

    # 创建配置（使用较小的参数进行测试）
    config = TrainConfig()
    config.epochs = 2
    config.batch_size = 4
    config.cache_images = False

    # 创建训练器
    trainer = YOLOTrainer(config)

    print("Trainer created successfully!")
    print("To start training, run train_custom.py\n")
