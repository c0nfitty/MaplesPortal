<img src="docs/Logo.png" alt="Maples Rugs" width="300" />

# MaplesPortal

A lightweight application portal that gives IBM i web applications a common front door.

MaplesPortal began as the front door for PATAI, an internal AI assistant running on IBM i. As additional web applications were developed, it became clear that a common portal with centralized authentication, application discovery, and health monitoring would make those tools significantly easier to manage. Although developed for Maples' environment, the project is intended to serve as a lightweight portal for any IBM i shop hosting multiple internal web applications.

MaplesPortal separates infrastructure concerns (authentication, routing, application discovery) from business applications, allowing new internal tools to be added with little more than a registry entry and a reverse proxy mapping.

---

## The Problem

IBM i shops accumulate web applications over time.

Inventory. Shipping. AI tools. Reporting. Documentation. Admin dashboards.

Each application ends up with its own URL, its own authentication, its own support contact, and its own documentation that lives nowhere in particular. Users bookmark ports. Developers remember which box runs which thing. Nobody knows if the app is even running until they try to open it.

MaplesPortal replaces that with a single landing page where applications can be discovered, monitored, and accessed — without requiring users to memorize hostnames, ports, or paths.

---

## Design Goals

MaplesPortal was built around a few simple principles:

- Keep authentication inside IBM i.
- Make adding new applications require configuration, not code.
- Provide a single URL for internal users.
- Keep application metadata separate from application logic.
- Make Db2 migration possible without redesigning the application.

---

## Features

- IBM i user authentication via IBM HTTP Server (no separate user database)
- Role-based application visibility driven by IBM i user class and group profiles
- YAML application registry with a Db2-ready architecture
- Health monitoring for backend applications
- Administrative portal with registry status and health overview
- Clean reverse proxy routing through IBM HTTP Server
- Application metadata: owners, documentation links, repositories, support contacts
- Modular Flask architecture — easy to extend

---

## Registry Backend

During early development the registry lives in YAML.

This keeps deployment simple while the application model evolves.

The registry layer intentionally abstracts the storage backend so Db2 can replace YAML without affecting routes, templates, or business logic.


---


## Architecture

```
                         Users
                           │
               ┌───────────▼───────────┐
               │    IBM HTTP Server    │
               │       Port 8081       │
               │                       │
               │  Basic auth against   │
               │  IBM i user profiles  │
               │  X-Remote-User header │
               └───────────┬───────────┘
                           │
               ┌───────────▼───────────┐
               │      MaplesPortal     │
               │    Flask + Waitress   │
               │       Port 4050       │
               │                       │
               │  Reads user header    │
               │  Resolves roles from  │
               │  QSYS2.USER_INFO      │
               │  Filters app registry │
               └───────────┬───────────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
     ┌──────▼──────┐      ...      ┌──────▼──────┐
     │    PATAI    │               │ Pattern     │
     │   Port 5000 │               │ Search      │
     │             │               │ Port 5005   │
     └─────────────┘               └─────────────┘
```

IBM HTTP Server owns authentication. MaplesPortal owns authorization. Individual applications enforce their own access controls.

---

## Repository Structure

```
portal/
├── app/
│   ├── auth/           # Authentication middleware, IBM i profile lookup
│   ├── models/         # Application dataclass
│   ├── routes/         # Home, admin, health endpoints
│   └── services/       # Registry loader, health check service
├── config/
│   ├── applications.yaml   # Application registry — add new apps here
│   ├── groups.yaml         # IBM i user class + group → portal role mapping
│   ├── settings.py         # Flask config (reads from environment variables)
│   └── users.yaml          # Emergency fallback user store (excluded from repo)
├── scripts/
│   ├── start.sh        # Start Waitress in background
│   └── stop.sh         # Stop via PID file
├── wsgi.py             # WSGI entry point
└── requirements.txt
```

---

## Running

**Development:**
```bash
python3 -m flask --app wsgi:application run
```

**Production (IBM i PASE):**
```bash
./scripts/start.sh
./scripts/stop.sh
```

Or directly:
```bash
PORTAL_ENV=production python3 -m waitress --port=4050 wsgi:application
```

---

## Configuration

### `config/applications.yaml`

The application registry. Each entry becomes a card on the portal home page.

```yaml
applications:
  - application_id: pattern-search
    name: Pattern Search
    short_description: Search rug patterns using natural language.
    category: AI Tools
    route: /apps/pattern-search
    internal_url: http://127.0.0.1:5005
    owner: Anthony Shrader
    support_contact: ashrader@maplesrugs.com
    required_roles:
      - product_users
    enabled: true
    display_order: 10
    health_check_url: http://127.0.0.1:5005/health
    environment: production
```

No restart required to add or update apps — use the Admin panel to reload the registry.

### `config/groups.yaml`

Maps IBM i user class and group profiles to portal roles. Edit this file to control who sees what without touching application code.

```yaml
user_class_roles:
  "*PGMR":
    - portal_users
    - developers
    - product_users
  "*USER":
    - portal_users
    - product_users

admin_users:
  - ASHRADER
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORTAL_ENV` | `development` | Config profile: `development`, `production` |
| `PORTAL_SECRET_KEY` | — | Flask session secret — **required in production** |
| `PORTAL_AUTH_MODE` | `proxy_header` | `proxy_header`, `session`, or `none` |
| `PORTAL_REGISTRY_PATH` | `config/applications.yaml` | Path to app registry |
| `PORTAL_GROUPS_PATH` | `config/groups.yaml` | Path to role mapping |
| `PORTAL_LOG_PATH` | `logs/portal.log` | Log file location |

### IBM HTTP Server

The portal expects IBM HTTP Server to handle authentication and pass the authenticated username as `X-Remote-User`. See the reference config in `ibm_http_server.conf`.

Core directives:

```apache
<Location />
    AuthType Basic
    AuthName "Maplesrugs Portal"
    PasswdFile %%SYSTEM%%
    Require valid-user
    RequestHeader set X-Remote-User expr=%{REMOTE_USER}
</Location>

ProxyPass /apps/pattern-search/ http://172.16.1.2:5005/
ProxyPassReverse /apps/pattern-search/ http://172.16.1.2:5005/
ProxyPass / http://172.16.1.2:4050/
ProxyPassReverse / http://172.16.1.2:4050/
```

---

## IBM i Setup Notes

`ibm_db` and `ibm_db_dbi` must be installed via yum and symlinked into the virtual environment. The PyPI versions do not build on IBM i PASE.

```bash
yum install python3-ibm_db

ln -s /QOpenSys/pkgs/lib/python3.9/site-packages/ibm_db.cpython-39.so \
      venv/lib/python3.9/site-packages/ibm_db.cpython-39.so

ln -s /QOpenSys/pkgs/lib/python3.9/site-packages/ibm_db_dbi.py \
      venv/lib/python3.9/site-packages/ibm_db_dbi.py
```

Local `ibm_db` connections use trusted authentication. Always connect with `ibm_db_dbi.connect()` — no credentials. This is intentional IBM i behavior, not a shortcut.

---

## Why IBM i?

MaplesPortal assumes IBM i already provides:

- User authentication
- User profiles
- Group membership
- System security

Rather than replacing those services, the portal integrates with them.

This keeps identity management inside IBM i while allowing modern Flask applications to participate.

---

## Roadmap

- [ ] Db2 application registry
- [ ] Automatic health monitoring with alerting
- [ ] Search and filtering on home page
- [ ] User favorites
- [ ] Usage metrics
- [ ] API for programmatic application registration

---

## Screenshots

*(Coming soon — once we're done being embarrassed by the CSS)*
