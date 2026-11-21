"""SQLite : connexions (clé API chiffrée), historique des importations, journal d'audit."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config, security

SCHEMA = """
CREATE TABLE IF NOT EXISTS connections(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, server_url TEXT NOT NULL,
  domain TEXT NOT NULL, username TEXT NOT NULL, api_key_enc TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS imports(
  id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL, source TEXT NOT NULL, connection_name TEXT,
  form_xmlns TEXT, period_start TEXT, period_end TEXT, n_records INTEGER, raw_path TEXT, sha256 TEXT,
  watermark TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, actor TEXT, action TEXT NOT NULL, details TEXT);
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, full_name TEXT, role TEXT NOT NULL,
  pw_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, failed_attempts INTEGER NOT NULL DEFAULT 0,
  locked_until TEXT, last_login TEXT, created_at TEXT NOT NULL);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect():
    config.ensure_dirs()
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    with connect() as con:
        con.executescript(SCHEMA)


def log_action(action: str, details: str = "", actor: str = "local") -> None:
    with connect() as con:
        con.execute("INSERT INTO audit_log(ts, actor, action, details) VALUES(?,?,?,?)",
                    (_now(), actor, action, details))


def save_connection(name: str, server_url: str, domain: str, username: str, api_key: str) -> None:
    with connect() as con:
        con.execute(
            """INSERT INTO connections(name, server_url, domain, username, api_key_enc, created_at)
               VALUES(?,?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET server_url=excluded.server_url,
               domain=excluded.domain, username=excluded.username, api_key_enc=excluded.api_key_enc""",
            (name, server_url, domain, username, security.encrypt(api_key), _now()))


def list_connections() -> list[dict]:
    with connect() as con:
        rows = con.execute("SELECT id, name, server_url, domain, username, created_at FROM connections ORDER BY name")
        return [dict(r) for r in rows]


def get_connection(name: str) -> dict:
    """Retourne la connexion AVEC clé déchiffrée : à n'appeler qu'au moment de l'usage."""
    with connect() as con:
        row = con.execute("SELECT * FROM connections WHERE name=?", (name,)).fetchone()
    if row is None:
        raise KeyError(f"Connexion inconnue : {name}")
    d = dict(row)
    d["api_key"] = security.decrypt(d.pop("api_key_enc"))
    return d


def record_import(**kw) -> int:
    cols = ["label", "source", "connection_name", "form_xmlns", "period_start", "period_end",
            "n_records", "raw_path", "sha256", "watermark"]
    vals = [kw.get(c) for c in cols]
    with connect() as con:
        cur = con.execute(f"INSERT INTO imports({','.join(cols)}, created_at) VALUES({','.join('?'*len(cols))},?)",
                          (*vals, _now()))
        return cur.lastrowid


def list_imports(limit: int = 50) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM imports ORDER BY id DESC LIMIT ?", (limit,))]


def last_import(connection_name: str, form_xmlns: str | None) -> dict | None:
    with connect() as con:
        row = con.execute("SELECT * FROM imports WHERE connection_name=? AND IFNULL(form_xmlns,'')=IFNULL(?,'') "
                          "ORDER BY id DESC LIMIT 1", (connection_name, form_xmlns)).fetchone()
    return dict(row) if row else None


def list_audit(limit: int = 50) -> list[dict]:
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))]
