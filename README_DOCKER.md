# Docker + ngrok Setup

This setup runs your Flask app, MySQL, and ngrok in Docker so you can access the app from anywhere without port forwarding.

## 1. Install Docker Desktop

1. Download Docker Desktop: https://www.docker.com/products/docker-desktop/
2. Install it and restart your PC if prompted.
3. Open Docker Desktop and wait until it shows as running.

## 2. Create a free ngrok account

1. Go to https://ngrok.com and create a free account (no card needed).
2. Go to https://dashboard.ngrok.com/get-started/your-authtoken.
3. Copy your authtoken.

## 3. Configure `.env`

Paste your token in `.env` as:

```env
NGROK_AUTHTOKEN=your_token_here
```

## 4. Start everything

```bash
docker-compose up -d
```

This starts:

- `flask_app` (Flask via gunicorn + gevent)
- `mysql` (MySQL 8 with persistent volume)
- `ngrok` (secure public tunnel to your Flask service)

## 5. Access from anywhere

Your public URL will appear at: `http://localhost:4040`
Share that URL with anyone to access your app.

## 6. Stop everything

```bash
docker-compose down
```

## 7. Back up MySQL data

Create SQL dump:

```bash
docker exec mysql mysqldump -uroot -pcatering123 catering_db > backup.sql
```

Restore later:

```bash
docker exec -i mysql mysql -uroot -pcatering123 catering_db < backup.sql
```

## 8. Update app after new code

```bash
git pull
docker-compose up --build -d
```
