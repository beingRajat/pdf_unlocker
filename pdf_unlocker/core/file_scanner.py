"""PDF discovery helpers.

Kept free of any UI dependency so the scan rules can be tested directly.
"""

import logging
import os
from collections.abc import Iterable
from typing import Optional

from pdf_unlocker.core.pdf_processor import OUTPUT_DIR_NAME, OUTPUT_PREFIX

logger = logging.getLogger('pdf_unlocker.scanner')

PDF_EXTENSION = ".pdf"


def is_pdf(path: str) -> bool:
    """Return True if path looks like a PDF by extension."""
    return path.lower().endswith(PDF_EXTENSION)


def find_pdfs(
    folder: str,
    exclude_dirs: Optional[Iterable[str]] = None,
    exclude_prefix: str = OUTPUT_PREFIX,
) -> list[str]:
    """Recursively collect PDF paths under folder.

    The output folder is pruned from the walk, and files already carrying the
    unlocked prefix are ignored. Without this, unlocking a folder a second
    time picks up its own results and produces unlocked_unlocked_*.pdf.

    Args:
        folder: Root folder to scan.
        exclude_dirs: Directory names to skip at any depth. Defaults to the
            processor's output folder name.
        exclude_prefix: Filename prefix to skip. Pass "" to keep everything.

    Returns:
        Sorted list of absolute PDF paths.
    """
    if exclude_dirs is None:
        exclude_dirs = {OUTPUT_DIR_NAME}
    skip: set[str] = {d.lower() for d in exclude_dirs}

    found: list[str] = []
    try:
        for root, dirs, files in os.walk(folder):
            # Pruning dirs in place stops os.walk descending into them.
            dirs[:] = [d for d in dirs if d.lower() not in skip]

            for name in files:
                if not is_pdf(name):
                    continue
                if exclude_prefix and name.startswith(exclude_prefix):
                    continue
                found.append(os.path.abspath(os.path.join(root, name)))
    except OSError as e:
        logger.error(f"Folder scan error under {folder}: {e}")

    return sorted(found)
