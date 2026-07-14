"""
Auth routes: /login and /logout.
"""
import logging

from flask import (
    Blueprint,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from flask import current_app
from app.auth import users as user_store
from app.auth import ibmi_auth

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
logger = logging.getLogger(__name__)


def _authenticate(username: str, password: str):
    """
    Validate credentials using the configured AUTH_MODE.

    ibmi  — validates against IBM i user profiles via ibm_db
    session (fallback) — validates against config/users.yaml
    """
    mode = current_app.config.get("AUTH_MODE", "session")
    uname = username.strip().upper()

    if mode == "ibmi":
        return ibmi_auth.authenticate(uname, password)

    # session / users.yaml fallback
    return user_store.authenticate(uname, password)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = _authenticate(username, password)
        if user:
            session.clear()
            session["user"] = user["username"]
            session["roles"] = user["roles"]
            session.permanent = True
            logger.info("Login: %s", user["username"])

            next_url = request.args.get("next") or url_for("main.index")
            if not next_url.startswith("/"):
                next_url = url_for("main.index")
            return redirect(next_url)

        logger.warning("Failed login attempt for username: %s", username)
        error = "Invalid username or password."

    return render_template("auth/login.html", error=error)


@auth_bp.route("/logout")
def logout():
    user = session.get("user", "unknown")
    session.clear()
    logger.info("Logout: %s", user)
    return redirect(url_for("auth.login"))
