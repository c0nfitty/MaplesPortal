"""
Application registry service.

Architecture note
-----------------
ApplicationRegistry is the single object the rest of the portal talks to.
It delegates loading to an interchangeable loader:

    YAMLRegistryLoader   — reads config/applications.yaml  (current default)
    Db2RegistryLoader    — reads from a Db2 for i table     (future migration)

To switch to Db2, implement Db2RegistryLoader with the same .load() signature
and pass it to ApplicationRegistry in app/__init__.py.  Nothing else changes.
"""
import logging
from pathlib import Path
from typing import List, Optional

import yaml

from app.models.application import Application

logger = logging.getLogger(__name__)

# Fields that must be present in every registry record.
REQUIRED_FIELDS = (
    "application_id",
    "name",
    "short_description",
    "category",
    "route",
    "internal_url",
)

# All fields accepted by the Application dataclass.
_APP_FIELDS = set(Application.__dataclass_fields__)


class RegistryError(Exception):
    pass


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------

class YAMLRegistryLoader:
    """Load the application registry from a YAML file on disk."""

    def __init__(self, registry_path: str):
        self.registry_path = Path(registry_path)

    def load(self) -> List[Application]:
        if not self.registry_path.exists():
            raise RegistryError(f"Registry file not found: {self.registry_path}")

        try:
            with open(self.registry_path, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise RegistryError(f"Invalid YAML in registry file: {exc}") from exc

        if not data or "applications" not in data:
            logger.warning(
                "Registry file has no 'applications' key — returning empty list"
            )
            return []

        apps: List[Application] = []
        for raw in data["applications"]:
            try:
                apps.append(_parse_record(raw))
            except (KeyError, TypeError, ValueError) as exc:
                app_id = raw.get("application_id", "<unknown>") if isinstance(raw, dict) else "<unknown>"
                logger.error("Skipping invalid registry record '%s': %s", app_id, exc)

        logger.info(
            "Registry loaded: %d application(s) from %s",
            len(apps),
            self.registry_path,
        )
        return apps


def _parse_record(raw: dict) -> Application:
    for field in REQUIRED_FIELDS:
        if field not in raw:
            raise KeyError(f"Missing required field: '{field}'")

    # Only pass fields the dataclass knows about; ignore any unknown extras.
    known = {k: v for k, v in raw.items() if k in _APP_FIELDS}
    return Application(**known)


# ---------------------------------------------------------------------------
# Registry (loader-agnostic)
# ---------------------------------------------------------------------------

class ApplicationRegistry:
    """
    Central registry used by the portal.

    The registry is loaded once at startup and can be reloaded via the
    admin page without restarting the process.
    """

    def __init__(self, loader):
        self._loader = loader
        self._apps: List[Application] = []
        self._loaded = False

    # --- Lifecycle ----------------------------------------------------------

    def load(self) -> None:
        self._apps = self._loader.load()
        self._loaded = True

    def reload(self) -> None:
        logger.info("Reloading application registry")
        self.load()

    # --- State --------------------------------------------------------------

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def count(self) -> int:
        return len(self._apps)

    # --- Queries ------------------------------------------------------------

    def all_apps(self) -> List[Application]:
        """All apps, including disabled ones.  Used by the admin page."""
        return list(self._apps)

    def all_enabled(self) -> List[Application]:
        """Enabled apps sorted by display_order."""
        return sorted(
            [a for a in self._apps if a.enabled],
            key=lambda a: a.display_order,
        )

    def for_roles(self, roles: List[str]) -> List[Application]:
        """
        Return enabled apps the user is allowed to see.

        An app with an empty required_roles list is visible to every
        authenticated user.  Otherwise, the user must hold at least one
        of the listed roles.
        """
        result = []
        for app in self.all_enabled():
            if not app.required_roles:
                result.append(app)
            elif any(r in roles for r in app.required_roles):
                result.append(app)
        return result

    def get_by_id(self, application_id: str) -> Optional[Application]:
        for app in self._apps:
            if app.application_id == application_id:
                return app
        return None

    def categories(self) -> List[str]:
        """Ordered, deduplicated list of categories from enabled apps."""
        seen: List[str] = []
        for app in self.all_enabled():
            if app.category not in seen:
                seen.append(app.category)
        return seen

    def search(self, query: str, roles: Optional[List[str]] = None) -> List[Application]:
        """
        Full-text search across name, description, category, and owner.
        If roles are supplied, only matching apps visible to that user are returned.
        """
        q = query.lower().strip()
        pool = self.for_roles(roles) if roles is not None else self.all_enabled()
        return [
            a for a in pool
            if q in a.name.lower()
            or q in a.short_description.lower()
            or q in a.category.lower()
            or q in a.owner.lower()
        ]
