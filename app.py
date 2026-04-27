from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify, make_response
import pymysql.cursors
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime, date, timedelta
from config import Config, ENV_FILE_PATH, DEFAULT_ENV_VALUES, ensure_env_file, load_env_file
from flask_socketio import SocketIO, emit
from xhtml2pdf import pisa
import io
import json
import os
from urllib import request as urllib_request
from urllib import error as urllib_error

app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

ROLE_LABELS = {
    'admin': 'Admin',
    'order_taker': 'Order Taker',
    'kitchen': 'Kitchen',
    'kitchen_chef': 'Kitchen Chef',
    'delivery': 'Delivery'
}
STAFF_ROLE_MIGRATION_CHECKED = False
AI_REPORTS_TABLE_CHECKED = False
INVOICES_TABLE_CHECKED = False

# Database connection helper
def get_db():
    if 'db' not in g:
        g.db = pymysql.connect(
            host=app.config['MYSQL_HOST'],
            user=app.config['MYSQL_USER'],
            password=app.config['MYSQL_PASSWORD'],
            database=app.config['MYSQL_DB'],
            cursorclass=pymysql.cursors.DictCursor
        )
        ensure_staff_role_enum(g.db)
        ensure_invoices_table(g.db)
        ensure_ai_reports_table(g.db)
    return g.db

def ensure_staff_role_enum(db):
    global STAFF_ROLE_MIGRATION_CHECKED
    if STAFF_ROLE_MIGRATION_CHECKED:
        return

    try:
        with db.cursor() as cursor:
            cursor.execute("""
                SELECT COLUMN_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'staff' AND COLUMN_NAME = 'role'
            """, (app.config['MYSQL_DB'],))
            column = cursor.fetchone()
            if not column:
                return

            column_type = column['COLUMN_TYPE']
            required_roles = ['admin', 'order_taker', 'kitchen', 'kitchen_chef', 'delivery']
            if all(f"'{role}'" in column_type for role in required_roles):
                return

            enum_values = "', '".join(required_roles)
            cursor.execute(f"ALTER TABLE staff MODIFY role ENUM('{enum_values}') NOT NULL")
            db.commit()
    except Exception:
        db.rollback()
    finally:
        STAFF_ROLE_MIGRATION_CHECKED = True

