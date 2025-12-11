#!/usr/bin/env python3
"""
ENHANCED INTELLIGENT SPORTS SCRAPER
Advanced bet365.ca pregame scraper with improved accuracy and sport-specific intelligence.

Key Improvements:
1. Sport-specific HTML pattern recognition using actual bet365 DOM structure
2. Precise team-to-odds alignment using grid positioning and DOM traversal
3. Enhanced tab detection with icon and text matching
4. Accurate fixture-to-odds mapping using bet365's grid layout
5. Sport-specific validation and cleansing
6. Better handling of virtualized content and dynamic loading
7. Focused HTML snippet extraction for precise parsing
"""

import asyncio
import argparse
import json
import logging
import re
import sys
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from patchright.async_api import async_playwright


# ----------------------------- Data Structures ----------------------------- #

@dataclass
class GameOdds:
    spread: List[str] = field(default_factory=list)
    total: List[str] = field(default_factory=list)
    moneyline: List[str] = field(default_factory=list)
    runline: List[str] = field(default_factory=list)
    puckline: List[str] = field(default_factory=list)  # For NHL
    to_win: List[str] = field(default_factory=list)  # For Golf/Outrights
    top_5: List[str] = field(default_factory=list)  # For Golf
    top_10: List[str] = field(default_factory=list)  # For Golf

    def to_dict(self) -> Dict[str, List[str]]:
        data = {}
        if self.spread: data["spread"] = self.spread
        if self.total: data["total"] = self.total  
        if self.moneyline: data["moneyline"] = self.moneyline
        if self.runline: data["runline"] = self.runline
        if self.puckline: data["puckline"] = self.puckline
        if self.to_win: data["to_win"] = self.to_win
        if self.top_5: data["top_5"] = self.top_5
        if self.top_10: data["top_10"] = self.top_10
        return data

    def has_valid_odds(self) -> bool:
        """Check if any odds category has valid data"""
        return any(self.to_dict().values())


@dataclass
class Game:
    sport: str
    team1: str
    team2: str
    date: Optional[str]
    time: Optional[str]
    odds: GameOdds
    fixture_id: str = ""
    confidence_score: float = 0.0
    game_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sport": self.sport,
            "team1": self.team1,
            "team2": self.team2,
            "date": self.date,
            "time": self.time,
            "odds": self.odds.to_dict(),
            "fixture_id": self.fixture_id,
            "confidence_score": self.confidence_score,
            "game_id": self.game_id,
        }


# ----------------------------- Enhanced Scraper Class ----------------------------- #

