"""CSV export: password positions only, and no live formulas."""

import csv
from datetime import datetime

from pdf_unlocker.core.pdf_processor import Status, UnlockResult
from pdf_unlocker.core.results_exporter import ResultsExporter


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.reader(f))


def make_result(**kwargs):
    defaults = dict(
        filename="statement.pdf",
        status=Status.SUCCESS,
        password_index=2,
        timestamp=datetime(2026, 1, 24, 9, 30, 0),
        error_message=None,
        output_path="C:/docs/unlocked/unlocked_statement.pdf",
    )
    defaults.update(kwargs)
    return UnlockResult(**defaults)


def test_exports_password_position_not_the_secret(tmp_path):
    out = tmp_path / "report.csv"

    assert ResultsExporter.export_to_csv([make_result()], str(out))

    rows = read_csv(out)
    assert rows[0] == ResultsExporter.HEADER
    assert rows[1][2] == "#2"


def test_blank_password_cell_when_none_was_needed(tmp_path):
    out = tmp_path / "report.csv"
    ResultsExporter.export_to_csv([make_result(password_index=None)], str(out))

    assert read_csv(out)[1][2] == ""


def test_formula_injection_is_neutralised(tmp_path):
    """A filename is attacker-influenced; Excel would otherwise run it."""
    out = tmp_path / "report.csv"
    hostile = make_result(
        filename="=cmd|'/c calc'!A1.pdf",
        status=Status.FAILED,
        password_index=None,
        error_message="@SUM(1+9)*cmd",
    )

    ResultsExporter.export_to_csv([hostile], str(out))

    row = read_csv(out)[1]
    assert row[0].startswith("'=")
    assert row[4].startswith("'@")


def test_unwritable_target_returns_false(tmp_path):
    assert not ResultsExporter.export_to_csv(
        [make_result()], str(tmp_path / "no-such-dir" / "report.csv")
    )


def test_generated_filename_is_timestamped_and_scoped(tmp_path):
    name = ResultsExporter.generate_filename(str(tmp_path))

    assert name.endswith(".csv")
    assert "pdf_unlock_results_" in name
    assert str(tmp_path) in name
