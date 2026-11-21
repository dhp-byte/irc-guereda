"""Jeu de données FICTIF au format CommCare HQ (aucune donnée réelle). Contient des anomalies volontaires
(doublons, valeurs manquantes, âges impossibles, dates hors période) pour tester le contrôle qualité."""
from __future__ import annotations

import copy
import random
import uuid
from datetime import date, datetime, time, timedelta

XMLNS = "http://openrosa.org/formdesigner/demo-services-v1"
SITES = ["Guéréda centre", "Site Nord", "Site Est", "Site Sud", "Site Ouest"]  # noms fictifs
SERVICES = {
    "Protection": ["Gestion de cas", "Soutien psychosocial"],
    "Santé": ["Consultation curative", "Consultation prénatale"],
    "Moyens d'existence": ["Formation AGR", "Transfert monétaire"],
}
VULNERABILITIES = ["Aucune", "Femme cheffe de ménage", "Personne handicapée", "Enfant non accompagné", "Personne âgée"]


def _uid(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def generate_submissions(start: date, end: date, n: int = 500, seed: int = 42,
                         anomaly_rate: float = 0.08, project: str = "PROJ-DEMO") -> list[dict]:
    rng = random.Random(seed)
    days = (end - start).days + 1
    pool = [f"B{seed % 100:02d}{i:05d}" for i in range(max(1, int(n * 0.6)))]  # bénéficiaires < participations
    people: dict[str, dict] = {}
    records: list[dict] = []
    for _ in range(n):
        bid = rng.choice(pool)
        p = people.setdefault(bid, {
            "sex": rng.choices(["F", "M"], [0.58, 0.42])[0], "age": min(79, int(rng.expovariate(1 / 22))),
            "site": rng.choice(SITES), "vuln": rng.choices(VULNERABILITIES, [0.55, 0.2, 0.1, 0.05, 0.1])[0],
            "hh": f"M{rng.randrange(10**5):05d}"})
        sector = rng.choice(list(SERVICES))
        sd = start + timedelta(days=rng.randrange(days))
        recv = datetime.combine(sd, time(8, 0)) + timedelta(hours=rng.randrange(0, 60))
        agent = rng.randrange(1, 9)
        records.append({
            "id": _uid(rng), "received_on": recv.strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "app_id": "demo-app",
            "xmlns": XMLNS,
            "metadata": {"userID": f"u{agent:03d}", "username": f"agent{agent}@demo",
                         "timeStart": recv.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                         "timeEnd": (recv + timedelta(minutes=6)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")},
            "form": {"@name": "Enregistrement des services", "beneficiary_id": bid, "hh_ref": p["hh"],
                     "sex": p["sex"], "age": str(p["age"]), "site": p["site"], "vulnerability": p["vuln"],
                     "sector": sector, "service_type": rng.choice(SERVICES[sector]), "service_date": sd.isoformat(),
                     "project": project, "num_services": "1", "gps": f"{14.1 + rng.random() / 10:.5f} {22.1 + rng.random() / 10:.5f} 0 10"}})
    extra = []
    for rec in records:
        if rng.random() >= anomaly_rate:
            continue
        kind = rng.choice(["dup", "sex", "age", "bid", "date"])
        if kind == "dup":
            d = copy.deepcopy(rec)
            d["id"] = _uid(rng)
            extra.append(d)
        elif kind == "sex":
            rec["form"]["sex"] = ""
        elif kind == "age":
            rec["form"]["age"] = "250"
        elif kind == "bid":
            rec["form"]["beneficiary_id"] = ""
        else:
            rec["form"]["service_date"] = (start - timedelta(days=365)).isoformat()
    return records + extra
