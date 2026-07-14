"""
Admin routes.

Only users with the 'admins' role can access /admin/*.
"""
import logging

from flask import Blueprint, abort, current_app, g, redirect, render_template, url_for

from app.auth.middleware import load_user
from app.services import health_check

admin_bp = Blueprint("admin", __name__)
logger = logging.getLogger(__name__)


@admin_bp.before_request
def before_request():
    load_user()
    if not g.is_admin:
        abort(403)


@admin_bp.route("/")
def index():
    registry = current_app.extensions["registry"]
    apps = registry.all_apps()          # includes disabled apps
    timeout = current_app.config.get("HEALTH_CHECK_TIMEOUT", 3)
    statuses = health_check.check_all(apps, timeout)

    for app in apps:
        app.status = statuses.get(app.application_id, "unknown")

    return render_template(
        "admin.html",
        apps=apps,
        user=g.user,
        is_admin=g.is_admin,
        registry_loaded=registry.loaded,
        registry_count=registry.count,
    )


@admin_bp.route("/reload-registry", methods=["POST"])
def reload_registry():
    registry = current_app.extensions["registry"]
    try:
        registry.reload()
        logger.info("Registry reloaded by %s", g.user)
    except Exception as exc:
        logger.error("Registry reload failed (triggered by %s): %s", g.user, exc)
    return redirect(url_for("admin.index"))
