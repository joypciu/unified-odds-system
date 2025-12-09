"""
Debug NBA Data Collection - Bet365
===================================
This script specifically debugs why NBA data is not being returned.
It focuses on:
- Network responses when navigating to NBA section
- Data format analysis
- Response body inspection
- Identifying if Cloudflare/anti-bot is blocking

Usage:
    python debug_nba_data.py
"""
import asyncio
import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List
import sys

from patchright.async_api import async_playwright
# Import from parent directory
sys.path.append(str(Path(__file__).parent.parent))
from chrome_helper import setup_chrome_browser, dismiss_bet365_popups, verify_bet365_loaded

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NBADataDebugger:
    """Debug NBA-specific data collection issues"""
    
    def __init__(self):
        self.output_dir = Path("nba_debug_output")
        self.output_dir.mkdir(exist_ok=True)
        
        self.captured_responses: List[Dict] = []
        self.nba_responses: List[Dict] = []
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    async def capture_response(self, response):
        """Capture and analyze responses"""
        try:
            # Skip non-bet365 responses
            if 'bet365' not in response.url.lower():
                return
            
            status = response.status
            url = response.url
            
            try:
                body = await response.text()
                body_size = len(body) if body else 0
            except:
                body = None
                body_size = 0
            
            response_data = {
                'timestamp': datetime.now().isoformat(),
                'url': url,
                'status': status,
                'size': body_size,
                'body': body,
            }
            
            self.captured_responses.append(response_data)
            
            # Analyze response
            status_icon = "✅" if status == 200 else "❌"
            logger.info(f"{status_icon} Response: {status} | {body_size:,} bytes | {url[:100]}...")
            
            if body and body_size > 0:
                # Check for NBA data patterns
                has_pa_ma = 'PA;' in body and 'MA;' in body
                has_nba_keywords = any(kw in body.upper() for kw in ['LAKERS', 'WARRIORS', 'CELTICS', 'NBA', 'BASKETBALL'])
                has_error = 'error' in body.lower() or 'not found' in body.lower()
                
                logger.info(f"   Data patterns:")
                logger.info(f"     - PA/MA format: {'✅' if has_pa_ma else '❌'}")
                logger.info(f"     - NBA keywords: {'✅' if has_nba_keywords else '❌'}")
                logger.info(f"     - Error message: {'⚠️ YES' if has_error else '✅ NO'}")
                
                # Preview
                if body_size < 500:
                    logger.info(f"   Full response: {body}")
                else:
                    preview = body[:300].replace('\n', ' ')
                    logger.info(f"   Preview: {preview}...")
                
                # Save if it looks like NBA data
                if has_pa_ma or has_nba_keywords:
                    self.nba_responses.append(response_data)
                    
                    # Save to file
                    filename = f"{self.session_id}_nba_response_{len(self.nba_responses)}.txt"
                    filepath = self.output_dir / filename
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(f"URL: {url}\n")
                        f.write(f"Status: {status}\n")
                        f.write(f"Size: {body_size:,} bytes\n")
                        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                        f.write("="*80 + "\n\n")
                        f.write(body)
                    
                    logger.info(f"   💾 Saved NBA data to: {filename}")
            else:
                logger.warning(f"   ⚠️ Empty or unreadable response")
                
        except Exception as e:
            logger.warning(f"Error capturing response: {e}")
    
    def save_summary(self):
        """Save debugging summary"""
        summary = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'total_responses': len(self.captured_responses),
            'nba_responses': len(self.nba_responses),
            'responses': self.captured_responses,
        }
        
        summary_file = self.output_dir / f"{self.session_id}_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"\n📊 Summary saved to: {summary_file}")
        logger.info(f"📦 Found {len(self.nba_responses)} responses with NBA data")


