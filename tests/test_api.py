from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_profile_invalid_url():
    response = client.post("/profile", json={"url": "https://invalid-url.com"})
    assert response.status_code == 400
    assert "Invalid LinkedIn profile URL" in response.json()["detail"]
