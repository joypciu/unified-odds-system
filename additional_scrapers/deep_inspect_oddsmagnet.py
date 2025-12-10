#!/usr/bin/env python3
"""
Deep OddsMagnet Inspector - Explores actual page structure
"""

from playwright.sync_api import sync_playwright
import json
import time

def inspect_oddsmagnet():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Non-headless to see what's happening
        page = browser.new_page()
        
        print("=" * 70)
        print("DEEP ODDSMAGNET INSPECTION - FULL NAVIGATION PATH")
        print("=" * 70)
        
        # Step 1: Visit homepage
        print("\n[STEP 1] Loading homepage...")
        page.goto("https://oddsmagnet.com/", wait_until="networkidle")
        time.sleep(3)
        page.screenshot(path="step1_homepage.png")
        print("    ✓ Homepage loaded")
        
        # Step 2: Click on Football
        print("\n[STEP 2] Clicking on Football sport...")
        try:
            # Try to find and click football link
            football_link = page.locator("a:has-text('FOOTBALL'), a:has-text('Football')").first
            football_link.click()
            page.wait_for_load_state("networkidle")
            time.sleep(3)
            page.screenshot(path="step2_football.png")
            print("    ✓ Football page loaded")
        except Exception as e:
            print(f"    ✗ Error: {e}")
            print("    Trying direct URL...")
            page.goto("https://oddsmagnet.com/football", wait_until="networkidle")
            time.sleep(3)
        
        # Step 3: Find and click Spain La Liga accordion
        print("\n[STEP 3] Looking for Spain La Liga accordion...")
        
        # Wait for accordions to load
        page.wait_for_selector(".accordion .card", timeout=10000)
        
        # Find all accordion cards with leagues
        accordion_cards = page.locator(".accordion .card").all()
        print(f"    Found {len(accordion_cards)} accordion cards")
        
        # Look for La Liga button
        la_liga_found = False
        la_liga_button = None
        
        print("    \nSearching for 'spain laliga' in accordion buttons...")
        for i, card in enumerate(accordion_cards[:20]):  # Check first 20
            try:
                button = card.locator("button").first
                button_text = button.inner_text().strip().lower()
                
                if 'spain laliga' in button_text or 'spain la liga' in button_text:
                    print(f"    ✓ Found La Liga at position {i+1}: '{button_text}'")
                    la_liga_button = button
                    la_liga_found = True
                    break
                elif i < 5:  # Show first 5 for reference
                    print(f"      [{i+1}] {button_text[:50]}")
            except Exception as e:
                continue
        
        if not la_liga_found:
            print("    ✗ Could not find La Liga accordion button")
            browser.close()
            return
        
        # Click to expand the La Liga accordion
        print("    \nClicking La Liga accordion...")
        la_liga_button.click()
        time.sleep(3)  # Wait longer for accordion to expand and load matches
        
        # Wait for the collapse section to be visible
        page.wait_for_selector("#collapse-spain-laliga", state="visible", timeout=5000)
        page.screenshot(path="step3_laliga_expanded.png")
        print("    ✓ La Liga accordion expanded")
        
        # Save expanded HTML to analyze
        html_expanded = page.content()
        with open("laliga_expanded.html", "w", encoding="utf-8") as f:
            f.write(html_expanded)
        print("    HTML saved: laliga_expanded.html")
        
        # Step 4: Find matches in expanded La Liga section
        print("\n[STEP 4] Looking for matches in La Liga section...")
        
        # After expanding, matches should appear in the collapse section
        # Check specifically within the La Liga collapse div
        time.sleep(2)  # Give it time to fully expand
        
        # Try to find matches within the expanded La Liga section
        laliga_section = page.locator("#collapse-spain-laliga")
        
        # Look for links within this section
        section_links = laliga_section.locator("a").all()
        print(f"    Found {len(section_links)} links in La Liga section")
        
        # Also check the entire page for any match-like links
        all_links = page.locator("a").all()
        match_links = []
        
        print("    \nSearching for match links...")
        for link in all_links:
            try:
                href = link.get_attribute("href")
                text = link.inner_text().strip()
                
                # Look for match links (team vs team patterns)
                # Typical patterns: "Team A v Team B", "Team A vs Team B"
                if href and (' v ' in text.lower() or ' vs ' in text.lower()) and len(text) > 5:
                    # Filter out navigation links
                    if 'football' in href and text.count(' ') >= 2:
                        match_links.append({
                            'text': text,
                            'href': href
                        })
                        if len(match_links) <= 3:  # Show first 3
                            print(f"      Found: {text[:50]} -> {href}")
            except:
                continue
        
        # Also try another approach - look for div/span elements that might contain match info
        if len(match_links) == 0:
            print("    \n    No links found, checking card-body for match elements...")
            card_bodies = laliga_section.locator(".card-body").all()
            print(f"    Found {len(card_bodies)} card bodies in La Liga section")
            
            if len(card_bodies) > 0:
                body_html = card_bodies[0].inner_html()
                print(f"    First card body HTML length: {len(body_html)} chars")
                
                # Check if it's empty or loading
                if len(body_html) < 50:
                    print("    Card body appears empty - matches may still be loading")
        
        print(f"    Total matches found: {len(match_links)}")
        
        if match_links:
            print("    \nFirst 5 matches:")
            for i, match in enumerate(match_links[:5]):
                print(f"      [{i+1}] {match['text']} -> {match['href']}")
        else:
            print("    ✗ No matches found")
            browser.close()
            return
        
        # Step 5: Click on first match
        if match_links:
            print(f"\n[STEP 5] Clicking on first match: {match_links[0]['text']}")
            try:
                match_url = match_links[0]['href']
                if not match_url.startswith('http'):
                    match_url = f"https://oddsmagnet.com{match_url}"
                
                page.goto(match_url, wait_until="networkidle")
                time.sleep(3)
                page.screenshot(path="step5_match_page.png")
                print("    ✓ Match page loaded")
                
                # List all available markets
                print("\n[STEP 6] Finding available markets...")
                market_links = []
                all_links = page.locator("a").all()
                
                for link in all_links:
                    try:
                        href = link.get_attribute("href")
                        text = link.inner_text()
                        
                        # Look for market links
                        market_keywords = ['market', 'win', 'draw', 'over', 'under', 'handicap', 'goals']
                        if href and any(keyword in href.lower() for keyword in market_keywords):
                            market_links.append({
                                'text': text,
                                'href': href
                            })
                            print(f"    Found market: {text} -> {href}")
                    except:
                        continue
                
                print(f"    Total markets found: {len(market_links)}")
                
                # Step 6: Click on first market (usually win-market)
                if market_links:
                    print(f"\n[STEP 7] Clicking on first market: {market_links[0]['text']}")
                    try:
                        market_url = market_links[0]['href']
                        if not market_url.startswith('http'):
                            market_url = f"https://oddsmagnet.com{market_url}"
                        
                        page.goto(market_url, wait_until="networkidle")
                        time.sleep(3)
                        page.screenshot(path="step7_market_odds.png")
                        print("    ✓ Market odds page loaded")
                        
                        # Step 7: Extract odds data
                        print("\n[STEP 8] Extracting odds data...")
                        
                        # Find odds table
                        tables = page.locator("table").all()
                        print(f"    Tables found: {len(tables)}")
                        
                        if tables:
                            print("\n    Odds Table Content:")
                            for table_idx, table in enumerate(tables[:3]):
                                print(f"\n    --- Table {table_idx + 1} ---")
                                try:
                                    rows = table.locator("tr").all()
                                    for i, row in enumerate(rows[:10]):
                                        cells = row.locator("td, th").all()
                                        row_text = [cell.inner_text().strip() for cell in cells if cell.inner_text().strip()]
                                        if row_text:
                                            print(f"      Row {i+1}: {' | '.join(row_text)}")
                                except Exception as e:
                                    print(f"      Error reading table: {e}")
                        
                        # Save HTML of odds page
                        html = page.content()
                        with open("oddsmagnet_odds_page.html", "w", encoding="utf-8") as f:
                            f.write(html)
                        print("\n    ✓ Odds page HTML saved: oddsmagnet_odds_page.html")
                        
                    except Exception as e:
                        print(f"    ✗ Error loading market: {e}")
                else:
                    print("    ✗ No markets found")
            except Exception as e:
                print(f"    ✗ Error loading match: {e}")
        else:
            print("    ✗ No matches found")
        
        print("\n" + "=" * 70)
        print("Inspection complete!")
        print("Check the screenshots and HTML file for details")
        print("=" * 70)
        
        input("\nPress Enter to close browser...")
        browser.close()

if __name__ == "__main__":
    inspect_oddsmagnet()
