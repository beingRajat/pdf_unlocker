"""PDF Unlocker Pro - Main Entry Point

A professional desktop application for unlocking password-protected PDFs.
"""

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from tkinter import messagebox

# Enable DPI awareness on Windows for crisp rendering
if sys.platform == 'win32':
    try:
        import ctypes
        # Windows 8.1+ per-monitor DPI awareness
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            # Fallback for Windows Vista/7/8
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

from core.config_manager import ConfigManager
from ui.main_window import MainWindow


def setup_logging(log_dir: str) -> logging.Logger:
    """Configure application logger with rotation.

    Args:
        log_dir: Directory for log files.

    Returns:
        Configured logger instance.
    """
    # Create logger
    logger = logging.getLogger('pdf_unlocker')
    logger.setLevel(logging.DEBUG)

    # Create log directory if needed
    os.makedirs(log_dir, exist_ok=True)

    # File handler with rotation (5MB max, 5 backups)
    log_file = os.path.join(log_dir, 'pdf_unlocker.log')
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def main():
    """Main application entry point."""
    # Initialize configuration
    config_manager = ConfigManager()

    # Setup logging
    logger = setup_logging(config_manager.get_log_dir())
    logger.info("PDF Unlocker Pro starting...")

    try:
        # Create and run main window
        app = MainWindow(config_manager, logger)
        logger.info("Main window created")

        # Check for drag-and-drop availability
        try:
            import tkinterdnd2
            logger.info("Drag-and-drop support available")
        except ImportError:
            logger.warning("tkinterdnd2 not available - drag-and-drop disabled")
            messagebox.showwarning(
                "Limited Functionality",
                "Drag-and-drop support is not available. "
                "Please use the Browse buttons to select files."
            )

        app.mainloop()
        logger.info("Application closed normally")

    except Exception as e:
        logger.exception("Fatal error in main application")
        try:
            messagebox.showerror(
                "Fatal Error",
                f"An unexpected error occurred:\n\n{str(e)}\n\n"
                f"Check the log file for details."
            )
        except:
            pass
        sys.exit(1)


if __name__ == '__main__':
    main()
