"""Importation : extraction brute immuable (JSONL + SHA-256), fusion incrémentale, mise à plat en DataFrame."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config

_DROP = {"attachments", "archived", "build_id", "edited_by_user_id", "edited_on", "is_phone_submission",
         "resource_uri", "server_modified_on", "problem", "uiversion", "version", "indexed_on",
         "initial_processing_complete", "deprecated_form_id"}


def merge_records(old: list[dict], new: list[dict]) -> list[dict]:
    """Fusion par identifiant de soumission ; la version la plus récente l'emporte."""
    merged = {r["id"]: r for r in old}
    merged.update({r["id"]: r for r in new})
    return list(merged.values())


def watermark(records: list[dict]) -> str | None:
    dates = [r["received_on"] for r in records if r.get("received_on")]
    return max(dates) if dates else None


def save_raw(records: list[dict], label: str, raw_dir: Path | None = None) -> tuple[str, str]:
    """Écrit un instantané brut en lecture seule. Retourne (chemin, sha256). Les données brutes ne sont jamais modifiées."""
    raw_dir = Path(raw_dir or config.RAW_DIR)
    raw_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", label).strip("_") or "base"
    path = raw_dir / f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%f}_{slug}.jsonl"
    payload = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in records).encode("utf-8")
    path.write_bytes(payload)
    os.chmod(path, 0o444)
    return str(path), hashlib.sha256(payload).hexdigest()


def load_raw(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def verify_raw(path: str | Path, sha256: str) -> bool:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha256


def flatten_submissions(records: list[dict]) -> pd.DataFrame:
    """Soumissions CommCare (JSON imbriqué) -> table plate. Les colonnes sont conservées en texte brut :
    le typage et le nettoyage relèvent de la phase 4 et seront tracés."""
    if not records:
        return pd.DataFrame()
    df = pd.json_normalize(records, sep=".")
    keep = []
    for c in df.columns:
        parts = c.split(".")
        if c in _DROP or parts[0] in ("attachments", "case") or any(p.startswith(("@", "#")) for p in parts):
            continue
        keep.append(c)
    df = df[keep].copy()
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, (list, dict))).any():
            df[c] = df[c].map(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
    ren: dict[str, str] = {}
    for c in df.columns:
        if c.startswith("form."):
            short = c[5:]
            if short not in df.columns and short not in ren.values():
                ren[c] = short
        elif c.startswith("metadata."):
            ren[c] = "meta_" + c[9:]
    df = df.rename(columns=ren).rename(columns={"id": "submission_id"})
    for c in ("received_on", "meta_timeStart", "meta_timeEnd"):
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", utc=True).dt.tz_localize(None)
    return df
