# Vision Tracker User Guide

> Document version: 1.0  
> Scope: Current Vision Tracker desktop application  
> Language: English

---

## 1. Overview

Vision Tracker is a desktop application built with PyQt5, SiliconUI, YOLO, and custom control logic for real-time target detection and tracking.

Main capabilities include:

- Real-time target detection
- Auto aim / auto fire
- Configuration management
- Sensitivity calibration
- Overlay rendering
- Performance monitoring
- User system and admin tools
- Training and advanced pages

> [Screenshot Placeholder] Figure 1: Main window overview

---

## 2. Page Structure

The application uses a sidebar-based layout. Common pages include:

| Page | Purpose |
|---|---|
| Home | Start, pause, stop tracking; choose target window and team |
| Configuration | Adjust model, FOV, controller, trigger, crosshair, and overlay options |
| Performance Monitor | View FPS, lock state, session activity, and calibration output |
| Logs | Log page |
| Help | Documentation page |
| Settings | Hotkeys, overlay display options, advanced mode |
| User | Profile, email, password, avatar |
| About | App info and project credits |
| Admin | User management page, visible to admin only |
| Training | Dataset and training tools, visible in advanced mode |
| Custom Tracker | Advanced tracking controls, visible in advanced mode |

> [Screenshot Placeholder] Figure 2: Sidebar navigation

---

## 3. Quick Start

### 3.1 Launch the App

Recommended launch command:

```bash
python -m app.main
```

### 3.2 Sign In

When the app opens:

1. It may sign in automatically if a valid session exists.
2. Otherwise, the login layer appears.
3. After signing in, the main UI becomes available.

### 3.3 Recommended Basic Workflow

1. Open `Configuration`
2. Check the model path and important parameters
3. Return to `Home`
4. Select a configuration
5. Select a target window or fullscreen
6. Select target team
7. Press `Start`
8. Use the configured hotkey to enable aim
9. Use `Pause` or `Stop` when needed

> [Screenshot Placeholder] Figure 3: Recommended first-time workflow

---

## 4. Home Page

The Home page is the main runtime control page.

### 4.1 Configuration Selector

Used to choose the active configuration file.

- `Default` is usually selected automatically if present
- Saved configurations from the Configuration page appear here

### 4.2 Windows Selector

Used to choose the target window.

- `Fullscreen`: capture the full screen
- Other entries: capture a specific application window

Use the refresh button to rescan open windows.

### 4.3 Team Buttons

- `CT`: track CT targets only
- `T`: track T targets only
- `ALL`: do not filter by team

### 4.4 Runtime Buttons

- `Start`: start tracking
- `Pause`: pause tracking
- `Stop`: stop tracking

### 4.5 Console Output

The console panel displays:

- Startup status
- Model loading info
- Window target info
- Hotkey summary
- Calibration results
- Warnings and errors

> [Screenshot Placeholder] Figure 4: Home page controls

---

## 5. Configuration Page

This page is used to tune application behavior.

### 5.1 Model

- Select a `.pt` or `.engine` model
- TensorRT `.engine` models are usually faster at inference time

### 5.2 Operation Mode

Common modes include:

- `auto_trigger`
- `auto_aim`
- `auto_aim_fire`

### 5.3 Aim Part

- `Head`
- `Body`
- `Head Priority`

### 5.4 FOV Settings

FOV controls the region used for detection.

- `FOV Width`
- `FOV Height`
- `Aim Point Y`

Notes:

- Larger FOV: wider search area, but more distractions
- Smaller FOV: tighter focus, but easier to miss targets

### 5.5 Snap Settings

- `Threshold`
- `Sensitivity`
- `Cooldown`
- `Update Thr.`

### 5.6 Controller Settings

Available controller types:

- `LADRC`
- `PID`

Shared parameters usually include:

- `Deadzone`
- `Cooldown`
- `Error Thr.`

### 5.7 Crosshair and Overlay

You can adjust:

- Crosshair visibility
- Length
- Thickness
- Gap
- Color
- Center dot

### 5.8 Save Configuration

It is strongly recommended to save after changing important parameters.

> [Screenshot Placeholder] Figure 5: Configuration page sections

---

## 6. Calibration

Calibration estimates a more suitable sensitivity value automatically.