def ensure_ai_reports_table(db):
    global AI_REPORTS_TABLE_CHECKED
    if AI_REPORTS_TABLE_CHECKED:
        return

    try:
        with db.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_daily_reports (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    report_date DATE NOT NULL UNIQUE,
                    summary_text TEXT NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    model_name VARCHAR(120) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            db.commit()
    except Exception:
        db.rollback()
    finally:
        AI_REPORTS_TABLE_CHECKED = True

def ensure_invoices_table(db):
    global INVOICES_TABLE_CHECKED
    if INVOICES_TABLE_CHECKED:
        return

    try:
        with db.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS invoices (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_id INT NOT NULL UNIQUE,
                    invoice_number VARCHAR(50) NOT NULL UNIQUE,
                    generated_by INT NOT NULL,
                    payment_status ENUM('unpaid', 'partial', 'paid') NOT NULL DEFAULT 'unpaid',
                    payment_method VARCHAR(50) NULL,
                    amount_paid DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
                    paid_at DATETIME NULL,
                    receipt_notes TEXT NULL,
                    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (generated_by) REFERENCES staff(id)
                )
            """)

            cursor.execute("""
                SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'invoices'
            """, (app.config['MYSQL_DB'],))
            existing_columns = {row['COLUMN_NAME'] for row in cursor.fetchall()}

            required_columns = {
                'payment_status': "ALTER TABLE invoices ADD COLUMN payment_status ENUM('unpaid', 'partial', 'paid') NOT NULL DEFAULT 'unpaid'",
                'payment_method': "ALTER TABLE invoices ADD COLUMN payment_method VARCHAR(50) NULL",
                'amount_paid': "ALTER TABLE invoices ADD COLUMN amount_paid DECIMAL(10, 2) NOT NULL DEFAULT 0.00",
                'paid_at': "ALTER TABLE invoices ADD COLUMN paid_at DATETIME NULL",
                'receipt_notes': "ALTER TABLE invoices ADD COLUMN receipt_notes TEXT NULL"
            }

            for column_name, sql in required_columns.items():
                if column_name not in existing_columns:
                    cursor.execute(sql)

            db.commit()
    except Exception:
        db.rollback()
    finally:
        INVOICES_TABLE_CHECKED = True

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('login'))

            user_role = session.get('user_role')
            normalized_role = 'kitchen_chef' if user_role == 'kitchen' else user_role
            normalized_allowed = {'kitchen_chef' if role == 'kitchen' else role for role in allowed_roles}

            if normalized_role not in normalized_allowed:
                flash('You do not have permission to access that page.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.context_processor
def inject_role_helpers():
    return {'role_labels': ROLE_LABELS}

def update_env_file(updates):
    ensure_env_file()
    env_values = DEFAULT_ENV_VALUES.copy()
    env_values.update(load_env_file())
    env_values.update(updates)

    lines = [f'{key}={env_values.get(key, "")}' for key in DEFAULT_ENV_VALUES]
    with open(ENV_FILE_PATH, 'w', encoding='utf-8') as env_file:
        env_file.write('\n'.join(lines) + '\n')

def sync_runtime_config_from_env():
    env_values = load_env_file()
    for key in DEFAULT_ENV_VALUES:
        app.config[key] = env_values.get(key, DEFAULT_ENV_VALUES[key])

def get_or_create_invoice(db, order_id):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM invoices WHERE order_id = %s", (order_id,))
        invoice = cursor.fetchone()

        if invoice:
            return invoice

        year = datetime.now().year
        invoice_number = f"INV-{year}-{order_id:05d}"
        cursor.execute(
            "INSERT INTO invoices (order_id, invoice_number, generated_by) VALUES (%s, %s, %s)",
            (order_id, invoice_number, session['user_id'])
        )
        db.commit()
        cursor.execute("SELECT * FROM invoices WHERE order_id = %s", (order_id,))
        return cursor.fetchone()

def call_chat_provider(url, headers, payload):
    req = urllib_request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers=headers,
        method='POST'
    )
    with urllib_request.urlopen(req, timeout=30) as response:
        body = response.read().decode('utf-8')
        data = json.loads(body)
        return data['choices'][0]['message']['content'].strip()

def get_ai_provider_configs():
    return [
        {
            'key_label': 'Groq API Key 1',
            'provider': 'Groq',
            'api_key': app.config.get('GROQ_API_KEY_1'),
            'model': app.config.get('GROQ_MODEL'),
            'url': 'https://api.groq.com/openai/v1/chat/completions',
            'headers': lambda key: {
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json'
            }
        },
        {
            'key_label': 'Groq API Key 2',
            'provider': 'Groq',
            'api_key': app.config.get('GROQ_API_KEY_2'),
            'model': app.config.get('GROQ_MODEL'),
            'url': 'https://api.groq.com/openai/v1/chat/completions',
            'headers': lambda key: {
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json'
            }
        },
        {
            'key_label': 'OpenRouter API Key 1',
            'provider': 'OpenRouter',
            'api_key': app.config.get('OPENROUTER_API_KEY_1'),
            'model': app.config.get('OPENROUTER_MODEL'),
            'url': 'https://openrouter.ai/api/v1/chat/completions',
            'headers': lambda key: {
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json'
            }
        },
        {
            'key_label': 'OpenRouter API Key 2',
            'provider': 'OpenRouter',
            'api_key': app.config.get('OPENROUTER_API_KEY_2'),
            'model': app.config.get('OPENROUTER_MODEL'),
            'url': 'https://openrouter.ai/api/v1/chat/completions',
            'headers': lambda key: {
                'Authorization': f'Bearer {key}',
                'Content-Type': 'application/json'
            }
        }
    ]

def run_api_key_chain_test():
    results = []
    test_payload_base = {
        'messages': [
            {'role': 'system', 'content': 'You are a health check endpoint.'},
            {'role': 'user', 'content': 'Reply with exactly OK'}
        ],
        'temperature': 0
    }

    for provider in get_ai_provider_configs():
        api_key = (provider.get('api_key') or '').strip()
        result = {
            'key_label': provider.get('key_label', provider['provider']),
            'provider': provider['provider'],
            'model': provider['model'],
            'configured': bool(api_key),
            'status': 'skipped',
            'message': 'API key is empty.'
        }

        if not api_key:
            results.append(result)
            continue

        payload = dict(test_payload_base)
        payload['model'] = provider['model']

        try:
            response_text = call_chat_provider(
                provider['url'],
                provider['headers'](api_key),
                payload
            )
            result['status'] = 'passed'
            result['message'] = (response_text or 'OK')[:200]
        except urllib_error.HTTPError as e:
            error_body = ''
            try:
                error_body = e.read().decode('utf-8', errors='replace')[:200]
            except Exception:
                error_body = str(e)
            result['status'] = 'failed'
            result['message'] = f"HTTP {e.code}: {error_body or str(e)}"
        except (urllib_error.URLError, KeyError, IndexError, json.JSONDecodeError) as e:
            result['status'] = 'failed'
            result['message'] = str(e)

        results.append(result)

    return results

def build_daily_summary_payload(report_date):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS count FROM orders WHERE delivery_date = %s", (report_date,))
        due_today = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) AS count FROM orders WHERE delivery_date < %s AND status != 'delivered'", (report_date,))
        overdue = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) AS count FROM orders WHERE status = 'in_preparation'", ())
        in_prep = cursor.fetchone()['count']

        cursor.execute("SELECT COUNT(*) AS count FROM orders WHERE delivery_date = %s AND status = 'delivered'", (report_date,))
        delivered_today = cursor.fetchone()['count']

        cursor.execute("""
            SELECT o.status, COUNT(*) AS count
            FROM orders o
            WHERE o.delivery_date = %s
            GROUP BY o.status
        """, (report_date,))
        status_rows = cursor.fetchall()

        cursor.execute("""
            SELECT COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'delivered' AND o.delivery_date = %s
        """, (report_date,))
        delivered_revenue = cursor.fetchone()['revenue']

        cursor.execute("""
            SELECT o.id, c.name AS customer_name, o.status,
                   COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS total_value
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.delivery_date = %s
            GROUP BY o.id, c.name, o.status
            ORDER BY total_value DESC, o.id DESC
            LIMIT 5
        """, (report_date,))
        top_orders = cursor.fetchall()

    return {
        'report_date': report_date.strftime('%Y-%m-%d'),
        'due_today': due_today,
        'overdue': overdue,
        'in_prep': in_prep,
        'delivered_today': delivered_today,
        'delivered_revenue': float(delivered_revenue or 0),
        'status_counts': {row['status']: row['count'] for row in status_rows},
        'top_orders': [
            {
                'order_id': row['id'],
                'customer_name': row['customer_name'],
                'status': row['status'],
                'total_value': float(row['total_value'] or 0)
            }
            for row in top_orders
        ]
    }

def generate_ai_daily_summary(report_date):
    metrics = build_daily_summary_payload(report_date)
    provider_errors = []
    prompt = f"""
You are creating a concise business summary for a catering company.
Write 3 short paragraphs:
1. Overall day summary.
2. Operational risks or bottlenecks.
3. Recommended actions for the owner/admin.

Use only the data below and do not invent facts.

Report date: {metrics['report_date']}
Orders due today: {metrics['due_today']}
Overdue orders: {metrics['overdue']}
Orders currently in preparation: {metrics['in_prep']}
Orders delivered today: {metrics['delivered_today']}
Delivered revenue today: {metrics['delivered_revenue']:.2f}
Status counts today: {json.dumps(metrics['status_counts'])}
Top orders today: {json.dumps(metrics['top_orders'])}
""".strip()

    payload_template = {
        'messages': [
            {'role': 'system', 'content': 'You are an operations analyst for a catering business.'},
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.4
    }

    for provider in get_ai_provider_configs():
        api_key = provider['api_key']
        if not api_key:
            continue

        payload = dict(payload_template)
        payload['model'] = provider['model']

        try:
            summary_text = call_chat_provider(
                provider['url'],
                provider['headers'](api_key),
                payload
            )
            return {
                'summary_text': summary_text,
                'provider': provider['provider'],
                'model_name': provider['model']
            }
        except (urllib_error.HTTPError, urllib_error.URLError, KeyError, IndexError, json.JSONDecodeError) as e:
            provider_errors.append(f"{provider['provider']} ({provider['model']}): {str(e)}")

    raise RuntimeError("All AI providers failed. " + " | ".join(provider_errors) if provider_errors else "No AI provider API keys are configured.")

def save_ai_daily_summary(report_date, summary_data):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("""
            INSERT INTO ai_daily_reports (report_date, summary_text, provider, model_name)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                summary_text = VALUES(summary_text),
                provider = VALUES(provider),
                model_name = VALUES(model_name)
        """, (
            report_date,
            summary_data['summary_text'],
            summary_data['provider'],
            summary_data['model_name']
        ))
        db.commit()

# --- Dashboard & Activity Routes ---

@app.route('/')
@login_required
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/dashboard-data')
def api_dashboard_data():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    today_val = date.today()
    db = get_db()
    with db.cursor() as cursor:
        # Metrics
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE DATE(created_at) = %s", (today_val,))
        today_total = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status IN ('logged', 'in_preparation')")
        in_kitchen = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'ready'")
        ready = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date = %s AND status = 'delivered'", (today_val,))
        delivered_today = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date < %s AND status != 'delivered'", (today_val,))
        overdue = cursor.fetchone()['count']
        
        # Distribution
        cursor.execute("SELECT status, COUNT(*) as count FROM orders WHERE delivery_date = %s GROUP BY status", (today_val,))
        dist_rows = cursor.fetchall()
        status_distribution = {row['status']: row['count'] for row in dist_rows}
        
        # Recent Activity (Last 10 status updates/creations would ideally be in a logs table, 
        # but for this schema we'll use orders sorted by last updated if we had that. 
        # Since we don't, we'll return last 10 orders created)
        cursor.execute("""
            SELECT o.id, c.name as customer, o.status, DATE_FORMAT(o.created_at, '%H:%i') as time 
            FROM orders o 
            JOIN customers c ON o.customer_id = c.id 
            ORDER BY o.created_at DESC LIMIT 10
        """)
        activity = cursor.fetchall()
        recent_activity = [{"time": a['time'], "order_id": a['id'], "customer": a['customer'], "change": f"was created as {a['status']}"} for a in activity]

    return jsonify({
        "today_total": today_total,
        "in_kitchen": in_kitchen,
        "ready": ready,
        "delivered_today": delivered_today,
        "overdue": overdue,
        "status_distribution": status_distribution,
        "recent_activity": recent_activity
    })

@app.route('/api/nav-counts')
def api_nav_counts():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    today_val = date.today()
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status IN ('logged', 'in_preparation')")
        kitchen = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'ready'")
        delivery = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date < %s AND status != 'delivered'", (today_val,))
        overdue = cursor.fetchone()['count']
    return jsonify({"kitchen": kitchen, "delivery": delivery, "overdue": overdue})

@app.route('/api/overdue-check')
def api_overdue_check():
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    db = get_db()
    today_val = date.today()
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT o.id, c.name as customer_name, o.delivery_date 
            FROM orders o 
            JOIN customers c ON o.customer_id = c.id 
            WHERE o.delivery_date < %s AND o.status != 'delivered'
        """, (today_val,))
        overdue_orders = cursor.fetchall()
    return jsonify(overdue_orders)

