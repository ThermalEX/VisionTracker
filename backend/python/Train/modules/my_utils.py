"""
工具函数模块
包含检查点管理、日志记录、早停机制等
"""
import torch
import os
from pathlib import Path
from datetime import datetime
import json


class CheckpointManager:
    """检查点管理器"""

    def __init__(self, save_dir, save_period=10):
        """
        Args:
            save_dir: 保存目录
            save_period: 每N个epoch保存一次
        """
        self.save_dir = Path(save_dir) / 'weights'
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.save_period = save_period
        self.best_map = 0.0

        print(f"检查点将保存到: {self.save_dir}")

    def save_checkpoint(self, model, optimizer, epoch, metrics, is_best=False, is_last=False):
        """
        保存检查点
        Args:
            model: 模型
            optimizer: 优化器
            epoch: 当前epoch
            metrics: 指标字典
            is_best: 是否是最佳模型
            is_last: 是否是最后一个epoch
        """
        checkpoint = {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        }

        # 保存最新的检查点
        if is_last:
            last_path = self.save_dir / 'last.pt'
            torch.save(checkpoint, last_path)
            print(f"保存最新检查点: {last_path}")

        # 保存最佳模型
        if is_best:
            best_path = self.save_dir / 'best 12.10.pt'
            torch.save(checkpoint, best_path)
            print(f"保存最佳模型: {best_path} (mAP: {metrics.get('mAP50', 0):.4f})")
            self.best_map = metrics.get('mAP50', 0)

        # 定期保存
        if (epoch + 1) % self.save_period == 0:
            epoch_path = self.save_dir / f'epoch_{epoch+1}.pt'
            torch.save(checkpoint, epoch_path)
            print(f"保存epoch检查点: {epoch_path}")

    def load_checkpoint(self, checkpoint_path, model, optimizer=None):
        """
        加载检查点
        Args:
            checkpoint_path: 检查点路径
            model: 模型
            optimizer: 优化器（可选）
        Returns:
            start_epoch: 开始的epoch
            metrics: 指标
        """
        if not Path(checkpoint_path).exists():
            print(f"检查点不存在: {checkpoint_path}")
            return 0, {}

        print(f"加载检查点: {checkpoint_path}")
        checkpoint = torch.load(checkpoint_path, map_location='cpu')

        # 加载模型
        model.load_state_dict(checkpoint['model_state_dict'])

        # 加载优化器
        if optimizer is not None and 'optimizer_state_dict' in checkpoint:
            optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        start_epoch = checkpoint.get('epoch', 0) + 1
        metrics = checkpoint.get('metrics', {})

        print(f"检查点加载完成，从epoch {start_epoch} 继续训练")
        return start_epoch, metrics


class TensorBoardLogger:
    """TensorBoard日志记录器"""

    def __init__(self, log_dir, enabled=True):
        """
        Args:
            log_dir: 日志目录
            enabled: 是否启用
        """
        self.enabled = enabled
        self.writer = None

        if self.enabled:
            try:
                from torch.utils.tensorboard import SummaryWriter
                self.log_dir = Path(log_dir)
                self.log_dir.mkdir(parents=True, exist_ok=True)
                self.writer = SummaryWriter(str(self.log_dir))
                print(f"TensorBoard日志目录: {self.log_dir}")
                print(f"使用命令查看: tensorboard --logdir {self.log_dir.parent}")
            except ImportError:
                print("警告: 无法导入tensorboard，日志功能将被禁用")
                self.enabled = False

    def log_scalar(self, tag, value, step):
        """记录标量值"""
        if self.enabled and self.writer is not None:
            self.writer.add_scalar(tag, value, step)

    def log_scalars(self, main_tag, tag_value_dict, step):
        """记录多个标量"""
        if self.enabled and self.writer is not None:
            self.writer.add_scalars(main_tag, tag_value_dict, step)

    def log_metrics(self, epoch, train_loss, val_metrics):
        """
        记录训练指标
        Args:
            epoch: 当前epoch
            train_loss: 训练损失
            val_metrics: 验证指标字典
        """
        if not self.enabled:
            return

        # 记录损失
        self.log_scalar('Loss/train', train_loss, epoch)

        # 记录验证指标
        for key, value in val_metrics.items():
            if isinstance(value, (int, float)):
                self.log_scalar(f'Metrics/{key}', value, epoch)

    def close(self):
        """关闭writer"""
        if self.writer is not None:
            self.writer.close()


