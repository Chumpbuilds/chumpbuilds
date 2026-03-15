"""
X87 Player - Authentication Module
Handles login, logout, and authentication decorators
Current Date and Time (UTC): 2025-11-23 11:22:00
Current User: covchump
FIXED: Added check for missing user_id in session to prevent KeyErrors
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, session
from functools import wraps
import hashlib
from admin_database import get_db_connection
from admin_templates import LOGIN_TEMPLATE

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    """
    Decorator to ensure user is logged in.
    Also checks if 'user_id' is present in session to prevent crashes with old cookies.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if logged in AND if critical session data (user_id) exists
        # If 'user_id' is missing (stale cookie), force a re-login
        if 'logged_in' not in session or not session['logged_in'] or 'user_id' not in session:
            session.clear() # Clear the corrupted/stale session
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', 
                      (username, hashed_password))
        user = cursor.fetchone()
        
        if user:
            # Check active status safely
            try:
                # Convert Row to dict-like access or handle explicitly
                keys = user.keys()
                is_active = user['is_active'] if 'is_active' in keys else 1
                
                if not is_active:
                    conn.close()
                    return render_template_string(LOGIN_TEMPLATE, error='❌ Account is deactivated')
            except Exception:
                # If column doesn't exist or error, assume active
                pass
            
            # Update last login timestamp
            try:
                cursor.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
                conn.commit()
            except Exception:
                pass
            
            # Set session variables
            session['logged_in'] = True
            session['username'] = username
            session['user_id'] = user['id']  # CRITICAL: This is what was missing in your old session
            
            # Safe role assignment
            try:
                session['role'] = user['role'] if 'role' in user.keys() else 'admin'
            except:
                session['role'] = 'admin'
            
            conn.close()
            return redirect(url_for('dashboard.admin_dashboard'))
        else:
            conn.close()
            return render_template_string(LOGIN_TEMPLATE, error='❌ Invalid username or password')
    
    return render_template_string(LOGIN_TEMPLATE)

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))