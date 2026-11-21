import io
import pytest
import requests
from PIL import Image
from meal_insight import login_media as lm


def _png(w=1280, h=720):
    b = io.BytesIO(); Image.new("RGB", (w, h), (200, 150, 20)).save(b, "PNG"); return b.getvalue()


def test_bundled_fallback_when_remote_disabled(monkeypatch):
    monkeypatch.setenv("MEAL_LOGIN_REMOTE", "0")
    s = lm.load_slides()
    assert len(s) >= 4 and all(x.startswith("data:image/jpeg;base64,") for x in s)


def test_remote_download_cached(monkeypatch):
    monkeypatch.delenv("MEAL_LOGIN_REMOTE", raising=False)
    calls = []
    monkeypatch.setattr(lm, "_fetch", lambda url: calls.append(url) or _png())
    s = lm.load_slides()
    assert len(calls) == len(lm.REMOTE_IMAGES) and len(s) >= len(lm.REMOTE_IMAGES)
    monkeypatch.setattr(lm, "_fetch", lambda url: pytest.fail("doit utiliser le cache"))
    assert len(lm.load_slides()) >= len(lm.REMOTE_IMAGES)


def test_offline_marks_and_skips(monkeypatch):
    monkeypatch.delenv("MEAL_LOGIN_REMOTE", raising=False)
    n = []
    def boom(url): n.append(1); raise requests.ConnectionError()
    monkeypatch.setattr(lm, "_fetch", boom)
    s = lm.load_slides()
    assert len(n) == 1 and len(s) >= 4  # une seule tentative puis repli sur les images fournies
    lm.load_slides(); assert len(n) == 1  # marqueur hors ligne : pas de nouvelle tentative


def test_normalize_size():
    im = Image.open(io.BytesIO(lm._normalize(_png(4000, 1000))))
    assert im.height == lm.SLIDE_H and im.width <= lm.SLIDE_MAX_W
