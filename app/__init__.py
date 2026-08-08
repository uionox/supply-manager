"""Application factory for the Camp Supply Tracker."""

import os

from flask import Flask

from . import admin, auth, cli, db, i18n, public


def _load_dotenv(path):
    """Minimal .env reader so local runs work without an extra dependency.

    In production systemd loads the same file via EnvironmentFile, so real
    environment variables always win over what is written here.
    """
    if not os.path.exists(path):
        return
    # utf-8-sig so a BOM-prefixed file (Windows editors love these) still parses.
    with open(path, encoding="utf-8-sig") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    _load_dotenv(os.path.join(os.path.dirname(app.root_path), ".env"))
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-key-not-for-production"),
        DATABASE=os.environ.get("DATABASE_PATH")
        or os.path.join(app.instance_path, "supply.db"),
        ADMIN_PASSWORD_HASH=os.environ.get("ADMIN_PASSWORD_HASH", ""),
        SITE_TITLE=os.environ.get("SITE_TITLE", "Camp Supply Tracker"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    cli.init_app(app)
    i18n.init_app(app)
    app.register_blueprint(public.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)

    with app.app_context():
        db.ensure_schema()

    return app
