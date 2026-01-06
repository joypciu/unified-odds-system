from playwright.sync_api import sync_playwright

url = "https://www.oddsportal.com/football/england/premier-league/bournemouth-tottenham-Ovaio0L0/"

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=False)
    context = browser.new_context(viewport={'width': 1920, 'height': 1080})
    page = context.new_page()
    
    print(f"Loading: {url}\n")
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    
    # Look for "Full Time Result" or "1x2" button
    print("Looking for odds tabs/buttons...")
    
    # Try to find and click the odds section
    try:
        # Look for buttons with "Odds" text
        buttons = page.query_selector_all('button')
        print(f"Found {len(buttons)} buttons on page")
        
        for btn in buttons[:20]:
            text = btn.inner_text()
            if text and ('odd' in text.lower() or '1x2' in text.lower() or 'result' in text.lower()):
                print(f"  Button: '{text}'")
        
        # Try clicking "1 X 2" or "Full Time Result"
        ftresult = page.query_selector('button:has-text("1 X 2")')
        if not ftresult:
            ftresult = page.query_selector('button:has-text("Full Time")')
        if not ftresult:
            ftresult = page.query_selector('button:has-text("Odds")')
        
        if ftresult:
            print(f"\nClicking button: {ftresult.inner_text()}")
            ftresult.click()
            page.wait_for_timeout(3000)
            
            # Now check for rows
            rows = page.query_selector_all('div[data-testid*="expanded-row"]')
            print(f"After click: Found {len(rows)} rows")
            
            odds_links = page.query_selector_all('a.odds-link')
            print(f"After click: Found {len(odds_links)} odds-link elements")
            
            if odds_links:
                print(f"\nFirst 5 odds:")
                for i, link in enumerate(odds_links[:5]):
                    print(f"  {i+1}. {link.inner_text()}")
        else:
            print("No odds button found")
            
    except Exception as e:
        print(f"Error: {e}")
    
    input("\nPress Enter to close...")
    browser.close()
