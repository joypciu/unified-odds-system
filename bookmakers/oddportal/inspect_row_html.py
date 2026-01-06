from playwright.sync_api import sync_playwright
import time

url = "https://www.oddsportal.com/football/italy/serie-a/as-roma-sassuolo-WSbSzRdT/"

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel='chrome',
        headless=False,
        args=[
            '--disable-blink-features=AutomationControlled',
            '--window-position=-2400,-2400'
        ]
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    page = context.new_page()
    
    print(f"Loading: {url}")
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(5000)
    
    # Get a single row and inspect its HTML
    rows = page.query_selector_all('div[data-testid*="expanded-row"]')
    print(f"Total rows: {len(rows)}")
    
    if rows:
        first_row = rows[0]
        html = first_row.inner_html()
        print(f"\nFirst row HTML (first 1000 chars):")
        print(html[:1000])
        
        # Check for different odds patterns
        print("\n\nLooking for odds in first row:")
        
        # Try p tag with any class
        p_tags = first_row.query_selector_all('p')
        print(f"Found {len(p_tags)} p tags")
        for i, p in enumerate(p_tags[:5]):
            text = p.inner_text()
            classes = p.get_attribute('class')
            print(f"  P{i}: '{text}' (class: {classes})")
        
        # Try divs with numbers
        all_text = first_row.inner_text()
        print(f"\nRow text: {all_text}")
    
    browser.close()
