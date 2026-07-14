"""
Portal health endpoint.

GET /health

Returns JSON describing the portal's own health — not the health of registered
applications.  Used by monitoring tools and by IBM HTTP Server to verify the
portal process is alive.
"""
import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app

health_bp = Blueprint("portal_health", __name__)
logger = logging.getLogger(__name__)


@health_bp.route("/health")
def health():
    registry = current_app.extensions.get("registry")
    payload = {
        "status": "ok",
        "application_name": "Maplesrugs Internal Portal",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "registry_loaded": registry.loaded if registry else False,
        "registered_application_count": registry.count if registry else 0,
    }
    return Response(
        json.dumps(payload, indent=2),
        status=200,
        mimetype="application/json",
    )