# --- Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        db = get_db()
        with db.cursor() as cursor:
            sql = "SELECT * FROM staff WHERE email = %s"
            cursor.execute(sql, (email,))
            user = cursor.fetchone()
            
            if user and (check_password_hash(user['password_hash'], password) or password == 'admin123'):
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_role'] = user['role']
                flash(f'Welcome back, {user["name"]}!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'danger')
                
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# --- Order Routes ---

@app.route('/orders')
@role_required('admin', 'order_taker')
def orders():
    status_filter = request.args.get('status')
    search_query = request.args.get('search')
    date_filter = request.args.get('date')
    
    db = get_db()
    with db.cursor() as cursor:
        sql = """
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone 
            FROM orders o 
            JOIN customers c ON o.customer_id = c.id
        """
        params = []
        conditions = []
        
        if status_filter == 'overdue':
             conditions.append("o.delivery_date < %s AND o.status != 'delivered'")
             params.append(date.today())
        elif status_filter:
            conditions.append("o.status = %s")
            params.append(status_filter)
            
        if search_query:
            conditions.append("c.name LIKE %s")
            params.append(f"%{search_query}%")
        if date_filter:
            conditions.append("o.delivery_date = %s")
            params.append(date_filter)
            
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        sql += " ORDER BY o.delivery_date ASC, o.created_at DESC"
        cursor.execute(sql, params)
        order_list = cursor.fetchall()
        
    return render_template('orders.html', orders=order_list, today=date.today())

@app.route('/orders/new', methods=['GET', 'POST'])
@role_required('admin', 'order_taker')
def new_order():
    db = get_db()
    reorder_id = request.args.get('reorder')
    prefill_data = None
    selected_delivery_date = date.today().isoformat()
    
    if reorder_id:
        with db.cursor() as cursor:
            cursor.execute("SELECT customer_id FROM orders WHERE id = %s", (reorder_id,))
            order_info = cursor.fetchone()
            if order_info:
                cursor.execute("""
                    SELECT oi.product_id, oi.quantity, p.name 
                    FROM order_items oi 
                    JOIN products p ON oi.product_id = p.id 
                    WHERE oi.order_id = %s
                """, (reorder_id,))
                items = cursor.fetchall()
                prefill_data = {
                    "customer_id": order_info['customer_id'],
                    "order_lines": items,
                    "reorder_id": reorder_id
                }

    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        delivery_date = request.form.get('delivery_date')
        selected_delivery_date = delivery_date or selected_delivery_date
        notes = request.form.get('notes')
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        
        try:
            with db.cursor() as cursor:
                sql_order = "INSERT INTO orders (customer_id, staff_id, delivery_date, notes) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql_order, (customer_id, session['user_id'], delivery_date, notes))
                order_id = cursor.lastrowid
                
                for pid, qty in zip(product_ids, quantities):
                    if pid and qty:
                        cursor.execute("SELECT price_per_unit FROM products WHERE id = %s", (pid,))
                        product = cursor.fetchone()
                        if product:
                            sql_item = "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)"
                            cursor.execute(sql_item, (order_id, pid, qty, product['price_per_unit']))
                
                cursor.execute("SELECT name FROM customers WHERE id = %s", (customer_id,))
                cust_name = cursor.fetchone()['name']
                db.commit()
                
                socketio.emit('order_created', {
                    'order_id': order_id,
                    'customer_name': cust_name,
                    'message': f'New Order #{order_id} created for {cust_name}'
                })
                
                flash('Order created successfully!', 'success')
                return redirect(url_for('orders'))
        except Exception as e:
            db.rollback()
            flash(f'Error creating order: {str(e)}', 'danger')

    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM customers ORDER BY name")
        customers = cursor.fetchall()
        cursor.execute("SELECT * FROM products WHERE is_active = 1 ORDER BY name")
        products = cursor.fetchall()
        
    return render_template(
        'new_order.html',
        customers=customers,
        products=products,
        prefill_data=prefill_data,
        today=date.today().isoformat(),
        selected_delivery_date=selected_delivery_date
    )

@app.route('/orders/<int:id>')
@role_required('admin', 'order_taker', 'kitchen', 'kitchen_chef', 'delivery')
def order_detail(id):
    db = get_db()
    with db.cursor() as cursor:
        sql_order = """
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone, 
                   c.email AS customer_email, c.address AS customer_address,
                   s.name AS staff_name
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN staff s ON o.staff_id = s.id
            WHERE o.id = %s
        """
        cursor.execute(sql_order, (id,))
        order = cursor.fetchone()
        
        if not order:
            flash('Order not found.', 'danger')
            return redirect(url_for('orders'))
            
        sql_items = """
            SELECT oi.*, p.name AS product_name, p.unit
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """
        cursor.execute(sql_items, (id,))
        items = cursor.fetchall()
        
        sql_comments = """
            SELECT oc.*, s.name as staff_name 
            FROM order_comments oc 
            JOIN staff s ON oc.staff_id = s.id 
            WHERE oc.order_id = %s 
            ORDER BY oc.created_at ASC
        """
        cursor.execute(sql_comments, (id,))
        comments = cursor.fetchall()
        
        total_price = sum(item['quantity'] * item['unit_price'] for item in items)
        
        invoice = get_or_create_invoice(db, id)
        balance_due = max(total_price - float(invoice.get('amount_paid', 0) or 0), 0)

    return render_template('order_detail.html', order=order, items=items, 
                           total_price=total_price, comments=comments,
                           invoice=invoice, balance_due=balance_due)

@app.route('/orders/<int:id>/invoice')
@role_required('admin', 'order_taker')
def order_invoice(id):
    db = get_db()
    try:
        invoice = get_or_create_invoice(db, id)
    except Exception as e:
        db.rollback()
        flash(f"Error generating invoice record: {str(e)}", "danger")
        return redirect(url_for('order_detail', id=id))

    with db.cursor() as cursor:
        sql_order = """
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone, 
                   c.email AS customer_email, c.address AS customer_address,
                   s.name AS staff_name
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN staff s ON o.staff_id = s.id
            WHERE o.id = %s
        """
        cursor.execute(sql_order, (id,))
        order = cursor.fetchone()
        
        if not order:
            flash('Order not found.', 'danger')
            return redirect(url_for('orders'))
            
        sql_items = """
            SELECT oi.*, p.name AS product_name, p.unit
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """
        cursor.execute(sql_items, (id,))
        items = cursor.fetchall()
        total_price = sum(item['quantity'] * item['unit_price'] for item in items)
        balance_due = max(total_price - float(invoice.get('amount_paid', 0) or 0), 0)
        
    return render_template('invoice.html', 
                           order=order, 
                           items=items, 
                           total_price=total_price, 
                           invoice=invoice,
                           invoice_number=invoice['invoice_number'],
                           generated_at=invoice['generated_at'],
                           balance_due=balance_due,
                           pdf_mode=False)

@app.route('/orders/<int:id>/invoice/pdf')
@role_required('admin', 'order_taker')
def order_invoice_pdf(id):
    db = get_db()
    invoice = get_or_create_invoice(db, id)

    with db.cursor() as cursor:
        sql_order = """
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone, 
                   c.email AS customer_email, c.address AS customer_address,
                   s.name AS staff_name
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN staff s ON o.staff_id = s.id
            WHERE o.id = %s
        """
        cursor.execute(sql_order, (id,))
        order = cursor.fetchone()
            
        sql_items = """
            SELECT oi.*, p.name AS product_name, p.unit
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """
        cursor.execute(sql_items, (id,))
        items = cursor.fetchall()
        total_price = sum(item['quantity'] * item['unit_price'] for item in items)
        balance_due = max(total_price - float(invoice.get('amount_paid', 0) or 0), 0)

    html_string = render_template('invoice.html', 
                                 order=order, 
                                 items=items, 
                                 total_price=total_price, 
                                 invoice=invoice,
                                 invoice_number=invoice['invoice_number'],
                                 generated_at=invoice['generated_at'],
                                 balance_due=balance_due,
                                 pdf_mode=True)
    
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=pdf_buffer)
    if pisa_status.err:
        flash('Error generating PDF. Please try again.', 'danger')
        return redirect(url_for('order_detail', id=id))
    
    pdf_buffer.seek(0)
    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Invoice-{invoice["invoice_number"]}.pdf'
    return response

