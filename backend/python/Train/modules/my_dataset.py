"""
数据集加载模块
实现YOLO格式数据集的加载和预处理
"""
import os
import cv2
import numpy as np
import torch
from torch.utils.data import Dataset, DataLoader
from pathlib import Path
import yaml
from typing import Optional, Callable


class YOLODataset(Dataset):
    """
    YOLO格式数据集
    支持图像缓存、数据增强
    """

    def __init__(
        self,
        images_dir: str,
        labels_dir: str,
        img_size: int = 640,
        augment: Optional[Callable] = None,
        cache: bool = False
    ):
        """
        Args:
            images_dir: 图像目录路径
            labels_dir: 标签目录路径
            img_size: 图像大小
            augment: 数据增强函数
            cache: 是否缓存图像到内存
        """
        self.images_dir = Path(images_dir)
        self.labels_dir = Path(labels_dir)
        self.img_size = img_size
        self.augment = augment
        self.cache = cache

        # 获取所有图像路径
        self.image_files = self._get_image_files()
        print(f"找到 {len(self.image_files)} 张图像")

        # 图像缓存
        self.cached_images = {}
        if self.cache:
            print("开始缓存图像到内存...")
            self._cache_images()
            print(f"缓存完成，共 {len(self.cached_images)} 张图像")

    def _get_image_files(self):
        """获取所有图像文件路径"""
        image_formats = ['.jpg', '.jpeg', '.png', '.bmp']
        image_files = []

        for ext in image_formats:
            image_files.extend(self.images_dir.glob(f'*{ext}'))
            image_files.extend(self.images_dir.glob(f'*{ext.upper()}'))

        # 排序以保证顺序一致
        image_files = sorted(image_files)
        return image_files

    def _cache_images(self):
        """缓存所有图像到内存"""
        for img_path in self.image_files:
            image = cv2.imread(str(img_path))
            if image is not None:
                self.cached_images[str(img_path)] = image

    def _load_image(self, index: int) -> np.ndarray:
        """
        加载图像
        Args:
            index: 图像索引
        Returns:
            图像数组 (H, W, 3)
        """
        img_path = str(self.image_files[index])

        # 从缓存加载
        if self.cache and img_path in self.cached_images:
            image = self.cached_images[img_path].copy()
        else:
            # 从磁盘加载
            image = cv2.imread(img_path)
            if image is None:
                raise ValueError(f"无法加载图像: {img_path}")

        # 调整图像大小
        if image.shape[0] != self.img_size or image.shape[1] != self.img_size:
            image = cv2.resize(image, (self.img_size, self.img_size))

        return image

    def _load_labels(self, index: int) -> np.ndarray:
        """
        加载标签
        Args:
            index: 标签索引
        Returns:
            标签数组 (N, 5), 格式为 [class, x_center, y_center, width, height]
        """
        # 获取对应的标签文件路径
        img_path = self.image_files[index]
        label_path = self.labels_dir / f"{img_path.stem}.txt"

        labels = []
        if label_path.exists():
            with open(label_path, 'r') as f:
                for line in f:
                    # 解析YOLO格式：class x y w h
                    parts = line.strip().split()
                    if len(parts) == 5:
                        class_id = int(parts[0])
                        x, y, w, h = map(float, parts[1:])
                        labels.append([class_id, x, y, w, h])

        if len(labels) == 0:
            # 如果没有标签，返回空数组
            return np.zeros((0, 5), dtype=np.float32)

        return np.array(labels, dtype=np.float32)

    def __len__(self):
        """返回数据集大小"""
        return len(self.image_files)

    def __getitem__(self, index: int):
        """
        获取一个样本
        Args:
            index: 样本索引
        Returns:
            image: Tensor (3, H, W)
            labels: Tensor (N, 6), 格式为 [batch_idx, class, x, y, w, h]
            img_path: 图像路径（用于调试）
        """
        # 1. 加载图像
        image = self._load_image(index)

        # 2. 加载标签
        labels = self._load_labels(index)

        # 3. 数据增强
        if self.augment is not None:
            image, labels = self.augment(image, labels)

        # 4. 转换为Tensor
        # 图像：(H, W, C) -> (C, H, W)，并归一化到[0,1]
        image = torch.from_numpy(image).permute(2, 0, 1).float() / 255.0

        # 标签：添加batch_idx列（在collate_fn中会用到）
        if len(labels) > 0:
            # 格式：[batch_idx, class, x, y, w, h]
            labels_out = np.zeros((len(labels), 6), dtype=np.float32)
            labels_out[:, 0] = index  # batch_idx，会在collate_fn中重新赋值
            labels_out[:, 1:] = labels  # class, x, y, w, h
            labels_out = torch.from_numpy(labels_out)
        else:
            labels_out = torch.zeros((0, 6), dtype=torch.float32)

        return image, labels_out, str(self.image_files[index])


