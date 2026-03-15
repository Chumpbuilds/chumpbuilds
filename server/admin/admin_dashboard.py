"""
X87 Player - Dashboard Module
Main dashboard view and statistics
"""

from flask import Blueprint, render_template_string, session
from admin_auth import login_required
from admin_database import get_db_connection
from admin_templates import ADMIN_DASHBOARD_TEMPLATE

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
@login_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM licenses')
    total_licenses = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
    active_licenses = cursor.fetchone()[0]
    
    try:
        cursor.execute('SELECT COUNT(*) FROM users WHERE is_active = 1')
        total_users = cursor.fetchone()[0]
    except:
        cursor.execute('SELECT COUNT(*) FROM users')
        total_users = cursor.fetchone()[0]
    
    monthly_revenue = active_licenses * 10
    
    cursor.execute('SELECT * FROM licenses ORDER BY created_at DESC LIMIT 10')
    licenses = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'total_licenses': total_licenses,
        'active_licenses': active_licenses,
        'total_users': total_users,
        'monthly_revenue': monthly_revenue
    }
    
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE, 
                                stats=stats, 
                                licenses=licenses, 
                                session=session)