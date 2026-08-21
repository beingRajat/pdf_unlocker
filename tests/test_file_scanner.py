"""Folder discovery rules."""

from pdf_unlocker.core.file_scanner import find_pdfs, is_pdf


def test_is_pdf_ignores_case():
    assert is_pdf("Statement.PDF")
    assert is_pdf("statement.pdf")
    assert not is_pdf("statement.pdfx")
    assert not is_pdf("notes.txt")


def test_finds_pdfs_recursively(tmp_path):
    (tmp_path / "a.pdf").touch()
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.pdf").touch()
    (tmp_path / "sub" / "notes.txt").touch()

    found = find_pdfs(str(tmp_path))

    assert [p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in found] == ["a.pdf", "b.pdf"]


def test_output_folder_is_excluded(tmp_path):
    """Regression: a second run used to pick up its own output.

    That produced unlocked/unlocked/unlocked_unlocked_*.pdf.
    """
    (tmp_path / "statement.pdf").touch()
    output = tmp_path / "unlocked"
    output.mkdir()
    (output / "unlocked_statement.pdf").touch()

    found = find_pdfs(str(tmp_path))

    assert len(found) == 1
    assert "statement.pdf" in found[0]
    assert "unlocked" not in found[0].replace(str(tmp_path), "")


def test_prefixed_files_are_excluded_even_outside_the_output_folder(tmp_path):
    (tmp_path / "unlocked_already.pdf").touch()
    (tmp_path / "fresh.pdf").touch()

    found = find_pdfs(str(tmp_path))

    assert len(found) == 1
    assert "fresh.pdf" in found[0]


def test_missing_folder_returns_empty_rather_than_raising(tmp_path):
    assert find_pdfs(str(tmp_path / "does-not-exist")) == []
