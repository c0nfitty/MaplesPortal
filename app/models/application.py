"""
Application data model.

This dataclass mirrors the fields in the YAML registry (and eventually the Db2 table).
The `status` field is a runtime value set by the health-check service — it is never
stored in the registry.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Application:
    # --- Required fields (must be present in registry) ---
    application_id: str
    name: str
    short_description: str
    category: str
    route: str
    internal_url: str

    # --- Optional registry fields ---
    long_description: str = ""
    icon: str = "grid"
    owner: str = ""
    support_contact: str = ""
    required_roles: List[str] = field(default_factory=list)
    enabled: bool = True
    display_order: int = 100
    health_check_url: str = ""
    documentation_url: str = ""
    source_repository: str = ""
    environment: str = "production"
    last_verified_date: str = ""

    # --- Runtime field: set by health_check service, not stored in registry ---
    status: str = "unknown"   # available | unavailable | maintenance | unknown

    @property
    def status_label(self) -> str:
        return {
            "available": "Available",
            "unavailable": "Unavailable",
            "maintenance": "Maintenance",
            "unknown": "Unknown",
        }.get(self.status, "Unknown")

    @property
    def status_css_class(self) -> str:
        return {
            "available": "status-available",
            "unavailable": "status-unavailable",
            "maintenance": "status-maintenance",
            "unknown": "status-unknown",
        }.get(self.status, "status-unknown")
