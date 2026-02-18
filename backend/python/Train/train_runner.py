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

    # Create TrainConfig and override with GUI values
    config = TrainConfig(create_dirs=False)

    for key, value in config_dict.items():
        if hasattr(config, key) and value != "":
            setattr(config, key, value)

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
