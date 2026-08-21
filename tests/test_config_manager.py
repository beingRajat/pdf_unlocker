"""Config persistence, including the corrupt-file paths."""

import json

import pytest

from pdf_unlocker.core.config_manager import ConfigManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """A ConfigManager rooted in tmp_path rather than the real user profile."""
    monkeypatch.setattr(
        "pdf_unlocker.core.config_manager.user_config_dir",
        lambda *_a, **_k: str(tmp_path / "config"),
    )
    monkeypatch.setattr(
        "pdf_unlocker.core.config_manager.user_log_dir",
        lambda *_a, **_k: str(tmp_path / "logs"),
    )
    return ConfigManager()


def test_defaults_when_no_file_exists(manager):
    config = manager.load_config()

    assert config["remember_passwords"] is False
    assert "last_input_folder" in config


def test_round_trip(manager):
    manager.save_config({"remember_passwords": True, "last_input_folder": "C:/docs"})

    config = manager.load_config()
    assert config["remember_passwords"] is True
    assert config["last_input_folder"] == "C:/docs"


def test_partial_file_is_merged_over_defaults(manager):
    with open(manager.get_config_dir() + "/config.json", "w", encoding="utf-8") as f:
        json.dump({"remember_passwords": True}, f)

    config = manager.load_config()

    assert config["remember_passwords"] is True
    assert "last_output_folder" in config, "missing keys must still be present"


def test_corrupt_json_falls_back_to_defaults(manager):
    with open(manager.get_config_dir() + "/config.json", "w", encoding="utf-8") as f:
        f.write("{not json at all")

    assert manager.load_config()["remember_passwords"] is False


def test_non_object_json_falls_back_to_defaults(manager):
    """A JSON list would make every later .get() raise AttributeError."""
    with open(manager.get_config_dir() + "/config.json", "w", encoding="utf-8") as f:
        json.dump(["unexpected"], f)

    assert isinstance(manager.load_config(), dict)


def test_save_leaves_no_temp_files_behind(manager, tmp_path):
    manager.save_config({"remember_passwords": False})

    leftovers = list((tmp_path / "config").glob("*.tmp"))
    assert leftovers == []
