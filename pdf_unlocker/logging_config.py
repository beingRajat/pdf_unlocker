"""Application logging setup.

Everything under the 'pdf_unlocker' logger name flows through the handlers
configured here, including the child loggers the core modules use. Nothing in
the codebase writes diagnostics to stdout, because the packaged executable is
built with --noconsole and has nowhere to print to.
"""

import contextlib
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOGGER_NAME = "pdf_unlocker"
LOG_FILENAME = "pdf_unlocker.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_dir: str) -> logging.Logger:
    """Configure the application logger with rotation.

    Safe to call more than once: existing handlers are cleared first so a
    second call cannot duplicate every log line.

    Args:
        log_dir: Directory for log files.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    os.makedirs(log_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, LOG_FILENAME),
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Only useful when launched from a terminal; absent in the windowed build.
    if sys.stderr is not None:
        # A cp1252 console raises UnicodeEncodeError on a filename outside its
        # codepage, which would turn a log call into a crash.
        if hasattr(sys.stderr, "reconfigure"):
            with contextlib.suppress(OSError, ValueError):
                sys.stderr.reconfigure(errors="replace")
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
