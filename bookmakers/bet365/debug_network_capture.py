"""
Debug Network Capture Script for Bet365
========================================
This script monitors all network activity when opening bet365 to help diagnose
why no data is being returned.

Features:
- Captures ALL network requests and responses
- Logs response sizes, status codes, content types
- Saves full response bodies for analysis
- Uses chrome_helper (manual Chrome setup - NEVER driver-based)
- Detailed debugging output

Usage:
    python debug_network_capture.py
    python debug_network_capture.py --url "https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/"
"""
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import argparse

from patchright.async_api import async_playwright
# Import from parent directory
sys.path.append(str(Path(__file__).parent.parent))
from chrome_helper import setup_chrome_browser, dismiss_bet365_popups, verify_bet365_loaded

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NetworkDebugger:
    """Capture and analyze network traffic to bet365"""
    
    def __init__(self, output_dir: str = "network_debug_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.requests_log: List[Dict] = []
        self.responses_log: List[Dict] = []
        self.captured_data: List[Dict] = []
        
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
    def _sanitize_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        import re
        # Extract meaningful parts
        filename = url.replace('https://', '').replace('http://', '')
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        return filename[:100]  # Limit length
    
    async def log_request(self, request):
        """Log outgoing request"""
        try:
            request_info = {
                'timestamp': datetime.now().isoformat(),
                'url': request.url,
                'method': request.method,
                'headers': dict(request.headers),
                'resource_type': request.resource_type,
                'is_navigation': request.is_navigation_request(),
            }
            
            self.requests_log.append(request_info)
            
            # Log interesting requests
            if 'bet365' in request.url.lower():
                logger.info(f"📤 REQUEST: {request.method} {request.url[:100]}...")
                
        except Exception as e:
            logger.warning(f"Error logging request: {e}")
    
    async def log_response(self, response):
        """Log incoming response and capture body"""
        try:
            response_info = {
                'timestamp': datetime.now().isoformat(),
                'url': response.url,
                'status': response.status,
                'status_text': response.status_text,
                'headers': dict(response.headers),
                'request_method': response.request.method,
                'resource_type': response.request.resource_type,
            }
            
            # Try to get response body
            body = None
            body_text = None
            body_size = 0
            content_type = response.headers.get('content-type', '')
            
            try:
                body_text = await response.text()
                body_size = len(body_text) if body_text else 0
                response_info['body_size'] = body_size
                response_info['content_type'] = content_type
                
                # Parse JSON if applicable
                if 'json' in content_type and body_text:
                    try:
                        body = json.loads(body_text)
                    except:
                        pass
                        
            except Exception as e:
                response_info['body_error'] = str(e)
                logger.debug(f"Could not read body from {response.url[:80]}: {e}")
            
            self.responses_log.append(response_info)
            
            # Log interesting responses
            if 'bet365' in response.url.lower():
                status_icon = "✅" if 200 <= response.status < 300 else "⚠️" if response.status < 400 else "❌"
                logger.info(f"{status_icon} RESPONSE: {response.status} | {body_size:,} bytes | {response.url[:80]}...")
                
                # Save significant bet365 responses
                if body_size > 500 and response.status == 200:
                    captured = {
                        'timestamp': datetime.now().isoformat(),
                        'url': response.url,
                        'status': response.status,
                        'size': body_size,
                        'content_type': content_type,
                        'body': body_text,
                    }
                    
                    self.captured_data.append(captured)
                    
                    # Save to individual file
                    filename = self._sanitize_filename(response.url)
                    timestamp = datetime.now().strftime('%H%M%S')
                    filepath = self.output_dir / f"{self.session_id}_{timestamp}_{filename}.txt"
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(f"URL: {response.url}\n")
                        f.write(f"Status: {response.status}\n")
                        f.write(f"Size: {body_size:,} bytes\n")
                        f.write(f"Content-Type: {content_type}\n")
                        f.write(f"Timestamp: {datetime.now().isoformat()}\n")
                        f.write("="*80 + "\n\n")
                        f.write(body_text or "")
                    
                    logger.info(f"💾 Saved response to: {filepath.name}")
                    
                    # Log preview
                    if body_text:
                        preview = body_text[:200].replace('\n', ' ')
                        logger.info(f"📄 Preview: {preview}...")
                        
                        # Check for common patterns
                        if 'PA;' in body_text and 'MA;' in body_text:
                            logger.info("🎯 Response contains PA/MA patterns (bet365 data format)")
                        elif 'error' in body_text.lower() or 'not found' in body_text.lower():
                            logger.warning("⚠️ Response may contain error message")
                        elif len(body_text) < 1000:
                            logger.warning("⚠️ Response is quite small - may be empty or error")
                            
            elif 'cloudflare' in response.url.lower():
                logger.warning(f"☁️ Cloudflare response: {response.status} | {response.url[:80]}...")
                
        except Exception as e:
            logger.warning(f"Error logging response from {response.url[:80]}: {e}")
    
    def save_summary(self):
        """Save summary of all network activity"""
        summary = {
            'session_id': self.session_id,
            'timestamp': datetime.now().isoformat(),
            'total_requests': len(self.requests_log),
            'total_responses': len(self.responses_log),
            'captured_data_count': len(self.captured_data),
            'requests': self.requests_log,
            'responses': self.responses_log,
        }
        
        summary_file = self.output_dir / f"{self.session_id}_network_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
        
        logger.info(f"📊 Saved network summary to: {summary_file}")
        
        # Save captured data separately
        if self.captured_data:
            captured_file = self.output_dir / f"{self.session_id}_captured_data.json"
            with open(captured_file, 'w', encoding='utf-8') as f:
                json.dump(self.captured_data, f, indent=2)
            logger.info(f"📦 Saved {len(self.captured_data)} captured responses to: {captured_file}")
        
        # Print statistics
        logger.info("\n" + "="*80)
        logger.info("📈 NETWORK ACTIVITY SUMMARY")
        logger.info("="*80)
        logger.info(f"Total Requests:  {len(self.requests_log)}")
        logger.info(f"Total Responses: {len(self.responses_log)}")
        logger.info(f"Captured Data:   {len(self.captured_data)} significant responses")
        
        # Response status breakdown
        status_counts = {}
        total_bytes = 0
        bet365_count = 0
        bet365_bytes = 0
        
        for resp in self.responses_log:
            status = resp.get('status', 0)
            status_counts[status] = status_counts.get(status, 0) + 1
            
            size = resp.get('body_size', 0)
            total_bytes += size
            
            if 'bet365' in resp.get('url', '').lower():
                bet365_count += 1
                bet365_bytes += size
        
        logger.info(f"\nStatus Code Breakdown:")
        for status in sorted(status_counts.keys()):
            logger.info(f"  {status}: {status_counts[status]} responses")
        
        logger.info(f"\nData Transfer:")
        logger.info(f"  Total: {total_bytes:,} bytes ({total_bytes/1024/1024:.2f} MB)")
        logger.info(f"  Bet365: {bet365_count} responses, {bet365_bytes:,} bytes ({bet365_bytes/1024/1024:.2f} MB)")
        
        logger.info("="*80 + "\n")


async def debug_network(target_url: str = "https://www.on.bet365.ca/", 
                       navigate_to: Optional[str] = None,
                       wait_seconds: int = 10):
    """
    Open bet365 and capture all network traffic
    
    Args:
        target_url: Initial URL to load (bet365 homepage)
        navigate_to: Optional URL to navigate to after initial load
        wait_seconds: How long to wait and monitor network activity
    """
    debugger = NetworkDebugger()
    
    logger.info("="*80)
    logger.info("🔍 BET365 NETWORK DEBUG SESSION")
    logger.info("="*80)
    logger.info(f"Session ID: {debugger.session_id}")
    logger.info(f"Output Directory: {debugger.output_dir}")
    logger.info(f"Target URL: {target_url}")
    if navigate_to:
        logger.info(f"Navigate To: {navigate_to}")
    logger.info(f"Monitor Duration: {wait_seconds} seconds")
    logger.info("="*80 + "\n")
    
    async with async_playwright() as playwright:
        # Use chrome_helper - NEVER use driver-based approach
        logger.info("🌐 Setting up Chrome browser (using chrome_helper)...")
        browser, chrome_manager = await setup_chrome_browser(playwright)
        
        if not browser:
            logger.error("❌ Could not setup Chrome browser")
            return False
        
        logger.info("✅ Chrome browser connected\n")
        
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
            
            logger.info("✅ Page object obtained\n")
            
        except Exception as e:
            logger.error(f"❌ Failed to get page: {e}")
            return False
        
        # Set up network listeners
        logger.info("🔌 Setting up network listeners...")
        page.on("request", lambda req: asyncio.create_task(debugger.log_request(req)))
        page.on("response", lambda resp: asyncio.create_task(debugger.log_response(resp)))
        logger.info("✅ Network listeners active\n")
        
        try:
            # Navigate to target URL
            logger.info(f"🌐 Navigating to: {target_url}")
            logger.info("="*80)
            await page.goto(target_url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(3)
            
            logger.info("✅ Page loaded\n")
            
            # Dismiss popups
            logger.info("🔕 Dismissing bet365 popups...")
            await dismiss_bet365_popups(page, logger)
            await asyncio.sleep(2)
            
            # Verify page loaded
            if not await verify_bet365_loaded(page, logger):
                logger.warning("⚠️ Page appears blank!")
                logger.warning("   This is a common issue - investigating...")
                
                # Try to get page content
                try:
                    content = await page.content()
                    logger.info(f"📄 Page HTML length: {len(content):,} characters")
                    
                    if len(content) < 1000:
                        logger.error("❌ Page HTML is suspiciously short")
                        logger.info("💡 This suggests Cloudflare or anti-bot protection")
                    else:
                        logger.info("✅ Page HTML looks substantial")
                        
                        # Check for specific patterns
                        if 'cloudflare' in content.lower():
                            logger.warning("☁️ Cloudflare detected in page content")
                        if 'challenge' in content.lower():
                            logger.warning("🛡️ Challenge/verification detected")
                        if 'bet365' in content.lower():
                            logger.info("🎯 Bet365 branding found in page")
                            
                except Exception as e:
                    logger.error(f"❌ Could not get page content: {e}")
            else:
                logger.info("✅ Page verified as loaded\n")
            
            # Navigate to specific section if requested
            if navigate_to:
                logger.info(f"\n🎯 Navigating to specific section:")
                logger.info(f"   {navigate_to}")
                logger.info("="*80)
                
                await page.goto(navigate_to, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(3)
                logger.info("✅ Section loaded\n")
            
            # Wait and monitor
            logger.info(f"⏱️ Monitoring network activity for {wait_seconds} seconds...")
            logger.info("="*80 + "\n")
            
            await asyncio.sleep(wait_seconds)
            
            logger.info("\n" + "="*80)
            logger.info("✅ Monitoring complete")
            logger.info("="*80 + "\n")
            
        except Exception as e:
            logger.error(f"❌ Error during navigation: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            # Save results
            debugger.save_summary()
            
            # Keep browser open for manual inspection
            logger.info("\n" + "="*80)
            logger.info("🔍 BROWSER KEPT OPEN FOR MANUAL INSPECTION")
            logger.info("="*80)
            logger.info("You can now:")
            logger.info("  1. Manually inspect the page in Chrome")
            logger.info("  2. Open DevTools (F12) to see network activity")
            logger.info("  3. Check if data is being loaded")
            logger.info("  4. Look for any error messages")
            logger.info("\nPress Ctrl+C when done...")
            logger.info("="*80 + "\n")
            
            try:
                # Wait indefinitely until user presses Ctrl+C
                await asyncio.sleep(999999)
            except KeyboardInterrupt:
                logger.info("\n👋 Shutting down...")
    
    return True


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Debug network traffic when opening bet365',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Monitor bet365 homepage
  python debug_network_capture.py
  
  # Monitor specific NBA page
  python debug_network_capture.py --url "https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/"
  
  # Navigate from homepage to NBA section
  python debug_network_capture.py --navigate "https://www.on.bet365.ca/#/AC/B18/C20604387/D48/E1453/F10/"
  
  # Monitor for 30 seconds
  python debug_network_capture.py --wait 30
        """
    )
    
    parser.add_argument('--url', default='https://www.on.bet365.ca/',
                       help='Initial URL to load (default: bet365 homepage)')
    parser.add_argument('--navigate', dest='navigate_to',
                       help='URL to navigate to after initial load')
    parser.add_argument('--wait', type=int, default=10,
                       help='Seconds to monitor network (default: 10)')
    
    args = parser.parse_args()
    
    try:
        success = asyncio.run(debug_network(
            target_url=args.url,
            navigate_to=args.navigate_to,
            wait_seconds=args.wait
        ))
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
