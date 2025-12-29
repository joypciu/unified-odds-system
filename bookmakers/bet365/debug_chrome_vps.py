#!/usr/bin/env python3
"""
Debug script to test Chrome connection and Bet365 website access on VPS
Run this on VPS to diagnose if scraper can access bet365.ca
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
        '--user-data-dir=/tmp/chrome_debug_bet365',
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

async def debug_bet365():
    """Test Chrome connection and bet365 access"""
    
    print("="*60)
    print("🔍 BET365 CHROME DEBUG SCRIPT FOR VPS")
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
        
        # Comprehensive stealth scripts
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
        
        navigator.mediaDevices = {
            getUserMedia: () => Promise.resolve({}),
            enumerateDevices: () => Promise.resolve([])
        };
        
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
        
        # Step 5: Navigate to Bet365.ca
        url = "https://www.bet365.ca"
        print(f"\n5️⃣  Navigating to {url}...")
        try:
            response = await page.goto(url, timeout=30000, wait_until='domcontentloaded')
            status = response.status if response else 'No response'
            print(f"   ✓ Page loaded - Status: {status}")
        except Exception as e:
            print(f"   ❌ Navigation failed: {e}")
            # Try to take screenshot anyway
            try:
                screenshot_path = Path(__file__).parent / "debug_bet365_failed.png"
                await page.screenshot(path=str(screenshot_path))
                print(f"   📸 Screenshot saved: {screenshot_path}")
            except:
                pass
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
        blocking_found = False
        if 'cloudflare' in content.lower():
            print("   ⚠️  Cloudflare detected in page")
            blocking_found = True
        if 'access denied' in content.lower():
            print("   ⚠️  'Access Denied' found in page")
            blocking_found = True
        if 'captcha' in content.lower():
            print("   ⚠️  CAPTCHA detected")
            blocking_found = True
        if 'robot' in content.lower():
            print("   ⚠️  Robot detection detected")
            blocking_found = True
        if 'blocked' in content.lower():
            print("   ⚠️  'Blocked' found in page")
            blocking_found = True
        
        if not blocking_found:
            print("   ✓ No obvious blocking detected")
        
        # Step 9: Check for Bet365 specific elements
        print("\n9️⃣  Looking for Bet365 page elements...")
        
        # Try to find common Bet365 elements
        element_selectors = [
            '.hm-MainHeaderCentered',  # Header
            '.wn-Page',  # Page wrapper
            '.hm-SportsHeaderModule',  # Sports header
            '.ovm-Fixture',  # Odds view module
            '.gl-MarketGroup',  # Market groups
            '.sl-MarketCouponFixtureLinkJumpLink',  # Sport links
            '[class*="bet365"]',  # Any bet365 class
        ]
        
        found_elements = []
        for selector in element_selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"   ✓ Found {len(elements)} elements with: {selector}")
                    found_elements.append(selector)
            except:
                continue
        
        if not found_elements:
            print("   ❌ No Bet365 specific elements found")
            print("   ⚠️  This may indicate the page didn't load properly")
        
        # Step 10: Test navigation to sports page
        print("\n🔟 Testing navigation to sports page...")
        sports_url = "https://www.bet365.ca/#/HO/"  # Home page with sports
        try:
            await page.goto(sports_url, timeout=30000, wait_until='domcontentloaded')
            await asyncio.sleep(3)
            print(f"   ✓ Loaded {sports_url}")
            
            # Check for sports menu
            print("\n   Looking for sports menu...")
            sports_found = False
            try:
                sports_menu = await page.query_selector('.wn-SportList, .wn-ClassificationBarButton, [class*="Sport"]')
                if sports_menu:
                    print("   ✓ Sports menu found")
                    sports_found = True
            except:
                pass
            
            if not sports_found:
                print("   ❌ Sports menu not found")
        
        except Exception as e:
            print(f"   ❌ Failed to load sports page: {e}")
        
        # Step 11: Check page interactivity
        print("\n1️⃣1️⃣  Checking page interactivity...")
        try:
            is_interactive = await page.evaluate("""
                () => {
                    // Check if page has interactive elements
                    const buttons = document.querySelectorAll('button');
                    const links = document.querySelectorAll('a');
                    const inputs = document.querySelectorAll('input');
                    
                    return {
                        buttons: buttons.length,
                        links: links.length,
                        inputs: inputs.length,
                        hasContent: document.body.innerText.length > 100
                    };
                }
            """)
            print(f"   Interactive elements:")
            print(f"     • Buttons: {is_interactive['buttons']}")
            print(f"     • Links: {is_interactive['links']}")
            print(f"     • Inputs: {is_interactive['inputs']}")
            print(f"     • Has Content: {is_interactive['hasContent']}")
        except Exception as e:
            print(f"   ⚠️  Could not check interactivity: {e}")
        
        # Step 12: Take screenshot
        print("\n📸 Taking screenshot...")
        screenshot_path = Path(__file__).parent / "debug_bet365_screenshot.png"
        await page.screenshot(path=str(screenshot_path), full_page=True)
        print(f"   ✓ Screenshot saved: {screenshot_path}")
        
        # Step 13: Save HTML
        print("\n💾 Saving HTML...")
        html_path = Path(__file__).parent / "debug_bet365_page.html"
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   ✓ HTML saved: {html_path}")
        
        # Final verdict
        print("\n" + "="*60)
        print("📊 FINAL VERDICT")
        print("="*60)
        
        if blocking_found:
            print("❌ BLOCKED - Bet365 appears to be blocking access")
            print("   Possible reasons:")
            print("   • VPS IP is blocked/blacklisted")
            print("   • Cloudflare protection")
            print("   • Geographic restrictions")
            print("   • Bot detection triggered")
        elif not found_elements:
            print("⚠️  WARNING - Page loaded but content is missing")
            print("   Possible reasons:")
            print("   • JavaScript not executed properly")
            print("   • Cloudflare challenge page")
            print("   • Redirect to error page")
        else:
            print("✅ SUCCESS - Bet365 appears accessible")
            print("   Page loaded with expected elements")
        
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
    asyncio.run(debug_bet365())
