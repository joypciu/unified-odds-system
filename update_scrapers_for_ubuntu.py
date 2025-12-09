#!/usr/bin/env python3
"""
Update Scrapers to Use chrome_helper for Cross-Platform Support

This script updates bet365 and fanduel scrapers to use the chrome_helper module
for cross-platform Chrome browser support (Windows and Ubuntu).

Usage:
    python update_scrapers_for_ubuntu.py [--dry-run]
    
Options:
    --dry-run    Show what would be changed without making changes
"""

import sys
import os
from pathlib import Path
import argparse

def show_instructions():
    """Show manual update instructions for files that need attention"""
    print("\n" + "="*70)
    print("📝 MANUAL UPDATE REQUIRED FOR SOME FILES")
    print("="*70)
    
    print("\n🔧 The following scrapers use direct Chrome launching:")
    print("   These need to be updated to use chrome_helper.py\n")
    
    print("📁 bet365/bet365_pregame_homepage_scraper.py")
    print("   Currently uses: playwright.chromium.launch()")
    print("   Update to:")
    print("   ```python")
    print("   from chrome_helper import setup_chrome_browser")
    print("   ")
    print("   # Replace browser launch with:")
    print("   browser, chrome_manager = await setup_chrome_browser(playwright)")
    print("   if not browser:")
    print("       logger.error('Failed to setup Chrome')")
    print("       return False")
    print("   ```\n")
    
    print("📁 fanduel/fanduel_master_collector.py")
    print("   Currently uses: playwright.chromium.connect_over_cdp()")
    print("   This is CORRECT for FanDuel - it connects to an existing Chrome instance")
    print("   ✅ No changes needed (Chrome is launched by run_unified_system.py)\n")
    
    print("📁 fanduel/fanduel_live_monitor.py")
    print("   Currently uses: playwright.chromium.connect_over_cdp()")
    print("   ✅ No changes needed (Chrome is launched by run_unified_system.py)\n")
    
    print("📁 fanduel/fanduel_future_collector.py")
    print("   Currently uses: playwright.chromium.connect_over_cdp()")
    print("   ✅ No changes needed (Chrome is launched by run_unified_system.py)\n")
    
    print("📁 bet365/bet365_live_scraper.py")
    print("   Currently uses: playwright.chromium.connect_over_cdp()")
    print("   ✅ No changes needed (Chrome is launched by bet365_live_concurrent_scraper.py)\n")
    
    print("="*70)
    print("💡 KEY POINTS:")
    print("="*70)
    print("1. ✅ chrome_helper.py has been added to the project root")
    print("2. ✅ It automatically detects Windows vs Ubuntu")
    print("3. ✅ On Ubuntu, it uses /usr/bin/google-chrome-stable")
    print("4. ✅ On Windows, it uses C:\\Program Files\\Google\\Chrome\\...")
    print("5. ⚠️  Scrapers that use .connect_over_cdp() are fine")
    print("6. ⚠️  Only scrapers that use .launch() need updating")
    print("7. ✅ The systemd service uses xvfb-run for virtual display")
    print("\n")

def check_scraper_patterns():
    """Check for patterns in scrapers that might need updating"""
    print("\n" + "="*70)
    print("🔍 ANALYZING SCRAPERS")
    print("="*70 + "\n")
    
    project_root = Path(__file__).parent
    
    patterns = {
        'launch': 'playwright.chromium.launch(',
        'connect_cdp': 'playwright.chromium.connect_over_cdp(',
        'chrome_helper': 'from chrome_helper import',
    }
    
    findings = {
        'needs_update': [],
        'uses_cdp': [],
        'already_updated': [],
    }
    
    # Check bet365 scrapers
    bet365_dir = project_root / 'bet365'
    if bet365_dir.exists():
        for py_file in bet365_dir.glob('*.py'):
            if py_file.name.startswith('__'):
                continue
                
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            
            has_helper = patterns['chrome_helper'] in content
            has_launch = patterns['launch'] in content
            has_cdp = patterns['connect_cdp'] in content
            
            if has_helper:
                findings['already_updated'].append(str(py_file.relative_to(project_root)))
            elif has_launch:
                findings['needs_update'].append(str(py_file.relative_to(project_root)))
            elif has_cdp:
                findings['uses_cdp'].append(str(py_file.relative_to(project_root)))
    
    # Check fanduel scrapers
    fanduel_dir = project_root / 'fanduel'
    if fanduel_dir.exists():
        for py_file in fanduel_dir.glob('*.py'):
            if py_file.name.startswith('__'):
                continue
                
            content = py_file.read_text(encoding='utf-8', errors='ignore')
            
            has_helper = patterns['chrome_helper'] in content
            has_launch = patterns['launch'] in content
            has_cdp = patterns['connect_cdp'] in content
            
            if has_helper:
                findings['already_updated'].append(str(py_file.relative_to(project_root)))
            elif has_launch:
                findings['needs_update'].append(str(py_file.relative_to(project_root)))
            elif has_cdp:
                findings['uses_cdp'].append(str(py_file.relative_to(project_root)))
    
    # Print findings
    if findings['already_updated']:
        print("✅ Already using chrome_helper:")
        for f in findings['already_updated']:
            print(f"   - {f}")
        print()
    
    if findings['needs_update']:
        print("⚠️  Need to update (using .launch()):")
        for f in findings['needs_update']:
            print(f"   - {f}")
        print()
    
    if findings['uses_cdp']:
        print("ℹ️  Using CDP connection (usually correct):")
        for f in findings['uses_cdp']:
            print(f"   - {f}")
        print()
    
    return findings

