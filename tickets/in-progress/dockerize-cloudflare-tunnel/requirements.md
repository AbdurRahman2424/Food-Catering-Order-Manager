# Requirements

- Status: `Design-ready`
- Scope classification: `Medium`
- Rationale: multi-service containerization + external tunnel + runtime config + docs.

## Goal / Problem Statement

Dockerize the Flask + MySQL app and expose it securely via Cloudflare Tunnel, with persistent MySQL data and no router/port-forwarding setup.

## In-Scope Use Cases

- `UC-001`: Developer starts the full stack on a new machine with Docker Desktop.
- `UC-002`: MySQL initializes schema/data automatically on first startup.
- `UC-003`: App is reachable remotely through Cloudflare Tunnel without opening local ports.
- `UC-004`: Runtime configuration is read from environment variables (Docker-first) with `.env` fallback.
- `UC-005`: Operator can maintain, back up, stop, and update deployment using documented commands.

## Requirements

- `R-001`: Provide Dockerfile based on `python:3.11-slim`, install requirements, expose `5000`, run gunicorn gevent worker.
- `R-002`: Provide `docker-compose.yml` with `flask_app`, `mysql`, `cloudflared` services and persistent `mysql_data` volume.
- `R-003`: Provide `.env` template containing Docker/MySQL/secret/tunnel token fields.
- `R-004`: Provide `init.sql` mounted into MySQL init directory for first-run schema+seed setup.
- `R-005`: Ensure config loading uses `os.environ` first and `.env` fallback without crashing if `.env` is absent.
- `R-006`: Ensure required dependency list remains: Flask, PyMySQL, Werkzeug, flask-socketio, gevent, gevent-websocket, gunicorn.
- `R-007`: Provide Docker + Cloudflare operational documentation for install, tunnel setup, run/stop, remote access, backup, and updates.

## Acceptance Criteria

- `AC-001`: `Dockerfile` exists and runs app with `gunicorn -k gevent -w 1 app:app` while listening on port `5000`.
- `AC-002`: `docker-compose.yml` defines exactly three services: `flask_app`, `mysql`, `cloudflared`.
- `AC-003`: MySQL service uses `mysql:8.0`, creates `catering_db`, persists data to named volume.
- `AC-004`: Cloudflared uses token-driven tunnel command and forwards traffic to `flask_app:5000`.
- `AC-005`: `.env` includes `MYSQL_HOST`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB`, `MYSQL_PORT`, `SECRET_KEY`, `TUNNEL_TOKEN`.
- `AC-006`: `init.sql` is mounted and valid for first-time DB initialization.
- `AC-007`: Config resolution order is env var first, file fallback second, default fallback third, with missing `.env` tolerated.
- `AC-008`: `requirements.txt` includes required packages and excludes `xhtml2pdf` and `reportlab`.
- `AC-009`: `README_DOCKER.md` documents end-to-end setup and operational lifecycle.

## Constraints / Dependencies

- Cloudflare account and tunnel token are required.
- Docker Desktop required on target PC.
- No port-forwarding or router changes are allowed.

## Assumptions

- Existing app entrypoint remains `app:app`.
- Existing schema in repository is the canonical DB schema baseline.
- User will replace placeholder tunnel token.

## Open Questions / Risks

- Cloudflare hostname route must be configured correctly in dashboard.
- Existing local `.env` values unrelated to Docker were intentionally replaced by Docker template for consistency.

## Requirement Coverage Map (Requirement -> Use Case)

| Requirement ID | Use Case IDs |
| --- | --- |
| R-001 | UC-001 |
| R-002 | UC-001, UC-003 |
| R-003 | UC-001 |
| R-004 | UC-002 |
| R-005 | UC-001, UC-004 |
| R-006 | UC-001 |
| R-007 | UC-005 |

## Acceptance Criteria Coverage Map (AC -> Stage 7 Scenario)

| Acceptance Criteria ID | Scenario IDs |
| --- | --- |
| AC-001 | AV-001 |
| AC-002 | AV-001 |
| AC-003 | AV-002 |
| AC-004 | AV-003 |
| AC-005 | AV-001 |
| AC-006 | AV-002 |
| AC-007 | AV-004 |
| AC-008 | AV-005 |
| AC-009 | AV-006 |
