"""
X87 Player - Database Management Module
Handles all database operations and migrations
"""

import sqlite3
import hashlib
import json
from datetime import datetime, timedelta

# FIXED: Use absolute path to share DB with Portal and Home services
DB_PATH = '/opt/iptv-panel/iptv_business.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def migrate_database():
    """Migrate existing database to add new columns"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔄 Checking database schema...")
    
    # Check if columns exist and add them if they don't
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'is_active' not in columns:
        print("➕ Adding is_active column to users table...")
        cursor.execute('ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1')
        conn.commit()
        print("✅ Added is_active column")
    
    if 'last_login' not in columns:
        print("➕ Adding last_login column to users table...")
        cursor.execute('ALTER TABLE users ADD COLUMN last_login TIMESTAMP')
        conn.commit()
        print("✅ Added last_login column")
    
    # Create settings table if it doesn't exist (migration check)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    # Initialize version settings if missing
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('latest_version', '1.0.0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('update_url', 'https://yourdomain.com/downloads')")
    conn.commit()

    # Migrate license_devices table
    _migrate_license_devices(conn)
    
    conn.close()
    print("✅ Database migration completed")

def _migrate_license_devices(conn):
    """Create license_devices table and migrate existing device_id values."""
    cursor = conn.cursor()

    # Create license_devices table and run one-time migrations
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
        conn.commit()
        print("✅ Created license_devices table")

        # Migrate existing device_id values from licenses table (one-time)
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

        # One-time: update existing licenses that have the old default of max_devices=1 to 3
        cursor.execute('UPDATE licenses SET max_devices = 3 WHERE max_devices = 1')
        if cursor.rowcount:
            print(f"✅ Updated {cursor.rowcount} license(s) max_devices from 1 to 3")

        conn.commit()

def init_database():
    """Initialize the database with all required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Users table for admin authentication
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # Licenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            customer_name TEXT,
            customer_email TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            last_used TIMESTAMP,
            device_id TEXT,
            app_version TEXT,
            features TEXT DEFAULT '{}',
            notes TEXT,
            max_devices INTEGER DEFAULT 3
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

    # License usage logs
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS license_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT,
            action TEXT,
            ip_address TEXT,
            user_agent TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT
        )
    ''')

    # App customizations
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE,
            app_name TEXT DEFAULT 'X87 Player',
            primary_color TEXT DEFAULT '#0d7377',
            secondary_color TEXT DEFAULT '#64b5f6',
            logo_url TEXT,
            theme TEXT DEFAULT 'dark',
            features TEXT DEFAULT '{}',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Global Settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')

    # Set default settings
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('latest_version', '1.0.0')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('update_url', 'https://yourdomain.com/downloads')")

    # Create default admin user if doesn't exist
    cursor.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
    if cursor.fetchone()[0] == 0:
        admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
        cursor.execute('INSERT INTO users (username, password, email, role, is_active) VALUES (?, ?, ?, ?, ?)',
                      ('admin', admin_password, 'admin@x87player.xyz', 'superadmin', 1))
        print("✅ Default admin user created (username: admin, password: admin123)")
        print("⚠️  PLEASE CHANGE THE DEFAULT PASSWORD!")

    conn.commit()
    conn.close()
    print("✅ Database initialized successfully")