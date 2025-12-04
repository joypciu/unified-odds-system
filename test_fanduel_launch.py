#!/usr/bin/env python3
"""
Test script to launch FanDuel collector directly like run_unified_system.py does
"""

import subprocess
import sys
import os
import time

def test_fanduel_launch():
    """Test launching FanDuel collector like the unified system does"""

    base_dir = os.path.dirname(os.path.abspath(__file__))
    fanduel_dir = os.path.join(base_dir, "fanduel")

    print("Testing FanDuel collector launch...")
    print(f"Base dir: {base_dir}")
    print(f"FanDuel dir: {fanduel_dir}")

    # Check if files exist
    script_path = os.path.join(fanduel_dir, "fanduel_master_collector.py")
    if not os.path.exists(script_path):
        print(f"❌ FanDuel script not found: {script_path}")
        return

    print(f"✅ FanDuel script found: {script_path}")

    # Build command like run_unified_system.py does
    cmd = [sys.executable, "fanduel_master_collector.py", "5"]  # 5 minutes
    print(f"Command: {' '.join(cmd)}")

    # Clean environment
    env = os.environ.copy()
    env.pop('CHROMIUM_FLAGS', None)
    env.pop('CHROME_MEMORY_PRESSURE_THRESHOLD', None)

    print("Environment variables cleaned")

    try:
        print("Launching FanDuel collector...")
        process = subprocess.Popen(
            cmd,
            cwd=fanduel_dir,
            env=env,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print(f"✅ Process started with PID: {process.pid}")

        # Wait longer to see if Chrome launches and pages load
        print("Waiting 15 seconds for Chrome to launch and pages to load...")
        time.sleep(15)

        if process.poll() is None:
            print("✅ Process is still running after 15 seconds - Chrome likely launched successfully")
            print("Terminating process...")
            try:
                process.terminate()
                process.wait(timeout=10)
                print("✅ Process terminated successfully")
            except subprocess.TimeoutExpired:
                print("⚠️  Process didn't terminate cleanly, force killing...")
                process.kill()
                process.wait()
                print("✅ Process force killed")
        else:
            return_code = process.returncode
            print(f"⚠️  Process exited early with code: {return_code}")
            if return_code != 0:
                print("This indicates the FanDuel collector failed to run properly")

    except Exception as e:
        print(f"❌ Failed to launch: {e}")

if __name__ == "__main__":
    test_fanduel_launch()