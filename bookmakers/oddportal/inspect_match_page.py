"""
Diagnostic test to inspect actual OddsPortal match page HTML structure
"""
from playwright.sync_api import sync_playwright
import json

def inspect_oddportal_match():
    # Test with a real match URL from the scraped data
    test_url = 'https://www.oddsportal.com/basketball/usa/nba/atlanta-hawks-milwaukee-bucks-hptuHG9c/'
    
    print(f"\n{'='*80}")
    print(f"INSPECTING ODDPORTAL MATCH PAGE")
    print(f"{'='*80}")
    print(f"\nURL: {test_url}\n")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible browser to see what happens
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        try:
            print("📡 Loading match page...")
            page.goto(test_url, wait_until='domcontentloaded', timeout=20000)
            page.wait_for_timeout(3000)  # Wait for dynamic content
            
            title = page.title()
            print(f"📄 Page title: {title}\n")
            
            # Try to find bookmaker names
            print("🔍 Searching for bookmaker elements...")
            bookmakers = ['bet365', '1xBet', 'Pinnacle', 'Betfair']
            
            for bm in bookmakers:
                elements = page.locator(f'text={bm}').count()
                print(f"  {bm}: {elements} elements found")
            
            # Look for odds tables or containers
            print(f"\n🎯 Looking for odds containers...")
            
            # Common selectors for odds
            selectors_to_try = [
                'table',
                '[class*="odd"]',
                '[class*="odds"]',
                '[class*="bookmaker"]',
                '.table-main',
                '#odds-data-table',
                'img[alt*="logo"]',
                'img[title]'
            ]
            
            for selector in selectors_to_try:
                count = page.locator(selector).count()
                if count > 0:
                    print(f"  {selector}: {count} elements")
            
            # Get first table if exists
            tables = page.locator('table').all()
            if tables:
                print(f"\n📊 Found {len(tables)} tables on page")
                print(f"  Analyzing first table...")
                
                first_table_html = tables[0].inner_html()
                print(f"  First 500 chars: {first_table_html[:500]}")
            
            # Look for data attributes
            print(f"\n🔑 Looking for bookmaker images...")
            bookmaker_imgs = page.locator('[class*="bookmaker"] img, img[alt*="logo"]').all()[:10]
            for i, img in enumerate(bookmaker_imgs):
                try:
                    alt = img.get_attribute('alt')
                    title = img.get_attribute('title')
                    src = img.get_attribute('src')
                    print(f"  {i+1}. alt={alt}, title={title}, src={src[:50] if src else 'None'}...")
                except:
                    pass
            
            # Try to click on a bookmaker if found
            print(f"\n🖱️  Trying to interact with odds...")
            try:
                # Look for decimal odds button
                decimal_buttons = page.locator('text=/decimal/i').all()
                if decimal_buttons:
                    print(f"  Found {len(decimal_buttons)} decimal buttons")
                    decimal_buttons[0].click()
                    page.wait_for_timeout(1000)
                    print("  ✓ Clicked decimal odds")
            except Exception as e:
                print(f"  ⚠️  Could not click decimal: {e}")
            
            # Get page screenshot for manual inspection
            screenshot_path = 'oddportal_match_screenshot.png'
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n📸 Screenshot saved to: {screenshot_path}")
            
            # Save HTML for inspection
            html_content = page.content()
            with open('oddportal_match_page.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"💾 HTML saved to: oddportal_match_page.html")
            
            # Try to extract visible text
            print(f"\n📝 Visible text (first 2000 chars):")
            visible_text = page.inner_text('body')
            print(visible_text[:2000])
            
            input("\n⏸️  Press Enter to close browser...")
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            browser.close()

if __name__ == "__main__":
    inspect_oddportal_match()
