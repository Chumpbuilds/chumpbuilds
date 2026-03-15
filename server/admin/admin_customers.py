"""
X87 Player - Customer Management Module
Handles all customer and license operations
FIXED: URL generation for clear_conflicts route
Current Date and Time (UTC): 2025-11-22 11:52:30
Current User: covchump
"""

from flask import Blueprint, render_template_string, request, redirect, url_for, session, jsonify, flash
from admin_auth import login_required
from admin_database import get_db_connection
from datetime import datetime, timedelta
import json
import sqlite3
import traceback
import secrets
import string
import sys

# Try to import the template with error handling
try:
    from admin_customers_template import CUSTOMER_TEMPLATE
    print("[CUSTOMERS] Template imported successfully")
except ImportError as e:
    print(f"[CUSTOMERS] Error importing template: {e}")
    # Fallback to a simple template if import fails
    CUSTOMER_TEMPLATE = '''
    <!DOCTYPE html>
    <html>
    <head><title>Customer Management</title></head>
    <body>
        <h1>Customer Management</h1>
        <p>Template loading error. Please check the template file.</p>
        <a href="{{ url_for('dashboard.admin_dashboard') }}">Back to Dashboard</a>
    </body>
    </html>
    '''

customers_bp = Blueprint('customers', __name__)

def generate_license_key():
    """Generate a license key"""
    segments = ['X87']
    chars = string.ascii_uppercase + string.digits
    for _ in range(3):
        segment = ''.join(secrets.choice(chars) for _ in range(4))
        segments.append(segment)
    return '-'.join(segments)

def convert_datetime_format(datetime_str):
    """Convert datetime from HTML datetime-local format to database format"""
    if not datetime_str:
        return None
    
    try:
        # Remove any trailing 'Z' if present
        datetime_str = datetime_str.replace('Z', '')
        
        # Try to parse different formats
        if 'T' in datetime_str:
            # HTML datetime-local format
            if len(datetime_str) == 16:  # 2030-11-28T19:50
                dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M')
            else:  # 2030-11-28T19:50:00
                dt = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%S')
        elif ' ' in datetime_str:
            # Already in correct format
            if len(datetime_str) == 19:  # 2030-11-28 19:50:00
                dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M:%S')
            else:  # 2030-11-28 19:50
                dt = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
        else:
            # Just a date, add time
            dt = datetime.strptime(datetime_str, '%Y-%m-%d')
        
        # Return in the standard database format with seconds
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception as e:
        print(f"[ERROR] Date conversion failed for '{datetime_str}': {e}")
        # Try to return the string as-is if it looks like a valid date
        if datetime_str and len(datetime_str) >= 10:
            # Add time if not present
            if len(datetime_str) == 10:  # Just date
                return datetime_str + ' 00:00:00'
        return None

