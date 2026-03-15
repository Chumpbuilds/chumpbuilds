"""
X87 Player - License Device Binding Diagnostic and Fix Tool
Diagnoses and fixes device binding inconsistencies
Current Date and Time (UTC): 2025-11-22 22:03:33
Current User: covchump
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = '/opt/iptv-panel/iptv_business.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def diagnose_all_licenses():
    """Diagnose all licenses for binding issues"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        print("\n" + "="*80)
        print("🔍 LICENSE DEVICE BINDING DIAGNOSTIC REPORT")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
        
        # Get all licenses
        cursor.execute('''
            SELECT id, license_key, customer_name, status, device_id, last_used
            FROM licenses
            ORDER BY created_at DESC
        ''')
        licenses = cursor.fetchall()
        
        print(f"Total licenses in database: {len(licenses)}\n")
        
        issues_found = []
        
        for license in licenses:
            license_id = license['id']
            license_key = license['license_key']
            customer = license['customer_name']
            status = license['status']
            device_id = license['device_id']
            last_used = license['last_used']
            
            print(f"License ID: {license_id}")
            print(f"  Key: {license_key}")
            print(f"  Customer: {customer or 'Not assigned'}")
            print(f"  Status: {status}")
            
            # Check device binding
            if device_id:
                print(f"  Device ID: {device_id[:16]}... (LENGTH: {len(device_id)} chars)")
                print(f"  Binding Status: 🔗 BOUND")
                
                # Check for binding conflict logs
                cursor.execute('''
                    SELECT COUNT(*) as conflict_count
                    FROM license_logs
                    WHERE license_key = ? AND action = 'binding_conflict'
                ''', (license_key,))
                conflict_result = cursor.fetchone()
                conflict_count = conflict_result['conflict_count'] if conflict_result else 0
                
                if conflict_count > 0:
                    print(f"  ⚠️  BINDING CONFLICTS DETECTED: {conflict_count}")
                    issues_found.append({
                        'type': 'binding_conflict',
                        'license_key': license_key,
                        'conflict_count': conflict_count
                    })
                    
                    # Show recent conflicts
                    cursor.execute('''
                        SELECT action, timestamp, details
                        FROM license_logs
                        WHERE license_key = ? AND action = 'binding_conflict'
                        ORDER BY timestamp DESC
                        LIMIT 3
                    ''', (license_key,))
                    conflicts = cursor.fetchall()
                    for conf in conflicts:
                        try:
                            details = json.loads(conf['details']) if conf['details'] else {}
                            print(f"      - {conf['timestamp']}: Attempted={details.get('attempted_hardware_id', 'Unknown')[:16]}...")
                        except:
                            pass
            else:
                print(f"  Device ID: None")
                print(f"  Binding Status: ⭕ UNBOUND")
            
            print(f"  Last Used: {last_used or 'Never'}")
            print()
        
        conn.close()
        
        # Summary
        print("\n" + "="*80)
        print("📊 SUMMARY")
        print("="*80)
        bound_count = sum(1 for l in licenses if l['device_id'])
        unbound_count = len(licenses) - bound_count
        print(f"Bound licenses: {bound_count}")
        print(f"Unbound licenses: {unbound_count}")
        print(f"Issues found: {len(issues_found)}\n")
        
        if issues_found:
            print("⚠️  ISSUES DETECTED:")
            for issue in issues_found:
                if issue['type'] == 'binding_conflict':
                    print(f"  • {issue['license_key']}: {issue['conflict_count']} binding conflicts")
        
        return issues_found
        
    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        return []

def unbind_specific_license(license_key):
    """Unbind a specific license from all devices"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get current binding info
        cursor.execute('SELECT device_id FROM licenses WHERE license_key = ?', (license_key,))
        result = cursor.fetchone()
        
        if not result:
            print(f"❌ License not found: {license_key}")
            return False
        
        old_device_id = result['device_id']
        
        print(f"\n🔓 UNBINDING LICENSE: {license_key}")
        print(f"  Current binding: {old_device_id[:16] + '...' if old_device_id else 'None'}")
        
        # Unbind the license
        cursor.execute('''
            UPDATE licenses
            SET device_id = NULL, last_used = NULL
            WHERE license_key = ?
        ''', (license_key,))
        
        # Clear all binding conflict logs for this license
        cursor.execute('''
            DELETE FROM license_logs
            WHERE license_key = ? AND action = 'binding_conflict'
        ''', (license_key,))
        
        deleted_conflicts = cursor.rowcount
        
        # Log the admin unbind action
        cursor.execute('''
            INSERT INTO license_logs (license_key, action, ip_address, user_agent, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            license_key,
            'admin_force_unbind',
            '127.0.0.1',
            'Diagnostic Tool',
            json.dumps({
                'old_device_id': old_device_id,
                'reason': 'Admin diagnostic tool unbind',
                'timestamp': datetime.now().isoformat()
            })
        ))
        
        conn.commit()
        conn.close()
        
        print(f"  ✅ Successfully unbound")
        print(f"  ✅ Cleared {deleted_conflicts} binding conflict logs")
        return True
        
    except Exception as e:
        print(f"❌ Error unbinding license: {e}")
        return False

def unbind_all_bound_licenses():
    """Unbind ALL licenses from their devices"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all bound licenses
        cursor.execute('SELECT license_key FROM licenses WHERE device_id IS NOT NULL')
        bound_licenses = cursor.fetchall()
        
        if not bound_licenses:
            print("\n✅ No bound licenses found - nothing to unbind")
            return True
        
        print(f"\n⚠️  Found {len(bound_licenses)} bound licenses")
        confirm = input("Unbind ALL of them? (type 'yes' to confirm): ")
        
        if confirm.lower() != 'yes':
            print("Cancelled.")
            return False
        
        for license in bound_licenses:
            unbind_specific_license(license['license_key'])
        
        print("\n✅ All licenses have been unbound!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def clear_binding_conflicts(license_key):
    """Clear binding conflict logs for a specific license"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            DELETE FROM license_logs
            WHERE license_key = ? AND action = 'binding_conflict'
        ''', (license_key,))
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        print(f"✅ Cleared {deleted} binding conflict logs for {license_key}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main menu"""
    while True:
        print("\n" + "="*80)
        print("X87 LICENSE DEVICE BINDING TOOL")
        print("="*80)
        print("1. 🔍 Diagnose all licenses")
        print("2. 🔓 Unbind specific license")
        print("3. 🔓🔓 Unbind ALL licenses")
        print("4. 🧹 Clear binding conflicts for a license")
        print("5. ❌ Exit")
        print("="*80)
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == '1':
            diagnose_all_licenses()
        
        elif choice == '2':
            license_key = input("\nEnter license key to unbind: ").strip().upper()
            if license_key:
                unbind_specific_license(license_key)
        
        elif choice == '3':
            unbind_all_bound_licenses()
        
        elif choice == '4':
            license_key = input("\nEnter license key: ").strip().upper()
            if license_key:
                clear_binding_conflicts(license_key)
        
        elif choice == '5':
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid option")

if __name__ == '__main__':
    print("\n" + "="*80)
    print("🔐 X87 PLAYER - LICENSE DEVICE BINDING DIAGNOSTIC & FIX TOOL")
    print("="*80)
    print("This tool helps diagnose and fix device binding issues\n")
    
    main()