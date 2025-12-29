"""
Chrome Helper Module for Cross-Platform Support
Handles Chrome/Chromium browser setup for both Windows and Ubuntu
This module is used by all scrapers in the unified odds system
"""
import os
import sys
import platform
import subprocess
import shutil
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple, Any

logger = logging.getLogger(__name__)


class ChromeManager:
    """Manages Chrome browser connection for automated scraping"""
    
    def __init__(self, debug_port: int = 9222):
        self.debug_port = debug_port
        self.platform = platform.system()
        self.chrome_process = None
        self.started_by_script = False
    
    def is_port_open(self, port: int = None) -> bool:
        """Check if Chrome is running on specified port"""
        import socket
        port = port or self.debug_port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except:
            return False
        
    def get_chrome_paths(self) -> list:
        """Get possible Chrome/Chromium executable paths based on platform"""
        if self.platform == "Windows":
            return [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Users\{}\AppData\Local\Google\Chrome\Application\chrome.exe".format(os.getenv('USERNAME')),
            ]
        elif self.platform == "Linux":
            return [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/snap/bin/chromium",
                "/opt/google/chrome/chrome",
            ]
        elif self.platform == "Darwin":  # macOS
            return [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Chromium.app/Contents/MacOS/Chromium",
            ]
        return []
    
    def find_chrome_executable(self) -> Optional[str]:
        """Find Chrome/Chromium executable on the system"""
        for path in self.get_chrome_paths():
            if os.path.exists(path):
                logger.info(f"Found Chrome at: {path}")
                return path
        
        # Try using 'which' command on Linux/Mac
        if self.platform in ["Linux", "Darwin"]:
            try:
                result = subprocess.run(['which', 'google-chrome'], 
                                       capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    path = result.stdout.strip()
                    logger.info(f"Found Chrome via which: {path}")
                    return path
            except:
                pass
        
        return None
    
    def get_cache_dirs(self) -> list:
        """Get Chrome cache directories based on platform"""
        if self.platform == "Windows":
            base = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Default"
            return [
                base / "Cache",
                base / "Code Cache",
            ]
        elif self.platform == "Linux":
            base = Path.home() / ".config" / "google-chrome" / "Default"
            return [
                base / "Cache",
                base / "Code Cache",
                Path.home() / ".cache" / "google-chrome",
                Path.home() / ".cache" / "chromium",
            ]
        return []
    
    def clear_cache(self):
        """Clear Chrome cache to prevent stale data"""
        logger.info("🌐 Clearing Chrome cache...")
        for cache_dir in self.get_cache_dirs():
            if cache_dir.exists():
                try:
                    shutil.rmtree(cache_dir, ignore_errors=True)
                    logger.info(f"  ✓ Cleared {cache_dir}")
                except Exception as e:
                    logger.warning(f"  Could not clear {cache_dir}: {e}")
    
    def get_temp_profile_dir(self) -> Path:
        """Get temporary profile directory based on platform"""
        from datetime import datetime
        import tempfile
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if self.platform == "Windows":
            # Use proper temp directory
            temp_base = Path(tempfile.gettempdir())
            return temp_base / f"chrome_debug_{timestamp}"
        else:
            return Path(f"/tmp/chrome_debug_{timestamp}")
    
    def start_chrome(self, url: str = "https://www.bet365.com", headless: bool = False) -> bool:
        """
        Start Chrome with remote debugging enabled
        
        Args:
            url: Initial URL to load
            headless: Whether to run in headless mode (not recommended for Cloudflare sites)
        """
        # Check if Chrome is already running on the port
        if self.is_port_open():
            logger.info(f"✓ Chrome already running on port {self.debug_port}")
            return True
        
        chrome_exe = self.find_chrome_executable()
        
        if not chrome_exe:
            logger.error("❌ Chrome executable not found. Please install Chrome or Chromium.")
            logger.error("   Ubuntu: sudo apt install google-chrome-stable")
            logger.error("   Or: sudo apt install chromium-browser")
            return False
        
        temp_dir = self.get_temp_profile_dir()
        
        # Clean up old temp directory if exists
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
        
        # Create temp directory if it doesn't exist
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        chrome_args = [
            chrome_exe,
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={temp_dir}",
            "--disable-blink-features=AutomationControlled",  # Hide automation
        ]
        
        # Add platform-specific arguments
        if self.platform == "Linux":
            # CRITICAL: Do NOT use --headless on Linux for Cloudflare-protected sites
            # Bet365/Cloudflare detects headless mode and blocks access
            chrome_args.extend([
                "--no-sandbox",  # Required for Ubuntu VPS
                "--disable-dev-shm-usage",  # Prevent shared memory issues
            ])
            if headless:
                logger.warning("⚠️ Headless mode enabled - may be blocked by Cloudflare!")
                chrome_args.append("--headless=new")
        else:
            # Windows: show window for debugging
            if headless:
                chrome_args.append("--headless=new")
        
        chrome_args.append(url)
        
        try:
            if self.platform == "Windows":
                # Windows-specific process creation
                # DON'T hide window - Chrome needs visible window for debug port to work
                self.chrome_process = subprocess.Popen(
                    chrome_args,
                    shell=False
                )
            else:
                # Linux/Mac process creation
                # Ensure DISPLAY environment variable is passed (set by xvfb-run)
                env = os.environ.copy()
                
                # Log display info for debugging
                if 'DISPLAY' in env:
                    logger.info(f"Using DISPLAY: {env['DISPLAY']}")
                else:
                    logger.warning("⚠️ DISPLAY not set - Chrome may run in headless mode!")
                
                if hasattr(os, 'setpgrp'):
                    self.chrome_process = subprocess.Popen(
                        chrome_args,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env,  # Pass environment with DISPLAY
                        preexec_fn=os.setpgrp  # type: ignore
                    )
                else:
                    self.chrome_process = subprocess.Popen(
                        chrome_args,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env  # Pass environment with DISPLAY
                    )
            
            self.started_by_script = True
            logger.info(f"✓ Chrome started with PID: {self.chrome_process.pid}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start Chrome: {e}")
            return False
    
    async def connect_to_chrome(self, playwright, retries: int = 3):
        """Connect to Chrome instance via CDP with retries"""
        for attempt in range(retries):
            try:
                # Try IPv4 first (127.0.0.1), then localhost
                browser = await playwright.chromium.connect_over_cdp(
                    f'http://127.0.0.1:{self.debug_port}'
                )
                logger.info(f"✓ Connected to Chrome on port {self.debug_port}")
                return browser
            except Exception as e:
                # Try with localhost as fallback
                try:
                    browser = await playwright.chromium.connect_over_cdp(
                        f'http://localhost:{self.debug_port}'
                    )
                    logger.info(f"✓ Connected to Chrome on port {self.debug_port}")
                    return browser
                except Exception as e2:
                    if attempt < retries - 1:
                        logger.warning(f"Connection attempt {attempt + 1} failed, retrying...")
                        await asyncio.sleep(2)
                    else:
                        logger.error(f"❌ Failed to connect to Chrome after {retries} attempts: {e2}")
                        return None
    
    async def get_or_start_chrome(self, playwright, url: str = "https://www.bet365.com"):
        """Try to connect to existing Chrome, or start new instance"""
        # First try to connect to existing instance
        browser = await self.connect_to_chrome(playwright)
        
        if browser:
            logger.info("✓ Connected to existing Chrome instance")
            return browser
        
        # No existing instance, start new one
        logger.info(f"⚠️ No Chrome found on port {self.debug_port}, starting new instance...")
        
        if not self.start_chrome(url=url):
            return None
        
        # Wait for Chrome to start and verify port is open
        logger.info("Waiting for Chrome to start...")
        for i in range(10):
            await asyncio.sleep(0.5)
            if self.is_port_open():
                logger.info(f"✓ Chrome port {self.debug_port} is open")
                break
        else:
            logger.error("Chrome port did not open in time")
            return None
        
        # Additional wait for Chrome to be fully ready
        await asyncio.sleep(2)
        
        # Try to connect again with retries
        browser = await self.connect_to_chrome(playwright, retries=5)
        return browser
    
    def cleanup(self):
        """Cleanup Chrome process if started by script"""
        if self.started_by_script and self.chrome_process:
            try:
                logger.info("Cleaning up Chrome process...")
                self.chrome_process.terminate()
                self.chrome_process.wait(timeout=5)
            except:
                try:
                    self.chrome_process.kill()
                except:
                    pass


async def setup_chrome_browser(playwright, debug_port: int = 9222, url: str = "https://www.bet365.com") -> Tuple[Optional[Any], Optional[ChromeManager]]:
    """
    Setup Chrome browser for scraping with anti-detection measures
    
    Args:
        playwright: Playwright instance
        debug_port: Chrome remote debugging port
        url: Initial URL to load
        
    Returns: 
        (browser, chrome_manager) tuple
    """
    manager = ChromeManager(debug_port=debug_port)
    
    # Clear cache before starting
    manager.clear_cache()
    
    # Get or start Chrome
    browser = await manager.get_or_start_chrome(playwright, url=url)
    
    if not browser:
        logger.error("❌ Could not setup Chrome browser")
        return None, None
    
    # Inject anti-detection JavaScript into all new pages
    async def add_stealth_to_page(page):
        """Add stealth JavaScript to hide automation"""
        try:
            await page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Mock Chrome runtime with more methods
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {}
                };
                
                // Mock permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Mock platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                // Mock vendor
                Object.defineProperty(navigator, 'vendor', {
                    get: () => 'Google Inc.'
                });
                
                // Mock hardware
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 0
                });
                
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                
                // Mock getUserMedia
                navigator.mediaDevices = {
                    getUserMedia: () => Promise.resolve({}),
                    enumerateDevices: () => Promise.resolve([])
                };
                
                // Remove automation indicators
                delete navigator.__proto__.webdriver;
            """)
        except Exception as e:
            logger.warning(f"Could not add stealth script to page: {e}")
    
    # Apply stealth to any new page created
    try:
        browser.on('page', add_stealth_to_page)
    except:
        pass
    
    return browser, manager


# Convenience function for backwards compatibility
async def get_chrome_page(playwright, url: str = "https://www.bet365.com", debug_port: int = 9222):
    """Get a Chrome page ready for scraping"""
    browser, manager = await setup_chrome_browser(playwright, debug_port=debug_port, url=url)
    
    if not browser:
        return None, None, None
    
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
        
        return browser, page, manager
    
    except Exception as e:
        logger.error(f"❌ Failed to get page: {e}")
        if manager:
            manager.cleanup()
        return None, None, None
