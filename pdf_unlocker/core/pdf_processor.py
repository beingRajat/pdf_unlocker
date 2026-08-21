"""PDF processing engine for unlocking password-protected PDFs.

This module handles the core PDF unlocking logic with multi-threading support.

Passwords are never stored on a result, logged, or exported. A successful
unlock records only the 1-based *index* of the password that matched, so a
run can be audited without a secret reaching the screen, the log or the disk.
"""

import logging
import os
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import pikepdf

DEFAULT_MAX_WORKERS = 3

# Prefix applied to every unlocked file, and the name of the folder they go in.
OUTPUT_PREFIX = "unlocked_"
OUTPUT_DIR_NAME = "unlocked"


class MessageType(Enum):
    """Types of messages sent through the queue."""
    PROGRESS = "progress"
    RESULT = "result"
    COMPLETE = "complete"


class Status:
    """Result statuses. SKIPPED means no unlock was needed or attempted."""
    SUCCESS = "Success"
    FAILED = "Failed"
    SKIPPED = "Skipped"


@dataclass
class QueueMessage:
    """Message sent from worker threads to main thread."""
    type: MessageType
    data: Any


@dataclass
class UnlockResult:
    """Result of a PDF unlock operation.

    Attributes:
        password_index: 1-based position of the password that worked, or None
            when no password was needed (an owner-restricted PDF opens with an
            empty user password). Never holds the password itself.
    """
    filename: str
    status: str  # Status.SUCCESS / Status.FAILED / Status.SKIPPED
    password_index: Optional[int]
    timestamp: datetime
    error_message: Optional[str] = None
    output_path: Optional[str] = None

    @property
    def password_label(self) -> str:
        """Human-readable description of which password matched."""
        if self.status != Status.SUCCESS:
            return ""
        if self.password_index is None:
            return "no user password"
        return f"password #{self.password_index}"


