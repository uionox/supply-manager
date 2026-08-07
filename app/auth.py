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

bp = Blueprint("auth", __name__, url_prefix="/admin")


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
    if request.method == "POST":
        password_hash = current_app.config["ADMIN_PASSWORD_HASH"]
        if not password_hash:
            flash(
                "No admin password is configured on this server. "
                "Set ADMIN_PASSWORD_HASH and restart.",
                "error",
            )
        elif check_password_hash(password_hash, request.form.get("password", "")):
            session.clear()
            session["is_admin"] = True
            return redirect(_safe_next(request.args.get("next")))
        else:
            flash("Incorrect password.", "error")
    return render_template("admin/login.html")


@bp.post("/logout")
def logout():
    session.clear()
    flash("Signed out.", "success")
    return redirect(url_for("public.index"))
