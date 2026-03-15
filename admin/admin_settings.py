"""
X87 Player - Settings Management Module
Handles global application settings (Version control, Update URLs)
"""

from flask import Blueprint, render_template_string, request, flash, redirect, url_for, session
from admin_auth import login_required
from admin_database import get_db_connection
from admin_templates import SETTINGS_TEMPLATE

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def manage_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        try:
            latest_version = request.form.get('latest_version', '1.0.0')
            update_url = request.form.get('update_url', '')
            
            # Update or Insert settings
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('latest_version', ?)", (latest_version,))
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('update_url', ?)", (update_url,))
            
            conn.commit()
            flash('✅ Settings updated successfully!', 'success')
        except Exception as e:
            flash(f'❌ Error updating settings: {str(e)}', 'error')
    
    # Fetch current settings
    settings = {}
    try:
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        for row in rows:
            settings[row['key']] = row['value']
    except Exception:
        # Default values if table is empty
        settings = {'latest_version': '1.0.0', 'update_url': ''}
        
    conn.close()
    
    return render_template_string(SETTINGS_TEMPLATE, settings=settings, session=session)