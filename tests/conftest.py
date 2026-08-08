"""Shared fixtures. Every test gets its own throwaway database."""

import os
import sys

import pytest
from werkzeug.security import generate_password_hash

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.db import get_db  # noqa: E402

ADMIN_PASSWORD = "hunter2"


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "DATABASE": str(tmp_path / "test.db"),
            "SECRET_KEY": "test-key-not-used-anywhere-real",
            "ADMIN_PASSWORD_HASH": generate_password_hash(ADMIN_PASSWORD),
            "SESSION_COOKIE_SECURE": False,
            "DISPLAY_TIMEZONE": "Asia/Beirut",
            "TESTING": True,
        }
    )
    # Each test starts with a fresh throttle, or an earlier lockout leaks.
    from app.auth import throttle

    throttle._failures.clear()
    yield application


@pytest.fixture
def client(app):
    """An anonymous visitor."""
    return app.test_client()


@pytest.fixture
def admin(app):
    """A signed-in organiser."""
    session = app.test_client()
    session.post("/admin/login", data={"password": ADMIN_PASSWORD})
    return session


@pytest.fixture
def query(app):
    def run(sql, args=()):
        with app.app_context():
            return get_db().execute(sql, args).fetchall()

    return run


@pytest.fixture
def scalar(query):
    def run(sql, args=()):
        return query(sql, args)[0][0]

    return run


@pytest.fixture
def board(admin, scalar):
    """Two categories and two items, ready to claim against."""
    admin.post("/admin/categories", data={"name": "Bedding"})
    admin.post("/admin/categories", data={"name": "Food"})
    bedding = scalar("SELECT id FROM categories WHERE name = 'Bedding'")

    admin.post("/admin/items", data={
        "category_id": bedding, "name": "Blankets",
        "description": "Warm ones", "quantity_needed": "10", "unit": "pcs"})
    admin.post("/admin/items", data={
        "category_id": bedding, "name": "Pillows",
        "description": "", "quantity_needed": "8", "unit": "pcs"})

    return {
        "category_id": bedding,
        "blankets": scalar("SELECT id FROM items WHERE name = 'Blankets'"),
        "pillows": scalar("SELECT id FROM items WHERE name = 'Pillows'"),
    }
