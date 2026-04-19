import os

class Config:
    # 1. Host is localhost for XAMPP
    MYSQL_HOST = os.environ.get('MYSQL_HOST', 'localhost')
    
    # 2. User is always root by default in XAMPP
    MYSQL_USER = os.environ.get('MYSQL_USER', 'root')
    
    # 3. Keep this EMPTY for XAMPP
    MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD', '')
    
    # 4. This MUST match the 'CREATE DATABASE' name in your script
    MYSQL_DB = os.environ.get('MYSQL_DB', 'catering_db')
    
    # 5. Just for Flask sessions
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_secret_key_123')