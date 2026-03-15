"""
X87 Player - Customer Portal Main Application
Entry point for customer self-service portal
Current Date and Time (UTC): 2025-11-22 15:44:14
Current User: covchump
UPDATED: Removed choose plan page, direct to login
"""

from flask import Flask, session, redirect, url_for, render_template_string, request
from flask_cors import CORS
import os
import sys
from datetime import datetime, timedelta

# Add current directory and parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import portal modules
from portal_database import init_database, migrate_database, DB_PATH
from portal_auth import auth_bp, login_required
from portal_dashboard import dashboard_bp

# Create Flask application
app = Flask(__name__)
app.secret_key = os.environ.get('PORTAL_SECRET_KEY', 'x87player_portal_secret_CHANGE_IN_PRODUCTION_2025')

# Enable CORS for API endpoints if needed
CORS(app, resources={
    r"/api/*": {
        "origins": ["*"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

# Register blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

# Root route - Redirects to login or dashboard
@app.route('/')
def index():
    if 'logged_in' in session and session['logged_in']:
        return redirect(url_for('dashboard.customer_dashboard'))
    # Redirect directly to login page (no choose plan page)
    return redirect(url_for('auth.login'))

# API Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        from portal_database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM licenses')
        license_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM customers')
        customer_count = cursor.fetchone()[0]
        conn.close()
        
        return {
            'status': 'healthy',
            'service': 'X87 Player Customer Portal',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stats': {
                'licenses': license_count,
                'customers': customer_count
            }
        }, 200
    except Exception as e:
        return {
            'status': 'error',
            'service': 'X87 Player Customer Portal',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'error': str(e)
        }, 500

# API endpoint to check session status
@app.route('/api/session/status', methods=['GET'])
def session_status():
    """Check if user session is valid"""
    if 'logged_in' in session and session['logged_in']:
        return {
            'authenticated': True,
            'username': session.get('username'),
            'license_key': session.get('license_key'),
            'customer_name': session.get('customer_name')
        }, 200
    else:
        return {
            'authenticated': False
        }, 401

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    ERROR_404_TEMPLATE = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>404 - Page Not Found</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
            }
            .error-container {
                background: white;
                border-radius: 20px;
                padding: 3rem;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                text-align: center;
                max-width: 500px;
                animation: slideUp 0.5s ease-out;
            }
            @keyframes slideUp {
                from { transform: translateY(20px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            .error-code {
                font-size: 6rem;
                font-weight: bold;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 1rem;
            }
            h1 {
                color: #1f2937;
                margin-bottom: 1rem;
            }
            p {
                color: #6b7280;
                margin-bottom: 2rem;
                line-height: 1.6;
            }
            .btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 0.75rem 2rem;
                border-radius: 10px;
                text-decoration: none;
                display: inline-block;
                transition: all 0.3s;
                font-weight: 500;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
            }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="error-code">404</div>
            <h1>Page Not Found</h1>
            <p>Oops! The page you're looking for doesn't exist or has been moved.</p>
            <a href="/login" class="btn">Go to Login</a>
        </div>
    </body>
    </html>
    '''
    return render_template_string(ERROR_404_TEMPLATE), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    ERROR_500_TEMPLATE = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>500 - Server Error</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
            }
            .error-container {
                background: white;
                border-radius: 20px;
                padding: 3rem;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                text-align: center;
                max-width: 500px;
                animation: slideUp 0.5s ease-out;
            }
            @keyframes slideUp {
                from { transform: translateY(20px); opacity: 0; }
                to { transform: translateY(0); opacity: 1; }
            }
            .error-code {
                font-size: 6rem;
                font-weight: bold;
                color: #ef4444;
                margin-bottom: 1rem;
            }
            h1 {
                color: #1f2937;
                margin-bottom: 1rem;
            }
            p {
                color: #6b7280;
                margin-bottom: 2rem;
                line-height: 1.6;
            }
            .btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 0.75rem 2rem;
                border-radius: 10px;
                text-decoration: none;
                display: inline-block;
                transition: all 0.3s;
                font-weight: 500;
            }
            .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 10px 20px rgba(102, 126, 234, 0.4);
            }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="error-code">500</div>
            <h1>Server Error</h1>
            <p>Something went wrong on our end. Our team has been notified and is working on a fix.</p>
            <a href="/login" class="btn">Go to Login</a>
        </div>
    </body>
    </html>
    '''
    # Log the error
    print(f"[ERROR] 500 Internal Server Error: {error}")
    return render_template_string(ERROR_500_TEMPLATE), 500

@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 errors"""
    ERROR_403_TEMPLATE = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>403 - Access Forbidden</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
            }
            .error-container {
                background: white;
                border-radius: 20px;
                padding: 3rem;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
                text-align: center;
                max-width: 500px;
            }
            .error-code {
                font-size: 6rem;
                font-weight: bold;
                color: #f59e0b;
                margin-bottom: 1rem;
            }
            .btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 0.75rem 2rem;
                border-radius: 10px;
                text-decoration: none;
                display: inline-block;
                margin-top: 1rem;
            }
        </style>
    </head>
    <body>
        <div class="error-container">
            <div class="error-code">403</div>
            <h1>Access Forbidden</h1>
            <p>You don't have permission to access this resource.</p>
            <a href="/login" class="btn">Login</a>
        </div>
    </body>
    </html>
    '''
    return render_template_string(ERROR_403_TEMPLATE), 403

# Session configuration
@app.before_request
def make_session_permanent():
    """Make session permanent with timeout"""
    session.permanent = True
    app.permanent_session_lifetime = timedelta(hours=24)  # Session expires after 24 hours

# Add request logging for debugging (only in debug mode)
@app.before_request
def log_request():
    """Log incoming requests for debugging"""
    if app.debug:
        # Skip logging for static files and health checks
        if not request.path.startswith('/static') and not request.path.startswith('/api/health'):
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {request.method} {request.path}")

# Context processor to inject common variables
@app.context_processor
def inject_globals():
    """Inject common variables into all templates"""
    return {
        'now': datetime.now(),
        'app_name': 'X87 Player',
        'app_version': '1.0.0',
        'support_email': 'support@x87player.xyz',
        'current_year': datetime.now().year
    }

# Main execution
if __name__ == '__main__':
    print("\n" + "="*70)
    print("🎬 X87 Player Customer Portal Starting...")
    print("="*70)
    print(f"📅 Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"👤 Current User: covchump")
    print(f"📁 Working Directory: {os.getcwd()}")
    print(f"🗄️ Database Path: {DB_PATH}")
    
    # Initialize database
    if os.path.exists(DB_PATH):
        print("📊 Database found, checking for migrations...")
        try:
            migrate_database()
            print("✅ Migrations completed successfully")
        except Exception as e:
            print(f"⚠️  Migration warning: {e}")
    else:
        print("📊 Database not found, creating new database...")
    
    try:
        init_database()
        print("✅ Database initialized successfully")
        
        # Check database stats
        from portal_database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if tables exist before counting
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='licenses'")
        if cursor.fetchone():
            cursor.execute('SELECT COUNT(*) FROM licenses')
            license_count = cursor.fetchone()[0]
        else:
            license_count = 0
            
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customers'")
        if cursor.fetchone():
            cursor.execute('SELECT COUNT(*) FROM customers')
            customer_count = cursor.fetchone()[0]
        else:
            customer_count = 0
            
        conn.close()
        
        print(f"📈 Database Stats:")
        print(f"   - Licenses: {license_count}")
        print(f"   - Customers: {customer_count}")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        print("   Portal may not function correctly!")
    
    print("\n🌐 Portal Routes:")
    print("   - Home:           /  (redirects to login)")
    print("   - Login:          /login")
    print("   - Register:       /register/trial")
    print("   - Dashboard:      /dashboard")
    print("   - Logout:         /logout")
    
    print("\n📡 API Endpoints:")
    print("   - Health Check:   /api/health")
    print("   - Session Status: /api/session/status")
    
    print("\n🔒 Security:")
    print("   - Session Timeout: 24 hours")
    print("   - CORS Enabled:    API endpoints only")
    
    print("\n💡 Portal Features:")
    print("   ✅ Direct login (no plan selection page)")
    print("   ✅ Username/password authentication")  
    print("   ✅ Customer dashboard")
    print("   ✅ Session management")
    print("   ✅ Responsive design")
    
    print("\n" + "="*70)
    print("✅ Customer Portal ready!")
    print("🌐 Starting server on: http://0.0.0.0:5001")
    print("📱 Access locally at: http://localhost:5001")
    print("🌍 Access remotely at: http://YOUR_SERVER_IP:5001")
    print("="*70 + "\n")
    
    # Run the portal on a different port than admin panel
    app.run(
        host='0.0.0.0',
        port=5001,
        debug=True  # Set to False in production
    )