"""
X87 Player - Portal Dashboard Module
Current Date and Time (UTC): 2025-11-22
UPDATED: Added File Upload for Logo
"""

from flask import Blueprint, render_template_string, session, url_for, request, flash, redirect, current_app
from portal_auth import login_required
from portal_database import get_db_connection
from datetime import datetime
import json
import os
from werkzeug.utils import secure_filename

dashboard_bp = Blueprint('dashboard', __name__)

# Configure Upload Folder (Relative to where portal_main.py runs)
UPLOAD_FOLDER = 'static/uploads/logos'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'ico'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard - X87 Player Portal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        /* ... (Keep all existing styles) ... */
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .header { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); color: white; padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
        .header h1 { font-size: 1.5rem; display: flex; align-items: center; gap: 0.5rem; }
        .nav-buttons { display: flex; gap: 1rem; }
        .nav-btn { background: rgba(255, 255, 255, 0.2); color: white; padding: 0.5rem 1rem; border-radius: 8px; text-decoration: none; transition: all 0.3s; border: 1px solid rgba(255, 255, 255, 0.3); }
        .nav-btn:hover { background: rgba(255, 255, 255, 0.3); transform: translateY(-2px); }
        .nav-btn.active { background: rgba(255, 255, 255, 0.3); font-weight: 600; }
        .container { max-width: 1200px; margin: 2rem auto; padding: 0 2rem; }
        .welcome-card { background: white; border-radius: 16px; padding: 2rem; margin-bottom: 2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        .welcome-card h2 { color: #1f2937; margin-bottom: 1rem; font-size: 1.875rem; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1.5rem; margin-bottom: 2rem; }
        .stat-card { background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); display: flex; align-items: center; gap: 1rem; }
        .stat-icon { font-size: 2.5rem; width: 60px; height: 60px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; color: white; }
        .stat-content { flex: 1; }
        .stat-label { color: #6b7280; font-size: 0.875rem; margin-bottom: 0.25rem; }
        .stat-value { color: #1f2937; font-size: 1.5rem; font-weight: 600; }
        .info-section { background: white; border-radius: 16px; padding: 2rem; margin-bottom: 2rem; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
        .info-title { color: #1f2937; font-size: 1.25rem; font-weight: 600; margin-bottom: 1.5rem; display: flex; align-items: center; gap: 0.5rem; }
        .info-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 1rem; }
        .info-item { padding: 0.75rem; background: #f9fafb; border-radius: 8px; border-left: 3px solid #667eea; }
        .info-label { color: #6b7280; font-size: 0.75rem; text-transform: uppercase; margin-bottom: 0.25rem; }
        .info-value { color: #1f2937; font-weight: 500; }
        .status-badge { padding: 0.25rem 0.75rem; border-radius: 20px; font-size: 0.875rem; font-weight: 500; display: inline-block; }
        .status-badge.active { background: #dcfce7; color: #166534; }
        .status-badge.expired { background: #fee2e2; color: #991b1b; }
        .features-list { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 1rem; }
        .feature-tag { padding: 0.25rem 0.75rem; background: #e0e7ff; color: #3730a3; border-radius: 6px; font-size: 0.875rem; }
        .action-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem; margin-top: 2rem; }
        .action-card { background: white; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 15px rgba(0,0,0,0.1); text-align: center; transition: all 0.3s; }
        .action-card:hover { transform: translateY(-5px); box-shadow: 0 10px 30px rgba(0,0,0,0.15); }
        .action-icon { font-size: 3rem; margin-bottom: 1rem; }
        .action-title { color: #1f2937; font-size: 1.125rem; font-weight: 600; margin-bottom: 0.5rem; }
        .action-desc { color: #6b7280; margin-bottom: 1rem; font-size: 0.875rem; }
        .action-btn { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 0.625rem 1.5rem; border-radius: 8px; text-decoration: none; display: inline-block; transition: all 0.3s; }
        .action-btn:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(102, 126, 234, 0.3); }
        .trial-warning { background: #fef3c7; border: 1px solid #fde68a; padding: 1rem; border-radius: 8px; margin-bottom: 1rem; display: flex; align-items: center; gap: 1rem; }
        .trial-warning-title { color: #92400e; font-weight: 600; }
        .input-field { width: 100%; padding: 0.75rem; border: 1px solid #e5e7eb; border-radius: 8px; font-size: 0.9rem; margin-bottom: 0.5rem; }
        .profile-table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
        .profile-table th { text-align: left; padding: 0.75rem; border-bottom: 2px solid #e5e7eb; color: #6b7280; font-size: 0.875rem; }
        .profile-table td { padding: 0.75rem; border-bottom: 1px solid #f3f4f6; color: #1f2937; }
        .btn-delete { background: #fee2e2; color: #dc2626; border: none; padding: 0.25rem 0.75rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
        .btn-add { background: #dcfce7; color: #166534; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-weight: 500; }
        
        /* File Upload Styling */
        .file-upload-wrapper {
            position: relative;
            width: 100%;
            height: 100px;
            border: 2px dashed #e5e7eb;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: all 0.2s;
            background: #f9fafb;
        }
        .file-upload-wrapper:hover {
            border-color: #667eea;
            background: #f0f4ff;
        }
        .file-upload-wrapper input[type=file] {
            position: absolute;
            width: 100%;
            height: 100%;
            opacity: 0;
            cursor: pointer;
        }
        .file-upload-text {
            color: #6b7280;
            font-size: 0.9rem;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎬 X87 Player Portal</h1>
        <div class="nav-buttons">
            <a href="{{ url_for('dashboard.customer_dashboard') }}" class="nav-btn active">📊 Dashboard</a>
            <a href="{{ url_for('auth.logout') }}" class="nav-btn">🚪 Logout</a>
        </div>
    </div>
    
    <div class="container">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="trial-warning" style="background: {% if category=='success' %}#dcfce7{% else %}#fee2e2{% endif %}; border-color: {% if category=='success' %}#86efac{% else %}#fecaca{% endif %};">
                        <div class="trial-warning-content">
                            <div class="trial-warning-title" style="color: {% if category=='success' %}#166534{% else %}#991b1b{% endif %};">
                                {{ message }}
                            </div>
                        </div>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <!-- BRANDING SECTION (UPDATED) -->
        <div class="info-section" style="border-left: 4px solid #7c3aed;">
            <h3 class="info-title">🎨 App Branding & Customization</h3>
            <p style="color: #6b7280; margin-bottom: 1.5rem;">
                Personalize the app appearance. Upload a logo to display on the splash screen.
            </p>
            
            <!-- Added enctype for file upload -->
            <form method="POST" action="{{ url_for('dashboard.update_branding') }}" enctype="multipart/form-data" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.5rem;">
                <div>
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">App Name</label>
                    <input type="text" name="app_name" value="{{ customization.app_name if customization and customization.app_name != 'X87 Player' else '' }}" 
                           placeholder="e.g. My Awesome TV" class="input-field">
                    <small style="color: #6b7280;">Appears on Splash Screen, Login, and Window Title.</small>
                </div>
                
                <div>
                    <label style="display: block; margin-bottom: 0.5rem; font-weight: 500;">Upload Logo (PNG/JPG)</label>
                    <div class="file-upload-wrapper">
                        <input type="file" name="logo_file" accept=".png,.jpg,.jpeg,.ico" onchange="document.getElementById('file-name').textContent = this.files[0].name">
                        <div class="file-upload-text">
                            <span id="file-name">Click to upload image</span><br>
                            <small>Max 2MB</small>
                        </div>
                    </div>
                    {% if customization.logo_url %}
                        <div style="margin-top: 0.5rem; font-size: 0.8rem; color: #166534;">
                            ✅ Current Logo: <a href="{{ customization.logo_url }}" target="_blank">View Image</a>
                        </div>
                    {% endif %}
                </div>
                
                <div style="grid-column: 1 / -1;">
                    <button type="submit" class="action-btn" style="border: none; cursor: pointer;">💾 Save Branding</button>
                </div>
            </form>
        </div>

        <!-- CLOUD PROFILES SECTION -->
        <div class="info-section" style="border-left: 4px solid #667eea;">
            <h3 class="info-title">☁️ Cloud Profiles (DNS)</h3>
            <p style="color: #6b7280; margin-bottom: 1.5rem;">
                Profiles created here will auto-appear in the app login screen.
            </p>
            
            <form method="POST" action="{{ url_for('dashboard.add_profile') }}" style="background: #f8fafc; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
                <div style="display: grid; grid-template-columns: 1fr 2fr auto; gap: 1rem; align-items: end;">
                    <div>
                        <label style="display: block; margin-bottom: 0.5rem; font-size: 0.875rem;">Profile Name</label>
                        <input type="text" name="profile_name" placeholder="e.g. Home TV" class="input-field" style="margin-bottom: 0;" required>
                    </div>
                    <div>
                        <label style="display: block; margin-bottom: 0.5rem; font-size: 0.875rem;">Server URL (DNS)</label>
                        <input type="text" name="dns_url" placeholder="http://line.example.com" class="input-field" style="margin-bottom: 0;" required>
                    </div>
                    <button type="submit" class="btn-add">➕ Add</button>
                </div>
            </form>

            <table class="profile-table">
                <thead><tr><th>Profile Name</th><th>Server URL</th><th style="text-align: right;">Actions</th></tr></thead>
                <tbody>
                    {% for profile in profiles %}
                    <tr>
                        <td><strong>{{ profile.profile_name }}</strong></td>
                        <td style="font-family: monospace; color: #667eea;">{{ profile.dns_url }}</td>
                        <td style="text-align: right;">
                            <form method="POST" action="{{ url_for('dashboard.delete_profile', profile_id=profile.id) }}" style="display: inline;">
                                <button type="submit" class="btn-delete" onclick="return confirm('Delete?')">🗑️</button>
                            </form>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="3" style="text-align: center; color: #9ca3af; padding: 2rem;">No profiles yet.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>

        <!-- Welcome & Stats -->
        <div class="welcome-card">
            <h2>Welcome back, {{ session.customer_name }}! 👋</h2>
            <p>Manage your subscription.</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📅</div>
                <div class="stat-content"><div class="stat-label">Status</div><div class="stat-value"><span class="status-badge {{ license.status }}">{{ license.status|upper }}</span></div></div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⏰</div>
                <div class="stat-content"><div class="stat-label">Days</div><div class="stat-value">{% if days_remaining is not none %}{{ days_remaining }}{% else %}Lifetime{% endif %}</div></div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📱</div>
                <div class="stat-content"><div class="stat-label">Device</div><div class="stat-value">{% if license.device_id %}Bound{% else %}Not Bound{% endif %}</div></div>
            </div>
        </div>
    </div>
</body>
</html>
'''

@dashboard_bp.route('/dashboard')
@login_required
def customer_dashboard():
    license_key = session.get('license_key')
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch Data
    cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
    license = cursor.fetchone()
    
    cursor.execute('SELECT * FROM license_profiles WHERE license_key = ? ORDER BY created_at ASC', (license_key,))
    profiles = cursor.fetchall()
    
    cursor.execute('SELECT * FROM customizations WHERE license_key = ?', (license_key,))
    customization = cursor.fetchone()
    
    days_remaining = None
    if license and license['expires_at']:
        try:
            expires_str = license['expires_at']
            if 'T' in expires_str: expires = datetime.strptime(expires_str[:19], '%Y-%m-%dT%H:%M')
            else: expires = datetime.strptime(expires_str, '%Y-%m-%d %H:%M:%S')
            delta = expires - datetime.now()
            days_remaining = max(0, delta.days)
        except: days_remaining = None
    
    features = {}
    if license and license['features']:
        try: features = json.loads(license['features'])
        except: features = {}
    
    conn.close()
    return render_template_string(DASHBOARD_TEMPLATE, license=license, profiles=profiles, customization=customization, days_remaining=days_remaining, features=features, session=session, url_for=url_for)

@dashboard_bp.route('/update_branding', methods=['POST'])
@login_required
def update_branding():
    license_key = session.get('license_key')
    app_name = request.form.get('app_name', '').strip()
    if not app_name: app_name = "X87 Player"
    
    logo_url = None
    
    # HANDLE FILE UPLOAD
    if 'logo_file' in request.files:
        file = request.files['logo_file']
        if file and file.filename and allowed_file(file.filename):
            # Make directory if not exists
            save_dir = os.path.join(current_app.root_path, UPLOAD_FOLDER)
            os.makedirs(save_dir, exist_ok=True)
            
            # Generate safe filename with license key prefix to avoid collisions
            filename = secure_filename(f"{license_key}_{file.filename}")
            file_path = os.path.join(save_dir, filename)
            
            try:
                file.save(file_path)
                # Generate full public URL for the file
                # Assuming portal runs on port 5001, we construct the URL
                host_url = request.host_url.rstrip('/')
                logo_url = f"{host_url}/{UPLOAD_FOLDER}/{filename}"
            except Exception as e:
                flash(f'❌ Error uploading file: {e}', 'error')
                return redirect(url_for('dashboard.customer_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT id FROM customizations WHERE license_key = ?', (license_key,))
        exists = cursor.fetchone()
        
        if exists:
            if logo_url:
                # Update both if logo provided
                cursor.execute('''
                    UPDATE customizations 
                    SET app_name = ?, logo_url = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE license_key = ?
                ''', (app_name, logo_url, license_key))
            else:
                # Update only app_name if no new file
                cursor.execute('''
                    UPDATE customizations 
                    SET app_name = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE license_key = ?
                ''', (app_name, license_key))
        else:
            cursor.execute('''
                INSERT INTO customizations (license_key, app_name, logo_url) 
                VALUES (?, ?, ?)
            ''', (license_key, app_name, logo_url))
            
        conn.commit()
        flash('✅ Branding updated successfully!', 'success')
    except Exception as e:
        flash(f'❌ Error updating branding: {e}', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('dashboard.customer_dashboard'))

# ... (Rest of the file remains the same: add_profile, delete_profile)
@dashboard_bp.route('/add_profile', methods=['POST'])
@login_required
def add_profile():
    license_key = session.get('license_key')
    name = request.form.get('profile_name', '').strip()
    dns = request.form.get('dns_url', '').strip()
    if not name or not dns:
        flash('❌ Name and DNS URL required', 'error')
        return redirect(url_for('dashboard.customer_dashboard'))
    if not dns.startswith(('http://', 'https://')): dns = 'http://' + dns
    conn = get_db_connection()
    try:
        conn.execute('INSERT INTO license_profiles (license_key, profile_name, dns_url) VALUES (?, ?, ?)', (license_key, name, dns))
        conn.commit()
        flash('✅ Profile added!', 'success')
    except Exception as e: flash(f'❌ Error: {e}', 'error')
    finally: conn.close()
    return redirect(url_for('dashboard.customer_dashboard'))

@dashboard_bp.route('/delete_profile/<int:profile_id>', methods=['POST'])
@login_required
def delete_profile(profile_id):
    license_key = session.get('license_key')
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM license_profiles WHERE id = ? AND license_key = ?', (profile_id, license_key))
        conn.commit()
        flash('🗑️ Profile removed', 'success')
    except Exception as e: flash(f'❌ Error: {e}', 'error')
    finally: conn.close()
    return redirect(url_for('dashboard.customer_dashboard'))