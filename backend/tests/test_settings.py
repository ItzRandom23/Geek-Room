import uuid

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


client = TestClient(app)


def test_profile_and_password_updates_require_auth_and_persist():
    settings = get_settings()
    original = settings.auth_required
    settings.auth_required = True
    suffix = uuid.uuid4().hex[:10]
    email = f"settings-{suffix}@example.com"
    new_email = f"updated-{suffix}@example.com"
    try:
        registered = client.post("/api/auth/register", json={"email": email, "password": "original-pass-1", "full_name": "Settings User", "organization_name": f"Settings Team {suffix}"})
        assert registered.status_code == 201
        headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

        profile = client.patch("/api/me", headers=headers, json={"full_name": "Updated Settings User", "email": new_email})
        assert profile.status_code == 200
        assert profile.json()["full_name"] == "Updated Settings User"
        assert profile.json()["email"] == new_email

        wrong_password = client.post("/api/me/password", headers=headers, json={"current_password": "wrong-pass", "new_password": "new-pass-123"})
        assert wrong_password.status_code == 400
        changed = client.post("/api/me/password", headers=headers, json={"current_password": "original-pass-1", "new_password": "new-pass-123"})
        assert changed.status_code == 200
        login = client.post("/api/auth/login", json={"email": new_email, "password": "new-pass-123"})
        assert login.status_code == 200
    finally:
        settings.auth_required = original
