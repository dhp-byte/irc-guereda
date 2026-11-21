"""Chiffrement des secrets (clés API), masquage et suppression sécurisée de fichiers temporaires."""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from . import config


def _load_key() -> bytes:
    env = os.environ.get("MEAL_MASTER_KEY")
    if env:
        return env.strip().encode()
    config.ensure_dirs()
    if config.KEY_FILE.exists():
        return config.KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()  # mode développement local uniquement
    config.KEY_FILE.write_bytes(key)
    os.chmod(config.KEY_FILE, 0o600)
    return key


def encrypt(plaintext: str) -> str:
    return Fernet(_load_key()).encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return Fernet(_load_key()).decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Impossible de déchiffrer : clé principale (MEAL_MASTER_KEY) incorrecte.") from exc


def mask(secret: str, keep: int = 4) -> str:
    return "*" * 8 + secret[-keep:] if len(secret) > keep else "*" * 8


def secure_delete(path: str | Path) -> None:
    """Écrase puis supprime un fichier temporaire (ne jamais l'utiliser sur les extractions brutes)."""
    p = Path(path)
    if not p.exists():
        return
    try:
        size = p.stat().st_size
        os.chmod(p, 0o600)
        with open(p, "r+b") as f:
            f.write(os.urandom(size))
            f.flush()
            os.fsync(f.fileno())
    finally:
        p.unlink(missing_ok=True)
