import pytest
from meal_insight import auth, config, db


def test_hash_verify_policy():
    h = auth.hash_password("Secret12345")
    assert auth.verify_password("Secret12345", h) and not auth.verify_password("secret12345", h)
    assert h != auth.hash_password("Secret12345")  # sel aléatoire
    for bad in ("court1", "uniquementlettres", "1234567890123"):
        with pytest.raises(auth.AuthError):
            auth.validate_password(bad, "bob")


def test_create_and_authenticate():
    assert not auth.has_users()
    auth.create_user("Admin.Test", "MotDePasse123", "admin", "Admin Test")
    assert auth.has_users()
    u = auth.authenticate("admin.test", "MotDePasse123")
    assert u["role"] == "admin" and u["full_name"] == "Admin Test"
    with pytest.raises(auth.AuthError):
        auth.create_user("admin.test", "MotDePasse123")  # doublon


def test_password_not_plaintext_and_audit():
    auth.create_user("alice", "MotDePasse123", "analyste")
    assert b"MotDePasse123" not in config.DB_PATH.read_bytes()
    auth.authenticate("alice", "MotDePasse123")
    with pytest.raises(auth.AuthError):
        auth.authenticate("alice", "mauvais")
    actions = [a["action"] for a in db.list_audit()]
    assert "login_reussi" in actions and "login_echec" in actions


def test_generic_error_unknown_vs_wrong():
    auth.create_user("bob", "MotDePasse123", "lecteur")
    msgs = set()
    for u, p in (("bob", "x"), ("inconnu", "x"), ("!!", "x")):
        with pytest.raises(auth.AuthError) as e:
            auth.authenticate(u, p)
        msgs.add(str(e.value))
    assert len(msgs) == 1


def test_lockout_and_unlock():
    auth.create_user("carl", "MotDePasse123", "lecteur")
    for _ in range(auth.MAX_FAILS):
        with pytest.raises(auth.AuthError):
            auth.authenticate("carl", "faux")
    with pytest.raises(auth.AuthError, match="Trop de tentatives"):
        auth.authenticate("carl", "MotDePasse123")  # même le bon mot de passe est refusé
    auth.set_password("carl", "NouveauMdp12345")  # réinitialisation admin lève le verrou
    assert auth.authenticate("carl", "NouveauMdp12345")["username"] == "carl"


def test_inactive_user_refused():
    auth.create_user("dina", "MotDePasse123", "lecteur")
    auth.set_active("dina", False)
    with pytest.raises(auth.AuthError):
        auth.authenticate("dina", "MotDePasse123")
