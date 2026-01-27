"""Configuration Manager for Vision Tracker"""

import os
import json
from typing import Dict, Any, Optional, List

# Default configuration values
DEFAULT_CONFIG = {
    "name": "Default",
    # Basic Settings
    "model_path": "",
    "operation_mode": "auto_aim_fire",  # auto_trigger, auto_aim, auto_aim_fire
    "team": "T",  # T, CT

    # FOV Settings
    "fov_width": 200,
    "fov_height": 200,

    # Display Settings
    "show_overlay": True,
    "show_bbox": True,

    # Fire Settings
    "auto_click": True,
    "click_interval": 0.2,
    "click_radius_ratio": 1.1,
    "click_radius_min": 5,
    "click_radius_max": 50,
    "target_priority": "nearest",  # nearest, largest, highest_conf

    # Snap Settings
    "snap_threshold": 40,
    "snap_sensitivity": 2.2,
    "snap_cooldown": 0.2,
    "snap_update_threshold": 20,

    # PID Settings
    "pid_kp": 0.3,
    "pid_ki": 0.0,
    "pid_kd": 0.001,
    "deadzone": 0,
    "pid_cooldown": 0.05,
    "pid_error_threshold": 3,
}


class ConfigManager:
    """Manages configuration files for Vision Tracker."""

    def __init__(self, config_dir: str = None):
        if config_dir is None:
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_dir = os.path.join(app_dir, "data", "configs")

        self.config_dir = config_dir
        self._ensure_config_dir()
        self._current_config_name = None
        self._current_config = None

    def _ensure_config_dir(self):
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir)
        if not self.list_configs():
            self.save_config("Default", DEFAULT_CONFIG.copy())

    def _get_config_path(self, name: str) -> str:
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        return os.path.join(self.config_dir, f"{safe_name}.json")

    def list_configs(self) -> List[str]:
        configs = []
        if os.path.exists(self.config_dir):
            for filename in os.listdir(self.config_dir):
                if filename.endswith(".json"):
                    configs.append(filename[:-5])
        return sorted(configs)

    def load_config(self, name: str) -> Optional[Dict[str, Any]]:
        config_path = self._get_config_path(name)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for key, value in DEFAULT_CONFIG.items():
                        if key not in config:
                            config[key] = value
                    self._current_config_name = name
                    self._current_config = config
                    return config
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def save_config(self, name: str, config: Dict[str, Any]) -> bool:
        config_path = self._get_config_path(name)
        try:
            config["name"] = name
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self._current_config_name = name
            self._current_config = config
            return True
        except IOError:
            return False

    def delete_config(self, name: str) -> bool:
        if len(self.list_configs()) <= 1:
            return False
        config_path = self._get_config_path(name)
        if os.path.exists(config_path):
            try:
                os.remove(config_path)
                if self._current_config_name == name:
                    self._current_config_name = None
                    self._current_config = None
                return True
            except IOError:
                return False
        return False

    def create_config(self, name: str) -> bool:
        if name in self.list_configs():
            return False
        config = DEFAULT_CONFIG.copy()
        config["name"] = name
        return self.save_config(name, config)

    def get_current_config(self) -> Optional[Dict[str, Any]]:
        return self._current_config

    def get_current_config_name(self) -> Optional[str]:
        return self._current_config_name

    @staticmethod
    def get_default_config() -> Dict[str, Any]:
        return DEFAULT_CONFIG.copy()
