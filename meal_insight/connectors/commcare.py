"""Client CommCare HQ (API v0.5) : authentification par clé API, pagination, filtres temporels,
mises à jour incrémentales, reprises sur erreur. Les identifiants ne sont jamais journalisés."""
from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Iterator
from urllib.parse import urljoin

import requests

log = logging.getLogger(__name__)
RETRY_STATUS = {429, 500, 502, 503, 504}


class CommCareError(Exception):
    """Erreur de communication avec CommCare HQ."""


class CommCareAuthError(CommCareError):
    """Identifiants refusés ou droits insuffisants."""


def _iso(v: date | datetime | str) -> str:
    if isinstance(v, datetime):
        return v.isoformat(timespec="seconds")
    if isinstance(v, date):
        return f"{v.isoformat()}T00:00:00"
    return str(v)


def _label(x) -> str:
    if isinstance(x, dict):
        return str(next(iter(x.values()), ""))
    return str(x or "")


class CommCareClient:
    def __init__(self, server_url: str, domain: str, username: str, api_key: str, *, session=None,
                 timeout: int = 30, max_retries: int = 3, retry_backoff: float = 1.5, page_size: int = 100):
        server = server_url.strip().rstrip("/")
        if not (server.startswith("https://") or server.startswith("http://localhost")):
            raise CommCareError("L'URL du serveur doit utiliser HTTPS.")
        if not (domain.strip() and username.strip() and api_key.strip()):
            raise CommCareError("Espace projet, utilisateur et clé API sont obligatoires.")
        self.server, self.domain = server, domain.strip()
        self._auth = f"ApiKey {username.strip()}:{api_key.strip()}"
        self.session = session or requests.Session()
        self.timeout, self.max_retries = timeout, max_retries
        self.retry_backoff, self.page_size = retry_backoff, page_size

    def __repr__(self) -> str:  # ne jamais exposer la clé
        return f"CommCareClient(server={self.server!r}, domain={self.domain!r})"

    def _api(self, resource: str) -> str:
        return f"{self.server}/a/{self.domain}/api/v0.5/{resource}/"

    def _get(self, url: str, params: dict | None = None) -> dict:
        last = "inconnue"
        for attempt in range(self.max_retries + 1):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout,
                                     headers={"Authorization": self._auth, "Accept": "application/json"})
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = f"erreur réseau ({type(exc).__name__})"
            else:
                if r.status_code == 200:
                    try:
                        return r.json()
                    except ValueError as exc:
                        raise CommCareError("Réponse non valide (JSON attendu).") from exc
                if r.status_code in (401, 403):
                    raise CommCareAuthError("Accès refusé : vérifiez l'utilisateur, la clé API et les droits sur l'espace projet.")
                if r.status_code == 404:
                    raise CommCareError("Ressource introuvable : vérifiez l'URL du serveur et le nom de l'espace projet.")
                if r.status_code not in RETRY_STATUS:
                    raise CommCareError(f"Erreur HTTP {r.status_code}.")
                last = f"HTTP {r.status_code}"
            if attempt < self.max_retries:
                log.warning("CommCare : %s, nouvelle tentative %d/%d", last, attempt + 1, self.max_retries)
                time.sleep(self.retry_backoff * 2 ** attempt)
        raise CommCareError(f"Échec après {self.max_retries + 1} tentatives ({last}).")

    def _paginate(self, url: str, params: dict | None) -> Iterator[dict]:
        next_url, next_params = url, params
        while next_url:
            data = self._get(next_url, next_params)
            yield from data.get("objects", [])
            nxt = (data.get("meta") or {}).get("next")
            next_url, next_params = (urljoin(self.server + "/", nxt), None) if nxt else (None, None)

    def test_connection(self) -> dict:
        data = self._get(self._api("application"), {"limit": 1})
        return {"ok": True, "applications": (data.get("meta") or {}).get("total_count")}

    def list_forms(self) -> list[dict]:
        """Formulaires disponibles (application > module > formulaire), avec leur xmlns."""
        forms = []
        for app in self._paginate(self._api("application"), {"limit": self.page_size}):
            for module in app.get("modules", []):
                for f in module.get("forms", []):
                    if f.get("xmlns"):
                        forms.append({"application": _label(app.get("name")), "module": _label(module.get("name")),
                                      "formulaire": _label(f.get("name")), "xmlns": f["xmlns"]})
        return forms

    def iter_forms(self, xmlns: str | None = None, start=None, end=None, since=None,
                   max_records: int | None = None) -> Iterator[dict]:
        """Soumissions reçues entre start et end. `since` (mise à jour incrémentale) remplace start."""
        params: dict = {"limit": self.page_size}
        if xmlns:
            params["xmlns"] = xmlns
        lower = since or start
        if lower:
            params["received_on_start"] = _iso(lower)
        if end:
            params["received_on_end"] = _iso(end)
        seen: set = set()
        for rec in self._paginate(self._api("form"), params):
            rid = rec.get("id")
            if rid in seen:
                continue
            seen.add(rid)
            yield rec
            if max_records and len(seen) >= max_records:
                return

    def fetch_forms(self, **kw) -> list[dict]:
        return list(self.iter_forms(**kw))
