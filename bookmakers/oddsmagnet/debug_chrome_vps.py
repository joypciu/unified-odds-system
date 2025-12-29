#!/usr/bin/env python3
"""
Debug script to test Chrome connection and OddsMagnet website access
Run this on VPS to diagnose why scraper finds no leagues
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

async def debug_chrome():
    """Test Chrome connection and website access"""
    
    print("="*60)
    print("🔍 CHROME + ODDSMAGNET DEBUG SCRIPT")
    print("="*60)
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
        
        # Step 3: Get or create context
        print("\n3️⃣  Getting browser context...")
        if browser.contexts:
            context = browser.contexts[0]
            print("   ✓ Using existing context")
        else:
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            print("   ✓ Created new context")
        
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
