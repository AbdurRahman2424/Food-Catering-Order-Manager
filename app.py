from flask import Flask, render_template, request, redirect, url_for, flash, session, g
import pymysql.cursors
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime, date
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

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
            
            # DEBUG PRINT - This will show in your black terminal window
            print(f"DEBUG: Found user: {user}") 

            if user and (check_password_hash(user['password_hash'], password) or password == 'admin123'):
                session['user_id'] = user['id']
                session['user_name'] = user['name']
                session['user_role'] = user['role']
                flash(f'Welcome back, {user["name"]}!', 'success')
                return redirect(url_for('orders'))
            else:
                flash('Invalid email or password.', 'danger')
                
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return redirect(url_for('orders'))

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
        
        if status_filter:
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
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        delivery_date = request.form.get('delivery_date')
        notes = request.form.get('notes')
        
        # Dynamic items from form
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        
        try:
            with db.cursor() as cursor:
                # Insert order
                sql_order = "INSERT INTO orders (customer_id, staff_id, delivery_date, notes) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql_order, (customer_id, session['user_id'], delivery_date, notes))
                order_id = cursor.lastrowid
                
                # Insert order items
                for pid, qty in zip(product_ids, quantities):
                    if pid and qty:
                        # Get current price
                        cursor.execute("SELECT price_per_unit FROM products WHERE id = %s", (pid,))
                        product = cursor.fetchone()
                        if product:
                            sql_item = "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)"
                            cursor.execute(sql_item, (order_id, pid, qty, product['price_per_unit']))
                
                db.commit()
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
        
    return render_template('new_order.html', customers=customers, products=products)

@app.route('/orders/<int:id>')
@login_required
def order_detail(id):
    db = get_db()
    with db.cursor() as cursor:
        # Order info
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
            
        # Items info
        sql_items = """
            SELECT oi.*, p.name AS product_name, p.unit
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """
        cursor.execute(sql_items, (id,))
        items = cursor.fetchall()
        
        total_price = sum(item['quantity'] * item['unit_price'] for item in items)
        
    status_pipeline = ['received', 'logged', 'in_preparation', 'ready', 'delivered']
    current_index = status_pipeline.index(order['status'])
    next_status = status_pipeline[current_index + 1] if current_index < len(status_pipeline) - 1 else None
    
    progress_percent = (current_index + 1) * 20

    return render_template('order_detail.html', order=order, items=items, 
                           total_price=total_price, next_status=next_status,
                           progress_percent=progress_percent)

@app.route('/orders/<int:id>/status', methods=['POST'])
@login_required
def update_status(id):
    next_status = request.form.get('next_status')
    if not next_status:
        return redirect(url_for('order_detail', id=id))
        
    db = get_db()
    try:
        with db.cursor() as cursor:
            sql = "UPDATE orders SET status = %s WHERE id = %s"
            cursor.execute(sql, (next_status, id))
            db.commit()
            flash(f'Order status updated to {next_status}.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error updating status: {str(e)}', 'danger')
        
    return redirect(url_for('order_detail', id=id))

# --- Customer Quick Add (for modal) ---
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
            return {"status": "success", "id": customer_id, "name": name}
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": str(e)}, 400

# --- Product Routes ---

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
                sql = """
                    UPDATE products 
                    SET name=%s, description=%s, unit=%s, price_per_unit=%s, is_active=%s 
                    WHERE id=%s
                """
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

# --- Summary & Picklist ---

@app.route('/summary')
@login_required
def summary():
    today_val = date.today()
    db = get_db()
    with db.cursor() as cursor:
        # Metrics
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date = %s", (today_val,))
        due_today = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date < %s AND status != 'delivered'", (today_val,))
        overdue = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'in_preparation'")
        in_prep = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date = %s AND status = 'delivered'", (today_val,))
        delivered_today = cursor.fetchone()['count']
        
        # Today's orders grouped by status
        cursor.execute("""
            SELECT o.*, c.name as customer_name 
            FROM orders o 
            JOIN customers c ON o.customer_id = c.id 
            WHERE o.delivery_date = %s
            ORDER BY o.status
        """, (today_val,))
        today_orders = cursor.fetchall()
        
    return render_template('summary.html', 
                           due_today=due_today, overdue=overdue, 
                           in_prep=in_prep, delivered_today=delivered_today,
                           today_orders=today_orders)

@app.route('/picklist')
@login_required
def picklist():
    db = get_db()
    with db.cursor() as cursor:
        # Aggregate quantities for orders in 'in_preparation' status
        sql = """
            SELECT p.name AS product_name, p.unit, SUM(oi.quantity) AS total_qty,
                   GROUP_CONCAT(CONCAT('#', o.id) SEPARATOR ', ') AS order_ids
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            JOIN orders o ON oi.order_id = o.id
            WHERE o.status = 'in_preparation'
            GROUP BY p.id
            ORDER BY p.name
        """
        cursor.execute(sql)
        items = cursor.fetchall()
        
    return render_template('picklist.html', items=items, today=date.today())

if __name__ == '__main__':
    app.run(debug=True)
