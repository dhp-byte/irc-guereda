"""IRC MEAL INSIGHT – Guéréda : authentification, connexion CommCare, importation (phases 1-2)."""
import os
import sys
import time
from datetime import date, datetime, time as dtime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from meal_insight import auth, config, db, ingest, synthetic
from meal_insight.connectors.commcare import CommCareClient, CommCareError
from meal_insight.i18n import NAV, PHASE, t
from meal_insight.logging_setup import setup_logging
from meal_insight.login_page import render_login

st.set_page_config(page_title="IRC MEAL INSIGHT – Guéréda", page_icon="📊", layout="wide")
setup_logging()
db.init_db()

ACCESS = {"commcare": {"admin", "analyste"}, "import": {"admin", "analyste"}, "settings": {"admin"}}


def logout(reason: str = "logout") -> None:
    user = st.session_state.get("user")
    if user:
        db.log_action("deconnexion" if reason == "logout" else "session_expiree", user["username"], actor=user["username"])
    lang = st.session_state.get("ui_lang", "fr")
    st.session_state.clear()  # efface aussi les bases chargées en mémoire
    st.session_state["ui_lang"] = lang
    if reason == "expired":
        st.session_state["expired"] = True
    st.rerun()


def require_login() -> dict:
    user = st.session_state.get("user")
    if user:
        limit = int(os.environ.get("MEAL_SESSION_MINUTES", "30")) * 60
        if time.time() - st.session_state.get("last_active", time.time()) > limit:
            logout("expired")
        st.session_state["last_active"] = time.time()
        return user
    render_login()  # ne retourne pas (st.stop)


st.session_state.setdefault("datasets", {})
st.session_state.setdefault("forms", {})
user = require_login()


def client_from(name: str) -> CommCareClient:
    c = db.get_connection(name)
    return CommCareClient(c["server_url"], c["domain"], c["username"], c["api_key"])


def page_home(lang: str) -> None:
    logo_col, title_col = st.columns([1, 6], vertical_alignment="center")
    logo_col.image(str(config.LOGO_PATH), width=110)
    title_col.title("IRC MEAL INSIGHT – Guéréda")
    title_col.caption(t("tagline", lang))
    st.divider()
    a, b, c = st.columns(3)
    a.metric("Connexions" if lang == "fr" else "Connections", len(db.list_connections()))
    b.metric("Importations" if lang == "fr" else "Imports", len(db.list_imports(1000)))
    c.metric("Bases chargées" if lang == "fr" else "Loaded datasets", len(st.session_state["datasets"]))
    for label, df in st.session_state["datasets"].items():
        st.write(f"**{label}** : {len(df):,} lignes × {df.shape[1]} colonnes")


def page_commcare(lang: str) -> None:
    st.header(t("commcare", lang))
    with st.form("conn"):
        name = st.text_input("Nom de la connexion", placeholder="ex. IRC-Gueréda-2026")
        server = st.text_input("URL du serveur", "https://www.commcarehq.org")
        domain = st.text_input("Espace projet (Project Space)")
        cc_user = st.text_input("Utilisateur (e-mail CommCare)")
        key = st.text_input("Clé API", type="password")
        submitted = st.form_submit_button("Tester et enregistrer")
    if submitted:
        try:
            info = CommCareClient(server, domain, cc_user, key).test_connection()
            db.save_connection(name.strip(), server.strip(), domain.strip(), cc_user.strip(), key.strip())
            db.log_action("connexion_enregistree", f"{name} / {domain}", actor=user["username"])
            st.success(f"Connexion réussie ({info['applications']} application(s)). Clé API enregistrée chiffrée.")
        except (CommCareError, ValueError) as exc:
            st.error(str(exc))
    conns = db.list_connections()
    if not conns:
        st.info("Aucune connexion enregistrée.")
        return
    sel = st.selectbox("Connexion enregistrée", [c["name"] for c in conns])
    if st.button("Charger les formulaires disponibles"):
        try:
            with st.spinner("Lecture des applications…"):
                st.session_state["forms"][sel] = client_from(sel).list_forms()
        except (CommCareError, ValueError) as exc:
            st.error(str(exc))
    forms = st.session_state["forms"].get(sel)
    if forms:
        st.dataframe(pd.DataFrame(forms), use_container_width=True)


