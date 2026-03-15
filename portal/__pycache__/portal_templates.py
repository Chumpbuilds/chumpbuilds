"""
X87 Player - Portal Templates Module
HTML templates for customer portal
Current Date and Time (UTC): 2025-11-20 13:12:03
Current User: covchump
"""

# Portal Login Template
PORTAL_LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🔐 Customer Login - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; 
            background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: white;
            padding: 3rem;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 400px;
            width: 100%;
            margin: 1rem;
        }
        h1 { text-align: center; color: #1e40af; margin-bottom: 1rem; font-size: 2.5rem; }
        .subtitle { text-align: center; color: #6b7280; margin-bottom: 2rem; }
        .form-group { margin-bottom: 1.5rem; }
        label { display: block; margin-bottom: 0.5rem; color: #374151; font-weight: 500; }
        input { 
            width: 100%; 
            padding: 0.75rem; 
            border: 2px solid #e5e7eb; 
            border-radius: 8px; 
            font-size: 1rem;
            box-sizing: border-box;
            transition: border-color 0.2s;
        }
        input:focus { outline: none; border-color: #1e40af; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
        button { 
            width: 100%; 
            background: #1e40af; 
            color: white; 
            padding: 0.75rem; 
            border: none; 
            border-radius: 8px; 
            font-size: 1rem; 
            cursor: pointer;
            font-weight: 600;
            transition: background-color 0.2s;
        }
        button:hover { background: #1d4ed8; }
        .error { 
            color: #dc2626; 
            text-align: center; 
            margin-bottom: 1rem; 
            padding: 0.75rem;
            background: #fee2e2;
            border-radius: 8px;
            border: 1px solid #fecaca;
        }
        .footer { 
            text-align: center; 
            margin-top: 2rem; 
            padding-top: 2rem;
            border-top: 1px solid #e5e7eb;
        }
        .security-notice {
            background: #f0f9ff;
            border: 1px solid #0ea5e9;
            color: #0c4a6e;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            font-size: 0.9rem;
        }
        .links {
            text-align: center;
            margin-top: 1.5rem;
        }
        .links a {
            color: #1e40af;
            text-decoration: none;
            font-weight: 500;
        }
        .links a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <h1>🎬</h1>
        <h2 style="text-align: center; color: #1e40af; margin: 0;">Customer Portal</h2>
        <p class="subtitle">X87 Player License Management</p>
        
        <div class="security-notice">
            <strong>🛡️ Secure Customer Access</strong><br>
            Manage your licenses and subscriptions
        </div>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        <form method="POST">
            <div class="form-group">
                <label for="username">Username or Email</label>
                <input type="text" id="username" name="username" required autofocus placeholder="Enter username or email">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Enter your password">
            </div>
            <button type="submit">🚀 Login to Portal</button>
        </form>
        
        <div class="links">
            <p>Don't have an account? <a href="{{ url_for('register.register') }}">Register Now</a></p>
            <p><a href="#">Forgot Password?</a></p>
        </div>
        
        <div class="footer">
            <p style="color: #6b7280; font-size: 0.9rem; margin: 0;">
                X87 Player Customer Portal<br>
                <strong>Professional IPTV Solutions</strong><br>
                Powered by <strong>covchump</strong> © 2025
            </p>
        </div>
    </div>
</body>
</html>
'''

# Portal Register Template
PORTAL_REGISTER_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>📝 Register - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; 
            background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 2rem 0;
        }
        .register-container {
            background: white;
            padding: 3rem;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            max-width: 500px;
            width: 100%;
            margin: 1rem;
        }
        h1 { text-align: center; color: #1e40af; margin-bottom: 1rem; font-size: 2rem; }
        .subtitle { text-align: center; color: #6b7280; margin-bottom: 2rem; }
        .form-group { margin-bottom: 1.5rem; }
        label { display: block; margin-bottom: 0.5rem; color: #374151; font-weight: 500; }
        input { 
            width: 100%; 
            padding: 0.75rem; 
            border: 2px solid #e5e7eb; 
            border-radius: 8px; 
            font-size: 1rem;
            box-sizing: border-box;
            transition: border-color 0.2s;
        }
        input:focus { outline: none; border-color: #1e40af; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
        button { 
            width: 100%; 
            background: #22c55e; 
            color: white; 
            padding: 0.75rem; 
            border: none; 
            border-radius: 8px; 
            font-size: 1rem; 
            cursor: pointer;
            font-weight: 600;
            transition: background-color 0.2s;
        }
        button:hover { background: #16a34a; }
        .error { 
            color: #dc2626; 
            text-align: center; 
            margin-bottom: 1rem; 
            padding: 0.75rem;
            background: #fee2e2;
            border-radius: 8px;
            border: 1px solid #fecaca;
        }
        .benefits {
            background: #f0fdf4;
            border: 1px solid #86efac;
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
        }
        .benefits h3 {
            color: #166534;
            margin: 0 0 0.5rem 0;
            font-size: 1rem;
        }
        .benefits ul {
            margin: 0;
            padding-left: 1.5rem;
            color: #15803d;
            font-size: 0.9rem;
        }
        .links {
            text-align: center;
            margin-top: 1.5rem;
        }
        .links a {
            color: #1e40af;
            text-decoration: none;
            font-weight: 500;
        }
    </style>
</head>
<body>
    <div class="register-container">
        <h1>📝 Create Account</h1>
        <p class="subtitle">Join X87 Player Today</p>
        
        <div class="benefits">
            <h3>✨ Get Started with:</h3>
            <ul>
                <li>7-Day Free Trial License</li>
                <li>Access to Live TV & Movies</li>
                <li>Professional Support</li>
                <li>Easy License Management</li>
            </ul>
        </div>
        
        {% if error %}
        <div class="error">{{ error }}</div>
        {% endif %}
        
        <form method="POST">
            <div class="form-group">
                <label for="username">Username *</label>
                <input type="text" id="username" name="username" required placeholder="Choose a username">
            </div>
            <div class="form-group">
                <label for="email">Email Address *</label>
                <input type="email" id="email" name="email" required placeholder="your@email.com">
            </div>
            <div class="form-group">
                <label for="full_name">Full Name</label>
                <input type="text" id="full_name" name="full_name" placeholder="John Doe">
            </div>
            <div class="form-group">
                <label for="company">Company (Optional)</label>
                <input type="text" id="company" name="company" placeholder="Company name">
            </div>
            <div class="form-group">
                <label for="password">Password *</label>
                <input type="password" id="password" name="password" required placeholder="Min 6 characters">
            </div>
            <div class="form-group">
                <label for="confirm_password">Confirm Password *</label>
                <input type="password" id="confirm_password" name="confirm_password" required placeholder="Confirm your password">
            </div>
            <button type="submit">🚀 Create Account & Get Trial</button>
        </form>
        
        <div class="links">
            <p>Already have an account? <a href="{{ url_for('auth.login') }}">Login Here</a></p>
        </div>
    </div>
</body>
</html>
'''

# Portal Dashboard Template
PORTAL_DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>📊 Dashboard - X87 Player Portal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; }
        .header { 
            background: linear-gradient(135deg, #1e40af 0%, #7c3aed 100%); 
            color: white; 
            padding: 1rem 2rem; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 1.5rem; }
        .nav-buttons {
            display: flex;
            gap: 0.5rem;
        }
        .nav-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            padding: 0.5rem 1rem;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.9rem;
        }
        .nav-btn:hover { background: rgba(255,255,255,0.3); }
        .nav-btn.active { background: rgba(255,255,255,0.4); font-weight: 600; }
        .container { max-width: 1400px; margin: 2rem auto; padding: 0 2rem; }
        
        .welcome-card {
            background: white;
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            margin-bottom: 2rem;
        }
        .welcome-card h2 {
            color: #1e293b;
            margin-bottom: 0.5rem;
        }
        
        .stats { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 1.5rem; 
            margin-bottom: 2rem; 
        }
        .stat-card { 
            background: white; 
            padding: 1.5rem; 
            border-radius: 12px; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            text-align: center;
        }
        .stat-number { font-size: 2rem; font-weight: bold; margin-bottom: 0.5rem; }
        .stat-label { color: #64748b; }
        .stat-card.active .stat-number { color: #22c55e; }
        .stat-card.expired .stat-number { color: #ef4444; }
        .stat-card.warning .stat-number { color: #f59e0b; }
        
        .table-container { 
            background: white; 
            border-radius: 12px; 
            overflow: hidden; 
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        }
        .table-header {
            background: #f8fafc;
            padding: 1.5rem;
            border-bottom: 1px solid #e2e8f0;
        }
        table { width: 100%; border-collapse: collapse; }
        th { 
            background: #f8fafc; 
            padding: 1rem; 
            text-align: left; 
            font-weight: 600; 
            color: #374151; 
        }
        td { padding: 1rem; border-bottom: 1px solid #f1f5f9; }
        
        .license-key {
            font-family: monospace;
            background: #f3f4f6;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
        }
        
        .status {
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 500;
        }
        .status.active { background: #dcfce7; color: #166534; }
        .status.expired { background: #fee2e2; color: #991b1b; }
        .status.suspended { background: #fef3c7; color: #92400e; }
        
        .btn-copy {
            background: #3b82f6;
            color: white;
            padding: 0.25rem 0.5rem;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.75rem;
        }
        .btn-copy:hover { background: #2563eb; }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🎬 X87 Player Customer Portal</h1>
            <small style="opacity: 0.8;">License Management System</small>
        </div>
        <div style="display: flex; align-items: center; gap: 2rem;">
            <div class="nav-buttons">
                <a href="{{ url_for('dashboard.customer_dashboard') }}" class="nav-btn active">📊 Dashboard</a>
                <a href="{{ url_for('licenses.my_licenses') }}" class="nav-btn">🔑 Licenses</a>
                <a href="{{ url_for('profile.customer_profile') }}" class="nav-btn">👤 Profile</a>
            </div>
            <div>
                <span style="margin-right: 1rem;">👤 {{ session.customer_name }}</span>
                <a href="{{ url_for('auth.logout') }}" class="nav-btn">🚪 Logout</a>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="welcome-card">
            <h2>Welcome back, {{ session.customer_name }}! 👋</h2>
            <p style="color: #64748b;">Manage your X87 Player licenses and subscriptions from this portal.</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ stats.total_licenses }}</div>
                <div class="stat-label">Total Licenses</div>
            </div>
            <div class="stat-card active">
                <div class="stat-number">{{ stats.active_licenses }}</div>
                <div class="stat-label">Active Licenses</div>
            </div>
            <div class="stat-card expired">
                <div class="stat-number">{{ stats.expired_licenses }}</div>
                <div class="stat-label">Expired</div>
            </div>
            <div class="stat-card warning">
                <div class="stat-number">{{ stats.expiring_soon }}</div>
                <div class="stat-label">Expiring Soon</div>
            </div>
        </div>
        
        <div class="table-container">
            <div class="table-header">
                <h2>🔑 Your Licenses</h2>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>License Key</th>
                        <th>Status</th>
                        <th>Created</th>
                        <th>Expires</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {% for license in licenses %}
                    <tr>
                        <td>
                            <span class="license-key">{{ license['license_key'] }}</span>
                        </td>
                        <td>
                            <span class="status {{ license['status'] }}">{{ license['status'].title() }}</span>
                        </td>
                        <td>{{ license['created_at'][:10] if license['created_at'] else 'N/A' }}</td>
                        <td>{{ license['expires_at'][:10] if license['expires_at'] else 'Never' }}</td>
                        <td>
                            <button class="btn-copy" onclick="copyToClipboard('{{ license['license_key'] }}')">
                                📋 Copy
                            </button>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                alert('License key copied to clipboard!');
            });
        }
    </script>
</body>
</html>
'''