"""Configuration manager for PDF Unlocker application.

This module handles loading and saving application configuration using
platformdirs for cross-platform configuration file storage.
"""

import json
import os
from typing import Dict, Any
from platformdirs import user_config_dir, user_log_dir


class ConfigManager:
    """Manages application configuration persistence.

    Uses platformdirs to determine the appropriate configuration directory
    for the current platform (Windows, macOS, Linux).
    """

    def __init__(self, app_name: str = "PDFUnlocker", app_author: str = "PDFUnlockerPro"):
        """Initialize ConfigManager.

        Args:
            app_name: Application name for directory creation.
            app_author: Application author for directory creation (Windows).
        """
        self.app_name = app_name
        self.app_author = app_author
        self._config_dir = user_config_dir(app_name, app_author)
        self._log_dir = user_log_dir(app_name, app_author)
        self._config_file = os.path.join(self._config_dir, "config.json")

        # Ensure directories exist
        os.makedirs(self._config_dir, exist_ok=True)
        os.makedirs(self._log_dir, exist_ok=True)

    def get_config_path(self) -> str:
        """Return path to configuration file.

        Returns:
            Absolute path to config.json file.
        """
        return self._config_file

    def get_log_dir(self) -> str:
        """Return path to log directory.

        Returns:
            Absolute path to log directory.
        """
        return self._log_dir

    def get_config_dir(self) -> str:
        """Return path to config directory.

        Returns:
            Absolute path to config directory.
        """
        return self._config_dir

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file.

        Returns default configuration if file doesn't exist or is corrupted.

        Returns:
            Dictionary containing configuration settings.
        """
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}. Using defaults.")
                return self.get_default_config()
        else:
            return self.get_default_config()

    def save_config(self, config: Dict[str, Any]) -> None:
        """Save configuration to file.

        Args:
            config: Dictionary containing configuration settings.
        """
        try:
            with open(self._config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving config: {e}")

    def get_default_config(self) -> Dict[str, Any]:
        """Return default configuration.

        Returns:
            Dictionary with default configuration values.
        """
        return {
            "last_input_folder": os.path.expanduser("~"),
            "last_output_folder": os.path.expanduser("~"),
            "remember_passwords": False,
        }
