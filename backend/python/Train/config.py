"""
训练配置文件
集中管理所有超参数，方便调整
"""
import os


class TrainConfig:
    """训练配置类"""

    # ========== 数据相关 ==========
    # 数据集配置文件路径
    # data_yaml = "../DataCollection/data/dataset.yaml"
    data_yaml = "E:/BaiduNetdiskDownload/data/dataset.yaml"

    # 图像大小（正方形）
    img_size = 640

    # 批次大小（根据显存调整）
    batch_size = 8

    # 数据加载线程数
    num_workers = 4

    # 类别数量
    num_classes = 4

    # 类别名称
    class_names = ['ct_head', 'ct_body', 't_head', 't_body']

    # ========== 训练相关 ==========
    # 训练轮数
    epochs = 1000

    # 初始学习率
    learning_rate = 0.01

    # 权重衰减（L2正则化）
    weight_decay = 0.0005

    # SGD动量
    momentum = 0.937

    # 预训练模型路径（用于迁移学习）
    pretrained_weights = "yolo11m.pt"

    # ========== 数据增强开关 ==========
    # 分辨率降低增强
    use_resolution_reduce = True
    resolution_min_scale = 0.25
    resolution_max_scale = 1.0
    resolution_prob = 0.5

    # 色彩增强（HSV空间）
    use_color_jitter = True
    hsv_h = 0.015  # 色调偏移范围（±1.5%）
    hsv_s = 0.7    # 饱和度缩放（0.7-1.3倍）
    hsv_v = 0.4    # 明度缩放（0.6-1.4倍）

    # 几何变换
    use_geometric = True
    flip_lr = 0.5          # 水平翻转概率
    flip_ud = 0.0          # 垂直翻转概率（游戏场景通常不翻转）
    rotate_degree = 15     # 旋转角度范围（±15度）
    rotate_prob = 0.3      # 旋转概率
    scale_min = 0.8        # 最小缩放比例
    scale_max = 1.2        # 最大缩放比例
    scale_prob = 0.5       # 缩放概率

    # 噪声和模糊
    use_noise_blur = True
    gaussian_noise_prob = 0.3
    gaussian_noise_std = 5.0
    motion_blur_prob = 0.3
    motion_blur_kernel_min = 3
    motion_blur_kernel_max = 7

    # Mosaic增强
    use_mosaic = True
    mosaic_prob = 0.5  # Mosaic增强概率

    # ========== 性能优化 ==========
    # 混合精度训练（自动混合精度）
    use_amp = True

    # 梯度累积步数（模拟更大的batch size）
    accumulate_grad = 4  # 实际batch = batch_size * accumulate_grad

    # 图像缓存（小数据集可以全部加载到内存）
    cache_images = False

    # 固定内存加速GPU数据传输
    pin_memory = True

    # 梯度裁剪最大范数（防止梯度爆炸）
    grad_clip_norm = 10.0

    # ========== 学习率调度 ==========
    # 使用余弦退火学习率
    use_cos_lr = True

    # Warmup轮数（前几个epoch慢慢提升学习率）
    warmup_epochs = 3
    warmup_momentum = 0.8
    warmup_bias_lr = 0.1

    # ========== 早停和保存 ==========
    # 早停patience（验证指标多少轮不提升就停止）
    patience = 50

    # 保存目录
    save_dir = "runs/custom_train"

    # 实验名称
    exp_name = "exp"

    # 是否覆盖已有实验（True: 每次覆盖同一目录, False: 自动递增编号）
    exist_ok = False

    # 每N个epoch保存一次检查点
    save_period = 10

    # ========== 日志和可视化 ==========
    # 使用TensorBoard
    use_tensorboard = True

    # 打印频率（每N个batch打印一次）
    print_freq = 10

    # 是否保存训练过程图片
    save_plots = True

    # ========== 验证相关 ==========
    # 置信度阈值（预测时）
    conf_threshold = 0.001

    # NMS的IoU阈值
    iou_threshold = 0.6

    # 每张图最多保留多少个检测框
    max_det = 300

    def __init__(self, create_dirs=True):
        """初始化
        Args:
            create_dirs: 是否创建保存目录，默认为True
        """
        # 初始化exp_dir，避免AttributeError
        self.exp_dir = ""

        if create_dirs:
            # 生成完整的保存路径
            self.exp_dir = self._get_save_dir()

            # 创建必要的目录
            os.makedirs(self.exp_dir, exist_ok=self.exist_ok)
            os.makedirs(os.path.join(self.exp_dir, 'weights'), exist_ok=True)

            if self.use_tensorboard:
                os.makedirs(os.path.join(self.exp_dir, 'logs'), exist_ok=True)

    def _get_save_dir(self):
        """获取保存目录路径（自动递增实验编号）"""
        if self.exist_ok:
            return os.path.join(self.save_dir, self.exp_name)

        # 查找下一个可用的实验编号
        i = 1
        while True:
            exp_dir = os.path.join(self.save_dir, f"{self.exp_name}{i}")
            if not os.path.exists(exp_dir):
                return exp_dir
            i += 1

    def print_config(self):
        """打印配置信息"""
        print("\n" + "="*70)
        print(" "*25 + "Training Configuration")
        print("="*70)

        # 基本配置
        print(f"Dataset          : {self.data_yaml}")
        print(f"Image Size       : {self.img_size}x{self.img_size}")
        print(f"Batch Size       : {self.batch_size} (grad accumulation: {self.accumulate_grad})")
        print(f"Epochs           : {self.epochs}")
        print(f"Learning Rate    : {self.learning_rate}")
        print(f"Classes          : {self.num_classes} {self.class_names}")

        # 数据增强
        aug_list = []
        if self.use_resolution_reduce: aug_list.append("Resolution")
        if self.use_color_jitter: aug_list.append("Color")
        if self.use_geometric: aug_list.append("Geometric")
        if self.use_noise_blur: aug_list.append("Noise/Blur")
        if self.use_mosaic: aug_list.append("Mosaic")
        print(f"Augmentation     : {', '.join(aug_list) if aug_list else 'None'}")

        # 性能优化
        opt_list = []
        if self.use_amp: opt_list.append("AMP")
        if self.cache_images: opt_list.append("Cache")
        if self.pin_memory: opt_list.append("PinMemory")
        print(f"Optimization     : {', '.join(opt_list) if opt_list else 'None'}")

        # 统一路径斜杠方向
        normalized_path = self.exp_dir.replace('\\', '/')
        print(f"Save Directory   : {normalized_path}")
        print("="*70 + "\n")


# 创建默认配置实例
default_config = TrainConfig(create_dirs=False)


if __name__ == '__main__':
    # 测试配置
    config = TrainConfig()
    config.print_config()
