"""Results exporter for PDF unlock operations.

This module handles exporting unlock results to CSV format.
"""

import csv
import os
from datetime import datetime
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from .pdf_processor import UnlockResult


class ResultsExporter:
    """Exports PDF unlock results to CSV format."""

    @staticmethod
    def export_to_csv(results: List['UnlockResult'], output_path: str) -> bool:
        """Export results to CSV file.

        Args:
            results: List of UnlockResult objects.
            output_path: Path where CSV file should be saved.

        Returns:
            True if export successful, False otherwise.
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow([
                    'Filename',
                    'Status',
                    'Password Used',
                    'Timestamp',
                    'Error Message',
                    'Output Path'
                ])

                # Write results
                for result in results:
                    writer.writerow([
                        result.filename,
                        result.status,
                        result.password_used if result.password_used else '',
                        result.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                        result.error_message if result.error_message else '',
                        result.output_path if result.output_path else ''
                    ])

            return True
        except IOError as e:
            print(f"Error exporting results to CSV: {e}")
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
