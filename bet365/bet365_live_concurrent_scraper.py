#!/usr/bin/env python3
"""
PERSISTENT TAB POOL CONCURRENT LIVE BET365 SCRAPER
Enhanced with comprehensive extraction script supporting all sports
Features: Persistent tabs, redirect detection, dynamic tab lifecycle

CRITICAL FIX APPLIED FOR FLICKERING ISSUE:
- Replaced threading.Lock() with asyncio.Lock() (line ~73)
- Made _save_incremental_data() async (line ~485) 
- Added await to all _save_incremental_data() calls (lines ~465, ~473)

REASON: threading.Lock() doesn't work properly with asyncio coroutines.
Using asyncio.Lock() ensures proper synchronization of concurrent async 
operations, preventing race conditions where one sport's data overwrites another's.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from bet365_live_scraper import UltimateLiveScraper

class TabState:
    """Represents the state of a persistent browser tab"""

    def __init__(self, sport_code: str, sport_name: str):
        self.sport_code = sport_code
        self.sport_name = sport_name
        from typing import Any, Optional
        self.page: Optional[Any] = None
        self.url: str = f"https://www.bet365.ca/#/IP/{sport_code}/"
        self.is_redirected: bool = False
        self.last_check_time: Optional[datetime] = None
        self.last_match_time: Optional[datetime] = None
        self.consecutive_empty_checks = 0
        self.consecutive_redirects = 0
        self.is_active = True
        self.error_count = 0
        self.retry_after: Optional[datetime] = None  # When to retry after being closed due to redirects
        
    def __repr__(self):
        status = "REDIRECTED" if self.is_redirected else "ACTIVE" if self.is_active else "INACTIVE"
        return f"<Tab {self.sport_name} ({self.sport_code}): {status}, empty_checks={self.consecutive_empty_checks}>"


class ConcurrentLiveScraper(UltimateLiveScraper):
    """
    Enhanced live scraper with persistent tab pool and comprehensive extraction.
    
    Features:
    - Persistent browser tabs (one per sport)
    - Comprehensive extraction for all sports (Cricket, Badminton, Volleyball, etc.)
    - Redirect detection
    - Dynamic tab lifecycle management
    """
    
    # No hardcoded redirect URLs - we detect redirects dynamically
    # by checking if the final URL matches the intended sport URL
    
    def __init__(self, 
                 disable_broadcasting=False,
                 recheck_interval_minutes=5,
                 cleanup_threshold_checks=10,
                 broadcast_callback=None):
        """Initialize concurrent scraper with persistent tab pool"""
        super().__init__(disable_broadcasting=disable_broadcasting)
        
        from typing import Any, Optional
        self.tab_pool: Dict[str, TabState] = {}
        self.context: Optional[Any] = None
        self.browser_instance: Optional[Any] = getattr(self, 'browser_instance', None)
        
        self.recheck_interval = timedelta(minutes=recheck_interval_minutes)
        self.cleanup_threshold = cleanup_threshold_checks
        self.broadcast_callback = broadcast_callback
        
        # CRITICAL FIX: Use asyncio.Lock for proper async synchronization
        # threading.Lock() doesn't work with async code - causes race conditions!
        self._file_lock = asyncio.Lock()
        
        self.logger.info(f"Persistent tab pool scraper initialized")
        self.logger.info(f"  - Recheck interval: {recheck_interval_minutes} minutes")
        self.logger.info(f"  - Cleanup threshold: {cleanup_threshold_checks} empty checks")
    
    async def initialize_tab_pool(self, sport_codes: List[str]):
        """Initialize persistent tabs for all sports"""
        self.logger.info(f"Initializing persistent tab pool for {len(sport_codes)} sports...")
        
        if not self.context:
            self.context = await self.browser_instance.new_context()
        
        for sport_code in sport_codes:
            if sport_code in self.tab_pool:
                continue
            
            sport_info = self.sport_mappings.get(sport_code, {})
            sport_name = sport_info.get('name', sport_code)
            
            tab_state = TabState(sport_code, sport_name)
            
            try:
                tab_state.page = await self.context.new_page()
                self.logger.info(f"  Created tab for {sport_name}")
                
                await tab_state.page.goto(tab_state.url, wait_until='domcontentloaded', timeout=20000)
                await asyncio.sleep(1.5)
                
                current_url = tab_state.page.url
                tab_state.is_redirected = self.is_redirect_url(current_url)

                if tab_state.is_redirected:
                    self.logger.info(f"    {sport_name} redirected (no matches) - URL: {current_url}")
                else:
                    self.logger.info(f"    {sport_name} loaded successfully - URL: {current_url}")
                
                tab_state.last_check_time = datetime.now()
                self.tab_pool[sport_code] = tab_state
                
            except Exception as e:
                self.logger.error(f"  Failed to create tab for {sport_name}: {e}")
                tab_state.error_count += 1
                if tab_state.page:
                    await tab_state.page.close()
        
        active_tabs = sum(1 for t in self.tab_pool.values() if t.is_active)
        redirected_tabs = sum(1 for t in self.tab_pool.values() if t.is_redirected)
        
        self.logger.info(f"Tab pool initialized: {active_tabs} active, {redirected_tabs} redirected")
    
    def is_redirect_url(self, url: str, intended_sport_code: Optional[str] = None) -> bool:
        """
        Check if URL is redirected by comparing the sport code in the URL with the intended sport code.
        A page is ONLY marked as redirected if the sport code in the final URL differs from the
        intended sport code, indicating bet365 redirected us to a different sport's page.
        """
        url_normalized = url.split('?')[0].rstrip('/')

        # Extract sport code from the actual URL  
        # Format: https://www.bet365.ca/#/IP/B16/ or https://on.bet365.ca/#/IP/B16/
        if '/#/IP/' in url_normalized:
            url_parts = url_normalized.split('/#/IP/')
            if len(url_parts) == 2:
                actual_sport_code = url_parts[1].strip('/').upper()
            else:
                # Couldn't extract sport code - likely redirected to home
                if intended_sport_code:
                    self.logger.debug(f"No sport code found in URL: {url_normalized}")
                    return True
                return False
        else:
            # No /#/IP/ pattern - definitely redirected
            if intended_sport_code:
                self.logger.debug(f"No IP pattern in URL: {url_normalized}")
                return True
            return False

        # If we have an intended sport code, compare them
        if intended_sport_code:
            intended_upper = intended_sport_code.upper()
            
            # CRITICAL: Only mark as redirected if the sport codes don't match
            # If they match, the page is correct even if no matches are currently available
            if actual_sport_code != intended_upper:
                self.logger.warning(f"Sport code mismatch: Expected {intended_upper}, got {actual_sport_code} in URL {url_normalized}")
                return True
            else:
                # Sport codes match - this is the correct page
                self.logger.debug(f"Sport code match confirmed: {actual_sport_code} == {intended_upper}")
                return False

        # No intended code to compare - not a redirect
        return False
    
    async def extract_from_tab(self, tab_state: TabState) -> Dict[str, Any]:
        """Extract data from a persistent tab with intelligent redirection handling"""
        start_time = asyncio.get_event_loop().time()
        try:
            # Check if this tab is waiting for retry after being closed
            if tab_state.retry_after and datetime.now() < tab_state.retry_after:
                # Still in retry wait period
                return {
                    'sport': tab_state.sport_name,
                    'code': tab_state.sport_code,
                    'matches': [],
                    'status': 'WAITING_RETRY',
                    'redirected': True,
                    'retry_at': tab_state.retry_after.isoformat(),
                    'extraction_time': 0
                }
            
            # If retry time has passed, try to reopen the tab
            if tab_state.retry_after and datetime.now() >= tab_state.retry_after:
                self.logger.info(f"Retry time reached for {tab_state.sport_name}, reopening tab...")
                tab_state.retry_after = None
                tab_state.is_redirected = False
                tab_state.is_active = True
                tab_state.consecutive_redirects = 0
                # Create new page
                if not self.context:
                    self.context = await self.browser_instance.new_context()
                tab_state.page = await self.context.new_page()
                await tab_state.page.goto(tab_state.url, wait_until='domcontentloaded', timeout=20000)
                await asyncio.sleep(1.5)
            
            if not tab_state.page:
                await self.ensure_tab_page(tab_state)

            current_url = tab_state.page.url
            was_redirected = tab_state.is_redirected
            tab_state.is_redirected = self.is_redirect_url(current_url, tab_state.sport_code)

            # CRITICAL: If redirected to a different sport, close THIS TAB ONLY and schedule retry
            if tab_state.is_redirected:
                if not was_redirected:
                    self.logger.warning(f"  {tab_state.sport_name} redirected to different sport page: {current_url}")
                    self.logger.info(f"  Closing tab for {tab_state.sport_name} (not entire browser)")
                    
                    # Close ONLY this specific tab/page, not the entire browser
                    try:
                        if tab_state.page:
                            await tab_state.page.close()
                            tab_state.page = None
                            self.logger.info(f"  Tab closed successfully for {tab_state.sport_name}")
                    except Exception as e:
                        self.logger.error(f"  Error closing tab for {tab_state.sport_name}: {e}")
                    
                    # Mark as inactive and schedule retry in 30 minutes
                    tab_state.is_active = False
                    tab_state.consecutive_redirects = 0
                    tab_state.consecutive_empty_checks = 0
                    tab_state.retry_after = datetime.now() + timedelta(minutes=30)
                    self.logger.info(f"  {tab_state.sport_name} will retry at {tab_state.retry_after.strftime('%H:%M:%S')}")

                return {
                    'sport': tab_state.sport_name,
                    'code': tab_state.sport_code,
                    'matches': [],  # NEVER return matches from redirected URLs
                    'status': 'REDIRECTED',
                    'matches_found': 0,
                    'redirected': True,
                    'url': current_url
                }

            # If we were previously redirected but now we're back to the correct sport, reactivate
            if was_redirected and not tab_state.is_redirected:
                self.logger.info(f"  {tab_state.sport_name} back to correct sport URL: {current_url}")
                tab_state.is_active = True
                tab_state.retry_after = None  # Clear retry timer

            # Reset redirect counters if no longer redirected
            if was_redirected and not tab_state.is_redirected:
                self.logger.info(f"  {tab_state.sport_name} no longer redirected - back to normal")
                tab_state.consecutive_redirects = 0

            # Only extract if page is still valid
            if not tab_state.page or tab_state.page.is_closed():
                self.logger.warning(f"Page is closed for {tab_state.sport_name}, skipping extraction")
                return {
                    'sport': tab_state.sport_name,
                    'code': tab_state.sport_code,
                    'matches': [],
                    'status': 'PAGE_CLOSED',
                    'matches_found': 0,
                    'redirected': False,
                    'url': tab_state.url
                }

            matches = await self.extract_matches_from_page(tab_state.page, tab_state.sport_code)

            elapsed = asyncio.get_event_loop().time() - start_time
            self.logger.debug(f"[TAB] {tab_state.sport_code} extracted {len(matches)} matches, elapsed={elapsed:.3f}s")

            tab_state.last_check_time = datetime.now()

            if matches:
                tab_state.consecutive_empty_checks = 0
                tab_state.consecutive_redirects = 0
                tab_state.last_match_time = datetime.now()
                tab_state.error_count = 0
                status = 'ACTIVE'
            else:
                tab_state.consecutive_empty_checks += 1
                status = 'NO MATCHES'

            return {
                'sport': tab_state.sport_name,
                'code': tab_state.sport_code,
                'matches': matches,
                'status': status,
                'matches_found': len(matches),
                'redirected': False,
                'url': current_url
            }

        except Exception as e:
            self.logger.error(f"  {tab_state.sport_name} extraction error: {e}")
            tab_state.error_count += 1

            return {
                'sport': tab_state.sport_name,
                'code': tab_state.sport_code,
                'matches': [],
                'status': 'ERROR',
                'matches_found': 0,
                'redirected': False,
                'error': str(e)
            }
    
    async def extract_matches_from_page(self, page, sport_code: str) -> List[Dict]:
        """Extract matches from a page using comprehensive extraction"""
        try:
            # Check if page is still valid before extraction
            if not page or page.is_closed():
                self.logger.warning(f"Page is closed or invalid for {sport_code}")
                return []

            sport_data = await self.extract_live_betting_data(page, sport_code)
            return sport_data.get('matches', []) if sport_data else []
        except Exception as e:
            self.logger.error(f"Error extracting matches from page: {e}")
            # Don't let page extraction errors crash the entire scraper
            return []

    async def ensure_tab_page(self, tab_state: TabState):
        """Ensure a TabState has a live Playwright page"""
        try:
            if tab_state.page:
                return

            if not self.context:
                if not self.browser_instance:
                    self.logger.error(f"No browser instance for {tab_state.sport_name}")
                    tab_state.error_count += 1
                    return
                self.context = await self.browser_instance.new_context()

            tab_state.page = await self.context.new_page()
            await tab_state.page.goto(tab_state.url, wait_until='domcontentloaded', timeout=20000)
            await asyncio.sleep(1.0)

            current_url = tab_state.page.url
            tab_state.is_redirected = self.is_redirect_url(current_url)
            tab_state.last_check_time = datetime.now()
            self.logger.info(f"    Recreated page for {tab_state.sport_name}")

        except Exception as e:
            self.logger.error(f"    Failed to recreate page for {tab_state.sport_name}: {e}")
            tab_state.error_count += 1
    
    async def recheck_redirected_tabs(self):
        """Re-check tabs that were redirected"""
        now = datetime.now()
        rechecked = []
        
        for sport_code, tab_state in self.tab_pool.items():
            if not tab_state.is_redirected:
                continue
            
            if tab_state.last_check_time:
                time_since_check = now - tab_state.last_check_time
                if time_since_check < self.recheck_interval:
                    continue
            
            try:
                self.logger.info(f"  Re-checking {tab_state.sport_name}...")
                
                await tab_state.page.goto(tab_state.url, wait_until='domcontentloaded', timeout=20000)
                await asyncio.sleep(1.5)
                
                current_url = tab_state.page.url
                tab_state.is_redirected = self.is_redirect_url(current_url)
                tab_state.last_check_time = now
                
                if not tab_state.is_redirected:
                    self.logger.info(f"    {tab_state.sport_name} now has matches!")
                    tab_state.consecutive_redirects = 0
                else:
                    self.logger.info(f"    {tab_state.sport_name} still redirected")
                
                rechecked.append(sport_code)
                
            except Exception as e:
                self.logger.error(f"    Error re-checking {tab_state.sport_name}: {e}")
                tab_state.error_count += 1
        
        if rechecked:
            self.logger.info(f"Re-checked {len(rechecked)} redirected sports")
    
    async def cleanup_inactive_tabs(self):
        """Close tabs for sports that have been empty for too long"""
        to_cleanup = []
        
        for sport_code, tab_state in self.tab_pool.items():
            if tab_state.consecutive_empty_checks < self.cleanup_threshold:
                continue
            
            if tab_state.error_count > 3:
                continue
            
            to_cleanup.append(sport_code)
        
        for sport_code in to_cleanup:
            tab_state = self.tab_pool[sport_code]
            
            try:
                self.logger.info(f"  Closing inactive tab: {tab_state.sport_name}")
                
                if tab_state.page:
                    await tab_state.page.close()
                
                tab_state.is_active = False
                
            except Exception as e:
                self.logger.error(f"    Error closing tab for {tab_state.sport_name}: {e}")
        
        if to_cleanup:
            self.logger.info(f"Cleaned up {len(to_cleanup)} inactive tabs")
    
    async def reopen_inactive_tabs(self):
        """Periodically reopen tabs that were closed, respecting retry_after timing"""
        now = datetime.now()
        reopened = []

        for sport_code, tab_state in self.tab_pool.items():
            if tab_state.is_active:
                continue

            # Check if we're still in the retry cooldown period
            if tab_state.retry_after and now < tab_state.retry_after:
                remaining = tab_state.retry_after - now
                self.logger.debug(f"  {tab_state.sport_name} in retry cooldown: {remaining.total_seconds():.0f}s remaining")
                continue

            if tab_state.last_check_time:
                time_since_check = now - tab_state.last_check_time
                if time_since_check < self.recheck_interval:
                    continue

            try:
                retry_reason = "redirected" if tab_state.retry_after else "inactive"
                self.logger.info(f"  Reopening {retry_reason} tab for {tab_state.sport_name}...")

                tab_state.page = await self.context.new_page()

                await tab_state.page.goto(tab_state.url, wait_until='domcontentloaded', timeout=20000)
                await asyncio.sleep(1.5)

                current_url = tab_state.page.url
                tab_state.is_redirected = self.is_redirect_url(current_url, tab_state.sport_code)
                tab_state.last_check_time = now
                tab_state.is_active = True
                tab_state.consecutive_empty_checks = 0
                tab_state.consecutive_redirects = 0  # Reset redirect counter on reopen

                # Clear retry_after since we've successfully reopened
                tab_state.retry_after = None

                if not tab_state.is_redirected:
                    self.logger.info(f"    {tab_state.sport_name} reopened successfully - has matches!")
                else:
                    self.logger.info(f"    {tab_state.sport_name} reopened but still redirected")

                reopened.append(sport_code)

            except Exception as e:
                self.logger.error(f"    Error reopening tab for {tab_state.sport_name}: {e}")
                tab_state.error_count += 1

        if reopened:
            self.logger.info(f"Reopened {len(reopened)} inactive tabs")
    
    async def extract_all_tabs_incremental(self) -> List[Dict[str, Any]]:
        """Extract data from all active tabs concurrently, collecting all results before saving"""
        active_tabs = [tab for tab in self.tab_pool.values() if tab.is_active]

        if not active_tabs:
            self.logger.warning("No active tabs to extract from")
            return []

        # Create tasks for all tabs
        task_list = [self.extract_from_tab(tab) for tab in active_tabs]
        tab_list = active_tabs

        all_matches = []
        valid_results = []

        # Process results as they complete
        for completed_task in asyncio.as_completed(task_list):
            try:
                result = await completed_task

                if isinstance(result, Exception):
                    self.logger.error(f"Extraction error: {result}")
                    continue

                valid_results.append(result)

                # Process this result - collect matches but DON'T save yet
                if result.get('matches'):
                    sport_matches = result['matches']
                    all_matches.extend(sport_matches)
                    self.logger.info(f"  {result['sport']}: {result['matches_found']} matches (collected)")

                elif result.get('redirected'):
                    if result.get('matches_found', 0) > 0:
                        sport_matches = result['matches']
                        all_matches.extend(sport_matches)
                        self.logger.info(f"  {result['sport']}: {result['matches_found']} redirected matches (collected)")
                    else:
                        self.logger.info(f"  - {result['sport']}: Redirected (no matches)")
                else:
                    self.logger.info(f"  - {result['sport']}: No matches")

            except Exception as e:
                self.logger.error(f"Error processing completed task: {e}")

        # SAVE ALL COLLECTED DATA ONCE AT THE END OF THE EXTRACTION CYCLE
        if all_matches:
            await self._save_all_collected_data(valid_results)

        return valid_results

    async def _save_incremental_data(self, result: Dict[str, Any]):
        """
        Save data incrementally with proper sport-specific replacement.

        MERGE STRATEGY:
        - Load existing matches from all sports
        - Remove ALL old matches from the current sport
        - Add NEW matches from the current sport
        - Keep matches from all other sports unchanged
        """
        try:
            # Use asyncio.Lock for proper async synchronization
            async with self._file_lock:
                # Load existing data
                current_data = self.load_current_data()
                if not isinstance(current_data, dict):
                    current_data = {
                        'last_updated': datetime.now().isoformat(),
                        'session_id': f"{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                        'total_matches': 0,
                        'matches': [],
                        'data_changes_log': [],
                        'sports_breakdown': {}
                    }

                # Identify what we're updating
                existing_matches = current_data.get('matches', [])
                new_matches = result.get('matches', [])
                sport_name = result.get('sport', 'Unknown')
                sport_code = result.get('code', 'unknown')

                # CRITICAL FIX: Remove ALL matches from THIS sport
                matches_from_other_sports = []

                for match in existing_matches:
                    if not isinstance(match, dict):
                        continue

                    match_sport = match.get('sport', '').strip()
                    match_code = match.get('sport_code', match.get('code', '')).strip()

                    # Keep only matches from OTHER sports
                    is_same_sport = (
                        match_sport == sport_name or
                        match_code == sport_code or
                        match_sport.lower() == sport_name.lower()
                    )

                    if not is_same_sport:
                        matches_from_other_sports.append(match)

                # Log the merge operation
                removed_count = len(existing_matches) - len(matches_from_other_sports)
                self.logger.debug(
                    f"Sport merge for {sport_name}: "
                    f"Removed {removed_count} old matches, "
                    f"adding {len(new_matches)} new matches, "
                    f"keeping {len(matches_from_other_sports)} from other sports"
                )

                # Build merged list: other sports + new sport data
                merged_matches = list(matches_from_other_sports)

                # Add new matches with timestamps
                for new_match in new_matches:
                    if not isinstance(new_match, dict):
                        continue

                    new_match['last_updated'] = datetime.now().isoformat()
                    if 'first_seen' not in new_match:
                        new_match['first_seen'] = datetime.now().isoformat()

                    merged_matches.append(new_match)

                # Update data structure
                current_data['matches'] = merged_matches
                current_data['total_matches'] = len(merged_matches)
                current_data['last_updated'] = datetime.now().isoformat()

                # Calculate sports breakdown
                sports_breakdown = {}
                for match in merged_matches:
                    sport = match.get('sport', 'Unknown')
                    sports_breakdown[sport] = sports_breakdown.get(sport, 0) + 1
                current_data['sports_breakdown'] = sports_breakdown

                # Save the merged data
                self.save_live_results(current_data)

                # Log successful merge
                sports_list = ', '.join([f"{s}:{c}" for s, c in sports_breakdown.items()])
                self.logger.info(
                    f"✓ Merged {sport_name}: {len(new_matches)} matches | "
                    f"Total: {len(merged_matches)} matches ({sports_list})"
                )

                # Also save statistics snapshot
                self._save_statistics_snapshot(current_data)

        except Exception as e:
            self.logger.error(f"Error saving incremental data: {e}")
            import traceback
            self.logger.error(traceback.format_exc())

    async def _save_all_collected_data(self, all_results: List[Dict[str, Any]]):
        """
        Save all collected data from all sports in a single atomic operation.
        This prevents flickering by ensuring the file is only written once per extraction cycle.
        """
        try:
            # Use asyncio.Lock for proper async synchronization
            async with self._file_lock:
                # Start with empty data structure
                current_data = {
                    'last_updated': datetime.now().isoformat(),
                    'session_id': f"{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'total_matches': 0,
                    'matches': [],
                    'data_changes_log': [],
                    'sports_breakdown': {}
                }

                all_matches = []

                # Collect all matches from all results
                for result in all_results:
                    if result.get('matches'):
                        sport_matches = result['matches']
                        # Add timestamps to matches
                        for match in sport_matches:
                            if isinstance(match, dict):
                                match['last_updated'] = datetime.now().isoformat()
                                if 'first_seen' not in match:
                                    match['first_seen'] = datetime.now().isoformat()
                        all_matches.extend(sport_matches)

                # Deduplicate matches across all sports
                all_matches = self.deduplicate_matches(all_matches)

                # Update data structure
                current_data['matches'] = all_matches
                current_data['total_matches'] = len(all_matches)
                current_data['last_updated'] = datetime.now().isoformat()

                # Calculate sports breakdown
                sports_breakdown = {}
                for match in all_matches:
                    sport = match.get('sport', 'Unknown')
                    sports_breakdown[sport] = sports_breakdown.get(sport, 0) + 1
                current_data['sports_breakdown'] = sports_breakdown

                # Save the complete data atomically
                self.save_live_results(current_data)

                # Log successful save
                sports_list = ', '.join([f"{s}:{c}" for s, c in sports_breakdown.items()])
                self.logger.info(
                    f"✓ Saved complete extraction cycle: {len(all_matches)} matches ({sports_list})"
                )

                # Also save statistics snapshot
                self._save_statistics_snapshot(current_data)

        except Exception as e:
            self.logger.error(f"Error saving all collected data: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
    def save_live_results(self, results: Dict):
        """Override parent method to save statistics without match details"""
        sports_count = {}
        for match in results.get('matches', []):
            if isinstance(match, dict):
                sport = match.get('sport', 'Unknown')
                sports_count[sport] = sports_count.get(sport, 0) + 1

        output = {
            'extraction_info': {
                'timestamp': datetime.now().isoformat(),
                'session_id': self.session_id,
                'source': 'bet365.ca',
                'method': 'CONCURRENT-LIVE-SCRAPER',
                'total_matches': len(results.get('matches', [])),
                'live_matches': results.get('summary', {}).get('live_matches', 0)
            },
            'sports_breakdown': sports_count,
            # Removed 'matches_data' to avoid duplicating match details
            'summary': results.get('summary', {})
        }

        try:
            with open(self.statistics_file, 'w', encoding='utf-8') as f:
                json.dump(output, f, indent=2, ensure_ascii=False)
            self.logger.info("Statistics saved successfully (no match details)")
        except Exception as e:
            self.logger.error(f"Failed to save statistics: {e}")

        # Save main data file with full match details - ATOMIC WRITE
        dashboard_data = {
            'last_updated': datetime.now().isoformat(),
            'session_id': self.session_id,
            'total_matches': len(results.get('matches', [])),
            'matches': results.get('matches', []),
            'sports_breakdown': sports_count
        }

        # ATOMIC FILE WRITE: Write to temp file first, then rename
        temp_file = self.current_data_file + '.tmp'
        try:
            # Write to temporary file
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(dashboard_data, f, indent=2, ensure_ascii=False)

            # Atomic rename (this is atomic on most filesystems)
            os.replace(temp_file, self.current_data_file)

            self.logger.info(f"Dashboard data saved atomically to {self.current_data_file}")

        except Exception as e:
            self.logger.error(f"Failed to save dashboard data: {e}")
            # Clean up temp file if it exists
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception:
                pass

    def _save_statistics_snapshot(self, data: Dict[str, Any]):
        """Save a separate statistics snapshot for monitoring - URL and update tracking (no match details)"""
        try:
            stats_file = Path('bet365_live_statistics.json')

            # Load existing stats to maintain historical data
            existing_stats = {}
            if stats_file.exists():
                try:
                    with open(stats_file, 'r', encoding='utf-8') as f:
                        existing_stats = json.load(f)
                except Exception:
                    existing_stats = {}

            # Initialize stats structure
            if 'url_tracking' not in existing_stats:
                existing_stats['url_tracking'] = {}
            if 'match_updates' not in existing_stats:
                existing_stats['match_updates'] = {}
            if 'extraction_cycles' not in existing_stats:
                existing_stats['extraction_cycles'] = 0

            # Update extraction cycle count
            existing_stats['extraction_cycles'] += 1
            existing_stats['last_updated'] = datetime.now().isoformat()

            # Track URL statistics (no match details)
            matches = data.get('matches', [])
            url_match_counts = {}

            # Count matches per URL/sport
            for match in matches:
                if not isinstance(match, dict):
                    continue

                sport_code = match.get('sport_code', match.get('code', 'unknown'))
                sport_name = match.get('sport', 'unknown')
                url_key = f"{sport_code}_{sport_name}"

                if url_key not in url_match_counts:
                    url_match_counts[url_key] = {
                        'sport_code': sport_code,
                        'sport_name': sport_name,
                        'count': 0
                    }
                url_match_counts[url_key]['count'] += 1

            # Update URL tracking
            for url_key, count_info in url_match_counts.items():
                if url_key not in existing_stats['url_tracking']:
                    existing_stats['url_tracking'][url_key] = {
                        'sport_code': count_info['sport_code'],
                        'sport_name': count_info['sport_name'],
                        'total_matches_ever': 0,
                        'current_matches': 0,
                        'update_cycles': 0,
                        'last_seen': None,
                        'first_seen': datetime.now().isoformat()
                    }

                url_stats = existing_stats['url_tracking'][url_key]
                url_stats['current_matches'] = count_info['count']
                url_stats['total_matches_ever'] = max(url_stats['total_matches_ever'], count_info['count'])
                url_stats['update_cycles'] += 1
                url_stats['last_seen'] = datetime.now().isoformat()

            # Track individual match updates (no match details, just counts)
            for match in matches:
                if not isinstance(match, dict):
                    continue

                teams = match.get('teams', {})
                home_team = teams.get('home', '').strip()
                away_team = teams.get('away', '').strip()
                sport_code = match.get('sport_code', match.get('code', 'unknown'))

                if home_team and away_team:
                    match_key = f"{sport_code}|{home_team} vs {away_team}"

                    if match_key not in existing_stats['match_updates']:
                        existing_stats['match_updates'][match_key] = {
                            'sport_code': sport_code,
                            'home_team': home_team,
                            'away_team': away_team,
                            'update_count': 0,
                            'first_seen': datetime.now().isoformat(),
                            'last_updated': datetime.now().isoformat(),
                            'has_odds': False,
                            'is_live': False
                        }

                    match_stats = existing_stats['match_updates'][match_key]
                    match_stats['update_count'] += 1
                    match_stats['last_updated'] = datetime.now().isoformat()
                    match_stats['has_odds'] = match.get('has_odds', False)
                    match_stats['is_live'] = match.get('live_fields', {}).get('is_live', False)

            # Calculate summary statistics
            existing_stats['summary'] = {
                'total_urls_tracked': len(existing_stats['url_tracking']),
                'total_matches_tracked': len(existing_stats['match_updates']),
                'extraction_cycles': existing_stats['extraction_cycles'],
                'most_active_url': max(existing_stats['url_tracking'].items(),
                                     key=lambda x: x[1]['update_cycles'])[0] if existing_stats['url_tracking'] else None,
                'most_updated_match': max(existing_stats['match_updates'].items(),
                                        key=lambda x: x[1]['update_count'])[0] if existing_stats['match_updates'] else None,
                'urls_with_matches': sum(1 for u in existing_stats['url_tracking'].values() if u['current_matches'] > 0),
                'total_current_matches': sum(u['current_matches'] for u in existing_stats['url_tracking'].values())
            }

            # Clean up old match tracking (keep only recent ones)
            cutoff_date = datetime.now() - timedelta(hours=24)
            to_remove = []
            for match_key, match_data in existing_stats['match_updates'].items():
                try:
                    last_updated = datetime.fromisoformat(match_data['last_updated'])
                    if last_updated < cutoff_date:
                        to_remove.append(match_key)
                except Exception:
                    to_remove.append(match_key)

            for match_key in to_remove:
                del existing_stats['match_updates'][match_key]

            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(existing_stats, f, indent=2, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Error saving statistics snapshot: {e}")
    
    async def run_concurrent_monitoring(self, sport_codes=None, interval_seconds=10, duration_seconds: Optional[int]=None):
        """Run real-time monitoring with persistent tab pool"""
        self.logger.info(f"Starting PERSISTENT TAB POOL MONITORING (interval: {interval_seconds}s)")
        
        if sport_codes is None:
            sport_codes = list(self.sport_mappings.keys())
        
        extraction_count = 0
        last_recheck_time = datetime.now()
        last_cleanup_time = datetime.now()
        last_reopen_time = datetime.now()
        
        try:
            if not self.check_server_availability():
                self.logger.error("Server unavailable")
                return

            self.load_current_data()

            browser_connected = False
            if await self.launch_manual_browser():
                if await self.connect_playwright_to_browser():
                    if await self.wait_for_bet365_load():
                        browser_connected = True
                        self.logger.info("Connected to existing browser session")

            if not browser_connected:
                self.logger.info("Launching new isolated browser for tab pool")
                self.kill_existing_browsers()

                if not self.launch_isolated_chrome():
                    return

                if not await self.connect_playwright_to_browser():
                    return

                if not await self.wait_for_bet365_load():
                    self.logger.error("Aborting monitoring - bet365 failed to load")
                    return
            
            await self.initialize_tab_pool(sport_codes)
            
            self.logger.info(f"Monitoring {len(self.tab_pool)} sports with persistent tabs")
            
            run_start_time = datetime.now()
            while True:
                extraction_count += 1
                start_time = asyncio.get_event_loop().time()
                now = datetime.now()
                
                self.logger.info(f"\n{'='*60}")
                self.logger.info(f"[EXTRACTION #{extraction_count}] {now.strftime('%H:%M:%S')}")
                self.logger.info(f"{'='*60}")
                
                try:
                    if (now - last_recheck_time) >= self.recheck_interval:
                        self.logger.info("Performing periodic re-check of redirected tabs...")
                        await self.recheck_redirected_tabs()
                        last_recheck_time = now
                    
                    if (now - last_cleanup_time) >= (self.recheck_interval * 2):
                        self.logger.info("Performing cleanup of inactive tabs...")
                        await self.cleanup_inactive_tabs()
                        last_cleanup_time = now
                    
                    if (now - last_reopen_time) >= self.recheck_interval:
                        self.logger.info("Checking for inactive tabs to reopen...")
                        await self.reopen_inactive_tabs()
                        last_reopen_time = now
                    
                    self.logger.info("Extracting from all active tabs...")
                    results = await self.extract_all_tabs_incremental()
                    
                    all_matches = []
                    active_sports = 0
                    redirected_sports = 0

                    for result in results:
                        if result.get('matches'):
                            active_sports += 1
                            all_matches.extend(result['matches'])
                            self.logger.info(f"  {result['sport']}: {result['matches_found']} matches")
                        elif result.get('redirected'):
                            redirected_sports += 1
                            if extraction_count % 5 == 0:
                                self.logger.info(f"  - {result['sport']}: Redirected (no matches)")
                        else:
                            self.logger.info(f"  - {result['sport']}: No matches")

                    all_matches = self.deduplicate_matches(all_matches)
                    
                    changes = self.detect_data_changes(all_matches)
                    self.process_data_changes(changes)
                    
                    elapsed = asyncio.get_event_loop().time() - start_time
                    
                    if self.broadcast_callback:
                        try:
                            dashboard_data = {
                                "type": "data_update",
                                "matches": all_matches,
                                "total_matches": len(all_matches),
                                "live_matches": len([m for m in all_matches if m.get('status', '').lower() == 'live']),
                                "extraction_count": extraction_count,
                                "timestamp": datetime.now().isoformat(),
                                "last_update": datetime.now().isoformat(),
                                "concurrent_mode": True,
                                "persistent_tabs": True,
                                "stats": {
                                    "active_sports": active_sports,
                                    "redirected_sports": redirected_sports,
                                    "new_matches": len(changes.get('new', [])),
                                    "updated_matches": len(changes.get('updated', [])),
                                    "removed_matches": len(changes.get('removed', [])),
                                    "active_tabs": sum(1 for t in self.tab_pool.values() if t.is_active),
                                    "inactive_tabs": sum(1 for t in self.tab_pool.values() if not t.is_active),
                                    "extraction_time": elapsed
                                }
                            }
                            await self.broadcast_callback(dashboard_data)
                        except Exception as e:
                            self.logger.error(f"Dashboard broadcast error: {e}")
                    
                    self.logger.info(f"\n{'='*60}")
                    self.logger.info(f"Extraction #{extraction_count} completed in {elapsed:.2f}s")
                    self.logger.info(f"Stats:")
                    self.logger.info(f"   - Total matches: {len(all_matches)}")
                    self.logger.info(f"   - Active sports: {active_sports}")
                    self.logger.info(f"   - Redirected sports: {redirected_sports}")
                    self.logger.info(f"   - New matches: {len(changes.get('new', []))}")
                    self.logger.info(f"   - Updated matches: {len(changes.get('updated', []))}")
                    self.logger.info(f"   - Removed matches: {len(changes.get('removed', []))}")
                    
                    active_tabs = sum(1 for t in self.tab_pool.values() if t.is_active)
                    inactive_tabs = sum(1 for t in self.tab_pool.values() if not t.is_active)
                    self.logger.info(f"   - Active tabs: {active_tabs}")
                    self.logger.info(f"   - Inactive tabs: {inactive_tabs}")
                    self.logger.info(f"{'='*60}\n")
                    
                except Exception as e:
                    self.logger.error(f"Extraction #{extraction_count} error: {e}")
                    import traceback
                    self.logger.error(traceback.format_exc())
                
                if duration_seconds and (datetime.now() - run_start_time).total_seconds() >= duration_seconds:
                    self.logger.info(f"Duration {duration_seconds}s reached, stopping monitor")
                    break

                await asyncio.sleep(interval_seconds)
        
        except KeyboardInterrupt:
            self.logger.info(f"\nMonitoring stopped after {extraction_count} extractions")
        
        except Exception as e:
            self.logger.error(f"Monitoring error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        
        finally:
            self.logger.info("Cleaning up tab pool...")
            for tab_state in self.tab_pool.values():
                if tab_state.page:
                    try:
                        await tab_state.page.close()
                    except Exception:
                        pass
            
            if self.context:
                try:
                    await self.context.close()
                except Exception:
                    pass
            
            await self.cleanup_isolated_browser()
    
    async def run_concurrent_extraction(self, sport_codes=None) -> Optional[Dict[str, Any]]:
        """Run single concurrent extraction using persistent tab pool"""
        self.logger.info("Starting PERSISTENT TAB POOL EXTRACTION...")

        if sport_codes is None:
            sport_codes = list(self.sport_mappings.keys())

        try:
            if not self.check_server_availability():
                self.logger.error("Server unavailable")
                return None

            self.kill_existing_browsers()

            if not await self.launch_manual_browser():
                return None

            if not await self.connect_playwright_to_browser():
                return None

            if not await self.wait_for_bet365_load():
                self.logger.error("bet365 failed to load")
                return None

            await self.initialize_tab_pool(sport_codes)

            results = await self.extract_all_tabs_incremental()
            
            all_matches = []

            for result in results:
                if result.get('matches'):
                    all_matches.extend(result['matches'])

            all_matches = self.deduplicate_matches(all_matches)
            
            changes = self.detect_data_changes(all_matches)
            self.process_data_changes(changes)
            
            extraction_results = {
                'timestamp': datetime.now().isoformat(),
                'matches': all_matches,
                'validation_results': results,
                'data_changes': changes,
                'summary': {
                    'total_matches': len(all_matches),
                    'live_matches': sum(1 for m in all_matches if m.get('live_fields', {}).get('is_live')),
                    'total_markets': sum(len(m.get('markets', [])) for m in all_matches),
                    'sports_processed': len(results),
                    'active_sports': sum(1 for v in results if v['status'] == 'ACTIVE'),
                    'redirected_sports': sum(1 for v in results if v.get('redirected')),
                    'total_tabs': len(self.tab_pool)
                }
            }
            
            self.save_live_results(extraction_results)
            
            self.logger.info(f"\nEXTRACTION COMPLETE")
            self.logger.info(f"Total matches: {len(all_matches)}")
            self.logger.info(f"Active sports: {extraction_results['summary']['active_sports']}/{len(results)}")
            self.logger.info(f"Redirected sports: {extraction_results['summary']['redirected_sports']}")
            
            return extraction_results
            
        except Exception as e:
            self.logger.error(f"Extraction error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return None
        
        finally:
            for tab_state in self.tab_pool.values():
                if tab_state.page:
                    try:
                        await tab_state.page.close()
                    except Exception:
                        pass
            
            if self.context:
                try:
                    await self.context.close()
                except Exception:
                    pass
            
            await self.cleanup_isolated_browser()

    def deduplicate_matches(self, all_matches):
        """Deduplicate matches based on team names and sport"""
        seen_matches = {}
        deduplicated = []
        collisions = 0

        for match in all_matches:
            if not isinstance(match, dict):
                continue

            teams = match.get('teams', {})
            home_team = teams.get('home', '').strip().lower()
            away_team = teams.get('away', '').strip().lower()

            if not home_team or not away_team:
                # If teams are missing, still include the match but use a different key
                match_key = f"no_teams_{id(match)}"
            else:
                sport_code = (match.get('sport_code') or match.get('code') or match.get('sport') or '').strip().lower()
                match_key = f"{sport_code}|{home_team}:{away_team}"

            if match_key not in seen_matches:
                seen_matches[match_key] = match
                deduplicated.append(match)
            else:
                existing = seen_matches[match_key]
                collisions += 1
                if self._is_better_match(existing, match):
                    seen_matches[match_key] = match
                    for i, m in enumerate(deduplicated):
                        if (m.get('teams', {}).get('home', '').strip().lower() == home_team and
                            m.get('teams', {}).get('away', '').strip().lower() == away_team):
                            deduplicated[i] = match
                            break

        self.logger.info(f"Deduplicated {len(all_matches)} matches to {len(deduplicated)} unique matches (collisions: {collisions})")
        return deduplicated

    def _is_better_match(self, existing, new):
        """Determine if new match has better data than existing"""
        existing_has_odds = bool(existing.get('odds', {}).get('home') or existing.get('odds', {}).get('away'))
        new_has_odds = bool(new.get('odds', {}).get('home') or new.get('odds', {}).get('away'))

        if new_has_odds and not existing_has_odds:
            return True

        existing_has_scores = bool(existing.get('scores', {}).get('home') != '0' or existing.get('scores', {}).get('away') != '0')
        new_has_scores = bool(new.get('scores', {}).get('home') != '0' or new.get('scores', {}).get('away') != '0')

        if new_has_scores and not existing_has_scores:
            return True

        existing_has_league = bool(existing.get('league'))
        new_has_league = bool(new.get('league'))

        if new_has_league and not existing_has_league:
            return True

        return False


async def main():
    """Main entry point for concurrent scraper"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Persistent Tab Pool Live Bet365 Scraper')
    parser.add_argument('--mode', choices=['single', 'monitor'], default='monitor',
                       help='Run mode: single extraction or continuous monitoring')
    parser.add_argument('--interval', type=int, default=1,
                       help='Update interval in seconds for monitoring mode (minimum: 1s, default: 1)')
    parser.add_argument('--recheck', type=int, default=5,
                       help='Re-check interval in minutes for redirected sports (default: 5)')
    parser.add_argument('--cleanup', type=int, default=10,
                       help='Close tab after this many consecutive empty checks (default: 10)')
    parser.add_argument('--sports', nargs='+',
                       help='Specific sport codes to monitor (e.g., B1 B12 B18)')
    parser.add_argument('--duration', type=int, default=None,
                       help='Total duration in seconds to run the monitor (optional)')
    
    args = parser.parse_args()
    
    scraper = ConcurrentLiveScraper(
        recheck_interval_minutes=args.recheck,
        cleanup_threshold_checks=args.cleanup
    )
    
    sport_codes = None
    if args.sports:
        valid_sports = []
        for sport in args.sports:
            if sport.upper() in scraper.sport_mappings:
                valid_sports.append(sport.upper())
            else:
                print(f"Warning: Unknown sport code '{sport}', skipping")
        sport_codes = valid_sports if valid_sports else None
    
    print("PERSISTENT TAB POOL LIVE BET365 SCRAPER")
    print("=" * 60)
    print(f"Mode: {args.mode}")
    print(f"Sports: {', '.join(sport_codes) if sport_codes else 'All'}")
    print(f"Update interval: {args.interval}s")
    print(f"Re-check interval: {args.recheck} minutes")
    print(f"Cleanup threshold: {args.cleanup} empty checks")
    print("=" * 60)
    
    if args.interval < 1:
        print("Interval too small, using minimum of 1 second")
        args.interval = 1

    if args.mode == 'single':
        await scraper.run_concurrent_extraction(sport_codes)
    else:
        await scraper.run_concurrent_monitoring(sport_codes, args.interval, duration_seconds=args.duration)


if __name__ == "__main__":
    asyncio.run(main())