### 6.1 Start Calibration

Default hotkey:

```text
F6
```

### 6.2 Recommendations

Before calibration:

- Make sure the model is loaded
- Make sure a stable and visible target is present
- Avoid large camera movement
- Make sure the mouse driver is available

### 6.3 What Happens During Calibration

The app will:

- clear stale frames
- detect a visible target
- measure the offset
- move the mouse
- compare before and after error
- update sensitivity

### 6.4 Where to View Results

You can check the result in:

- `Console Output`
- `Performance Monitor`

> [Screenshot Placeholder] Figure 6: Calibration flow and result

---

## 7. Performance Monitor

This page shows trends and runtime status.

Current sections include:

- Tracker Status
- FPS
- Lock State
- Runtime
- FPS Trend
- Session Activity
- Calibration Output
- Recent Events

### 7.1 Lock State

`Lock State` shows whether a target is currently locked:

- `LOCKED`: a target is currently locked
- `IDLE`: no target is currently locked

### 7.2 Calibration Output

Shows:

- current or latest calibrated sensitivity
- current PID Kp

You can use the copy button to copy the sensitivity value.

> [Screenshot Placeholder] Figure 7: Performance Monitor page

---

## 8. Settings Page

Settings mainly controls hotkeys and overlay display options.

### 8.1 Hotkeys

Configurable actions:

- Aim Toggle
- Calibrate
- Lineup Switch

### 8.2 Overlay Display

You can enable or disable overlay items such as:

- Show FPS
- Show Mode
- Show AIM / FIRE
- Show Target Info
- Show Error Vector
- Show Controller Params

### 8.3 Advanced Mode

When enabled, the sidebar shows:

- Training
- Custom Tracker

> [Screenshot Placeholder] Figure 8: Settings page

---

## 9. User and Admin Pages

### 9.1 User Page

Regular users can:

- change username
- change password
- change email
- change avatar
- log out

### 9.2 Admin Page

Administrators can:

- view the user list
- search users
- create users
- edit users
- delete users
- review system statistics

> [Screenshot Placeholder] Figure 9: User and Admin pages

---

## 10. Training and Custom Tracker

These pages are usually used in advanced mode.

### 10.1 Training

Can be used for:

- dataset browsing
- class management
- training parameter setup

### 10.2 Custom Tracker

Can be used for:

- selecting another model
- selecting custom target classes
- adjusting runtime tracking behavior

> [Screenshot Placeholder] Figure 10: Training and Custom Tracker pages

---

## 11. Recommended First-Time Order

If you are using the app for the first time, this is a good sequence:

1. Confirm the model path in `Configuration`
2. Review controller type and FOV
3. Return to `Home`
4. Select target window
5. Start tracking
6. Test hotkeys
7. Run one calibration pass
8. Observe `Performance Monitor`
9. Fine-tune parameters and save

---

## 12. Troubleshooting

### 12.1 Model Fails to Load

Check:

- whether the path is correct
- whether the `.engine` file matches your TensorRT / CUDA runtime
- whether the file is corrupted

### 12.2 No Targets Detected

Check:

- target window selection
- FOV size
- model class compatibility
- team filter selection

### 12.3 LADRC Feels Unstable

Review:

- `Kp`
- `Alpha`
- `Deadzone`
- `Cooldown`
- `Error Thr.`

### 12.4 Calibration Looks Wrong

Check:

- scene stability
- whether the target is lost during calibration
- whether the mouse driver is available

### 12.5 Markdown Does Not Render in Help Page

Install dependencies:

```bash
pip install -r requirements.txt
```

Required libraries include:

- `markdown`
- `pygments`

---

## 13. Screenshot Placement

The following placeholder format is intentionally kept in this document:

```text
[Screenshot Placeholder] Figure X: description
```

Recommended screenshot folder:

```text
docs/help/images/
```

Then replace the placeholder with actual Markdown image syntax:

```markdown
![Home page screenshot](images/home_page.png)
```

---

## 14. Maintenance Notes

Whenever the application workflow changes, update both help documents:

- Chinese: `docs/help/vision_tracker_help_zh.md`
- English: `docs/help/vision_tracker_help_en.md`

The Help page will then display the updated content automatically.
