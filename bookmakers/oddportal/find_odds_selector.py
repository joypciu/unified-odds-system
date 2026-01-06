from playwright.sync_api import sync_playwright

url = "https://www.oddsportal.com/football/italy/serie-a/as-roma-sassuolo-WSbSzRdT/"

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel='chrome',
        headless=False,
        args=['--disable-blink-features=AutomationControlled', '--window-position=-2400,-2400']
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    page = context.new_page()
    
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)
    
    rows = page.query_selector_all('div[data-testid*="expanded-row"]')
    print(f"Total rows: {len(rows)}")
    
    if rows:
        first_row = rows[0]
        
        # Try to find elements containing odds values
        print("\nSearching for odds values...")
        
        # Try all p tags
        all_p = first_row.query_selector_all('p')
        print(f"\nAll P tags: {len(all_p)}")
        for p in all_p:
            text = p.inner_text().strip()
            if text and text[0].isdigit():
                print(f"  Found number: '{text}' | class: {p.get_attribute('class')}")
        
        # Try all divs
        all_divs = first_row.query_selector_all('div')
        print(f"\nChecking divs for numeric content...")
        for div in all_divs[:20]:
            text = div.inner_text().strip()
            if text and len(text) < 10 and text[0].isdigit() and '.' in text:
                print(f"  Div with odds: '{text}' | class: {div.get_attribute('class')}")
        
        # Try a tags
        all_a = first_row.query_selector_all('a')
        print(f"\nChecking <a> tags...")
        for a in all_a:
            text = a.inner_text().strip()
            if text and len(text) < 10 and text and text[0].isdigit():
                print(f"  A tag: '{text}' | class: {a.get_attribute('class')}")
    
    browser.close()
