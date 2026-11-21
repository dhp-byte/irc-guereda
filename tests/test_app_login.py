from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from meal_insight import auth

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("MEAL_LOGIN_REMOTE", "0")
    monkeypatch.delenv("MEAL_SETUP_TOKEN", raising=False)


def run():
    return AppTest.from_file(APP, default_timeout=60).run()


def test_first_run_setup_then_login():
    at = run()
    assert not at.exception
    assert [t for t in at.text_input if t.key == "setup_user"] and not at.sidebar.radio  # pas d'accès à l'app
    at.text_input(key="setup_user").set_value("admin")
    at.text_input(key="setup_name").set_value("Admin")
    at.text_input(key="setup_pw").set_value("MotDePasse123")
    at.text_input(key="setup_pw2").set_value("MotDePasse123")
    at.button(key="setup_submit").click().run()
    assert auth.has_users()
    assert [t for t in at.text_input if t.key == "login_user"]  # formulaire de connexion affiché
    at.text_input(key="login_user").set_value("admin")
    at.text_input(key="login_pw").set_value("mauvais")
    at.button(key="login_submit").click().run()
    assert at.error and not at.sidebar.radio
    at.text_input(key="login_pw").set_value("MotDePasse123")
    at.button(key="login_submit").click().run()
    assert not at.exception and at.sidebar.radio  # connecté : navigation visible


def test_setup_mismatch_refused():
    at = run()
    at.text_input(key="setup_user").set_value("admin")
    at.text_input(key="setup_pw").set_value("MotDePasse123")
    at.text_input(key="setup_pw2").set_value("Autre1234567")
    at.button(key="setup_submit").click().run()
    assert not auth.has_users() and at.error


def test_role_restrictions():
    auth.create_user("lect", "MotDePasse123", "lecteur")
    at = run()
    at.text_input(key="login_user").set_value("lect")
    at.text_input(key="login_pw").set_value("MotDePasse123")
    at.button(key="login_submit").click().run()
    at.sidebar.radio[0].set_value("settings").run()
    assert at.warning and not at.exception
    at.sidebar.radio[0].set_value("import").run()
    assert at.warning


def test_logout_returns_to_login():
    auth.create_user("anna", "MotDePasse123", "admin")
    at = run()
    at.text_input(key="login_user").set_value("anna")
    at.text_input(key="login_pw").set_value("MotDePasse123")
    at.button(key="login_submit").click().run()
    [b for b in at.sidebar.button if b.label == "Se déconnecter"][0].click().run()
    assert [t for t in at.text_input if t.key == "login_user"] and not at.sidebar.radio
