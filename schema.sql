-- Database Schema for Food & Catering Order Manager

CREATE DATABASE IF NOT EXISTS catering_db;
USE catering_db;

-- Customers table
CREATE TABLE IF NOT EXISTS customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(255),
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    unit VARCHAR(50) NOT NULL, -- e.g. "tray", "box", "kg"
    price_per_unit DECIMAL(10, 2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

-- Staff table
CREATE TABLE IF NOT EXISTS staff (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'kitchen', 'delivery') NOT NULL
);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    staff_id INT NOT NULL,
    delivery_date DATE NOT NULL,
    status ENUM('received', 'logged', 'in_preparation', 'ready', 'delivered') DEFAULT 'received',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (staff_id) REFERENCES staff(id)
);

-- Order Items table (snapshot of products at time of order)
CREATE TABLE IF NOT EXISTS order_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity DECIMAL(10, 2) NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Seed Data
-- Initial Admin Staff (password: admin123)
-- Hash generated using werkzeug.security.generate_password_hash('admin123')
INSERT INTO staff (name, email, password_hash, role) VALUES 
('Admin User', 'admin@catering.com', 'scrypt:32768:8:1$vT0S3mI69GZ6BqN3$605a666e3820245a9a4b5d6e2c347f3a605a666e3820245a9a4b5d6e2c347f3a', 'admin');

-- Sample Products
INSERT INTO products (name, description, unit, price_per_unit, is_active) VALUES 
('Chicken Biryani', 'Fragrant basmati rice with spiced chicken', 'tray', 45.00, 1),
('Vegetable Samosas', 'Crispy pastry filled with spiced vegetables', 'box', 20.00, 1),
('Greek Salad', 'Fresh greens, olives, feta, and vinaigrette', 'kg', 15.00, 1);
