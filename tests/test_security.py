"""The hardening added before going live."""

import os

import pytest
from flask.sessions import SecureCookieSessionInterface

from app.security import COMPROMISED_KEYS, LoginThrottle, resolve_secret_key

from .conftest import ADMIN_PASSWORD


# ── session key ──────────────────────────────────────────────────────────

@pytest.fixture
def no_env_key(monkeypatch):
    """Nothing in SECRET_KEY, so the generated-key path is what runs."""
    monkeypatch.delenv("SECRET_KEY", raising=False)


def test_a_generated_key_is_random_and_persistent(tmp_path, no_env_key):
    first = resolve_secret_key(str(tmp_path))
    second = resolve_secret_key(str(tmp_path))
    assert first == second, "restarting must not invalidate live sessions"
    assert len(first) >= 32
    assert first not in COMPROMISED_KEYS


def test_generated_keys_differ_between_installs(tmp_path, no_env_key):
    one = tmp_path / "a"
    two = tmp_path / "b"
    one.mkdir()
    two.mkdir()
    assert resolve_secret_key(str(one)) != resolve_secret_key(str(two))


def test_an_env_key_wins_over_a_generated_one(tmp_path, monkeypatch, no_env_key):
    generated = resolve_secret_key(str(tmp_path))
    monkeypatch.setenv("SECRET_KEY", "b" * 64)
    assert generated != "b" * 64
    assert resolve_secret_key(str(tmp_path)) == "b" * 64


def test_the_old_published_key_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "dev-key-not-for-production")
    with pytest.raises(RuntimeError, match="public in this repository"):
        resolve_secret_key(str(tmp_path))


@pytest.mark.parametrize("placeholder", sorted(COMPROMISED_KEYS))
def test_every_known_placeholder_is_refused(tmp_path, monkeypatch, placeholder):
    monkeypatch.setenv("SECRET_KEY", placeholder)
    with pytest.raises(RuntimeError):
        resolve_secret_key(str(tmp_path))


def test_a_real_env_key_is_used_as_is(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "a" * 64)
    assert resolve_secret_key(str(tmp_path)) == "a" * 64


def test_admin_session_cannot_be_forged_with_the_old_default(app):
    """The exact attack the published fallback key allowed."""
    forger = app.test_client()
    app.config["SECRET_KEY"] = "dev-key-not-for-production"
    cookie = SecureCookieSessionInterface().get_signing_serializer(app).dumps(
        {"is_admin": True})

    # Put the real key back, then present the cookie signed with the old one.
    app.config["SECRET_KEY"] = "test-key-not-used-anywhere-real"
    forger.set_cookie("session", cookie, domain="localhost")

    assert forger.get("/admin/", follow_redirects=False).status_code == 302
    assert forger.get("/admin/export.xlsx", follow_redirects=False).status_code == 302


# ── login throttling ─────────────────────────────────────────────────────

def test_repeated_wrong_passwords_get_locked_out(client):
    for _ in range(8):
        assert client.post("/admin/login", data={"password": "guess"}).status_code == 200
    blocked = client.post("/admin/login", data={"password": "guess"})
    assert blocked.status_code == 429
    assert b"Too many failed" in blocked.data


def test_lockout_blocks_even_the_right_password(client):
    for _ in range(9):
        client.post("/admin/login", data={"password": "guess"})
    response = client.post("/admin/login", data={"password": ADMIN_PASSWORD},
                           follow_redirects=False)
    assert response.status_code == 429


def test_signing_in_clears_the_counter(client):
    for _ in range(3):
        client.post("/admin/login", data={"password": "guess"})
    assert client.post("/admin/login", data={"password": ADMIN_PASSWORD},
                       follow_redirects=False).status_code == 302

    for _ in range(8):
        client.post("/admin/login", data={"password": "guess"})
    assert client.post("/admin/login", data={"password": "guess"}).status_code == 429


def test_throttle_forgets_old_failures():
    throttle = LoginThrottle(limit=2, window=0.2, lockout=0.2)
    throttle.record_failure("1.2.3.4")
    throttle.record_failure("1.2.3.4")
    assert throttle.seconds_blocked("1.2.3.4") > 0

    import time
    time.sleep(0.25)
    assert throttle.seconds_blocked("1.2.3.4") == 0


def test_throttling_is_per_caller():
    throttle = LoginThrottle(limit=1)
    throttle.record_failure("1.1.1.1")
    assert throttle.seconds_blocked("1.1.1.1") > 0
    assert throttle.seconds_blocked("2.2.2.2") == 0


# ── cookie flags ─────────────────────────────────────────────────────────

def test_session_cookie_flags(app):
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_secure_cookie_is_on_by_default(monkeypatch, tmp_path):
    from app import create_app

    monkeypatch.delenv("SESSION_COOKIE_SECURE", raising=False)
    monkeypatch.setattr("app._load_dotenv", lambda path: None)
    fresh = create_app({"DATABASE": str(tmp_path / "x.db")})
    assert fresh.config["SESSION_COOKIE_SECURE"] is True


def test_admin_redirect_cannot_be_pointed_off_site(client):
    response = client.post(
        "/admin/login?next=https://evil.example/steal",
        data={"password": ADMIN_PASSWORD}, follow_redirects=False)
    assert "evil.example" not in response.headers["Location"]
