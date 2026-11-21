"""Page d'authentification : logo IRC, photos défilantes (droite -> gauche), formulaire identifiant / mot de passe."""
from __future__ import annotations

import base64
import hmac
import os
import re
import time

import streamlit as st

from . import auth, config, login_media
from .i18n import t

_CSS = """
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stHeader"],[data-testid="stToolbar"]{display:none !important}
.stApp{background:#FFF3C4}
.block-container{max-width:1100px;padding-top:1.2rem}
.mq{overflow:hidden;border-radius:14px;box-shadow:0 2px 10px rgba(26,17,16,.25)}
.track{display:flex;width:max-content;animation:mq-scroll %(dur)ss linear infinite}
.mq:hover .track{animation-play-state:paused}
.slide{flex:0 0 auto;width:300px;height:190px;margin-right:10px;background-size:cover;background-position:center}
@keyframes mq-scroll{from{transform:translateX(0)}to{transform:translateX(-50%%)}}
@media (prefers-reduced-motion:reduce){.track{animation:none}}
.login-head{text-align:center;margin:1.2rem 0 .4rem}
.login-head img{width:92px;border-radius:12px}
.login-head h1{font-size:1.55rem;margin:.6rem 0 0;color:#1A1110}
.login-head p{color:#5b4e4a;margin:.2rem 0 .4rem}
div[data-testid="stForm"]{background:#fff;border:1px solid #e6d9a8;border-radius:14px;padding:1.2rem}
.login-foot{text-align:center;font-size:.75rem;color:#6b5d57;margin-top:.8rem}
%(imgs)s
"""


@st.cache_resource(show_spinner=False)
def _slides() -> list[str]:
    return login_media.load_slides()


@st.cache_resource(show_spinner=False)
def _logo_uri() -> str:
    return "data:image/png;base64," + base64.b64encode(config.LOGO_PATH.read_bytes()).decode()


def _marquee_html() -> str:
    slides = _slides()
    imgs = "".join(f".s{i}{{background-image:url({u})}}" for i, u in enumerate(slides))
    css = re.sub(r"\s+", " ", _CSS % {"dur": max(20, len(slides) * 7), "imgs": imgs})
    one = "".join(f'<div class="slide s{i}"></div>' for i in range(len(slides)))
    return f'<style>{css}</style><div class="mq" aria-hidden="true"><div class="track">{one}{one}</div></div>'


def _setup_form(lang: str) -> None:
    st.subheader(t("setup_title", lang))
    token_required = os.environ.get("MEAL_SETUP_TOKEN")
    with st.form("setup"):
        user = st.text_input(t("username", lang), key="setup_user")
        name = st.text_input(t("full_name", lang), key="setup_name")
        pw = st.text_input(t("password", lang), type="password", key="setup_pw")
        pw2 = st.text_input(t("password2", lang), type="password", key="setup_pw2")
        token = st.text_input(t("setup_token", lang), type="password", key="setup_token") if token_required else ""
        ok = st.form_submit_button(t("setup_btn", lang), key="setup_submit", use_container_width=True)
    if not ok:
        return
    if token_required and not hmac.compare_digest(token.encode(), token_required.encode()):
        st.error(t("bad_token", lang))
    elif pw != pw2:
        st.error(t("pw_mismatch", lang))
    else:
        try:
            auth.create_user(user, pw, "admin", name, actor="setup")
            st.session_state["setup_done"] = True
            st.rerun()
        except auth.AuthError as exc:
            st.error(str(exc))


def _login_form(lang: str) -> None:
    if st.session_state.pop("setup_done", False):
        st.success(t("setup_ok", lang))
    if st.session_state.pop("expired", False):
        st.warning(t("expired", lang))
    with st.form("login"):
        username = st.text_input(t("username", lang), key="login_user", autocomplete="username")
        password = st.text_input(t("password", lang), type="password", key="login_pw", autocomplete="current-password")
        ok = st.form_submit_button(t("login_btn", lang), key="login_submit", use_container_width=True)
    if ok:
        try:
            st.session_state["user"] = auth.authenticate(username, password)
            st.session_state["last_active"] = time.time()
            st.rerun()
        except auth.AuthError as exc:
            st.error(str(exc))


def render_login() -> None:
    """Affiche la page de connexion puis interrompt le script (st.stop)."""
    st.markdown(_marquee_html(), unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        lang = st.radio("Langue / Language", ["fr", "en"], horizontal=True, key="lang_login",
                        index=["fr", "en"].index(st.session_state.get("ui_lang", "fr")),
                        format_func=lambda x: {"fr": "Français", "en": "English"}[x], label_visibility="collapsed")
        st.session_state["ui_lang"] = lang
        st.markdown(f'<div class="login-head"><img src="{_logo_uri()}" alt="IRC"/>'
                    f'<h1>IRC MEAL INSIGHT – Guéréda</h1><p>{t("login_sub", lang)}</p></div>', unsafe_allow_html=True)
        _login_form(lang) if auth.has_users() else _setup_form(lang)
        st.markdown(f'<div class="login-foot">{t("notice", lang)}<br>{t("credit", lang)}</div>', unsafe_allow_html=True)
    st.stop()