def verify_chrome_helper_exists():
    """Verify chrome_helper.py exists in project root"""
    project_root = Path(__file__).parent
    chrome_helper = project_root / 'chrome_helper.py'
    
    print("🔍 Checking for chrome_helper.py...")
    if chrome_helper.exists():
        print("   ✅ chrome_helper.py exists")
        return True
    else:
        print("   ❌ chrome_helper.py NOT FOUND!")
        print("   Please ensure chrome_helper.py is in the project root directory.")
        return False

def create_example_update():
    """Create an example of how to update a scraper"""
    example = """
# EXAMPLE: How to update bet365_pregame_homepage_scraper.py

# BEFORE (OLD CODE):
async with async_playwright() as playwright:
    browser = await playwright.chromium.launch(
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    # ... rest of code

# AFTER (NEW CODE):
from chrome_helper import setup_chrome_browser

async with async_playwright() as playwright:
    # Use chrome_helper to set up browser (works on Windows and Ubuntu)
    browser, chrome_manager = await setup_chrome_browser(playwright)
    
    if not browser:
        logger.error("❌ Could not setup Chrome browser")
        return False
    
    try:
        # ... your scraping code here
    finally:
        await browser.close()
        if chrome_manager:
            chrome_manager.cleanup()
"""
    
    project_root = Path(__file__).parent
    example_file = project_root / 'UPDATE_EXAMPLE.txt'
    example_file.write_text(example)
    print(f"\n📝 Example update saved to: {example_file}")

def main():
    parser = argparse.ArgumentParser(description='Update scrapers for cross-platform Chrome support')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed')
    args = parser.parse_args()
    
    print("="*70)
    print("🔧 Scraper Update Tool - Chrome Helper Integration")
    print("="*70)
    
    # Step 1: Verify chrome_helper.py exists
    if not verify_chrome_helper_exists():
        return 1
    
    # Step 2: Analyze scrapers
    findings = check_scraper_patterns()
    
    # Step 3: Show instructions
    show_instructions()
    
    # Step 4: Create example
    create_example_update()
    
    # Summary
    print("="*70)
    print("📊 SUMMARY")
    print("="*70)
    print(f"✅ Chrome helper: Ready")
    print(f"✅ Already updated: {len(findings['already_updated'])} files")
    print(f"⚠️  Need manual update: {len(findings['needs_update'])} files")
    print(f"ℹ️  Using CDP (OK): {len(findings['uses_cdp'])} files")
    print("\n")
    
    if findings['needs_update']:
        print("⚠️  ACTION REQUIRED:")
        print("   Some scrapers need manual updating to use chrome_helper")
        print("   See UPDATE_EXAMPLE.txt for code examples")
    else:
        print("✅ All scrapers are ready for Ubuntu deployment!")
    
    print("\n🚀 Next steps:")
    print("   1. Review scrapers that need updating")
    print("   2. Apply chrome_helper integration (see UPDATE_EXAMPLE.txt)")
    print("   3. Test locally on Windows")
    print("   4. Commit and push to GitHub")
    print("   5. Deploy to VPS (will use Ubuntu's Chrome automatically)")
    print("\n")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