class EnhancedIntelligentScraper:
    def __init__(self, headless: bool = True, load_wait: int = 2000, max_scrolls: int = 15, scroll_pause: int = 300, email: str = None, password: str = None):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.headless = headless
        self.load_wait = load_wait
        self.max_scrolls = max_scrolls
        self.scroll_pause = scroll_pause
        self.timeout = 5000  # Fast timeout like test scraper
        self.fast_mode = True  # Enable fast extraction mode
        self.email = email
        self.password = password
        self.setup_logging()
        
        # Enhanced sport detection patterns
        self.sport_patterns = {
            "MLB": {
                "tabs": ["World Series", "MLB", "Baseball"],
                "fixture_classes": [
                    "cpm-ParticipantFixtureDetailsBaseball",
                    "cpm-ParticipantFixtureDetails120"
                ],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "runline", "total"],
                "logo_indicators": ["mlb", "baseball"],
                "validation_keywords": ["dodgers", "yankees", "red sox", "blue jays"]
            },
            "NBA": {
                "tabs": ["NBA", "Basketball"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsBasketball"],
                "team_class": "_Team", 
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "spread", "total"],
                "logo_indicators": ["nba", "basketball"],
                "validation_keywords": ["thunder", "warriors", "lakers", "celtics"]
            },
            "NHL": {
                "tabs": ["NHL", "Hockey"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsIceHockey"],
                "team_class": "_Team",
                "time_class": "_BookCloses", 
                "expected_odds": ["moneyline", "puckline", "total"],
                "logo_indicators": ["nhl", "hockey"],
                "validation_keywords": ["rangers", "bruins", "maple leafs", "lightning"]
            },
            "NCAAF": {
                "tabs": ["NCAAF", "College Football"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsAmericanFootball"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "spread", "total"], 
                "logo_indicators": ["ncaa", "college", "zlogo_ncaaf_official.svg"],
                "validation_keywords": ["colorado", "utah", "ohio state", "michigan", "alabama", "georgia"],
                "spotlight_logo": "zlogo_ncaaf_official.svg",
                "week_pattern": r"Week \d+"
            },
            "NFL": {
                "tabs": ["NFL", "American Football"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsAmericanFootball"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "spread", "total"],
                "logo_indicators": ["nfl"],
                "validation_keywords": ["patriots", "cowboys", "packers", "chiefs"],
                "icon_class": "afl-NFLLeagueLogo"
            },
            "Tennis": {
                "tabs": ["Tennis", "ATP/WTA", "ATP", "WTA"],
                "fixture_classes": ["cpm-ParticipantFixtureDetails"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline"],
                "logo_indicators": ["tennis", "atp", "wta"],
                "validation_keywords": ["federer", "djokovic", "nadal", "williams", "serena", "sinner", "zverev"],
                "icon_svg": "zClass_Tennis.svg"
            },
             "PGA": {
                "tabs": ["PGA TOUR", "PGA Tour", "Golf", "PGA", "WWT Championship"],
                "fixture_classes": ["cpm-ParticipantLabelGolfScore", "fh-ParticipantFixtureOutrightsListOdds"],
                "team_class": "_Name",
                "time_class": "_HeaderLabel",
                "expected_odds": ["to_win", "top_5", "top_10"],  # Supports 1 or 3 columns dynamically
                "logo_indicators": ["pga", "golf", "zlogo_pga_official.svg"],
                "validation_keywords": ["tiger", "spieth", "mcilroy", "championship", "tournament", "wwt", "ben griffin", "j.j. spaun"],
                "icon_svg": "zlogo_pga_official.svg",
                "spotlight_header": None,  # Tournament names vary
                "is_outrights": True
            },
            "CFL": {
                "tabs": ["CFL", "Canadian Football"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsAmericanFootball"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "spread", "total"],
                "logo_indicators": ["cfl", "canadian football"],
                "validation_keywords": ["alouettes", "bluebombers", "lions", "roughriders", "stampeders", "redblacks"],
                "icon_svg": "zClass_AmericanFootball.svg"
            },
            "UFC": {
                "tabs": ["UFC", "MMA", "Mixed Martial Arts"],
                "fixture_classes": ["cpm-ParticipantFixtureDetails100"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline"],  # Fixed: UFC uses moneyline odds, not to_win
                "logo_indicators": ["ufc", "mma"],
                "validation_keywords": ["aspinall", "gane", "nurmagomedov", "volkov", "almeida", "dern"],
                "icon_svg": "ufcofficialwhite.svg",
                "spotlight_header": "321"
            },
            "NBA2K": {
                "tabs": ["NBA2K", "NBA 2K"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsBasketball"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "spread", "total"],
                "logo_indicators": ["esports", "nba2k"],
                "validation_keywords": ["jd", "hyper", "carnage", "outlaw", "rider", "unbreakable", "prodigy", "scorch", "decoy", "fenrir", "hawk"],
                "icon_svg": "zClass_ESports.svg"
            },
            "Soccer": {
                "tabs": ["Soccer", "Football"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsSoccer"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "total"],
                "logo_indicators": ["soccer", "football"],
                "validation_keywords": ["messi", "ronaldo", "neymar", "mbappe", "haaland", "salah", "kane", "benzema"],
                "icon_svg": "zClass_Soccer.svg",
                "spotlight_header": "Featured Matches"
            },
            "EPL": {
                "tabs": ["Premier League", "EPL", "English Premier League"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsSoccer"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "total"],  # EPL uses 1/X/2 betting, not spread
                "logo_indicators": ["soccer", "premier league"],
                "validation_keywords": ["arsenal", "manchester", "liverpool", "chelsea", "tottenham", "city", "united"],
                "icon_svg": "zClass_Soccer.svg",
                "spotlight_header": "Premier League"
            },
            "MLS": {
                "tabs": ["MLS", "Major League Soccer", "Round 1"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsSoccer"],
                "team_class": "_Team",
                "time_class": "_BookCloses",  
                "expected_odds": ["moneyline", "total"],
                "logo_indicators": ["mls", "major league soccer"],
                "validation_keywords": ["philadelphia", "chicago fire", "vancouver", "fc dallas", "lafc", "austin fc", "seattle"],
                "icon_svg": "zlogo_MLS_Official.svg",
                "spotlight_header": "Round 1"
            },
            "NCAAB": {
                "tabs": ["NCAAB", "College Basketball"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsBasketball"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "spread", "total"],
                "logo_indicators": ["ncaa", "college", "ncaab"],
                "validation_keywords": ["duke", "kansas", "gonzaga", "kentucky", "villanova"],
                "spotlight_logo": "zlogo_ncaab_official.svg"
            },
            "UCL": {
                "tabs": ["UEFA Champions League", "UCL", "Champions League"],
                "fixture_classes": ["cpm-ParticipantFixtureDetailsSoccer"],
                "team_class": "_Team",
                "time_class": "_BookCloses",
                "expected_odds": ["moneyline", "total"],
                "logo_indicators": ["ucl", "uefa", "champions league", "zlogo_UCL_Official.svg"],
                "validation_keywords": ["liverpool", "real madrid", "bayern", "psg", "arsenal", "napoli", "juventus", "atletico"],
                "icon_svg": "zlogo_UCL_Official.svg",
                "spotlight_header": "UEFA Champions League"
            }
        }

        # Odds header mappings
        self.odds_mappings = {
            "money": "moneyline",
            "moneyline": "moneyline", 
            "spread": "spread",
            "total": "total",
            "run line": "runline",
            "runline": "runline",
            "puck line": "puckline",
            "puckline": "puckline",
            "win only": "to_win",
            "to win": "to_win",
            "top 5": "top_5",
            "top 5 (inc ties)": "top_5",
            "top 10": "top_10",
            "top 10 (inc ties)": "top_10"
        }

        self.outputs_dir = Path(".")

        # Load hierarchical cache for team name normalization
        self.hierarchical_cache = {}
        self.nickname_index = {}  # O(1) lookup by nickname
        self.sport_team_index = {}  # O(1) lookup by sport -> teams
        try:
            cache_file = Path("cache_data.json")
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.hierarchical_cache = data.get('alias_lookup', {})
                
                # Build O(1) lookup indices
                self._build_lookup_indices()
                
                self.logger.info(f"Loaded hierarchical cache with {len(self.hierarchical_cache)} aliases")
            else:
                self.logger.warning("cache_data.json not found, team names will not be normalized")
        except Exception as e:
            self.logger.warning(f"Could not load hierarchical cache: {e}")
    
    def _build_lookup_indices(self):
        """Build O(1) lookup indices for fast team name normalization"""
        self.nickname_index = {}  # nickname -> list of (alias, path)
        self.sport_team_index = {}  # sport -> list of team canonical names
        
        for alias, path in self.hierarchical_cache.items():
            # Build nickname index (last word of alias)
            words = alias.split()
            if len(words) >= 2 and path.get('team'):
                nickname = words[-1]
                if nickname not in self.nickname_index:
                    self.nickname_index[nickname] = []
                self.nickname_index[nickname].append((alias, path))
            
            # Build sport/league index
            team = path.get('team')
            if team:
                sport = path.get('sport', '')
                league = path.get('league', '')
                
                # Index by sport
                if sport:
                    if sport not in self.sport_team_index:
                        self.sport_team_index[sport] = {}
                    canonical = path.get('canonical_name')
                    if canonical:
                        self.sport_team_index[sport][alias] = canonical
                
                # Index by league
                if league:
                    if league not in self.sport_team_index:
                        self.sport_team_index[league] = {}
                    canonical = path.get('canonical_name')
                    if canonical:
                        self.sport_team_index[league][alias] = canonical
        
        self.logger.info(f"Built lookup indices: {len(self.nickname_index)} nicknames, {len(self.sport_team_index)} sports/leagues")
    
    # ----------------------------- Logging & Utilities ----------------------------- #

    def setup_logging(self):
        # Configure UTF-8 encoding for Windows
        if sys.platform == 'win32':
            try:
                sys.stdout.reconfigure(encoding='utf-8')
            except AttributeError:
                # Python < 3.7
                import codecs
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        
        logging.basicConfig(
            level=logging.INFO,  # Back to INFO for cleaner output
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger("enhanced_scraper")

    @staticmethod
    def clean_text(text: Optional[str]) -> Optional[str]:
        """Clean and normalize text content"""
        if not text:
            return None
        cleaned = re.sub(r'\s+', ' ', text.strip())
        return cleaned if cleaned else None

    @staticmethod
    def generate_game_id(team1: str, team2: str, date: Optional[str] = None, time: Optional[str] = None) -> str:
        """
        Generate game_id in format: home_team:away_team:yearmonthday:americantime
        Example: "real_madrid:barcelona:20251010:1730"
        """
        from datetime import datetime
        import re
        
        # Clean team names - remove spaces, special chars, make lowercase
        def clean_team_name(team: str) -> str:
            if not team:
                return "unknown"
            # Remove common prefixes/suffixes and clean
            clean = re.sub(r'\b(FC|CF|United|City|Town|County|SC|AC)\b', '', team, flags=re.IGNORECASE)
            clean = re.sub(r'[^\w\s]', '', clean)  # Remove special chars
            clean = re.sub(r'\s+', '_', clean.strip().lower())  # Replace spaces with underscores
            return clean[:15] if clean else "unknown"  # Limit length
        
        # Process date - convert to YYYYMMDD format
        def parse_date(date_str: Optional[str]) -> str:
            if not date_str:
                return datetime.now().strftime("%Y%m%d")
                
            try:
                # Handle various date formats
                date_str = date_str.strip()
                
                # Format: "Sat Oct 25", "Sun Oct 26"
                if re.match(r'\w{3}\s+\w{3}\s+\d{1,2}', date_str):
                    # Parse "Sat Oct 25" format - assume current year
                    parts = date_str.split()
                    if len(parts) >= 3:
                        month_day = f"{parts[1]} {parts[2]}"
                        current_year = datetime.now().year
                        parsed = datetime.strptime(f"{month_day} {current_year}", "%b %d %Y")
                        return parsed.strftime("%Y%m%d")
                
                # Format: "2025-10-26"
                elif re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                    parsed = datetime.strptime(date_str, "%Y-%m-%d")
                    return parsed.strftime("%Y%m%d")
                
                # Default to today if can't parse
                return datetime.now().strftime("%Y%m%d")
                
            except Exception:
                return datetime.now().strftime("%Y%m%d")
        
        # Process time - convert to HHMM format (24-hour)
        def parse_time(time_str: Optional[str]) -> str:
            if not time_str:
                return "0000"
                
            try:
                time_str = time_str.strip()
                
                # Format: "1:00 PM", "10:15 PM"
                if re.search(r'\d{1,2}:\d{2}\s*[APap][Mm]', time_str):
                    # Extract time part
                    time_match = re.search(r'(\d{1,2}):(\d{2})\s*([APap][Mm])', time_str)
                    if time_match:
                        hour = int(time_match.group(1))
                        minute = int(time_match.group(2))
                        is_pm = time_match.group(3).lower() == 'pm'
                        
                        # Convert to 24-hour format
                        if is_pm and hour != 12:
                            hour += 12
                        elif not is_pm and hour == 12:
                            hour = 0
                            
                        return f"{hour:02d}{minute:02d}"
                
                # Format: "17:30" (already 24-hour)
                elif re.match(r'\d{1,2}:\d{2}', time_str):
                    parts = time_str.split(':')
                    if len(parts) == 2:
                        hour = int(parts[0])
                        minute = int(parts[1])
                        return f"{hour:02d}{minute:02d}"
                
                return "0000"
                
            except Exception:
                return "0000"
        
        # Generate the components
        home_team = clean_team_name(team1)
        away_team = clean_team_name(team2)
        date_part = parse_date(date)
        time_part = parse_time(time)
        
        return f"{home_team}:{away_team}:{date_part}:{time_part}"

    @staticmethod
    def is_valid_odds(text: str) -> bool:
        """Validate if text represents valid betting odds"""
        if not text:
            return False
        text = text.strip()

        # American odds format: +/-XXX
        if re.match(r'^[+-]\d{2,4}$', text):
            return True

        # Decimal odds format: X.XX
        if re.match(r'^\d{1,2}\.\d{1,2}$', text):
            return True

        return False

    def normalize_team_name(self, team_name: str, sport: Optional[str] = None) -> str:
        """Normalize team name using hierarchical cache with O(1) lookups"""
        if not team_name or not self.hierarchical_cache:
            return team_name

        team_lower = team_name.lower().strip()
        
        # Remove common punctuation and extra spaces
        team_cleaned = re.sub(r'[^\w\s]', '', team_lower)
        team_cleaned = re.sub(r'\s+', ' ', team_cleaned).strip()

        # Stage 1: Direct exact match - O(1)
        if team_lower in self.hierarchical_cache:
            path = self.hierarchical_cache[team_lower]
            canonical = path.get('canonical_name')
            if canonical:
                return canonical
        
        # Stage 2: Try cleaned version - O(1)
        if team_cleaned != team_lower and team_cleaned in self.hierarchical_cache:
            path = self.hierarchical_cache[team_cleaned]
            canonical = path.get('canonical_name')
            if canonical:
                return canonical

        # Stage 3: Try without spaces - O(1)
        team_no_space = team_cleaned.replace(' ', '')
        if team_no_space != team_cleaned and team_no_space in self.hierarchical_cache:
            path = self.hierarchical_cache[team_no_space]
            canonical = path.get('canonical_name')
            if canonical:
                return canonical

        # Stage 4: Nickname matching using pre-built index - O(1)
        words = team_cleaned.split()
        if len(words) >= 2:
            nickname = words[-1]
            
            # O(1) lookup in nickname index
            if nickname in self.nickname_index:
                candidates = self.nickname_index[nickname]
                
                # Check sport match if provided
                for alias, path in candidates:
                    if sport:
                        cache_sport = path.get('sport', '')
                        cache_league = path.get('league', '')
                        # Match either sport or league
                        if cache_sport and sport.upper() == cache_sport.upper():
                            return path.get('canonical_name')
                        if cache_league and sport.upper() == cache_league.upper():
                            return path.get('canonical_name')
                    else:
                        # No sport filter, return first match
                        return path.get('canonical_name')

        # Stage 5: Sport-specific lookup - O(1)
        if sport:
            # Check if sport has an index
            sport_index = self.sport_team_index.get(sport, {})
            
            # Try various formats
            for variant in [team_lower, team_cleaned, team_no_space]:
                if variant in sport_index:
                    return sport_index[variant]
            
            # Try with nickname if available
            if len(words) >= 2:
                nickname = words[-1]
                # Look for any alias ending with this nickname in this sport
                for alias, canonical in sport_index.items():
                    if alias.endswith(nickname):
                        return canonical

        # Stage 6: Fallback - Check if any word matches (still faster than full iteration)
        # Only do this for very short lookups to avoid performance issues
        if len(team_words := team_cleaned.split()) <= 3:
            # Try combining words in different ways
            for i in range(len(team_words)):
                for j in range(i + 1, len(team_words) + 1):
                    subset = ' '.join(team_words[i:j])
                    if subset in self.hierarchical_cache:
                        path = self.hierarchical_cache[subset]
                        if path.get('team'):  # Only return if it's a team
                            canonical = path.get('canonical_name')
                            if canonical:
                                return canonical

        # Return original if no match found
        return team_name

    def normalize_game_teams(self, game: Game) -> Game:
        """Normalize both team names in a game using hierarchical cache"""
        if self.hierarchical_cache:
            game.team1 = self.normalize_team_name(game.team1, game.sport)
            game.team2 = self.normalize_team_name(game.team2, game.sport)
        return game

    def normalize_games_list(self, games: List[Game]) -> List[Game]:
        """Normalize team names in a list of games using hierarchical cache"""
        if self.hierarchical_cache:
            for game in games:
                game.team1 = self.normalize_team_name(game.team1, game.sport)
                game.team2 = self.normalize_team_name(game.team2, game.sport)
        return games

    def calculate_confidence_score(self, game: Game) -> float:
        """Calculate confidence score for extracted game data"""
        score = 0.0
        
        # Team names validation (40 points)
        if game.team1 and game.team2:
            score += 20
            # Check for sport-specific keywords
            sport_keywords = self.sport_patterns.get(game.sport, {}).get("validation_keywords", [])
            team_text = f"{game.team1} {game.team2}".lower()
            
            # More lenient validation for NCAAF and NFL - just check for reasonable team names
            if game.sport in ["NCAAF", "NFL"]:
                # For football, any reasonable team names get the keyword bonus
                if len(game.team1) > 2 and len(game.team2) > 2:
                    score += 20
            elif any(keyword.lower() in team_text for keyword in sport_keywords):
                score += 20
        
        # Time information (10 points)
        if game.time:
            score += 10
            
        # Date information (10 points) 
        if game.date:
            score += 10
            
        # Odds validation (40 points)
        odds_dict = game.odds.to_dict()
        if odds_dict:
            # Base score for having odds
            score += 10
            
            # Score for expected odds categories
            expected_odds = self.sport_patterns.get(game.sport, {}).get("expected_odds", [])
            for expected in expected_odds:
                if expected in odds_dict and odds_dict[expected]:
                    score += 10
                    
        return min(score, 100.0)

    # ----------------------------- Tab Detection & Navigation ----------------------------- #

    async def detect_sport_tabs(self, page) -> List[Tuple[str, str, Any]]:
        """Enhanced sport tab detection with confidence scoring"""
        detected_tabs = []
        
        try:
            # Find horizontal scroller for navigation tabs
            scroller = await page.query_selector('div[class*="hsn-Scroller_HScroll"]')
            if scroller:
                nav_tabs = await scroller.query_selector_all('div[class*="hsn-NavTab"]')
                self.logger.info(f"Found {len(nav_tabs)} navigation tabs")
                
                for tab in nav_tabs:
                    try:
                        # Get tab label
                        label_el = await tab.query_selector('div[class*="hsn-NavTab_Label"]')
                        if not label_el:
                            continue
                            
                        label = await label_el.inner_text()
                        label = self.clean_text(label)
                        if not label:
                            continue
                        
                        # Check for sport matches (case insensitive)
                        for sport, config in self.sport_patterns.items():
                            # Check exact match first
                            if label in config["tabs"]:
                                detected_tabs.append((sport, label, tab))
                                self.logger.info(f"Detected sport tab: {sport} -> '{label}'")
                                break
                            # Then check case-insensitive match
                            elif any(label.lower() == expected.lower() for expected in config["tabs"]):
                                detected_tabs.append((sport, label, tab))
                                self.logger.info(f"Detected sport tab (case-insensitive): {sport} -> '{label}'")
                                break
                        else:
                            # Log unmatched tabs for debugging UFC detection
                            self.logger.debug(f"Unmatched tab label: '{label}'")
                                
                    except Exception as e:
                        self.logger.debug(f"Error processing tab: {e}")
                        continue
            
            # Also scan for homepage spotlight sections
            self.logger.info("Scanning for homepage spotlight sections...")
            
            # Look for spotlight sections with specific headers and icons
            spotlights = await page.query_selector_all('div.ss-HomepageSpotlight, div.cpm-CouponPodModule')
            
            for spotlight in spotlights:
                try:
                    # Check for header title
                    header_el = await spotlight.query_selector('div.ss-HomeSpotlightHeader_Title, div.cpm-Header_Title')
                    if not header_el:
                        continue
                        
                    header_text = await header_el.inner_text()
                    header_text = self.clean_text(header_text)
                    if not header_text:
                        continue
                    
                    # Check for icon in header image
                    icon_el = await spotlight.query_selector('div.ss-HomeSpotlightHeader_HeaderImage, div.cpm-Header_HeaderImage')
                    icon_style = ""
                    if icon_el:
                        icon_style = await icon_el.get_attribute('style') or ""
                    
                    # Check for specific spotlight headers and icons
                    for sport, config in self.sport_patterns.items():
                        spotlight_header = config.get("spotlight_header")
                        icon_svg = config.get("icon_svg", "")
                        
                        if spotlight_header and header_text == spotlight_header:
                            # Verify icon matches
                            if icon_svg and icon_svg in icon_style:
                                detected_tabs.append((sport, header_text, spotlight))
                                self.logger.info(f"Detected spotlight section: {sport} -> '{header_text}' (icon: {icon_svg})")
                                break
                            elif not icon_svg:  # No icon requirement
                                detected_tabs.append((sport, header_text, spotlight))
                                self.logger.info(f"Detected spotlight section: {sport} -> '{header_text}'")
                                break
                        elif icon_svg and icon_svg in icon_style:
                            # Icon-based detection as fallback
                            detected_tabs.append((sport, f"{sport}_icon", spotlight))
                            self.logger.info(f"Detected spotlight section by icon: {sport} -> icon: {icon_svg}")
                            break
                            
                except Exception as e:
                    self.logger.debug(f"Error processing spotlight: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Tab detection error: {e}")
            
        return detected_tabs

    async def navigate_to_sport(self, page, tab_element, sport: str) -> bool:
        """Navigate to specific sport tab with validation"""
        try:
            # Click the tab
            await tab_element.click()
            await page.wait_for_timeout(min(self.load_wait, 2000))  # Faster loading
            
            # Wait for sport-specific content to load
            sport_config = self.sport_patterns[sport]
            for fixture_class in sport_config["fixture_classes"]:
                try:
                    await page.wait_for_selector(
                        f'div[class*="{fixture_class}"]',
                        timeout=self.timeout  # Use fast timeout
                    )
                    self.logger.info(f"Successfully navigated to {sport}")
                    return True
                except:
                    continue
                    
            self.logger.warning(f"Sport content not detected after clicking {sport} tab")
            return False
            
        except Exception as e:
            self.logger.error(f"Navigation error for {sport}: {e}")
            return False

    # ----------------------------- Content Loading & Discovery ----------------------------- #

    async def progressive_scroll_load(self, page, sport: str):
        """Enhanced progressive scrolling with sport-specific optimization"""
        try:
            # Fast mode: Skip extensive scrolling for speed
            if self.fast_mode:
                await page.wait_for_timeout(200)  # Minimal wait in fast mode
                return
                
            grid = await page.query_selector('div[class*="cpm-CouponPodMarketGrid"]')
            if not grid:
                return
                
            last_count = 0
            stable_iterations = 0
            
            for scroll_iteration in range(self.max_scrolls):
                # Scroll to load more content
                scroll_y = 1500 * scroll_iteration
                await grid.evaluate(f'(element) => element.scrollTo(0, {scroll_y})')
                await page.wait_for_timeout(min(self.scroll_pause, 1000))  # Faster scrolling
                
                # Count fixtures for this sport
                sport_config = self.sport_patterns[sport]
                current_count = 0
                
                for fixture_class in sport_config["fixture_classes"]:
                    fixtures = await page.query_selector_all(f'div[class*="{fixture_class}"]')
                    for fixture in fixtures:
                        class_attr = await fixture.get_attribute("class")
                        if not class_attr or "Hidden" in class_attr:
                            continue
                        current_count += 1
                
                # Check for stability
                if current_count == last_count:
                    stable_iterations += 1
                else:
                    stable_iterations = 0
                    
                last_count = current_count
                
                # Stop if content is stable
                if stable_iterations >= 3:
                    self.logger.info(f"{sport}: Content stabilized at {current_count} fixtures after {scroll_iteration + 1} scrolls")
                    break
                    
            self.logger.info(f"{sport}: Final count {last_count} fixtures after scrolling")
            
        except Exception as e:
            self.logger.debug(f"Scroll loading error for {sport}: {e}")

    async def find_sport_grid(self, page, sport: str):
        """Find the most relevant coupon grid for the sport"""
        try:
            grids = await page.query_selector_all('div[class*="cpm-CouponPodMarketGrid"]')
            
            best_grid = None
            best_score = 0
            sport_config = self.sport_patterns[sport]
            
            for grid in grids:
                score = 0
                
                # Count sport-specific fixtures
                for fixture_class in sport_config["fixture_classes"]:
                    fixtures = await grid.query_selector_all(f'div[class*="{fixture_class}"]')
                    for fixture in fixtures:
                        class_attr = await fixture.get_attribute("class")
                        if class_attr and "Hidden" not in class_attr:
                            score += 1
                            
                if score > best_score:
                    best_score = score
                    best_grid = grid
                    
            if best_grid:
                self.logger.info(f"{sport}: Selected grid with {best_score} relevant fixtures")
                

               
                
            return best_grid
            
        except Exception as e:
            self.logger.error(f"Grid selection error for {sport}: {e}")
            return None

    # ----------------------------- Enhanced Extraction Engine ----------------------------- #

    async def extract_sport_games(self, page, sport: str) -> List[Game]:
        """Enhanced sport-specific game extraction"""
        self.logger.info(f"Starting extraction for {sport}")
        
        # Load content progressively
        await self.progressive_scroll_load(page, sport)
        
        # Find the best grid for this sport
        grid = await self.find_sport_grid(page, sport)
        if not grid:
            self.logger.warning(f"{sport}: No suitable grid found")
            return []
            
        # Extract games using sport-specific approach
        if sport == "MLB":
            games = await self.extract_mlb_games(grid, sport)
            return self.normalize_games_list(games)
        elif sport == "NBA":
            games = await self.extract_nba_games_fixed(page, sport)
            return self.normalize_games_list(games)
        elif sport == "NBA2K":
            games = await self.extract_nba2k_games(page, sport)
            return self.normalize_games_list(games)
        elif sport == "NHL":
            games = await self.extract_nhl_games(grid, sport)
            return self.normalize_games_list(games)
        elif sport == "NCAAF":
            games = await self.extract_ncaaf_games(page, sport)  # NCAAF uses page-based approach for spotlight sections
            return self.normalize_games_list(games)
        elif sport == "NCAAB":
            games = await self.extract_ncaab_games(page, sport)  # NCAAB uses page-based approach for spotlight sections
            return self.normalize_games_list(games)
        elif sport == "NFL":
            games = await self.extract_nfl_games(page, sport)  # NFL uses page-based approach
            return self.normalize_games_list(games)
        elif sport == "Tennis":
            games = await self.extract_tennis_games(grid, sport)
            return self.normalize_games_list(games)
        elif sport == "CFL":
            games = await self.extract_cfl_games(page, sport)  # CFL uses page-based approach
            return self.normalize_games_list(games)
        elif sport == "PGA":
            games = await self.extract_pga_games(page, sport)  # PGA handles both 1-column and 3-column odds dynamically
            return self.normalize_games_list(games)
        elif sport == "UFC":
            games = await self.extract_ufc_games(page, sport)  # UFC uses page-based approach
            return self.normalize_games_list(games)
        elif sport == "Soccer":
            games = await self.extract_soccer_games(page, sport)  # Soccer uses page-based approach
            return self.normalize_games_list(games)
        elif sport == "EPL":
            games = await self.extract_epl_games(page, sport)  # EPL uses page-based approach
            return self.normalize_games_list(games)
        elif sport == "MLS":
            games = await self.extract_mls_games(page, sport)  # MLS uses page-based approach
            return self.normalize_games_list(games)
        elif sport == "UCL":
            games = await self.extract_ucl_games(page, sport)  # UCL uses soccer-based approach
            return self.normalize_games_list(games)
        else:
            games = await self.extract_generic_games(grid, sport)
            return self.normalize_games_list(games)

    async def extract_mlb_games(self, grid, sport: str) -> List[Game]:
        """MLB-specific extraction with runline handling"""
        games = []
        
        try:
            # Execute specialized JavaScript for MLB
            extraction_result = await grid.evaluate("""
                (grid) => {
                    const results = [];
                    const fixtures = Array.from(grid.querySelectorAll('div.cpm-MarketFixture'));
                    
                    for (const fixture of fixtures) {
                        // Find visible baseball fixture details
                        const details = Array.from(fixture.querySelectorAll('div[class*="cpm-ParticipantFixtureDetailsBaseball"], div[class*="cpm-ParticipantFixtureDetails120"]'))
                            .find(d => !d.className.includes('Hidden'));
                        
                        if (!details) continue;
                        
                        // Extract teams from team containers
                        const teamContainers = Array.from(details.querySelectorAll('div[class*="_TeamContainer"]'));
                        const teamNodes = [];
                        
                        for (const container of teamContainers) {
                            const teamEl = container.querySelector('div[class*="_Team"]');
                            if (teamEl) {
                                const teamText = teamEl.textContent.trim();
                                if (teamText && teamText.length > 1) {
                                    teamNodes.push(teamText);
                                }
                            }
                        }
                        
                        if (teamNodes.length < 2) continue;
                        
                        // Extract time
                        const timeEl = details.querySelector('div[class*="_BookCloses"]');
                        const gameTime = timeEl ? timeEl.textContent.trim() : null;
                        
                        // Extract date
                        const dateEl = fixture.querySelector('div.cpm-MarketFixtureDateHeader');
                        const gameDate = dateEl ? dateEl.textContent.trim() : null;
                        
                        // Extract odds from sibling elements
                        const odds = {};
                        let sibling = fixture.nextElementSibling;
                        
                        while (sibling && !sibling.className.includes('cpm-MarketFixture')) {
                            if (sibling.className.includes('cpm-MarketOdds')) {
                                const header = sibling.querySelector('.cpm-MarketOddsHeader');
                                const headerText = header ? header.textContent.trim().toLowerCase() : '';
                                
                                let category = null;
                                if (headerText.includes('run line') || headerText.includes('runline')) {
                                    category = 'runline';
                                } else if (headerText === 'money' || headerText.includes('moneyline')) {
                                    category = 'moneyline';
                                } else if (headerText.includes('total')) {
                                    category = 'total';
                                }
                                
                                if (category) {
                                    const oddsElements = Array.from(sibling.querySelectorAll('.cpm-ParticipantOdds'));
                                    const oddsValues = [];
                                    
                                    for (const el of oddsElements) {
                                        const handicap = el.querySelector('.cpm-ParticipantOdds_Handicap');
                                        const price = el.querySelector('.cpm-ParticipantOdds_Odds');
                                        
                                        const hText = handicap ? handicap.textContent.trim() : '';
                                        const pText = price ? price.textContent.trim() : '';
                                        
                                        if (pText && /^[+-]\\d{2,4}$/.test(pText)) {
                                            if (hText && category !== 'moneyline') {
                                                oddsValues.push(`${hText} (${pText})`);
                                            } else {
                                                oddsValues.push(pText);
                                            }
                                        }
                                    }
                                    
                                    if (oddsValues.length > 0) {
                                        odds[category] = oddsValues.slice(0, 2);
                                    }
                                }
                            }
                            sibling = sibling.nextElementSibling;
                        }
                        
                        results.push({
                            team1: teamNodes[0],
                            team2: teamNodes[1], 
                            time: gameTime,
                            date: gameDate,
                            odds: odds,
                            fixture_id: `mlb_${results.length}`
                        });
                    }
                    
                    return results;
                }
            """)
            
            # Process results
            for idx, result in enumerate(extraction_result):
                odds_obj = GameOdds(
                    moneyline=result['odds'].get('moneyline', []),
                    runline=result['odds'].get('runline', []),
                    total=result['odds'].get('total', [])
                )
                
                team1_clean = self.clean_text(result['team1']) or f"Team1_{idx}"
                team2_clean = self.clean_text(result['team2']) or f"Team2_{idx}"
                date_clean = self.clean_text(result['date'])
                time_clean = self.clean_text(result['time'])
                
                game = Game(
                    sport=sport,
                    team1=team1_clean,
                    team2=team2_clean,
                    date=date_clean,
                    time=time_clean,
                    odds=odds_obj,
                    fixture_id=result['fixture_id'],
                    game_id=self.generate_game_id(team1_clean, team2_clean, date_clean, time_clean)
                )
                
                game.confidence_score = self.calculate_confidence_score(game)
                
                if game.confidence_score >= 30.0:  # Lowered confidence threshold for initial testing
                    games.append(game)
                    
        except Exception as e:
            self.logger.error(f"MLB extraction error: {e}")
            
        self.logger.info(f"MLB: Extracted {len(games)} games")
        return games

    async def extract_nba_games_fixed(self, page, sport: str) -> List[Game]:
        """NBA-specific extraction with proper NBA vs NBA2K distinction using SVG detection"""
        games = []
        
        try:
            self.logger.info("🏀 Starting NBA extraction with proper NBA vs NBA2K detection...")
            
            # NBA extraction using section-based detection to avoid NBA2K confusion
            extraction_result = await page.evaluate("""
                () => {
                    const results = [];
                    
                    console.log('🔍 Looking for NBA section by SVG logo...');
                    
                    // Step 1: Find REAL NBA section by NBA logo (not eSports logo)
                    let nbaSection = null;
                    
                    // Look for NBA section by NBA-specific SVG logo
                    const nbaLogos = document.querySelectorAll('.nba-NBALeagueLogo, .nba-NBALeagueLogo_SVG');
                    for (const logo of nbaLogos) {
                        const section = logo.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                        if (section) {
                            // Verify this is NOT eSports by checking for eSports indicators
                            const sectionHTML = section.innerHTML;
                            
                            // eSports sections have zClass_ESports.svg, NBA has nba-NBALeagueLogo
                            if (!sectionHTML.includes('zClass_ESports.svg') && sectionHTML.includes('nba-NBALeagueLogo')) {
                                nbaSection = section;
                                console.log('✅ Found REAL NBA section (not eSports)');
                                break;
                            }
                        }
                    }
                    
                    // Fallback: Look for NBA title with NBA logo wrapper
                    if (!nbaSection) {
                        const headers = document.querySelectorAll('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                        for (const header of headers) {
                            if (header.textContent.trim() === 'NBA') {
                                const section = header.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                if (section) {
                                    const sectionHTML = section.innerHTML;
                                    // Double check it's not eSports
                                    if (!sectionHTML.includes('zClass_ESports.svg')) {
                                        nbaSection = section;
                                        console.log('✅ Found NBA section by title (verified not eSports)');
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    
                    if (!nbaSection) {
                        console.log('❌ REAL NBA section not found (may have found eSports instead)');
                        return [];
                    }
                    
                    // Step 2: Extract NBA fixtures from verified NBA section only
                    const fixtures = Array.from(nbaSection.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball'))
                        .filter(fixture => !fixture.className.includes('Hidden'));
                    
                    console.log(`📋 Found ${fixtures.length} NBA fixtures in verified NBA section`);
                    
                    // Step 3: Extract odds columns from NBA section
                    const oddsColumns = {};
                    
                    const marketOdds = Array.from(nbaSection.querySelectorAll('div.cpm-MarketOdds'));
                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent;
                            if (headerText) {
                                const headerName = headerText.trim();
                                if (["Spread", "Total", "Money"].includes(headerName)) {
                                    const columnOdds = [];
                                    
                                    // Enhanced: Get both handicap and odds for Spread/Total, just odds for Money
                                    const participantOdds = section.querySelectorAll('.cpm-ParticipantOdds');
                                    for (const participantOdd of participantOdds) {
                                        const handicap = participantOdd.querySelector('.cpm-ParticipantOdds_Handicap');
                                        const oddsValue = participantOdd.querySelector('.cpm-ParticipantOdds_Odds');
                                        
                                        if (headerName === 'Money') {
                                            // Moneyline: just the odds value
                                            if (oddsValue) {
                                                columnOdds.push(oddsValue.textContent.trim());
                                            }
                                        } else {
                                            // Spread/Total: include handicap + odds (clean format like NCAAF)
                                            if (handicap && oddsValue) {
                                                columnOdds.push(`${handicap.textContent.trim()} ${oddsValue.textContent.trim()}`);
                                            }
                                        }
                                    }
                                    
                                    oddsColumns[headerName] = columnOdds;
                                }
                            }
                        }
                    }
                    
                    // Extract game date with fallback for pregame
                    const dateHeader = nbaSection.querySelector('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateHeader ? dateHeader.textContent.trim() : null;
                    
                    // Fallback to today's date for pregame if no date found
                    if (!gameDate || gameDate === null) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }
                    
                    // Step 4: Process fixtures and validate they're REAL NBA (no gamer tags)
                    for (let i = 0; i < fixtures.length; i++) {
                        const fixture = fixtures[i];
                        
                        // Extract team names
                        const teamElems = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball_Team');
                        
                        let team1, team2;
                        if (teamElems.length >= 2) {
                            team1 = teamElems[0].textContent.trim();
                            team2 = teamElems[1].textContent.trim();
                        } else {
                            // Fallback to team containers
                            const teamContainers = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball_TeamContainer');
                            if (teamContainers.length >= 2) {
                                const t1 = teamContainers[0].querySelector('div.cpm-ParticipantFixtureDetailsBasketball_Team');
                                const t2 = teamContainers[1].querySelector('div.cpm-ParticipantFixtureDetailsBasketball_Team');
                                team1 = t1 ? t1.textContent.trim() : '';
                                team2 = t2 ? t2.textContent.trim() : '';
                            }
                        }
                        
                        // CRITICAL: Validate this is REAL NBA, not NBA2K eSports
                        // NBA2K teams have gamer tags in parentheses like "OKC Thunder (JD)"
                        const nba2kTags = ['(JD)', '(HYPER)', '(CARNAGE)', '(OUTLAW)', '(RIDER)', '(UNBREAKABLE)', '(PRODIGY)', '(SCORCH)', '(DECOY)', '(FENRIR)', '(HAWK)', '(COMBO)', '(GRAVITY)', '(PUNISHER)', '(CRUCIAL)'];
                        const hasNba2kTag = nba2kTags.some(tag => team1.includes(tag) || team2.includes(tag));
                        
                        if (!team1 || !team2 || hasNba2kTag) {
                            console.log(`❌ Filtered out eSports/invalid team: ${team1} vs ${team2}`);
                            continue;
                        }
                        
                        console.log(`✅ Valid NBA teams: ${team1} vs ${team2}`);
                        
                        // Extract time
                        const timeElem = fixture.querySelector('div.cpm-ParticipantFixtureDetailsBasketball_BookCloses');
                        const gameTime = timeElem ? timeElem.textContent.trim() : "TBD";
                        
                        // Map odds correctly (each game gets 2 odds per column - team1 and team2)
                        const spreadOdds = [];
                        const totalOdds = [];
                        const moneylineOdds = [];
                        
                        const gameIndex = i * 2; // Each game has 2 odds entries
                        
                        // Spread odds (2 per game)
                        if (oddsColumns["Spread"] && oddsColumns["Spread"].length > gameIndex + 1) {
                            spreadOdds.push(oddsColumns["Spread"][gameIndex]);
                            spreadOdds.push(oddsColumns["Spread"][gameIndex + 1]);
                        }
                        
                        // Total odds (2 per game)
                        if (oddsColumns["Total"] && oddsColumns["Total"].length > gameIndex + 1) {
                            totalOdds.push(oddsColumns["Total"][gameIndex]);
                            totalOdds.push(oddsColumns["Total"][gameIndex + 1]);
                        }
                        
                        // Money odds (2 per game)
                        if (oddsColumns["Money"] && oddsColumns["Money"].length > gameIndex + 1) {
                            moneylineOdds.push(oddsColumns["Money"][gameIndex]);
                            moneylineOdds.push(oddsColumns["Money"][gameIndex + 1]);
                        }
                        
                        // Create game object
                        results.push({
                            team1: team1,
                            team2: team2,
                            date: gameDate,
                            time: gameTime,
                            spread: spreadOdds,
                            total: totalOdds,
                            moneyline: moneylineOdds,
                            fixture_id: `nba_real_${i}`
                        });
                    }
                    
                    console.log(`🏀 Total REAL NBA games extracted: ${results.length}`);
                    return results;
                }
            """)
            
            # Process results into Game objects
            for result in extraction_result:
                odds_obj = GameOdds(
                    spread=result['spread'],
                    total=result['total'],
                    moneyline=result['moneyline']
                )
                
                team1_clean = self.clean_text(result['team1']) or f"Team1_{len(games)}"
                team2_clean = self.clean_text(result['team2']) or f"Team2_{len(games)}"
                date_clean = self.clean_text(result['date'])
                time_clean = self.clean_text(result['time'])
                
                game = Game(
                    sport=sport,
                    team1=team1_clean,
                    team2=team2_clean,
                    date=date_clean,
                    time=time_clean,
                    odds=odds_obj,
                    fixture_id=result['fixture_id'],
                    game_id=self.generate_game_id(team1_clean, team2_clean, date_clean, time_clean)
                )
                
                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)
                    
        except Exception as e:
            self.logger.error(f"NBA extraction error: {e}")
            
        self.logger.info(f"NBA: Extracted {len(games)} games (verified REAL NBA, not eSports)")
        return games

    async def extract_nba2k_games(self, page, sport: str) -> List[Game]:
        """NBA2K-specific extraction with esports team names and validation"""
        games = []

        try:
            self.logger.info("🏀 Starting NBA2K extraction...")

            # NBA2K extraction using direct selectors
            extraction_result = await page.evaluate("""
                () => {
                    const results = [];

                    console.log('🎮 Starting NBA2K extraction...');
                    
                    // Step 1: Find NBA2K/eSports section by eSports SVG logo
                    let nba2kSection = null;
                    
                    // Look for eSports logo in header images
                    const headerImages = document.querySelectorAll('.ss-HomeSpotlightHeader_HeaderImage, .cpm-Header_HeaderImage');
                    for (const img of headerImages) {
                        const style = img.getAttribute('style') || '';
                        if (style.includes('zClass_ESports.svg')) {
                            nba2kSection = img.closest('.ss-HomepageSpotlight, .cpm-CouponPodModule');
                            console.log('✅ Found NBA2K/eSports section by eSports SVG');
                            break;
                        }
                    }
                    
                    // Fallback: Look for NBA2K title
                    if (!nba2kSection) {
                        const headers = document.querySelectorAll('.ss-HomeSpotlightHeader_Title, .cpm-Header_Title');
                        for (const header of headers) {
                            if (header.textContent.trim() === 'NBA2K') {
                                nba2kSection = header.closest('.ss-HomepageSpotlight, .cpm-CouponPodModule');
                                console.log('✅ Found NBA2K section by title');
                                break;
                            }
                        }
                    }
                    
                    if (!nba2kSection) {
                        console.log('❌ NBA2K/eSports section not found');
                        return [];
                    }
                    
                    // Step 2: Extract odds columns data from NBA2K section
                    const oddsColumns = {};

                    const marketOdds = Array.from(nba2kSection.querySelectorAll('div.cpm-MarketOdds'));
                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent;
                            if (headerText) {
                                const headerName = headerText.trim();
                                if (["Spread", "Total", "Money"].includes(headerName)) {
                                    const columnOdds = [];

                                    // Extract odds elements correctly
                                    const oddsElems = section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                                    for (const oddsElem of oddsElems) {
                                        const oddsText = oddsElem.textContent;
                                        if (oddsText && oddsText.trim()) {
                                            columnOdds.push(oddsText.trim());
                                        }
                                    }

                                    oddsColumns[headerName] = columnOdds;
                                }
                            }
                        }
                    }

                    // Step 3: Process fixtures and map odds correctly
                    const fixtures = Array.from(nba2kSection.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball'))
                        .filter(fixture => !fixture.className.includes('Hidden'));

                    // Extract game date with fallback for pregame
                    const dateHeader = nba2kSection.querySelector('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateHeader ? dateHeader.textContent.trim() : null;
                    
                    // Fallback to today's date for pregame if no date found
                    if (!gameDate || gameDate === null) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }

                    for (let i = 0; i < fixtures.length; i++) {
                        const fixture = fixtures[i];

                        // Extract team names (NBA2K has team names with player tags like "JD", "HYPER")
                        const teamElems = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball_Team');

                        let team1, team2;
                        if (teamElems.length >= 2) {
                            team1 = teamElems[0].textContent.trim();
                            team2 = teamElems[1].textContent.trim();
                        } else {
                            // Fallback to team containers
                            const teamContainers = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball_TeamContainer');
                            if (teamContainers.length >= 2) {
                                const t1 = teamContainers[0].querySelector('div.cpm-ParticipantFixtureDetailsBasketball_Team');
                                const t2 = teamContainers[1].querySelector('div.cpm-ParticipantFixtureDetailsBasketball_Team');
                                team1 = t1 ? t1.textContent.trim() : '';
                                team2 = t2 ? t2.textContent.trim() : '';
                            }
                        }

                        // Validate NBA2K teams (must contain player tags)
                        const nba2kTags = ['JD', 'HYPER', 'CARNAGE', 'OUTLAW', 'RIDER', 'UNBREAKABLE', 'PRODIGY', 'SCORCH', 'DECOY', 'FENRIR', 'HAWK'];
                        const hasNba2kTag = nba2kTags.some(tag => team1.includes(tag) || team2.includes(tag));

                        if (!team1 || !team2 || !hasNba2kTag) continue;

                        // Extract time
                        const timeElem = fixture.querySelector('div.cpm-ParticipantFixtureDetailsBasketball_BookCloses');
                        const gameTime = timeElem ? timeElem.textContent.trim() : "TBD";

                        // Map odds correctly (each game gets 2 odds per column - team1 and team2)
                        const spreadOdds = [];
                        const totalOdds = [];
                        const moneylineOdds = [];

                        const gameIndex = i * 2; // Each game has 2 odds entries

                        // Spread odds (2 per game)
                        if (oddsColumns["Spread"] && oddsColumns["Spread"].length > gameIndex + 1) {
                            spreadOdds.push(oddsColumns["Spread"][gameIndex]);
                            spreadOdds.push(oddsColumns["Spread"][gameIndex + 1]);
                        }

                        // Total odds (2 per game)
                        if (oddsColumns["Total"] && oddsColumns["Total"].length > gameIndex + 1) {
                            totalOdds.push(oddsColumns["Total"][gameIndex]);
                            totalOdds.push(oddsColumns["Total"][gameIndex + 1]);
                        }

                        // Money odds (2 per game)
                        if (oddsColumns["Money"] && oddsColumns["Money"].length > gameIndex + 1) {
                            moneylineOdds.push(oddsColumns["Money"][gameIndex]);
                            moneylineOdds.push(oddsColumns["Money"][gameIndex + 1]);
                        }

                        // Create game object
                        results.push({
                            team1: team1,
                            team2: team2,
                            date: gameDate,
                            time: gameTime,
                            spread: spreadOdds,
                            total: totalOdds,
                            moneyline: moneylineOdds,
                            fixture_id: `nba2k_${i}`
                        });
                    }

                    return results;
                }
            """)

            # Process results into Game objects
            for result in extraction_result:
                odds_obj = GameOdds(
                    spread=result['spread'],
                    total=result['total'],
                    moneyline=result['moneyline']
                )

                team1_clean = self.clean_text(result['team1']) or f"Team1_{len(games)}"
                team2_clean = self.clean_text(result['team2']) or f"Team2_{len(games)}"
                date_clean = self.clean_text(result['date'])
                time_clean = self.clean_text(result['time'])

                game = Game(
                    sport=sport,
                    team1=team1_clean,
                    team2=team2_clean,
                    date=date_clean,
                    time=time_clean,
                    odds=odds_obj,
                    fixture_id=result['fixture_id'],
                    game_id=self.generate_game_id(team1_clean, team2_clean, date_clean, time_clean)
                )

                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)

        except Exception as e:
            self.logger.error(f"NBA2K extraction error: {e}")

        self.logger.info(f"NBA2K: Extracted {len(games)} games")
        return games

    async def extract_ncaab_games(self, page, sport: str) -> List[Game]:
        """NCAAB-specific extraction similar to NBA with college basketball teams"""
        games = []
        
        try:
            self.logger.info("🏀 Starting NCAAB extraction...")
            
            # NCAAB extraction using spotlight section detection
            extraction_result = await page.evaluate("""
                () => {
                    const results = [];
                    
                    console.log('🏀 Looking for NCAAB section by SVG logo...');
                    
                    // Step 1: Find NCAAB section by NCAAB logo
                    let ncaabSection = null;
                    
                    // Look for NCAAB section by NCAAB-specific SVG logo
                    const headerImages = document.querySelectorAll('.ss-HomeSpotlightHeader_HeaderImage, .cpm-Header_HeaderImage');
                    for (const img of headerImages) {
                        const style = img.getAttribute('style') || '';
                        if (style.includes('zlogo_ncaab_official.svg')) {
                            ncaabSection = img.closest('.ss-HomepageSpotlight, .cpm-CouponPodModule');
                            console.log('✅ Found NCAAB section by NCAAB logo');
                            break;
                        }
                    }
                    
                    // Fallback: Look for NCAAB or College Basketball title
                    if (!ncaabSection) {
                        const headers = document.querySelectorAll('.ss-HomeSpotlightHeader_Title, .cpm-Header_Title');
                        for (const header of headers) {
                            const titleText = header.textContent.trim();
                            if (titleText === 'NCAAB' || titleText === 'College Basketball') {
                                ncaabSection = header.closest('.ss-HomepageSpotlight, .cpm-CouponPodModule');
                                console.log(`✅ Found NCAAB section by title: ${titleText}`);
                                break;
                            }
                        }
                    }
                    
                    if (!ncaabSection) {
                        console.log('❌ NCAAB section not found');
                        return [];
                    }
                    
                    // Step 2: Extract fixtures from NCAAB section only
                    const fixtures = Array.from(ncaabSection.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball'))
                        .filter(fixture => !fixture.className.includes('Hidden'));
                    
                    console.log(`📋 Found ${fixtures.length} NCAAB fixtures in verified NCAAB section`);
                    
                    // Step 3: Extract odds columns from NCAAB section
                    const oddsColumns = {};
                    
                    const marketOdds = Array.from(ncaabSection.querySelectorAll('div.cpm-MarketOdds'));
                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent;
                            if (headerText) {
                                const headerName = headerText.trim();
                                if (["Spread", "Total", "Money"].includes(headerName)) {
                                    const columnOdds = [];
                                    
                                    // Enhanced: Get both handicap and odds for Spread/Total, just odds for Money
                                    const participantOdds = section.querySelectorAll('.cpm-ParticipantOdds');
                                    for (const participantOdd of participantOdds) {
                                        const handicap = participantOdd.querySelector('.cpm-ParticipantOdds_Handicap');
                                        const oddsValue = participantOdd.querySelector('.cpm-ParticipantOdds_Odds');
                                        
                                        if (headerName === 'Money') {
                                            // Moneyline: just the odds value
                                            if (oddsValue) {
                                                columnOdds.push(oddsValue.textContent.trim());
                                            }
                                        } else {
                                            // Spread/Total: include handicap + odds
                                            if (handicap && oddsValue) {
                                                columnOdds.push(`${handicap.textContent.trim()} ${oddsValue.textContent.trim()}`);
                                            }
                                        }
                                    }
                                    
                                    oddsColumns[headerName] = columnOdds;
                                }
                            }
                        }
                    }
                    
                    // Extract game date with fallback for pregame
                    const dateHeader = ncaabSection.querySelector('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateHeader ? dateHeader.textContent.trim() : null;
                    
                    // Fallback to today's date for pregame if no date found
                    if (!gameDate || gameDate === null) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }
                    
                    // Step 4: Process fixtures and validate they're college basketball teams
                    for (let i = 0; i < fixtures.length; i++) {
                        const fixture = fixtures[i];
                        
                        // Extract team names
                        const teamElems = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball_Team');
                        
                        let team1, team2;
                        if (teamElems.length >= 2) {
                            team1 = teamElems[0].textContent.trim();
                            team2 = teamElems[1].textContent.trim();
                        } else {
                            // Fallback to team containers
                            const teamContainers = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsBasketball_TeamContainer');
                            if (teamContainers.length >= 2) {
                                const t1 = teamContainers[0].querySelector('div.cpm-ParticipantFixtureDetailsBasketball_Team');
                                const t2 = teamContainers[1].querySelector('div.cpm-ParticipantFixtureDetailsBasketball_Team');
                                team1 = t1 ? t1.textContent.trim() : '';
                                team2 = t2 ? t2.textContent.trim() : '';
                            }
                        }
                        
                        // Validate teams (skip if missing or NBA pro teams)
                        const nbaTeams = ['Lakers', 'Celtics', 'Warriors', 'Heat', 'Bucks', 'Nets', 'Clippers', 'Mavericks', 
                                         'Nuggets', '76ers', 'Suns', 'Grizzlies', 'Cavaliers', 'Knicks', 'Thunder'];
                        const hasNBATeam = nbaTeams.some(nba => team1.includes(nba) || team2.includes(nba));
                        
                        // Skip NBA2K gamer tags
                        const nba2kTags = ['(JD)', '(HYPER)', '(CARNAGE)', '(OUTLAW)', '(RIDER)', '(UNBREAKABLE)'];
                        const hasNba2kTag = nba2kTags.some(tag => team1.includes(tag) || team2.includes(tag));
                        
                        if (!team1 || !team2 || hasNBATeam || hasNba2kTag) {
                            console.log(`❌ Filtered out invalid/NBA team: ${team1} vs ${team2}`);
                            continue;
                        }
                        
                        console.log(`✅ Valid NCAAB teams: ${team1} vs ${team2}`);
                        
                        // Extract time
                        const timeElem = fixture.querySelector('div.cpm-ParticipantFixtureDetailsBasketball_BookCloses');
                        const gameTime = timeElem ? timeElem.textContent.trim() : "TBD";
                        
                        // Map odds correctly (each game gets 2 odds per column - team1 and team2)
                        const spreadOdds = [];
                        const totalOdds = [];
                        const moneylineOdds = [];
                        
                        const gameIndex = i * 2; // Each game has 2 odds entries
                        
                        // Spread odds (2 per game)
                        if (oddsColumns["Spread"] && oddsColumns["Spread"].length > gameIndex + 1) {
                            spreadOdds.push(oddsColumns["Spread"][gameIndex]);
                            spreadOdds.push(oddsColumns["Spread"][gameIndex + 1]);
                        }
                        
                        // Total odds (2 per game)
                        if (oddsColumns["Total"] && oddsColumns["Total"].length > gameIndex + 1) {
                            totalOdds.push(oddsColumns["Total"][gameIndex]);
                            totalOdds.push(oddsColumns["Total"][gameIndex + 1]);
                        }
                        
                        // Money odds (2 per game)
                        if (oddsColumns["Money"] && oddsColumns["Money"].length > gameIndex + 1) {
                            moneylineOdds.push(oddsColumns["Money"][gameIndex]);
                            moneylineOdds.push(oddsColumns["Money"][gameIndex + 1]);
                        }
                        
                        // Create game object
                        results.push({
                            team1: team1,
                            team2: team2,
                            date: gameDate,
                            time: gameTime,
                            spread: spreadOdds,
                            total: totalOdds,
                            moneyline: moneylineOdds,
                            fixture_id: `ncaab_${i}`
                        });
                    }
                    
                    console.log(`🏀 Total NCAAB games extracted: ${results.length}`);
                    return results;
                }
            """)
            
            # Process results into Game objects
            for result in extraction_result:
                odds_obj = GameOdds(
                    spread=result['spread'],
                    total=result['total'],
                    moneyline=result['moneyline']
                )
                
                team1_clean = self.clean_text(result['team1']) or f"Team1_{len(games)}"
                team2_clean = self.clean_text(result['team2']) or f"Team2_{len(games)}"
                date_clean = self.clean_text(result['date'])
                time_clean = self.clean_text(result['time'])
                
                game = Game(
                    sport=sport,
                    team1=team1_clean,
                    team2=team2_clean,
                    date=date_clean,
                    time=time_clean,
                    odds=odds_obj,
                    fixture_id=result['fixture_id'],
                    game_id=self.generate_game_id(team1_clean, team2_clean, date_clean, time_clean)
                )
                
                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)
                    
        except Exception as e:
            self.logger.error(f"NCAAB extraction error: {e}")
            
        self.logger.info(f"NCAAB: Extracted {len(games)} games")
        return games

    async def extract_nhl_games(self, grid, sport: str) -> List[Game]:
        """NHL-specific extraction with simplified approach"""
        games = []
        
        try:
            extraction_result = await grid.evaluate("""
                (grid) => {
                    const results = [];
                    
                    // Find all unique team pairs first
                    const gameFixtures = Array.from(grid.querySelectorAll('div[class*="cpm-ParticipantFixtureDetailsIceHockey"]'))
                        .filter(d => !d.className.includes('Hidden'));
                    
                    // Extract date with fallback for pregame
                    const dateEl = grid.querySelector('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateEl ? dateEl.textContent.trim() : null;
                    
                    // Fallback to today's date for pregame if no date found  
                    if (!gameDate || gameDate === null) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }
                    
                    const seenGames = new Set();
                    
                    for (const fixture of gameFixtures) {
                        // Extract teams
                        const teamContainers = Array.from(fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsIceHockey_TeamContainer'));
                        const teams = [];
                        
                        for (const container of teamContainers) {
                            const teamEl = container.querySelector('div.cpm-ParticipantFixtureDetailsIceHockey_Team');
                            if (teamEl) {
                                teams.push(teamEl.textContent.trim());
                            }
                        }
                        
                        if (teams.length < 2) continue;
                        
                        // Create unique game signature to avoid duplicates
                        const gameSignature = `${teams[0]} vs ${teams[1]}`;
                        if (seenGames.has(gameSignature)) continue;
                        seenGames.add(gameSignature);
                        
                        // Extract time
                        const timeEl = fixture.querySelector('div.cpm-ParticipantFixtureDetailsIceHockey_BookCloses');
                        const gameTime = timeEl ? timeEl.textContent.trim() : null;
                        
                        // NHL: Extract spread, total, AND moneyline odds (user wants all three)
                        const odds = {};
                        const oddsColumns = Array.from(grid.querySelectorAll('div.cpm-MarketOdds'));
                        
                        if (oddsColumns.length > 0) {
                            // Extract ALL odds types: spread, total, and moneyline
                            for (const column of oddsColumns) {
                                const header = column.querySelector('.cpm-MarketOddsHeader');
                                if (header) {
                                    const headerText = header.textContent.toLowerCase().trim();
                                    
                                    // Map header text to odds type
                                    let oddsType = null;
                                    if (headerText === 'money' || headerText === 'moneyline') {
                                        oddsType = 'moneyline';
                                    } else if (headerText.includes('spread') || headerText.includes('puck') || headerText.includes('handicap')) {
                                        oddsType = 'spread';
                                    } else if (headerText.includes('total') || headerText.includes('over') || headerText.includes('under')) {
                                        oddsType = 'total';
                                    }
                                    
                                    if (oddsType) {
                                        const columnOdds = Array.from(column.querySelectorAll('.cpm-ParticipantOdds'));
                                        const gameIndex = results.length;
                                        const startIndex = gameIndex * 2;
                                        
                                        if (columnOdds.length > startIndex + 1) {
                                            const odds1 = columnOdds[startIndex];
                                            const odds2 = columnOdds[startIndex + 1];
                                            
                                            let p1, p2;
                                            
                                            if (oddsType === 'moneyline') {
                                                // Moneyline: just odds values
                                                p1 = odds1?.querySelector('.cpm-ParticipantOdds_Odds')?.textContent?.trim();
                                                p2 = odds2?.querySelector('.cpm-ParticipantOdds_Odds')?.textContent?.trim();
                                            } else {
                                                // Spread/Total: include handicap + odds (clean format like NCAAF)
                                                const h1 = odds1?.querySelector('.cpm-ParticipantOdds_Handicap')?.textContent?.trim();
                                                const o1 = odds1?.querySelector('.cpm-ParticipantOdds_Odds')?.textContent?.trim();
                                                const h2 = odds2?.querySelector('.cpm-ParticipantOdds_Handicap')?.textContent?.trim();
                                                const o2 = odds2?.querySelector('.cpm-ParticipantOdds_Odds')?.textContent?.trim();
                                                
                                                p1 = (h1 && o1) ? `${h1} ${o1}` : o1;
                                                p2 = (h2 && o2) ? `${h2} ${o2}` : o2;
                                            }
                                            
                                            if (p1 && p2) {
                                                odds[oddsType] = [p1, p2];
                                                console.log(`NHL: Extracted ${oddsType} odds: [${p1}, ${p2}]`);
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        const game = {
                            teams: teams,
                            time: gameTime,
                            date: gameDate,  // Add date field
                            league: 'NHL',
                            odds: Object.keys(odds).length > 0 ? odds : null,
                            confidence: teams.length > 1 ? 0.9 : 0.5
                        };
                        
                        results.push(game);
                        console.log('Extracted NHL game:', teams.join(' vs '));
                    }
                    
                    return results;
                }
            """)
            
            # Process results
            for idx, result in enumerate(extraction_result):
                teams = result.get('teams', [])
                if len(teams) < 2:
                    continue
                    
                team1 = self.clean_text(teams[0]) or f"Team1_{idx}"
                team2 = self.clean_text(teams[1]) or f"Team2_{idx}"
                date_clean = self.clean_text(result.get('date'))
                time_clean = self.clean_text(result.get('time'))
                
                odds_data = result.get('odds') or {}
                # NHL: Include spread, total, AND moneyline per user request
                odds_obj = GameOdds(
                    spread=odds_data.get('spread', []),
                    total=odds_data.get('total', []),
                    moneyline=odds_data.get('moneyline', [])
                )
                
                game = Game(
                    sport=sport,
                    team1=team1,
                    team2=team2,
                    date=date_clean,
                    time=time_clean,
                    odds=odds_obj,
                    fixture_id=f"{sport.lower()}_{idx}",
                    game_id=self.generate_game_id(team1, team2, date_clean, time_clean)
                )
                
                game.confidence_score = result.get('confidence', 0.9) * 100
                
                if game.confidence_score >= 30.0:
                    games.append(game)
                    
        except Exception as e:
            self.logger.error(f"NHL extraction error: {e}")
            
        self.logger.info(f"NHL: Extracted {len(games)} games")
        return games

    async def extract_football_games(self, grid, sport: str) -> List[Game]:
        """NCAAF/NFL extraction with enhanced debugging and flexible detection"""
        games = []
        
        try:
            extraction_result = await grid.evaluate("""
                (grid) => {
                    const results = [];
                    const seenGames = new Set();
                    
                    console.log('🏈 Starting football extraction...');
                    
                    // Enhanced search for football fixtures with multiple approaches
                    let gameFixtures = [];
                    
                    // Primary: Exact American Football class
                    gameFixtures = Array.from(grid.querySelectorAll('div.cpm-ParticipantFixtureDetailsAmericanFootball'))
                        .filter(d => !d.className.includes('Hidden'));
                    console.log(`Primary search: Found ${gameFixtures.length} American Football fixtures`);
                    
                    // Secondary: Look for any football/sport fixtures in the entire page
                    if (gameFixtures.length === 0) {
                        console.log('Expanding search to entire document...');
                        gameFixtures = Array.from(document.querySelectorAll('div.cpm-ParticipantFixtureDetailsAmericanFootball'))
                            .filter(d => !d.className.includes('Hidden'));
                        console.log(`Document-wide search: Found ${gameFixtures.length} American Football fixtures`);
                    }
                    
                    // Tertiary: Look for spotlight sections that might contain college games
                    if (gameFixtures.length === 0) {
                        console.log('Searching spotlight sections for college games...');
                        const spotlights = Array.from(document.querySelectorAll('div.ss-HomepageSpotlight'));
                        console.log(`Found ${spotlights.length} spotlight sections`);
                        
                        for (const spotlight of spotlights) {
                            const text = spotlight.textContent.toLowerCase();
                            // Look for college/NCAAF indicators
                            if (text.includes('week') || text.includes('colorado') || text.includes('utah') || 
                                text.includes('college') || text.includes('ncaa')) {
                                console.log('Found potential college spotlight:', text.substring(0, 100));
                                const spotlightFixtures = Array.from(spotlight.querySelectorAll('div[class*="ParticipantFixture"]'));
                                gameFixtures.push(...spotlightFixtures);
                            }
                        }
                        console.log(`After spotlight search: Found ${gameFixtures.length} potential fixtures`);
                    }
                    
                    // Final fallback: Any fixture details that might be football
                    if (gameFixtures.length === 0) {
                        const allFixtures = Array.from(grid.querySelectorAll('div[class*="cpm-ParticipantFixtureDetails"]'))
                            .filter(d => !d.className.includes('Hidden'));
                        console.log(`Final fallback: Found ${allFixtures.length} total fixtures`);
                        
                        // Filter for likely football fixtures by checking content
                        for (const fixture of allFixtures) {
                            const text = fixture.textContent.toLowerCase();
                            // Look for typical football indicators or specific teams we know about
                            if (text.includes('spread') || text.includes('total') || text.includes('moneyline') || 
                                text.includes('vs') || text.includes(' - ') || text.includes('colorado') || text.includes('utah')) {
                                gameFixtures.push(fixture);
                            }
                        }
                        console.log(`After final filtering: Found ${gameFixtures.length} potential football fixtures`);
                    }
                    
                    for (let i = 0; i < gameFixtures.length; i++) {
                        const fixture = gameFixtures[i];
                        
                        // Enhanced team extraction with multiple fallback approaches
                        let teams = [];
                        
                        // Approach 1: Exact American Football class names
                        const exactContainers = Array.from(fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsAmericanFootball_TeamContainer'));
                        console.log(`Fixture ${i}: Found ${exactContainers.length} exact team containers`);
                        
                        for (const container of exactContainers) {
                            const teamEl = container.querySelector('div.cpm-ParticipantFixtureDetailsAmericanFootball_Team');
                            if (teamEl) {
                                const teamText = teamEl.textContent.trim();
                                console.log(`  Exact method team: "${teamText}"`);
                                if (teamText && teamText.length > 1) {
                                    teams.push(teamText);
                                }
                            }
                        }
                        
                        // Approach 2: Generic team container patterns
                        if (teams.length < 2) {
                            console.log(`  Trying wildcard approach for fixture ${i}...`);
                            const wildcardContainers = Array.from(fixture.querySelectorAll('div[class*="_TeamContainer"]'));
                            console.log(`  Found ${wildcardContainers.length} wildcard containers`);
                            
                            for (const container of wildcardContainers) {
                                const teamEl = container.querySelector('div[class*="_Team"]');
                                if (teamEl) {
                                    const teamText = teamEl.textContent.trim();
                                    console.log(`  Wildcard method team: "${teamText}"`);
                                    if (teamText && teamText.length > 1 && !teams.includes(teamText)) {
                                        teams.push(teamText);
                                    }
                                }
                            }
                        }
                        
                        // Approach 3: Look for any text elements that might be team names
                        if (teams.length < 2) {
                            console.log(`  Trying text-based team extraction for fixture ${i}...`);
                            const allDivs = Array.from(fixture.querySelectorAll('div'));
                            for (const div of allDivs) {
                                const text = div.textContent.trim();
                                const directChildren = div.children.length;
                                
                                // Look for divs with text but few children (likely team names)
                                if (text && text.length > 2 && text.length < 50 && directChildren < 3) {
                                    // Filter out obvious non-team elements
                                    if (!text.includes(':') && !text.includes('+') && !text.includes('-') && 
                                        !text.includes('PM') && !text.includes('AM') && !text.includes('View') &&
                                        !text.match(/^\\d+$/) && !teams.includes(text)) {
                                        console.log(`  Text-based method found potential team: "${text}"`);
                                        teams.push(text);
                                        if (teams.length >= 2) break;
                                    }
                                }
                            }
                        }
                        
                        // Approach 4: Specific search for known college teams (Colorado, Utah)
                        if (teams.length < 2) {
                            console.log(`  Searching specifically for Colorado/Utah...`);
                            const allText = fixture.textContent.toLowerCase();
                            const knownTeams = ['colorado', 'utah', 'buffaloes', 'utes', 'cu', 'colorado state'];
                            
                            for (const teamName of knownTeams) {
                                if (allText.includes(teamName)) {
                                    console.log(`  Found potential college team: ${teamName}`);
                                    // Try to extract the actual display name
                                    const textNodes = fixture.querySelectorAll('*');
                                    for (const node of textNodes) {
                                        const nodeText = node.textContent.trim();
                                        if (nodeText.toLowerCase().includes(teamName) && nodeText.length < 30) {
                                            teams.push(nodeText);
                                            console.log(`  Added college team: "${nodeText}"`);
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                        
                        if (teams.length < 2) {
                            console.log(`Skipping fixture - only found ${teams.length} teams:`, teams);
                            continue;
                        }
                        
                        // Create unique game signature to avoid duplicates
                        const gameSignature = `${teams[0]} vs ${teams[1]}`;
                        if seenGames.has(gameSignature) continue;
                        seenGames.add(gameSignature);
                        
                        // Extract time
                        const timeEl = fixture.querySelector('div.cpm-ParticipantFixtureDetailsAmericanFootball_BookCloses');
                        const gameTime = timeEl ? timeEl.textContent.trim() : null;
                        
                        // Extract odds from parent grid structure  
                        const odds = {};
                        
                        // Find all odds columns in the same container
                        const parentGrid = fixture.closest('div[class*="cpm-CouponPodMarketGrid"]');
                        
                        if (parentGrid) {
                            const oddsColumns = Array.from(parentGrid.querySelectorAll('div.cpm-MarketOdds'));
                            
                            // Process each column to extract different odds types
                            for (const column of oddsColumns) {
                                const header = column.querySelector('.cpm-MarketOddsHeader');
                                const headerText = header ? header.textContent.trim().toLowerCase() : '';
                                
                                let category = null;
                                if (headerText === 'money' || headerText.includes('moneyline')) {
                                    category = 'moneyline';
                                } else if (headerText.includes('spread') || headerText.includes('handicap')) {
                                    category = 'spread';
                                } else if (headerText.includes('total') || headerText.includes('over/under')) {
                                    category = 'total';
                                }
                                
                                if (category) {
                                    const columnOdds = Array.from(column.querySelectorAll('.cpm-ParticipantOdds'));
                                    
                                    // Calculate which odds belong to this game (each game = 2 odds rows)
                                    const gameIndex = results.length;
                                    const startIndex = gameIndex * 2;
                                    
                                    if (columnOdds.length > startIndex + 1) {
                                        const odds1 = columnOdds[startIndex];
                                        const odds2 = columnOdds[startIndex + 1];
                                        
                                        const h1 = odds1?.querySelector('.cpm-ParticipantOdds_Handicap')?.textContent?.trim() || '';
                                        const p1 = odds1?.querySelector('.cpm-ParticipantOdds_Odds')?.textContent?.trim() || '';
                                        const h2 = odds2?.querySelector('.cpm-ParticipantOdds_Handicap')?.textContent?.trim() || '';
                                        const p2 = odds2?.querySelector('.cpm-ParticipantOdds_Odds')?.textContent?.trim() || '';
                                        
                                        // Validate that we have actual odds values
                                        if (p1 && p2 && (p1.includes('+') || p1.includes('-')) && (p2.includes('+') || p2.includes('-'))) {
                                            if (category === 'moneyline') {
                                                odds[category] = [p1, p2];
                                            } else {
                                                // ENHANCED: Include handicap (+/-) and odds values for spread/total
                                                odds[category] = [
                                                    h1 ? `${h1} (${p1})` : p1,
                                                    h2 ? `${h2} (${p2})` : p2
                                                ];
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        
                        // Get current date as fallback for pregame
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        const gameDate = today.toLocaleDateString('en-US', options);
                        
                        const game = {
                            teams: teams,
                            time: gameTime,
                            date: gameDate,  // Add date field
                            league: 'NCAAF',
                            odds: odds,
                            confidence: teams.length > 1 ? 0.9 : 0.5
                        };
                        
                        results.push(game);
                    }
                    
                    console.log(`Total NCAAF/NFL games extracted: ${results.length}`);
                    return results;
                }
            """)
            
            # Process results with enhanced logging and flexible filtering
            self.logger.info(f"🏈 Processing {len(extraction_result)} {sport} extraction results...")
            
            potential_games = []  # Store all potential games before filtering
            
            for idx, result in enumerate(extraction_result):
                teams = result.get('teams', [])
                if len(teams) < 2:
                    self.logger.debug(f"Skipping result {idx}: insufficient teams ({len(teams)})")
                    continue
                    
                team1 = self.clean_text(teams[0]) or f"Team1_{idx}"
                team2 = self.clean_text(teams[1]) or f"Team2_{idx}"
                
                self.logger.debug(f"Processing {sport} match: {team1} vs {team2}")
                
                # Store all games with their NFL classification
                is_nfl = self._is_nfl_team(team1, team2)
                potential_games.append((idx, result, team1, team2, is_nfl))
            
            # Apply filtering logic based on what we found
            filtered_games = []
            nfl_games_found = sum(1 for _, _, _, _, is_nfl in potential_games if is_nfl)
            college_games_found = len(potential_games) - nfl_games_found
            
            self.logger.info(f"🏈 Found {nfl_games_found} NFL games and {college_games_found} college games")
            
            for idx, result, team1, team2, is_nfl in potential_games:
                # Apply normal filtering
                if sport == "NCAAF" and is_nfl:
                    # If we're looking for NCAAF but only found NFL games, be more permissive
                    if college_games_found == 0:
                        self.logger.warning(f"⚠️ NCAAF tab contains NFL games - keeping as fallback: {team1} vs {team2}")
                        # Keep the game but mark it with special handling
                        filtered_games.append((idx, result, team1, team2, "nfl_fallback"))
                    else:
                        self.logger.info(f"🚫 Filtering NFL team from NCAAF: {team1} vs {team2}")
                        continue
                elif sport == "NFL" and not is_nfl:
                    self.logger.info(f"🚫 Filtering college team from NFL: {team1} vs {team2}")
                    continue
                else:
                    self.logger.debug(f"✅ Accepted {sport} match: {team1} vs {team2} (is_nfl: {is_nfl})")
                    filtered_games.append((idx, result, team1, team2, "normal"))
                
            # Create games from filtered results
            for idx, result, team1, team2, game_type in filtered_games:
                odds_data = result.get('odds') or {}
                odds_obj = GameOdds(
                    moneyline=odds_data.get('moneyline', []),
                    spread=odds_data.get('spread', []),
                    total=odds_data.get('total', [])
                )
                
                # Adjust sport label if this is a fallback case
                effective_sport = sport
                if game_type == "nfl_fallback":
                    # Keep NCAAF label but add a note in the fixture_id
                    fixture_id = f"{sport.lower()}_nfl_fallback_{idx}"
                    self.logger.info(f"🏈 Creating NCAAF game from NFL fallback: {team1} vs {team2}")
                else:
                    fixture_id = f"{sport.lower()}_{idx}"
                
                game = Game(
                    sport=effective_sport,
                    team1=team1,
                    team2=team2,
                    date=self.clean_text(result.get('date')),
                    time=self.clean_text(result.get('time')),
                    odds=odds_obj,
                    fixture_id=fixture_id
                )
                
                game.confidence_score = result.get('confidence', 0.9) * 100
                
                # Be more lenient with confidence for fallback games
                min_confidence = 20.0 if game_type == "nfl_fallback" else 30.0
                
                if game.confidence_score >= min_confidence:
                    games.append(game)
                    
        except Exception as e:
            self.logger.error(f"{sport} extraction error: {e}")
            
        self.logger.info(f"{sport}: Extracted {len(games)} games")
        return games

    async def extract_ncaaf_games(self, page, sport: str) -> List[Game]:
        """NCAAF-specific extraction from homepage spotlight sections"""
        games = []
        
        try:
            self.logger.info("🏈 Starting NCAAF extraction from spotlight sections...")
            
            # Look for NCAAF spotlight sections specifically
            extraction_result = await page.evaluate("""
                () => {
                    const results = [];
                    
                    console.log('🏈 Searching for NCAAF spotlight sections...');
                    
                    // NFL teams to filter out - comprehensive list
                    const nflTeams = new Set([
                        'Arizona Cardinals', 'Atlanta Falcons', 'Baltimore Ravens', 'Buffalo Bills',
                        'Carolina Panthers', 'Chicago Bears', 'Cincinnati Bengals', 'Cleveland Browns',
                        'Dallas Cowboys', 'Denver Broncos', 'Detroit Lions', 'Green Bay Packers',
                        'Houston Texans', 'Indianapolis Colts', 'Jacksonville Jaguars', 'Kansas City Chiefs',
                        'Las Vegas Raiders', 'Los Angeles Chargers', 'Los Angeles Rams', 'Miami Dolphins',
                        'Minnesota Vikings', 'New England Patriots', 'New Orleans Saints', 'New York Giants',
                        'New York Jets', 'Philadelphia Eagles', 'Pittsburgh Steelers', 'San Francisco 49ers',
                        'Seattle Seahawks', 'Tampa Bay Buccaneers', 'Tennessee Titans', 'Washington Commanders',
                        // Abbreviated versions
                        'ARI Cardinals', 'ATL Falcons', 'BAL Ravens', 'BUF Bills', 'CAR Panthers', 
                        'CHI Bears', 'CIN Bengals', 'CLE Browns', 'DAL Cowboys', 'DEN Broncos',
                        'DET Lions', 'GB Packers', 'HOU Texans', 'IND Colts', 'JAX Jaguars', 'KC Chiefs',
                        'LV Raiders', 'LAC Chargers', 'LAR Rams', 'MIA Dolphins', 'MIN Vikings',
                        'NE Patriots', 'NO Saints', 'NY Giants', 'NY Jets', 'PHI Eagles', 'PIT Steelers',
                        'SF 49ers', 'SEA Seahawks', 'TB Buccaneers', 'TEN Titans', 'WAS Commanders'
                    ]);
                    
                    // Function to check if team name contains NFL teams
                    function isNFLTeam(teamName) {
                        const cleanTeam = teamName.trim();
                        return nflTeams.has(cleanTeam) || 
                               Array.from(nflTeams).some(nflTeam => 
                                   cleanTeam.includes(nflTeam) || nflTeam.includes(cleanTeam.split(' ')[0])
                               );
                    }
                    
                    // Find all spotlight sections
                    const spotlights = Array.from(document.querySelectorAll('div.ss-HomepageSpotlight'));
                    console.log(`Found ${spotlights.length} total spotlight sections`);
                    
                    for (const spotlight of spotlights) {
                        // Look for NCAAF logo indicator - must be very specific
                        const headerImages = spotlight.querySelectorAll('div[style*="zlogo_ncaaf_official.svg"]');
                        const headerTitles = spotlight.querySelectorAll('div.ss-HomeSpotlightHeader_Title, div.cpm-Header_Title');
                        
                        let isNCAA = false;
                        let weekInfo = null;
                        
                        // Check for NCAAF logo - this is the most reliable indicator
                        if (headerImages.length > 0) {
                            console.log('Found NCAAF logo in spotlight section');
                            isNCAA = true;
                        }
                        
                        // Check for week header (Week X) - but only if we also have NCAAF logo
                        for (const title of headerTitles) {
                            const titleText = title.textContent.trim();
                            if (titleText.match(/Week \\d+/i) && headerImages.length > 0) {
                                console.log(`Found week header with NCAAF logo: ${titleText}`);
                                weekInfo = titleText;
                            }
                        }
                        
                        // Only proceed if we found NCAAF logo
                        if (!isNCAA) continue;
                        
                        console.log(`Processing NCAAF spotlight section with ${weekInfo || 'unknown week'}`);
                        
                        // Extract games from this NCAAF section - but only within this specific section
                        const gameFixtures = Array.from(spotlight.querySelectorAll('div.cpm-ParticipantFixtureDetailsAmericanFootball'))
                            .filter(d => !d.className.includes('Hidden'));
                        
                        console.log(`Found ${gameFixtures.length} fixtures in NCAAF section`);
                        
                        for (let i = 0; i < gameFixtures.length; i++) {
                            const fixture = gameFixtures[i];
                            
                            // Extract teams using NCAAF-specific structure
                            let teams = [];
                            
                            const teamContainers = Array.from(fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsAmericanFootball_TeamContainer'));
                            console.log(`Fixture ${i}: Found ${teamContainers.length} team containers`);
                            
                            for (const container of teamContainers) {
                                const teamEl = container.querySelector('div.cpm-ParticipantFixtureDetailsAmericanFootball_Team');
                                if (teamEl) {
                                    const teamText = teamEl.textContent.trim();
                                    console.log(`  Found team: "${teamText}"`);
                                    if (teamText && teamText.length > 1) {
                                        teams.push(teamText);
                                    }
                                }
                            }
                            
                            if (teams.length < 2) {
                                console.log(`Skipping fixture - only found ${teams.length} teams`);
                                continue;
                            }
                            
                            // Critical: Filter out NFL teams - this is the key fix
                            const isNFL1 = isNFLTeam(teams[0]);
                            const isNFL2 = isNFLTeam(teams[1]);
                            
                            if (isNFL1 || isNFL2) {
                                console.log(`🚫 Skipping NFL teams: ${teams[0]} vs ${teams[1]}`);
                                continue;
                            }
                            
                            console.log(`✅ Valid NCAAF teams: ${teams[0]} vs ${teams[1]}`);
                            
                            
                            // Extract time/clock info
                            let gameTime = null;
                            const clockEl = fixture.querySelector('div.cpm-ParticipantFixtureDetailsAmericanFootball_Clock, div.cpm-ParticipantFixtureDetailsAmericanFootball_BookCloses');
                            if (clockEl) {
                                gameTime = clockEl.textContent.trim();
                            }
                            
                            // Extract date
                            let gameDate = null;
                            const dateEl = fixture.closest('div.gl-MarketGroup')?.querySelector('div.cpm-MarketFixtureDateHeader');
                            if (dateEl) {
                                gameDate = dateEl.textContent.trim();
                            }
                            
                            // Extract odds from the odds columns - but only within this spotlight section
                            const odds = {};
                            
                            // Make sure we stay within the current spotlight section for odds extraction
                            const parentGrid = fixture.closest('div.cpm-CouponPodMarketGrid');
                            
                            // Double-check that this odds grid is still within our NCAAF spotlight section
                            if (parentGrid && spotlight.contains(parentGrid)) {
                                const oddsColumns = Array.from(parentGrid.querySelectorAll('div.cpm-MarketOdds'));
                                
                                for (const column of oddsColumns) {
                                    const header = column.querySelector('.cpm-MarketOddsHeader');
                                    const headerText = header ? header.textContent.trim().toLowerCase() : '';
                                    
                                    let category = null;
                                    if (headerText === 'money' || headerText.includes('moneyline')) {
                                        category = 'moneyline';
                                    } else if (headerText.includes('spread') || headerText.includes('handicap')) {
                                        category = 'spread';
                                    } else if (headerText.includes('total') || headerText.includes('over/under')) {
                                        category = 'total';
                                    }
                                    
                                    if (category) {
                                        const columnOdds = Array.from(column.querySelectorAll('.cpm-ParticipantOdds'));
                                        
                                        if (columnOdds.length >= 2) {
                                            const odds1 = columnOdds[0];
                                            const odds2 = columnOdds[1];
                                            
                                            const h1 = odds1?.querySelector('.cpm-ParticipantOdds_Handicap')?.textContent?.trim() || '';
                                            const p1 = odds1?.querySelector('.cpm-ParticipantOdds_Odds')?.textContent?.trim() || '';
                                            const h2 = odds2?.querySelector('.cpm-ParticipantOdds_Handicap')?.textContent?.trim() || '';
                                            const p2 = odds2?.querySelector('.cpm-ParticipantOdds_Odds')?.textContent?.trim() || '';
                                            
                                            // Format odds properly
                                            if (p1 && p2) {
                                                if (category === 'moneyline') {
                                                    odds[category] = [p1, p2];
                                                } else {
                                                    // Include handicap values for spread/total
                                                    odds[category] = [
                                                        h1 ? `${h1} ${p1}` : p1,
                                                        h2 ? `${h2} ${p2}` : p2
                                                    ];
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                            
                            const game = {
                                teams: teams,
                                time: gameTime,
                                date: gameDate,
                                week: weekInfo,
                                league: 'NCAAF',
                                odds: odds,
                                confidence: 0.95
                            };
                            
                            results.push(game);
                            console.log(`Added NCAAF game: ${teams[0]} vs ${teams[1]}`);
                        }
                    }
                    
                    console.log(`Total NCAAF games extracted: ${results.length}`);
                    return results;
                }
            """)
            
            # Process results
            for idx, result in enumerate(extraction_result):
                teams = result.get('teams', [])
                if len(teams) < 2:
                    continue
                    
                team1 = self.clean_text(teams[0]) or f"Team1_{idx}"
                team2 = self.clean_text(teams[1]) or f"Team2_{idx}"
                date_clean = self.clean_text(result.get('date'))
                time_clean = self.clean_text(result.get('time'))
                
                self.logger.info(f"🏈 Found NCAAF game: {team1} vs {team2}")
                
                odds_data = result.get('odds') or {}
                odds_obj = GameOdds(
                    moneyline=odds_data.get('moneyline', []),
                    spread=odds_data.get('spread', []),
                    total=odds_data.get('total', [])
                )
                
                game = Game(
                    sport=sport,
                    team1=team1,
                    team2=team2,
                    date=date_clean,
                    time=time_clean,
                    odds=odds_obj,
                    fixture_id=f"ncaaf_{idx}",
                    game_id=self.generate_game_id(team1, team2, date_clean, time_clean)
                )
                
                game.confidence_score = result.get('confidence', 0.95) * 100
                games.append(game)
                
        except Exception as e:
            self.logger.error(f"NCAAF extraction error: {e}")
            
        self.logger.info(f"NCAAF: Extracted {len(games)} games")
        return games

    def _is_nfl_team(self, team1: str, team2: str) -> bool:
        """Check if teams are NFL teams using precise team names"""
        # NFL team names - using full team names to avoid false positives
        nfl_teams = [
            # AFC East
            "new england patriots", "miami dolphins", "buffalo bills", "new york jets",
            # AFC North  
            "baltimore ravens", "cincinnati bengals", "cleveland browns", "pittsburgh steelers",
            # AFC South
            "houston texans", "indianapolis colts", "jacksonville jaguars", "tennessee titans",
            # AFC West
            "denver broncos", "kansas city chiefs", "las vegas raiders", "los angeles chargers",
            # NFC East
            "dallas cowboys", "new york giants", "philadelphia eagles", "washington commanders",
            # NFC North
            "chicago bears", "detroit lions", "green bay packers", "minnesota vikings",
            # NFC South
            "atlanta falcons", "carolina panthers", "new orleans saints", "tampa bay buccaneers",
            # NFC West  
            "arizona cardinals", "los angeles rams", "san francisco 49ers", "seattle seahawks"
        ]
        
        # NFL city names that are unique identifiers
        nfl_cities = [
            "patriots", "dolphins", "bills", "jets",
            "ravens", "bengals", "browns", "steelers", 
            "texans", "colts", "jaguars", "titans",
            "broncos", "chiefs", "raiders", "chargers",
            "cowboys", "giants", "eagles", "commanders",
            "bears", "lions", "packers", "vikings",
            "falcons", "panthers", "saints", "buccaneers",
            "cardinals", "rams", "49ers", "seahawks"
        ]
        
        # NFL abbreviations (must be exact matches)
        nfl_abbreviations = [
            "ne ", "mia ", "buf ", "nyj ",
            "bal ", "cin ", "cle ", "pit ",
            "hou ", "ind ", "jax ", "ten ",
            "den ", "kc ", "lv ", "lac ",
            "dal ", "nyg ", "phi ", "was ",
            "chi ", "det ", "gb ", "min ",
            "atl ", "car ", "no ", "tb ",
            "ari ", "lar ", "sf ", "sea "
        ]
        
        combined_teams = f"{team1} {team2}".lower()
        
        # Check for exact NFL team names
        for team_name in nfl_teams:
            if team_name in combined_teams:
                return True
                
        # Check for NFL team nicknames (but be more careful about context)
        # Only check if the team name appears as a complete word
        import re
        for nickname in nfl_cities:
            # Use word boundaries to avoid partial matches
            if re.search(rf'\b{re.escape(nickname)}\b', combined_teams):
                # Additional check: make sure it's not part of a college name
                # Skip if it contains typical college indicators
                college_indicators = ['state', 'university', 'tech', 'college', 'institute', 'colorado', 'utah', 'buffaloes', 'utes']
                if any(indicator in combined_teams for indicator in college_indicators):
                    continue
                return True
        
        # Check for NFL abbreviations (exact matches with spaces)
        team_text_spaced = f" {combined_teams} "
        for abbrev in nfl_abbreviations:
            if abbrev in team_text_spaced:
                return True
        
        return False

    async def extract_tennis_games(self, grid, sport: str) -> List[Game]:
        """Fast Tennis extraction following exact HTML structure pattern"""
        games = []
        
        try:
            self.logger.info("🎾 Starting fast Tennis extraction...")
            
            # Fast Tennis extraction using ATP/WTA section detection
            extraction_result = await grid.evaluate("""
                (grid) => {
                    const results = [];
                    
                    console.log('🎾 Starting Tennis extraction...');
                    
                    // Step 1: Find Tennis section by icon
                    let tennisSection = null;
                    
                    // Method 1: Look for Tennis SVG logo in header images
                    const headerImages = document.querySelectorAll('.ss-HomeSpotlightHeader_HeaderImage, .cpm-Header_HeaderImage');
                    for (const img of headerImages) {
                        const style = img.getAttribute('style') || '';
                        if (style.includes('zClass_Tennis.svg')) {
                            tennisSection = img.closest('.ss-HomepageSpotlight, .cpm-CouponPodModule');
                            console.log('✅ Found Tennis section by Tennis SVG');
                            break;
                        }
                    }
                    
                    // Method 2: Look for tennis class or text as backup
                    if (!tennisSection) {
                        const headers = document.querySelectorAll('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                        for (const header of headers) {
                            if (header.textContent.trim().includes('ATP') || header.textContent.trim().includes('WTA') || header.textContent.trim().includes('Tennis')) {
                                tennisSection = header.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                console.log('✅ Found Tennis section by title text');
                                break;
                            }
                        }
                    }
                    
                    if (!tennisSection) {
                        console.log('❌ Tennis section not found by icon/text detection');
                        return [];
                    }
                    
                    console.log('Found Tennis section');
                    
                    // Step 2: Extract fixtures from tennis section only
                    const fixtures = Array.from(tennisSection.querySelectorAll('div.cpm-ParticipantFixtureDetails'))
                        .filter(fixture => !fixture.className.includes('Hidden'));
                    
                    console.log(`Found ${fixtures.length} tennis fixtures`);
                    
                    // Step 3: Extract odds columns data from tennis section
                    const oddsColumns = {};
                    
                    // Find column "1" odds within tennis section
                    const col1Section = tennisSection.querySelector('div.cpm-MarketOdds');
                    if (col1Section) {
                        const col1Header = col1Section.querySelector('div.cpm-MarketOddsHeader');
                        if (col1Header && col1Header.textContent.trim() === "1") {
                            const col1Odds = [];
                            const oddsElems = col1Section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                            for (const oddsElem of oddsElems) {
                                const oddsText = oddsElem.textContent;
                                if (oddsText) {
                                    col1Odds.push(oddsText.trim());
                                }
                            }
                            oddsColumns["1"] = col1Odds;
                        }
                    }
                    
                    // Find column "2" odds within tennis section
                    const col2Sections = Array.from(tennisSection.querySelectorAll('div.cpm-MarketOdds'));
                    for (const section of col2Sections) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header && header.textContent.trim() === "2") {
                            const col2Odds = [];
                            const oddsElems = section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                            for (const oddsElem of oddsElems) {
                                const oddsText = oddsElem.textContent;
                                if (oddsText) {
                                    col2Odds.push(oddsText.trim());
                                }
                            }
                            oddsColumns["2"] = col2Odds;
                            break;
                        }
                    }
                    
                    // Extract game date with fallback for pregame
                    const dateHeader = grid.querySelector('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateHeader ? dateHeader.textContent.trim() : null;
                    
                    // Fallback to today's date for pregame if no date found
                    if (!gameDate || gameDate === null) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }
                    
                    // Step 3: Process fixtures and map odds correctly
                    for (let i = 0; i < fixtures.length; i++) {
                        const fixture = fixtures[i];
                        
                        // Extract player names using multiple methods
                        const teamElems = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetails_Team');
                        
                        let player1, player2;
                        
                        if (teamElems.length >= 2) {
                            // Method 1: Direct team elements
                            player1 = teamElems[0].textContent;
                            player2 = teamElems[1].textContent;
                        } else {
                            // Method 2: Parse from fixture text
                            const fixtureText = fixture.textContent;
                            if (!fixtureText.includes(' v ')) continue;
                            
                            const players = fixtureText.split(' v ');
                            if (players.length < 2) continue;
                            
                            player1 = players[0].trim();
                            player2 = players[1].trim();
                        }
                        
                        player1 = player1.trim();
                        player2 = player2.trim();
                        
                        // Validate tennis match (relaxed validation)
                        if (!player1 || !player2 || player1.length < 3 || player2.length < 3) continue;
                        
                        // Extract time
                        const timeElem = fixture.querySelector('div.cpm-ParticipantFixtureDetails_BookCloses, [class*="BookCloses"], [class*="Time"]');
                        const gameTime = timeElem ? timeElem.textContent : "TBD";
                        
                        // Map odds correctly to players
                        const moneylineOdds = [];
                        
                        // Player 1 gets odds from column "1", Player 2 gets odds from column "2"
                        if (oddsColumns["1"] && oddsColumns["1"].length > i) {
                            moneylineOdds.push(oddsColumns["1"][i]);  // Player 1 odds
                        }
                        
                        if (oddsColumns["2"] && oddsColumns["2"].length > i) {
                            moneylineOdds.push(oddsColumns["2"][i]);  // Player 2 odds
                        }
                        
                        // Create game object
                        results.push({
                            team1: player1,
                            team2: player2,
                            date: gameDate,
                            time: gameTime.trim(),
                            moneyline: moneylineOdds,
                            fixture_id: `tennis_${i}`
                        });
                    }
                    
                    return results;
                }
            """)
            
            # Process results into Game objects
            for result in extraction_result:
                odds_obj = GameOdds(
                    spread=[],
                    total=[],
                    moneyline=result['moneyline']
                )
                
                game = Game(
                    sport=sport,
                    team1=self.clean_text(result['team1']) or f"Team1_{len(games)}",
                    team2=self.clean_text(result['team2']) or f"Team2_{len(games)}",
                    date=self.clean_text(result['date']),
                    time=self.clean_text(result['time']),
                    odds=odds_obj,
                    fixture_id=result['fixture_id']
                )
                
                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)
                
        except Exception as e:
            self.logger.error(f"Tennis extraction error: {e}")
            
        self.logger.info(f"Tennis: Extracted {len(games)} games with fast method")
        return games

    async def extract_nfl_games(self, page, sport: str) -> List[Game]:
        """Fast NFL extraction using Week 8 section detection."""
        self.logger.info("🏈 Starting fast NFL extraction...")
        
        try:
            # Use JavaScript to extract NFL data directly
            nfl_data = await page.evaluate("""
                () => {
                    const games = [];
                    
                    // Find NFL section by looking for NFL logo icon
                    let nflSection = null;
                    
                    // Method 1: Look for NFL logo class
                    const nflLogos = document.querySelectorAll('.afl-NFLLeagueLogo, .afl-NFLLeagueLogo_SVG');
                    for (const logo of nflLogos) {
                        nflSection = logo.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                        if (nflSection) break;
                    }
                    
                    // Method 2: Look for NFL logo wrapper if method 1 fails
                    if (!nflSection) {
                        const logoWrappers = document.querySelectorAll('.cpm-Header_Logo, .ss-HomeSpotlightHeader_Logo');
                        for (const wrapper of logoWrappers) {
                            if (wrapper.querySelector('.afl-NFLLeagueLogo')) {
                                nflSection = wrapper.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                break;
                            }
                        }
                    }
                    
                    if (!nflSection) {
                        console.log('NFL section not found by logo detection');
                        return { games: [], spreadOdds: [], totalOdds: [], moneylineOdds: [] };
                    }
                    
                    console.log('Found NFL section by logo detection');
                    
                    // Find NFL fixtures within the Week 8 section (use AmericanFootball class)
                    const fixtures = nflSection.querySelectorAll('.cpm-ParticipantFixtureDetailsAmericanFootball');
                    
                    fixtures.forEach((fixture, index) => {
                        try {
                            const teamElements = fixture.querySelectorAll('.cpm-ParticipantFixtureDetailsAmericanFootball_Team');
                            if (teamElements.length >= 2) {
                                const team1 = teamElements[0].textContent.trim();
                                const team2 = teamElements[1].textContent.trim();
                                
                                // Get game time
                                const timeElement = fixture.querySelector('.cpm-ParticipantFixtureDetailsAmericanFootball_BookCloses');
                                const gameTime = timeElement ? timeElement.textContent.trim() : 'TBD';
                                
                                games.push({
                                    team1: team1,
                                    team2: team2,
                                    date: new Date().toISOString().split('T')[0],  // Add date field
                                    time: gameTime,
                                    index: index
                                });
                            }
                        } catch (e) {
                            console.log('Error processing NFL fixture:', e);
                        }
                    });
                    
                    // Find odds columns within NFL section (Spread, Total, Money)
                    const spreadOdds = [];
                    const totalOdds = [];
                    const moneylineOdds = [];
                    
                    // ENHANCED: Get Spread column odds with +/- values (clean format like NCAAF)
                    const spreadHeaders = Array.from(nflSection.querySelectorAll('.cpm-MarketOddsHeader')).filter(h => h.textContent.trim() === 'Spread');
                    if (spreadHeaders.length > 0) {
                        const spreadContainer = spreadHeaders[0].parentElement;
                        const spreadElements = spreadContainer.querySelectorAll('.cpm-ParticipantOdds');
                        spreadElements.forEach(odds => {
                            const handicap = odds.querySelector('.cpm-ParticipantOdds_Handicap');
                            const oddsValue = odds.querySelector('.cpm-ParticipantOdds_Odds');
                            if (handicap && oddsValue) {
                                // Clean format: "+7.0 -105" (no parentheses)
                                spreadOdds.push(`${handicap.textContent.trim()} ${oddsValue.textContent.trim()}`);
                            }
                        });
                    }
                    
                    // ENHANCED: Get Total column odds with Over/Under values (clean format like NCAAF)
                    const totalHeaders = Array.from(nflSection.querySelectorAll('.cpm-MarketOddsHeader')).filter(h => h.textContent.trim() === 'Total');
                    if (totalHeaders.length > 0) {
                        const totalContainer = totalHeaders[0].parentElement;
                        const totalElements = totalContainer.querySelectorAll('.cpm-ParticipantOdds');
                        totalElements.forEach(odds => {
                            const handicap = odds.querySelector('.cpm-ParticipantOdds_Handicap');
                            const oddsValue = odds.querySelector('.cpm-ParticipantOdds_Odds');
                            if (handicap && oddsValue) {
                                // Clean format: "O 44.0 -110" (no parentheses)
                                totalOdds.push(`${handicap.textContent.trim()} ${oddsValue.textContent.trim()}`);
                            }
                        });
                    }
                    
                    // Get Money column odds
                    const moneyHeaders = Array.from(nflSection.querySelectorAll('.cpm-MarketOddsHeader')).filter(h => h.textContent.trim() === 'Money');
                    if (moneyHeaders.length > 0) {
                        const moneyContainer = moneyHeaders[0].parentElement;
                        const moneyElements = moneyContainer.querySelectorAll('.cpm-ParticipantOdds_Odds');
                        moneyElements.forEach(odds => {
                            moneylineOdds.push(odds.textContent.trim());
                        });
                    }
                    
                    return {
                        games: games,
                        spreadOdds: spreadOdds,
                        totalOdds: totalOdds,
                        moneylineOdds: moneylineOdds
                    };
                }
            """)
            
            games = []
            
            if nfl_data and nfl_data.get('games'):
                for i, game_info in enumerate(nfl_data['games']):
                    try:
                        # ENHANCED: Map odds to games - NFL has spread, total, and moneyline (2 teams each)
                        # Extract spread +/- values and totals Over/Under values as requested
                        spread_odds = []
                        total_odds = []  
                        moneyline_odds = []
                        
                        # Each game has 2 entries (one per team) for spread and total, moneyline
                        base_index = i * 2
                        
                        # ENHANCED Spread odds with +/- values (team1, team2)
                        if base_index < len(nfl_data.get('spreadOdds', [])):
                            spread_odds.append(nfl_data['spreadOdds'][base_index])
                        if base_index + 1 < len(nfl_data.get('spreadOdds', [])):
                            spread_odds.append(nfl_data['spreadOdds'][base_index + 1])
                            
                        # ENHANCED Total odds with Over/Under values (over, under)  
                        if base_index < len(nfl_data.get('totalOdds', [])):
                            total_odds.append(nfl_data['totalOdds'][base_index])
                        if base_index + 1 < len(nfl_data.get('totalOdds', [])):
                            total_odds.append(nfl_data['totalOdds'][base_index + 1])
                            
                        # Moneyline odds (team1, team2)
                        if base_index < len(nfl_data.get('moneylineOdds', [])):
                            moneyline_odds.append(nfl_data['moneylineOdds'][base_index])
                        if base_index + 1 < len(nfl_data.get('moneylineOdds', [])):
                            moneyline_odds.append(nfl_data['moneylineOdds'][base_index + 1])
                        
                        # Create GameOdds object
                        odds = GameOdds(
                            spread=spread_odds,
                            total=total_odds,
                            moneyline=moneyline_odds
                        )
                        
                        # Create Game object
                        team1_clean = game_info['team1']
                        team2_clean = game_info['team2']
                        date_clean = game_info.get('date', datetime.now().strftime("%Y-%m-%d"))
                        time_clean = game_info['time']
                        
                        game = Game(
                            sport="NFL",
                            team1=team1_clean,
                            team2=team2_clean,
                            date=date_clean,
                            time=time_clean,
                            odds=odds,
                            game_id=self.generate_game_id(team1_clean, team2_clean, date_clean, time_clean)
                        )
                        
                        # Calculate confidence score like other methods
                        game.confidence_score = self.calculate_confidence_score(game)
                        games.append(game)
                        
                    except Exception as e:
                        self.logger.error(f"Error processing NFL game {i}: {e}")
                        continue
            
            self.logger.info(f"NFL: Extracted {len(games)} games with fast method")
            return games
            
        except Exception as e:
            self.logger.error(f"Error in NFL extraction: {e}")
            return []

    async def extract_cfl_games(self, grid, sport: str) -> List[Game]:
        """Fast CFL extraction using icon-based detection"""
        games = []

        try:
            self.logger.info("🏈 Starting fast CFL extraction...")

            # Enhanced CFL extraction with proper validation
            extraction_result = await grid.evaluate("""
                (grid) => {
                    const results = [];

                    console.log('Starting CFL extraction with section validation');

                    // Step 1: Find proper CFL section by looking for CFL-specific indicators
                    let cflSection = null;

                    // Look for CFL section by header text + American Football icon
                    const headers = document.querySelectorAll('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                    for (const header of headers) {
                        if (header.textContent.trim() === 'CFL') {
                            // Verify this is the CFL section with American Football icon
                            const headerImage = header.parentElement.querySelector('.cpm-Header_HeaderImage, .ss-HomeSpotlightHeader_HeaderImage');
                            if (headerImage) {
                                const style = headerImage.getAttribute('style') || '';
                                if (style.includes('zClass_AmericanFootball.svg')) {
                                    cflSection = header.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                    console.log('Found CFL section with proper AmericanFootball icon validation');
                                    break;
                                }
                            }
                        }
                    }

                    if (!cflSection) {
                        console.log('CFL section not found with proper validation - may be on wrong page');
                        return [];
                    }

                    // Step 2: Look for CFL fixtures within the verified CFL section
                    const fixtures = Array.from(cflSection.querySelectorAll('.cpm-ParticipantFixtureDetailsAmericanFootball'));

                    console.log(`Found ${fixtures.length} CFL fixtures in validated CFL section`);

                    // Each CFL fixture contains multiple teams within TeamNames div
                    // We need to group them into pairs for matchups
                    for (let i = 0; i < fixtures.length; i++) {
                        const fixtureElement = fixtures[i];

                        console.log(`Processing CFL fixture ${i + 1} of ${fixtures.length}`);

                        // Get all team containers within this fixture
                        const teamContainers = fixtureElement.querySelectorAll('.cpm-ParticipantFixtureDetailsAmericanFootball_TeamContainer');

                        console.log(`Found ${teamContainers.length} teams in fixture ${i + 1}`);

                        // CFL fixtures should have exactly 2 teams per matchup
                        if (teamContainers.length >= 2) {
                            // Process teams in pairs (assuming they're arranged as matchups)
                            for (let j = 0; j < teamContainers.length; j += 2) {
                                const team1Container = teamContainers[j];
                                const team2Container = teamContainers[j + 1];

                                if (!team1Container || !team2Container) {
                                    console.log(`Incomplete team pair at index ${j}, skipping`);
                                    continue;
                                }

                                // Extract team names
                                const team1NameElement = team1Container.querySelector('.cpm-ParticipantFixtureDetailsAmericanFootball_Team');
                                const team2NameElement = team2Container.querySelector('.cpm-ParticipantFixtureDetailsAmericanFootball_Team');

                                if (!team1NameElement || !team2NameElement) {
                                    console.log(`Missing team names in pair ${j/2 + 1}, skipping`);
                                    continue;
                                }

                                const team1 = team1NameElement.textContent.trim();
                                const team2 = team2NameElement.textContent.trim();

                                console.log(`Processing CFL game ${j/2 + 1}: ${team1} vs ${team2}`);

                                // Extract game time from the fixture details section
                                const timeElement = fixtureElement.querySelector('.cpm-ParticipantFixtureDetailsAmericanFootball_BookCloses');
                                const time = timeElement ? timeElement.textContent.trim() : '';

                                // Find the market group container that contains odds
                                const gameRow = fixtureElement.closest('.gl-MarketGroup');
                                if (!gameRow) {
                                    console.log(`No market group found for ${team1} vs ${team2}`);
                                    // Still create the game entry without odds
                                }

                                // Initialize odds arrays
                                let spreadOdds = [];
                                let totalOdds = [];
                                let moneylineOdds = [];

                                if (gameRow) {
                                    // Get all odds elements in the market group
                                    const allOddsElements = gameRow.querySelectorAll('.cpm-ParticipantOdds_Odds');
                                    const handicapElements = gameRow.querySelectorAll('.cpm-ParticipantOdds_Handicap');

                                    console.log(`Found ${allOddsElements.length} odds elements and ${handicapElements.length} handicap elements for CFL game`);

                                    // Extract spread and total odds (with handicaps)
                                    for (let k = 0; k < handicapElements.length && k < allOddsElements.length; k++) {
                                        const handicap = handicapElements[k] ? handicapElements[k].textContent.trim() : '';
                                        const odds = allOddsElements[k] ? allOddsElements[k].textContent.trim() : '';

                                        if (handicap && odds) {
                                            if (handicap.startsWith('O ') || handicap.startsWith('U ')) {
                                                totalOdds.push(`${handicap} ${odds}`);
                                            } else if (handicap.startsWith('+') || handicap.startsWith('-')) {
                                                spreadOdds.push(`${handicap} ${odds}`);
                                            }
                                        }
                                    }

                                    // Extract moneyline odds (odds-only, no handicaps)
                                    const moneylineElements = gameRow.querySelectorAll('.cpm-ParticipantOddsOnly50 .cpm-ParticipantOdds_Odds');
                                    for (const oddsElem of moneylineElements) {
                                        const odds = oddsElem.textContent.trim();
                                        if (odds && (odds.startsWith('+') || odds.startsWith('-'))) {
                                            moneylineOdds.push(odds);
                                        }
                                    }
                                }

                                results.push({
                                    team1: team1,
                                    team2: team2,
                                    date: new Date().toISOString().split('T')[0],
                                    time: time,
                                    spread_odds: spreadOdds,
                                    total_odds: totalOdds,
                                    moneyline_odds: moneylineOdds,
                                    fixture_id: `cfl_${i}_${j/2}`
                                });
                            }
                        } else {
                            console.log(`Fixture ${i + 1} has ${teamContainers.length} teams, not enough for CFL matchups`);
                        }
                    }

                    return results;
                }
            """)

            # Process results into Game objects
            for result in extraction_result:
                odds_obj = GameOdds(
                    spread=result['spread_odds'],
                    total=result['total_odds'],
                    moneyline=result['moneyline_odds']
                )

                game = Game(
                    sport="CFL",
                    team1=self.clean_text(result['team1']) or f"Team1_{len(games)}",
                    team2=self.clean_text(result['team2']) or f"Team2_{len(games)}",
                    date=self.clean_text(result['date']),
                    time=self.clean_text(result['time']),
                    odds=odds_obj,
                    fixture_id=result['fixture_id']
                )

                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)

        except Exception as e:
            self.logger.error(f"CFL extraction error: {e}")

        self.logger.info(f"CFL: Extracted {len(games)} games with fast method")
        return games

    async def extract_pga_games(self, page, sport: str) -> List[Game]:
        """
        Unified PGA extraction that dynamically handles both:
        - 1-column format: Win Only
        - 3-column format: Win Only, Top 5 (Inc Ties), Top 10 (Inc Ties)
        """
        games = []

        try:
            self.logger.info("🏌️ Starting unified PGA extraction...")

            extraction_result = await page.evaluate("""
                () => {
                    const results = [];

                    // Step 1: Find PGA section by looking for PGA logo
                    let pgaSection = null;
                    const headerImages = document.querySelectorAll('.cpm-Header_HeaderImage, .ss-HomeSpotlightHeader_HeaderImage');
                    for (const img of headerImages) {
                        const style = img.getAttribute('style') || '';
                        if (style.includes('zlogo_pga_official.svg') || style.includes('pga')) {
                            pgaSection = img.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                            console.log('Found PGA section by logo');
                            break;
                        }
                    }

                    // Fallback: Look for tournament/golf text
                    if (!pgaSection) {
                        const headers = document.querySelectorAll('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                        for (const header of headers) {
                            const headerText = header.textContent.toLowerCase();
                            if (headerText.includes('championship') || headerText.includes('tour') || headerText.includes('golf')) {
                                pgaSection = header.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                console.log('Found PGA section by text');
                                break;
                            }
                        }
                    }

                    if (!pgaSection) {
                        console.log('❌ PGA section not found');
                        return [];
                    }

                    // Step 2: Extract tournament name
                    const tournamentElement = pgaSection.querySelector('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                    const tournamentName = tournamentElement ? tournamentElement.textContent.trim() : 'PGA Tournament';
                    console.log(`Tournament: ${tournamentName}`);

                    // Step 3: Extract player names
                    const playerElements = Array.from(pgaSection.querySelectorAll('.cpm-ParticipantLabelGolfScore_Name'));
                    console.log(`Found ${playerElements.length} golfers`);

                    // Step 4: Dynamically detect and extract odds columns
                    const oddsColumns = {};
                    
                    // Method 1: Try multi-column format (.cpm-HScrollPlaceColumnMarketGolf with headers)
                    const marketColumns = Array.from(pgaSection.querySelectorAll('.cpm-HScrollPlaceColumnMarketGolf'));
                    if (marketColumns.length > 0) {
                        console.log(`Found ${marketColumns.length} market columns (multi-column format)`);
                        for (const column of marketColumns) {
                            const header = column.querySelector('.gl-MarketColumnHeader');
                            if (header) {
                                const headerText = header.textContent.trim();
                                const columnOdds = [];
                                const oddsElems = column.querySelectorAll('.cpm-ParticipantOdds_Odds');
                                for (const oddsElem of oddsElems) {
                                    const oddsText = oddsElem.textContent;
                                    if (oddsText) {
                                        columnOdds.push(oddsText.trim());
                                    }
                                }
                                oddsColumns[headerText] = columnOdds;
                                console.log(`Column "${headerText}": ${columnOdds.length} odds`);
                            }
                        }
                    }
                    
                    // Method 2: Single column format (just one odds container)
                    if (Object.keys(oddsColumns).length === 0) {
                        console.log('Trying single-column format');
                        const oddsContainer = pgaSection.querySelector('.cpm-HScrollPlaceColumnMarketGolf');
                        if (oddsContainer) {
                            const columnOdds = [];
                            const oddsElems = oddsContainer.querySelectorAll('.cpm-ParticipantOdds_Odds');
                            for (const oddsElem of oddsElems) {
                                const oddsText = oddsElem.textContent;
                                if (oddsText) {
                                    columnOdds.push(oddsText.trim());
                                }
                            }
                            oddsColumns['Win Only'] = columnOdds;
                            console.log(`Single column "Win Only": ${columnOdds.length} odds`);
                        }
                    }

                    // Step 5: Map players to odds
                    for (let i = 0; i < playerElements.length; i++) {
                        const playerName = playerElements[i].textContent.trim();
                        
                        if (!playerName || playerName.length < 3) continue;

                        // Extract odds for each available column
                        const winOnlyOdds = oddsColumns['Win Only'] && oddsColumns['Win Only'][i] ? [oddsColumns['Win Only'][i]] : [];
                        const top5Odds = oddsColumns['Top 5 (Inc Ties)'] && oddsColumns['Top 5 (Inc Ties)'][i] ? [oddsColumns['Top 5 (Inc Ties)'][i]] : [];
                        const top10Odds = oddsColumns['Top 10 (Inc Ties)'] && oddsColumns['Top 10 (Inc Ties)'][i] ? [oddsColumns['Top 10 (Inc Ties)'][i]] : [];

                        results.push({
                            player: playerName,
                            tournament: tournamentName,
                            date: new Date().toISOString().split('T')[0],
                            time: 'Tournament',
                            to_win: winOnlyOdds,
                            top_5: top5Odds,
                            top_10: top10Odds,
                            fixture_id: `pga_${i}`
                        });
                    }

                    console.log(`✅ Processed ${results.length} golfers with odds`);
                    return results;
                }
            """)

            # Process results into Game objects
            for result in extraction_result:
                odds_obj = GameOdds(
                    to_win=result['to_win'],
                    top_5=result['top_5'],
                    top_10=result['top_10']
                )

                game = Game(
                    sport="PGA",
                    team1=self.clean_text(result['player']) or f"Player_{len(games)}",
                    team2=f"Field ({result['tournament']})",
                    date=self.clean_text(result['date']),
                    time=self.clean_text(result['time']),
                    odds=odds_obj,
                    fixture_id=result['fixture_id']
                )

                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)

        except Exception as e:
            self.logger.error(f"PGA extraction error: {e}")

        self.logger.info(f"PGA: Extracted {len(games)} golfers")
        return games

    async def extract_ufc_games(self, page, sport: str) -> List[Game]:
        """UFC extraction using improved fixture detection with spread and total odds"""
        games = []

        try:
            self.logger.info("🥊 Starting UFC extraction...")

            # UFC extraction using direct page extraction after navigation
            extraction_result = await page.evaluate("""
                () => {
                    const results = [];
                    const seenFights = new Set(); // Track unique fights within UFC extraction

                    console.log('🥊 Starting UFC extraction...');

                    // Step 1: Find ALL UFC fixtures on the page (more comprehensive approach)
                    let allFixtures = [];

                    // Method 1: Direct UFC fixture elements (most reliable)
                    const ufcFixtures = document.querySelectorAll('div.cpm-ParticipantFixtureDetails100');
                    console.log(`🥊 Found ${ufcFixtures.length} UFC fixtures using direct selector`);

                    for (const fixture of ufcFixtures) {
                        // Skip hidden fixtures
                        if (fixture.className.includes('Hidden') || fixture.offsetParent === null) {
                            continue;
                        }
                        allFixtures.push(fixture);
                    }

                    // Method 2: Look for fixtures in UFC sections (backup)
                    if (allFixtures.length === 0) {
                        // Find UFC sections first
                        let ufcSections = [];

                        // Look for UFC logo in style background-image
                        const headerImages = document.querySelectorAll('.cpm-Header_HeaderImage, .ss-HomeSpotlightHeader_HeaderImage');
                        for (const img of headerImages) {
                            const style = img.getAttribute('style') || '';
                            if (style.includes('ufcofficialwhite.svg') || style.includes('ufc')) {
                                const section = img.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                if (section && !ufcSections.includes(section)) {
                                    ufcSections.push(section);
                                }
                            }
                        }

                        // Extract fixtures from UFC sections
                        for (const ufcSection of ufcSections) {
                            const fixtureSelectors = [
                                'div.cpm-ParticipantFixtureDetails100',
                                'div[class*="ParticipantFixture"]',
                                'div.gl-MarketFixture',
                                'div.rcl-MarketFixtureDetailsLabelBase'
                            ];

                            for (const selector of fixtureSelectors) {
                                const fixtures = Array.from(ufcSection.querySelectorAll(selector))
                                    .filter(fixture => !fixture.className.includes('Hidden') && fixture.offsetParent !== null);
                                allFixtures = allFixtures.concat(fixtures);
                            }
                        }
                    }

                    // Remove duplicates based on content
                    const uniqueFixtures = [];
                    const seenFixtureTexts = new Set();
                    for (const fixture of allFixtures) {
                        const fixtureText = fixture.textContent.trim();
                        if (!seenFixtureTexts.has(fixtureText)) {
                            seenFixtureTexts.add(fixtureText);
                            uniqueFixtures.push(fixture);
                        }
                    }

                    console.log(`🥊 Found ${uniqueFixtures.length} unique UFC fixtures`);

                    // Step 2: Extract fight date with fallback for pregame
                    const dateHeaders = document.querySelectorAll('div.cpm-MarketFixtureDateHeader');
                    let fightDate = dateHeaders.length > 0 ? dateHeaders[0].textContent.trim() : null;

                    // Fallback to today's date for pregame if no date found
                    if (!fightDate || fightDate === null) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        fightDate = today.toLocaleDateString('en-US', options);
                    }

                    // Step 3: Extract odds columns from the page (enhanced for spread and total)
                    const oddsColumns = {};
                    const marketOdds = document.querySelectorAll('div.cpm-MarketOdds');

                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent.trim();
                            // Look for moneyline, spread, and total columns
                            if (headerText === 'To Win' || headerText === 'Money' || headerText === '1' ||
                                headerText.includes('Spread') || headerText.includes('Handicap') ||
                                headerText.includes('Total') || headerText.includes('Over/Under') ||
                                headerText === 'O/U' || headerText === 'Line') {
                                const columnOdds = [];
                                const oddsElems = section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                                for (const oddsElem of oddsElems) {
                                    const oddsText = oddsElem.textContent;
                                    if (oddsText && oddsText.trim()) {
                                        columnOdds.push(oddsText.trim());
                                    }
                                }
                                oddsColumns[headerText] = columnOdds;
                            }
                        }
                    }

                    console.log(`🥊 Odds columns found: ${Object.keys(oddsColumns).join(', ')}`);

                    // Step 4: Process ALL fixtures and extract fighter information
                    for (let i = 0; i < uniqueFixtures.length; i++) {
                        const fixture = uniqueFixtures[i];

                        // Extract fighter names using multiple approaches
                        let fighter1, fighter2;

                        // Method 1: Look for specific UFC team elements
                        const teamElems = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetails100_Team');
                        if (teamElems.length >= 2) {
                            fighter1 = teamElems[0].textContent.trim();
                            fighter2 = teamElems[1].textContent.trim();
                        } else {
                            // Method 2: Look for general team containers
                            const teamContainers = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetails100_TeamContainer');
                            if (teamContainers.length >= 2) {
                                const t1 = teamContainers[0].querySelector('div.cpm-ParticipantFixtureDetails100_Team, div[class*="_Team"]');
                                const t2 = teamContainers[1].querySelector('div.cpm-ParticipantFixtureDetails100_Team, div[class*="_Team"]');
                                fighter1 = t1 ? t1.textContent.trim() : '';
                                fighter2 = t2 ? t2.textContent.trim() : '';
                            } else {
                                // Method 3: Parse fixture text for UFC fights (format: Fighter1 v Fighter2)
                                const fixtureText = fixture.textContent;
                                if (fixtureText.includes(' v ')) {
                                    const fighters = fixtureText.split(' v ');
                                    if (fighters.length >= 2) {
                                        fighter1 = fighters[0].trim();
                                        fighter2 = fighters[1].trim();
                                    }
                                } else if (fixtureText.includes(' vs ')) {
                                    const fighters = fixtureText.split(' vs ');
                                    if (fighters.length >= 2) {
                                        fighter1 = fighters[0].trim();
                                        fighter2 = fighters[1].trim();
                                    }
                                }
                            }
                        }

                        if (!fighter1 || !fighter2 || fighter1.length < 3 || fighter2.length < 3) {
                            console.log(`❌ Invalid UFC fighters: ${fighter1} vs ${fighter2}`);
                            continue;
                        }

                        // Create unique fight signature to avoid duplicates within UFC extraction
                        const fightSignature = `${fighter1.toLowerCase().trim()} vs ${fighter2.toLowerCase().trim()}`;
                        if (seenFights.has(fightSignature)) {
                            console.log(`⚠️ Skipping duplicate UFC fight: ${fightSignature}`);
                            continue;
                        }
                        seenFights.add(fightSignature);

                        console.log(`✅ UFC Fight: ${fighter1} vs ${fighter2}`);

                        // Extract fight time
                        const timeElem = fixture.querySelector('div[class*="BookCloses"], div[class*="Clock"]');
                        const fightTime = timeElem ? timeElem.textContent.trim() : "TBD";

                        // Extract odds for moneyline, spread, and total
                        const moneylineOdds = [];
                        const spreadOdds = [];
                        const totalOdds = [];

                        // FIXED: Correctly map odds to individual fights
                        // Each fight gets its own set of odds from the fixtures and columns

                        // Moneyline odds (To Win) - Map correctly with actual HTML structure
                        const moneylineKey = oddsColumns['To Win'] ? 'To Win' : (oddsColumns['Money'] ? 'Money' : null);
                        if (moneylineKey && oddsColumns[moneylineKey] && oddsColumns[moneylineKey].length > i * 2 + 1) {
                            moneylineOdds.push(oddsColumns[moneylineKey][i * 2]);     // Fighter 1 moneyline
                            moneylineOdds.push(oddsColumns[moneylineKey][i * 2 + 1]); // Fighter 2 moneyline
                        }

                        // FIXED: Extract spread odds correctly from the odds columns
                        // Find spread column odds for this specific fight (index i)
                        const spreadColumnKey = Object.keys(oddsColumns).find(key => key.includes('Spread') || key.includes('Handicap'));
                        if (spreadColumnKey && oddsColumns[spreadColumnKey] && oddsColumns[spreadColumnKey].length > i * 2 + 1) {
                            // Each fight has 2 spread odds (fighter1 spread, fighter2 spread)
                            const spread1 = oddsColumns[spreadColumnKey][i * 2] || '';
                            const spread2 = oddsColumns[spreadColumnKey][i * 2 + 1] || '';
                            if (spread1 && spread2) {
                                spreadOdds.push(spread1);
                                spreadOdds.push(spread2);
                            }
                        }

                        // FIXED: Extract total odds correctly from the odds columns
                        // Find total column odds for this specific fight (index i) 
                        const totalColumnKey = Object.keys(oddsColumns).find(key => key.includes('Total') || key.includes('O/U') || key.includes('Over'));
                        if (totalColumnKey && oddsColumns[totalColumnKey] && oddsColumns[totalColumnKey].length > i * 2 + 1) {
                            // Each fight has 2 total odds (Over, Under)
                            const total1 = oddsColumns[totalColumnKey][i * 2] || '';
                            const total2 = oddsColumns[totalColumnKey][i * 2 + 1] || '';
                            if (total1 && total2) {
                                totalOdds.push(total1);
                                totalOdds.push(total2);
                            }
                        }

                        console.log(`🥊 Moneyline for ${fighter1} vs ${fighter2}: [${moneylineOdds.join(', ')}]`);
                        console.log(`🥊 Spread for ${fighter1} vs ${fighter2}: [${spreadOdds.join(', ')}]`);
                        console.log(`🥊 Total for ${fighter1} vs ${fighter2}: [${totalOdds.join(', ')}]`);

                        // Create fight entry
                        results.push({
                            fighter1: fighter1,
                            fighter2: fighter2,
                            date: fightDate,
                            time: fightTime,
                            moneyline_odds: moneylineOdds,
                            spread_odds: spreadOdds,
                            total_odds: totalOdds,
                            fixture_id: `ufc_${results.length}`
                        });
                    }

                    console.log(`🥊 Total unique UFC fights extracted: ${results.length}`);
                    return results;
                }
            """)

            # Process results into Game objects
            for result in extraction_result:
                odds_obj = GameOdds(
                    spread=result.get('spread_odds', []),
                    total=result.get('total_odds', []),
                    moneyline=result.get('moneyline_odds', [])
                )

                game = Game(
                    sport="UFC",
                    team1=self.clean_text(result['fighter1']) or f"Fighter1_{len(games)}",
                    team2=self.clean_text(result['fighter2']) or f"Fighter2_{len(games)}",
                    date=self.clean_text(result['date']),
                    time=self.clean_text(result['time']),
                    odds=odds_obj,
                    fixture_id=result['fixture_id']
                )

                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)

        except Exception as e:
            self.logger.error(f"UFC extraction error: {e}")

        self.logger.info(f"UFC: Extracted {len(games)} fights with enhanced odds")
        return games

    async def extract_soccer_games(self, page, sport: str) -> List[Game]:
        """Soccer extraction using section-based scoping to avoid conflicts with UCL/EPL/MLS"""
        games = []

        try:
            self.logger.info("⚽ Starting Soccer extraction...")

            # Soccer extraction using section-based detection to avoid UCL/EPL/MLS conflicts
            extraction_result = await page.evaluate("""
                () => {
                    const results = [];
                    const seenMatches = new Set();

                    console.log('⚽ Starting Soccer extraction...');

                    // Step 1: Find generic Soccer section (excluding UCL, EPL, MLS, and eSoccer)
                    let soccerSection = null;
                    
                    // Method 1: Look for "Featured Matches" header (common for generic soccer)
                    const headers = document.querySelectorAll('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                    for (const header of headers) {
                        const headerText = header.textContent.trim();
                        // Match generic soccer headers, excluding specific leagues
                        if ((headerText === 'Featured Matches' || headerText === 'Soccer' || headerText === 'Football') &&
                            !headerText.includes('UEFA') && !headerText.includes('Champions League') &&
                            !headerText.includes('Premier League') && !headerText.includes('EPL') &&
                            !headerText.includes('MLS') && !headerText.includes('Major League Soccer')) {
                            soccerSection = header.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                            console.log(`Found generic Soccer section by header: "${headerText}"`);
                            break;
                        }
                    }
                    
                    // Method 2: Look for generic soccer icon (zClass_Soccer.svg) without specific league identifiers
                    if (!soccerSection) {
                        const headerImages = document.querySelectorAll('.cpm-Header_HeaderImage, .ss-HomeSpotlightHeader_HeaderImage');
                        for (const img of headerImages) {
                            const style = img.getAttribute('style') || '';
                            // Must have generic soccer icon, but NOT UCL, EPL, MLS, or eSports icons
                            if (style.includes('zClass_Soccer.svg') &&
                                !style.includes('zlogo_UCL_Official.svg') &&
                                !style.includes('zlogo_MLS_Official.svg') &&
                                !style.includes('zClass_ESports.svg')) {
                                
                                const section = img.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                if (section) {
                                    // Double-check the section title doesn't contain specific league names
                                    const sectionTitle = section.querySelector('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                                    const titleText = sectionTitle ? sectionTitle.textContent.trim() : '';
                                    
                                    if (!titleText.includes('UEFA') && !titleText.includes('Champions League') &&
                                        !titleText.includes('Premier League') && !titleText.includes('EPL') &&
                                        !titleText.includes('MLS') && !titleText.includes('eSoccer') &&
                                        !titleText.includes('e-soccer')) {
                                        soccerSection = section;
                                        console.log(`Found generic Soccer section by icon, title: "${titleText}"`);
                                        break;
                                    }
                                }
                            }
                        }
                    }

                    if (!soccerSection) {
                        console.log('Generic Soccer section not found (this is OK if UCL/EPL/MLS are being used)');
                        return [];
                    }

                    // Step 2: Extract fixtures ONLY from the generic soccer section
                    const allFixtures = Array.from(soccerSection.querySelectorAll('div.cpm-ParticipantFixtureDetailsSoccer'))
                        .filter(fixture => !fixture.className.includes('Hidden'));

                    console.log(`Found ${allFixtures.length} soccer fixtures in generic soccer section`);

                    // Step 3: Extract odds columns from the soccer section
                    const oddsColumns = {};
                    const marketOdds = Array.from(soccerSection.querySelectorAll('div.cpm-MarketOdds'));
                    
                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent.trim();
                            if (['1', 'X', '2', 'Money', 'Spread', 'Total'].includes(headerText)) {
                                const columnOdds = [];
                                const oddsElems = section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                                for (const oddsElem of oddsElems) {
                                    const oddsText = oddsElem.textContent;
                                    if (oddsText) {
                                        columnOdds.push(oddsText.trim());
                                    }
                                }
                                oddsColumns[headerText] = columnOdds;
                            }
                        }
                    }

                    // Step 4: Extract game date
                    const dateHeader = soccerSection.querySelector('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateHeader ? dateHeader.textContent.trim() : null;
                    if (!gameDate) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }

                    // Step 5: Extract odds columns from the scoped section
                    const oddsColumns = {};
                    const marketOdds = soccerSection.querySelectorAll('div.cpm-MarketOdds');

                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent.trim();
                            if (headerText === '1' || headerText === 'X' || headerText === '2' || 
                                headerText === 'Money' || headerText === '1X2' || headerText === 'Match Winner') {
                                const columnOdds = [];
                                const oddsElems = section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                                for (const oddsElem of oddsElems) {
                                    const oddsText = oddsElem.textContent;
                                    if (oddsText && oddsText.trim()) {
                                        columnOdds.push(oddsText.trim());
                                    }
                                }
                                oddsColumns[headerText] = columnOdds;
                            }
                        }
                    }

                    console.log(`📊 Soccer Odds columns found: ${Object.keys(oddsColumns).join(', ')}`);

                    // Step 6: Process fixtures from the scoped soccer section
                    for (let i = 0; i < allFixtures.length; i++) {
                        const fixture = allFixtures[i];

                        // Extract team names using soccer-specific selectors
                        let team1, team2;

                        // Method 1: Direct soccer team elements
                        const teamElems = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsSoccer_Team');
                        if (teamElems.length >= 2) {
                            team1 = teamElems[0].textContent.trim();
                            team2 = teamElems[1].textContent.trim();
                        } else {
                            // Method 2: Parse fixture text for soccer matches
                            const fixtureText = fixture.textContent;
                            if (fixtureText.includes(' v ')) {
                                const teams = fixtureText.split(' v ');
                                if (teams.length >= 2) {
                                    team1 = teams[0].trim();
                                    team2 = teams[1].trim();
                                }
                            }
                        }

                        if (!team1 || !team2 || team1.length < 3 || team2.length < 3) {
                            console.log(`❌ Invalid soccer teams: ${team1} vs ${team2}`);
                            continue;
                        }

                        // Additional eSoccer filtering (double-check)
                        const combinedText = `${team1} ${team2}`.toLowerCase();
                        if (combinedText.includes('esoccer') || combinedText.includes('e-soccer') ||
                            combinedText.includes('virtual') || combinedText.includes('simulated')) {
                            console.log(`⚠️ Skipping esoccer match: ${team1} vs ${team2}`);
                            continue;
                        }

                        // Check for eSoccer nickname pattern
                        const team1HasNickname = team1.includes('(') && team1.includes(')') &&
                            !team1.toLowerCase().includes('youth') && !team1.toLowerCase().includes('u21');
                        const team2HasNickname = team2.includes('(') && team2.includes(')') &&
                            !team2.toLowerCase().includes('youth') && !team2.toLowerCase().includes('u21');

                        if (team1HasNickname || team2HasNickname) {
                            console.log(`⚠️ Skipping potential esoccer match with nicknames: ${team1} vs ${team2}`);
                            continue;
                        }

                        // Create unique match signature to avoid duplicates
                        const matchSignature = `${team1.toLowerCase().trim()} vs ${team2.toLowerCase().trim()}`;
                        if (seenMatches.has(matchSignature)) {
                            console.log(`⚠️ Skipping duplicate soccer match: ${matchSignature}`);
                            continue;
                        }
                        seenMatches.add(matchSignature);

                        console.log(`✅ Soccer Match: ${team1} vs ${team2}`);

                        // Extract match time
                        const timeElem = fixture.querySelector('div.cpm-ParticipantFixtureDetailsSoccer_BookCloses');
                        const matchTime = timeElem ? timeElem.textContent.trim() : "TBD";

                        // Map odds to teams (1X2 format: 1=home, X=draw, 2=away)
                        const moneylineOdds = [];

                        // Use '1', 'X', '2' columns for soccer 1X2 betting
                        if (oddsColumns['1'] && oddsColumns['1'].length > i) {
                            moneylineOdds.push(oddsColumns['1'][i]);  // Home team odds
                        }

                        if (oddsColumns['X'] && oddsColumns['X'].length > i) {
                            moneylineOdds.push(oddsColumns['X'][i]);  // Draw odds
                        }

                        if (oddsColumns['2'] && oddsColumns['2'].length > i) {
                            moneylineOdds.push(oddsColumns['2'][i]);  // Away team odds
                        }

                        // Fallback to other formats if 1X2 not available
                        if (moneylineOdds.length === 0) {
                            const oddsKey = oddsColumns['Money'] ? 'Money' : (oddsColumns['1X2'] ? '1X2' : 'Match Winner');
                            if (oddsColumns[oddsKey] && oddsColumns[oddsKey].length > i * 3 + 2) {
                                moneylineOdds.push(oddsColumns[oddsKey][i * 3]);     // Home team odds
                                moneylineOdds.push(oddsColumns[oddsKey][i * 3 + 1]); // Draw odds
                                moneylineOdds.push(oddsColumns[oddsKey][i * 3 + 2]); // Away team odds
                            }
                        }

                        console.log(`⚽ Odds for ${team1} vs ${team2}: [${moneylineOdds.join(', ')}]`);

                        // Create match entry
                        results.push({
                            team1: team1,
                            team2: team2,
                            date: matchDate,
                            time: matchTime,
                            moneyline_odds: moneylineOdds,
                            fixture_id: `soccer_${results.length}`
                        });
                    }

                    console.log(`⚽ Total unique REAL soccer matches extracted: ${results.length}`);
                    return results;
                }
            """)

            # Process results into Game objects
            for result in extraction_result:
                odds_obj = GameOdds(
                    spread=[],
                    total=[],
                    moneyline=result['moneyline_odds']
                )

                team1_clean = self.clean_text(result['team1']) or f"Team1_{len(games)}"
                team2_clean = self.clean_text(result['team2']) or f"Team2_{len(games)}"
                date_clean = self.clean_text(result['date'])
                time_clean = self.clean_text(result['time'])

                game = Game(
                    sport="Soccer",
                    team1=team1_clean,
                    team2=team2_clean,
                    date=date_clean,
                    time=time_clean,
                    odds=odds_obj,
                    fixture_id=result['fixture_id'],
                    game_id=self.generate_game_id(team1_clean, team2_clean, date_clean, time_clean)
                )

                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)

        except Exception as e:
            self.logger.error(f"Soccer extraction error: {e}")

        self.logger.info(f"Soccer: Extracted {len(games)} REAL soccer matches (eSoccer filtered out)")
        return games

    async def extract_generic_games(self, grid, sport: str) -> List[Game]:
        """Generic extraction for unsupported sports"""
        self.logger.info(f"Using generic extraction for {sport}")
        return []

    # ----------------------------- Deduplication & Validation ----------------------------- #

    def deduplicate_games(self, games: List[Game]) -> List[Game]:
        """Remove duplicate games with confidence-based selection"""
        seen_games = {}
        
        for game in games:
            # Create game signature
            signature = (
                game.sport.lower(),
                game.team1.lower().strip(),
                game.team2.lower().strip(),
                game.date or "",
                game.time or ""
            )
            
            if signature in seen_games:
                # Keep the game with higher confidence
                if game.confidence_score > seen_games[signature].confidence_score:
                    seen_games[signature] = game
            else:
                seen_games[signature] = game
                
        unique_games = list(seen_games.values())
        self.logger.info(f"Deduplication: {len(games)} -> {len(unique_games)} games")
        return unique_games

    def validate_game_data(self, game: Game) -> bool:
        """Comprehensive game data validation"""
        if not game.team1 or not game.team2:
            return False
            
        if game.team1.lower() == game.team2.lower():
            self.logger.debug(f"Validation failed: Same team names - {game.team1} vs {game.team2}")
            return False
            
        if not game.odds.has_valid_odds():
            return False
            
        if game.confidence_score < 20.0:  # Lowered threshold to allow more matches
            return False
            
        return True

    # ----------------------------- Pregame History Tracking ----------------------------- #

    async def handle_pregame_history(self, current_result: Dict[str, Any]):
        """Track games that were removed from the website and save to pregame_history.json"""
        try:
            history_file = self.outputs_dir / "pregame_history.json"
            current_file = self.outputs_dir / "bet365_current_pregame.json"
            
            # Load previous pregame data if it exists
            previous_games = {}
            if current_file.exists():
                try:
                    with open(current_file, 'r', encoding='utf-8') as f:
                        previous_data = json.load(f)
                        if 'sports_data' in previous_data:
                            for sport, sport_data in previous_data['sports_data'].items():
                                for game_dict in sport_data.get('games', []):
                                    if 'game_id' in game_dict and game_dict['game_id']:
                                        previous_games[game_dict['game_id']] = game_dict
                except Exception as e:
                    self.logger.warning(f"Could not load previous pregame data: {e}")
            
            # Get current games
            current_games = {}
            if 'sports_data' in current_result:
                for sport, sport_data in current_result['sports_data'].items():
                    for game_dict in sport_data.get('games', []):
                        if 'game_id' in game_dict and game_dict['game_id']:
                            current_games[game_dict['game_id']] = game_dict
            
            # Find removed games (games that were in previous but not in current)
            removed_games = []
            for game_id, game_data in previous_games.items():
                if game_id not in current_games:
                    # Add removal timestamp
                    game_data_copy = game_data.copy()
                    game_data_copy['removed_timestamp'] = datetime.now().isoformat()
                    removed_games.append(game_data_copy)
            
            if removed_games:
                self.logger.info(f"📉 Found {len(removed_games)} games removed from website")
                
                # Load existing history
                existing_history = []
                if history_file.exists():
                    try:
                        with open(history_file, 'r', encoding='utf-8') as f:
                            history_data = json.load(f)
                            existing_history = history_data.get('games', [])
                    except Exception as e:
                        self.logger.warning(f"Could not load existing history: {e}")
                
                # Add new removed games to history
                existing_history.extend(removed_games)
                
                # Keep only last 1000 historical games to prevent file from growing too large
                if len(existing_history) > 1000:
                    existing_history = existing_history[-1000:]
                
                # Save updated history
                history_data = {
                    "timestamp": datetime.now().isoformat(),
                    "total_historical_games": len(existing_history),
                    "games": existing_history
                }
                
                with open(history_file, 'w', encoding='utf-8') as f:
                    json.dump(history_data, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"💾 Saved {len(removed_games)} newly removed games to pregame_history.json")
                
                # Log sample of removed games
                for i, game in enumerate(removed_games[:3]):  # Show first 3
                    self.logger.info(f"   Removed: {game.get('team1', 'N/A')} vs {game.get('team2', 'N/A')} ({game.get('sport', 'N/A')})")
                if len(removed_games) > 3:
                    self.logger.info(f"   ... and {len(removed_games) - 3} more")
            else:
                self.logger.info("📊 No games were removed since last run")
                
        except Exception as e:
            self.logger.error(f"Error handling pregame history: {e}")

    # ----------------------------- Main Orchestration ----------------------------- #

    async def scrape_all_sports(self) -> Dict[str, Any]:
        """Enhanced orchestration with improved error handling"""
        start_time = datetime.now()
        
        result = {
            "extraction_info": {
                "timestamp": start_time.isoformat(),
                "session_id": self.session_id,
                "source": "bet365.ca",
                "version": "enhanced-intelligent-v1.0",
                "headless": self.headless,
            },
            "sports_data": {},
            "extraction_summary": {}
        }

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-extensions',
                    '--no-first-run',
                    '--disable-default-apps'
                ]
            )
            
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            )
            
            page = await context.new_page()
            
            # Apply fast page setup like test scraper
            await page.set_viewport_size({"width": 1920, "height": 1080})
            page.set_default_navigation_timeout(self.timeout)
            page.set_default_timeout(self.timeout)
            
            try:
                self.logger.info("Navigating to bet365.ca...")
                await page.goto("https://bet365.ca/#/HO/", timeout=self.timeout, wait_until="load")  # Direct HO URL like fast test
                
                # Fast selector waiting like test scraper
                await page.wait_for_selector('.ss-HomepageSpotlight', timeout=self.timeout)
                
                # Detect available sport tabs
                sport_tabs = await self.detect_sport_tabs(page)
                
                if not sport_tabs:
                    self.logger.warning("No supported sport tabs detected")
                    return result
                    
                self.logger.info(f"Processing {len(sport_tabs)} sports: {[s for s, _, _ in sport_tabs]}")
                
                all_games = []
                
                # Process each sport sequentially  
                for sport, tab_label, tab_element in sport_tabs:
                    self.logger.info(f"\n{'='*60}")
                    self.logger.info(f"PROCESSING {sport.upper()} (Tab: '{tab_label}')")
                    self.logger.info(f"{'='*60}")
                    
                    try:
                        # Navigate to sport
                        if not await self.navigate_to_sport(page, tab_element, sport):
                            self.logger.warning(f"Failed to navigate to {sport}")
                            continue
                            
                        # Extract games
                        sport_games = await self.extract_sport_games(page, sport)
                        
                        if sport_games:
                            # Validate games
                            valid_games = [game for game in sport_games if self.validate_game_data(game)]
                            all_games.extend(valid_games)
                            
                            result["sports_data"][sport] = {
                                "total_games": len(valid_games),
                                "games": [game.to_dict() for game in valid_games]
                            }
                            
                            self.logger.info(f"{sport}: {len(valid_games)} valid games extracted")
                            
                            # Log sample games
                            for game in valid_games[:3]:
                                odds_summary = ", ".join(f"{k}({len(v)})" for k, v in game.odds.to_dict().items() if v)
                                self.logger.info(f"  Sample: {game.team1} vs {game.team2} | {odds_summary}")
                        else:
                            self.logger.warning(f"{sport}: No games extracted")
                            
                    except Exception as e:
                        self.logger.error(f"Error processing {sport}: {e}")
                        continue
                
                # Deduplicate all games
                all_games = self.deduplicate_games(all_games)
                
                # Generate summary
                end_time = datetime.now()
                result["extraction_summary"] = {
                    "total_games": len(all_games),
                    "sports_processed": len(sport_tabs),
                    "extraction_duration": str(end_time - start_time),
                    "average_confidence": sum(game.confidence_score for game in all_games) / len(all_games) if all_games else 0,
                    "games_by_sport": {sport: len(data["games"]) for sport, data in result["sports_data"].items()}
                }
                
            except Exception as e:
                self.logger.error(f"Critical extraction error: {e}")
                
            finally:
                await browser.close()

        # Handle pregame history tracking
        await self.handle_pregame_history(result)

        # Save results to single file (not timestamped)
        output_file = self.outputs_dir / "bet365_current_pregame.json"
        output_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        
        # Log final summary
        self.logger.info(f"\n{'='*80}")
        self.logger.info(f"ENHANCED INTELLIGENT SCRAPER - EXTRACTION COMPLETE")
        self.logger.info(f"{'='*80}")
        self.logger.info(f"Results saved to: {output_file}")
        self.logger.info(f"Session ID: {self.session_id}")
        
        # Safe logging with fallback for failed extractions
        if result['extraction_summary'] and 'total_games' in result['extraction_summary']:
            self.logger.info(f"Total games: {result['extraction_summary']['total_games']}")
            for sport, count in result["extraction_summary"]["games_by_sport"].items():
                self.logger.info(f"{sport}: {count} games")
        else:
            self.logger.warning("Extraction failed or incomplete - no games extracted")
            
        return result

    async def extract_single_sport_realtime(self, sport: str) -> Dict[str, Any]:
        """FAST real-time extraction using existing browser session with minimal overhead"""
        try:
            # Check if browser session is available
            if not hasattr(self, 'browser') or not self.browser or not hasattr(self, 'page') or not self.page:
                self.logger.error(f"❌ Browser session not initialized for real-time extraction of {sport}")
                return {"games": [], "error": "Browser session not initialized"}
            
            # OPTIMIZATION: Skip homepage navigation - use current page state
            # Only navigate to homepage if we detect we're not on bet365
            current_url = self.page.url  # Fixed: url is a property, not an async method
            if not current_url or "bet365" not in current_url:
                try:
                    await self.page.goto("https://www.bet365.ca/", wait_until="domcontentloaded", timeout=8000)
                    await self.page.wait_for_timeout(200)  # Minimal wait
                except Exception as nav_error:
                    self.logger.warning(f"⚠️ Navigation issue for {sport}: {nav_error}")
            
            # OPTIMIZATION: Fast sport tab detection with caching
            tab = await self.find_sport_tab_fast(self.page, sport)
            if not tab:
                return {"games": [], "error": f"Sport tab not found for {sport}"}
                
            await tab.click()
            await self.page.wait_for_timeout(400)  # Minimal wait for real-time
            
            # OPTIMIZATION: Skip scrolling for real-time - use visible content only
            # await self.progressive_scroll_load(self.page, sport)  # Commented out for speed
            
            # OPTIMIZATION: Use faster extraction method for real-time
            games = await self.extract_sport_games_fast(self.page, sport)
            
            # Convert Game objects to dicts (optimized)
            games_dicts = []
            for game in games:
                if hasattr(game, 'to_dict'):
                    games_dicts.append(game.to_dict())
                else:
                    # Quick conversion for real-time
                    odds_obj = getattr(game, 'odds', None)
                    odds_dict = odds_obj.to_dict() if (odds_obj and hasattr(odds_obj, 'to_dict')) else {}
                    games_dicts.append({
                        "sport": sport,
                        "team1": getattr(game, 'team1', ''),
                        "team2": getattr(game, 'team2', ''),
                        "player1_team1": getattr(game, 'team1', ''),  # Backward compatibility
                        "player2_team2": getattr(game, 'team2', ''),  # Backward compatibility
                        "date": getattr(game, 'date', ''),
                        "time": getattr(game, 'time', ''),
                        "fixture_id": getattr(game, 'fixture_id', ''),
                        "odds": odds_dict
                    })
            
            return {
                "games": games_dicts,
                "timestamp": datetime.now().isoformat(),
                "sport": sport
            }
            
        except Exception as e:
            self.logger.error(f"Real-time extraction error for {sport}: {e}")
            return {"games": [], "error": str(e)}

    async def quick_extract_sport(self, sport: str, page) -> List[Dict[str, Any]]:
        """Quick extraction method for real-time monitoring with existing page"""
        try:
            # Navigate to sport tab
            tab = await self.find_sport_tab(page, sport)
            if not tab:
                return []
                
            await tab.click()
            await page.wait_for_timeout(800)  # Quick wait
            
            # Extract games using the main method
            games = await self.extract_sport_games(page, sport)
            
            # Convert Game objects to dicts
            games_dicts = []
            for game in games:
                if hasattr(game, 'to_dict'):
                    games_dicts.append(game.to_dict())
                else:
                    # Convert manually if needed
                    odds_obj = getattr(game, 'odds', None) 
                    odds_dict = odds_obj.to_dict() if (odds_obj and hasattr(odds_obj, 'to_dict')) else {}
                    games_dicts.append({
                        "sport": sport,
                        "player1_team1": getattr(game, 'player1_team1', ''),
                        "player2_team2": getattr(game, 'player2_team2', ''),
                        "time": getattr(game, 'time', ''),
                        "odds": odds_dict
                    })
                    
            return games_dicts
            
        except Exception as e:
            self.logger.error(f"Quick extract error for {sport}: {e}")
            return []

    async def initialize(self):
        """Initialize the scraper for real-time monitoring"""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )
            self.page = await self.browser.new_page()
            self.logger.info("✅ Enhanced scraper initialized successfully")
        except Exception as e:
            self.logger.error(f"❌ Failed to initialize scraper: {e}")
            raise

    async def navigate_to_bet365(self):
        """Navigate to bet365.ca for monitoring and login if credentials provided"""
        try:
            await self.page.goto("https://www.bet365.ca/", wait_until="networkidle", timeout=30000)
            self.logger.info("🌐 Navigated to bet365.ca")

            # Check if login is needed and credentials are available
            if self.email and self.password:
                await self.login_to_bet365()
            else:
                self.logger.info("No login credentials provided, proceeding without login")
        except Exception as e:
            self.logger.error(f"❌ Failed to navigate to bet365: {e}")
            raise

    async def login_to_bet365(self):
        """Login to bet365 using provided credentials"""
        try:
            self.logger.info("🔐 Attempting to login to bet365...")

            # Wait for page to load completely
            await self.page.wait_for_timeout(2000)

            # Look for login button/link - bet365 has multiple ways to trigger login
            login_selectors = [
                'a[href*="login"]',
                'button[class*="login"]',
                'div[class*="login"]',
                'span:has-text("Log In")',
                'a:has-text("Log In")',
                'button:has-text("Log In")',
                '[data-testid*="login"]',
                '.hm-Login',
                '.hm-LoginButton'
            ]

            login_button = None
            for selector in login_selectors:
                try:
                    login_button = await self.page.query_selector(selector)
                    if login_button and await login_button.is_visible():
                        self.logger.info(f"Found login button with selector: {selector}")
                        break
                except:
                    continue

            if not login_button:
                # Try to find login in the header menu
                try:
                    # Look for the header menu that might contain login
                    header_menu = await self.page.query_selector('.hm-MainHeaderRHSLoggedOut')
                    if header_menu:
                        login_link = await header_menu.query_selector('a[href*="login"]')
                        if login_link:
                            login_button = login_link
                            self.logger.info("Found login link in header menu")
                except:
                    pass

            if not login_button:
                self.logger.warning("Could not find login button, checking if already logged in...")
                # Check if we're already logged in by looking for user menu or balance
                try:
                    user_menu = await self.page.query_selector('.hm-MainHeaderRHSLoggedIn')
                    if user_menu:
                        self.logger.info("✅ Already logged in to bet365")
                        return
                except:
                    pass

                self.logger.warning("Could not find login button and not logged in, proceeding without login")
                return

            # Click the login button
            await login_button.click()
            await self.page.wait_for_timeout(2000)

            # Wait for login form to appear
            login_form_selectors = [
                'form[class*="login"]',
                '.lms-LoginForm',
                '.lms-StandardLogin',
                'input[type="email"]',
                'input[name*="email"]',
                'input[placeholder*="email"]'
            ]

            login_form = None
            for selector in login_form_selectors:
                try:
                    login_form = await self.page.query_selector(selector)
                    if login_form:
                        self.logger.info(f"Found login form with selector: {selector}")
                        break
                except:
                    continue

            if not login_form:
                self.logger.warning("Login form not found, checking if modal appeared...")
                # Sometimes login opens in a modal
                try:
                    modal = await self.page.query_selector('.lms-ModalContent')
                    if modal:
                        login_form = modal
                        self.logger.info("Found login modal")
                except:
                    pass

            if not login_form:
                self.logger.warning("Could not find login form, proceeding without login")
                return

            # Fill in email
            email_selectors = [
                'input[type="email"]',
                'input[name*="email"]',
                'input[name*="Email"]',
                'input[placeholder*="email"]',
                'input[placeholder*="Email"]',
                '#txtUsername'
            ]

            email_input = None
            for selector in email_selectors:
                try:
                    email_input = await self.page.query_selector(selector)
                    if email_input and await email_input.is_visible():
                        break
                except:
                    continue

            if email_input:
                await email_input.fill(self.email)
                self.logger.info("Filled email field")
            else:
                self.logger.warning("Could not find email input field")

            # Fill in password
            password_selectors = [
                'input[type="password"]',
                'input[name*="password"]',
                'input[name*="Password"]',
                'input[placeholder*="password"]',
                'input[placeholder*="Password"]',
                '#txtPassword'
            ]

            password_input = None
            for selector in password_selectors:
                try:
                    password_input = await self.page.query_selector(selector)
                    if password_input and await password_input.is_visible():
                        break
                except:
                    continue

            if password_input:
                await password_input.fill(self.password)
                self.logger.info("Filled password field")
            else:
                self.logger.warning("Could not find password input field")

            # Click login button
            login_submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'button:has-text("Sign In")',
                '.lms-LoginButton',
                '#btnLogin'
            ]

            login_submit = None
            for selector in login_submit_selectors:
                try:
                    login_submit = await self.page.query_selector(selector)
                    if login_submit and await login_submit.is_visible():
                        break
                except:
                    continue

            if login_submit:
                await login_submit.click()
                self.logger.info("Clicked login submit button")

                # Wait for login to complete
                await self.page.wait_for_timeout(5000)

                # Check if login was successful
                try:
                    # Look for user menu or balance to confirm login
                    user_menu = await self.page.query_selector('.hm-MainHeaderRHSLoggedIn')
                    if user_menu:
                        self.logger.info("✅ Successfully logged in to bet365")
                        return
                    else:
                        # Check for error messages
                        error_selectors = [
                            '.lms-LoginError',
                            '.error-message',
                            '[class*="error"]',
                            ':has-text("incorrect")',
                            ':has-text("invalid")'
                        ]
                        for selector in error_selectors:
                            try:
                                error = await self.page.query_selector(selector)
                                if error:
                                    error_text = await error.inner_text()
                                    self.logger.warning(f"Login error detected: {error_text}")
                                    break
                            except:
                                continue
                except Exception as check_error:
                    self.logger.warning(f"Could not verify login status: {check_error}")
            else:
                self.logger.warning("Could not find login submit button")

        except Exception as e:
            self.logger.error(f"❌ Login failed: {e}")
            # Don't raise exception, just log and continue without login

    async def extract_games_for_sport(self, sport: str, tab_element) -> List[Game]:
        """Extract games for a specific sport using tab element"""
        try:
            await tab_element.click()
            await self.page.wait_for_timeout(1500)
            
            # Use existing extraction logic
            games = await self.extract_sport_games(self.page, sport)
            return games
            
        except Exception as e:
            self.logger.error(f"Failed to extract {sport} games: {e}")
            return []

    async def extract_epl_games(self, page, sport: str) -> List[Game]:
        """EPL extraction using Premier League section detection with proper odds extraction"""
        games = []

        try:
            self.logger.info("⚽ Starting EPL extraction...")

            extraction_result = await page.evaluate("""
                () => {
                    const results = [];

                    // Step 1: Find EPL section by Premier League header
                    let eplSection = null;
                    const headers = document.querySelectorAll('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                    for (const header of headers) {
                        if (header.textContent.trim() === 'Premier League') {
                            eplSection = header.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                            console.log('Found EPL section by Premier League title');
                            break;
                        }
                    }

                    if (!eplSection) {
                        console.log('EPL section not found');
                        return [];
                    }

                    // Step 2: Extract fixtures from EPL section
                    const fixtures = Array.from(eplSection.querySelectorAll('div.cpm-ParticipantFixtureDetailsSoccer'))
                        .filter(fixture => !fixture.className.includes('Hidden'));

                    console.log(`Found ${fixtures.length} EPL fixtures`);

                    // Step 3: Extract odds columns (1, X, 2 format for soccer)
                    const oddsColumns = {};
                    const marketOdds = Array.from(eplSection.querySelectorAll('div.cpm-MarketOdds'));
                    
                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent.trim();
                            if (['1', 'X', '2'].includes(headerText)) {
                                const columnOdds = [];
                                const oddsElems = section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                                for (const oddsElem of oddsElems) {
                                    const oddsText = oddsElem.textContent;
                                    if (oddsText) {
                                        columnOdds.push(oddsText.trim());
                                    }
                                }
                                oddsColumns[headerText] = columnOdds;
                            }
                        }
                    }

                    // Step 4: Extract game date
                    const dateHeader = eplSection.querySelector('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateHeader ? dateHeader.textContent.trim() : null;
                    if (!gameDate) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }

                    // Step 5: Process fixtures
                    for (let i = 0; i < fixtures.length; i++) {
                        const fixture = fixtures[i];

                        // Extract team names
                        const teamElements = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsSoccer_Team');
                        if (teamElements.length < 2) continue;

                        const team1 = teamElements[0].textContent.trim();
                        const team2 = teamElements[1].textContent.trim();

                        // Extract time
                        const timeElement = fixture.querySelector('div.cpm-ParticipantFixtureDetailsSoccer_BookCloses');
                        const gameTime = timeElement ? timeElement.textContent.trim() : "TBD";

                        // Map odds for soccer (1=home win, X=draw, 2=away win)
                        const moneylineOdds = [];
                        
                        // Team 1 (Home) odds from column "1"
                        if (oddsColumns["1"] && oddsColumns["1"].length > i) {
                            moneylineOdds.push(oddsColumns["1"][i]);
                        }
                        
                        // Draw odds from column "X" (we'll include this as additional info)
                        let drawOdds = null;
                        if (oddsColumns["X"] && oddsColumns["X"].length > i) {
                            drawOdds = oddsColumns["X"][i];
                        }
                        
                        // Team 2 (Away) odds from column "2"
                        if (oddsColumns["2"] && oddsColumns["2"].length > i) {
                            moneylineOdds.push(oddsColumns["2"][i]);
                        }

                        results.push({
                            team1: team1,
                            team2: team2,
                            date: gameDate,
                            time: gameTime,
                            moneyline: moneylineOdds,
                            draw_odds: drawOdds, // EPL specific - draw option
                            fixture_id: `epl_${i}`
                        });
                    }

                    return results;
                }
            """)

            # Process results into Game objects
            for result in extraction_result:
                # For EPL, we include draw odds in the total pool
                moneyline_with_draw = result['moneyline'][:]
                if result.get('draw_odds'):
                    moneyline_with_draw.append(result['draw_odds'])

                odds_obj = GameOdds(
                    spread=[],  # EPL doesn't typically use spread betting
                    total=[],   # Total goals betting would need separate extraction
                    moneyline=moneyline_with_draw
                )

                game = Game(
                    sport="EPL",
                    team1=self.clean_text(result['team1']) or f"Team1_{len(games)}",
                    team2=self.clean_text(result['team2']) or f"Team2_{len(games)}",
                    date=self.clean_text(result['date']),
                    time=self.clean_text(result['time']),
                    odds=odds_obj,
                    fixture_id=result['fixture_id']
                )

                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)

        except Exception as e:
            self.logger.error(f"EPL extraction error: {e}")

        self.logger.info(f"EPL: Extracted {len(games)} games")
        return games

    async def extract_ucl_games(self, page, sport: str) -> List[Game]:
        """UCL extraction using UEFA Champions League section detection with proper odds extraction"""
        games = []

        try:
            self.logger.info("⚽ Starting UCL extraction...")

            extraction_result = await page.evaluate("""
                () => {
                    const results = [];

                    // Step 1: Find UCL section by UEFA Champions League header or logo
                    let uclSection = null;
                    
                    // Method 1: Look for UCL logo
                    const headerImages = document.querySelectorAll('.cpm-Header_HeaderImage, .ss-HomeSpotlightHeader_HeaderImage');
                    for (const img of headerImages) {
                        const style = img.getAttribute('style') || '';
                        if (style.includes('zlogo_UCL_Official.svg')) {
                            uclSection = img.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                            console.log('Found UCL section by UCL logo');
                            break;
                        }
                    }
                    
                    // Method 2: Look for "UEFA Champions League" text
                    if (!uclSection) {
                        const headers = document.querySelectorAll('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                        for (const header of headers) {
                            if (header.textContent.includes('UEFA Champions League') || header.textContent.includes('Champions League')) {
                                uclSection = header.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                console.log('Found UCL section by title');
                                break;
                            }
                        }
                    }

                    if (!uclSection) {
                        console.log('UCL section not found');
                        return [];
                    }

                    // Step 2: Extract fixtures from UCL section
                    const fixtures = Array.from(uclSection.querySelectorAll('div.cpm-ParticipantFixtureDetailsSoccer'))
                        .filter(fixture => !fixture.className.includes('Hidden'));

                    console.log(`Found ${fixtures.length} UCL fixtures`);

                    // Step 3: Extract odds columns (1, X, 2 format for soccer)
                    const oddsColumns = {};
                    const marketOdds = Array.from(uclSection.querySelectorAll('div.cpm-MarketOdds'));
                    
                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent.trim();
                            if (['1', 'X', '2'].includes(headerText)) {
                                const columnOdds = [];
                                const oddsElems = section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                                for (const oddsElem of oddsElems) {
                                    const oddsText = oddsElem.textContent;
                                    if (oddsText) {
                                        columnOdds.push(oddsText.trim());
                                    }
                                }
                                oddsColumns[headerText] = columnOdds;
                            }
                        }
                    }

                    // Step 4: Extract game date
                    const dateHeader = uclSection.querySelector('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateHeader ? dateHeader.textContent.trim() : null;
                    if (!gameDate) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }

                    // Step 5: Process fixtures
                    for (let i = 0; i < fixtures.length; i++) {
                        const fixture = fixtures[i];

                        // Extract team names
                        const teamElements = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsSoccer_Team');
                        if (teamElements.length < 2) continue;

                        const team1 = teamElements[0].textContent.trim();
                        const team2 = teamElements[1].textContent.trim();

                        // Extract time
                        const timeElement = fixture.querySelector('div.cpm-ParticipantFixtureDetailsSoccer_BookCloses');
                        const gameTime = timeElement ? timeElement.textContent.trim() : "TBD";

                        // Map odds for soccer (1=home win, X=draw, 2=away win)
                        const moneylineOdds = [];
                        
                        // Team 1 (Home) odds from column "1"
                        if (oddsColumns["1"] && oddsColumns["1"].length > i) {
                            moneylineOdds.push(oddsColumns["1"][i]);
                        }
                        
                        // Draw odds from column "X"
                        let drawOdds = null;
                        if (oddsColumns["X"] && oddsColumns["X"].length > i) {
                            drawOdds = oddsColumns["X"][i];
                        }
                        
                        // Team 2 (Away) odds from column "2"
                        if (oddsColumns["2"] && oddsColumns["2"].length > i) {
                            moneylineOdds.push(oddsColumns["2"][i]);
                        }

                        results.push({
                            team1: team1,
                            team2: team2,
                            date: gameDate,
                            time: gameTime,
                            moneyline: moneylineOdds,
                            draw_odds: drawOdds,
                            fixture_id: `ucl_${i}`
                        });
                    }

                    return results;
                }
            """)

            # Process results into Game objects
            for result in extraction_result:
                # Include draw odds in moneyline
                moneyline_with_draw = result['moneyline'][:]
                if result.get('draw_odds'):
                    moneyline_with_draw.append(result['draw_odds'])

                odds_obj = GameOdds(
                    spread=[],
                    total=[],
                    moneyline=moneyline_with_draw
                )

                game = Game(
                    sport="UCL",
                    team1=self.clean_text(result['team1']) or f"Team1_{len(games)}",
                    team2=self.clean_text(result['team2']) or f"Team2_{len(games)}",
                    date=self.clean_text(result['date']),
                    time=self.clean_text(result['time']),
                    odds=odds_obj,
                    fixture_id=result['fixture_id']
                )

                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)

        except Exception as e:
            self.logger.error(f"UCL extraction error: {e}")

        self.logger.info(f"UCL: Extracted {len(games)} games")
        return games

    async def extract_mls_games(self, page, sport: str) -> List[Game]:
        """MLS extraction using Round 1 section detection with proper odds extraction"""
        games = []

        try:
            self.logger.info("⚽ Starting MLS extraction...")

            extraction_result = await page.evaluate("""
                () => {
                    const results = [];

                    // Step 1: Find MLS section by Round 1 header or MLS logo
                    let mlsSection = null;
                    
                    // Method 1: Look for MLS logo
                    const headerImages = document.querySelectorAll('.cpm-Header_HeaderImage, .ss-HomeSpotlightHeader_HeaderImage');
                    for (const img of headerImages) {
                        const style = img.getAttribute('style') || '';
                        if (style.includes('zlogo_MLS_Official.svg')) {
                            mlsSection = img.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                            console.log('Found MLS section by MLS logo');
                            break;
                        }
                    }

                    // Method 2: Look for Round 1 title as backup
                    if (!mlsSection) {
                        const headers = document.querySelectorAll('.cpm-Header_Title, .ss-HomeSpotlightHeader_Title');
                        for (const header of headers) {
                            if (header.textContent.trim() === 'Round 1') {
                                mlsSection = header.closest('.cpm-CouponPodModule, .ss-HomepageSpotlight');
                                console.log('Found MLS section by Round 1 title');
                                break;
                            }
                        }
                    }

                    if (!mlsSection) {
                        console.log('MLS section not found');
                        return [];
                    }

                    // Step 2: Extract fixtures from MLS section
                    const fixtures = Array.from(mlsSection.querySelectorAll('div.cpm-ParticipantFixtureDetailsSoccer'))
                        .filter(fixture => !fixture.className.includes('Hidden'));

                    console.log(`Found ${fixtures.length} MLS fixtures`);

                    // Step 3: Extract odds columns (1, X, 2 format for soccer)
                    const oddsColumns = {};
                    const marketOdds = Array.from(mlsSection.querySelectorAll('div.cpm-MarketOdds'));
                    
                    for (const section of marketOdds) {
                        const header = section.querySelector('div.cpm-MarketOddsHeader');
                        if (header) {
                            const headerText = header.textContent.trim();
                            if (['1', 'X', '2'].includes(headerText)) {
                                const columnOdds = [];
                                const oddsElems = section.querySelectorAll('span.cpm-ParticipantOdds_Odds');
                                for (const oddsElem of oddsElems) {
                                    const oddsText = oddsElem.textContent;
                                    if (oddsText) {
                                        columnOdds.push(oddsText.trim());
                                    }
                                }
                                oddsColumns[headerText] = columnOdds;
                            }
                        }
                    }

                    // Step 4: Extract game dates for each date section
                    const dateHeaders = mlsSection.querySelectorAll('div.cpm-MarketFixtureDateHeader');
                    let gameDate = dateHeaders.length > 0 ? dateHeaders[0].textContent.trim() : null;
                    if (!gameDate) {
                        const today = new Date();
                        const options = { weekday: 'short', month: 'short', day: 'numeric' };
                        gameDate = today.toLocaleDateString('en-US', options);
                    }

                    // Step 5: Process fixtures
                    for (let i = 0; i < fixtures.length; i++) {
                        const fixture = fixtures[i];

                        // Extract team names
                        const teamElements = fixture.querySelectorAll('div.cpm-ParticipantFixtureDetailsSoccer_Team');
                        if (teamElements.length < 2) continue;

                        const team1 = teamElements[0].textContent.trim();
                        const team2 = teamElements[1].textContent.trim();

                        // Extract time
                        const timeElement = fixture.querySelector('div.cpm-ParticipantFixtureDetailsSoccer_BookCloses');
                        const gameTime = timeElement ? timeElement.textContent.trim() : "TBD";

                        // Map odds for soccer (1=home win, X=draw, 2=away win)
                        const moneylineOdds = [];
                        
                        // Team 1 (Home) odds from column "1"
                        if (oddsColumns["1"] && oddsColumns["1"].length > i) {
                            moneylineOdds.push(oddsColumns["1"][i]);
                        }
                        
                        // Draw odds from column "X"
                        let drawOdds = null;
                        if (oddsColumns["X"] && oddsColumns["X"].length > i) {
                            drawOdds = oddsColumns["X"][i];
                        }
                        
                        // Team 2 (Away) odds from column "2"
                        if (oddsColumns["2"] && oddsColumns["2"].length > i) {
                            moneylineOdds.push(oddsColumns["2"][i]);
                        }

                        results.push({
                            team1: team1,
                            team2: team2,
                            date: gameDate,
                            time: gameTime,
                            moneyline: moneylineOdds,
                            draw_odds: drawOdds, // MLS specific - draw option
                            fixture_id: `mls_${i}`
                        });
                    }

                    return results;
                }
            """)

            # Process results into Game objects
            for result in extraction_result:
                # For MLS, we include draw odds in the total pool
                moneyline_with_draw = result['moneyline'][:]
                if result.get('draw_odds'):
                    moneyline_with_draw.append(result['draw_odds'])

                odds_obj = GameOdds(
                    spread=[],  # MLS doesn't typically use spread betting
                    total=[],   # Total goals betting would need separate extraction
                    moneyline=moneyline_with_draw
                )

                game = Game(
                    sport="MLS",
                    team1=self.clean_text(result['team1']) or f"Team1_{len(games)}",
                    team2=self.clean_text(result['team2']) or f"Team2_{len(games)}",
                    date=self.clean_text(result['date']),
                    time=self.clean_text(result['time']),
                    odds=odds_obj,
                    fixture_id=result['fixture_id']
                )

                game.confidence_score = self.calculate_confidence_score(game)
                games.append(game)

        except Exception as e:
            self.logger.error(f"MLS extraction error: {e}")

        self.logger.info(f"MLS: Extracted {len(games)} games")
        return games

    async def find_sport_tab(self, page, sport: str):
        """Find sport tab element (compatibility method)"""
        sport_patterns = self.sport_patterns.get(sport, {})
        tab_names = sport_patterns.get("tabs", [sport])
        
        for tab_name in tab_names:
            try:
                tab = await page.query_selector(f'div[class*="Classification"]:has-text("{tab_name}")')
                if tab:
                    return tab
            except:
                continue
        return None

    async def find_sport_tab_fast(self, page, sport: str):
        """FAST sport tab detection for real-time monitoring"""
        try:
            # Cache common sport mappings for speed
            sport_mapping = {
                'NFL': 'NFL', 'NBA': 'NBA', 'NHL': 'NHL', 'EPL': 'EPL', 
                'MLB': 'World Series', 'Tennis': 'Tennis', 'NBA2K': 'NBA2K',
                'Soccer': 'Soccer', 'MLS': 'MLS'
            }
            
            tab_name = sport_mapping.get(sport, sport)
            
            # Try most common selectors first for speed
            selectors = [
                f'div[class*="Classification"]:has-text("{tab_name}")',
                f'div[class*="nav"]:has-text("{tab_name}")',
                f'*:has-text("{tab_name}")'
            ]
            
            for selector in selectors:
                try:
                    tab = await page.query_selector(selector)
                    if tab and await tab.is_visible():
                        return tab
                except:
                    continue
                    
            # Fallback to original method
            return await self.find_sport_tab(page, sport)
            
        except Exception as e:
            self.logger.warning(f"Fast tab detection failed for {sport}: {e}")
            return await self.find_sport_tab(page, sport)

    async def extract_sport_games_fast(self, page, sport: str) -> List[Game]:
        """FAST game extraction for real-time monitoring - visible content only"""
        try:
            # Use existing extraction but with minimal waits and no scrolling
            games = await self.extract_sport_games(page, sport)
            
            # For real-time monitoring, limit to first N games for speed
            if len(games) > 20:  # Limit for performance
                games = games[:20]
                
            return games
            
        except Exception as e:
            self.logger.error(f"Fast extraction error for {sport}: {e}")
            return []

    async def close(self):
        """Close the browser and cleanup"""
        try:
            if hasattr(self, 'browser') and self.browser:
                await self.browser.close()
                self.logger.info("🔒 Browser closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing browser: {e}")

    async def extract_games_generic(self, page, sport: str) -> List[Game]:
        """Generic game extraction as fallback"""
        try:
            return await self.extract_sport_games(page, sport)
        except Exception as e:
            self.logger.error(f"Generic extraction failed for {sport}: {e}")
            return []


# ----------------------------- CLI Entry Point ----------------------------- #

async def main():
    parser = argparse.ArgumentParser(description="Enhanced Intelligent Sports Scraper for bet365.ca")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    parser.add_argument("--wait", type=int, default=4000, help="Wait time after tab clicks (ms)")
    parser.add_argument("--scrolls", type=int, default=15, help="Maximum scroll iterations")
    parser.add_argument("--scroll-pause", type=int, default=500, help="Pause between scrolls (ms)")
    
    args = parser.parse_args()

    scraper = EnhancedIntelligentScraper(
        headless=args.headless,
        load_wait=args.wait,
        max_scrolls=args.scrolls,
        scroll_pause=args.scroll_pause,
    )
    
    await scraper.scrape_all_sports()


if __name__ == "__main__":
    asyncio.run(main())