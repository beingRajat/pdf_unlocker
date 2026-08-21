"""Unlock-engine behaviour.

Each test here pins down a defect found in the January build, so a regression
shows up as a failure rather than as a wrong report to the user.
"""

import queue

import pikepdf
import pytest

from pdf_unlocker.core.pdf_processor import (
    MessageType,
    PDFProcessor,
    Status,
)


@pytest.fixture
def processor(logger):
    return PDFProcessor(logger, max_workers=2)


def drain(result_queue):
    """Split a run's queue into (results, completion)."""
    results, completion = [], None
    while not result_queue.empty():
        msg = result_queue.get()
        if msg.type == MessageType.RESULT:
            results.append(msg.data)
        elif msg.type == MessageType.COMPLETE:
            completion = msg.data
    return results, completion


def run(processor, files):
    q = queue.Queue()
    processor.process_batch([str(f) for f in files], ["pw1", "pw2"], q)
    return drain(q)


def test_user_password_unlocks_and_records_position(processor, make_pdf, tmp_path):
    locked = make_pdf("locked.pdf", user="pw2", owner="pw2")

    results, completion = run(processor, [locked])

    assert len(results) == 1
    result = results[0]
    assert result.status == Status.SUCCESS
    assert result.password_index == 2, "must record which password matched"
    assert result.password_label == "password #2"
    assert completion["success"] == 1

    output = tmp_path / "unlocked" / "unlocked_locked.pdf"
    assert output.exists()
    with pikepdf.open(output) as pdf:
        assert not pdf.is_encrypted, "output must be decrypted"


def test_password_value_never_appears_on_the_result(processor, make_pdf):
    """The result carries a position, never the secret itself."""
    locked = make_pdf("locked.pdf", user="pw1", owner="pw1")

    results, _ = run(processor, [locked])

    assert not hasattr(results[0], "password_used")
    assert "pw1" not in repr(results[0])


def test_unencrypted_pdf_is_skipped_not_claimed_as_success(processor, make_pdf, tmp_path):
    """Regression: an unencrypted file used to report Success with pw1.

    That put a password the file never had into the results pane and the CSV.
    """
    plain = make_pdf("plain.pdf")

    results, completion = run(processor, [plain])

    result = results[0]
    assert result.status == Status.SKIPPED
    assert result.password_index is None
    assert "Not encrypted" in result.error_message
    assert completion["skipped"] == 1
    assert completion["success"] == 0
    assert not (tmp_path / "unlocked").exists(), "nothing to write for a plain PDF"


def test_owner_locked_pdf_unlocks_without_a_user_password(processor, make_pdf, tmp_path):
    """Regression: permissions-only PDFs used to be unopenable.

    The empty user password was filtered out before any attempt, so these
    failed with "None of the provided passwords worked".
    """
    owner_locked = make_pdf("owner_only.pdf", user="", owner="ownerpw")

    results, completion = run(processor, [owner_locked])

    result = results[0]
    assert result.status == Status.SUCCESS
    assert result.password_index is None
    assert result.password_label == "no user password"
    assert completion["success"] == 1

    output = tmp_path / "unlocked" / "unlocked_owner_only.pdf"
    with pikepdf.open(output) as pdf:
        assert not pdf.is_encrypted


def test_wrong_passwords_fail_cleanly(processor, make_pdf):
    locked = make_pdf("locked.pdf", user="not-in-list", owner="not-in-list")

    results, completion = run(processor, [locked])

    result = results[0]
    assert result.status == Status.FAILED
    assert result.password_index is None
    assert result.error_message == "None of the provided passwords worked"
    assert completion["fail"] == 1


def test_missing_file_is_reported_not_raised(processor, tmp_path):
    results, completion = run(processor, [tmp_path / "ghost.pdf"])

    assert results[0].status == Status.FAILED
    assert "Validation error" in results[0].error_message
    assert completion["error"] is None


def test_mixed_batch_counts_each_category(processor, make_pdf):
    files = [
        make_pdf("a.pdf", user="pw1", owner="pw1"),
        make_pdf("b.pdf", user="pw2", owner="pw2"),
        make_pdf("c.pdf"),
        make_pdf("d.pdf", user="unknown", owner="unknown"),
    ]

    results, completion = run(processor, files)

    assert len(results) == 4
    assert completion["success"] == 2
    assert completion["skipped"] == 1
    assert completion["fail"] == 1
    assert completion["total"] == 4


def test_completion_is_emitted_even_when_the_batch_raises(processor, monkeypatch, make_pdf):
    """Regression: a worker exception used to strand the UI forever.

    process_batch had try/finally with no except, so nothing ever queued
    COMPLETE and the window stayed disabled in its processing state.
    """
    locked = make_pdf("locked.pdf", user="pw1", owner="pw1")

    def boom(*_args, **_kwargs):
        raise RuntimeError("submit exploded")

    q = queue.Queue()
    monkeypatch.setattr(
        "concurrent.futures.ThreadPoolExecutor.submit", boom
    )
    processor.process_batch([str(locked)], ["pw1"], q)

    _results, completion = drain(q)
    assert completion is not None, "COMPLETE must always be emitted"
    assert completion["error"] == "submit exploded"


def test_cancel_marks_remaining_work_skipped(processor, make_pdf):
    locked = make_pdf("locked.pdf", user="pw1", owner="pw1")
    processor.cancel_processing()

    results, completion = run(processor, [locked])

    assert completion["cancelled"] is False, "flag is cleared per batch"
    assert results[0].status == Status.SUCCESS
