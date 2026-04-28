# Docker + Cloudflare Tunnel Setup

This setup runs your Flask app, MySQL, and Cloudflare Tunnel in Docker so you can access the app from anywhere without port forwarding.

## 1. Install Docker Desktop

1. Download Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Install it and restart your PC if prompted.
3. Open Docker Desktop and wait until it shows as running.

## 2. Create a free Cloudflare Tunnel

1. Go to https://dash.cloudflare.com/
2. Open **Zero Trust**.
3. Go to **Networks** > **Tunnels**.
4. Create a tunnel (Cloudflared connector).
5. Add a public hostname route that points to `http://flask_app:5000`.

## 3. Get your tunnel token

1. In the tunnel page, find the Docker connector command.
2. Copy the token value used with `--token`.

## 4. Configure `.env`

Open `.env` and replace:

```env
TUNNEL_TOKEN=your_cloudflare_tunnel_token_here
```

## 5. Start everything

```bash
docker-compose up -d
```

This starts:

- `flask_app` (Flask via gunicorn + gevent)
- `mysql` (MySQL 8 with persistent volume)
- `cloudflared` (secure public tunnel to your Flask service)

## 6. Stop everything

```bash
docker-compose down
```

## 7. Access from anywhere

Use the Cloudflare public URL configured in your tunnel hostname. No router changes and no port forwarding are required.

## 8. Back up MySQL data

Create SQL dump:

```bash
docker exec mysql mysqldump -uroot -pcatering123 catering_db > backup.sql
```

Restore later:

```bash
docker exec -i mysql mysql -uroot -pcatering123 catering_db < backup.sql
```

## 9. Update app after new code

```bash
git pull
docker-compose up --build -d
```
