# Food Catering Order Manager

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-%20-lightgrey?logo=flask)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-blue?logo=mysql)](https://www.mysql.com/)
[![Docker](https://img.shields.io/badge/Docker-%20-blue?logo=docker)](https://www.docker.com/)
[![ngrok](https://img.shields.io/badge/ngrok-latest-purple?logo=ngrok)](https://ngrok.com/)

A lightweight catering/order management web app built with Flask and MySQL. Manage customers, products, orders, invoices, and production workflows — with real-time updates via Socket.IO and a Docker-ready setup for easy local and remote access (ngrok).

---

## 🚀 Features

- 🔐 Authentication & sessions: secure login system with password hashing and session management.
- 👥 Role-based access control: admin, order_taker, kitchen, kitchen_chef, delivery (fine-grained permission checks).
- 🧾 Order management: create, update, track order status across a multi-stage pipeline.
- 🛒 Product & catalog management: add and maintain products, prices, units and availability.
- 👨‍👩‍👧 Customer management: store customer contact and address details.
- ⚡ Real-time updates: live UI updates using flask-socketio (gevent async worker).
- 🧾 Invoice generation: invoice creation, numbering, payment status tracking and receipt notes.
- 🛠 Admin API key settings: secure admin panel to save API keys (Groq/OpenRouter) and test them.
- 🤖 AI daily reports: storage table and integration points for automated daily reports.
- 🔁 Auto DB checks & migrations: helper routines to ensure required table columns/tables exist at runtime.
- 🧾 Production pick lists & daily summaries: operational views for kitchen/production teams.
- 🖨 PDF generation support: PDF/print-friendly pages (WeasyPrint notes in docs).
- 📁 Templating & static assets: Jinja2 templates and Bootstrap-based responsive UI.

---

## 🛠️ Tech Stack

| Technology | Purpose |
| --- | --- |
| Flask | Web framework and routing |
| PyMySQL | MySQL client driver |
| MySQL (8.0) | Relational database for persistent data |
| gunicorn | Production WSGI server |
| gevent | Asynchronous worker for socket support |
| flask-socketio | Real-time websocket features |
| Docker | Containerization for local/portable deployment |
| ngrok | Secure public tunneling for local services |
| Python 3.11 | Runtime language |

---

## 📁 Project Structure

```
├─ README.md                 # THIS FILE — overview & setup
├─ README_DOCKER.md          # Docker + ngrok runbook
├─ Dockerfile                # App Docker image
├─ docker-compose.yml        # Services: flask_app, mysql, ngrok
├─ .env                      # Environment variables (template)
├─ app.py                    # Main Flask application (routes, sockets, DB helpers)
├─ config.py                 # Env loader and configuration defaults
├─ requirements.txt          # Python dependencies
├─ schema.sql                # Database schema + seed data
├─ init.sql                  # MySQL init script (mounted into container)
├─ templates/                # Jinja2 templates (HTML views)
├─ static/                   # CSS / JS / assets
└─ tickets/                  # Workflow & ticket artifacts
```

- app.py — Contains routes, DB helpers, role checks, socketio setup, invoice helpers, and admin endpoints.
- config.py — Reads environment variables (.env fallback) and exposes Config for Flask.
- Dockerfile/docker-compose.yml — Containerized runtime with MySQL and ngrok.
- schema.sql / init.sql — DB creation and seeds (auto-run for Docker MySQL initialization).

---

## ⚙️ Local Setup (Without Docker)

**Requirements**: Python 3.11, XAMPP or local MySQL server

1. Clone the repository:

```bash
git clone https://github.com/youruser/Food-Catering-Order-Manager.git
cd Food-Catering-Order-Manager
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

3. Create MySQL database and import schema (using XAMPP/MySQL Workbench or CLI):

```bash
# CLI example
mysql -u root -p
CREATE DATABASE catering_db;
exit
mysql -u root -p catering_db < schema.sql
```

4. Configure environment variables: create a `.env` file at project root (see template below).

5. Run the app:

```bash
python app.py
```

Open http://127.0.0.1:5000 in your browser.

---

## 🐳 Docker Setup (Main Setup)

**Requirements**: Docker Desktop, (optional) ngrok account for public access

### Steps

1. Clone the repo (if not already):

```bash
git clone https://github.com/youruser/Food-Catering-Order-Manager.git
cd Food-Catering-Order-Manager
```

2. Configure `.env` (template shown below):

```env
MYSQL_HOST=mysql
MYSQL_USER=root
MYSQL_PASSWORD=catering123
MYSQL_DB=catering_db
MYSQL_PORT=3306
SECRET_KEY=supersecretkey123
NGROK_AUTHTOKEN=your_ngrok_token_here
```

3. Get ngrok authtoken: sign in at https://dashboard.ngrok.com/get-started/your-authtoken and copy your token.

4. Start stack:

```bash
docker-compose up -d
```

This command builds the app image, starts MySQL with a persistent named volume, and launches ngrok (if configured).

5. (Alternative) If you prefer running ngrok locally instead of in-container:

```bash
# on your host machine after docker-compose up
ngrok http 5000
```

6. Access the app locally: http://localhost:5000

7. Access public URL:

- If ngrok runs in Docker the ngrok dashboard is available at http://localhost:4040 and shows the public forwarding URL. Share that URL to allow external access.

---

## 🔒 Environment Variables

| Variable | Description | Required |
| --- | --- | :---: |
| MYSQL_HOST | MySQL host (service name or hostname) | ✅ |
| MYSQL_USER | MySQL username | ✅ |
| MYSQL_PASSWORD | MySQL password | ✅ |
| MYSQL_DB | Database name (catering_db) | ✅ |
| MYSQL_PORT | MySQL port (default: 3306) | ✅ |
| SECRET_KEY | Flask secret key for sessions | ✅ (use strong value in production) |
| NGROK_AUTHTOKEN | ngrok authtoken for public tunnel | Optional (required for automatic in-container ngrok) |

> Note: config.py also includes optional keys for external AI providers (GROQ / OPENROUTER) — add them to `.env` if you intend to use those integrations.

---

## 🗄️ Database

- The project uses MySQL and expects a `catering_db` database.
- When using Docker, `init.sql` is mounted into `/docker-entrypoint-initdb.d/` so the schema and seed data are created automatically on first container start.

**Manual import (MySQL Workbench)**:

1. Open MySQL Workbench and connect to your local server.
2. Create a new schema named `catering_db`.
3. File > Run SQL Script... and choose `schema.sql`.

---

## 🐞 Troubleshooting

- Cryptography wheel / build errors:
  - Upgrade pip and wheel, then install cryptography:

  ```bash
  pip install --upgrade pip setuptools wheel
  pip install cryptography
  ```

  - On Windows install Visual C++ Build Tools if building from source.

- gevent / gevent-websocket errors:
  - Ensure compatible binary wheels are installed:

  ```bash
  pip install gevent gevent-websocket
  ```

  - Use the Docker image (which installs binary wheels) to avoid local build issues.

- MySQL not ready / connection errors on app start:
  - In docker-compose, `restart: always` is set for mysql and flask_app; ensure `depends_on` is configured. Consider using a wait-for script or healthcheck to delay app startup until MySQL is accepting connections.

- Internal Server Error (500) when running in Docker:
  - Check container logs:

  ```bash
  docker-compose logs -f flask_app
  docker logs flask_app
  ```

- ngrok public URL changes on restart:
  - Free ngrok URLs are ephemeral and change on each run. For a stable public domain you'll need a paid ngrok plan or use a custom tunnel solution.

---

## ⛏️ How to Stop & Start

```bash
# Start (detached)
docker-compose up -d

# Stop and remove containers
docker-compose down

# Rebuild after code changes
docker-compose up --build -d
```

---

## ☁️ Deployment (Railway)

This project has been deployed on Railway in the past. Railway (https://railway.app) can run containerized or Python apps and provides a straightforward way to deploy this stack; you can use the provided `Procfile` (`gunicorn -k gevent -w 1 app:app`) as the start command.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Make changes and add tests where appropriate.
4. Commit and push your changes: `git commit -m "Add feature"`.
5. Open a pull request and describe your changes.

Please be respectful and follow the project's code style and testing approach.

---

## 📜 License

This project is licensed under the MIT License — see the LICENSE file for details.

---

If you'd like, I can also run `git add . && git commit -m "Add professional README" && git push`. Note: I may not have permission to push from this environment — if you want me to attempt it, tell me and I'll run the commands and report back. 
