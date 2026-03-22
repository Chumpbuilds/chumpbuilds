"""
Enhanced License Manager - Complete Version 2.1.0
Handles partial license key matching for desktop app
Includes Force 200 OK fix for desktop app compatibility
Current Date and Time (UTC): 2025-11-21 21:52:15
Current User: covchump
"""

import sqlite3
import json
from datetime import datetime, timedelta
from flask import request, jsonify, Blueprint
import hashlib
import os
import logging

# Create blueprint for license management
license_bp = Blueprint('license', __name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection"""
    db_path = '/opt/iptv-panel/iptv_business.db'
    if not os.path.exists(db_path):
        raise Exception(f"Database not found: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def normalize_license_key(license_key):
    """Enhanced normalize license key to handle partial matches"""
    if not license_key:
        return []
    
    # Clean the input
    clean_key = license_key.replace('-', '').replace(' ', '').strip().upper()
    
    # Generate different possible formats
    formats = [
        license_key.strip(),  # Original format
        clean_key,           # No dashes
    ]
    
    # If we have enough characters, try to add dashes in X87-XXXX-XXXX-XXXX format
    if len(clean_key) >= 7:
        if clean_key.startswith('X87'):
            if len(clean_key) >= 15:
                formatted = f"X87-{clean_key[3:7]}-{clean_key[7:11]}-{clean_key[11:15]}"
                formats.append(formatted)
            elif len(clean_key) >= 11:
                formatted = f"X87-{clean_key[3:7]}-{clean_key[7:11]}"
                formats.append(formatted)
    
    # Remove duplicates while preserving order
    unique_formats = []
    for fmt in formats:
        if fmt not in unique_formats:
            unique_formats.append(fmt)
    
    return unique_formats

def find_license_in_database(license_key):
    """Enhanced find license with IMPROVED partial matching"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all possible formats of the license key
        possible_keys = normalize_license_key(license_key)
        
        logger.info(f"[License] Searching for license with formats: {possible_keys}")
        
        # First try exact matches
        for key_format in possible_keys:
            # logger.info(f"[License] Trying exact match: {key_format}")
            
            cursor.execute("""
                SELECT l.*, c.username, c.email as customer_email_alt
                FROM licenses l 
                LEFT JOIN customers c ON l.customer_name = c.username 
                WHERE l.license_key = ? AND l.status = 'active'
            """, (key_format,))
            
            license_data = cursor.fetchone()
            if license_data:
                logger.info(f"[License] ✅ Found exact match: {key_format}")
                conn.close()
                return license_data
        
        # ENHANCED: If no exact match, try partial matching for 8+ character keys starting with X87
        clean_key = license_key.replace('-', '').replace(' ', '').strip().upper()
        if len(clean_key) >= 8 and clean_key.startswith('X87'):
            logger.info(f"[License] Trying partial match for: {clean_key}")
            
            # Try different partial matching strategies
            partial_patterns = [
                f"{clean_key}%",           # X87IL4AJ% -> X87IL4AJ56Q0TXF
                f"{clean_key[:8]}%",       # First 8 chars
            ]
            
            for pattern in partial_patterns:
                # logger.info(f"[License] Trying partial pattern: {pattern}")
                
                cursor.execute("""
                    SELECT l.*, c.username, c.email as customer_email_alt
                    FROM licenses l 
                    LEFT JOIN customers c ON l.customer_name = c.username 
                    WHERE REPLACE(REPLACE(l.license_key, '-', ''), ' ', '') LIKE ? AND l.status = 'active'
                    LIMIT 1
                """, (pattern,))
                
                partial_match = cursor.fetchone()
                if partial_match:
                    logger.info(f"[License] ✅ Found partial match: {partial_match['license_key']} with pattern: {pattern}")
                    conn.close()
                    return partial_match
        
        conn.close()
        logger.warning(f"[License] No license found for: {license_key}")
        return None
        
    except Exception as e:
        logger.error(f"[License] Database search error: {e}")
        return None

def is_valid_license(license_key, hardware_id=None):
    """Check if license key is valid and active"""
    try:
        license_data = find_license_in_database(license_key)
        
        if not license_data:
            logger.warning(f"[License] License key not found: {license_key}")
            return False, "License key not found"
        
        logger.info(f"[License] Found license for: {license_data['customer_name']}")
        
        # Check if license is active
        if license_data['status'] != 'active':
            logger.warning(f"[License] License status not active: {license_data['status']}")
            return False, f"License is not active (status: {license_data['status']})"
        
        # Check expiry date
        if license_data['expires_at']:
            try:
                expiry_date = datetime.fromisoformat(license_data['expires_at'])
                if expiry_date < datetime.now():
                    logger.warning(f"[License] License expired: {license_data['expires_at']}")
                    return False, f"License has expired on {license_data['expires_at']}"
            except Exception as e:
                logger.error(f"[License] Error parsing expiry date: {e}")
        
        # Handle hardware binding using license_devices table
        if hardware_id:
            max_devices = license_data.get('max_devices') if license_data.get('max_devices') is not None else 3

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # Check if this device is already bound
                cursor.execute(
                    'SELECT id FROM license_devices WHERE license_key = ? AND device_id = ?',
                    (license_data['license_key'], hardware_id)
                )
                existing_device = cursor.fetchone()

                if existing_device:
                    # Device already bound — update last_used
                    cursor.execute(
                        'UPDATE license_devices SET last_used = CURRENT_TIMESTAMP WHERE id = ?',
                        (existing_device['id'],)
                    )
                    cursor.execute(
                        'UPDATE licenses SET last_used = ?, app_version = ? WHERE license_key = ?',
                        (datetime.now().isoformat(), '1.0.0', license_data['license_key'])
                    )
                    conn.commit()
                    logger.info(f"[License] Device already bound, updated last_used")
                else:
                    # New device — check if limit is reached
                    cursor.execute(
                        'SELECT COUNT(*) as cnt FROM license_devices WHERE license_key = ?',
                        (license_data['license_key'],)
                    )
                    device_count = cursor.fetchone()['cnt']

                    if device_count >= max_devices:
                        conn.close()
                        logger.warning(
                            f"[License] Device limit reached ({device_count}/{max_devices}) "
                            f"for license {license_data['license_key']}"
                        )
                        return False, (
                            f"Device limit reached ({device_count}/{max_devices}). "
                            "Unbind a device from your portal or purchase additional device slots."
                        )

                    # Auto-bind the new device
                    cursor.execute(
                        '''INSERT INTO license_devices (license_key, device_id)
                           VALUES (?, ?)''',
                        (license_data['license_key'], hardware_id)
                    )
                    # Keep legacy device_id in sync for first device
                    if device_count == 0:
                        cursor.execute(
                            'UPDATE licenses SET device_id = ?, last_used = ?, app_version = ? WHERE license_key = ?',
                            (hardware_id, datetime.now().isoformat(), '1.0.0', license_data['license_key'])
                        )
                    else:
                        cursor.execute(
                            'UPDATE licenses SET last_used = ?, app_version = ? WHERE license_key = ?',
                            (datetime.now().isoformat(), '1.0.0', license_data['license_key'])
                        )
                    conn.commit()
                    logger.info(f"[License] New device auto-bound ({device_count + 1}/{max_devices})")
            finally:
                conn.close()
        
        return True, license_data
        
    except Exception as e:
        logger.error(f"[License] Validation error: {e}")
        return False, f"Database error: {str(e)}"

def get_user_settings(license_key):
    """Get user customization settings from license"""
    try:
        license_data = find_license_in_database(license_key)
        
        if license_data:
            # Parse features from the license
            enabled_features = {
                'live_tv': True,
                'movies': True,
                'search': True,
                'epg': True,
                'series': True,
                'favorites': True,
                'downloads': True,
                'quality_selection': True
            }
            
            if license_data['features']:
                try:
                    features_from_db = json.loads(license_data['features'])
                    if isinstance(features_from_db, dict):
                        enabled_features.update(features_from_db)
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"[License] Could not parse features JSON: {e}")
            
            # Calculate days remaining
            days_remaining = 0
            if license_data['expires_at']:
                try:
                    expiry_date = datetime.fromisoformat(license_data['expires_at'])
                    days_remaining = max(0, (expiry_date - datetime.now()).days)
                except Exception as e:
                    logger.error(f"[License] Error calculating days remaining: {e}")
            
            # Query customizations table for portal-configured branding
            theme = 'dark'
            app_name = 'X87 Player'
            primary_color = '#0d7377'
            accent_color = '#64b5f6'
            logo_url = ''
            try:
                conn = get_db_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        'SELECT app_name, logo_url, theme, primary_color, secondary_color FROM customizations WHERE license_key = ?',
                        (license_data['license_key'],)
                    )
                    cust_row = cursor.fetchone()
                finally:
                    conn.close()
                if cust_row:
                    app_name = cust_row['app_name'] or app_name
                    logo_url = cust_row['logo_url'] or logo_url
                    theme = cust_row['theme'] or theme
                    primary_color = cust_row['primary_color'] or primary_color
                    accent_color = cust_row['secondary_color'] or accent_color
            except Exception as e:
                logger.warning(f"[License] Could not read customizations: {e}")

            return {
                'theme': theme,
                'app_name': app_name,
                'primary_color': primary_color,
                'accent_color': accent_color,
                'logo_url': logo_url,
                'background_image': '',
                'enabled_features': enabled_features,
                'plan_type': 'premium',
                'username': license_data['customer_name'],
                'email': license_data['customer_email'] if 'customer_email' in license_data.keys() else '',
                'language': 'en',
                'timezone': 'UTC',
                'quality_preference': 'auto',
                'max_devices': license_data.get('max_devices', 1),
                'expires_at': license_data.get('expires_at', ''),
                'days_remaining': days_remaining,
                'license_key_display': license_data['license_key'][:12] + '...'
            }
    except Exception as e:
        logger.error(f"[License] Error getting settings: {e}")
    
    return {}

