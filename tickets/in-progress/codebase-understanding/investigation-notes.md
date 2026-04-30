# Investigation Notes - Codebase Understanding

## Entrypoints
- `app.py`: Main Flask application.
- `config.py`: Environment and configuration management.
- `schema.sql`: Initial database structure.

## Architecture
- Backend: Flask (Python)
- Database: MySQL (PyMySQL)
- Frontend: HTML/Jinja2, Vanilla CSS, SocketIO for real-time updates.
- AI Integration: Supports Groq and OpenRouter for daily business summaries.

## Core Flow
1. **Authentication**: `login_required` and `role_required` decorators protect routes. Roles: admin, order_taker, kitchen, kitchen_chef, delivery.
2. **Order Lifecycle**: `received` -> `logged` -> `in_preparation` -> `ready` -> `delivered`.
3. **Invoicing**: Generated automatically or on demand. Supports payment tracking (`unpaid`, `partial`, `paid`).
4. **Kitchen/Delivery Views**: Specialized dashboards for operational staff.
5. **AI Summaries**: Aggregates daily metrics and generates analysis using LLMs.

## Subsystems
- **Auth**: Session-based, password hashing with Werkzeug.
- **Orders**: Creation, status tracking, items, comments.
- **Customers**: CRM-lite, order history.
- **Inventory (Products)**: Basic product management.
- **Billing**: Invoices, payments, receipts.
- **Reporting**: Sales metrics (daily, weekly, monthly, yearly), AI-powered operational summaries.

## Key Files
- `app.py`: Logic for routes, database helpers, AI integration, SocketIO events.
- `config.py`: Loads `.env` values, handles fallbacks.
- `templates/base.html`: Main layout with navigation and SocketIO client.
- `static/style.css`: Custom styling.

## Findings
- Database schema is dynamic in `app.py`: checks and adds columns/tables on startup (`ensure_staff_role_enum`, `ensure_invoices_table`, `ensure_ai_reports_table`).
- Role-based access is hierarchical/functional: `kitchen` and `kitchen_chef` share permissions.
- SocketIO used for broadcasting new orders, status updates, and comments.
- AI integration has a failover chain across multiple providers/keys.

## Dark Mode & UI Issues
- **Visibility**: Hardcoded `bg-white` and `bg-light` classes in templates (headers/footers) override CSS theme variables, making text invisible in dark mode.
- **Charts**: Chart.js labels in `dashboard.html` do not adapt to dark mode.
- **API Connectivity Test**: Identified as a redundant feature to be removed. Logic resides in `app.py` (`run_api_key_chain_test`, `/admin/api-key-test`) and `admin_api_settings.html`.
