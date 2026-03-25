# Vision Tracker 使用说明

> 文档版本：1.0  
> 适用范围：当前桌面端 Vision Tracker 程序  
> 语言：中文

---

## 1. 程序简介

Vision Tracker 是一个基于 PyQt5、SiliconUI、YOLO 和自定义控制器的实时目标检测与跟踪桌面程序。  
它主要包含以下能力：

- 实时目标检测
- 自动瞄准 / 自动开火
- 配置管理
- 灵敏度校准
- 覆盖面板显示
- 性能监控
- 用户系统与管理员页面
- 训练与高级功能页

> [截图占位] 图 1：程序主界面总览

---

## 2. 界面结构

程序左侧为导航栏，常见页面如下：

| 页面 | 作用 |
|---|---|
| Home | 启动、暂停、停止跟踪，选择窗口和队伍 |
| Configuration | 调整模型、FOV、控制器、开火、准星等参数 |
| Performance Monitor | 查看 FPS、锁定状态、会话活动、校准结果 |
| Logs | 日志页 |
| Help | 帮助文档 |
| Settings | 快捷键、覆盖层显示设置、高级模式 |
| User | 用户资料、邮箱、密码、头像 |
| About | 关于程序、项目来源、技术信息 |
| Admin | 用户管理，仅管理员可见 |
| Training | 数据集与训练工具，高级模式下可见 |
| Custom Tracker | 自定义跟踪器，高级模式下可见 |

> [截图占位] 图 2：左侧导航栏与页面入口

---

## 3. 快速开始

### 3.1 启动程序

推荐使用以下方式启动：

```bash
python -m app.main
```

### 3.2 登录

打开程序后：

1. 如果已有会话，程序可能自动登录。
2. 如果没有会话，会弹出登录层。
3. 输入账号密码后进入主界面。

### 3.3 基本使用流程

最常见的使用顺序如下：

1. 打开 `Configuration` 页面检查模型和参数
2. 返回 `Home`
3. 选择配置
4. 选择目标窗口或全屏
5. 选择目标队伍
6. 点击 `Start`
7. 按设定快捷键启用瞄准
8. 需要时使用 `Pause` / `Stop`

> [截图占位] 图 3：首次使用推荐流程

---

## 4. Home 页面操作

Home 页面是日常使用最频繁的页面。

### 4.1 Configuration 下拉框

用于选择当前要使用的配置文件。

- 如果存在 `Default`，通常会默认选中它
- 你在 `Configuration` 页保存的新配置也会出现在这里

### 4.2 Windows 下拉框

用于选择目标窗口。

- `Fullscreen`：全屏捕获
- 其他项：指定窗口捕获

右侧刷新按钮可以重新扫描当前打开的窗口。

### 4.3 队伍按钮

- `CT`：只跟踪 CT 类目标
- `T`：只跟踪 T 类目标
- `ALL`：不过滤队伍

### 4.4 控制按钮

- `Start`：启动跟踪
- `Pause`：暂停跟踪
- `Stop`：停止跟踪

### 4.5 Console Output

右侧终端区域会显示：

- 启动状态
- 模型加载情况
- 窗口目标信息
- 快捷键信息
- 校准结果
- 错误与警告

> [截图占位] 图 4：Home 页面操作区域

---

## 5. Configuration 页面说明

Configuration 页面用于配置程序运行参数。

### 5.1 模型相关

- 选择 `.pt` 或 `.engine` 模型文件
- TensorRT `.engine` 通常推理更快

### 5.2 模式相关

常见模式有：

- `auto_trigger`
- `auto_aim`
- `auto_aim_fire`

### 5.3 Aim Part

- `Head`
- `Body`
- `Head Priority`

### 5.4 FOV 设置

FOV 决定检测区域大小。

- `FOV Width`
- `FOV Height`
- `Aim Point Y`

说明：

- FOV 太大：检测范围更广，但更容易引入干扰
- FOV 太小：更聚焦，但容易丢目标

### 5.5 Snap 设置

- `Threshold`
- `Sensitivity`
- `Cooldown`
- `Update Thr.`

说明：

- Threshold 越小，越容易进入瞬移式修正
- Sensitivity 越大，Snap 越激进

### 5.6 Controller 设置

可切换：

- `LADRC`
- `PID`

共享参数通常包括：

- `Deadzone`
- `Cooldown`
- `Error Thr.`

### 5.7 准星与覆盖层

可以调整：

- 是否显示准星
- 准星长度
- 粗细
- 间距
- 颜色
- 中心点

### 5.8 保存配置

建议每次调完核心参数后保存，避免下次重新设置。

> [截图占位] 图 5：Configuration 页面参数分区

