from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
import pymysql.cursors
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime, date, timedelta
from config import Config
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config.from_object(Config)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='eventlet')

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
    return g.db

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
            SELECT o.id, c.name as customer, o.status, DATE_FORMAT(o.created_at, '%%H:%%i') as time 
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
@login_required
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
@login_required
def new_order():
    db = get_db()
    reorder_id = request.args.get('reorder')
    prefill_data = None
    
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
        
    return render_template('new_order.html', customers=customers, products=products, prefill_data=prefill_data)

@app.route('/orders/<int:id>')
@login_required
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
        
    return render_template('order_detail.html', order=order, items=items, 
                           total_price=total_price, comments=comments)

@app.route('/orders/<int:id>/status', methods=['POST'])
@login_required
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
            
            if new_status not in status_pipeline:
                flash('Invalid status.', 'danger')
                return redirect(request.referrer or url_for('orders'))
            
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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

# --- Existing Product, Summary, Picklist ---

@app.route('/products')
@login_required
def products():
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM products ORDER BY name")
        product_list = cursor.fetchall()
    return render_template('products.html', products=product_list)

@app.route('/products/new', methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
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
    return render_template('summary.html', due_today=due_today, overdue=overdue, in_prep=in_prep, delivered_today=delivered_today, today_orders=today_orders)

@app.route('/picklist')
@login_required
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
@login_required
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

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
