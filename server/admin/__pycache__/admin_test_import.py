"""
Test script to check if the import is working
Current Date and Time (UTC): 2025-11-22 09:08:04
Current User: covchump
"""

import sys
import os

# Add the admin directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from admin_customers_template import CUSTOMER_TEMPLATE
    print("✅ Template imported successfully")
    print(f"Template length: {len(CUSTOMER_TEMPLATE)} characters")
except ImportError as e:
    print(f"❌ Import failed: {e}")
except SyntaxError as e:
    print(f"❌ Syntax error in template: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")