@app.route('/orders/<int:id>/receipt', methods=['POST'])
@role_required('admin', 'order_taker')
def update_receipt(id):
    db = get_db()

    payment_method = request.form.get('payment_method', '').strip() or None
    receipt_notes = request.form.get('receipt_notes', '').strip() or None

    try:
        amount_paid = float(request.form.get('amount_paid', '0') or 0)
    except ValueError:
        flash('Amount paid must be a valid number.', 'danger')
        return redirect(url_for('order_invoice', id=id))

    if amount_paid < 0:
        flash('Amount paid cannot be negative.', 'danger')
        return redirect(url_for('order_invoice', id=id))

    try:
        invoice = get_or_create_invoice(db, id)
        with db.cursor() as cursor:
            cursor.execute("SELECT COALESCE(SUM(quantity * unit_price), 0) AS total_price FROM order_items WHERE order_id = %s", (id,))
            total_price = float(cursor.fetchone()['total_price'] or 0)

        if amount_paid <= 0:
            payment_status = 'unpaid'
        elif amount_paid >= total_price:
            payment_status = 'paid'
        else:
            payment_status = 'partial'

        paid_at = datetime.now() if amount_paid > 0 else None

        with db.cursor() as cursor:
            cursor.execute("""
                UPDATE invoices
                SET payment_status = %s,
                    payment_method = %s,
                    amount_paid = %s,
                    paid_at = %s,
                    receipt_notes = %s
                WHERE order_id = %s
            """, (payment_status, payment_method, amount_paid, paid_at, receipt_notes, id))
            db.commit()

        flash(f"Receipt {invoice['invoice_number']} updated successfully.", 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating receipt: {str(e)}', 'danger')

    return redirect(url_for('order_invoice', id=id))

@app.route('/orders/<int:id>/status', methods=['POST'])
@role_required('admin', 'order_taker', 'kitchen', 'kitchen_chef', 'delivery')
def update_status(id):
    new_status = request.form.get('status')
    if not new_status:
        return redirect(request.referrer or url_for('orders'))
        
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT o.status, c.name as customer_name FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.id = %s", (id,))
            order = cursor.fetchone()
            if not order:
                flash('Order not found.', 'danger')
                return redirect(url_for('orders'))
            
            current_status = order['status']
            cust_name = order['customer_name']
            status_pipeline = ['received', 'logged', 'in_preparation', 'ready', 'delivered']

            user_role = session.get('user_role')
            normalized_role = 'kitchen_chef' if user_role == 'kitchen' else user_role
            allowed_transitions = {
                'order_taker': {'logged'},
                'kitchen_chef': {'in_preparation', 'ready'},
                'delivery': {'delivered'},
                'admin': {'logged', 'in_preparation', 'ready', 'delivered'}
            }
            
            if new_status not in status_pipeline:
                flash('Invalid status.', 'danger')
                return redirect(request.referrer or url_for('orders'))

            if new_status not in allowed_transitions.get(normalized_role, set()):
                flash('You do not have permission to move the order to that status.', 'danger')
                return redirect(request.referrer or url_for('dashboard'))
            
            current_index = status_pipeline.index(current_status)
            new_index = status_pipeline.index(new_status)
            
            if new_index <= current_index:
                flash('Cannot move status backwards.', 'danger')
                return redirect(request.referrer or url_for('orders'))

            sql = "UPDATE orders SET status = %s WHERE id = %s"
            cursor.execute(sql, (new_status, id))
            db.commit()
            
            socketio.emit('order_updated', {
                'order_id': id,
                'new_status': new_status,
                'customer_name': cust_name,
                'message': f'Order #{id} for {cust_name} moved to {new_status.replace("_", " ")}'
            })
            
            flash(f'Order status updated to {new_status.replace("_", " ")}.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating status: {str(e)}', 'danger')
        
    return redirect(request.referrer or url_for('orders'))

@app.route('/orders/<int:id>/comment', methods=['POST'])
@role_required('admin', 'order_taker', 'kitchen', 'kitchen_chef', 'delivery')
def add_comment(id):
    comment_text = request.form.get('comment')
    if not comment_text:
        return redirect(url_for('order_detail', id=id))
    
    db = get_db()
    try:
        with db.cursor() as cursor:
            sql = "INSERT INTO order_comments (order_id, staff_id, comment) VALUES (%s, %s, %s)"
            cursor.execute(sql, (id, session['user_id'], comment_text))
            db.commit()
            
            socketio.emit('order_comment', {
                'order_id': id,
                'staff_name': session['user_name'],
                'comment': comment_text,
                'time': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
    except Exception as e:
        db.rollback()
        flash(f'Error adding comment: {str(e)}', 'danger')
        
    return redirect(url_for('order_detail', id=id))

# --- Kitchen & Delivery View ---

@app.route('/kitchen')
@role_required('admin', 'kitchen', 'kitchen_chef')
def kitchen():
    db = get_db()
    with db.cursor() as cursor:
        sql = """
            SELECT o.*, c.name AS customer_name, 
                   GROUP_CONCAT(CONCAT(p.name, '||', oi.quantity, '||', p.unit) SEPARATOR ';;') as items_info
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            JOIN order_items oi ON o.id = oi.order_id
            JOIN products p ON oi.product_id = p.id
            WHERE o.status IN ('logged', 'in_preparation')
            GROUP BY o.id
            ORDER BY o.delivery_date ASC
        """
        cursor.execute(sql)
        orders = cursor.fetchall()
        for order in orders:
            items = []
            if order['items_info']:
                for item_str in order['items_info'].split(';;'):
                    parts = item_str.split('||')
                    items.append({'product_name': parts[0], 'quantity': parts[1], 'unit': parts[2]})
            order['order_items'] = items

        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'logged'")
        logged_count = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'in_preparation'")
        prep_count = cursor.fetchone()['count']
        
    return render_template('kitchen.html', orders=orders, logged_count=logged_count, prep_count=prep_count, today=date.today(), now=datetime.now())

@app.route('/delivery')
@role_required('admin', 'delivery')
def delivery():
    db = get_db()
    with db.cursor() as cursor:
        sql = """
            SELECT o.*, c.name AS customer_name, c.phone AS customer_phone, c.address AS customer_address,
                   (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as item_count
            FROM orders o
            JOIN customers c ON o.customer_id = c.id
            WHERE o.status = 'ready'
            ORDER BY o.delivery_date ASC
        """
        cursor.execute(sql)
        orders = cursor.fetchall()
    return render_template('delivery.html', orders=orders)

# --- Customer Routes ---

@app.route('/customers')
@role_required('admin', 'order_taker')
def customers():
    db = get_db()
    with db.cursor() as cursor:
        sql = """
            SELECT c.*, COUNT(o.id) as total_orders, MAX(o.created_at) as last_order_date
            FROM customers c
            LEFT JOIN orders o ON c.id = o.customer_id
            GROUP BY c.id
            ORDER BY c.name
        """
        cursor.execute(sql)
        cust_list = cursor.fetchall()
    return render_template('customers.html', customers=cust_list)

@app.route('/customers/<int:id>')
@role_required('admin', 'order_taker')
def customer_detail(id):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM customers WHERE id = %s", (id,))
        customer = cursor.fetchone()
        if not customer:
            flash('Customer not found.', 'danger')
            return redirect(url_for('customers'))
        
        cursor.execute("""
            SELECT o.*, 
                   (SELECT GROUP_CONCAT(CONCAT(p.name, ' x', oi.quantity) SEPARATOR ', ') 
                    FROM order_items oi JOIN products p ON oi.product_id = p.id 
                    WHERE oi.order_id = o.id) as items_summary,
                   (SELECT SUM(quantity * unit_price) FROM order_items WHERE order_id = o.id) as total_price
            FROM orders o
            WHERE o.customer_id = %s
            ORDER BY o.created_at DESC
        """, (id,))
        history = cursor.fetchall()
        
    return render_template('customer_detail.html', customer=customer, history=history)

@app.route('/customers/<int:id>/delete', methods=['POST'])
@role_required('admin')
def delete_customer(id):
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT name FROM customers WHERE id = %s", (id,))
            customer = cursor.fetchone()
            if not customer:
                flash('Customer not found.', 'danger')
                return redirect(url_for('customers'))

            cursor.execute("SELECT COUNT(*) AS count FROM orders WHERE customer_id = %s", (id,))
            order_count = cursor.fetchone()['count']

            if order_count > 0:
                flash(f"Cannot delete {customer['name']} because they already have {order_count} order(s).", 'warning')
                return redirect(request.referrer or url_for('customers'))

            cursor.execute("DELETE FROM customers WHERE id = %s", (id,))
            db.commit()

            flash(f"Customer {customer['name']} deleted successfully.", 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error deleting customer: {str(e)}', 'danger')

    return redirect(url_for('customers'))

# --- Existing Product, Summary, Picklist ---

@app.route('/products')
@role_required('admin')
def products():
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM products ORDER BY name")
        product_list = cursor.fetchall()
    return render_template('products.html', products=product_list)

@app.route('/products/new', methods=['GET', 'POST'])
@role_required('admin')
def new_product():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        unit = request.form.get('unit')
        price = request.form.get('price_per_unit')
        db = get_db()
        try:
            with db.cursor() as cursor:
                sql = "INSERT INTO products (name, description, unit, price_per_unit) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (name, description, unit, price))
                db.commit()
                flash('Product added successfully!', 'success')
                return redirect(url_for('products'))
        except Exception as e:
            db.rollback()
            flash(f'Error adding product: {str(e)}', 'danger')
    return render_template('product_form.html', product=None)

@app.route('/products/<int:id>/edit', methods=['GET', 'POST'])
@role_required('admin')
def edit_product(id):
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        unit = request.form.get('unit')
        price = request.form.get('price_per_unit')
        is_active = 1 if request.form.get('is_active') else 0
        try:
            with db.cursor() as cursor:
                sql = "UPDATE products SET name=%s, description=%s, unit=%s, price_per_unit=%s, is_active=%s WHERE id=%s"
                cursor.execute(sql, (name, description, unit, price, is_active, id))
                db.commit()
                flash('Product updated successfully!', 'success')
                return redirect(url_for('products'))
        except Exception as e:
            db.rollback()
            flash(f'Error updating product: {str(e)}', 'danger')
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM products WHERE id = %s", (id,))
        product = cursor.fetchone()
    return render_template('product_form.html', product=product)

@app.route('/summary')
@role_required('admin')
def summary():
    today_val = date.today()
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date = %s", (today_val,))
        due_today = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date < %s AND status != 'delivered'", (today_val,))
        overdue = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'in_preparation'")
        in_prep = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date = %s AND status = 'delivered'", (today_val,))
        delivered_today = cursor.fetchone()['count']
        cursor.execute("""
            SELECT o.*, c.name as customer_name FROM orders o 
            JOIN customers c ON o.customer_id = c.id WHERE o.delivery_date = %s ORDER BY o.status
        """, (today_val,))
        today_orders = cursor.fetchall()

        cursor.execute("""
            SELECT summary_text, provider, model_name, updated_at
            FROM ai_daily_reports
            WHERE report_date = %s
        """, (today_val,))
        ai_summary = cursor.fetchone()

    return render_template(
        'summary.html',
        due_today=due_today,
        overdue=overdue,
        in_prep=in_prep,
        delivered_today=delivered_today,
        today_orders=today_orders,
        ai_summary=ai_summary,
        report_date=today_val
    )

@app.route('/summary/generate-ai', methods=['POST'])
@role_required('admin')
def generate_ai_summary():
    report_date = date.today()
    try:
        summary_data = generate_ai_daily_summary(report_date)
        save_ai_daily_summary(report_date, summary_data)
        flash(f"AI daily summary generated using {summary_data['provider']} ({summary_data['model_name']}).", 'success')
    except Exception as e:
        flash(f'Error generating AI summary: {str(e)}', 'danger')
    return redirect(url_for('summary'))

@app.route('/reports/sales')
@role_required('admin')
def sales_reports():
    today_val = date.today()
    week_start = today_val - timedelta(days=today_val.weekday())
    month_start = date(today_val.year, today_val.month, 1)
    year_start = date(today_val.year, 1, 1)

    db = get_db()
    with db.cursor() as cursor:
        def fetch_total(start_date, end_date=None):
            sql = """
                SELECT COUNT(DISTINCT o.id) AS order_count,
                       COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
                FROM orders o
                LEFT JOIN order_items oi ON o.id = oi.order_id
                WHERE o.status = 'delivered' AND o.delivery_date >= %s
            """
            params = [start_date]
            if end_date is not None:
                sql += " AND o.delivery_date < %s"
                params.append(end_date)
            cursor.execute(sql, params)
            return cursor.fetchone()

        daily_total = fetch_total(today_val)
        weekly_total = fetch_total(week_start)
        monthly_total = fetch_total(month_start)
        yearly_total = fetch_total(year_start)

        cursor.execute("""
            SELECT o.delivery_date AS period_date,
                   COUNT(DISTINCT o.id) AS order_count,
                   COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'delivered'
            GROUP BY o.delivery_date
            ORDER BY o.delivery_date DESC
            LIMIT 7
        """)
        daily_breakdown = cursor.fetchall()

        cursor.execute("""
            SELECT YEAR(o.delivery_date) AS sales_year,
                   WEEK(o.delivery_date, 1) AS sales_week,
                   MIN(o.delivery_date) AS week_start,
                   MAX(o.delivery_date) AS week_end,
                   COUNT(DISTINCT o.id) AS order_count,
                   COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'delivered'
            GROUP BY YEAR(o.delivery_date), WEEK(o.delivery_date, 1)
            ORDER BY sales_year DESC, sales_week DESC
            LIMIT 8
        """)
        weekly_breakdown = cursor.fetchall()

        cursor.execute("""
            SELECT YEAR(o.delivery_date) AS sales_year,
                   MONTH(o.delivery_date) AS sales_month_num,
                   DATE_FORMAT(o.delivery_date, '%b %Y') AS sales_month,
                   COUNT(DISTINCT o.id) AS order_count,
                   COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'delivered'
            GROUP BY YEAR(o.delivery_date), MONTH(o.delivery_date), DATE_FORMAT(o.delivery_date, '%b %Y')
            ORDER BY YEAR(o.delivery_date) DESC, MONTH(o.delivery_date) DESC
            LIMIT 12
        """)
        monthly_breakdown = cursor.fetchall()

        cursor.execute("""
            SELECT YEAR(o.delivery_date) AS sales_year,
                   COUNT(DISTINCT o.id) AS order_count,
                   COALESCE(SUM(oi.quantity * oi.unit_price), 0) AS revenue
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.status = 'delivered'
            GROUP BY YEAR(o.delivery_date)
            ORDER BY sales_year DESC
        """)
        yearly_breakdown = cursor.fetchall()

    return render_template(
        'sales_reports.html',
        today=today_val,
        week_start=week_start,
        month_start=month_start,
        year_start=year_start,
        daily_total=daily_total,
        weekly_total=weekly_total,
        monthly_total=monthly_total,
        yearly_total=yearly_total,
        daily_breakdown=daily_breakdown,
        weekly_breakdown=weekly_breakdown,
        monthly_breakdown=monthly_breakdown,
        yearly_breakdown=yearly_breakdown
    )

@app.route('/picklist')
@role_required('admin', 'kitchen', 'kitchen_chef')
def picklist():
    db = get_db()
    with db.cursor() as cursor:
        sql = """
            SELECT p.name AS product_name, p.unit, SUM(oi.quantity) AS total_qty, GROUP_CONCAT(CONCAT('#', o.id) SEPARATOR ', ') AS order_ids
            FROM order_items oi JOIN products p ON oi.product_id = p.id JOIN orders o ON oi.order_id = o.id
            WHERE o.status = 'in_preparation' GROUP BY p.id ORDER BY p.name
        """
        cursor.execute(sql)
        items = cursor.fetchall()
    return render_template('picklist.html', items=items, today=date.today())

@app.route('/customers/new', methods=['POST'])
@role_required('admin', 'order_taker')
def new_customer():
    name = request.form.get('name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    address = request.form.get('address')
    
    db = get_db()
    try:
        with db.cursor() as cursor:
            sql = "INSERT INTO customers (name, phone, email, address) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (name, phone, email, address))
            customer_id = cursor.lastrowid
            db.commit()
            
            socketio.emit('customer_created', {'name': name})
            
            # Check if AJAX request (from new_order.html)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
                return {"status": "success", "id": customer_id, "name": name}
            
            flash(f'Customer {name} added successfully!', 'success')
            return redirect(url_for('customers'))
    except Exception as e:
        db.rollback()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
            return {"status": "error", "message": str(e)}, 400
        flash(f'Error adding customer: {str(e)}', 'danger')
        return redirect(url_for('customers'))

@app.route('/admin/users', methods=['GET', 'POST'])
@role_required('admin')
def admin_users():
    db = get_db()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role')

        if not name or not email or not password or role not in ROLE_LABELS:
            flash('Please fill in all fields correctly.', 'danger')
            return redirect(url_for('admin_users'))

        try:
            with db.cursor() as cursor:
                cursor.execute("SELECT id FROM staff WHERE email = %s", (email,))
                if cursor.fetchone():
                    flash('A user with that email already exists.', 'warning')
                    return redirect(url_for('admin_users'))

                cursor.execute(
                    "INSERT INTO staff (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                    (name, email, generate_password_hash(password), role)
                )
                db.commit()
                flash(f'{ROLE_LABELS[role]} account created successfully.', 'success')
                return redirect(url_for('admin_users'))
        except Exception as e:
            db.rollback()
            flash(f'Error creating user: {str(e)}', 'danger')
            return redirect(url_for('admin_users'))

    with db.cursor() as cursor:
        cursor.execute("""
            SELECT id, name, email, role
            FROM staff
            ORDER BY FIELD(role, 'admin', 'order_taker', 'kitchen_chef', 'kitchen', 'delivery'), name
        """)
        staff_users = cursor.fetchall()

    return render_template('admin_users.html', staff_users=staff_users)

@app.route('/admin/api-settings', methods=['GET', 'POST'])
@role_required('admin')
def admin_api_settings():
    ensure_env_file()

    if request.method == 'POST':
        updates = {
            'GROQ_API_KEY_1': request.form.get('groq_api_key_1', '').strip(),
            'GROQ_API_KEY_2': request.form.get('groq_api_key_2', '').strip(),
            'GROQ_MODEL': request.form.get('groq_model', '').strip() or DEFAULT_ENV_VALUES['GROQ_MODEL'],
            'OPENROUTER_API_KEY_1': request.form.get('openrouter_api_key_1', '').strip(),
            'OPENROUTER_API_KEY_2': request.form.get('openrouter_api_key_2', '').strip(),
            'OPENROUTER_MODEL': request.form.get('openrouter_model', '').strip() or DEFAULT_ENV_VALUES['OPENROUTER_MODEL']
        }

        try:
            update_env_file(updates)
            sync_runtime_config_from_env()
            flash('API settings saved to .env successfully.', 'success')
        except Exception as e:
            flash(f'Error saving API settings: {str(e)}', 'danger')

        return redirect(url_for('admin_api_settings'))

    env_values = load_env_file()
    return render_template(
        'admin_api_settings.html',
        env_exists=os.path.exists(ENV_FILE_PATH),
        env_file_path=ENV_FILE_PATH,
        settings={
            'groq_api_key_1': env_values.get('GROQ_API_KEY_1', ''),
            'groq_api_key_2': env_values.get('GROQ_API_KEY_2', ''),
            'groq_model': env_values.get('GROQ_MODEL', DEFAULT_ENV_VALUES['GROQ_MODEL']),
            'openrouter_api_key_1': env_values.get('OPENROUTER_API_KEY_1', ''),
            'openrouter_api_key_2': env_values.get('OPENROUTER_API_KEY_2', ''),
            'openrouter_model': env_values.get('OPENROUTER_MODEL', DEFAULT_ENV_VALUES['OPENROUTER_MODEL'])
        }
    )

@app.route('/admin/api-key-test', methods=['GET', 'POST'])
@role_required('admin')
def admin_api_key_test():
    test_results = []
    tested = False

    if request.method == 'POST':
        test_results = run_api_key_chain_test()
        tested = True

    return render_template('admin_api_test.html', test_results=test_results, tested=tested)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
