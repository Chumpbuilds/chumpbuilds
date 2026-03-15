"""
X87 Player - Admin Panel Main Application
Integrates all modules (API, Auth, Dashboard, Customers, Users, Settings)
"""

from flask import Flask, redirect, url_for
import os
import sys
from admin_database import init_database, migrate_database

# Import Blueprints from other modules
from admin_api import api_bp
from admin_auth import auth_bp
from admin_dashboard import dashboard_bp
from admin_customers import customers_bp
from admin_users import users_bp
from admin_profile import profile_bp
from admin_settings import settings_bp  # <--- IMPORT THIS

# Initialize Flask App
app = Flask(__name__)
app.secret_key = 'x87-admin-secret-2025'  # Keep this secure

# Register Blueprints
app.register_blueprint(api_bp)        # Connects /api/license/validate
app.register_blueprint(auth_bp)       # Connects /login, /logout
app.register_blueprint(dashboard_bp)  # Connects /dashboard
app.register_blueprint(customers_bp)  # Connects /customers
app.register_blueprint(users_bp)      # Connects /users
app.register_blueprint(profile_bp)    # Connects /profile
app.register_blueprint(settings_bp)   # Connects /settings <--- REGISTER THIS

# Initialize Database on startup
try:
    print("🔄 Initializing database...")
    init_database()
    migrate_database()
    print("✅ Database ready")
except Exception as e:
    print(f"❌ Database initialization failed: {e}")

@app.route('/')
def index():
    """Root URL redirects to dashboard (which handles login check)"""
    return redirect(url_for('dashboard.admin_dashboard'))

if __name__ == '__main__':
    print("="*70)
    print("🚀 X87 Admin Panel & API Server Starting...")
    print("📍 Port: 5000")
    print(f"📂 API Endpoint: http://127.0.0.1:5000/api/license/validate")
    print("="*70)
    
    # Run on all interfaces (0.0.0.0) so Nginx can reach it
    app.run(host='0.0.0.0', port=5000, debug=True)