"""Configuration manager for PDF Unlocker application.

This module handles loading and saving application configuration using
platformdirs for cross-platform configuration file storage.
"""

import contextlib
import json
import logging
import os
import tempfile
from typing import Any

from platformdirs import user_config_dir, user_log_dir

# Child of the app logger, so records reach the rotating file handler that
# pdf_unlocker.setup_logging attaches to 'pdf_unlocker'. print() would be
# discarded entirely in the --noconsole PyInstaller build.
logger = logging.getLogger('pdf_unlocker.config')


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

    def load_config(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns default configuration if file doesn't exist or is corrupted.

        Returns:
            Dictionary containing configuration settings.
        """
        config = self.get_default_config()

        if not os.path.exists(self._config_file):
            return config

        try:
            with open(self._config_file, encoding='utf-8') as f:
                stored = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Could not read config: {e}. Using defaults.")
            return config

        if not isinstance(stored, dict):
            logger.warning("Config file is not an object. Using defaults.")
            return config

        # Merge over the defaults so a partial or hand-edited file cannot
        # leave a caller with a missing key.
        config.update(stored)
        return config

    def save_config(self, config: dict[str, Any]) -> None:
        """Save configuration to file.

        Args:
            config: Dictionary containing configuration settings.
        """
        # Write to a sibling temp file and replace, so an interrupted save
        # cannot leave a truncated config behind.
        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=self._config_dir, prefix="config.", suffix=".tmp"
            )
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, self._config_file)
        except OSError as e:
            logger.error(f"Could not save config: {e}")
            if tmp_path and os.path.exists(tmp_path):
                with contextlib.suppress(OSError):
                    os.remove(tmp_path)

    def get_default_config(self) -> dict[str, Any]:
        """Return default configuration.

        Returns:
            Dictionary with default configuration values.
        """
        return {
            "last_input_folder": os.path.expanduser("~"),
            "last_output_folder": os.path.expanduser("~"),
            "remember_passwords": False,
        }
