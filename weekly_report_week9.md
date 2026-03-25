# Weekly Progress Report – Week 9

**Date:** 4 March 2026

---

## This Week

- Added hotkey settings to the Settings page (Aim Toggle, Calibrate, Lineup Switch), with a click-to-bind `KeyCaptureButton` widget; bindings saved to `app_settings.json`
- Added overlay display switches in Settings (FPS, Mode, AIM/FIRE, Target Info, Error Vector, Controller Params); switches now take effect immediately during tracking without restart
- Added error vector display on overlay showing directional pixel offset (→ ← ↑ ↓) to the locked target
- Redesigned overlay text using Microsoft YaHei font (via PIL) with a cleaner 4-row layout and white text
- Fixed FIRE status dot colour (was always grey, now green when active)
- Moved Advanced Mode toggle to the bottom of the Settings page
- Updated default config: `aim_point_y` 47 → 50, set ADRC as default controller with initial parameters

---

## 本周工作

- 在设置页新增热键配置（瞄准开关、校准、阵容切换），支持点击捕获按键绑定，配置持久化至 `app_settings.json`
- 在设置页新增覆盖层显示开关（FPS、模式、AIM/FIRE、目标信息、误差向量、控制器参数），开关在追踪运行中实时生效，无需重启
- 覆盖层新增误差向量显示，以方向箭头（→ ← ↑ ↓）展示准星与锁定目标的像素偏移量
- 重新设计覆盖层文字，采用微软雅黑字体（通过 PIL 渲染），改为简洁四行布局，文字颜色统一为白色
- 修复 FIRE 状态点颜色错误（原来始终为灰色，现在激活时正确显示为绿色）
- 将高级模式开关移至设置页底部
- 更新默认配置：`aim_point_y` 从 47 调整为 50，将 ADRC 设为默认控制器并配置初始参数
