import logging
import pytest
from meal_insight import config, db, security
from meal_insight.logging_setup import RedactingFilter


def test_roundtrip_and_mask():
    tok = security.encrypt("secret-key-123")
    assert tok != "secret-key-123" and security.decrypt(tok) == "secret-key-123"
    assert security.mask("abcdefgh").endswith("efgh") and "abcd" not in security.mask("abcdefgh")


def test_wrong_key_rejected(monkeypatch):
    tok = security.encrypt("x")
    config.KEY_FILE.unlink()
    with pytest.raises(ValueError):
        security.decrypt(tok)


def test_api_key_never_plaintext_in_db():
    db.save_connection("c1", "https://www.commcarehq.org", "demo", "u@x.org", "SUPERSECRETKEY")
    assert b"SUPERSECRETKEY" not in config.DB_PATH.read_bytes()
    assert db.get_connection("c1")["api_key"] == "SUPERSECRETKEY"
    assert "api_key" not in db.list_connections()[0]


def test_log_redaction():
    rec = logging.LogRecord("x", logging.INFO, "", 0, "Authorization: ApiKey u:abc123 api_key=zzz", (), None)
    RedactingFilter().filter(rec)
    assert "abc123" not in rec.msg and "zzz" not in rec.msg


def test_secure_delete(tmp_path):
    f = tmp_path / "tmp.csv"
    f.write_text("données")
    security.secure_delete(f)
    assert not f.exists()
