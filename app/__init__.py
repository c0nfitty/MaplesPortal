"""
Flask application factory.

Usage:
    from app import create_app
    app = create_app("production")

The factory pattern lets us create multiple app instances with different
configs (e.g. in tests) without global state.
"""
import logging
import logging.handlers
import os

from flask import Flask, render_template, redirect, request, session, url_for

from config.settings import config


def create_app(config_name: str = None) -> Flask:
    if config_name is None:
        config_name = os.environ.get("PORTAL_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    _configure_logging(app)
    _init_registry(app)
    _load_users(app)
    _register_blueprints(app)
    _register_error_handlers(app)
    _enforce_login(app)

    app.logger.info("Portal started — environment: %s", config_name)
    return app


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _configure_logging(app: Flask) -> None:
    log_path = app.config.get("LOG_PATH", "logs/portal.log")
    os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)

    handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=10_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(module)s: %(message)s")
    )
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)

    # Also log to stderr so Gunicorn/Waitress picks it up.
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")
    )
    app.logger.addHandler(stderr_handler)


def _init_registry(app: Flask) -> None:
    from app.services.registry import ApplicationRegistry, YAMLRegistryLoader

    registry_path = app.config.get("REGISTRY_PATH", "config/applications.yaml")
    loader = YAMLRegistryLoader(registry_path)
    registry = ApplicationRegistry(loader)

    try:
        registry.load()
    except Exception as exc:
        app.logger.error("Failed to load registry on startup: %s", exc)

    # Store on app.extensions so blueprints can access it via current_app.extensions["registry"].
    app.extensions["registry"] = registry


def _load_users(app: Flask) -> None:
    mode = app.config.get("AUTH_MODE")

    if mode in ("ibmi", "proxy_header"):
        # Load groups.yaml so IBM i group → portal role mapping is ready
        from app.auth import ibmi_auth
        ibmi_auth.load_groups(app.config.get("GROUPS_PATH", "config/groups.yaml"))
        ibmi_auth.set_ibmi_system(app.config.get("IBMI_SYSTEM", "172.16.1.2"))

    if mode in ("ibmi", "session"):
        # Also load users.yaml (login page fallback / emergency access)
        from app.auth import users as user_store
        user_store.load_users(app.config.get("USERS_PATH", "config/users.yaml"))


def _enforce_login(app: Flask) -> None:
    """
    Gate unauthenticated requests.

    session/ibmi  — redirect to /auth/login (Flask handles the login page)
    proxy_header  — IBM HTTP Server already challenged the user; if the header
                    is absent, return 401 so the browser re-triggers the
                    HTTP Basic auth dialog rather than a Flask redirect.
    none          — no gate (development)
    """
    @app.before_request
    def check_login():
        mode = app.config.get("AUTH_MODE")

        if mode in ("session", "ibmi"):
            open_endpoints = {"auth.login", "auth.logout", "static", "portal_health.health"}
            if request.endpoint in open_endpoints:
                return None
            if not session.get("user"):
                return redirect(url_for("auth.login", next=request.path))

        elif mode == "proxy_header":
            open_endpoints = {"static", "portal_health.health"}
            if request.endpoint in open_endpoints:
                return None
            header = app.config.get("AUTH_HEADER", "X-Remote-User")
            if not request.headers.get(header):
                # Header absent — IBM HTTP Server didn't authenticate this
                # request (e.g. direct connection bypassing the proxy).
                # Return 401 to trigger re-authentication.
                return "Unauthorized — access this portal via the IBM HTTP Server.", 401


def _register_blueprints(app: Flask) -> None:
    from app.routes.main import main_bp
    from app.routes.admin import admin_bp
    from app.routes.health import health_bp
    from app.auth.routes import auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(health_bp)


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Unhandled exception")
        return render_template("errors/500.html"), 500