async def debug_nba_collection():
    """Debug NBA data collection process"""
    
    logger.info("="*80)
    logger.info("🏀 NBA DATA COLLECTION DEBUG")
    logger.info("="*80)
    logger.info("This script will:")
    logger.info("  1. Open bet365 homepage")
    logger.info("  2. Navigate to NBA section")
    logger.info("  3. Capture all network responses")
    logger.info("  4. Analyze data patterns")
    logger.info("  5. Identify issues")
    logger.info("="*80 + "\n")
    
    debugger = NBADataDebugger()
    
    async with async_playwright() as playwright:
        # Setup browser using chrome_helper (NEVER driver)
        logger.info("🌐 Setting up Chrome browser...")
        browser, chrome_manager = await setup_chrome_browser(playwright)
        
        if not browser:
            logger.error("❌ Could not setup Chrome browser")
            return False
        
        logger.info("✅ Browser connected\n")
        
        # Get page
        try:
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
                pages = context.pages
                if pages:
                    page = pages[0]
                else:
                    page = await context.new_page()
            else:
                page = await browser.new_page()
                
            # Apply anti-detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)
            
        except Exception as e:
            logger.error(f"❌ Failed to get page: {e}")
            return False
        
        # Set up network listener
        page.on("response", lambda resp: asyncio.create_task(debugger.capture_response(resp)))
        
        try:
            # Step 1: Load homepage
            logger.info("="*80)
            logger.info("STEP 1: Loading bet365 homepage")
            logger.info("="*80 + "\n")
            
            await page.goto('https://www.on.bet365.ca/', wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)
            
            # Dismiss popups
            logger.info("🔕 Dismissing popups...")
            await dismiss_bet365_popups(page, logger)
            await asyncio.sleep(2)
            
            # Verify loaded
            if not await verify_bet365_loaded(page, logger):
                logger.error("❌ Homepage did not load properly!")
                logger.error("   Common causes:")
                logger.error("   - Cloudflare challenge")
                logger.error("   - Anti-bot protection")
                logger.error("   - Network issues")
                logger.error("\n   Checking page content...")
                
                try:
                    content = await page.content()
                    logger.info(f"   Page length: {len(content):,} chars")
                    
                    if 'cloudflare' in content.lower():
                        logger.error("   ☁️ CLOUDFLARE DETECTED")
                    if 'challenge' in content.lower():
                        logger.error("   🛡️ CHALLENGE/CAPTCHA DETECTED")
                    
                    # Save page content for inspection
                    debug_file = debugger.output_dir / f"{debugger.session_id}_homepage.html"
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"   💾 Saved page content to: {debug_file}")
                    
                except Exception as e:
                    logger.error(f"   Could not get page content: {e}")
            else:
                logger.info("✅ Homepage loaded successfully\n")
            
            # Step 2: Human-like scrolling
            logger.info("="*80)
            logger.info("STEP 2: Human-like scrolling")
            logger.info("="*80 + "\n")
            
            scroll_duration = random.uniform(2, 3)
            logger.info(f"Scrolling for {scroll_duration:.1f} seconds...")
            
            start_time = asyncio.get_event_loop().time()
            while (asyncio.get_event_loop().time() - start_time) < scroll_duration:
                scroll_amount = random.randint(50, 300)
                await page.evaluate(f'window.scrollBy(0, {scroll_amount})')
                await asyncio.sleep(random.uniform(0.3, 0.6))
                
                if random.random() > 0.7:
                    scroll_back = random.randint(-150, -50)
                    await page.evaluate(f'window.scrollBy(0, {scroll_back})')
                
                await asyncio.sleep(random.uniform(0.2, 0.4))
            
            logger.info("✅ Scrolling complete\n")
            
            # Step 3: Navigate to NBA
            logger.info("="*80)
            logger.info("STEP 3: Navigating to NBA section")
            logger.info("="*80 + "\n")
            
            await asyncio.sleep(random.uniform(1, 2))
            
            logger.info("🏀 Clicking NBA link...")
            
            # Try to find and click NBA
            nba_clicked = False
            try:
                # Look for NBA link/button
                nba_selector = 'text=/.*NBA.*|Basketball.*/i'
                nba_element = page.locator(nba_selector).first
                
                if await nba_element.count() > 0:
                    await nba_element.click()
                    logger.info("✅ Clicked NBA element")
                    nba_clicked = True
                else:
                    logger.warning("⚠️ Could not find NBA element")
                    
            except Exception as e:
                logger.warning(f"⚠️ Could not click NBA: {e}")
            
            # Alternative: Direct navigation
            if not nba_clicked:
                logger.info("📍 Trying direct URL navigation...")
                nba_url = 'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/'
                await page.goto(nba_url, wait_until='domcontentloaded', timeout=30000)
                logger.info("✅ Navigated directly to NBA URL")
            
            await asyncio.sleep(5)
            
            # Check if NBA section loaded
            logger.info("\n🔍 Checking if NBA data loaded...")
            
            try:
                content = await page.content()
                has_nba = any(kw in content.upper() for kw in ['LAKERS', 'WARRIORS', 'CELTICS', 'NBA'])
                
                if has_nba:
                    logger.info("✅ NBA content found in page")
                else:
                    logger.warning("⚠️ No NBA content detected in page")
                    
                    # Save for inspection
                    nba_file = debugger.output_dir / f"{debugger.session_id}_nba_page.html"
                    with open(nba_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"   💾 Saved NBA page to: {nba_file}")
                    
            except Exception as e:
                logger.error(f"❌ Could not check page content: {e}")
            
            # Step 4: Wait and monitor
            logger.info("\n" + "="*80)
            logger.info("STEP 4: Monitoring for additional network activity")
            logger.info("="*80 + "\n")
            
            logger.info("⏱️ Waiting 10 seconds...")
            await asyncio.sleep(10)
            
            logger.info("✅ Monitoring complete\n")
            
        except Exception as e:
            logger.error(f"❌ Error during debug: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            # Save results
            debugger.save_summary()
            
            # Analysis
            logger.info("\n" + "="*80)
            logger.info("📊 DEBUG ANALYSIS")
            logger.info("="*80)
            logger.info(f"Total bet365 responses: {len(debugger.captured_responses)}")
            logger.info(f"NBA data responses: {len(debugger.nba_responses)}")
            
            if len(debugger.nba_responses) == 0:
                logger.error("\n❌ NO NBA DATA FOUND")
                logger.error("Possible causes:")
                logger.error("  1. Cloudflare/anti-bot blocking requests")
                logger.error("  2. Page not fully loading")
                logger.error("  3. NBA section not being accessed correctly")
                logger.error("  4. Network requests being blocked")
                logger.error("\n💡 Recommendations:")
                logger.error("  - Check saved HTML files for Cloudflare")
                logger.error("  - Verify Chrome is actually showing NBA page")
                logger.error("  - Look at network tab in Chrome DevTools")
                logger.error("  - Try with manual CAPTCHA solving if needed")
            else:
                logger.info("\n✅ NBA DATA CAPTURED")
                logger.info(f"Found {len(debugger.nba_responses)} responses with NBA data")
                logger.info("Check output files for details")
            
            logger.info("="*80)
            
            # Keep browser open
            logger.info("\n🔍 Browser kept open for manual inspection")
            logger.info("Press Ctrl+C when done...\n")
            
            try:
                await asyncio.sleep(999999)
            except KeyboardInterrupt:
                logger.info("\n👋 Shutting down...")
    
    return True


def main():
    """Main entry point"""
    try:
        success = asyncio.run(debug_nba_collection())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n\n👋 Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
