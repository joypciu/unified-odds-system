from playwright.sync_api import sync_playwright

url = "https://www.oddsportal.com/football/italy/serie-a/as-roma-sassuolo-WSbSzRdT/"

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel='chrome',
        headless=False,
        args=['--disable-blink-features=AutomationControlled']
    )
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    page = context.new_page()
    
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(3000)
    
    # Click the first odds button to expand
    try:
        # Look for the odds display area
        odds_container = page.query_selector('div.eventTable__wrapper')
        if odds_container:
            print("Found odds container")
            
        # Get the actual page content
        page.wait_for_timeout(2000)
        
        # Try to find odds values directly using text content
        page_text = page.content()
        
        # Look for pattern like data-v-... with odds values
        print("\nSearching page source for odds patterns...")
        if '1.61' in page_text:
            print("✓ Found 1.61 in page source")
            # Find context around it
            idx = page_text.find('1.61')
            context = page_text[max(0, idx-200):idx+200]
            print(f"\nContext around 1.61:")
            print(context)
    except Exception as e:
        print(f"Error: {e}")
    
    input("\nPress Enter to close...")
    browser.close()
