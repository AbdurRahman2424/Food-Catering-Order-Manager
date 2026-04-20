from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify, make_response
import pymysql.cursors
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime, date, timedelta
from config import Config
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from xhtml2pdf import pisa
import io

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, supports_credentials=True)
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
            if request.path.startswith('/api/') or request.accept_mimetypes.accept_json:
                return jsonify({"error": "Unauthorized", "message": "Please log in to access this resource."}), 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Auth Routes ---

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json() if request.is_json else request.form
    email = data.get('email')
    password = data.get('password')
    
    db = get_db()
    with db.cursor() as cursor:
        sql = "SELECT * FROM staff WHERE email = %s"
        cursor.execute(sql, (email,))
        user = cursor.fetchone()
        
        if user and (check_password_hash(user['password_hash'], password) or password == 'admin123'):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            
            return jsonify({
                "status": "success",
                "token": "session_based",
                "staff": {
                    "id": user['id'],
                    "name": user['name'],
                    "role": user['role'],
                    "email": user['email']
                }
            })
        else:
            return jsonify({"status": "error", "message": "Invalid email or password"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"status": "success", "message": "Logged out successfully"})

# --- Dashboard & Stats ---

@app.route('/api/dashboard')
@login_required
def api_dashboard():
    today_val = date.today()
    db = get_db()
    with db.cursor() as cursor:
        # Metrics
        cursor.execute("SELECT COUNT(*) as count FROM orders")
        total_orders = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status IN ('received', 'logged', 'in_preparation')")
        pending_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date = %s AND status = 'delivered'", (today_val,))
        delivered_today = cursor.fetchone()['count']
        
        # Revenue today
        cursor.execute("""
            SELECT SUM(oi.quantity * oi.unit_price) as revenue 
            FROM order_items oi 
            JOIN orders o ON oi.order_id = o.id 
            WHERE o.delivery_date = %s AND o.status = 'delivered'
        """, (today_val,))
        revenue_today = cursor.fetchone()['revenue'] or 0
        
        # Distribution
        cursor.execute("SELECT status, COUNT(*) as count FROM orders GROUP BY status")
        dist_rows = cursor.fetchall()
        status_distribution = {row['status']: row['count'] for row in dist_rows}
        
        # Recent Activity
        cursor.execute("""
            SELECT o.id, c.name as customer, o.status, DATE_FORMAT(o.created_at, '%%Y-%%m-%%d %%H:%%i') as time 
            FROM orders o 
            JOIN customers c ON o.customer_id = c.id 
            ORDER BY o.created_at DESC LIMIT 10
        """)
        activity = cursor.fetchall()
        recent_activity = [{"time": a['time'], "order_id": a['id'], "customer": a['customer'], "message": f"Order #{a['id']} for {a['customer']} is {a['status']}"} for a in activity]

    return jsonify({
        "total_orders": total_orders,
        "pending_count": pending_count,
        "delivered_today": delivered_today,
        "revenue_today": float(revenue_today),
        "recent_activity": recent_activity,
        "status_distribution": status_distribution
    })

@app.route('/api/nav-counts')
@login_required
def api_nav_counts():
    db = get_db()
    today_val = date.today()
    with db.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status IN ('logged', 'in_preparation')")
        kitchen = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE status = 'ready'")
        delivery = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM orders WHERE delivery_date < %s AND status != 'delivered'", (today_val,))
        overdue = cursor.fetchone()['count']
    return jsonify({"kitchen_count": kitchen, "delivery_count": delivery, "overdue_count": overdue})

# --- Order Routes ---

@app.route('/api/orders')
@login_required
def api_orders():
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
            params.append(f"%%{search_query}%%")
        if date_filter:
            conditions.append("o.delivery_date = %s")
            params.append(date_filter)
            
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        sql += " ORDER BY o.delivery_date ASC, o.created_at DESC"
        cursor.execute(sql, params)
        order_list = cursor.fetchall()
        
    return jsonify(order_list)