def page_import(lang: str) -> None:
    st.header(t("import", lang))
    source = st.radio("Source", ["CommCare HQ", "Démonstration (données fictives)"], horizontal=True)
    label = st.text_input("Nom de la base", "Base 1")
    c1, c2 = st.columns(2)
    start = c1.date_input("Début de période", date.today().replace(day=1))
    end = c2.date_input("Fin de période", date.today())
    if start > end:
        st.error("La date de début doit précéder la date de fin.")
        return
    conn_name = xmlns = None
    incremental = False
    if source == "CommCare HQ":
        conns = [c["name"] for c in db.list_connections()]
        if not conns:
            st.warning("Créez d'abord une connexion (menu Connexion CommCare HQ).")
            return
        conn_name = st.selectbox("Connexion", conns)
        forms = st.session_state["forms"].get(conn_name, [])
        if forms:
            opts = {f"{f['application']} › {f['module']} › {f['formulaire']}": f["xmlns"] for f in forms}
            xmlns = opts[st.selectbox("Formulaire", list(opts))]
        else:
            xmlns = st.text_input("xmlns du formulaire (ou chargez la liste)") or None
        incremental = st.checkbox("Mise à jour incrémentale (depuis la dernière importation)")
    else:
        n = st.slider("Nombre de soumissions fictives", 100, 5000, 600, 100)
        seed = st.number_input("Graine aléatoire", 0, 10**6, 42)
    if not st.button("Importer"):
        return
    try:
        with st.spinner("Importation en cours…"):
            if source == "CommCare HQ":
                prev = db.last_import(conn_name, xmlns) if incremental else None
                old = ingest.load_raw(prev["raw_path"]) if prev and prev.get("raw_path") else []
                new = client_from(conn_name).fetch_forms(
                    xmlns=xmlns, start=start, end=datetime.combine(end, dtime.max).replace(microsecond=0),
                    since=prev["watermark"] if prev else None)
                records = ingest.merge_records(old, new)
                src = "commcare"
            else:
                records, src = synthetic.generate_submissions(start, end, int(n), int(seed)), "demo"
            path, sha = ingest.save_raw(records, label)
            df = ingest.flatten_submissions(records)
        st.session_state["datasets"][label] = df
        db.record_import(label=label, source=src, connection_name=conn_name, form_xmlns=xmlns,
                         period_start=str(start), period_end=str(end), n_records=len(records),
                         raw_path=path, sha256=sha, watermark=ingest.watermark(records))
        db.log_action("importation", f"{label} · {src} · {len(records)} soumissions · sha256={sha[:12]}", actor=user["username"])
        st.success(f"{len(records):,} soumissions importées. Extraction brute archivée (lecture seule, SHA-256 {sha[:12]}…).")
        st.dataframe(df.head(50), use_container_width=True)
    except (CommCareError, ValueError, KeyError) as exc:
        st.error(str(exc))
    hist = db.list_imports(20)
    if hist:
        st.subheader("Historique des importations")
        st.dataframe(pd.DataFrame(hist).drop(columns=["raw_path"]), use_container_width=True)


def page_settings(lang: str) -> None:
    st.header(t("settings", lang))
    tab_users, tab_audit = st.tabs(["Utilisateurs", "Journal d'audit"])
    with tab_users:
        users = auth.list_users()
        st.dataframe(pd.DataFrame(users), use_container_width=True)
        with st.form("new_user", clear_on_submit=True):
            st.markdown("**Créer un utilisateur**")
            u = st.text_input("Identifiant")
            n = st.text_input("Nom complet")
            r = st.selectbox("Rôle", auth.ROLES, index=1)
            p = st.text_input("Mot de passe initial", type="password")
            if st.form_submit_button("Créer"):
                try:
                    auth.create_user(u, p, r, n, actor=user["username"])
                    st.success("Utilisateur créé.")
                    st.rerun()
                except auth.AuthError as exc:
                    st.error(str(exc))
        others = [x["username"] for x in users if x["username"] != user["username"]]
        if others:
            c1, c2, c3 = st.columns(3)
            target = c1.selectbox("Utilisateur", others)
            if c2.button("Activer / désactiver"):
                cur = next(x for x in users if x["username"] == target)
                auth.set_active(target, not cur["active"], actor=user["username"])
                st.rerun()
            newpw = c3.text_input("Nouveau mot de passe", type="password")
            if c3.button("Réinitialiser le mot de passe"):
                try:
                    auth.set_password(target, newpw, actor=user["username"])
                    st.success("Mot de passe modifié.")
                except auth.AuthError as exc:
                    st.error(str(exc))
    with tab_audit:
        audit = db.list_audit(200)
        st.dataframe(pd.DataFrame(audit) if audit else pd.DataFrame({"info": ["Journal vide"]}), use_container_width=True)


lang = st.session_state.get("ui_lang", "fr")
st.sidebar.image(str(config.LOGO_PATH), width=120)
st.sidebar.markdown("### IRC MEAL INSIGHT")
lang = st.sidebar.selectbox("Langue / Language", ["fr", "en"], index=["fr", "en"].index(lang),
                            format_func=lambda x: {"fr": "Français", "en": "English"}[x])
st.session_state["ui_lang"] = lang
page = st.sidebar.radio("Navigation", NAV, format_func=lambda k: t(k, lang), label_visibility="collapsed")
st.sidebar.divider()
st.sidebar.caption(f"👤 {user['full_name']} · {user['role']}")
if st.sidebar.button(t("logout", lang)):
    logout()

PAGES = {"home": page_home, "commcare": page_commcare, "import": page_import, "settings": page_settings}
if user["role"] not in ACCESS.get(page, set(auth.ROLES)):
    st.warning(t("denied", lang))
elif page in PAGES:
    PAGES[page](lang)
else:
    st.header(t(page, lang))
    st.info(t("coming", lang, n=PHASE[page]))
