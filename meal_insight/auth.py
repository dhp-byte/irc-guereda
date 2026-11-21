"""Comptes utilisateurs : mots de passe hachés (scrypt + sel), verrouillage anti-force brute, rôles, audit.
Aucun compte par défaut : le premier administrateur est créé à la première utilisation ou en ligne de commande.

  python -m meal_insight.auth create-user NOM --role admin
  python -m meal_insight.auth reset-password NOM
  python -m meal_insight.auth list
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import os
import re
from datetime import datetime, timedelta, timezone

from . import db

ROLES = ("admin", "analyste", "lecteur")
MAX_FAILS = 5
LOCK_MINUTES = 15
_USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._@-]{2,63}$")
_N, _R, _P = 2 ** 14, 8, 1


class AuthError(Exception):
    """Échec d'authentification ou de gestion de compte (message affichable)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        h = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(h.hex(), digest)
    except (ValueError, TypeError):
        return False


_DUMMY_HASH = hash_password("mot-de-passe-factice-pour-temps-constant")


def normalize_username(username: str) -> str:
    u = (username or "").strip().lower()
    if not _USERNAME_RE.match(u):
        raise AuthError("Identifiant invalide : 3 à 64 caractères (lettres, chiffres, . _ @ -).")
    return u


def validate_password(password: str, username: str = "") -> None:
    problems = []
    if len(password) < 10:
        problems.append("au moins 10 caractères")
    if not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        problems.append("des lettres et des chiffres")
    if username and password.lower() == username.lower():
        problems.append("différent de l'identifiant")
    if problems:
        raise AuthError("Mot de passe trop faible : il faut " + ", ".join(problems) + ".")


def has_users() -> bool:
    with db.connect() as con:
        return con.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None


def create_user(username: str, password: str, role: str = "lecteur", full_name: str = "", actor: str = "system") -> None:
    u = normalize_username(username)
    if role not in ROLES:
        raise AuthError(f"Rôle inconnu : {role}.")
    validate_password(password, u)
    with db.connect() as con:
        if con.execute("SELECT 1 FROM users WHERE username=?", (u,)).fetchone():
            raise AuthError("Cet identifiant existe déjà.")
        con.execute("INSERT INTO users(username, full_name, role, pw_hash, created_at) VALUES(?,?,?,?,?)",
                    (u, full_name.strip(), role, hash_password(password), _now().isoformat(timespec="seconds")))
    db.log_action("utilisateur_cree", f"{u} ({role})", actor=actor)


def list_users() -> list[dict]:
    with db.connect() as con:
        rows = con.execute("SELECT username, full_name, role, active, last_login, created_at FROM users ORDER BY username")
        return [dict(r) for r in rows]


def set_password(username: str, password: str, actor: str = "system") -> None:
    u = normalize_username(username)
    validate_password(password, u)
    with db.connect() as con:
        cur = con.execute("UPDATE users SET pw_hash=?, failed_attempts=0, locked_until=NULL WHERE username=?",
                          (hash_password(password), u))
        if cur.rowcount == 0:
            raise AuthError("Utilisateur introuvable.")
    db.log_action("mot_de_passe_modifie", u, actor=actor)


def set_active(username: str, active: bool, actor: str = "system") -> None:
    u = normalize_username(username)
    with db.connect() as con:
        con.execute("UPDATE users SET active=?, failed_attempts=0, locked_until=NULL WHERE username=?", (int(active), u))
    db.log_action("utilisateur_active" if active else "utilisateur_desactive", u, actor=actor)


def authenticate(username: str, password: str) -> dict:
    """Retourne {username, full_name, role} ou lève AuthError (message volontairement générique)."""
    generic = AuthError("Identifiant ou mot de passe incorrect.")
    try:
        u = normalize_username(username)
    except AuthError:
        verify_password(password, _DUMMY_HASH)
        raise generic
    with db.connect() as con:
        row = con.execute("SELECT * FROM users WHERE username=?", (u,)).fetchone()
        user = dict(row) if row else None
        if user and user["locked_until"] and datetime.fromisoformat(user["locked_until"]) > _now():
            db.log_action("login_bloque", u, actor=u)
            raise AuthError("Trop de tentatives échouées. Réessayez dans quelques minutes.")
        ok = verify_password(password, user["pw_hash"] if user else _DUMMY_HASH) and bool(user and user["active"])
        if not ok:
            if user:
                fails = user["failed_attempts"] + 1
                locked = None
                if fails >= MAX_FAILS:
                    locked, fails = (_now() + timedelta(minutes=LOCK_MINUTES)).isoformat(timespec="seconds"), 0
                con.execute("UPDATE users SET failed_attempts=?, locked_until=? WHERE id=?", (fails, locked, user["id"]))
            con.commit()
            db.log_action("login_echec", u, actor=u)
            raise generic
        con.execute("UPDATE users SET failed_attempts=0, locked_until=NULL, last_login=? WHERE id=?",
                    (_now().isoformat(timespec="seconds"), user["id"]))
    db.log_action("login_reussi", u, actor=u)
    return {"username": user["username"], "full_name": user["full_name"] or user["username"], "role": user["role"]}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m meal_insight.auth")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user"); c.add_argument("username"); c.add_argument("--role", choices=ROLES, default="lecteur"); c.add_argument("--name", default="")
    r = sub.add_parser("reset-password"); r.add_argument("username")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    db.init_db()
    try:
        if a.cmd == "list":
            for u in list_users():
                print(f"{u['username']:<24}{u['role']:<10}{'actif' if u['active'] else 'inactif'}")
            return
        pw = getpass.getpass("Mot de passe : ")
        if pw != getpass.getpass("Confirmer : "):
            raise AuthError("Les mots de passe ne correspondent pas.")
        if a.cmd == "create-user":
            create_user(a.username, pw, a.role, a.name, actor="cli")
        else:
            set_password(a.username, pw, actor="cli")
        print("OK")
    except AuthError as exc:
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
