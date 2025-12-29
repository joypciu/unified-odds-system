#!/usr/bin/env python3
"""
Quick Launcher for Parallel OddsMagnet Scraper
Use this to quickly start scraping all sports in parallel
"""

import sys
import subprocess
from pathlib import Path

def main():
    script_dir = Path(__file__).parent
    scraper_script = script_dir / "parallel_sports_scraper.py"
    
    print("="*60)
    print("🚀 PARALLEL ODDSMAGNET SCRAPER")
    print("="*60)
    print()
    print("Choose an option:")
    print("  1. Run ONCE (scrape all sports, then exit)")
    print("  2. Run CONTINUOUS (scrape every 60s)")
    print("  3. Run CONTINUOUS FAST (scrape every 30s)")
    print("  4. Run FOOTBALL ONLY (continuous)")
    print("  5. Run CUSTOM")
    print()
    
    choice = input("Enter choice (1-5): ").strip()
    
    if choice == "1":
        # Single run
        print("\n▶️  Running single scrape...")
        subprocess.run([sys.executable, str(scraper_script), "--mode", "local"])
    
    elif choice == "2":
        # Continuous 60s
        print("\n▶️  Running continuous scraper (60s interval)...")
        print("   Press Ctrl+C to stop")
        subprocess.run([sys.executable, str(scraper_script), "--mode", "local", "--continuous", "--interval", "60"])
    
    elif choice == "3":
        # Continuous 30s
        print("\n▶️  Running continuous scraper (30s interval)...")
        print("   Press Ctrl+C to stop")
        subprocess.run([sys.executable, str(scraper_script), "--mode", "local", "--continuous", "--interval", "30"])
    
    elif choice == "4":
        # Football only
        print("\n▶️  Running FOOTBALL only (continuous)...")
        print("   Press Ctrl+C to stop")
        subprocess.run([sys.executable, str(scraper_script), "--mode", "local", "--continuous", "--sports", "football"])
    
    elif choice == "5":
        # Custom
        print("\nAvailable sports: football, basketball, tennis, american-football, table-tennis")
        sports = input("Enter sports (space-separated): ").strip().split()
        interval = input("Enter interval in seconds (default 60): ").strip() or "60"
        
        cmd = [sys.executable, str(scraper_script), "--mode", "local", "--continuous", "--interval", interval]
        if sports:
            cmd.extend(["--sports"] + sports)
        
        print(f"\n▶️  Running custom scraper...")
        print("   Press Ctrl+C to stop")
        subprocess.run(cmd)
    
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
