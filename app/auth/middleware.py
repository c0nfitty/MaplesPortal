"""
Authentication middleware.

Populates g.user, g.roles, and g.is_admin for every request.

AUTH_MODE options (set in settings.py or PORTAL_AUTH_MODE env var):

  none          — development shortcut; g.user = 'DEVUSER', all roles granted
  session       — Flask login page + users.yaml (emergency fallback)
  ibmi          — Flask login page + QSYVATUP credential validation (WIP)
  proxy_header  — IBM HTTP Server validates IBM i profiles, passes
                  authenticated username via X-Remote-User header.
                  Roles resolved from QSYS2.USER_INFO + config/groups.yaml.
                  This is the recommended production mode.

Role assignment
---------------
  proxy_header  — IBM HTTP Server already validated credentials.
                  Flask reads the username from the request header, queries
                  QSYS2.USER_INFO (trusted ibm_db_dbi connection), maps
                  IBM i group profiles to portal roles via groups.yaml.
  session/ibmi  — roles were stored in the Flask session at login time.
  none          — ADMIN_USERS list below (dev only).
"""
import logging

from flask import g, request, current_app, session

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Used only for AUTH_MODE = 'none' (development).
# ---------------------------------------------------------------------------

ADMIN_USERS: list = [
    "ASHRADER",
]

DEFAULT_ROLES = ["portal_users"]


# ---------------------------------------------------------------------------

def get_current_user() -> str:
    """Return the authenticated username for the current request."""
    mode = current_app.config.get("AUTH_MODE", "session")

    if mode in ("session", "ibmi"):
        return session.get("user", "ANONYMOUS")

    if mode == "proxy_header":
        header = current_app.config.get("AUTH_HEADER", "X-Remote-User")
        user = request.headers.get(header, "").strip().upper()
        # IBM HTTP Server sends "(NULL)" when the request wasn't authenticated
        if not user or user in ("(NULL)", "NULL", "-"):
            logger.warning(
                "AUTH_MODE is 'proxy_header' but %s header was absent or null", header
            )
            return "ANONYMOUS"
        return user

    # none / development
    return "DEVUSER"


def get_user_roles(username: str) -> list:
    """Return portal roles for the given username."""
    if username in ("ANONYMOUS", ""):
        return []

    mode = current_app.config.get("AUTH_MODE", "session")

    if mode in ("session", "ibmi"):
        # Roles were stored in the session at login time
        return list(session.get("roles", DEFAULT_ROLES))

    if mode == "proxy_header":
        return _roles_from_ibmi(username)

    # none / development — grant everything so devs can see all UI
    roles = list(DEFAULT_ROLES)
    roles.extend(["developers", "product_users"])
    if username in ADMIN_USERS and "admins" not in roles:
        roles.append("admins")
    return roles


def load_user() -> None:
    """
    Populate g.user, g.roles, and g.is_admin for the current request.
    Called via @blueprint.before_request in each route module.
    """
    g.user = get_current_user()
    g.roles = get_user_roles(g.user)
    g.is_admin = "admins" in g.roles


# ---------------------------------------------------------------------------
# IBM i group lookup — used by proxy_header mode
# ---------------------------------------------------------------------------

def _roles_from_ibmi(username: str) -> list:
    """
    Look up this user's IBM i group profiles and map them to portal roles.

    Uses ibm_db_dbi.connect() — no credentials needed, runs as the portal
    job's trusted profile.  Group → role mapping from config/groups.yaml,
    loaded at startup via ibmi_auth.load_groups().
    """
    try:
        from app.auth.ibmi_auth import _get_ibmi_profile, _resolve_roles
        profile = _get_ibmi_profile(username)
        return _resolve_roles(username, profile["groups"], profile["user_class"])
    except Exception as exc:
        logger.warning(
            "IBM i group lookup failed for %s, using defaults: %s",
            username, exc,
        )
        return list(DEFAULT_ROLES)
