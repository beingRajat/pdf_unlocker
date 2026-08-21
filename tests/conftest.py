"""Shared fixtures. PDFs are generated in-process, so no binary test data."""

import logging
import pathlib
import sys

import pikepdf
import pytest

# Allow `pytest` from a clean checkout without installing the package first.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


@pytest.fixture
def logger():
    """A logger that stays silent during tests."""
    log = logging.getLogger("pdf_unlocker.test")
    log.addHandler(logging.NullHandler())
    log.propagate = False
    return log


@pytest.fixture
def make_pdf(tmp_path):
    """Build a one-page PDF, optionally encrypted.

    Args:
        name: Filename to create under tmp_path.
        user: User (open) password. "" leaves the document openable.
        owner: Owner (permissions) password.

    Passing neither user nor owner produces an unencrypted file.
    """

    def _make(name, user=None, owner=None):
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(200, 200))
        target = tmp_path / name
        if user is None and owner is None:
            pdf.save(target)
        else:
            pdf.save(
                target,
                encryption=pikepdf.Encryption(
                    user=user or "", owner=owner or "", R=6
                ),
            )
        return target

    return _make
