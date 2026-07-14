"""
Health check service.

Each registered application may expose a GET /health endpoint.
This module polls those endpoints and returns a simple status string.

Status values
-------------
  available    — endpoint returned HTTP 200
  unavailable  — endpoint returned non-200, timed out, or refused connection
  unknown      — no health_check_url configured for this app

Health checks run synchronously on page load.  The timeout is deliberately
short (default 3 s) so a down app does not stall the portal page.  Internal
exception details are never surfaced to the user.
"""
import logging
from typing import Dict, List

import requests

from app.models.application import Application

logger = logging.getLogger(__name__)

STATUS_AVAILABLE = "available"
STATUS_UNAVAILABLE = "unavailable"
STATUS_UNKNOWN = "unknown"


def check_application(app: Application, timeout: int = 3) -> str:
    """
    Poll a single application's health endpoint.

    Returns one of the STATUS_* constants.
    """
    if not app.health_check_url:
        return STATUS_UNKNOWN

    try:
        response = requests.get(app.health_check_url, timeout=timeout)
        if response.status_code == 200:
            return STATUS_AVAILABLE
        logger.warning(
            "Health check for '%s' returned HTTP %s",
            app.application_id,
            response.status_code,
        )
        return STATUS_UNAVAILABLE

    except requests.exceptions.Timeout:
        logger.warning("Health check for '%s' timed out", app.application_id)
        return STATUS_UNAVAILABLE

    except requests.exceptions.ConnectionError:
        logger.info(
            "Health check for '%s': connection refused (app may be down)",
            app.application_id,
        )
        return STATUS_UNAVAILABLE

    except Exception as exc:
        # Catch-all — we never want a health check failure to crash the portal.
        logger.error(
            "Unexpected error checking '%s': %s", app.application_id, exc
        )
        return STATUS_UNKNOWN


def check_all(apps: List[Application], timeout: int = 3) -> Dict[str, str]:
    """
    Check every app in the list and return a dict of {application_id: status}.
    """
    return {
        app.application_id: check_application(app, timeout)
        for app in apps
    }
