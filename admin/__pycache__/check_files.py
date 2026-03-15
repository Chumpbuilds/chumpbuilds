import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
print(f"Current directory: {current_dir}")

files_to_check = [
    'admin_customers.py',
    'admin_customers_template.py',
    'admin_database.py',
    'admin_auth.py',
    'admin_app.py'
]

print("\nChecking files:")
for file in files_to_check:
    filepath = os.path.join(current_dir, file)
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        print(f"✅ {file} exists (size: {size} bytes)")
    else:
        print(f"❌ {file} NOT FOUND")

print("\nTrying to import admin_customers_template...")
try:
    sys.path.insert(0, current_dir)
    from admin_customers_template import CUSTOMER_TEMPLATE
    print("✅ Import successful!")
    print(f"Template length: {len(CUSTOMER_TEMPLATE)} characters")
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
