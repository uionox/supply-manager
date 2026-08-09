"""Application factory for the Camp Supply Tracker."""

import os

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from . import admin, auth, cli, db, i18n, public, timefmt
from .security import resolve_secret_key


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


def _flag(name, default):
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    _load_dotenv(os.path.join(os.path.dirname(app.root_path), ".env"))
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=resolve_secret_key(app.instance_path),
        DATABASE=os.environ.get("DATABASE_PATH")
        or os.path.join(app.instance_path, "supply.db"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", ""),
        SITE_TITLE=os.environ.get("SITE_TITLE", "Camp Supply Tracker"),
        DISPLAY_TIMEZONE=os.environ.get("DISPLAY_TIMEZONE", "Asia/Beirut"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # On by default: the admin cookie should never cross a plain HTTP
        # connection. Local development over http sets this to 0 in .env.
        SESSION_COOKIE_SECURE=_flag("SESSION_COOKIE_SECURE", "1"),
    )
    if test_config:
        app.config.update(test_config)

    # Behind Caddy every request appears to come from 127.0.0.1, which would
    # lump all visitors into one bucket for login throttling. Only trust the
    # forwarded headers when a proxy is actually in front, or they can be
    # spoofed to dodge the throttle.
    if _flag("TRUST_PROXY", "0"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    cli.init_app(app)
    i18n.init_app(app)
    timefmt.init_app(app)
    app.register_blueprint(public.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)

    with app.app_context():
        db.ensure_schema()

    return app
