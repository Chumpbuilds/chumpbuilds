"""
X87 Player - Portal Profile Module
Customer profile management
Current Date and Time (UTC): 2025-11-20 13:12:03
Current User: covchump
"""

from flask import Blueprint, render_template_string, session
from portal_auth import customer_login_required

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/profile')
@customer_login_required
def customer_profile():
    # For now, redirect to dashboard (can be expanded later)
    from flask import redirect, url_for
    return redirect(url_for('dashboard.customer_dashboard'))