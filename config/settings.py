"""
Portal configuration.

Set PORTAL_ENV environment variable to select the active config:
  development  — debug on, no auth, YAML registry from ./config/applications.yaml
  production   — auth via reverse-proxy header, structured logging

Never store production secrets in source control.
Set PORTAL_SECRET_KEY via environment variable or a secrets file.
"""
import os


class Config:
    SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY", "change-me-in-production")
    REGISTRY_PATH = os.environ.get("PORTAL_REGISTRY_PATH", "config/applications.yaml")

    # AUTH_MODE options:
    #   none          — no authentication (development only)
    #   ibmi          — IBM i user profile auth via ibm_db + QSYS2.USER_INFO
    #   session       — Flask login + users.yaml (emergency fallback)
    #   proxy_header  — IBM HTTP Server sets X-Remote-User header
    AUTH_MODE = os.environ.get("PORTAL_AUTH_MODE", "proxy_header")
    AUTH_HEADER = os.environ.get("PORTAL_AUTH_HEADER", "X-Remote-User")

    # Path to users.yaml (session/emergency auth only)
    USERS_PATH = os.environ.get("PORTAL_USERS_PATH", "config/users.yaml")

    # Path to groups.yaml (ibmi auth — maps IBM i groups to portal roles)
    GROUPS_PATH = os.environ.get("PORTAL_GROUPS_PATH", "config/groups.yaml")

    # IBM i system IP or hostname used in ODBC connection strings
    IBMI_SYSTEM = os.environ.get("PORTAL_IBMI_SYSTEM", "172.16.1.2")

    # Seconds before a health check is considered timed out
    HEALTH_CHECK_TIMEOUT = int(os.environ.get("PORTAL_HEALTH_CHECK_TIMEOUT", "3"))

    LOG_PATH = os.environ.get("PORTAL_LOG_PATH", "logs/portal.log")
    DEBUG = False
    TESTING = False


class DevelopmentConfig(Config):
    DEBUG = True
    AUTH_MODE = "none"
    LOG_PATH = os.environ.get("PORTAL_LOG_PATH", "logs/portal-dev.log")


class TestConfig(Config):
    TESTING = True
    AUTH_MODE = "none"
    REGISTRY_PATH = "tests/fixtures/applications.yaml"


class ProductionConfig(Config):
    DEBUG = False
    # AUTH_MODE inherits from Config, which reads PORTAL_AUTH_MODE env var.
    # Default is 'proxy_header' (IBM HTTP Server validates IBM i credentials).
    # Override with: export PORTAL_AUTH_MODE=session  (emergency fallback)


config = {
    "development": DevelopmentConfig,
    "test": TestConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