class PDFProcessor:
    """Main PDF processing engine with multi-threading support."""

    def __init__(
        self,
        logger: logging.Logger,
        max_workers: int = DEFAULT_MAX_WORKERS
    ):
        """Initialize PDFProcessor.

        Args:
            logger: Logger instance. Errors go here and nowhere else.
            max_workers: Number of PDFs to process concurrently.
        """
        self.logger = logger
        self.max_workers = max(1, max_workers)
        self._cancel_flag = threading.Event()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._start_time = None

    def cancel_processing(self) -> None:
        """Signal cancellation.

        Sets the flag that workers poll; queued work is dropped and in-flight
        work stops at its next checkpoint. The executor itself is shut down by
        the finally block in process_batch.
        """
        self.logger.info("Cancel requested")
        self._cancel_flag.set()

    def process_batch(
        self,
        files: list[str],
        passwords: list[str],
        result_queue: queue.Queue,
    ) -> None:
        """Process multiple PDF files with ThreadPoolExecutor.

        Always emits exactly one COMPLETE message, even if the batch raises,
        so a caller polling the queue can never be left waiting forever.

        Args:
            files: List of file paths to process.
            passwords: List of passwords to try, in order.
            result_queue: Queue for sending results to main thread.
        """
        self._cancel_flag.clear()
        self._start_time = time.time()
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)

        completed_count = 0
        success_count = 0
        fail_count = 0
        skip_count = 0
        fatal_error: Optional[str] = None

        try:
            self.logger.info(
                f"Starting batch processing: {len(files)} files, "
                f"{len(passwords)} passwords, {self.max_workers} workers"
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
            for future in as_completed(futures):
                if self._cancel_flag.is_set():
                    break

                i, file_path = futures[future]
                completed_count += 1

                try:
                    result = future.result()
                except Exception as e:
                    self.logger.exception(f"Error processing {file_path}")
                    result = UnlockResult(
                        filename=os.path.basename(file_path),
                        status=Status.FAILED,
                        password_index=None,
                        timestamp=datetime.now(),
                        error_message=f"Unexpected error: {e}"
                    )

                if result.status == Status.SUCCESS:
                    success_count += 1
                elif result.status == Status.SKIPPED:
                    skip_count += 1
                else:
                    fail_count += 1

                result_queue.put(QueueMessage(MessageType.RESULT, result))

                progress_data = {
                    'current': completed_count,
                    'total': len(files),
                    'success': success_count,
                    'fail': fail_count,
                    'skipped': skip_count,
                    'eta': self._calculate_eta(completed_count, len(files))
                }
                result_queue.put(
                    QueueMessage(MessageType.PROGRESS, progress_data)
                )

        except Exception as e:
            # Never let the worker thread die without reporting COMPLETE, or
            # the UI would stay in its processing state indefinitely.
            self.logger.exception("Fatal error during batch processing")
            fatal_error = str(e)

        finally:
            if self._executor is not None:
                self._executor.shutdown(wait=True, cancel_futures=True)
                self._executor = None

            completion_data = {
                'total': len(files),
                'processed': completed_count,
                'success': success_count,
                'fail': fail_count,
                'skipped': skip_count,
                'cancelled': self._cancel_flag.is_set(),
                'error': fatal_error,
            }
            result_queue.put(QueueMessage(MessageType.COMPLETE, completion_data))

            self.logger.info(
                f"Batch processing complete: {success_count} succeeded, "
                f"{fail_count} failed, {skip_count} skipped"
            )

    def _process_single_file(
        self,
        file_path: str,
        passwords: list[str]
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
            return self._cancelled_result(filename)

        # Pre-processing validation
        try:
            self._validate_file(file_path)
        except OSError as e:
            return UnlockResult(
                filename=filename,
                status=Status.FAILED,
                password_index=None,
                timestamp=datetime.now(),
                error_message=f"Validation error: {e}"
            )

        # Try unlocking
        try:
            return self._attempt_unlock(file_path, passwords)
        except pikepdf.PasswordError:
            return UnlockResult(
                filename=filename,
                status=Status.FAILED,
                password_index=None,
                timestamp=datetime.now(),
                error_message="None of the provided passwords worked"
            )
        except pikepdf.PdfError as e:
            self.logger.error(f"PDF error for {filename}: {e}")
            return UnlockResult(
                filename=filename,
                status=Status.FAILED,
                password_index=None,
                timestamp=datetime.now(),
                error_message=f"PDF error: {e}"
            )
        except OSError as e:
            self.logger.error(f"OS error for {filename}: {e}")
            return UnlockResult(
                filename=filename,
                status=Status.FAILED,
                password_index=None,
                timestamp=datetime.now(),
                error_message=f"File system error: {e}"
            )
        except Exception as e:
            self.logger.exception(f"Unexpected error for {filename}")
            return UnlockResult(
                filename=filename,
                status=Status.FAILED,
                password_index=None,
                timestamp=datetime.now(),
                error_message=f"Unexpected error: {e}"
            )

    def _validate_file(self, file_path: str) -> None:
        """Validate file before processing.

        Args:
            file_path: Path to file.

        Raises:
            OSError: If the file is missing, unreadable or empty.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"No read permission: {file_path}")

        if os.path.getsize(file_path) == 0:
            raise OSError(f"File is empty: {file_path}")

    def _attempt_unlock(
        self,
        file_path: str,
        passwords: list[str]
    ) -> UnlockResult:
        """Attempt to unlock a PDF.

        Tries the empty password first. That distinguishes three cases which
        must not be conflated:

        * not encrypted at all -> nothing to do, report SKIPPED rather than
          claiming whichever password happened to be tried first
        * encrypted with an empty user password (owner/permissions-only
          restrictions) -> decrypt it, no user password is needed
        * encrypted with a user password -> try each supplied password in turn

        Args:
            file_path: Path to PDF file.
            passwords: List of passwords to try, in order.

        Returns:
            UnlockResult with outcome.

        Raises:
            pikepdf.PasswordError: If every password fails.
        """
        filename = os.path.basename(file_path)
        output_folder = self._get_output_folder(file_path)
        output_path = os.path.join(output_folder, f"{OUTPUT_PREFIX}{filename}")

        # Empty password: is the file encrypted at all, and does it need a
        # user password? Opening costs no more than the attempts below.
        try:
            with pikepdf.open(file_path) as pdf:
                if not pdf.is_encrypted:
                    return UnlockResult(
                        filename=filename,
                        status=Status.SKIPPED,
                        password_index=None,
                        timestamp=datetime.now(),
                        error_message="Not encrypted - no unlock needed"
                    )

                # Encrypted, but no user password: permissions-only lock.
                os.makedirs(output_folder, exist_ok=True)
                pdf.save(output_path)
                self.logger.info(f"Unlocked {filename} (no user password)")
                return UnlockResult(
                    filename=filename,
                    status=Status.SUCCESS,
                    password_index=None,
                    timestamp=datetime.now(),
                    output_path=output_path
                )
        except pikepdf.PasswordError:
            pass  # A user password is required - fall through and try them.

        # Try each supplied password, recording only its position.
        for index, password in enumerate(passwords, start=1):
            if self._cancel_flag.is_set():
                return self._cancelled_result(filename)

            try:
                # `with` guarantees the handle is released even if save()
                # fails, so a failed write cannot leave the file locked.
                with pikepdf.open(file_path, password=password) as pdf:
                    os.makedirs(output_folder, exist_ok=True)
                    pdf.save(output_path)

                self.logger.info(f"Unlocked {filename} with password #{index}")
                return UnlockResult(
                    filename=filename,
                    status=Status.SUCCESS,
                    password_index=index,
                    timestamp=datetime.now(),
                    output_path=output_path
                )
            except pikepdf.PasswordError:
                continue  # Try next password

        # No password worked
        raise pikepdf.PasswordError("All passwords failed")

    def _cancelled_result(self, filename: str) -> UnlockResult:
        """Build the result used for work abandoned by a cancel request."""
        return UnlockResult(
            filename=filename,
            status=Status.SKIPPED,
            password_index=None,
            timestamp=datetime.now(),
            error_message="Operation cancelled"
        )

    def _get_output_folder(self, input_file_path: str) -> str:
        """Get output folder path for unlocked file.

        Creates an "unlocked" subfolder in the same directory as input file.

        Args:
            input_file_path: Path to input PDF file.

        Returns:
            Path to output folder.
        """
        input_dir = os.path.dirname(input_file_path)
        return os.path.join(input_dir, OUTPUT_DIR_NAME)

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
