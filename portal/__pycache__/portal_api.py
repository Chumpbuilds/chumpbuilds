"""
X87 Player - Portal API Module
API endpoints for customer portal
Current Date and Time (UTC): 2025-11-20 13:12:03
Current User: covchump
"""

from flask import Blueprint, jsonify, request, session
from portal_auth import customer_login_required
from portal_database import get_customer_licenses

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/my-licenses', methods=['GET'])
@customer_login_required
def api_my_licenses():
    """Get customer's licenses via API"""
    email = session.get('customer_email')
    licenses = get_customer_licenses(email)
    
    return jsonify({
        'success': True,
        'licenses': licenses
    }), 200

@api_bp.route('/portal-health', methods=['GET'])
def portal_health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'X87 Player Customer Portal',
        'version': '1.0.0'
    }), 200