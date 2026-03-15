"""
X87 Player - Profile Management Module
Handles user profile operations
Current Date and Time (UTC): 2025-11-20 11:57:00
Current User: covchump
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, session, flash, get_flashed_messages
from admin_auth import login_required
from admin_database import get_db_connection
from admin_templates import MY_PROFILE_TEMPLATE
import hashlib

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def my_profile():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        email = request.form.get('email', '')
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        cursor.execute('UPDATE users SET email = ? WHERE id = ?', (email, session['user_id']))
        
        if current_password and new_password:
            if new_password != confirm_password:
                flash('New passwords do not match!', 'error')
            else:
                hashed_current = hashlib.sha256(current_password.encode()).hexdigest()
                cursor.execute('SELECT password FROM users WHERE id = ?', (session['user_id'],))
                user_password = cursor.fetchone()[0]
                
                if user_password == hashed_current:
                    hashed_new = hashlib.sha256(new_password.encode()).hexdigest()
                    cursor.execute('UPDATE users SET password = ? WHERE id = ?', (hashed_new, session['user_id']))
                    flash('Password changed successfully!', 'success')
                else:
                    flash('Current password is incorrect!', 'error')
        
        conn.commit()
        
        if current_password or new_password:
            # Only show general success if no password was attempted
            pass
        else:
            flash('Profile updated successfully!', 'success')
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    return render_template_string(MY_PROFILE_TEMPLATE, user=user, session=session)