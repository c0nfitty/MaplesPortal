"""
Main portal routes: home page and search.
"""
import logging

from flask import Blueprint, current_app, g, render_template, request

from app.auth.middleware import load_user
from app.services import health_check

main_bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)


@main_bp.before_request
def before_request():
    load_user()


@main_bp.route("/")
def index():
    registry = current_app.extensions["registry"]
    apps = registry.for_roles(g.roles)
    timeout = current_app.config.get("HEALTH_CHECK_TIMEOUT", 3)
    statuses = health_check.check_all(apps, timeout)

    for app in apps:
        app.status = statuses.get(app.application_id, "unknown")

    # Group apps by category while preserving display_order within each group.
    categories = registry.categories()
    grouped: dict = {cat: [] for cat in categories}
    for app in apps:
        if app.category in grouped:
            grouped[app.category].append(app)

    logger.info("User %s loaded portal home (%d app(s) visible)", g.user, len(apps))
    return render_template(
        "index.html",
        grouped=grouped,
        categories=categories,
        user=g.user,
        is_admin=g.is_admin,
        search_query="",
    )


@main_bp.route("/search")
def search():
    query = request.args.get("q", "").strip()
    registry = current_app.extensions["registry"]
    timeout = current_app.config.get("HEALTH_CHECK_TIMEOUT", 3)

    apps = registry.search(query, roles=g.roles) if query else registry.for_roles(g.roles)
    statuses = health_check.check_all(apps, timeout)
    for app in apps:
        app.status = statuses.get(app.application_id, "unknown")

    return render_template(
        "index.html",
        grouped={"Search results": apps} if query else {},
        categories=["Search results"] if query else [],
        user=g.user,
        is_admin=g.is_admin,
        search_query=query,
    )