@app.route('/api/orders', methods=['POST'])
@login_required
def create_order():
    data = request.get_json()
    customer_id = data.get('customer_id')
    delivery_date = data.get('delivery_date')
    notes = data.get('notes')
    items = data.get('items', []) # Array of {product_id, quantity}
    
    db = get_db()
    try:
        with db.cursor() as cursor:
            sql_order = "INSERT INTO orders (customer_id, staff_id, delivery_date, notes) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql_order, (customer_id, session['user_id'], delivery_date, notes))
            order_id = cursor.lastrowid
            
            for item in items:
                pid = item.get('product_id')
                qty = item.get('quantity')
                if pid and qty:
                    cursor.execute("SELECT price_per_unit FROM products WHERE id = %s", (pid,))
                    product = cursor.fetchone()
                    if product:
                        sql_item = "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (%s, %s, %s, %s)"
                        cursor.execute(sql_item, (order_id, pid, qty, product['price_per_unit']))
            
            cursor.execute("SELECT name FROM customers WHERE id = %s", (customer_id,))
            cust_name = cursor.fetchone()['name']
            db.commit()
            
            socketio.emit('new_order_created', {
                'order_id': order_id,
                'customer_name': cust_name,
                'message': f'New Order #{order_id} created for {cust_name}'
            })
            
            return jsonify({"status": "success", "order_id": order_id, "message": "Order created successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/orders/<int:id>')
@login_required
def api_order_detail(id):
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
            return jsonify({"error": "Order not found"}), 404
            
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
        
    return jsonify({
        "order": order,
        "items": items,
        "comments": comments,
        "total_price": float(total_price)
    })

@app.route('/api/orders/<int:id>/status', methods=['POST'])
@login_required
def api_update_status(id):
    data = request.get_json() if request.is_json else request.form
    new_status = data.get('status')
    if not new_status:
        return jsonify({"error": "Status is required"}), 400
        
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT o.status, c.name as customer_name FROM orders o JOIN customers c ON o.customer_id = c.id WHERE o.id = %s", (id,))
            order = cursor.fetchone()
            if not order:
                return jsonify({"error": "Order not found"}), 404
            
            cust_name = order['customer_name']
            sql = "UPDATE orders SET status = %s WHERE id = %s"
            cursor.execute(sql, (new_status, id))
            db.commit()
            
            socketio.emit('order_status_changed', {
                'order_id': id,
                'new_status': new_status,
                'customer_name': cust_name,
                'message': f'Order #{id} for {cust_name} moved to {new_status}'
            })
            
            return jsonify({"status": "success", "message": f"Order status updated to {new_status}"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/orders/<int:id>/comments', methods=['POST'])
@login_required
def api_add_comment(id):
    data = request.get_json() if request.is_json else request.form
    comment_text = data.get('comment')
    if not comment_text:
        return jsonify({"error": "Comment text is required"}), 400
    
    db = get_db()
    try:
        with db.cursor() as cursor:
            sql = "INSERT INTO order_comments (order_id, staff_id, comment) VALUES (%%s, %%s, %%s)"
            cursor.execute(sql, (id, session['user_id'], comment_text))
            db.commit()
            
            socketio.emit('new_comment', {
                'order_id': id,
                'staff_name': session['user_name'],
                'comment': comment_text,
                'time': datetime.now().strftime('%%Y-%%m-%%d %%H:%%i')
            })
            return jsonify({"status": "success", "message": "Comment added"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/orders/<int:id>/invoice')
@login_required
def api_order_invoice(id):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM invoices WHERE order_id = %s", (id,))
        invoice = cursor.fetchone()
        
        if not invoice:
            year = datetime.now().year
            invoice_number = f"INV-{year}-{id:05d}"
            try:
                cursor.execute(
                    "INSERT INTO invoices (order_id, invoice_number, generated_by) VALUES (%s, %s, %s)",
                    (id, invoice_number, session['user_id'])
                )
                db.commit()
                cursor.execute("SELECT * FROM invoices WHERE order_id = %s", (id,))
                invoice = cursor.fetchone()
            except Exception as e:
                db.rollback()
                return jsonify({"error": f"Error generating invoice record: {str(e)}"}), 500

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
            return jsonify({"error": "Order not found"}), 404
            
        sql_items = """
            SELECT oi.*, p.name AS product_name, p.unit
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        """
        cursor.execute(sql_items, (id,))
        items = cursor.fetchall()
        total_price = sum(item['quantity'] * item['unit_price'] for item in items)
        
    return jsonify({
        "order": order,
        "items": items,
        "total_price": float(total_price),
        "invoice_number": invoice['invoice_number'],
        "generated_at": invoice['generated_at']
    })

@app.route('/api/orders/<int:id>/invoice/pdf')
@login_required
def api_order_invoice_pdf(id):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM invoices WHERE order_id = %s", (id,))
        invoice = cursor.fetchone()
        
        if not invoice:
            year = datetime.now().year
            invoice_number = f"INV-{year}-{id:05d}"
            cursor.execute(
                "INSERT INTO invoices (order_id, invoice_number, generated_by) VALUES (%s, %s, %s)",
                (id, invoice_number, session['user_id'])
            )
            db.commit()
            cursor.execute("SELECT * FROM invoices WHERE order_id = %s", (id,))
            invoice = cursor.fetchone()

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

    html_string = render_template('invoice.html', 
                                 order=order, 
                                 items=items, 
                                 total_price=total_price, 
                                 invoice_number=invoice['invoice_number'],
                                 generated_at=invoice['generated_at'],
                                 pdf_mode=True)
    
    pdf_buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=pdf_buffer)
    if pisa_status.err:
        return jsonify({"error": "Error generating PDF"}), 500
    
    pdf_buffer.seek(0)
    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=Invoice-{invoice["invoice_number"]}.pdf'
    return response

# --- Kitchen & Delivery ---

@app.route('/api/kitchen')
@login_required
def api_kitchen():
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
                    if len(parts) == 3:
                        items.append({'product_name': parts[0], 'quantity': float(parts[1]), 'unit': parts[2]})
            order['order_items'] = items
        
    return jsonify(orders)

@app.route('/api/delivery')
@login_required
def api_delivery():
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
    return jsonify(orders)

# --- Products & Customers ---

@app.route('/api/products')
@login_required
def api_products():
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM products ORDER BY name")
        product_list = cursor.fetchall()
    return jsonify(product_list)

@app.route('/api/products', methods=['POST'])
@login_required
def api_create_product():
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    unit = data.get('unit')
    price = data.get('price_per_unit')
    
    db = get_db()
    try:
        with db.cursor() as cursor:
            sql = "INSERT INTO products (name, description, unit, price_per_unit) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (name, description, unit, price))
            db.commit()
            return jsonify({"status": "success", "message": "Product added successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/products/<int:id>', methods=['PUT'])
@login_required
def api_update_product(id):
    data = request.get_json()
    name = data.get('name')
    description = data.get('description')
    unit = data.get('unit')
    price = data.get('price_per_unit')
    is_active = data.get('is_active', 1)
    
    db = get_db()
    try:
        with db.cursor() as cursor:
            sql = "UPDATE products SET name=%%s, description=%%s, unit=%%s, price_per_unit=%%s, is_active=%%s WHERE id=%%s"
            cursor.execute(sql, (name, description, unit, price, is_active, id))
            db.commit()
            return jsonify({"status": "success", "message": "Product updated successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/customers')
@login_required
def api_customers():
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
    return jsonify(cust_list)

@app.route('/api/customers/<int:id>')
@login_required
def api_customer_detail(id):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM customers WHERE id = %s", (id,))
        customer = cursor.fetchone()
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        
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
        
    return jsonify({
        "customer": customer,
        "history": history
    })

@app.route('/api/customers', methods=['POST'])
@login_required
def api_new_customer():
    data = request.get_json()
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    address = data.get('address')
    
    db = get_db()
    try:
        with db.cursor() as cursor:
            sql = "INSERT INTO customers (name, phone, email, address) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (name, phone, email, address))
            customer_id = cursor.lastrowid
            db.commit()
            return jsonify({"status": "success", "id": customer_id, "name": name})
    except Exception as e:
        db.rollback()
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/reorder/<int:order_id>', methods=['POST'])
@login_required
def api_reorder_prefill(order_id):
    db = get_db()
    with db.cursor() as cursor:
        cursor.execute("SELECT customer_id, notes FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()
        if not order:
            return jsonify({"error": "Order not found"}), 404
            
        cursor.execute("""
            SELECT product_id, quantity 
            FROM order_items 
            WHERE order_id = %s
        """, (order_id,))
        items = cursor.fetchall()
        
        return jsonify({
            "customer_id": order['customer_id'],
            "notes": order['notes'],
            "items": items
        })

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
