"""PDF processing engine for unlocking password-protected PDFs.

This module handles the core PDF unlocking logic with multi-threading support.
"""

import os
import logging
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional, Callable
import pikepdf


class MessageType(Enum):
    """Types of messages sent through the queue."""
    PROGRESS = "progress"
    RESULT = "result"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class QueueMessage:
    """Message sent from worker threads to main thread."""
    type: MessageType
    data: any


@dataclass
class UnlockResult:
    """Result of a PDF unlock operation."""
    filename: str
    status: str  # "Success", "Failed", "Skipped"
    password_used: Optional[str]
    timestamp: datetime
    error_message: Optional[str] = None
    output_path: Optional[str] = None


class PDFProcessor:
    """Main PDF processing engine with multi-threading support."""

    def __init__(self, logger: logging.Logger, error_log_path: str):
        """Initialize PDFProcessor.

        Args:
            logger: Logger instance for debugging.
            error_log_path: Path to error log file.
        """
        self.logger = logger
        self.error_log_path = error_log_path
        self._cancel_flag = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._start_time = None

    def cancel_processing(self) -> None:
        """Signal cancellation and shutdown executor."""
        self.logger.info("Cancel requested")
        self._cancel_flag.set()

    def process_batch(
        self,
        files: List[str],
        passwords: List[str],
        result_queue: queue.Queue,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> None:
        """Process multiple PDF files with ThreadPoolExecutor.

        Args:
            files: List of file paths to process.
            passwords: List of passwords to try.
            result_queue: Queue for sending results to main thread.
            progress_callback: Optional callback for progress updates.
        """
        self._cancel_flag.clear()
        self._start_time = time.time()
        self._executor = ThreadPoolExecutor(max_workers=3)

        try:
            self.logger.info(
                f"Starting batch processing: {len(files)} files, "
                f"{len(passwords)} passwords"
            )

            # Submit all tasks
            futures = {}
            for i, file_path in enumerate(files):
                if self._cancel_flag.is_set():
                    break

                future = self._executor.submit(
                    self._process_single_file,
                    file_path,
                    passwords
                )
                futures[future] = (i, file_path)

            # Process results as they complete
            completed_count = 0
            success_count = 0
            fail_count = 0

            for future in as_completed(futures):
                if self._cancel_flag.is_set():
                    break

                i, file_path = futures[future]
                completed_count += 1

                try:
                    result = future.result()

                    # Track success/failure
                    if result.status == "Success":
                        success_count += 1
                    else:
                        fail_count += 1

                    # Send result to main thread
                    result_queue.put(QueueMessage(MessageType.RESULT, result))

                    # Send progress update
                    progress_data = {
                        'current': completed_count,
                        'total': len(files),
                        'success': success_count,
                        'fail': fail_count,
                        'eta': self._calculate_eta(completed_count, len(files))
                    }
                    result_queue.put(
                        QueueMessage(MessageType.PROGRESS, progress_data)
                    )

                except Exception as e:
                    self.logger.exception(f"Error processing {file_path}")
                    error_result = UnlockResult(
                        filename=os.path.basename(file_path),
                        status="Failed",
                        password_used=None,
                        timestamp=datetime.now(),
                        error_message=f"Unexpected error: {str(e)}"
                    )
                    result_queue.put(
                        QueueMessage(MessageType.RESULT, error_result)
                    )

            # Send completion message
            completion_data = {
                'total': len(files),
                'success': success_count,
                'fail': fail_count,
                'cancelled': self._cancel_flag.is_set()
            }
            result_queue.put(QueueMessage(MessageType.COMPLETE, completion_data))

            self.logger.info(
                f"Batch processing complete: {success_count} succeeded, "
                f"{fail_count} failed"
            )

        finally:
            self._executor.shutdown(wait=True)
            self._executor = None

    def _process_single_file(
        self,
        file_path: str,
        passwords: List[str]
    ) -> UnlockResult:
        """Process a single PDF file.

        Args:
            file_path: Path to PDF file.
            passwords: List of passwords to try.

        Returns:
            UnlockResult with processing outcome.
        """
        filename = os.path.basename(file_path)

        # Check for cancellation
        if self._cancel_flag.is_set():
            return UnlockResult(
                filename=filename,
                status="Skipped",
                password_used=None,
                timestamp=datetime.now(),
                error_message="Operation cancelled"
            )

        # Pre-processing validation
        try:
            self._validate_file(file_path)
        except Exception as e:
            return UnlockResult(
                filename=filename,
                status="Failed",
                password_used=None,
                timestamp=datetime.now(),
                error_message=f"Validation error: {str(e)}"
            )

        # Try unlocking
        try:
            return self._attempt_unlock(file_path, passwords)
        except pikepdf.PasswordError:
            return UnlockResult(
                filename=filename,
                status="Failed",
                password_used=None,
                timestamp=datetime.now(),
                error_message="None of the provided passwords worked"
            )
        except pikepdf.PdfError as e:
            self.logger.error(f"PDF error for {filename}: {e}")
            self._log_to_error_file(filename, str(e))
            return UnlockResult(
                filename=filename,
                status="Failed",
                password_used=None,
                timestamp=datetime.now(),
                error_message=f"PDF error: {str(e)}"
            )
        except OSError as e:
            self.logger.error(f"OS error for {filename}: {e}")
            return UnlockResult(
                filename=filename,
                status="Failed",
                password_used=None,
                timestamp=datetime.now(),
                error_message=f"File system error: {str(e)}"
            )
        except Exception as e:
            self.logger.exception(f"Unexpected error for {filename}")
            self._log_to_error_file(filename, str(e))
            return UnlockResult(
                filename=filename,
                status="Failed",
                password_used=None,
                timestamp=datetime.now(),
                error_message=f"Unexpected error: {str(e)}"
            )

    def _validate_file(self, file_path: str) -> None:
        """Validate file before processing.

        Args:
            file_path: Path to file.

        Raises:
            Exception: If validation fails.
        """
        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")

        if not os.access(file_path, os.R_OK):
            raise Exception(f"No read permission: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise Exception(f"File is empty: {file_path}")

    def _attempt_unlock(
        self,
        file_path: str,
        passwords: List[str]
    ) -> UnlockResult:
        """Attempt to unlock PDF with provided passwords.

        Args:
            file_path: Path to PDF file.
            passwords: List of passwords to try.

        Returns:
            UnlockResult with outcome.

        Raises:
            pikepdf.PasswordError: If all passwords fail.
        """
        filename = os.path.basename(file_path)
        output_folder = self._get_output_folder(file_path)
        output_path = os.path.join(output_folder, f"unlocked_{filename}")

        # Create output folder
        os.makedirs(output_folder, exist_ok=True)

        # Try each password
        for password in passwords:
            if self._cancel_flag.is_set():
                return UnlockResult(
                    filename=filename,
                    status="Skipped",
                    password_used=None,
                    timestamp=datetime.now(),
                    error_message="Operation cancelled"
                )

            try:
                pdf = pikepdf.open(file_path, password=password)
                pdf.save(output_path)
                pdf.close()

                return UnlockResult(
                    filename=filename,
                    status="Success",
                    password_used=password,
                    timestamp=datetime.now(),
                    output_path=output_path
                )
            except pikepdf.PasswordError:
                continue  # Try next password

        # No password worked
        raise pikepdf.PasswordError("All passwords failed")

    def _get_output_folder(self, input_file_path: str) -> str:
        """Get output folder path for unlocked file.

        Creates an "unlocked" subfolder in the same directory as input file.

        Args:
            input_file_path: Path to input PDF file.

        Returns:
            Path to output folder.
        """
        input_dir = os.path.dirname(input_file_path)
        return os.path.join(input_dir, "unlocked")

    def _calculate_eta(self, completed: int, total: int) -> str:
        """Calculate estimated time remaining.

        Args:
            completed: Number of files completed.
            total: Total number of files.

        Returns:
            ETA string (e.g., "2m 30s").
        """
        if completed == 0 or self._start_time is None:
            return "Calculating..."

        elapsed = time.time() - self._start_time
        avg_time_per_file = elapsed / completed
        remaining_files = total - completed
        eta_seconds = int(avg_time_per_file * remaining_files)

        if eta_seconds < 60:
            return f"{eta_seconds}s"
        elif eta_seconds < 3600:
            minutes = eta_seconds // 60
            seconds = eta_seconds % 60
            return f"{minutes}m {seconds}s"
        else:
            hours = eta_seconds // 3600
            minutes = (eta_seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def _log_to_error_file(self, filename: str, error: str) -> None:
        """Log detailed error to error_log.txt.

        Args:
            filename: Name of file that caused error.
            error: Error message.
        """
        try:
            with open(self.error_log_path, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().isoformat()
                f.write(f"{timestamp} | {filename} | {error}\n")
        except IOError:
            self.logger.error("Failed to write to error log file")