def save_user_settings(license_key, settings):
    """Save user customization settings"""
    try:
        license_data = find_license_in_database(license_key)
        if not license_data:
            return False
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update any features if provided
        if 'enabled_features' in settings:
            current_features = {}
            if license_data['features']:
                try:
                    current_features = json.loads(license_data['features'])
                except:
                    pass
            
            # Merge new features with existing
            current_features.update(settings['enabled_features'])
            
            cursor.execute("""
                UPDATE licenses 
                SET features = ?
                WHERE license_key = ?
            """, (json.dumps(current_features), license_data['license_key']))
            
            conn.commit()
            logger.info(f"[License] Updated features for license: {license_key[:8]}...")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"[License] Error saving settings: {e}")
        return False

@license_bp.route('/api/license/validate', methods=['POST'])
def validate_license():
    """
    Validate app license key.
    CRITICAL: Always returns HTTP 200 OK, even for failures.
    This ensures the desktop app reads the 'message' field instead of 
    treating 400/404/500 codes as generic connection errors.
    """
    try:
        logger.info("[License] 🔑 License validation request received")
        data = request.get_json()
        
        if not data:
            logger.warning("[License] No JSON data received")
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 200  # FORCE 200 OK
        
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        app_version = data.get('app_version', '1.0.0')
        platform_info = data.get('platform', 'Unknown')
        
        logger.info(f"[License] Validating license: {license_key[:8]}... for hardware: {hardware_id[:16]}...")
        
        if not license_key:
            return jsonify({
                'success': False,
                'message': 'License key is required'
            }), 200  # FORCE 200 OK
        
        # Enhanced validation with improved partial key support
        is_valid, result = is_valid_license(license_key, hardware_id)
        
        if is_valid:
            # Parse features from license
            enabled_features = {
                'live_tv': True,
                'movies': True,
                'search': True,
                'epg': True,
                'series': True,
                'favorites': True,
                'downloads': True,
                'quality_selection': True
            }
            
            if result['features']:
                try:
                    features_from_db = json.loads(result['features'])
                    if isinstance(features_from_db, dict):
                        enabled_features.update(features_from_db)
                except:
                    pass
            
            user_settings = {
                'theme': 'dark',
                'app_name': 'X87 Player',
                'primary_color': '#0d7377',
                'secondary_color': '#64b5f6',
                'enabled_features': enabled_features
            }
            
            logger.info(f"[License] ✅ Validation successful for: {license_key[:8]}... (Customer: {result['customer_name']})")
            
            response_data = {
                'success': True,
                'message': 'License valid',
                'user_settings': user_settings,
                'customer_name': result['customer_name'],
                'expires_at': result['expires_at'],
                'features': enabled_features,
                'license_info': {
                    'key': license_key[:8] + '...',
                    'customer_name': result['customer_name'],
                    'expires_at': result['expires_at'],
                    'full_license_key': result['license_key']  # Return the full license key found
                }
            }
            
            return jsonify(response_data), 200
        else:
            logger.warning(f"[License] ❌ Validation failed for {license_key[:8]}...: {result}")
            return jsonify({
                'success': False,
                'message': result  # This contains the error message string
            }), 200  # FORCE 200 OK - Critical Fix
            
    except Exception as e:
        logger.error(f"[License] Validation API error: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 200  # FORCE 200 OK

@license_bp.route('/api/settings/update', methods=['POST'])
def update_user_settings_api():
    """Update user's app settings"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'message': 'No data provided'
            }), 200
        
        license_key = data.get('license_key', '').strip()
        settings = data.get('settings', {})
        hardware_id = data.get('hardware_id', '').strip()
        
        if not license_key:
            return jsonify({
                'success': False,
                'message': 'License key is required'
            }), 200
        
        # Validate license first
        is_valid, result = is_valid_license(license_key, hardware_id)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': result
            }), 200
        
        # Save settings
        if save_user_settings(license_key, settings):
            logger.info(f"[License] Settings updated for: {license_key[:8]}...")
            return jsonify({
                'success': True,
                'message': 'Settings updated successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Failed to update settings'
            }), 200
            
    except Exception as e:
        logger.error(f"[License] Settings update error: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 200

@license_bp.route('/api/settings/get', methods=['POST'])
def get_user_settings_api():
    """Get user settings"""
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        hardware_id = data.get('hardware_id', '').strip()
        
        if not license_key:
            return jsonify({
                'success': False,
                'message': 'License key is required'
            }), 200
        
        # Validate license first
        is_valid, result = is_valid_license(license_key, hardware_id)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': result
            }), 200
        
        settings = get_user_settings(license_key)
        
        return jsonify({
            'success': True,
            'settings': settings
        }), 200
        
    except Exception as e:
        logger.error(f"[License] Settings get error: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 200

@license_bp.route('/api/license/info', methods=['POST'])
def get_license_info():
    """Get detailed license information"""
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        
        if not license_key:
            return jsonify({
                'success': False,
                'message': 'License key is required'
            }), 200
        
        # Get license info
        is_valid, result = is_valid_license(license_key)
        
        if is_valid and isinstance(result, sqlite3.Row):
            license_data = result
            
            # Calculate days remaining
            days_remaining = 0
            if license_data['expires_at']:
                try:
                    expiry_date = datetime.fromisoformat(license_data['expires_at'])
                    days_remaining = max(0, (expiry_date - datetime.now()).days)
                except:
                    pass
            
            return jsonify({
                'success': True,
                'license_info': {
                    'license_key': license_key[:8] + '...',
                    'full_license_key': license_data['license_key'],
                    'customer_name': license_data['customer_name'],
                    'customer_email': license_data['customer_email'] if 'customer_email' in license_data.keys() else '',
                    'status': license_data['status'],
                    'created_at': license_data['created_at'],
                    'expires_at': license_data['expires_at'],
                    'days_remaining': days_remaining,
                    'last_used': license_data['last_used'],
                    'device_id': license_data['device_id'][:16] + '...' if license_data['device_id'] else 'Not bound',
                    'app_version': license_data['app_version'],
                    'max_devices': license_data['max_devices'],
                    'notes': license_data['notes'],
                    'features': json.loads(license_data['features']) if license_data['features'] else {},
                    'is_valid': True
                }
            }), 200
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid license key',
                'license_info': {
                    'license_key': license_key[:8] + '...',
                    'is_valid': False
                }
            }), 200
            
    except Exception as e:
        logger.error(f"[License] License info error: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 200

@license_bp.route('/api/license/debug/<license_key>', methods=['GET'])
def debug_license(license_key):
    """Debug endpoint to help troubleshoot license issues - ENHANCED"""
    try:
        # Get all possible formats
        possible_formats = normalize_license_key(license_key)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check each format
        results = {}
        for fmt in possible_formats:
            cursor.execute("SELECT license_key, customer_name, status FROM licenses WHERE license_key = ?", (fmt,))
            result = cursor.fetchone()
            results[fmt] = {
                'found': bool(result),
                'license_key': result['license_key'] if result else 'Not found',
                'customer': result['customer_name'] if result else 'N/A',
                'status': result['status'] if result else 'N/A'
            }
        
        # Enhanced partial matching test
        partial_results = {}
        clean_key = license_key.replace('-', '').replace(' ', '').strip().upper()
        if len(clean_key) >= 6 and clean_key.startswith('X87'):
            patterns = [f"{clean_key}%", f"{clean_key[:8]}%"]
            
            for pattern in patterns:
                cursor.execute("""
                    SELECT license_key, customer_name, status 
                    FROM licenses 
                    WHERE UPPER(REPLACE(REPLACE(license_key, '-', ''), ' ', '')) LIKE ? AND status = 'active'
                """, (pattern,))
                
                partial_matches = cursor.fetchall()
                partial_results[pattern] = []
                for match in partial_matches:
                    partial_results[pattern].append({
                        'license_key': match['license_key'],
                        'customer': match['customer_name'],
                        'status': match['status']
                    })
        
        # Get all licenses for comparison
        cursor.execute("SELECT license_key, customer_name FROM licenses ORDER BY created_at DESC")
        all_licenses = []
        for row in cursor.fetchall():
            clean_db_key = row[0].replace('-', '').replace(' ', '').strip().upper()
            all_licenses.append({
                'key': row[0],
                'clean_key': clean_db_key,
                'customer': row[1],
                'matches_input': clean_db_key.startswith(clean_key) if len(clean_key) >= 6 else False
            })
        
        conn.close()
        
        return jsonify({
            'input_key': license_key,
            'input_length': len(license_key),
            'clean_input_key': clean_key,
            'normalized_formats': possible_formats,
            'exact_match_results': results,
            'partial_match_results': partial_results,
            'enhanced_partial_matching': len(clean_key) >= 6 and clean_key.startswith('X87'),
            'all_licenses_in_db': all_licenses,
            'debug_info': {
                'timestamp': datetime.now().isoformat(),
                'patterns_tested': [f"{clean_key}%", f"{clean_key[:8]}%"] if len(clean_key) >= 6 else []
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e), 'timestamp': datetime.now().isoformat()}), 200

@license_bp.route('/api/license/test', methods=['GET'])
def test_license_api():
    """Test endpoint to verify API is working"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = [row[0] for row in cursor.fetchall()]
        
        cursor.execute("SELECT COUNT(*) FROM licenses")
        license_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM licenses WHERE status = 'active'")
        active_license_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM customers")
        customer_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT license_key, customer_name, status, expires_at FROM licenses LIMIT 5")
        sample_licenses = []
        for row in cursor.fetchall():
            sample_licenses.append({
                'key': row[0][:8] + '...',
                'customer': row[1],
                'status': row[2],
                'expires_at': row[3]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'License API is working with proper database connection',
            'timestamp': datetime.now().isoformat(),
            'database_info': {
                'all_tables': tables,
                'total_licenses': license_count,
                'active_licenses': active_license_count,
                'total_customers': customer_count,
                'sample_licenses': sample_licenses
            },
            'endpoints': [
                'GET  /api/license/test',
                'GET  /api/license/health', 
                'POST /api/license/validate',
                'POST /api/license/info',
                'POST /api/settings/get',
                'POST /api/settings/update',
                'GET  /api/license/debug/<key>'
            ],
            'features': [
                'Enhanced license key normalization (handles dashes and partials)',
                'IMPROVED partial key matching (6+ character support)',
                'Flexible pattern matching',
                'Hardware ID binding',
                'Expiry date validation', 
                'Feature management',
                'Multi-device support',
                'Usage tracking',
                'Enhanced error handling'
            ],
            'version': '2.1.1'
        }), 200
    except Exception as e:
        logger.error(f"[License] Test endpoint error: {e}")
        return jsonify({
            'success': False,
            'message': f'Database error: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 200

@license_bp.route('/api/license/health', methods=['GET'])
def license_health():
    """Health check for license service"""
    return jsonify({
        'status': 'healthy',
        'service': 'license_manager',
        'timestamp': datetime.now().isoformat(),
        'version': '2.1.1',
        'database': '/opt/iptv-panel/iptv_business.db',
        'features': ['improved_partial_key_matching', 'flexible_pattern_matching', 'enhanced_normalization', 'hardware_binding', 'force_200_ok']
    }), 200

# Export the blueprint
__all__ = ['license_bp']