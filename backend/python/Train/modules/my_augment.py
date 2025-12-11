"""
数据增强模块
包含各种图像增强方法，适配YOLO格式标注
"""
import cv2
import numpy as np
import random
from typing import Tuple, List


class BaseAugment:
    """增强基类，定义统一接口"""

    def __call__(self, image: np.ndarray, labels: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        对图像和标签进行增强
        Args:
            image: 图像数组 (H, W, 3)
            labels: 标注数组 (N, 5), 格式为 [class, x_center, y_center, width, height]
                   坐标为归一化值 [0, 1]
        Returns:
            增强后的图像和标签
        """
        raise NotImplementedError


class ResolutionReduce(BaseAugment):
    """
    随机降低分辨率增强
    模拟低画质输入，增强模型对远距离目标的识别能力
    从 Data_Augmentation_Example.py 迁移
    """

    def __init__(self, min_scale=0.25, max_scale=1.0, probability=0.5):
        """
        Args:
            min_scale: 最小缩放比例
            max_scale: 最大缩放比例
            probability: 应用增强的概率
        """
        self.min_scale = min_scale
        self.max_scale = max_scale
        self.probability = probability

    def __call__(self, image, labels):
        # 按概率决定是否应用增强
        if random.random() > self.probability:
            return image, labels

        h, w = image.shape[:2]
        # 随机选择缩放比例
        scale = random.uniform(self.min_scale, self.max_scale)

        if scale < 1.0:
            # 计算缩小后的尺寸
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))

            # 先缩小图像
            small = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # 再放大回原尺寸（模拟模糊效果）
            interpolation = random.choice([cv2.INTER_NEAREST, cv2.INTER_LINEAR])
            image = cv2.resize(small, (w, h), interpolation=interpolation)

        # 标签不需要改变（因为图像尺寸没变）
        return image, labels


class RandomHSV(BaseAugment):
    """
    随机HSV色彩增强
    在HSV色彩空间调整色调、饱和度、明度
    """

    def __init__(self, h_gain=0.015, s_gain=0.7, v_gain=0.4, probability=0.5):
        """
        Args:
            h_gain: 色调偏移范围（±h_gain）
            s_gain: 饱和度缩放范围（1-s_gain 到 1+s_gain）
            v_gain: 明度缩放范围（1-v_gain 到 1+v_gain）
            probability: 应用概率
        """
        self.h_gain = h_gain
        self.s_gain = s_gain
        self.v_gain = v_gain
        self.probability = probability

    def __call__(self, image, labels):
        if random.random() > self.probability:
            return image, labels

        # 随机生成HSV调整系数
        h_factor = 1 + random.uniform(-self.h_gain, self.h_gain)
        s_factor = 1 + random.uniform(-self.s_gain, self.s_gain)
        v_factor = 1 + random.uniform(-self.v_gain, self.v_gain)

        # 转换到HSV空间
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)

        # 调整HSV通道
        hsv[..., 0] *= h_factor  # H通道
        hsv[..., 1] *= s_factor  # S通道
        hsv[..., 2] *= v_factor  # V通道

        # 裁剪到合法范围
        hsv[..., 0] = np.clip(hsv[..., 0], 0, 179)  # H范围是0-179
        hsv[..., 1] = np.clip(hsv[..., 1], 0, 255)
        hsv[..., 2] = np.clip(hsv[..., 2], 0, 255)

        # 转换回BGR
        image = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

        # 标签不变
        return image, labels


class RandomFlip(BaseAugment):
    """
    随机翻转增强
    支持水平和垂直翻转，并相应调整标注框
    """

    def __init__(self, lr_prob=0.5, ud_prob=0.0):
        """
        Args:
            lr_prob: 水平翻转概率
            ud_prob: 垂直翻转概率
        """
        self.lr_prob = lr_prob
        self.ud_prob = ud_prob

    def __call__(self, image, labels):
        h, w = image.shape[:2]

        # 水平翻转
        if random.random() < self.lr_prob:
            image = cv2.flip(image, 1)  # 1表示水平翻转
            if len(labels) > 0:
                # 调整x坐标：x_new = 1 - x_old
                labels[:, 1] = 1.0 - labels[:, 1]

        # 垂直翻转
        if random.random() < self.ud_prob:
            image = cv2.flip(image, 0)  # 0表示垂直翻转
            if len(labels) > 0:
                # 调整y坐标：y_new = 1 - y_old
                labels[:, 2] = 1.0 - labels[:, 2]

        return image, labels


class RandomScale(BaseAugment):
    """
    随机缩放增强
    缩放图像并相应调整标注框
    """

    def __init__(self, scale_min=0.8, scale_max=1.2, probability=0.5):
        """
        Args:
            scale_min: 最小缩放比例
            scale_max: 最大缩放比例
            probability: 应用概率
        """
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.probability = probability

    def __call__(self, image, labels):
        if random.random() > self.probability:
            return image, labels

        h, w = image.shape[:2]

        # 随机缩放比例
        scale = random.uniform(self.scale_min, self.scale_max)

        # 缩放图像
        new_h, new_w = int(h * scale), int(w * scale)
        image_scaled = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

        # 创建画布（保持原尺寸）
        canvas = np.zeros((h, w, 3), dtype=np.uint8)

        # 计算粘贴位置（居中）
        y_offset = (h - new_h) // 2
        x_offset = (w - new_w) // 2

        # 处理缩放后图像超出画布的情况
        if new_h > h or new_w > w:
            # 裁剪超出部分
            crop_y = max(0, -y_offset)
            crop_x = max(0, -x_offset)
            crop_h = min(new_h, h + crop_y)
            crop_w = min(new_w, w + crop_x)
            image_scaled = image_scaled[crop_y:crop_h, crop_x:crop_w]
            y_offset = max(0, y_offset)
            x_offset = max(0, x_offset)
            new_h, new_w = image_scaled.shape[:2]

        # 粘贴到画布
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = image_scaled

        # 调整标注框
        if len(labels) > 0:
            # 缩放bbox
            labels[:, 1:5] *= scale  # x, y, w, h都缩放

            # 平移bbox（考虑offset）
            labels[:, 1] += x_offset / w  # x偏移
            labels[:, 2] += y_offset / h  # y偏移

            # 裁剪到[0,1]范围并过滤超出边界的框
            labels[:, 1:5] = np.clip(labels[:, 1:5], 0, 1)

            # 过滤掉面积过小的框
            box_areas = labels[:, 3] * labels[:, 4]
            labels = labels[box_areas > 0.001]

        return canvas, labels


class GaussianNoise(BaseAugment):
    """
    高斯噪声增强
    模拟低质量图像
    """

    def __init__(self, mean=0, std=5.0, probability=0.3):
        """
        Args:
            mean: 噪声均值
            std: 噪声标准差
            probability: 应用概率
        """
        self.mean = mean
        self.std = std
        self.probability = probability

    def __call__(self, image, labels):
        if random.random() > self.probability:
            return image, labels

        # 生成高斯噪声
        noise = np.random.normal(self.mean, self.std, image.shape).astype(np.float32)

        # 添加噪声并裁剪到合法范围
        image = image.astype(np.float32) + noise
        image = np.clip(image, 0, 255).astype(np.uint8)

        return image, labels


class MotionBlur(BaseAugment):
    """
    运动模糊增强
    模拟快速移动场景
    """

    def __init__(self, kernel_min=3, kernel_max=7, probability=0.3):
        """
        Args:
            kernel_min: 最小模糊核大小
            kernel_max: 最大模糊核大小
            probability: 应用概率
        """
        self.kernel_min = kernel_min
        self.kernel_max = kernel_max
        self.probability = probability

    def __call__(self, image, labels):
        if random.random() > self.probability:
            return image, labels

        # 随机核大小（奇数）
        kernel_size = random.randint(self.kernel_min//2, self.kernel_max//2) * 2 + 1

        # 创建运动模糊核
        kernel = np.zeros((kernel_size, kernel_size))
        kernel[kernel_size//2, :] = 1  # 水平方向模糊
        kernel = kernel / kernel_size

        # 随机旋转模糊方向
        angle = random.uniform(0, 360)
        center = (kernel_size // 2, kernel_size // 2)
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        kernel = cv2.warpAffine(kernel, rotation_matrix, (kernel_size, kernel_size))

        # 应用模糊
        image = cv2.filter2D(image, -1, kernel)

        return image, labels


class AugmentCompose:
    """
    增强组合器
    按顺序应用多个增强
    """

    def __init__(self, augments: List[BaseAugment]):
        """
        Args:
            augments: 增强列表
        """
        self.augments = augments

    def __call__(self, image, labels):
        """依次应用所有增强"""
        for aug in self.augments:
            image, labels = aug(image, labels)
        return image, labels


def create_augment_pipeline(config):
    """
    根据配置创建数据增强管道
    Args:
        config: TrainConfig配置对象
    Returns:
        AugmentCompose增强组合器
    """
    augments = []

    # 1. 几何变换（先做，因为会影响bbox）
    if config.use_geometric:
        augments.append(RandomFlip(
            lr_prob=config.flip_lr,
            ud_prob=config.flip_ud
        ))
        augments.append(RandomScale(
            scale_min=config.scale_min,
            scale_max=config.scale_max,
            probability=config.scale_prob
        ))

    # 2. 色彩增强（不影响bbox）
    if config.use_color_jitter:
        augments.append(RandomHSV(
            h_gain=config.hsv_h,
            s_gain=config.hsv_s,
            v_gain=config.hsv_v,
            probability=0.5
        ))

    # 3. 分辨率降低
    if config.use_resolution_reduce:
        augments.append(ResolutionReduce(
            min_scale=config.resolution_min_scale,
            max_scale=config.resolution_max_scale,
            probability=config.resolution_prob
        ))

    # 4. 噪声和模糊（最后做）
    if config.use_noise_blur:
        augments.append(GaussianNoise(
            std=config.gaussian_noise_std,
            probability=config.gaussian_noise_prob
        ))
        augments.append(MotionBlur(
            kernel_min=config.motion_blur_kernel_min,
            kernel_max=config.motion_blur_kernel_max,
            probability=config.motion_blur_prob
        ))

    print(f"创建数据增强管道，包含 {len(augments)} 个增强")
    return AugmentCompose(augments)


if __name__ == '__main__':
    # 测试数据增强
    from config import TrainConfig  # type: ignore

    # 创建测试图像和标签
    test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    test_labels = np.array([
        [0, 0.5, 0.5, 0.2, 0.3],  # class=0, 中心在(0.5,0.5), 大小(0.2,0.3)
        [1, 0.3, 0.3, 0.1, 0.1],
    ])

    # 创建增强管道
    config = TrainConfig()
    augment = create_augment_pipeline(config)

    # 应用增强
    aug_image, aug_labels = augment(test_image, test_labels)

    print(f"原始图像形状: {test_image.shape}")
    print(f"增强后图像形状: {aug_image.shape}")
    print(f"原始标签数量: {len(test_labels)}")
    print(f"增强后标签数量: {len(aug_labels)}")
    print("测试通过！")
