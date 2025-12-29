#!/usr/bin/env python3
"""
Debug script to test Chrome connection and OddsMagnet website access
Run this on VPS to diagnose why scraper finds no leagues
"""

import asyncio
import sys
import subprocess
import socket
import time
from pathlib import Path
from playwright.async_api import async_playwright

def is_port_open(port=9222):
    """Check if Chrome is running on port"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    except:
        return False

def start_chrome():
    """Start Chrome with remote debugging"""
    if is_port_open(9222):
        print("   ✓ Chrome already running on port 9222")
        return True
    
    print("   🚀 Starting Chrome on port 9222...")
    subprocess.Popen([
        'google-chrome',
        '--remote-debugging-port=9222',
        '--user-data-dir=/tmp/chrome_debug_auto',
        '--no-first-run',
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--no-sandbox',
        '--headless=new'
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    for _ in range(10):
        time.sleep(0.5)
        if is_port_open(9222):
            print("   ✓ Chrome started successfully")
            return True
    
    print("   ❌ Chrome failed to start")
    return False

async def debug_chrome():
    """Test Chrome connection and website access"""
    
    print("="*60)
    print("🔍 CHROME + ODDSMAGNET DEBUG SCRIPT")
    print("="*60)
    print()
    
    # Auto-start Chrome if needed
    start_chrome()
    print()
    
    playwright = None
    browser = None
    
    try:
        # Step 1: Start Playwright
        print("1️⃣  Starting Playwright...")
        playwright = await async_playwright().start()
        print("   ✓ Playwright started")
        
        # Step 2: Connect to Chrome on port 9222
        print("\n2️⃣  Connecting to Chrome on port 9222...")
        try:
            browser = await playwright.chromium.connect_over_cdp("http://localhost:9222")
            print("   ✓ Connected to Chrome remote debugging")
        except Exception as e:
            print(f"   ❌ Failed to connect: {e}")
            print("\n💡 Make sure Chrome is running with:")
            print("   google-chrome --remote-debugging-port=9222 --headless=new")
            return
        
        # Step 3: Create FRESH context with stealth
        print("\n3️⃣  Creating fresh browser context with stealth...")
        
        # Stealth scripts to inject before page creation
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        window.chrome = { runtime: {}, loadTimes: function() {}, csi: function() {} };
        Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
        Object.defineProperty(navigator, 'vendor', { get: () => 'Google Inc.' });
        Object.defineProperty(navigator, 'maxTouchPoints', { get: () => 0 });
        Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
        Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        
        // Mock getUserMedia
        navigator.mediaDevices = {
            getUserMedia: () => Promise.resolve({}),
            enumerateDevices: () => Promise.resolve([])
        };
        
        // Override permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        """
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Upgrade-Insecure-Requests': '1'
            }
        )
        
        await context.add_init_script(stealth_js)
        print("   ✓ Fresh context with anti-detection scripts created")
        
        # Step 4: Create page
        print("\n4️⃣  Creating new page...")
        page = await context.new_page()
        print("   ✓ Page created")
        
        # Step 5: Navigate to OddsMagnet
        url = "https://www.oddsmagnet.com"
        print(f"\n5️⃣  Navigating to {url}...")
        try:
            response = await page.goto(url, timeout=30000, wait_until='domcontentloaded')
            status = response.status if response else 'No response'
            print(f"   ✓ Page loaded - Status: {status}")
        except Exception as e:
            print(f"   ❌ Navigation failed: {e}")
            return
        
        # Step 6: Wait for page to settle
        print("\n6️⃣  Waiting for page to load...")
        await asyncio.sleep(3)
        print("   ✓ Wait complete")
        
        # Step 7: Check page title
        print("\n7️⃣  Checking page title...")
        title = await page.title()
        print(f"   Title: {title}")
        
        # Step 8: Check page content
        print("\n8️⃣  Checking page content...")
        content = await page.content()
        print(f"   HTML length: {len(content)} characters")
        
        # Check for common blocking indicators
        if 'cloudflare' in content.lower():
            print("   ⚠️  Cloudflare detected in page")
        if 'access denied' in content.lower():
            print("   ⚠️  'Access Denied' found in page")
        if 'captcha' in content.lower():
            print("   ⚠️  CAPTCHA detected")
        if 'robot' in content.lower():
            print("   ⚠️  Robot detection detected")
        
        # Step 9: Check for sport navigation
        print("\n9️⃣  Looking for sport navigation...")
        
        # Try to find sport links
        sport_selectors = [
            'a[href*="football"]',
            'a[href*="basketball"]',
            'a[href*="soccer"]',
            'nav a',
            '.sports-nav a',
            '[class*="sport"] a'
        ]
        
        found_sports = False
        for selector in sport_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                print(f"   ✓ Found {len(elements)} elements with selector: {selector}")
                # Print first few hrefs
                for i, elem in enumerate(elements[:5]):
                    href = await elem.get_attribute('href')
                    text = await elem.inner_text()
                    print(f"      [{i+1}] {text[:50]} -> {href}")
                found_sports = True
                break
        
        if not found_sports:
            print("   ❌ No sport navigation found")
        
        # Step 10: Try football specifically
        print("\n🔟 Testing football page...")
        football_url = "https://www.oddsmagnet.com/football"
        try:
            await page.goto(football_url, timeout=30000, wait_until='domcontentloaded')
            await asyncio.sleep(2)
            print(f"   ✓ Loaded {football_url}")
            
            # Look for leagues
            print("\n   Looking for leagues...")
            league_selectors = [
                'a[href*="/football/"]',
                '.league',
                '[class*="league"]',
                'a[class*="competition"]'
            ]
            
            for selector in league_selectors:
                leagues = await page.query_selector_all(selector)
                if leagues:
                    print(f"   ✓ Found {len(leagues)} potential leagues with: {selector}")
                    for i, league in enumerate(leagues[:5]):
                        href = await league.get_attribute('href')
                        text = await league.inner_text()
                        print(f"      [{i+1}] {text[:50]} -> {href}")
                    break
            else:
                print("   ❌ No leagues found")
        
        except Exception as e:
            print(f"   ❌ Failed to load football page: {e}")
        
        # Step 11: Take screenshot
        print("\n📸 Taking screenshot...")
        screenshot_path = Path(__file__).parent / "debug_screenshot.png"
        await page.screenshot(path=str(screenshot_path))
        print(f"   ✓ Screenshot saved: {screenshot_path}")
        
        # Step 12: Save HTML
        print("\n💾 Saving HTML...")
        html_path = Path(__file__).parent / "debug_page.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✓ HTML saved: {html_path}")
        
        print("\n" + "="*60)
        print("✅ DEBUG COMPLETE")
        print("="*60)
        print(f"\nCheck files:")
        print(f"  • Screenshot: {screenshot_path}")
        print(f"  • HTML: {html_path}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        if browser:
            try:
                await browser.close()
            except:
                pass
        if playwright:
            try:
                await playwright.stop()
            except:
                pass


if __name__ == "__main__":
    asyncio.run(debug_chrome())
