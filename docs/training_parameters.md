# Training Parameters Guide

This document explains every parameter available on the **Training** page of Vision Tracker.

---

## 1. Dataset

| Field | Description |
|---|---|
| **Dataset YAML** | Path to the YOLO-format dataset config file (`.yaml`). Must contain `path`, `train`, `val`, and `names` fields. |
| **Pretrained Weights** | (Optional) Path to a `.pt` checkpoint for transfer learning. Leave empty to train from scratch. Using pretrained weights greatly speeds up convergence. |

---

## 2. Model Parameters

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Image Size** | `640` | 128–1280 (step 32) | Input resolution fed into the network. Larger values improve small-object detection but increase VRAM and training time. Must be a multiple of 32. |
| **Num Classes** | `4` | 1–100 | Number of object categories in your dataset. Must match the number of `names` in the YAML file. |

---

## 3. Class Configuration

After setting **Num Classes**, text fields appear for naming each class (e.g. `head`, `body`, `arm`, `leg`).
Click **Save** (floppy disk icon) to write `app/data/class_config.json`.
The **Custom Tracker** page reads this file to populate its Target dropdown.

> **Tip:** If you load a dataset YAML that contains class names, the fields are filled automatically.

---

## 4. Training Parameters

### Core

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Epochs** | `1000` | 1–2000 | Total number of training passes over the full dataset. More epochs allow better convergence but cost more time. Combined with early stopping, high values are safe. |
| **Batch Size** | `8` | 1–64 | Images processed per gradient update. Larger batches are more stable but need more VRAM. If you get CUDA OOM, halve this value. |
| **Num Workers** | `4` | 0–16 | DataLoader worker threads for parallel image loading. Set to `0` if you experience crashes on Windows. |
| **Learning Rate** | `0.01` | 0.0001–0.1 | Initial learning rate for the SGD optimizer. Too high → divergence; too low → slow convergence. Default works well with cosine annealing. |

### Optimizer (SGD)

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Weight Decay** | `0.0005` | 0.0–0.01 | L2 regularisation penalty to reduce overfitting. Increase slightly if the model overfits on small datasets. |
| **Momentum** | `0.937` | 0.8–0.999 | SGD momentum factor. Higher values smooth gradient updates across steps. Rarely needs tuning. |

### LR Schedule & Early Stopping

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Cosine Annealing LR** | `ON` | — | Decays learning rate following a cosine curve from `lr` to near 0 over the training run. Recommended — leave enabled. |
| **Warmup Epochs** | `3` | 0–20 | Gradually ramps the learning rate from 0 to the configured value during the first N epochs. Prevents early instability. |
| **Early Stop Patience** | `50` | 0–500 | Stop training automatically if validation mAP does not improve for this many consecutive epochs. Set to `0` to disable. |
| **Save Period** | `10` | 1–100 | Save a checkpoint every N epochs (in addition to the best model). Useful for resuming interrupted runs. |

---

## 5. Data Augmentation

Augmentation is applied on-the-fly during training only. It artificially expands the dataset variety to improve generalisation.

### Resolution Reduce

Randomly downsizes images before feeding them to the model, then pads back to the target size. Helps the model handle low-resolution or distant targets.

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Enable** | `ON` | — | Toggle the entire module. |
| **Min Scale** | `0.25` | 0.1–1.0 | Smallest resize factor. `0.25` means images can be shrunk to 25 % of original size. |
| **Max Scale** | `1.0` | 0.1–1.0 | Largest resize factor. Keep at `1.0` to allow full-resolution images. |
| **Probability** | `0.5` | 0.0–1.0 | Chance of applying resolution reduce to each image per batch. |

### Color Jitter (HSV)

Randomly shifts the hue, saturation, and brightness of images. Helps generalise across different lighting and monitor conditions.

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Enable** | `ON` | — | Toggle the entire module. |
| **Hue (H)** | `0.015` | 0.0–0.1 | Max shift in hue (colour tint). Small values like `0.015` are subtle; increase only if your targets vary widely in colour. |
| **Saturation (S)** | `0.7` | 0.0–1.0 | Max multiplicative change in saturation (colour intensity). High values create dramatic colour shifts. |
| **Value (V)** | `0.4` | 0.0–1.0 | Max multiplicative change in brightness. Helps handle bright/dark scenes. |

