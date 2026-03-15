"""
X87 Player - Home Page Application
Professional landing page with Flask
Current Date and Time (UTC): 2025-11-22 19:00:35
Current User: covchump
FIXED: Use request host for redirects to maintain domain/protocol
"""

from flask import Flask, render_template_string, jsonify, redirect, request, flash, session, url_for
from flask_cors import CORS
import os
import sys
import requests
from datetime import datetime, timedelta
import sqlite3
import hashlib
import secrets
import string

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)
app.secret_key = os.environ.get('HOME_SECRET_KEY', 'x87home_secret_key_2025')

# Enable CORS
CORS(app)

# Database path
DB_PATH = '/opt/iptv-panel/iptv_business.db'

def generate_license_key():
    """Generate a unique license key"""
    segments = ['X87']
    chars = string.ascii_uppercase + string.digits
    for _ in range(3):
        segment = ''.join(secrets.choice(chars) for _ in range(4))
        segments.append(segment)
    return '-'.join(segments)

def hash_password(password):
    """Hash a password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_base_url(request):
    """Get the base URL from the current request"""
    # If we're behind a proxy with HTTPS
    if request.headers.get('X-Forwarded-Proto') == 'https':
        scheme = 'https'
    else:
        scheme = request.scheme
    
    # Get the host (could be domain or IP)
    host = request.headers.get('X-Forwarded-Host', request.host)
    
    # Remove port if it's the default port
    if ':' in host:
        host_parts = host.split(':')
        if (scheme == 'https' and host_parts[1] == '443') or \
           (scheme == 'http' and host_parts[1] == '80'):
            host = host_parts[0]
    
    return f"{scheme}://{host}"

# Import templates
try:
    from templates import HOME_PAGE_TEMPLATE, FEATURES_PAGE_TEMPLATE, PRICING_PAGE_TEMPLATE
    print("✅ Templates imported successfully from templates.py")
except ImportError:
    from home_templates import HOME_PAGE_TEMPLATE, FEATURES_PAGE_TEMPLATE, PRICING_PAGE_TEMPLATE
    print("✅ Templates imported from home_templates.py")

# Registration success template
REGISTRATION_SUCCESS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Registration Successful - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            opacity: 0.1;
            z-index: -1;
        }
        .success-container {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            text-align: center;
            max-width: 600px;
            animation: slideUp 0.5s ease-out;
        }
        @keyframes slideUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        .success-icon {
            font-size: 5rem;
            margin-bottom: 1.5rem;
            animation: pulse 1s ease-out;
        }
        @keyframes pulse {
            0% { transform: scale(0); }
            50% { transform: scale(1.1); }
            100% { transform: scale(1); }
        }
        h1 {
            color: #10b981;
            margin-bottom: 1rem;
        }
        .info-box {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 10px;
            padding: 1.5rem;
            margin: 2rem 0;
            text-align: left;
        }
        .info-row {
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        .info-row:last-child {
            border-bottom: none;
        }
        .info-label {
            color: rgba(255, 255, 255, 0.6);
        }
        .info-value {
            color: white;
            font-weight: 500;
        }
        .license-key {
            font-family: monospace;
            background: rgba(255, 255, 255, 0.1);
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
        }
        .btn {
            display: inline-block;
            padding: 1rem 2rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            font-weight: 600;
            margin: 0.5rem;
            transition: all 0.3s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }
        .btn-secondary {
            background: transparent;
            border: 2px solid rgba(255, 255, 255, 0.3);
        }
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
        }
    </style>
</head>
<body>
    <div class="gradient-bg"></div>
    <div class="success-container">
        <div class="success-icon">🎉</div>
        <h1>Welcome to X87 Player!</h1>
        <p style="font-size: 1.125rem; margin-bottom: 2rem;">Your 7-day free trial has been activated successfully!</p>
        
        <div class="info-box">
            <h3 style="color: white; margin-bottom: 1rem;">Your Account Details:</h3>
            <div class="info-row">
                <span class="info-label">Username:</span>
                <span class="info-value">{{ username }}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Email:</span>
                <span class="info-value">{{ email }}</span>
            </div>
            <div class="info-row">
                <span class="info-label">License Key:</span>
                <span class="info-value license-key">{{ license_key }}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Trial Expires:</span>
                <span class="info-value">{{ expires_at }}</span>
            </div>
        </div>
        
        <p style="color: rgba(255, 255, 255, 0.8); margin-bottom: 2rem;">
            You can now log in to the Customer Portal to manage your account and access your streaming service.
        </p>
        
        <div>
            <a href="{{ portal_url }}" class="btn">Login to Portal</a>
            <a href="{{ home_url }}" class="btn btn-secondary">Back to Home</a>
        </div>
        
        <p style="color: rgba(255, 255, 255, 0.5); font-size: 0.875rem; margin-top: 2rem;">
            💡 Tip: Save your license key in a safe place. You'll need it to access your account.
        </p>
    </div>
</body>
</html>
'''

# Registration template
REGISTRATION_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Start Your Free Trial - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            opacity: 0.1;
            z-index: -1;
        }
        
        .registration-container {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            width: 100%;
            max-width: 500px;
            animation: slideUp 0.5s ease-out;
        }
        
        @keyframes slideUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        .header {
            text-align: center;
            margin-bottom: 2rem;
        }
        
        .logo {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        
        h1 {
            color: white;
            margin-bottom: 0.5rem;
        }
        
        .subtitle {
            color: rgba(255, 255, 255, 0.7);
        }
        
        .trial-badge {
            display: inline-block;
            background: linear-gradient(135deg, #10b981, #34d399);
            color: white;
            padding: 0.5rem 1.5rem;
            border-radius: 20px;
            margin: 1rem 0;
            font-weight: bold;
        }
        
        .form-group {
            margin-bottom: 1.5rem;
        }
        
        label {
            display: block;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 500;
            margin-bottom: 0.5rem;
            font-size: 0.875rem;
        }
        
        input {
            width: 100%;
            padding: 0.75rem;
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            font-size: 1rem;
            color: white;
            transition: all 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
            background: rgba(255, 255, 255, 0.15);
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.2);
        }
        
        input::placeholder {
            color: rgba(255, 255, 255, 0.4);
        }
        
        .input-hint {
            font-size: 0.75rem;
            color: rgba(255, 255, 255, 0.5);
            margin-top: 0.25rem;
        }
        
        .btn {
            width: 100%;
            padding: 1rem;
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
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        }
        
        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .alert {
            padding: 0.75rem;
            border-radius: 8px;
            margin-bottom: 1rem;
            font-size: 0.875rem;
        }
        
        .alert-success {
            background: rgba(16, 185, 129, 0.2);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        
        .alert-error {
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .terms {
            font-size: 0.75rem;
            color: rgba(255, 255, 255, 0.5);
            text-align: center;
            margin: 1rem 0;
        }
        
        .terms a {
            color: #667eea;
            text-decoration: none;
        }
        
        .login-link {
            text-align: center;
            margin-top: 1.5rem;
            padding-top: 1.5rem;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .login-link a {
            color: #667eea;
            text-decoration: none;
            font-weight: 500;
        }
        
        .features-list {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .feature-item {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="gradient-bg"></div>
    <div class="registration-container">
        <div class="header">
            <div class="logo">🎁</div>
            <h1>Start Your Free Trial</h1>
            <p class="subtitle">Get instant access to X87 Player</p>
            <div class="trial-badge">7 DAYS FREE - NO CREDIT CARD</div>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="features-list">
            <div class="feature-item">
                <span>✅</span>
                <span>Instant activation</span>
            </div>
            <div class="feature-item">
                <span>✅</span>
                <span>10,000+ live channels</span>
            </div>
            <div class="feature-item">
                <span>✅</span>
                <span>50,000+ movies & series</span>
            </div>
            <div class="feature-item">
                <span>✅</span>
                <span>Cancel anytime</span>
            </div>
        </div>
        
        <form method="POST" id="registrationForm">
            <div class="form-group">
                <label for="username">Username *</label>
                <input type="text" 
                       id="username" 
                       name="username" 
                       placeholder="Choose a username" 
                       required
                       minlength="3"
                       maxlength="20"
                       pattern="[a-zA-Z0-9_]+"
                       autofocus>
                <div class="input-hint">3-20 characters, letters, numbers, and underscores only</div>
            </div>
            
            <div class="form-group">
                <label for="email">Email Address *</label>
                <input type="email" 
                       id="email" 
                       name="email" 
                       placeholder="your@email.com" 
                       required>
                <div class="input-hint">We'll send your account details here</div>
            </div>
            
            <div class="form-group">
                <label for="password">Password *</label>
                <input type="password" 
                       id="password" 
                       name="password" 
                       placeholder="Choose a strong password" 
                       required
                       minlength="6">
                <div class="input-hint">At least 6 characters</div>
            </div>
            
            <div class="form-group">
                <label for="confirm_password">Confirm Password *</label>
                <input type="password" 
                       id="confirm_password" 
                       name="confirm_password" 
                       placeholder="Re-enter your password" 
                       required>
            </div>
            
            <div class="form-group">
                <label style="display: flex; align-items: center; gap: 0.5rem;">
                    <input type="checkbox" required style="width: auto;">
                    I agree to the Terms of Service and Privacy Policy
                </label>
            </div>
            
            <button type="submit" class="btn">Start Free Trial</button>
        </form>
        
        <p class="terms">
            By creating an account, you agree to our <a href="/terms">Terms of Service</a> 
            and <a href="/privacy">Privacy Policy</a>
        </p>
        
        <div class="login-link">
            <p>Already have an account? <a href="{{ portal_url }}">Sign In</a></p>
            <p style="margin-top: 0.5rem;"><a href="/" style="color: rgba(255,255,255,0.5);">← Back to Home</a></p>
        </div>
    </div>
    
    <script>
        const form = document.getElementById('registrationForm');
        const password = document.getElementById('password');
        const confirmPassword = document.getElementById('confirm_password');
        const username = document.getElementById('username');
        
        form.addEventListener('submit', function(e) {
            if (password.value !== confirmPassword.value) {
                e.preventDefault();
                alert('Passwords do not match!');
                confirmPassword.focus();
            }
        });
        
        username.addEventListener('input', function(e) {
            this.value = this.value.toLowerCase().replace(/[^a-z0-9_]/g, '');
        });
    </script>
</body>
</html>
'''

PURCHASE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Purchase Premium - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0a0a;
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            opacity: 0.1;
            z-index: -1;
        }
        .container {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 3rem;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            text-align: center;
            max-width: 500px;
        }
        .logo { font-size: 4rem; margin-bottom: 1rem; }
        h1 { color: white; margin-bottom: 1rem; }
        p { color: rgba(255,255,255,0.8); margin-bottom: 1.5rem; line-height: 1.6; }
        
        .contact-info {
            background: rgba(255,255,255,0.05);
            padding: 1.5rem;
            border-radius: 10px;
            margin: 2rem 0;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .email-link {
            display: inline-block;
            background: linear-gradient(135deg, #ffd700, #ffed4e);
            color: #1a1a1a;
            padding: 1rem 2rem;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            margin-top: 1rem;
            transition: all 0.3s;
        }
        
        .email-link:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(255, 215, 0, 0.4);
        }
        
        .back-link {
            color: rgba(255,255,255,0.5);
            text-decoration: none;
            margin-top: 2rem;
            display: inline-block;
        }
        
        .back-link:hover {
            color: #667eea;
        }
    </style>
</head>
<body>
    <div class="gradient-bg"></div>
    <div class="container">
        <div class="logo">💳</div>
        <h1>Purchase Premium License</h1>
        <p>Get unlimited access to X87 Player with our premium subscription!</p>
        
        <div class="contact-info">
            <h3>How to Purchase:</h3>
            <p>Contact our sales team for payment options and instant activation</p>
            <a href="mailto:sales@x87player.xyz?subject=Premium%20License%20Purchase" class="email-link">
                Contact Sales Team
            </a>
        </div>
        
        <p><strong>Payment Methods:</strong></p>
        <p>Credit Card, PayPal, Cryptocurrency</p>
        
        <a href="/" class="back-link">← Back to Home</a>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    """Main landing page"""
    return render_template_string(HOME_PAGE_TEMPLATE)

@app.route('/features')
def features():
    """Features page"""
    return render_template_string(FEATURES_PAGE_TEMPLATE)

@app.route('/pricing')
def pricing():
    """Pricing page"""
    return render_template_string(PRICING_PAGE_TEMPLATE)

@app.route('/admin')
def redirect_admin():
    """Redirect to admin panel"""
    base_url = get_base_url(request)
    # If we're on the domain, use subdomain
    if 'x87player.xyz' in base_url:
        return redirect('https://admin.x87player.xyz')
    else:
        # Otherwise use IP with port
        return redirect(f'{base_url.split(":")[0]}:5000')

@app.route('/portal')
def redirect_portal():
    """Redirect to customer portal"""
    base_url = get_base_url(request)
    # If we're on the domain, use subdomain
    if 'x87player.xyz' in base_url:
        return redirect('https://portal.x87player.xyz')
    else:
        # Otherwise use IP with port
        return redirect(f'{base_url.split(":")[0]}:5001')

@app.route('/register-trial', methods=['GET', 'POST'])
def register_trial():
    """Handle free trial registration"""
    base_url = get_base_url(request)
    
    # Determine portal URL based on how user accessed the site
    if 'x87player.xyz' in base_url:
        portal_url = 'https://portal.x87player.xyz/login'
    else:
        # Use IP with port
        portal_url = f'{base_url.split(":")[0]}:5001/login'
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        print(f"📝 Registration attempt for: {username} ({email})")
        print(f"   Base URL: {base_url}")
        print(f"   Portal URL: {portal_url}")
        
        # Validation
        if not all([username, email, password, confirm_password]):
            flash('All fields are required.', 'error')
            return redirect('/register-trial')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect('/register-trial')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
            return redirect('/register-trial')
        
        # Database operations
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Check if username exists
            cursor.execute('SELECT id FROM customers WHERE username = ?', (username,))
            if cursor.fetchone():
                flash('Username already taken. Please choose another.', 'error')
                conn.close()
                return redirect('/register-trial')
            
            # Check if email exists
            cursor.execute('SELECT id FROM customers WHERE email = ?', (email,))
            if cursor.fetchone():
                flash('Email already registered. Please sign in.', 'error')
                conn.close()
                return redirect(portal_url)
            
            # Generate license key
            license_key = generate_license_key()
            
            # Ensure unique license key
            while True:
                cursor.execute('SELECT id FROM licenses WHERE license_key = ?', (license_key,))
                if not cursor.fetchone():
                    break
                license_key = generate_license_key()
            
            # Calculate expiry (7 days)
            expires_at = (datetime.now() + timedelta(days=7))
            expires_at_str = expires_at.strftime('%Y-%m-%d %H:%M:%S')
            
            # Create license (for admin panel)
            cursor.execute('''
                INSERT INTO licenses (
                    license_key, customer_name, customer_email, 
                    status, expires_at, max_devices, features, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                license_key,
                username,
                email,
                'active',
                expires_at_str,
                1,
                '{"live_tv": true, "movies": true, "series": true, "search": true, "favorites": true, "epg": true}',
                f'7-Day Free Trial - Registered {datetime.now().strftime("%Y-%m-%d")}'
            ))
            
            # Create customer account (for portal login)
            password_hash = hash_password(password)
            cursor.execute('''
                INSERT INTO customers (
                    license_key, username, email, password_hash, customer_name
                ) VALUES (?, ?, ?, ?, ?)
            ''', (license_key, username, email, password_hash, username))
            
            conn.commit()
            conn.close()
            
            print(f"✅ Trial registration successful: {username}")
            
            # Show success page with account details
            return render_template_string(
                REGISTRATION_SUCCESS_TEMPLATE,
                username=username,
                email=email,
                license_key=license_key,
                expires_at=expires_at.strftime('%Y-%m-%d'),
                portal_url=portal_url,
                home_url=base_url
            )
            
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"❌ Registration error: {e}")
            flash('Registration failed. Please try again.', 'error')
            return redirect('/register-trial')
    
    # GET request - show registration form
    return render_template_string(REGISTRATION_TEMPLATE, portal_url=portal_url)

@app.route('/purchase')
def purchase():
    """Purchase page"""
    return render_template_string(PURCHASE_TEMPLATE)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'X87 Player Home Page',
        'version': '1.0.0',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200

@app.route('/api/status')
def api_status():
    """Check status of all services"""
    status = {
        'home': 'online',
        'admin': 'checking',
        'portal': 'checking'
    }
    
    # Check admin panel
    try:
        response = requests.get('http://127.0.0.1:5000/api/health', timeout=2)
        if response.status_code == 200:
            status['admin'] = 'online'
        else:
            status['admin'] = 'offline'
    except:
        status['admin'] = 'offline'
    
    # Check customer portal
    try:
        response = requests.get('http://127.0.0.1:5001/api/health', timeout=2)
        if response.status_code == 200:
            status['portal'] = 'online'
        else:
            status['portal'] = 'offline'
    except:
        status['portal'] = 'offline'
    
    return jsonify(status)

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🏠 X87 Player Home Page Starting...")
    print("="*70)
    print(f"📍 Running on port 5002")
    print(f"🌐 Access at: http://0.0.0.0:5002")
    print("="*70 + "\n")
    
    app.run(
        host='0.0.0.0',
        port=5002,
        debug=True
    )