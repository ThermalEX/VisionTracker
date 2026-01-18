"""Authentication configuration."""

import os
import json
from dataclasses import asdict
from typing import Optional

from .email_service import SMTPConfig


class AuthConfig:
    """Authentication configuration manager."""

    def __init__(self):
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(app_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        self.config_file = os.path.join(data_dir, 'auth_config.json')

    def get_smtp_config(self) -> SMTPConfig:
        """
        Get SMTP configuration.

        Priority:
        1. Environment variables
        2. Config file
        3. Default values
        """
        # Try environment variables first
        if os.environ.get('SMTP_HOST'):
            return SMTPConfig(
                host=os.environ.get('SMTP_HOST', 'smtp.qq.com'),
                port=int(os.environ.get('SMTP_PORT', 587)),
                username=os.environ.get('SMTP_USERNAME', ''),
                password=os.environ.get('SMTP_PASSWORD', ''),
                use_tls=os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true',
                sender_name=os.environ.get('SMTP_SENDER_NAME', 'Vision Tracker')
            )

        # Try config file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    smtp_config = config.get('smtp', {})
                    return SMTPConfig(**smtp_config)
            except Exception as e:
                print(f"Failed to load config file: {e}")

        # Return default config (will need to be configured)
        return SMTPConfig(
            host="smtp.qq.com",
            port=587,
            username="2210692765@qq.com",
            password="nyqmezbceydrecij",
            use_tls=True,
            sender_name="Vision Tracker"
        )

    def save_smtp_config(self, config: SMTPConfig) -> bool:
        """Save SMTP configuration to file."""
        try:
            data = {'smtp': asdict(config)}
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False