class EarlyStopping:
    """早停机制"""

    def __init__(self, patience=50, min_delta=0.0001):
        """
        Args:
            patience: 容忍的epoch数（指标不提升的最大epoch数）
            min_delta: 最小改进阈值
        """
        self.patience = patience
        self.min_delta = min_delta
        self.counter = 0
        self.best_score = None
        self.early_stop = False

        print(f"早停机制: patience={patience}, min_delta={min_delta}")

    def __call__(self, score):
        """
        检查是否应该早停
        Args:
            score: 当前指标得分（越大越好，如mAP）
        Returns:
            should_stop: 是否应该停止训练
        """
        if self.best_score is None:
            self.best_score = score
            return False

        # 检查是否有改进
        if score > self.best_score + self.min_delta:
            # 有改进
            self.best_score = score
            self.counter = 0
            return False
        else:
            # 没有改进
            self.counter += 1
            print(f"早停计数: {self.counter}/{self.patience} (最佳: {self.best_score:.4f})")

            if self.counter >= self.patience:
                print(f"触发早停！{self.patience}个epoch内指标未提升")
                self.early_stop = True
                return True

        return False


class MetricsTracker:
    """指标跟踪器"""

    def __init__(self, save_dir):
        """
        Args:
            save_dir: 保存目录
        """
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.save_dir / 'metrics.json'

        # 指标历史
        self.history = {
            'epochs': [],
            'train_loss': [],
            'val_metrics': []
        }

        print(f"指标将保存到: {self.metrics_file}")

    def update(self, epoch, train_loss, val_metrics):
        """
        更新指标
        Args:
            epoch: 当前epoch
            train_loss: 训练损失
            val_metrics: 验证指标字典
        """
        self.history['epochs'].append(epoch)
        self.history['train_loss'].append(float(train_loss))
        self.history['val_metrics'].append(val_metrics)

        # 保存到文件
        self._save()

    def _save(self):
        """保存指标到JSON文件"""
        with open(self.metrics_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)

    def get_best_epoch(self, metric_name='mAP50'):
        """
        获取最佳epoch
        Args:
            metric_name: 指标名称
        Returns:
            best_epoch, best_value
        """
        if len(self.history['val_metrics']) == 0:
            return 0, 0.0

        best_idx = 0
        best_value = 0.0

        for i, metrics in enumerate(self.history['val_metrics']):
            value = metrics.get(metric_name, 0.0)
            if value > best_value:
                best_value = value
                best_idx = i

        best_epoch = self.history['epochs'][best_idx]
        return best_epoch, best_value


def print_training_progress(epoch, total_epochs, train_loss, val_metrics, elapsed_time):
    """
    打印训练进度
    Args:
        epoch: 当前epoch
        total_epochs: 总epoch数
        train_loss: 训练损失
        val_metrics: 验证指标
        elapsed_time: 已用时间（秒）
    """
    print("\n" + "="*70)
    print(f"Epoch [{epoch+1}/{total_epochs}]")
    print("-"*70)
    print(f"训练损失: {train_loss:.4f}")

    if val_metrics:
        print(f"验证指标:")
        for key, value in val_metrics.items():
            if isinstance(value, (int, float)):
                print(f"  {key}: {value:.4f}")

    # 时间信息
    hours = int(elapsed_time // 3600)
    minutes = int((elapsed_time % 3600) // 60)
    seconds = int(elapsed_time % 60)
    print(f"已用时间: {hours:02d}:{minutes:02d}:{seconds:02d}")

    print("="*70 + "\n")


if __name__ == '__main__':
    # 测试工具函数
    import tempfile

    print("测试工具函数")
    print("="*60)

    # 创建临时目录
    with tempfile.TemporaryDirectory() as tmpdir:
        # 测试检查点管理器
        print("\n1. 测试检查点管理器")
        ckpt_mgr = CheckpointManager(tmpdir, save_period=5)

        # 创建假的模型和优化器
        dummy_model = torch.nn.Linear(10, 2)
        dummy_optimizer = torch.optim.SGD(dummy_model.parameters(), lr=0.01)

        # 保存检查点
        test_metrics = {'mAP50': 0.85, 'mAP75': 0.70}
        ckpt_mgr.save_checkpoint(
            dummy_model, dummy_optimizer,
            epoch=9, metrics=test_metrics,
            is_best=True, is_last=True
        )

        # 测试TensorBoard
        print("\n2. 测试TensorBoard日志")
        logger = TensorBoardLogger(os.path.join(tmpdir, 'logs'), enabled=True)
        logger.log_metrics(0, 1.5, {'mAP50': 0.80})
        logger.close()

        # 测试早停
        print("\n3. 测试早停机制")
        early_stopping = EarlyStopping(patience=3)
        scores = [0.80, 0.82, 0.81, 0.81, 0.80]
        for i, score in enumerate(scores):
            should_stop = early_stopping(score)
            print(f"  Epoch {i}: score={score:.2f}, stop={should_stop}")

        # 测试指标跟踪
        print("\n4. 测试指标跟踪器")
        tracker = MetricsTracker(tmpdir)
        for i in range(5):
            tracker.update(i, 1.0 - i*0.1, {'mAP50': 0.7 + i*0.05})

        best_epoch, best_map = tracker.get_best_epoch()
        print(f"  最佳epoch: {best_epoch}, 最佳mAP: {best_map:.4f}")

    print("\n测试通过！")
