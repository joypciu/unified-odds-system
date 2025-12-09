"""
Debug Bet365 Odds API Calls
============================
Specifically monitors for the API endpoints that deliver PA/MA odds data.
This script helps identify WHY odds data is not being returned.

The actual odds data comes from specific API patterns like:
- /Api/1/...
- Contains PA; and MA; patterns
- Usually large responses (>50KB)
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path
import sys

from patchright.async_api import async_playwright
sys.path.append(str(Path(__file__).parent.parent))
from chrome_helper import setup_chrome_browser, dismiss_bet365_popups

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OddsAPIMonitor:
    """Monitor specifically for odds API calls"""
    
    def __init__(self):
        self.odds_responses = []
        self.all_api_calls = []
        self.output_dir = Path("odds_api_debug")
        self.output_dir.mkdir(exist_ok=True)
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    async def monitor_response(self, response):
        """Check if response contains odds data"""
        try:
            url = response.url
            
            # Look for API endpoints
            if '/Api/' in url or '/api/' in url or 'bet365' in url.lower():
                self.all_api_calls.append({
                    'url': url,
                    'status': response.status,
                    'timestamp': datetime.now().isoformat()
                })
                
                logger.info(f"📡 API Call: {response.status} | {url[:120]}...")
                
                # Try to get body
                try:
                    body = await response.text()
                    size = len(body) if body else 0
                    
                    # Check for PA/MA pattern (actual odds data!)
                    has_odds_data = body and ('PA;' in body and 'MA;' in body)
                    
                    if has_odds_data:
                        logger.info(f"  ✅ FOUND ODDS DATA! Size: {size:,} bytes")
                        logger.info(f"  Preview: {body[:200]}...")
                        
                        # Save it!
                        self.odds_responses.append({
                            'url': url,
                            'body': body,
                            'size': size,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        filename = f"{self.session_id}_ODDS_DATA_{len(self.odds_responses)}.txt"
                        filepath = self.output_dir / filename
                        
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(f"URL: {url}\n")
                            f.write(f"Size: {size:,} bytes\n")
                            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                            f.write("="*80 + "\n\n")
                            f.write(body)
                        
                        logger.info(f"  💾 Saved to: {filename}")
                    
                    elif size > 10000:
                        logger.info(f"  📦 Large response: {size:,} bytes (no odds pattern)")
                    else:
                        logger.info(f"  📄 Small response: {size:,} bytes")
                        
                except Exception as e:
                    logger.debug(f"  Could not read body: {e}")
                    
        except Exception as e:
            logger.warning(f"Error monitoring response: {e}")


async def main():
    """Main debug routine"""
    logger.info("="*80)
    logger.info("🔍 BET365 ODDS API DEBUG")
    logger.info("="*80)
    logger.info("This will:")
    logger.info("  1. Open bet365 homepage")
    logger.info("  2. Navigate to NBA section")
    logger.info("  3. Monitor ALL API calls")
    logger.info("  4. Specifically look for PA/MA odds data")
    logger.info("="*80 + "\n")
    
    monitor = OddsAPIMonitor()
    
    async with async_playwright() as playwright:
        logger.info("🌐 Setting up Chrome...")
        browser, chrome_manager = await setup_chrome_browser(playwright)
        
        if not browser:
            logger.error("❌ Could not setup Chrome")
            return False
        
        logger.info("✅ Chrome connected\n")
        
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
                
        except Exception as e:
            logger.error(f"❌ Failed to get page: {e}")
            return False
        
        # Set up monitoring
        page.on("response", lambda resp: asyncio.create_task(monitor.monitor_response(resp)))
        
        try:
            # Load homepage
            logger.info("="*80)
            logger.info("LOADING BET365 HOMEPAGE")
            logger.info("="*80 + "\n")
            
            await page.goto('https://www.on.bet365.ca/', wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)
            
            logger.info("✅ Homepage loaded\n")
            
            # Dismiss popups
            await dismiss_bet365_popups(page, logger)
            await asyncio.sleep(2)
            
            # Navigate to NBA
            logger.info("="*80)
            logger.info("NAVIGATING TO NBA")
            logger.info("="*80 + "\n")
            
            nba_url = 'https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/'
            logger.info(f"Going to: {nba_url}")
            
            await page.goto(nba_url, wait_until='domcontentloaded', timeout=30000)
            
            logger.info("\n⏱️ Waiting 15 seconds for odds data to load...")
            await asyncio.sleep(15)
            
            # Results
            logger.info("\n" + "="*80)
            logger.info("📊 RESULTS")
            logger.info("="*80)
            logger.info(f"Total API calls: {len(monitor.all_api_calls)}")
            logger.info(f"Odds data responses: {len(monitor.odds_responses)}")
            
            if len(monitor.odds_responses) > 0:
                logger.info("\n✅ SUCCESS! Found odds data:")
                for idx, odds in enumerate(monitor.odds_responses, 1):
                    logger.info(f"  {idx}. {odds['size']:,} bytes from {odds['url'][:80]}...")
            else:
                logger.error("\n❌ NO ODDS DATA FOUND!")
                logger.error("\nPossible reasons:")
                logger.error("  1. Cloudflare/anti-bot is blocking API requests")
                logger.error("  2. Page is not fully loading")
                logger.error("  3. Bet365 detected automation")
                logger.error("  4. Different API endpoint being used")
                
                if len(monitor.all_api_calls) > 0:
                    logger.error("\nAPI calls that WERE made:")
                    for call in monitor.all_api_calls[:10]:
                        logger.error(f"  - {call['url'][:100]}...")
                else:
                    logger.error("\n⚠️ NO API calls were made at all!")
                    logger.error("  This suggests page is completely blocked")
            
            logger.info("="*80)
            
            # Keep open
            logger.info("\n🔍 Browser kept open for inspection")
            logger.info("Check if you can see NBA games and odds manually")
            logger.info("Press Ctrl+C when done...\n")
            
            try:
                await asyncio.sleep(999999)
            except KeyboardInterrupt:
                logger.info("\n👋 Shutting down...")
                
        except Exception as e:
            logger.error(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n\n👋 Interrupted")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
