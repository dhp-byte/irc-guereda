"""Images défilantes de la page de connexion.
1) tente de récupérer des photos publiées sur rescue.org (mises en cache localement, hors ligne ensuite) ;
2) complète/remplace par les photos fournies dans assets/login/ (extraites du rapport annuel IRC Tchad 2019).
Désactiver le téléchargement : MEAL_LOGIN_REMOTE=0."""
from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
import time
from pathlib import Path

import requests
from PIL import Image

from . import config

log = logging.getLogger(__name__)

# Photos publiées par l'IRC sur rescue.org (© IRC, Taiwo Aina-Adeokun / J. Zocherman). Modifiables ici.
REMOTE_IMAGES = [
    "https://www.rescue.org/sites/default/files/styles/widescreen_16x9_1280px_wide/public/2024-07/20240214-Chad-JZocherman%20Nutrition-0021%E2%80%9321x9-2.jpg?itok=vYDfboiy",
    "https://www.rescue.org/sites/default/files/styles/widescreen_16x9_1280px_wide/public/2026-09/20260423-EasternChad-TaiwoAina-health-DSCF6420-1200x800-5b2df79.jpg?h=df3c6bf4&itok=Cta4chyi",
    "https://www.rescue.org/sites/default/files/styles/landscape_4x3_640px_wide/public/2026-09/20260423-EasternChad-TaiwoAina-health-DSCF6017-1200x800-5b2df79.jpg?itok=4TjwGhx6",
    "https://www.rescue.org/sites/default/files/styles/landscape_4x3_640px_wide/public/2026-09/20260425-EasternChad-TaiwoAina-health-DSCF6729-1200x800-5b2df79.jpg?itok=31znZwYI",
    "https://www.rescue.org/sites/default/files/styles/landscape_4x3_640px_wide/public/2026-09/20260423-EasternChad-TaiwoAina-health-DSCF6146-1200x800-5b2df79.jpg?itok=CmOZbq51",
]
BUNDLED_DIR = config.ROOT / "assets" / "login"
SLIDE_H, SLIDE_MAX_W, MAX_BYTES = 360, 720, 5_000_000
OFFLINE_RETRY_SECONDS = 3600


def _cache_dir() -> Path:
    d = config.DATA_DIR / "login_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _fetch(url: str) -> bytes | None:
    """Télécharge une image. Retourne None si la réponse n'est pas une image ; lève RequestException si hors ligne."""
    r = requests.get(url, timeout=6, headers={"User-Agent": "IRC-MEAL-INSIGHT/0.3"}, stream=True)
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        return None
    data = r.raw.read(MAX_BYTES + 1, decode_content=True)
    return data if 0 < len(data) <= MAX_BYTES else None


def _normalize(raw: bytes) -> bytes:
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    s = SLIDE_H / im.height
    im = im.resize((max(1, round(im.width * s)), SLIDE_H), Image.LANCZOS)
    if im.width > SLIDE_MAX_W:
        left = (im.width - SLIDE_MAX_W) // 2
        im = im.crop((left, 0, left + SLIDE_MAX_W, SLIDE_H))
    out = io.BytesIO()
    im.save(out, "JPEG", quality=72, optimize=True)
    return out.getvalue()


def _uri(jpeg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()


def _remote_slides() -> list[str]:
    if os.environ.get("MEAL_LOGIN_REMOTE", "1") == "0":
        return []
    cache = _cache_dir()
    marker = cache / ".offline"
    slides: list[str] = []
    offline = marker.exists() and time.time() - marker.stat().st_mtime < OFFLINE_RETRY_SECONDS
    for url in REMOTE_IMAGES:
        f = cache / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg")
        if f.exists():
            slides.append(_uri(f.read_bytes()))
            continue
        if offline:
            continue
        try:
            raw = _fetch(url)
            if raw:
                jpeg = _normalize(raw)
                f.write_bytes(jpeg)
                slides.append(_uri(jpeg))
        except requests.RequestException:
            marker.touch()  # hors ligne : ne pas réessayer à chaque ouverture de page
            break
        except (OSError, ValueError):  # image illisible
            continue
    return slides


def load_slides(min_slides: int = 4) -> list[str]:
    slides = _remote_slides()
    if len(slides) < min_slides:
        slides += [_uri(p.read_bytes()) for p in sorted(BUNDLED_DIR.glob("*.jpg"))]
    return slides
