import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "session_configured" in r.json()


def test_root():
    assert client.get("/").status_code == 200


@pytest.mark.parametrize("bad_url", [
    "https://example.com/in/foo",
    "https://www.linkedin.com/company/microsoft",
    "not a url",
])
def test_profile_rejects_non_profile_urls(bad_url):
    r = client.post("/profile", json={"url": bad_url})
    assert r.status_code == 400


def test_get_variant_also_validates():
    r = client.get("/profile", params={"url": "https://example.com/in/foo"})
    assert r.status_code == 400


def test_profile_without_cookie_returns_401(monkeypatch):
    monkeypatch.delenv("LINKEDIN_LI_AT", raising=False)
    from app.linkedin.client import LinkedInClient
    from app.routes.profile import profile_service

    profile_service.client = LinkedInClient()
    r = client.post("/profile", json={"url": "https://www.linkedin.com/in/williamhgates"})
    assert r.status_code == 401
