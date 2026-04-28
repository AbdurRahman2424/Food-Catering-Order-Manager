# Proposed Design (v1)

## Current State (As-Is)

- App can run directly or via Railway.
- Local DB assumptions are host-based (`localhost` pattern).
- No container orchestration and no Cloudflare tunnel service in repo.

## Target State (To-Be)

- Spine `DS-001`: `cloudflared -> flask_app (gunicorn/gevent) -> mysql`.
- One compose-managed network where services resolve by service name.
- MySQL auto-initializes from mounted `init.sql`.
- Runtime config resolved from environment first, `.env` fallback second.

## Ownership / Boundaries

- `Dockerfile`: owns app runtime image definition.
- `docker-compose.yml`: owns service graph and runtime wiring.
- `.env`: owns deployment-time values.
- `init.sql`: owns first-run DB schema+seed bootstrap.
- `README_DOCKER.md`: owns operational runbook.
- `config.py` and `app.py`: own runtime configuration and DB connection behavior.

## Change Inventory

| Change ID | Type | File | Change |
| --- | --- | --- | --- |
| C-001 | Add | `Dockerfile` | Python 3.11 slim app image with gunicorn startup |
| C-002 | Add | `docker-compose.yml` | Flask + MySQL + cloudflared services |
| C-003 | Modify | `.env` | Docker template values + tunnel token placeholder |
| C-004 | Add | `init.sql` | MySQL first-run schema/seed init script |
| C-005 | Add | `README_DOCKER.md` | Full Docker + Cloudflare setup and operations |
| C-006 | Modify | `config.py` | Cached env-file loading with env-first fallback semantics |
| C-007 | Modify | `app.py` | MySQL port usage + env cache invalidation on write |

## Naming Decisions

- `flask_app`, `mysql`, `cloudflared` service names are explicit and environment-agnostic.
- Ticket name: `dockerize-cloudflare-tunnel` maps directly to scope.
