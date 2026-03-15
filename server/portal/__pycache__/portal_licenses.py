"""
X87 Player - Portal Licenses Module
Customer license management
Current Date and Time (UTC): 2025-11-20 13:12:03
Current User: covchump
"""

from flask import Blueprint, render_template_string, session
from portal_auth import customer_login_required
from portal_database import get_customer_licenses

licenses_bp = Blueprint('licenses', __name__)

@licenses_bp.route('/licenses')
@customer_login_required
def my_licenses():
    # For now, redirect to dashboard (can be expanded later)
    from flask import redirect, url_for
    return redirect(url_for('dashboard.customer_dashboard'))