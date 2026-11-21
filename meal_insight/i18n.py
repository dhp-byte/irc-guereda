"""Libellés FR/EN de l'interface."""
NAV = ["home", "commcare", "import", "explore", "clean", "dqa", "indicators", "compare", "viz",
       "donor", "reports", "history", "settings"]
PHASE = {"explore": 3, "clean": 4, "dqa": 4, "indicators": 5, "compare": 6, "viz": 7,
         "donor": 9, "reports": 8, "history": 8}

TEXTS = {
    "fr": {
        "home": "Accueil / Dashboard", "commcare": "Connexion CommCare HQ", "import": "Importation des données",
        "explore": "Exploration des bases", "clean": "Nettoyage des données", "dqa": "Data Quality Assessment",
        "indicators": "Indicateurs MEAL", "compare": "Analyse comparative", "viz": "Visualisation",
        "donor": "Donor Reporting", "reports": "Génération des rapports", "history": "Historique des rapports",
        "settings": "Paramètres (utilisateurs, audit)", "language": "Langue", "coming": "Module prévu en phase {n}.",
        "tagline": "Suivi, évaluation, redevabilité et apprentissage",
        "login_sub": "Connexion sécurisée", "username": "Identifiant", "password": "Mot de passe",
        "login_btn": "Se connecter", "logout": "Se déconnecter", "denied": "Accès non autorisé pour votre rôle.",
        "setup_title": "Première utilisation : créer le compte administrateur", "full_name": "Nom complet",
        "password2": "Confirmer le mot de passe", "setup_btn": "Créer le compte administrateur",
        "setup_token": "Jeton d'installation", "setup_ok": "Compte administrateur créé. Vous pouvez vous connecter.",
        "pw_mismatch": "Les mots de passe ne correspondent pas.", "bad_token": "Jeton d'installation incorrect.",
        "expired": "Session expirée par inactivité. Veuillez vous reconnecter.",
        "notice": "Accès réservé au personnel autorisé. Les connexions sont journalisées.",
        "credit": "Photos © IRC",
    },
    "en": {
        "home": "Home / Dashboard", "commcare": "CommCare HQ connection", "import": "Data import",
        "explore": "Data exploration", "clean": "Data cleaning", "dqa": "Data Quality Assessment",
        "indicators": "MEAL indicators", "compare": "Comparative analysis", "viz": "Visualization",
        "donor": "Donor Reporting", "reports": "Report generation", "history": "Report history",
        "settings": "Settings (users, audit)", "language": "Language", "coming": "Module planned in phase {n}.",
        "tagline": "Monitoring, Evaluation, Accountability and Learning",
        "login_sub": "Secure sign-in", "username": "Username", "password": "Password",
        "login_btn": "Sign in", "logout": "Sign out", "denied": "Your role does not allow access to this page.",
        "setup_title": "First use: create the administrator account", "full_name": "Full name",
        "password2": "Confirm password", "setup_btn": "Create administrator account",
        "setup_token": "Setup token", "setup_ok": "Administrator account created. You can now sign in.",
        "pw_mismatch": "Passwords do not match.", "bad_token": "Incorrect setup token.",
        "expired": "Session expired due to inactivity. Please sign in again.",
        "notice": "Restricted to authorized staff. Sign-ins are logged.",
        "credit": "Photos © IRC",
    },
}


def t(key: str, lang: str = "fr", **kw) -> str:
    s = TEXTS.get(lang, TEXTS["fr"]).get(key, key)
    return s.format(**kw) if kw else s
