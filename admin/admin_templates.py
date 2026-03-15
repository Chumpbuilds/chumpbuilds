"""
X87 Player - HTML Templates Module
Contains all HTML templates used in the admin panel
UPDATED: Added Settings Tab and standardized Navigation Bar
"""

# --- 1. SHARED STYLES ---
BASE_STYLES = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; }
    
    /* Header Styles */
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
    .header .user-info { display: flex; align-items: center; gap: 1rem; }
    
    /* Navigation Buttons */
    .nav-buttons { display: flex; gap: 0.5rem; margin-right: 2rem; }
    .nav-btn {
        background: rgba(255,255,255,0.2);
        color: white;
        border: 1px solid rgba(255,255,255,0.3);
        padding: 0.5rem 1rem;
        border-radius: 6px;
        text-decoration: none;
        transition: all 0.2s;
        cursor: pointer;
        font-size: 0.9rem;
    }
    .nav-btn:hover { background: rgba(255,255,255,0.3); }
    .nav-btn.active { background: rgba(255,255,255,0.4); font-weight: 600; }
    
    .logout-btn { 
        background: rgba(255,255,255,0.2); 
        color: white; 
        border: 1px solid rgba(255,255,255,0.3);
        padding: 0.5rem 1rem; 
        border-radius: 6px; 
        text-decoration: none;
        transition: background-color 0.2s;
    }
    .logout-btn:hover { background: rgba(255,255,255,0.3); }
    
    /* Layout & Components */
    .container { max-width: 1400px; margin: 2rem auto; padding: 0 2rem; }
    .alert { padding: 1rem 1.5rem; border-radius: 8px; margin-bottom: 1rem; border: 1px solid; }
    .alert-success { background: #dcfce7; color: #166534; border-color: #86efac; }
    .alert-error { background: #fee2e2; color: #991b1b; border-color: #fecaca; }
    
    /* Form Elements */
    .form-group { margin-bottom: 1.5rem; }
    label { display: block; margin-bottom: 0.5rem; color: #374151; font-weight: 500; }
    input { width: 100%; padding: 0.75rem; border: 2px solid #e5e7eb; border-radius: 8px; font-size: 1rem; box-sizing: border-box; }
    input:focus { outline: none; border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
    button.btn-save { background: #3b82f6; color: white; padding: 0.75rem 1.5rem; border: none; border-radius: 6px; cursor: pointer; font-size: 1rem; }
    button.btn-save:hover { background: #2563eb; }
    
    .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 2rem; }
"""

# --- 2. SHARED NAVIGATION HEADER (INCLUDES SETTINGS TAB) ---
NAV_HEADER = """
    <div class="header">
        <div>
            <h1>🎬 X87 Player Business Panel</h1>
            <small style="opacity: 0.8;">Professional IPTV License Management</small>
        </div>
        <div style="display: flex; align-items: center; gap: 2rem;">
            <div class="nav-buttons">
                <a href="{{ url_for('dashboard.admin_dashboard') }}" class="nav-btn">📊 Dashboard</a>
                <a href="{{ url_for('customers.manage_customers') }}" class="nav-btn">🎯 Customers</a>
                <a href="{{ url_for('users.manage_users') }}" class="nav-btn">👥 Users</a>
                <a href="{{ url_for('settings.manage_settings') }}" class="nav-btn">⚙️ Settings</a>
                <a href="{{ url_for('profile.my_profile') }}" class="nav-btn">👤 Profile</a>
            </div>
            <div class="user-info">
                <span>👤 {{ session.username }}</span>
                <a href="{{ url_for('auth.logout') }}" class="logout-btn">🚪 Logout</a>
            </div>
        </div>
    </div>
"""

# --- 3. PAGE TEMPLATES ---

# Login Page
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>🔐 Admin Login - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        ''' + BASE_STYLES + '''
        body { 
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
            width: 90%;
        }
        .login-btn { width: 100%; background: #1e40af; color: white; padding: 0.75rem; border: none; border-radius: 8px; font-size: 1rem; cursor: pointer; }
        .login-btn:hover { background: #1d4ed8; }
    </style>
</head>
<body>
    <div class="login-container">
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="font-size: 3rem; margin-bottom: 0.5rem;">🔐</h1>
            <h2 style="color: #1e40af;">Admin Login</h2>
            <p style="color: #6b7280;">X87 Player Business Panel</p>
        </div>
        
        {% if error %}
        <div class="alert alert-error">{{ error }}</div>
        {% endif %}
        
        <form method="POST">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autofocus>
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="login-btn">🚀 Access Admin Panel</button>
        </form>
    </div>
</body>
</html>
'''

# Settings Page
SETTINGS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>⚙️ System Settings - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        ''' + BASE_STYLES + '''
        .nav-btn[href*="settings"] { background: rgba(255,255,255,0.4); font-weight: 600; }
        .card { max-width: 800px; margin: 0 auto; }
    </style>
</head>
<body>
    ''' + NAV_HEADER + '''
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="card">
            <h2 style="margin-bottom: 1.5rem; color: #1e293b; border-bottom: 1px solid #eee; padding-bottom: 1rem;">
                ⚙️ Application Settings
            </h2>
            <form method="POST">
                <div class="form-group">
                    <label>Latest App Version</label>
                    <input type="text" name="latest_version" value="{{ settings.get('latest_version', '1.0.0') }}" placeholder="e.g. 1.0.5">
                    <small style="color: #6b7280; display: block; margin-top: 0.5rem;">
                        If a user opens the app with a version lower than this, they will be prompted to update.
                    </small>
                </div>
                
                <div class="form-group">
                    <label>Update Download URL</label>
                    <input type="url" name="update_url" value="{{ settings.get('update_url', '') }}" placeholder="https://yourdomain.com/downloads/app.exe">
                    <small style="color: #6b7280; display: block; margin-top: 0.5rem;">
                        The direct link where the user can download the new installer file.
                    </small>
                </div>
                
                <div style="margin-top: 2rem;">
                    <button type="submit" class="btn-save">💾 Save Global Settings</button>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
'''

# Dashboard Page
ADMIN_DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>📊 Dashboard - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        ''' + BASE_STYLES + '''
        .nav-btn[href*="dashboard"] { background: rgba(255,255,255,0.4); font-weight: 600; }
        
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; }
        .stat-number { font-size: 2.5rem; font-weight: bold; margin-bottom: 0.5rem; }
        .stat-label { color: #64748b; font-weight: 500; }
        
        .stat-card.blue .stat-number { color: #0ea5e9; }
        .stat-card.green .stat-number { color: #22c55e; }
        .stat-card.orange .stat-number { color: #f59e0b; }
        .stat-card.purple .stat-number { color: #8b5cf6; }
        
        .recent-table { width: 100%; border-collapse: collapse; }
        .recent-table th { text-align: left; padding: 1rem; background: #f8fafc; color: #64748b; font-weight: 600; font-size: 0.875rem; }
        .recent-table td { padding: 1rem; border-bottom: 1px solid #f1f5f9; color: #334155; }
    </style>
</head>
<body>
    ''' + NAV_HEADER + '''
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="stats">
            <div class="stat-card blue">
                <div class="stat-number">{{ stats.total_licenses }}</div>
                <div class="stat-label">📋 Total Licenses</div>
            </div>
            <div class="stat-card green">
                <div class="stat-number">{{ stats.active_licenses }}</div>
                <div class="stat-label">✅ Active Licenses</div>
            </div>
            <div class="stat-card orange">
                <div class="stat-number">{{ stats.total_users }}</div>
                <div class="stat-label">👥 Admin Users</div>
            </div>
            <div class="stat-card purple">
                <div class="stat-number">${{ stats.monthly_revenue }}</div>
                <div class="stat-label">💰 Est. Monthly Revenue</div>
            </div>
        </div>
        
        <div class="card">
            <h3 style="margin-bottom: 1rem; color: #1e293b;">🔑 Recently Created Licenses</h3>
            <table class="recent-table">
                <thead>
                    <tr>
                        <th>License Key</th>
                        <th>Customer</th>
                        <th>Status</th>
                        <th>Created</th>
                    </tr>
                </thead>
                <tbody>
                    {% for license in licenses %}
                    <tr>
                        <td style="font-family: monospace; background: #f1f5f9; padding: 0.5rem; border-radius: 4px; display: inline-block;">{{ license['license_key'] }}</td>
                        <td>{{ license['customer_name'] or 'N/A' }}</td>
                        <td>
                            <span style="padding: 4px 8px; border-radius: 12px; font-size: 0.75rem; font-weight: 600; 
                                background: {% if license['status']=='active' %}#dcfce7; color:#166534{% else %}#fee2e2; color:#991b1b{% endif %}">
                                {{ license['status'].upper() }}
                            </span>
                        </td>
                        <td>{{ license['created_at'][:10] }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            <div style="margin-top: 1rem; text-align: right;">
                <a href="{{ url_for('customers.manage_customers') }}" style="color: #3b82f6; text-decoration: none; font-weight: 500;">View All Licenses →</a>
            </div>
        </div>
    </div>
</body>
</html>
'''

# User Management Template
USER_MANAGEMENT_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>👥 User Management - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        ''' + BASE_STYLES + '''
        .nav-btn[href*="users"] { background: rgba(255,255,255,0.4); font-weight: 600; }
    </style>
</head>
<body>
    ''' + NAV_HEADER + '''
    <div class="container">
        <!-- 
        Note: The main content for this page is usually injected directly from admin_users.py 
        because it contains complex modals. 
        If you see a blank page, admin_users.py might be using its own internal template string.
        -->
    </div>
</body>
</html>
'''

# Profile Template
MY_PROFILE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>👤 My Profile - X87 Player</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        ''' + BASE_STYLES + '''
        .nav-btn[href*="profile"] { background: rgba(255,255,255,0.4); font-weight: 600; }
        .card { max-width: 600px; margin: 0 auto; }
    </style>
</head>
<body>
    ''' + NAV_HEADER + '''
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <div class="card">
            <h2 style="margin-bottom: 1.5rem; color: #1e293b;">👤 My Profile</h2>
            <form method="POST">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" value="{{ session.username }}" disabled style="background: #f1f5f9;">
                </div>
                
                <div class="form-group">
                    <label>Email Address</label>
                    <input type="email" name="email" value="{{ user['email'] }}" placeholder="admin@example.com">
                </div>
                
                <hr style="margin: 2rem 0; border: 0; border-top: 1px solid #eee;">
                
                <h3 style="margin-bottom: 1rem; color: #1e293b;">Change Password</h3>
                <div class="form-group">
                    <label>Current Password</label>
                    <input type="password" name="current_password" placeholder="Required to make changes">
                </div>
                
                <div class="form-group">
                    <label>New Password</label>
                    <input type="password" name="new_password" placeholder="Leave blank to keep current">
                </div>
                
                <div class="form-group">
                    <label>Confirm New Password</label>
                    <input type="password" name="confirm_password">
                </div>
                
                <button type="submit" class="btn-save">Update Profile</button>
            </form>
        </div>
    </div>
</body>
</html>
'''