---

## 6. 校准功能

校准用于自动估算较合适的灵敏度。

### 6.1 开始校准

默认快捷键：

```text
F6
```

### 6.2 使用建议

校准前请确保：

- 模型已正常加载
- 当前有清晰、稳定、可识别的目标
- 画面尽量不要剧烈移动
- 鼠标驱动可用

### 6.3 校准过程现象

校准过程中程序会：

- 清空旧帧
- 检测当前目标
- 计算偏差
- 执行一次或多次移动
- 对比移动前后误差
- 更新灵敏度

### 6.4 校准结果查看

校准完成后可以在：

- `Console Output`
- `Performance Monitor`

中查看新的灵敏度值。

> [截图占位] 图 6：校准过程提示与校准结果

---

## 7. Performance Monitor 页面

该页面用于观察运行状态与趋势数据。

当前主要模块包括：

- Tracker Status
- FPS
- Lock State
- Runtime
- FPS Trend
- Session Activity
- Calibration Output
- Recent Events

### 7.1 Lock State

Lock State 表示当前是否已经锁定目标：

- `LOCKED`：当前已锁定目标
- `IDLE`：当前未锁定目标

### 7.2 Calibration Output

显示：

- 当前或最近一次校准灵敏度
- 当前 PID Kp

可以点击复制按钮，将灵敏度复制到剪贴板。

> [截图占位] 图 7：Performance Monitor 页面

---

## 8. Settings 页面

Settings 页面主要用于快捷键和显示配置。

### 8.1 快捷键

可以设置：

- Aim Toggle
- Calibrate
- Lineup Switch

### 8.2 Overlay Display

可以控制覆盖层显示内容，例如：

- Show FPS
- Show Mode
- Show AIM / FIRE
- Show Target Info
- Show Error Vector
- Show Controller Params

### 8.3 Advanced Mode

开启后会显示：

- Training
- Custom Tracker

> [截图占位] 图 8：Settings 页面

---

## 9. User 与 Admin 页面

### 9.1 User 页面

普通用户可以：

- 修改用户名
- 修改密码
- 修改邮箱
- 修改头像
- 退出登录

### 9.2 Admin 页面

管理员可以：

- 查看用户列表
- 搜索用户
- 新增用户
- 编辑用户
- 删除用户
- 查看系统统计

> [截图占位] 图 9：User 页面与 Admin 页面

---

## 10. Training 与 Custom Tracker 页面

这两页通常在高级模式下使用。

### 10.1 Training

可用于：

- 数据集浏览
- 类别管理
- 训练参数配置

### 10.2 Custom Tracker

可用于：

- 选择不同模型
- 自定义目标类别
- 调整实时追踪行为

> [截图占位] 图 10：Training 与 Custom Tracker 页面

---

## 11. 推荐操作顺序

如果你是第一次使用，建议按这个顺序：

1. 在 `Configuration` 中确认模型路径正确
2. 检查控制器类型和 FOV
3. 回到 `Home` 页面选择目标窗口
4. 启动跟踪
5. 测试快捷键是否正常
6. 进行一次校准
7. 在 `Performance Monitor` 中观察 FPS 与 Lock State
8. 再回到配置页微调参数

---

## 12. 常见问题排查

### 12.1 模型无法加载

检查：

- 模型路径是否正确
- `.engine` 是否与当前 TensorRT / CUDA 环境匹配
- 文件是否损坏

### 12.2 无法检测到目标

检查：

- 窗口是否选择正确
- FOV 是否过小
- 模型类别是否与目标一致
- 当前队伍筛选是否正确

### 12.3 LADRC 表现不稳定

建议优先检查：

- `Kp`
- `Alpha`
- `Deadzone`
- `Cooldown`
- `Error Thr.`

### 12.4 校准结果异常

检查：

- 当前画面是否稳定
- 校准时是否丢目标
- 鼠标驱动是否可用

### 12.5 帮助页无法正确显示 Markdown

请确认已安装依赖：

```bash
pip install -r requirements.txt
```

其中至少需要：

- `markdown`
- `pygments`

---

## 13. 截图替换说明

本文档中的以下提示位置可以替换为正式截图：

```text
[截图占位] 图 X：说明文字
```

建议将截图放入：

```text
docs/help/images/
```

然后在文档中改为：

```markdown
![Home 页面示意图](images/home_page.png)
```

---

## 14. 维护建议

每次程序功能变化后，建议同步更新这两份帮助文档：

- 中文：`docs/help/vision_tracker_help_zh.md`
- 英文：`docs/help/vision_tracker_help_en.md`

这样 `Help` 页就能自动读取最新内容。
