"""PDF Unlocker Pro - application bootstrap.

Wires up DPI awareness, configuration and logging, then hands control to the
main window. Run it with: python -m pdf_unlocker
"""

import contextlib
import sys
from tkinter import messagebox

from pdf_unlocker.core.config_manager import ConfigManager
from pdf_unlocker.logging_config import setup_logging


def enable_dpi_awareness() -> None:
    """Ask Windows for per-monitor DPI awareness so text renders crisply.

    CustomTkinter also does this, but only once a window exists; setting it
    before any Tk call avoids a first-paint at the wrong scale. Failure is not
    worth reporting - the app simply renders as it would have anyway.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor v1
    except (AttributeError, OSError):
        with contextlib.suppress(AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()  # Vista/7/8 fallback


def main() -> int:
    """Application entry point.

    Returns:
        Process exit code: 0 on a normal close, 1 on a fatal error.
    """
    enable_dpi_awareness()

    config_manager = ConfigManager()
    logger = setup_logging(config_manager.get_log_dir())
    logger.info("PDF Unlocker Pro starting")

    # Imported here so logging is configured before the UI module reports on
    # drag-and-drop availability.
    from pdf_unlocker.ui.main_window import MainWindow

    try:
        app = MainWindow(config_manager, logger)
        app.mainloop()
        logger.info("Application closed normally")
        return 0
    except Exception as e:
        logger.exception("Fatal error in main application")
        # No display available is fine; the log already has the traceback.
        with contextlib.suppress(Exception):
            messagebox.showerror(
                "Fatal Error",
                f"An unexpected error occurred:\n\n{e}\n\n"
                "Check the log file for details.",
            )
        return 1


if __name__ == "__main__":
    sys.exit(main())
