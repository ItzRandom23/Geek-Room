from fastapi.testclient import TestClient

from app.main import app
from app.services.rate_limit import RateLimiter

client = TestClient(app)


def test_local_limiter_enforces_limit():
    limiter = RateLimiter()
    key = "test-bucket:unit"
    for _ in range(5):
        assert limiter.hit(key, 5, 60) is True
    assert limiter.hit(key, 5, 60) is False


def test_local_limiter_resets_after_window(monkeypatch):
    import app.services.rate_limit as rl

    clock = iter([0.0, 0.0, 61.0])
    monkeypatch.setattr(rl.time, "monotonic", lambda: next(clock))
    limiter = rl.RateLimiter()
    key = "test-bucket:window"
    assert limiter.hit(key, 1, 60) is True
    assert limiter.hit(key, 1, 60) is False
    assert limiter.hit(key, 1, 60) is True


def test_login_returns_429_when_ip_is_rate_limited(monkeypatch):
    from app.main import get_limiter

    fresh = RateLimiter()
    monkeypatch.setattr("app.main.get_limiter", lambda: fresh)
    payload = {"email": "nobody@example.com", "password": "wrong-password"}
    for _ in range(5):
        assert client.post("/api/auth/login", json=payload).status_code == 401
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"
    assert response.headers.get("Retry-After") == "60"
    assert get_limiter() is not fresh


def test_register_returns_429_when_ip_is_rate_limited(monkeypatch):
    import uuid

    from app.main import get_limiter

    suffix = uuid.uuid4().hex[:8]
    fresh = RateLimiter()
    monkeypatch.setattr("app.main.get_limiter", lambda: fresh)
    for index in range(3):
        response = client.post("/api/auth/register", json={"email": f"spam-{suffix}-{index}@example.com", "password": "strong-pass-1", "full_name": "Spam", "organization_name": "Spam Inc"})
        assert response.status_code == 201
    response = client.post("/api/auth/register", json={"email": f"spam-{suffix}-4@example.com", "password": "strong-pass-1", "full_name": "Spam", "organization_name": "Spam Inc"})
    assert response.status_code == 429
    assert response.headers.get("Retry-After") == "3600"
    assert get_limiter() is not fresh
