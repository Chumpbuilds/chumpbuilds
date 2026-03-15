"""
X87 Player - Helper Functions Module
Common utility functions used across modules
"""

import secrets
import string
from datetime import datetime

def generate_license_key():
    """Generate a random license key with X87 prefix"""
    segments = ['X87']
    for _ in range(3):
        segment = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
        segments.append(segment)
    return '-'.join(segments)

def format_datetime(dt_string):
    """Format datetime string for display"""
    if not dt_string:
        return 'N/A'
    try:
        dt = datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%Y-%m-%d %I:%M %p')
    except:
        return dt_string[:16] if len(dt_string) > 16 else dt_string

def calculate_days_until_expiry(expiry_date):
    """Calculate days until license expiry"""
    if not expiry_date:
        return None
    try:
        expiry = datetime.strptime(expiry_date, '%Y-%m-%d %H:%M:%S')
        delta = expiry - datetime.now()
        return delta.days
    except:
        return None