"""Single shared admin password, kept in a Flask session."""

import functools

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

from .security import LoginThrottle

bp = Blueprint("auth", __name__, url_prefix="/admin")

throttle = LoginThrottle()


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def _safe_next(target):
    """Only follow same-site paths, so ?next= can't be used for redirects off-site."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("admin.dashboard")


@bp.route("/login", methods=("GET", "POST"))
def login():
    caller = request.remote_addr or "unknown"

    if request.method == "POST":
        blocked_for = throttle.seconds_blocked(caller)
        if blocked_for:
            flash(
                f"Too many failed sign-in attempts. Try again in "
                f"{max(1, blocked_for // 60)} minute(s).",
                "error",
            )
            return render_template("admin/login.html"), 429

        password_hash = current_app.config["ADMIN_PASSWORD_HASH"]
        if not password_hash:
            flash(
                "No admin password is configured on this server. "
                "Set ADMIN_PASSWORD_HASH and restart.",
                "error",
            )
        elif check_password_hash(password_hash, request.form.get("password", "")):
            throttle.reset(caller)
            # Clear on sign-in to avoid session fixation, but a language
            # choice is a harmless UI preference — keep it.
            language = session.get("lang")
            session.clear()
            session["is_admin"] = True
            if language:
                session["lang"] = language
            return redirect(_safe_next(request.args.get("next")))
        else:
            throttle.record_failure(caller)
            flash("Incorrect password.", "error")
    return render_template("admin/login.html")


@bp.post("/logout")
def logout():
    language = session.get("lang")
    session.clear()
    if language:
        session["lang"] = language
    flash("Signed out.", "success")
    return redirect(url_for("public.index"))
