"""
User store — loads portal users from config/users.yaml.

Each entry has a werkzeug-hashed password and a list of roles.
This module is intentionally thin; swap the loader to move users to Db2.
"""
import logging
import yaml

from werkzeug.security import check_password_hash

logger = logging.getLogger(__name__)

_users: dict = {}


def load_users(path: str) -> None:
    """Load users from the YAML file into the module-level cache."""
    global _users
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _users = data.get("users", {})
        logger.info("Loaded %d portal user(s) from %s", len(_users), path)
    except FileNotFoundError:
        logger.warning("Users file not found: %s — no users loaded", path)
        _users = {}
    except Exception as exc:
        logger.error("Failed to load users file: %s", exc)
        _users = {}


def authenticate(username: str, password: str):
    """
    Validate credentials.

    Returns the user dict on success, None on failure.
    Username comparison is case-insensitive (normalised to uppercase).
    """
    key = username.strip().upper()
    user = _users.get(key)
    if not user:
        return None

    stored_hash = user.get("password_hash", "")
    if not stored_hash:
        logger.warning("User %s has no password hash configured", key)
        return None

    if check_password_hash(stored_hash, password):
        return {"username": key, "roles": user.get("roles", [])}

    return None


def get_user(username: str):
    """Return raw user dict for a given username, or None."""
    return _users.get(username.strip().upper())
