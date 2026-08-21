"""Results exporter for PDF unlock operations.

This module handles exporting unlock results to CSV format. The report
records which password matched by position, never the password itself.
"""

import csv
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pdf_unlocker.core.pdf_processor import UnlockResult

logger = logging.getLogger('pdf_unlocker.export')

# Excel and Calc treat a leading one of these as the start of a formula.
FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _sanitize(value: Any) -> str:
    """Neutralise spreadsheet formula injection in an exported cell.

    Filenames and PDF error strings are attacker-influenced. A file named
    "=cmd|'/c calc'!A1.pdf" would otherwise execute on open in Excel.
    """
    text = "" if value is None else str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


class ResultsExporter:
    """Exports PDF unlock results to CSV format."""

    HEADER = [
        'Filename',
        'Status',
        'Password Used',
        'Timestamp',
        'Error Message',
        'Output Path',
    ]

    @staticmethod
    def export_to_csv(results: list['UnlockResult'], output_path: str) -> bool:
        """Export results to CSV file.

        Args:
            results: List of UnlockResult objects.
            output_path: Path where CSV file should be saved.

        Returns:
            True if export successful, False otherwise.
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(ResultsExporter.HEADER)

                for result in results:
                    # Position only. The password itself is never written to
                    # disk, matching the masking in the UI.
                    if result.password_index is not None:
                        password_cell = f"#{result.password_index}"
                    else:
                        password_cell = ''

                    writer.writerow([
                        _sanitize(result.filename),
                        _sanitize(result.status),
                        password_cell,
                        result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        _sanitize(result.error_message),
                        _sanitize(result.output_path),
                    ])

            return True
        except (OSError, csv.Error, UnicodeError) as e:
            logger.error(f"Could not export results to {output_path}: {e}")
            return False

    @staticmethod
    def generate_filename(base_folder: str = None) -> str:
        """Generate timestamped filename for results CSV.

        Args:
            base_folder: Optional folder path. If None, uses current directory.

        Returns:
            Full path to CSV file with timestamp.
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"pdf_unlock_results_{timestamp}.csv"

        if base_folder:
            return os.path.join(base_folder, filename)
        return filename
