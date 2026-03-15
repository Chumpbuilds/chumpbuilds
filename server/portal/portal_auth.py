"""
X87 Player - Portal Authentication Module
Handles customer authentication for the portal
Current Date and Time (UTC): 2025-11-22 15:56:20
Current User: covchump
FIXED: Moved request import to top of file
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, session, flash  # Added request here
from functools import wraps
from portal_database import get_db_connection, log_action
import hashlib
import secrets
import string
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

def hash_password(password):
    """Hash a password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_license_key():
    """Generate a unique license key"""
    segments = ['X87']
    chars = string.ascii_uppercase + string.digits
    for _ in range(3):
        segment = ''.join(secrets.choice(chars) for _ in range(4))
        segments.append(segment)
    return '-'.join(segments)

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Login - X87 Player Portal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .login-container {
            background: white;
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            width: 100%;
            max-width: 400px;
            animation: slideUp 0.5s ease-out;
        }
        
        @keyframes slideUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        .logo {
            font-size: 3rem;
            text-align: center;
            margin-bottom: 1rem;
        }
        
        h2 {
            text-align: center;
            color: #1f2937;
            margin-bottom: 2rem;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        label {
            display: block;
            color: #374151;
            font-weight: 500;
            margin-bottom: 0.5rem;
            font-size: 0.875rem;
        }
        
        input {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 1rem;
            transition: all 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .btn {
            width: 100%;
            padding: 0.875rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }
        
        .alert {
            padding: 0.75rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            font-size: 0.875rem;
        }
        
        .alert-error {
            background: #fee2e2;
            color: #991b1b;
            border: 1px solid #fecaca;
        }
        
        .alert-warning {
            background: #fef3c7;
            color: #92400e;
            border: 1px solid #fde68a;
        }
        
        .alert-success {
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
        }
        
        .links {
            text-align: center;
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid #e5e7eb;
        }
        
        .links p {
            color: #6b7280;
            margin-bottom: 0.5rem;
        }
        
        .links a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        
        .links a:hover {
            text-decoration: underline;
        }
        
        .back-link {
            display: block;
            margin-top: 1rem;
            color: #6b7280;
            text-decoration: none;
            font-size: 0.875rem;
        }
        
        .back-link:hover {
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo">🎬</div>
        <h2>Customer Portal Login</h2>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="POST" action="{{ url_for('auth.login') }}">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" 
                       id="username" 
                       name="username" 
                       placeholder="Enter your username" 
                       required
                       autofocus>
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" 
                       id="password" 
                       name="password" 
                       placeholder="Enter your password" 
                       required>
            </div>
            
            <button type="submit" class="btn">Sign In</button>
        </form>
        
        <div class="links">
            <p>Don't have an account?</p>
            <p>Please purchase a license from our main website</p>
            <a href="http://{{ request.host.split(':')[0] }}/" class="back-link">← Back to Main Site</a>
        </div>
    </div>
</body>
</html>
'''

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Customer login with username and password"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please enter both username and password.', 'error')
            return redirect(url_for('auth.login'))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # Check if customer exists with these credentials
            password_hash = hash_password(password)
            cursor.execute('''
                SELECT c.*, l.* 
                FROM customers c
                JOIN licenses l ON c.license_key = l.license_key
                WHERE c.username = ? AND c.password_hash = ?
            ''', (username, password_hash))
            
            result = cursor.fetchone()
            
            if result:
                # Check if license is active
                if result['status'] not in ['active', 'trial']:
                    flash(f'Your license is {result["status"]}. Please contact support.', 'error')
                    conn.close()
                    return redirect(url_for('auth.login'))
                
                # Check if trial/license has expired
                if result['expires_at']:
                    try:
                        expires_str = result['expires_at']
                        if 'T' in expires_str:
                            expiry_date = datetime.strptime(expires_str[:19], '%Y-%m-%dT%H:%M')
                        else:
                            expiry_date = datetime.strptime(expires_str, '%Y-%m-%d %H:%M:%S')
                        
                        if expiry_date < datetime.now():
                            # Update license status to expired
                            cursor.execute('''
                                UPDATE licenses SET status = 'expired' 
                                WHERE license_key = ?
                            ''', (result['license_key'],))
                            conn.commit()
                            
                            flash('Your trial/subscription has expired. Please contact support.', 'error')
                            conn.close()
                            return redirect(url_for('auth.login'))
                    except Exception as e:
                        print(f"Error parsing expiry date: {e}")
                
                # Set session variables
                session['logged_in'] = True
                session['customer_id'] = result['id']
                session['username'] = username
                session['license_key'] = result['license_key']
                session['customer_name'] = result['customer_name']
                session['customer_email'] = result['email']
                session['license_status'] = result['status']
                
                # Update last login
                cursor.execute('''
                    UPDATE customers SET last_login = CURRENT_TIMESTAMP WHERE username = ?
                ''', (username,))
                
                # Log the login
                cursor.execute('''
                    INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    result['license_key'],
                    'portal_login',
                    request.remote_addr,
                    request.headers.get('User-Agent'),
                    f'Username: {username}'
                ))
                
                conn.commit()
                conn.close()
                
                flash(f'Welcome back, {result["customer_name"]}!', 'success')
                return redirect(url_for('dashboard.customer_dashboard'))
            else:
                # Log failed attempt
                cursor.execute('''
                    INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    'UNKNOWN',
                    'portal_login_failed',
                    request.remote_addr,
                    request.headers.get('User-Agent'),
                    f'Username: {username}'
                ))
                
                conn.commit()
                conn.close()
                
                flash('Invalid username or password.', 'error')
                return redirect(url_for('auth.login'))
                
        except Exception as e:
            print(f"[ERROR] Login failed: {e}")
            conn.close()
            flash('Login failed. Please try again.', 'error')
            return redirect(url_for('auth.login'))
    
    # No need to import request again, it's already imported at the top
    return render_template_string(LOGIN_TEMPLATE, url_for=url_for, request=request)

@auth_bp.route('/logout')
def logout():
    """Customer logout"""
    if 'license_key' in session:
        # Log the logout
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            session['license_key'],
            'portal_logout',
            request.remote_addr,
            request.headers.get('User-Agent'),
            f'Username: {session.get("username")}'
        ))
        
        conn.commit()
        conn.close()
    
    # Clear session
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('auth.login'))