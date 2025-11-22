#!/usr/bin/env python3
"""
Simple test script to check email configuration
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_unified_system import AlertSystem

def test_email_config():
    print("Testing email configuration...")
    print("Current working directory:", os.getcwd())
    print("Config file exists:", os.path.exists('config.json'))

    try:
        print("Initializing AlertSystem...")
        alert_system = AlertSystem()
        print("✓ AlertSystem initialized successfully")

        print("Sending test alert...")
        # Test sending an alert
        alert_system.send_alert(
            module_name="test",
            error_type="TEST",
            message="This is a test alert",
            details="Testing email configuration"
        )
        print("✓ Test alert sent")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_email_config()