"""
X87 Player - Portal Database Module
Database operations for the customer portal
Current Date and Time (UTC): 2025-11-22 14:50:43
Current User: covchump
UPDATED: Added license_profiles table for Multi-DNS
"""

import sqlite3
import os
from datetime import datetime

# Use the shared database path
DB_PATH = '/opt/iptv-panel/iptv_business.db'

def get_db_connection():
    """Create a database connection with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    # Licenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            customer_name TEXT,
            customer_email TEXT,
            status TEXT DEFAULT 'active',
            expires_at DATETIME,
            device_id TEXT,
            max_devices INTEGER DEFAULT 3,
            features TEXT,
            notes TEXT,
            user_dns TEXT, /* Legacy field, kept for compatibility */
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # License devices table (multi-device tracking)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS license_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            device_id TEXT NOT NULL,
            device_name TEXT,
            platform TEXT,
            bound_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(license_key, device_id)
        )
    ''')
    
    # NEW: License Profiles (Multi-DNS)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS license_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            profile_name TEXT NOT NULL,
            dns_url TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (license_key) REFERENCES licenses (license_key) ON DELETE CASCADE
        )
    ''')
    
    # Customers table (for portal login)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            customer_name TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME,
            FOREIGN KEY (license_key) REFERENCES licenses (license_key)
        )
    ''')
    
    # Customizations table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            app_name TEXT DEFAULT 'X87 Player',
            primary_color TEXT DEFAULT '#667eea',
            secondary_color TEXT DEFAULT '#764ba2',
            logo_url TEXT,
            theme TEXT DEFAULT 'dark',
            features TEXT,
            config TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (license_key) REFERENCES licenses (license_key)
        )
    ''')
    
    # License logs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS license_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            action TEXT NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Portal sessions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portal_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            session_token TEXT UNIQUE,
            ip_address TEXT,
            user_agent TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME,
            FOREIGN KEY (license_key) REFERENCES licenses (license_key)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")

def migrate_database():
    """Run database migrations to add new columns if needed"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check for license_profiles table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='license_profiles'")
        if not cursor.fetchone():
            print("➕ Creating license_profiles table...")
            cursor.execute('''
                CREATE TABLE license_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT NOT NULL,
                    profile_name TEXT NOT NULL,
                    dns_url TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (license_key) REFERENCES licenses (license_key) ON DELETE CASCADE
                )
            ''')
            conn.commit()
            print("✅ Created license_profiles table")

        # Check if customers table has all columns
        cursor.execute("PRAGMA table_info(customers)")
        customer_columns = [column[1] for column in cursor.fetchall()]
        
        if 'last_login' not in customer_columns:
            cursor.execute('ALTER TABLE customers ADD COLUMN last_login DATETIME')
        
        if 'customer_name' not in customer_columns:
            cursor.execute('ALTER TABLE customers ADD COLUMN customer_name TEXT')
        
        # Check if customizations table has all columns
        cursor.execute("PRAGMA table_info(customizations)")
        cust_columns = [column[1] for column in cursor.fetchall()]
        
        new_columns = [
            ('app_version', 'TEXT DEFAULT "1.0.0"'),
            ('server_url', 'TEXT'),
            ('api_endpoint', 'TEXT DEFAULT "/api/license/validate"'),
            ('iptv_url', 'TEXT'),
            ('epg_url', 'TEXT'),
            ('language', 'TEXT DEFAULT "en"'),
            ('auto_update', 'INTEGER DEFAULT 1'),
            ('analytics', 'INTEGER DEFAULT 0'),
            ('config', 'TEXT'),
        ]
        
        for column_name, column_def in new_columns:
            if column_name not in cust_columns:
                try:
                    cursor.execute(f'ALTER TABLE customizations ADD COLUMN {column_name} {column_def}')
                except Exception:
                    pass
        
        # Check if licenses table has features and USER_DNS column
        cursor.execute("PRAGMA table_info(licenses)")
        license_columns = [column[1] for column in cursor.fetchall()]
        
        if 'features' not in license_columns:
            cursor.execute('ALTER TABLE licenses ADD COLUMN features TEXT')
        if 'notes' not in license_columns:
            cursor.execute('ALTER TABLE licenses ADD COLUMN notes TEXT')
        if 'user_dns' not in license_columns:
            cursor.execute('ALTER TABLE licenses ADD COLUMN user_dns TEXT')

        # Migrate license_devices table (one-time)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='license_devices'")
        if not cursor.fetchone():
            print("➕ Creating license_devices table...")
            cursor.execute('''
                CREATE TABLE license_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    license_key TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    device_name TEXT,
                    platform TEXT,
                    bound_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(license_key, device_id)
                )
            ''')
            print("✅ Created license_devices table")

            # Migrate existing device_id values (one-time)
            cursor.execute('''
                SELECT license_key, device_id FROM licenses
                WHERE device_id IS NOT NULL AND device_id != ""
            ''')
            rows = cursor.fetchall()
            migrated = 0
            for row in rows:
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO license_devices (license_key, device_id)
                        VALUES (?, ?)
                    ''', (row[0], row[1]))
                    if cursor.rowcount:
                        migrated += 1
                except Exception:
                    pass
            if migrated:
                print(f"✅ Migrated {migrated} existing device_id(s) into license_devices")

            # One-time: update existing licenses with old default max_devices=1 to 3
            cursor.execute('UPDATE licenses SET max_devices = 3 WHERE max_devices = 1')
            if cursor.rowcount:
                print(f"✅ Updated {cursor.rowcount} license(s) max_devices from 1 to 3")

        conn.commit()
        print("✅ Database migrations completed")
        
    except Exception as e:
        print(f"⚠️ Migration warning: {e}")
    finally:
        conn.close()

# ... (Keep rest of existing functions: verify_license, log_action, get_license_info) ...
def verify_license(license_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM licenses WHERE license_key = ? AND (status = 'active' OR status = 'trial')''', (license_key,))
    license = cursor.fetchone()
    conn.close()
    if not license: return False, "Invalid or inactive license key"
    if license['expires_at']:
        try:
            expires_str = license['expires_at']
            if 'T' in expires_str: expiry_date = datetime.strptime(expires_str[:19], '%Y-%m-%dT%H:%M')
            else: expiry_date = datetime.strptime(expires_str, '%Y-%m-%d %H:%M:%S')
            if expiry_date < datetime.now(): return False, "License has expired"
        except: pass
    return True, license

def log_action(license_key, action, ip_address=None, user_agent=None, details=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO license_logs (license_key, action, ip_address, user_agent, details) VALUES (?, ?, ?, ?, ?)''', (license_key, action, ip_address, user_agent, details))
    conn.commit()
    conn.close()

def get_license_info(license_key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    license = cursor.fetchone()
    if license:
        cursor.execute('SELECT * FROM customizations WHERE license_key = ?', (license_key,))
        customization = cursor.fetchone()
        cursor.execute('SELECT * FROM license_logs WHERE license_key = ? ORDER BY timestamp DESC LIMIT 10', (license_key,))
        logs = cursor.fetchall()
        conn.close()
        return {'license': dict(license) if license else None, 'customization': dict(customization) if customization else None, 'recent_logs': [dict(log) for log in logs]}
    conn.close()
    return None

if not os.path.exists(DB_PATH):
    print(f"📊 Creating database at {DB_PATH}")
    init_database()