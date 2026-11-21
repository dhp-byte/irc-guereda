import pytest
from meal_insight import config, db


@pytest.fixture(autouse=True)
def tmp_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "KEY_FILE", tmp_path / ".k")
    monkeypatch.setattr(config, "LOG_PATH", tmp_path / "app.log")
    monkeypatch.delenv("MEAL_MASTER_KEY", raising=False)
    db.init_db()
