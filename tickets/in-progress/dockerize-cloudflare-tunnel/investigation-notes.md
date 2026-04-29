# Investigation Notes

## Goals

1. Confirm current runtime/deployment shape.
2. Confirm existing env-loading behavior.
3. Confirm schema source for MySQL initialization.
4. Determine minimal code/config changes for Docker + Cloudflare Tunnel.

## Sources

- `app.py`
- `config.py`
- `schema.sql`
- `requirements.txt`
- `Procfile`
- `railway.json`
- `README.md`

## Findings

- App already runs with gunicorn/gevent in Railway configs (`Procfile`, `railway.json`).
- `config.py` already checks `os.environ` before `.env` values and defaults.
- `.env` file existed with local/dev-specific values and non-Docker host.
- `app.py` DB connector did not use `MYSQL_PORT`, which is required for explicit Docker runtime portability.
- `requirements.txt` already contains required packages and does not contain `xhtml2pdf`/`reportlab`.
- `schema.sql` already contains database creation, table creation, and seed data suitable for first-run initialization.

## Scope Triage

- Classification: `Medium`
- Why: multiple deployment/runtime boundaries (application container, database container, Cloudflare tunnel container), plus config and documentation changes.

## Implications for Design

- Compose must define a service-networked hostname (`mysql`) and avoid host port dependency.
- Cloudflared must forward to container service name `flask_app:5000`.
- Runtime config should remain resilient with missing `.env`.
