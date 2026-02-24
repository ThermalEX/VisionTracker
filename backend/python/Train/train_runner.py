"""
Subprocess entry point for training.
Reads a JSON config file, creates TrainConfig, and runs training.
Called by the GUI's TrainingManager via QProcess.

Usage: python train_runner.py <config.json>
"""

import sys
import json
import os

# Ensure unbuffered output for real-time progress
os.environ["PYTHONUNBUFFERED"] = "1"

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TrainConfig
from modules.my_trainer import train_model


def _patch_torch_save():
    """Fix Python 3.13 + ultralytics BytesIO compatibility bug.

    In Python 3.13, PyTorch's C++ ZipFile writer closes the underlying
    BytesIO in its destructor, causing 'I/O operation on closed file'
    when ultralytics' save_model() uses a BytesIO buffer with torch.save.
    This patch routes BytesIO saves through a temp file instead.
    """
    import io
    import tempfile
    import torch

    try:
        import ultralytics.utils.patches as _ul_patches
        _real_save = _ul_patches._torch_save

        def _safe_save(obj, f, *args, **kwargs):
            if isinstance(f, io.BytesIO):
                fd, tmp = tempfile.mkstemp(suffix='.pt.tmp')
                os.close(fd)
                try:
                    _real_save(obj, tmp, *args, **kwargs)
                    with open(tmp, 'rb') as tmp_f:
                        f.write(tmp_f.read())
                finally:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass
            else:
                _real_save(obj, f, *args, **kwargs)

        _ul_patches.torch_save = _safe_save
        torch.save = _safe_save
    except Exception as e:
        print(f"[WARN] Could not apply torch.save patch: {e}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python train_runner.py <config.json>", file=sys.stderr)
        sys.exit(1)

    config_path = sys.argv[1]

    # Read JSON config
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
    except Exception as e:
        print(f"Error reading config: {e}", file=sys.stderr)
        sys.exit(1)

    # Apply torch.save fix before ultralytics is used
    _patch_torch_save()

    # Create TrainConfig and override with GUI values
    config = TrainConfig(create_dirs=False)

    for key, value in config_dict.items():
        if hasattr(config, key) and value != "":
            setattr(config, key, value)

    # Round img_size up to the nearest multiple of 32 (YOLO requirement)
    config.img_size = max(32, ((config.img_size + 31) // 32) * 32)

    # Create directories after setting all values
    config.exp_dir = config._get_save_dir()
    os.makedirs(config.exp_dir, exist_ok=True)
    os.makedirs(os.path.join(config.exp_dir, 'weights'), exist_ok=True)
    if config.use_tensorboard:
        os.makedirs(os.path.join(config.exp_dir, 'logs'), exist_ok=True)

    # Print config
    config.print_config()

    # Run training
    try:
        results = train_model(config)
        print("\nTraining completed successfully.")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\nTraining interrupted.")
        sys.exit(1)
    except Exception as e:
        print(f"\nTraining error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == '__main__':
    main()
