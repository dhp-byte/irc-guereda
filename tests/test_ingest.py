import os
from datetime import date
import pandas as pd
from meal_insight import ingest, synthetic

S, E = date(2026, 11, 1), date(2026, 11, 30)


def test_synthetic_reproducible_and_anomalies():
    a = synthetic.generate_submissions(S, E, 500, seed=1)
    assert a == synthetic.generate_submissions(S, E, 500, seed=1)
    forms = [r["form"] for r in a]
    assert any(f["age"] == "250" for f in forms) and any(f["sex"] == "" for f in forms)
    assert any(f["beneficiary_id"] == "" for f in forms)
    assert len({f["beneficiary_id"] for f in forms}) < len(forms)  # participations > bénéficiaires uniques


def test_flatten():
    df = ingest.flatten_submissions(synthetic.generate_submissions(S, E, 50, seed=2))
    assert {"submission_id", "beneficiary_id", "sex", "site", "received_on", "meta_username"} <= set(df.columns)
    assert not any("@" in c for c in df.columns)
    assert pd.api.types.is_datetime64_any_dtype(df["received_on"])
    assert df["submission_id"].is_unique


def test_raw_immutable_and_hash(tmp_path):
    recs = synthetic.generate_submissions(S, E, 20, seed=3)
    path, sha = ingest.save_raw(recs, "Base 1", tmp_path)
    assert ingest.verify_raw(path, sha) and ingest.load_raw(path) == recs
    assert not os.access(path, os.W_OK) or os.geteuid() == 0


def test_merge_and_watermark():
    old = [{"id": "a", "received_on": "2026-11-01T00:00:00Z", "v": 1}]
    new = [{"id": "a", "received_on": "2026-11-01T00:00:00Z", "v": 2}, {"id": "b", "received_on": "2026-11-05T00:00:00Z"}]
    m = ingest.merge_records(old, new)
    assert len(m) == 2 and next(r for r in m if r["id"] == "a")["v"] == 2
    assert ingest.watermark(m) == "2026-11-05T00:00:00Z"
