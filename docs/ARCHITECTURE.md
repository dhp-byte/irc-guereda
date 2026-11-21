# Architecture – IRC MEAL INSIGHT – Guéréda

## Principes
1. **Données brutes immuables** : chaque extraction est archivée en JSONL en lecture seule avec son SHA-256 (`data/raw/`).
2. **Traçabilité** : toute action (connexion, importation, plus tard nettoyage/exclusion) est écrite dans `audit_log`.
3. **Secrets chiffrés** : clés API chiffrées (Fernet) en base ; masquées dans les journaux ; jamais en clair.
4. **Séparation des couches** : l'interface (`app.py`) n'appelle que des modules métier testables sans Streamlit.

## Carte des modules
| Composant (cahier des charges §11) | Module | Phase |
|---|---|---|
| 1. Connexion CommCare | `connectors/commcare.py` | 2 ✅ |
| 2. Extraction | `ingest.py` (brut, fusion incrémentale) | 2 ✅ |
| 3. Préparation / nettoyage | `etl/` (à créer) | 4 |
| 4. Contrôle qualité | `quality/` | 4 |
| 5. Indicateurs | `indicators/` | 5 |
| 6. Analyses / comparaisons | `analysis/` | 6 |
| 7. Visualisation | `viz/` (Plotly) | 7 |
| 8. Rapports | `reports/` (docx, pdf, xlsx, pptx) | 8 |
| 9. Reporting bailleur | `donors/` | 9 |
| 10. Utilisateurs et sécurité | `security.py`, `db.py`, rôles à étendre | 1-10 |

## Flux de données
CommCare HQ → `CommCareClient` → `save_raw` (JSONL + SHA-256) → `flatten_submissions` → DataFrame (texte brut) →
[phase 4 : typage, nettoyage tracé, doublons] → [phase 5 : indicateurs] → [phases 6-9 : comparaisons, rapports].

## Choix à valider
- SQLite en local ; PostgreSQL envisageable en multi-utilisateurs (même schéma).
- Authentification actuelle : mot de passe unique optionnel (`MEAL_APP_PASSWORD`). Rôles/permissions multi-comptes : phase 10.
- L'IA externe (phase 8+) ne recevra que des agrégats anonymisés, après autorisation institutionnelle.
