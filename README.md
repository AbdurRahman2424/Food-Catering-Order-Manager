# FreshPlate Co. - Food & Catering Order Manager

A full-stack internal tool for managing catering orders, preparation stages, and product catalogs. Built with Python Flask, MySQL, and Bootstrap 5.

## Features
- **Order Management:** Create, track, and update orders through a 5-stage pipeline.
- **Dynamic Order Creation:** Add multiple products to a single order with live total calculation.
- **Product Catalog:** Manage products, units, and pricing.
- **Daily Summary:** Overview of orders due today, overdue orders, and production metrics.
- **Production Pick List:** Aggregate view of all items needed for orders in the preparation stage (print-optimized).
- **Responsive UI:** Works on both desktop and mobile browsers using Bootstrap 5.

## Prerequisites
- Python 3.x
- MySQL Server

## Installation & Setup

1. **Clone the repository** (or extract the files).

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Database Setup:**
   - Create a MySQL database named `catering_db`.
   - Run the provided `schema.sql` to create tables and seed initial data.
   ```bash
   mysql -u your_username -p catering_db < schema.sql
   ```

4. **Configuration:**
   - Open `config.py` and update the `MYSQL_USER` and `MYSQL_PASSWORD` to match your local MySQL credentials.
   - (Optional) Change the `SECRET_KEY` for production.

5. **Run the application:**
   ```bash
   python app.py
   ```
   The app will be available at `http://127.0.0.1:5000`.

## Default Credentials
- **Email:** `admin@catering.com`
- **Password:** `admin123`

## File Structure
- `app.py`: Main Flask application logic and routes.
- `config.py`: Database and Flask configuration.
- `schema.sql`: MySQL database schema and seed data.
- `templates/`: Jinja2 HTML templates using Bootstrap 5.
- `static/`: Custom CSS and assets.
- `requirements.txt`: Python package dependencies.
