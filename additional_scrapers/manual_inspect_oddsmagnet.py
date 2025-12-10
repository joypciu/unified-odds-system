#!/usr/bin/env python3
"""
Manual OddsMagnet Inspector - Opens browser for you to click through manually
This will help us understand the actual structure when you interact with the site
"""

from playwright.sync_api import sync_playwright
import time

def manual_inspect():
    print("="*70)
    print("MANUAL ODDSMAGNET INSPECTION")
    print("="*70)
    print("\nThis will open a Chrome browser for you to interact with.")
    print("Please follow these steps:")
    print("  1. Click on 'Football' sport")
    print("  2. Click on 'Spain La Liga' league")
    print("  3. Click on any match")
    print("  4. Click on any market")
    print("  5. When you're done, come back here and press Enter")
    print("\n" + "="*70)
    
    with sync_playwright() as p:
        # Launch browser with headed mode (visible)
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage'
            ]
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = context.new_page()
        
        # Load homepage
        print("\nLoading homepage...")
        page.goto("https://oddsmagnet.com", wait_until="domcontentloaded")
        print("Homepage loaded! You can now interact with the browser.")
        print("\nWaiting for you to complete the navigation...")
        print("(The browser will stay open until you press Enter here)")
        
        # Wait for user to finish
        input("\nPress Enter when you're done exploring...")
        
        # Get final page state
        print("\n" + "="*70)
        print("CAPTURING PAGE STATE")
        print("="*70)
        
        # Wait for page to stabilize
        time.sleep(2)
        
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass  # Page might still be loading, continue anyway
        
        current_url = page.url
        print(f"\nFinal URL: {current_url}")
        
        # Save HTML
        try:
            html = page.content()
            with open("final_page.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"HTML saved to: final_page.html ({len(html)} chars)")
        except Exception as e:
            print(f"Could not save HTML: {e}")
        
        # Get page title
        try:
            title = page.title()
            print(f"Page title: {title}")
        except:
            print("Could not get page title")
        
        # Count links
        try:
            all_links = page.locator("a").all()
            print(f"Total links on page: {len(all_links)}")
        except:
            print("Could not count links")
        
        # Look for odds tables or similar
        try:
            tables = page.locator("table").all()
            print(f"Total tables on page: {len(tables)}")
            
            if len(tables) > 0:
                print("\nTable details:")
                for i, table in enumerate(tables[:3]):
                    rows = table.locator("tr").all()
                    print(f"  Table {i+1}: {len(rows)} rows")
        except:
            print("Could not analyze tables")
        
        # Look for common odds-related classes
        try:
            print("\nLooking for odds-related elements...")
            odds_elements = page.locator("[class*='odd'], [class*='price'], [class*='bet']").all()
            print(f"Found {len(odds_elements)} elements with odds-related classes")
        except:
            print("Could not find odds elements")
        
        print("\n" + "="*70)
        print("Inspection complete! Browser will close in 3 seconds...")
        time.sleep(3)
        
        browser.close()
        
        print("\nTo analyze the saved HTML, you can search for specific patterns.")
        print(f"File saved: final_page.html")

if __name__ == "__main__":
    manual_inspect()
