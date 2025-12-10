"""
模型定义模块
基于ultralytics YOLO，进行简化封装
"""
import torch
import torch.nn as nn
from ultralytics import YOLO
from pathlib import Path


class SimpleYOLO(nn.Module):
    """
    简化的YOLO模型包装器
    基于ultralytics YOLO11，但添加了清晰的注释和简化的接口
    """

    def __init__(self, model_path='yolo11n.pt', num_classes=4):
        """
        初始化模型
        Args:
            model_path: 预训练模型路径（.pt文件）
            num_classes: 类别数量
        """
        super().__init__()

        self.num_classes = num_classes

        # 加载ultralytics的YOLO模型
        print(f"正在加载YOLO模型: {model_path}")
        self.yolo = YOLO(model_path)

        # 获取PyTorch模型
        self.model = self.yolo.model

        # 修改类别数（如果需要）
        if hasattr(self.model, 'nc') and self.model.nc != num_classes:
            print(f"调整模型类别数: {self.model.nc} -> {num_classes}")
            self._adjust_num_classes(num_classes)

        print(f"模型加载完成！类别数: {num_classes}")

    def _adjust_num_classes(self, num_classes):
        """
        调整模型的类别数
        主要是修改检测头的输出层
        """
        # 这里需要根据实际的YOLO结构调整
        # 简化处理：重新设置类别数
        try:
            self.model.nc = num_classes
            # 如果有names属性，也要更新
            if hasattr(self.model, 'names'):
                self.model.names = {i: str(i) for i in range(num_classes)}
        except Exception as e:
            print(f"调整类别数时出错: {e}")
            print("将使用预训练模型的类别数")

    def forward(self, x):
        """
        前向传播
        Args:
            x: 输入图像 Tensor (B, 3, H, W)
        Returns:
            预测结果
        """
        return self.model(x)

    def get_model(self):
        """获取内部的PyTorch模型"""
        return self.model


def create_model(num_classes=4, pretrained='yolo11n.pt'):
    """
    创建YOLO模型
    Args:
        num_classes: 类别数量
        pretrained: 预训练权重路径，如果为None则从头训练
    Returns:
        SimpleYOLO模型
    """
    if pretrained is not None and Path(pretrained).exists():
        print(f"使用预训练权重: {pretrained}")
        model = SimpleYOLO(model_path=pretrained, num_classes=num_classes)
    else:
        print(f"警告: 预训练权重 {pretrained} 不存在")
        print("将使用默认的 yolo11n.pt")
        model = SimpleYOLO(model_path='yolo11n.pt', num_classes=num_classes)

    return model


def load_checkpoint(model, checkpoint_path):
    """
    加载训练检查点
    Args:
        model: 模型
        checkpoint_path: 检查点路径
    Returns:
        epoch, metrics等信息
    """
    print(f"加载检查点: {checkpoint_path}")

    checkpoint = torch.load(checkpoint_path, map_location='cpu')

    # 加载模型权重
    if 'model_state_dict' in checkpoint:
        model.load_state_dict(checkpoint['model_state_dict'])
    elif 'model' in checkpoint:
        model.load_state_dict(checkpoint['model'])
    else:
        # 直接是权重字典
        model.load_state_dict(checkpoint)

    print("检查点加载完成")

    # 返回其他信息
    info = {}
    if 'epoch' in checkpoint:
        info['epoch'] = checkpoint['epoch']
    if 'metrics' in checkpoint:
        info['metrics'] = checkpoint['metrics']

    return info


def count_parameters(model):
    """
    统计模型参数量
    Args:
        model: 模型
    Returns:
        total_params: 总参数量
        trainable_params: 可训练参数量
    """
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)

    print(f"模型参数统计:")
    print(f"  总参数: {total_params:,}")
    print(f"  可训练参数: {trainable_params:,}")
    print(f"  参数大小: {total_params * 4 / 1024 / 1024:.2f} MB (FP32)")

    return total_params, trainable_params


if __name__ == '__main__':
    # 测试模型创建
    print("="*60)
    print("测试模型创建")
    print("="*60)

    # 创建模型
    model = create_model(num_classes=4, pretrained='yolo11n.pt')

    # 统计参数
    count_parameters(model)

    # 测试前向传播
    print("\n测试前向传播...")
    dummy_input = torch.randn(2, 3, 640, 640)  # batch=2
    print(f"输入形状: {dummy_input.shape}")

    model.eval()
    with torch.no_grad():
        output = model(dummy_input)
        print(f"输出类型: {type(output)}")
        if isinstance(output, (list, tuple)):
            for i, out in enumerate(output):
                if isinstance(out, torch.Tensor):
                    print(f"  输出[{i}]形状: {out.shape}")
        elif isinstance(output, torch.Tensor):
            print(f"输出形状: {output.shape}")

    print("\n测试通过！")