@customers_bp.route('/customers')
@login_required
def manage_customers():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First check if customers table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='customers'
        """)
        
        customers = []
        if cursor.fetchone():
            # Get all registered customers with their license counts
            cursor.execute('''
                SELECT c.*,
                       (SELECT COUNT(*) FROM licenses WHERE customer_email = c.email) as license_count,
                       (SELECT COUNT(*) FROM licenses WHERE customer_email = c.email AND status = 'active') as active_license_count
                FROM customers c
                ORDER BY c.created_at DESC
            ''')
            rows = cursor.fetchall()
            customers = [dict(row) for row in rows]
        
        # Get all licenses with hardware binding info
        cursor.execute('''
            SELECT l.*, 
                   (SELECT COUNT(*) FROM license_logs 
                    WHERE license_key = l.license_key 
                    AND action = 'binding_conflict'
                    AND timestamp > datetime('now', '-7 days')) as recent_binding_conflicts
            FROM licenses l 
            ORDER BY l.created_at DESC
        ''')
        licenses_rows = cursor.fetchall()
        licenses = []
        for row in licenses_rows:
            license = dict(row)
            # Parse features if they exist
            if license.get('features'):
                try:
                    license['features_dict'] = json.loads(license['features'])
                except:
                    license['features_dict'] = {}
            else:
                license['features_dict'] = {}
            licenses.append(license)
        
        # Debug: Print number of licenses found
        print(f"[DEBUG] Found {len(licenses)} licenses in database")
        
        # Get recent REAL binding conflicts (only last 7 days, and verify they're actual conflicts)
        cursor.execute('''
            SELECT ll.*, l.customer_name, l.device_id as current_device
            FROM license_logs ll
            JOIN licenses l ON ll.license_key = l.license_key
            WHERE ll.action = 'binding_conflict'
            AND ll.timestamp > datetime('now', '-7 days')
            ORDER BY ll.timestamp DESC
            LIMIT 10
        ''')
        conflict_rows = cursor.fetchall()
        
        # Filter out false conflicts (where the hardware IDs actually match)
        real_conflicts = []
        for conflict in conflict_rows:
            try:
                details = json.loads(conflict['details']) if conflict['details'] else {}
                attempted_hw = details.get('attempted_hardware_id', '').strip().lower()
                current_hw = conflict['current_device'].strip().lower() if conflict['current_device'] else ''
                
                # Only show if they're actually different
                if attempted_hw and current_hw and attempted_hw != current_hw:
                    real_conflicts.append({
                        'id': conflict['id'],  # Add conflict log ID for clearing
                        'license_key': conflict['license_key'],
                        'customer_name': conflict['customer_name'],
                        'timestamp': conflict['timestamp'],
                        'attempted_device': attempted_hw[:16] + '...',
                        'bound_device': current_hw[:16] + '...'
                    })
            except:
                continue
        
        # Calculate statistics
        cursor.execute('SELECT COUNT(DISTINCT customer_email) FROM licenses WHERE customer_email IS NOT NULL')
        total_customers = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "active"')
        active_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "expired"')
        expired_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE status = "suspended"')
        suspended_licenses = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM licenses WHERE device_id IS NOT NULL')
        bound_licenses = cursor.fetchone()[0]
        
        # Check for expiring soon (within 7 days)
        seven_days_from_now = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute('''
            SELECT COUNT(*) FROM licenses 
            WHERE status = "active" 
            AND expires_at IS NOT NULL 
            AND expires_at < ? 
            AND expires_at > CURRENT_TIMESTAMP
        ''', (seven_days_from_now,))
        expiring_soon = cursor.fetchone()[0]
        
        conn.close()
        
        stats = {
            'total_customers': total_customers,
            'active_licenses': active_licenses,
            'expired_licenses': expired_licenses,
            'suspended_licenses': suspended_licenses,
            'expiring_soon': expiring_soon,
            'registered_customers': len(customers),
            'bound_licenses': bound_licenses,
            'total_licenses': len(licenses)
        }
        
        # Generate URLs here to pass to template
        # Don't generate clear_conflicts URL here since it needs a license_key parameter
        form_urls = {
            'add_license': url_for('customers.add_license'),
            'edit_license': url_for('customers.edit_license'),
            'clear_all_conflicts': url_for('customers.clear_all_conflicts')
        }
        
        # Use the template from the separate file
        return render_template_string(CUSTOMER_TEMPLATE, 
                                     licenses=licenses, 
                                     customers=customers,
                                     stats=stats,
                                     conflicts=real_conflicts,
                                     session=session,
                                     form_urls=form_urls,
                                     url_for=url_for)  # Pass url_for to template
    except Exception as e:
        print(f"[CUSTOMERS] Error in manage_customers: {e}")
        traceback.print_exc()
        return f"<h1>Error</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>", 500

@customers_bp.route('/clear_conflict/<license_key>', methods=['POST'])
@login_required
def clear_conflicts(license_key):
    """Clear binding conflicts for a specific license"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete binding conflict logs for this license
        cursor.execute('''
            DELETE FROM license_logs 
            WHERE license_key = ? AND action = 'binding_conflict'
        ''', (license_key,))
        
        deleted_count = cursor.rowcount
        
        # Log the action
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            license_key,
            'conflicts_cleared',
            request.remote_addr,
            f'Admin: {session.get("username")}',
            json.dumps({
                'cleared_count': deleted_count,
                'admin': session.get('username'),
                'timestamp': datetime.now().isoformat()
            })
        ))
        
        conn.commit()
        conn.close()
        
        flash(f'✅ Cleared {deleted_count} binding conflicts for license {license_key}', 'success')
    except Exception as e:
        flash(f'❌ Error clearing conflicts: {str(e)}', 'error')
    
    return redirect(url_for('customers.manage_customers'))