def collate_fn(batch):
    """
    自定义collate函数
    处理变长的标签（每张图的目标数量不同）

    Args:
        batch: 列表，每个元素是 (image, labels, img_path)

    Returns:
        images: Tensor (B, 3, H, W)
        labels: Tensor (M, 6), 所有batch的标签拼接，格式 [batch_idx, class, x, y, w, h]
        paths: 图像路径列表
    """
    images, labels, paths = zip(*batch)

    # 堆叠图像
    images = torch.stack(images, 0)

    # 处理标签
    for i, label in enumerate(labels):
        if len(label) > 0:
            label[:, 0] = i  # 设置batch_idx

    # 拼接所有标签
    labels = torch.cat(labels, 0) if len(labels) else torch.zeros((0, 6))

    return images, labels, paths


def create_dataloader(
    dataset: Dataset,
    batch_size: int,
    num_workers: int = 4,
    shuffle: bool = True,
    pin_memory: bool = True
) -> DataLoader:
    """
    创建DataLoader
    Args:
        dataset: 数据集
        batch_size: 批次大小
        num_workers: 工作线程数
        shuffle: 是否打乱
        pin_memory: 是否固定内存
    Returns:
        DataLoader
    """
    # 创建DataLoader
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=num_workers,
        shuffle=shuffle,
        pin_memory=pin_memory,
        collate_fn=collate_fn,
        persistent_workers=True if num_workers > 0 else False,  # 保持worker进程
        drop_last=False  # 保留最后不完整的batch
    )

    return dataloader


def load_dataset_config(yaml_path: str):
    """
    加载数据集配置文件
    Args:
        yaml_path: dataset.yaml路径
    Returns:
        配置字典
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"数据集配置文件不存在: {yaml_path}")

    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 转换相对路径为绝对路径
    data_dir = yaml_path.parent
    for key in ['train', 'val', 'test']:
        if key in config:
            # images路径
            config[f'{key}_images'] = str(data_dir / config[key])
            # labels路径
            config[f'{key}_labels'] = str(data_dir / config[key].replace('images', 'labels'))

    return config


if __name__ == '__main__':
    # 测试数据集加载
    import sys
    from pathlib import Path

    # 添加父目录到路径
    parent_dir = Path(__file__).parent.parent
    if str(parent_dir) not in sys.path:
        sys.path.insert(0, str(parent_dir))

    from config import TrainConfig
    from modules.my_augment import create_augment_pipeline

    # 加载配置
    config = TrainConfig()

    # 加载数据集配置
    dataset_config = load_dataset_config(config.data_yaml)
    print(f"数据集配置: {dataset_config}")

    # 创建增强
    augment = create_augment_pipeline(config)

    # 创建训练数据集
    train_dataset = YOLODataset(
        images_dir=dataset_config['train_images'],
        labels_dir=dataset_config['train_labels'],
        img_size=config.img_size,
        augment=augment,
        cache=config.cache_images
    )

    print(f"训练集大小: {len(train_dataset)}")

    # 测试获取一个样本
    image, labels, path = train_dataset[0]
    print(f"图像形状: {image.shape}")
    print(f"标签形状: {labels.shape}")
    print(f"图像路径: {path}")

    # 创建DataLoader
    train_loader = create_dataloader(
        train_dataset,
        batch_size=4,
        num_workers=0,  # 测试时用0
        shuffle=True,
        pin_memory=False
    )

    # 测试加载一个batch
    for images, labels, paths in train_loader:
        print(f"Batch images: {images.shape}")
        print(f"Batch labels: {labels.shape}")
        print(f"标签示例:\n{labels[:5]}")
        break

    print("测试通过！")
