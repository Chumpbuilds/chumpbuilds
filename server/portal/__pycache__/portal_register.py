"""
X87 Player - Portal Registration Module
New customer registration
Current Date and Time (UTC): 2025-11-20 13:12:03
Current User: covchump
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, flash
from portal_database import create_customer_account
from portal_templates import PORTAL_REGISTER_TEMPLATE

register_bp = Blueprint('register', __name__)

@register_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        full_name = request.form.get('full_name', '')
        company = request.form.get('company', '')
        
        # Validate
        if password != confirm_password:
            return render_template_string(PORTAL_REGISTER_TEMPLATE, error='Passwords do not match')
        
        if len(password) < 6:
            return render_template_string(PORTAL_REGISTER_TEMPLATE, error='Password must be at least 6 characters')
        
        # Create account
        result = create_customer_account(username, password, email, full_name, company)
        
        if result['success']:
            flash(f'✅ Account created successfully! Your trial license: {result["trial_license"]}', 'success')
            return redirect(url_for('auth.login'))
        else:
            return render_template_string(PORTAL_REGISTER_TEMPLATE, error=result['error'])
    
    return render_template_string(PORTAL_REGISTER_TEMPLATE)