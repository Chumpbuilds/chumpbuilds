"""
X87 Player - API Module
Handles all API endpoints for license validation and other operations
FIXED: Now fetches 'customizations' (Branding) from DB and sends to client
UPDATED: Strict multi-device binding enforcement using license_devices table
"""

from flask import Blueprint, request, jsonify
from admin_database import get_db_connection
from datetime import datetime
import json
import os
import traceback

api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/license/validate', methods=['POST'])
def validate_license():
    """Validate license key with hardware binding"""
    try:
        data = request.get_json()
        if not data or 'license_key' not in data:
            return jsonify({'success': False, 'message': 'License key required'}), 200
        
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        app_version = data.get('app_version', '')
        platform = data.get('platform', '')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM licenses WHERE license_key = ?', (license_key,))
        license_data = cursor.fetchone()
        
        if not license_data:
            conn.close()
            return jsonify({'success': False, 'message': 'Invalid license key'}), 200
        
        if license_data['status'] != 'active':
            conn.close()
            return jsonify({'success': False, 'message': f'License is {license_data["status"]}'}), 200

        # Check expiry
        if license_data['expires_at']:
            try:
                expires_str = license_data['expires_at']
                if 'T' in expires_str:
                    expiry_date = datetime.strptime(expires_str[:19], '%Y-%m-%dT%H:%M:%S')
                else:
                    expiry_date = datetime.strptime(expires_str, '%Y-%m-%d %H:%M:%S')
                if expiry_date < datetime.now():
                    conn.close()
                    return jsonify({'success': False, 'message': 'License has expired'}), 200
            except Exception:
                pass

        # --- Multi-device binding enforcement ---
        if hardware_id:
            max_devices = license_data['max_devices'] if license_data['max_devices'] is not None else 3

            # Check if this device is already bound
            cursor.execute(
                'SELECT id FROM license_devices WHERE license_key = ? AND device_id = ?',
                (license_key, hardware_id)
            )
            existing_device = cursor.fetchone()

            if existing_device:
                # Device already bound — update last_used
                cursor.execute(
                    'UPDATE license_devices SET last_used = CURRENT_TIMESTAMP WHERE id = ?',
                    (existing_device['id'],)
                )
            else:
                # New device — check if limit is reached
                cursor.execute(
                    'SELECT COUNT(*) as cnt FROM license_devices WHERE license_key = ?',
                    (license_key,)
                )
                device_count = cursor.fetchone()['cnt']

                if device_count >= max_devices:
                    conn.close()
                    return jsonify({
                        'success': False,
                        'message': (
                            f'Device limit reached ({device_count}/{max_devices}). '
                            'Unbind a device from your portal or purchase additional device slots.'
                        )
                    }), 200

                # Auto-bind the new device
                cursor.execute(
                    '''INSERT INTO license_devices (license_key, device_id, platform)
                       VALUES (?, ?, ?)''',
                    (license_key, hardware_id, platform or None)
                )
                # Also keep legacy device_id column in sync (first device only)
                if device_count == 0:
                    cursor.execute(
                        'UPDATE licenses SET device_id = ? WHERE license_key = ?',
                        (hardware_id, license_key)
                    )

            cursor.execute(
                'UPDATE licenses SET last_used = CURRENT_TIMESTAMP WHERE license_key = ?',
                (license_key,)
            )
        else:
            cursor.execute(
                'UPDATE licenses SET last_used = CURRENT_TIMESTAMP WHERE license_key = ?',
                (license_key,)
            )

        conn.commit()
        
        # --- 1. FETCH CLOUD PROFILES ---
        cursor.execute('SELECT profile_name, dns_url FROM license_profiles WHERE license_key = ? ORDER BY created_at ASC', (license_key,))
        profile_rows = cursor.fetchall()
        cloud_profiles = [{'name': row['profile_name'], 'url': row['dns_url']} for row in profile_rows]
        
        # --- 2. FETCH CUSTOMIZATIONS (BRANDING) ---
        cursor.execute('SELECT app_name, logo_url, theme, primary_color, secondary_color FROM customizations WHERE license_key = ?', (license_key,))
        cust_row = cursor.fetchone()
        
        user_settings = {}
        if cust_row:
            logo = cust_row['logo_url'] or ''
            # Backward compatibility: convert legacy relative paths to absolute URLs so
            # the client (which only fetches http/https URLs) can display the logo.
            if logo and not logo.startswith(('http://', 'https://')):
                portal_base = os.environ.get('PORTAL_PUBLIC_BASE_URL', '').rstrip('/')
                if portal_base:
                    logo = f"{portal_base}/{logo.lstrip('/')}"
                else:
                    logo = ''
            # Convert SQLite row to dict
            user_settings = {
                'app_name': cust_row['app_name'],
                'logo_url': logo,
                'theme': cust_row['theme'],
                'primary_color': cust_row['primary_color'],
                'accent_color': cust_row['secondary_color']
            }
        # ------------------------------------------
        
        # --- FETCH SETTINGS ---
        cursor.execute("SELECT value FROM settings WHERE key='latest_version'")
        ver = cursor.fetchone()
        latest_ver = ver['value'] if ver else '1.0.0'
        
        cursor.execute("SELECT value FROM settings WHERE key='update_url'")
        u_url = cursor.fetchone()
        update_url = u_url['value'] if u_url else ''
        
        features = json.loads(license_data['features'] if license_data['features'] else '{}')
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'License valid',
            'customer_name': license_data['customer_name'],
            'features': features,
            'latest_version': latest_ver,
            'update_url': update_url,
            'cloud_profiles': cloud_profiles,
            'user_settings': user_settings  # NOW SENDING BRANDING DATA
        }), 200
        
    except Exception as e:
        print(f"[API Error] {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 200