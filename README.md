# IRC MEAL INSIGHT – Guéréda (phases 1-2 + authentification)

Application Streamlit de suivi MEAL branchée sur CommCare HQ.
Phases livrées : architecture, connexion CommCare HQ, importation, jeu de données fictif, tests.

## Installation
```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # puis renseigner MEAL_MASTER_KEY (voir le fichier)
export MEAL_MASTER_KEY=...   # ou charger .env avec votre outil habituel
streamlit run app.py
python -m pytest -q          # tests
```
## Connexion à l'application
Une page d'authentification (identifiant + mot de passe) s'affiche avant toute donnée.
- **Aucun compte par défaut.** À la première ouverture, la page propose de créer le compte administrateur
  (si `MEAL_SETUP_TOKEN` est défini, ce jeton est exigé). Alternative en ligne de commande :
  `python -m meal_insight.auth create-user NOM --role admin`
- Mots de passe : 10 caractères minimum, lettres + chiffres ; stockés hachés (scrypt + sel).
- 5 échecs consécutifs = compte verrouillé 15 minutes. Déconnexion automatique après 30 min d'inactivité (`MEAL_SESSION_MINUTES`).
- Rôles : `admin` (tout, gestion des utilisateurs, journal), `analyste` (connexion CommCare, importation), `lecteur` (consultation).
- Connexions, échecs et déconnexions sont inscrits dans le journal d'audit (Paramètres, réservé aux admins).
- Photos défilantes : l'application tente de télécharger des photos de rescue.org (cache local, liste dans
  `meal_insight/login_media.py`) ; sinon elle utilise `assets/login/`. `MEAL_LOGIN_REMOTE=0` désactive le téléchargement.
- En production : servir derrière HTTPS (reverse proxy), Streamlit ne chiffre pas le trafic seul.

## Premier essai sans CommCare
Menu **Importation** → source « Démonstration » → *Importer*. Deux bases (ex. nov. 2025 / nov. 2026) peuvent être
créées avec des noms différents pour préparer la phase 6.

## Connexion réelle
Menu **Connexion CommCare HQ** : URL du serveur, espace projet, e-mail de l'utilisateur et clé API
(CommCare HQ › Mon compte › API Keys). La clé est chiffrée avant stockage. Prérequis : l'utilisateur doit avoir accès
aux données du formulaire dans l'espace projet.

## Sécurité
- `data/` ne doit jamais être versionné ni partagé (extractions brutes, base, clé locale).
- En production : définir `MEAL_MASTER_KEY` et `MEAL_SETUP_TOKEN`, servir en HTTPS.
