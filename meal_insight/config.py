"""Chemins et paramètres globaux. Lus à l'exécution (modifiables via variables d'environnement)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("MEAL_DATA_DIR") or ROOT / "data")
RAW_DIR = DATA_DIR / "raw"          # extractions brutes immuables (JSONL, lecture seule)
DB_PATH = DATA_DIR / "meal_insight.db"
KEY_FILE = DATA_DIR / ".master.key"  # utilisé seulement si MEAL_MASTER_KEY est absente (dev local)
LOG_PATH = DATA_DIR / "app.log"
LOGO_PATH = ROOT / "assets" / "logo_irc.png"  # réutilisé pour la page de couverture des rapports


def ensure_dirs() -> None:
    for p in (DATA_DIR, RAW_DIR):
        p.mkdir(parents=True, exist_ok=True)