### Geometric Transforms

Applies flips, rotations, and scaling to teach the model to detect targets at different orientations and distances.

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Enable** | `ON` | — | Toggle the entire module. |
| **Flip LR Prob** | `0.5` | 0.0–1.0 | Probability of horizontal (left-right) flip per image. `0.5` means half of images are mirrored. |
| **Flip UD Prob** | `0.0` | 0.0–1.0 | Probability of vertical (up-down) flip. Usually kept at `0` for top-down fixed-camera scenes. |
| **Rotate Degree** | `15` | 0–180 | Maximum rotation angle in degrees (randomly sampled from `-degree` to `+degree`). |
| **Rotate Prob** | `0.3` | 0.0–1.0 | Probability of applying rotation to each image. |
| **Scale Min** | `0.8` | 0.1–1.0 | Minimum zoom-out factor. `0.8` means objects can appear 20 % smaller. |
| **Scale Max** | `1.2` | 1.0–2.0 | Maximum zoom-in factor. `1.2` means objects can appear 20 % larger. |
| **Scale Prob** | `0.5` | 0.0–1.0 | Probability of applying random scaling to each image. |

### Noise & Blur

Simulates sensor noise and motion artefacts, improving robustness on degraded footage.

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Enable** | `ON` | — | Toggle the entire module. |
| **Gaussian Prob** | `0.3` | 0.0–1.0 | Probability of adding Gaussian (random pixel) noise to an image. |
| **Gaussian Std** | `5.0` | 0.0–50.0 | Standard deviation of the noise distribution. Higher = noisier. Values above `20` may hurt accuracy. |
| **Motion Blur Prob** | `0.3` | 0.0–1.0 | Probability of applying motion blur (linear blur kernel). |
| **Blur Kernel Min** | `3` | 3–15 (odd) | Smallest motion blur kernel size in pixels. |
| **Blur Kernel Max** | `7` | 3–21 (odd) | Largest motion blur kernel size. Higher values create more pronounced blur. |

### Mosaic

Combines 4 images into a single composite, dramatically increasing scene variety and forcing the model to detect small objects.

| Parameter | Default | Range | Description |
|---|---|---|---|
| **Enable** | `ON` | — | Toggle the entire module. Recommended for most datasets. |
| **Probability** | `0.5` | 0.0–1.0 | Fraction of training batches that use mosaic composition. |

---

## 6. Performance

| Parameter | Default | Description |
|---|---|---|
| **Mixed Precision (AMP)** | `ON` | Uses FP16 computation where safe, cutting VRAM usage roughly in half and speeding up training by ~30–50 % on modern NVIDIA GPUs. Requires CUDA. |
| **Image Cache** | `OFF` | Loads the entire dataset into RAM before training begins. Only enable for small datasets (< 5,000 images) that fit in RAM — dramatically speeds up data loading. |
| **Accumulation Steps** | `4` | 1–16 | Simulates a larger effective batch size by accumulating gradients over N steps before updating weights. Effective batch = `batch_size × steps`. Useful when VRAM limits batch size. |

---

## 7. Training Control

| Field | Default | Description |
|---|---|---|
| **Save Directory** | `app/models/user/` | Folder where training outputs (weights, logs, charts) are written. Defaults to the user models directory so trained models appear automatically in the Custom Tracker. |
| **Start** | — | Begins training with the current configuration. The progress bar, loss chart, and log output update in real time. |
| **Stop** | — | Gracefully stops training after the current epoch completes. The best checkpoint (`best.pt`) is preserved. |

---

## Quick-Start Recommendation

For a new dataset with ~1,000 images per class:

```
Epochs:          300
Batch Size:      8  (16 if GPU has ≥ 8 GB VRAM)
Image Size:      640
Learning Rate:   0.01
Warmup Epochs:   3
Patience:        50
AMP:             ON
Mosaic:          ON, Prob 0.5
Resolution:      ON, 0.25–1.0, Prob 0.5
Color Jitter:    ON (defaults)
Geometric:       ON (defaults)
Noise & Blur:    ON (defaults)
```

After training, click **Save** in Class Configuration so the Custom Tracker knows your class names.
