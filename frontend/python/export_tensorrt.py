"""
TensorRT 引擎导出脚本
将 YOLO 模型导出为 TensorRT 引擎以加速推理

使用方法:
    python export_tensorrt.py

注意:
    - 需要 CUDA 和 TensorRT 支持
    - 导出过程需要 1-5 分钟
    - 生成的 .engine 文件仅适用于当前 GPU
"""

import torch
from ultralytics import YOLO
import os

def export_to_tensorrt(model_path, imgsz=640, half=True):
    """
    导出 YOLO 模型为 TensorRT 引擎

    Args:
        model_path: 原始模型路径 (.pt 文件)
        imgsz: 输入图像尺寸 (默认 640)
        half: 是否使用 FP16 半精度（推荐，速度更快）
    """
    print(f"开始导出模型: {model_path}")
    print(f"输入尺寸: {imgsz}x{imgsz}")
    print(f"使用半精度 (FP16): {half}")

    # 检查 CUDA 是否可用
    if not torch.cuda.is_available():
        print("警告: CUDA 不可用，TensorRT 优化效果可能不明显")
        return

    # 加载模型
    print("加载模型...")
    model = YOLO(model_path)

    # 导出为 TensorRT 引擎
    print("开始导出 TensorRT 引擎（这可能需要几分钟）...")
    print("- 正在优化网络结构...")
    print("- 正在编译 CUDA 内核...")

    try:
        # 导出参数:
        # format='engine': 导出为 TensorRT 引擎
        # half=True: 使用 FP16 半精度（2倍速度提升）
        # dynamic=False: 固定输入尺寸（更快）
        # simplify=True: 简化 ONNX 图
        model.export(
            format='engine',
            half=half,
            dynamic=False,
            simplify=True,
            workspace=4,  # TensorRT workspace size (GB)
            imgsz=imgsz,
        )

        # 默认输出文件名（ultralytics 自动生成）
        default_engine_path = model_path.replace('.pt', '.engine')

        # 自定义文件名：添加尺寸标识
        base_name = model_path.replace('.pt', '')
        custom_engine_path = f"{base_name}_{imgsz}.engine"

        # 重命名文件
        if os.path.exists(default_engine_path):
            if os.path.exists(custom_engine_path):
                os.remove(custom_engine_path)  # 删除旧文件
            os.rename(default_engine_path, custom_engine_path)
            engine_path = custom_engine_path
        else:
            engine_path = default_engine_path

        print(f"\n✅ 导出成功!")
        print(f"引擎文件: {engine_path}")
        print(f"文件大小: {os.path.getsize(engine_path) / 1024 / 1024:.2f} MB")
        print(f"输入尺寸: {imgsz}x{imgsz}")
        print(f"\n现在可以在 Demo08.py 中使用此引擎文件")

    except Exception as e:
        print(f"\n❌ 导出失败: {e}")
        print("\n可能的原因:")
        print("1. TensorRT 未安装或版本不兼容")
        print("2. CUDA 版本不匹配")
        print("3. GPU 内存不足")
        print("\n尝试安装 TensorRT: pip install tensorrt")

if __name__ == '__main__':
    # 配置
    MODEL_PATH = "models/best 12.23.pt"
    EXPORT_SIZES = [200]  # 可以导出多个尺寸，如 [320, 384, 480, 640]

    print("=" * 60)
    print("TensorRT 引擎导出工具")
    print("=" * 60)

    # 检查模型是否存在
    if not os.path.exists(MODEL_PATH):
        print(f"错误: 找不到模型文件 {MODEL_PATH}")
        print(f"当前目录: {os.getcwd()}")
        print("请确保模型文件在当前目录")
    else:
        print(f"\n将导出以下尺寸的引擎: {EXPORT_SIZES}")
        print("提示: 修改 EXPORT_SIZES 可自定义导出尺寸\n")

        for size in EXPORT_SIZES:
            print(f"\n{'='*60}")
            print(f"导出 {size}x{size} 引擎")
            print(f"{'='*60}")
            export_to_tensorrt(MODEL_PATH, imgsz=size, half=True)
            print()

        print("\n" + "=" * 60)
        print("全部导出完成！")
        print("=" * 60)
