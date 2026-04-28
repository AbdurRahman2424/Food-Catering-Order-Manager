# Future-State Runtime Call Stack (v1)

## UC-001 Start Full Stack

- Spine ID: `DS-001`
- Source Type: `Requirement`
- Entry: `docker compose up -d`
1. `docker-compose.yml:flask_app` build+run starts app container.
2. `Dockerfile:CMD` launches `gunicorn -k gevent -w 1 app:app`.
3. `config.py:get_env_value` resolves config from env vars.
4. `app.py:get_db` connects to `mysql:3306`.
5. Flask app serves requests through gunicorn/gevent.

## UC-002 First-Run Database Bootstrap

- Spine ID: `DS-002`
- Source Type: `Requirement`
1. `docker-compose.yml:mysql` mounts `./init.sql` into `/docker-entrypoint-initdb.d/`.
2. `mysql:8.0` entrypoint executes init SQL on first startup.
3. `init.sql` creates database/tables and seed rows.
4. App queries initialized tables successfully.

## UC-003 Remote Access Without Port Forwarding

- Spine ID: `DS-003`
- Source Type: `Requirement`
1. `docker-compose.yml:cloudflared` starts `tunnel --no-autoupdate run --token ...`.
2. Cloudflare edge forwards hostname traffic through tunnel.
3. Tunnel routes traffic to `flask_app:5000`.
4. Flask responds to requests; router remains closed.

## UC-004 Config Resolution Safety

- Spine ID: `DS-004`
- Source Type: `Requirement`
1. `config.py:get_env_value` checks `os.environ` first.
2. If missing, `config.py:load_env_file` reads `.env` if present.
3. If `.env` missing or key absent, defaults are used.
4. Runtime stays non-crashing on missing `.env`.