@customers_bp.route('/clear_all_conflicts', methods=['POST'])
@login_required
def clear_all_conflicts():
    """Clear all binding conflicts older than 7 days"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Delete old binding conflict logs (or all conflicts based on your preference)
        cursor.execute('''
            DELETE FROM license_logs 
            WHERE action = 'binding_conflict'
        ''')
        
        deleted_count = cursor.rowcount
        
        # Log the action
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            'SYSTEM',
            'all_conflicts_cleared',
            request.remote_addr,
            f'Admin: {session.get("username")}',
            json.dumps({
                'cleared_count': deleted_count,
                'admin': session.get('username'),
                'timestamp': datetime.now().isoformat()
            })
        ))
        
        conn.commit()
        conn.close()
        
        flash(f'✅ Cleared {deleted_count} binding conflicts', 'success')
    except Exception as e:
        flash(f'❌ Error clearing conflicts: {str(e)}', 'error')
    
    return redirect(url_for('customers.manage_customers'))

# Rest of your functions remain the same...

@customers_bp.route('/add_license', methods=['POST'])
@login_required
def add_license():
    """Add a new license"""
    try:
        # Get form data
        license_key = request.form.get('license_key', '').strip()
        if not license_key:
            license_key = generate_license_key()
        
        customer_name = request.form['customer_name']
        customer_email = request.form.get('customer_email', '')
        status = request.form.get('status', 'active')
        expires_at_raw = request.form.get('expires_at', '')
        max_devices = request.form.get('max_devices', 1)
        notes = request.form.get('notes', '')
        
        # Convert the datetime format
        expires_at = convert_datetime_format(expires_at_raw)
        
        # Get features
        features = {
            'live_tv': 'feature_live_tv' in request.form,
            'movies': 'feature_movies' in request.form,
            'series': 'feature_series' in request.form,
            'search': 'feature_search' in request.form,
            'favorites': 'feature_favorites' in request.form,
            'epg': 'feature_epg' in request.form
        }
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert license
        cursor.execute('''
            INSERT INTO licenses 
            (license_key, customer_name, customer_email, status, expires_at, max_devices, features, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (license_key, customer_name, customer_email, status, expires_at, 
              max_devices, json.dumps(features), notes))
        
        # Log the action
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            license_key,
            'license_created',
            request.remote_addr,
            f'Admin: {session.get("username")}',
            json.dumps({
                'customer_name': customer_name,
                'admin': session.get('username'),
                'timestamp': datetime.now().isoformat()
            })
        ))
        
        conn.commit()
        conn.close()
        
        flash(f'✅ License {license_key} created successfully!', 'success')
    except sqlite3.IntegrityError:
        flash('❌ License key already exists!', 'error')
    except Exception as e:
        flash(f'❌ Error adding license: {str(e)}', 'error')
        traceback.print_exc()
    
    return redirect(url_for('customers.manage_customers'))

@customers_bp.route('/edit_license', methods=['POST'])
@login_required
def edit_license():
    """Edit an existing license"""
    try:
        # Get form data
        license_id = request.form['license_id']
        customer_name = request.form['customer_name']
        customer_email = request.form.get('customer_email', '')
        status = request.form.get('status', 'active')
        expires_at_raw = request.form.get('expires_at', '')
        max_devices = request.form.get('max_devices', 1)
        notes = request.form.get('notes', '')
        
        # Convert the datetime format
        expires_at = convert_datetime_format(expires_at_raw)
        
        # Get features
        features = {
            'live_tv': 'feature_live_tv' in request.form,
            'movies': 'feature_movies' in request.form,
            'series': 'feature_series' in request.form,
            'search': 'feature_search' in request.form,
            'favorites': 'feature_favorites' in request.form,
            'epg': 'feature_epg' in request.form
        }
        
        # Handle reset device option
        reset_device = 'reset_device' in request.form
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current license info for logging
        cursor.execute('SELECT * FROM licenses WHERE id = ?', (license_id,))
        old_license = cursor.fetchone()
        
        if old_license:
            license_key = old_license['license_key']
            old_status = old_license['status']
            old_customer = old_license['customer_name']
            
            # Build update query
            if reset_device:
                cursor.execute('''
                    UPDATE licenses 
                    SET customer_name = ?, customer_email = ?, status = ?, 
                        expires_at = ?, max_devices = ?, features = ?, notes = ?,
                        device_id = NULL
                    WHERE id = ?
                ''', (customer_name, customer_email, status, expires_at, 
                      max_devices, json.dumps(features), notes, license_id))
            else:
                cursor.execute('''
                    UPDATE licenses 
                    SET customer_name = ?, customer_email = ?, status = ?, 
                        expires_at = ?, max_devices = ?, features = ?, notes = ?
                    WHERE id = ?
                ''', (customer_name, customer_email, status, expires_at, 
                      max_devices, json.dumps(features), notes, license_id))
            
            # Log the changes
            changes = []
            if old_customer != customer_name:
                changes.append(f'customer: {old_customer} → {customer_name}')
            if old_status != status:
                changes.append(f'status: {old_status} → {status}')
            if reset_device:
                changes.append('device binding reset')
            
            cursor.execute('''
                INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                license_key,
                'license_edited',
                request.remote_addr,
                f'Admin: {session.get("username")}',
                json.dumps({
                    'changes': changes,
                    'admin': session.get('username'),
                    'timestamp': datetime.now().isoformat()
                })
            ))
            
            conn.commit()
            flash(f'✅ License {license_key} updated successfully!', 'success')
        else:
            flash('❌ License not found!', 'error')
        
        conn.close()
        
    except Exception as e:
        flash(f'❌ Error updating license: {str(e)}', 'error')
        traceback.print_exc()
    
    return redirect(url_for('customers.manage_customers'))

@customers_bp.route('/delete_license/<int:license_id>', methods=['POST'])
@login_required
def delete_customer(license_id):
    """Delete a license and all associated data"""
    conn = None
    try:
        print(f"[DELETE] Starting deletion for license ID: {license_id}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # First, get the license key for logging and related deletions
        cursor.execute('SELECT license_key, customer_name FROM licenses WHERE id = ?', (license_id,))
        result = cursor.fetchone()
        
        if result:
            license_key = result['license_key']
            customer_name = result['customer_name']
            print(f"[DELETE] Found license: {license_key} for customer: {customer_name}")
            
            # Start transaction
            conn.execute('BEGIN TRANSACTION')
            
            # Delete from customizations table
            cursor.execute('DELETE FROM customizations WHERE license_key = ?', (license_key,))
            
            # Delete from license_logs table
            cursor.execute('DELETE FROM license_logs WHERE license_key = ?', (license_key,))
            
            # Finally, delete from licenses table
            cursor.execute('DELETE FROM licenses WHERE id = ?', (license_id,))
            
            # Commit the transaction
            conn.commit()
            
            flash(f'✅ Successfully deleted license {license_key}', 'success')
        else:
            flash('❌ License not found in database!', 'error')
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'❌ Error while deleting license: {str(e)}', 'error')
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('customers.manage_customers'))

@customers_bp.route('/unbind/<int:license_id>', methods=['POST'])
@login_required
def unbind_device(license_id):
    """Unbind hardware ID from a license"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get license info
        cursor.execute('SELECT license_key, device_id FROM licenses WHERE id = ?', (license_id,))
        result = cursor.fetchone()
        
        if result:
            license_key = result['license_key']
            
            # Unbind device
            cursor.execute('UPDATE licenses SET device_id = NULL WHERE id = ?', (license_id,))
            
            # Also clear any binding conflicts for this license
            cursor.execute('''
                DELETE FROM license_logs 
                WHERE license_key = ? AND action = 'binding_conflict'
            ''', (license_key,))
            
            conn.commit()
            flash(f'✅ Device unbound and conflicts cleared for license {license_key}', 'success')
        else:
            flash('❌ License not found!', 'error')
        
        conn.close()
    except Exception as e:
        flash(f'❌ Error unbinding device: {str(e)}', 'error')
    
    return redirect(url_for('customers.manage_customers'))