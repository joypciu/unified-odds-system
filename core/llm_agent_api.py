"""
LLM Agent API Integration
Provides real-time LLM analysis for the odds comparison UI
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional, List
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from agent/.env
load_dotenv(Path(__file__).parent.parent / "agent" / ".env")

# Add agent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "agent"))

from data_analyzer import DataAnalyzer
from llm_agent import LLMAgent

class LLMAgentAPI:
    """
    API wrapper for LLM Agent to integrate with FastAPI backend
    """
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.analyzer = None
        self.llm_agent = None
        self.last_analysis = None
        self.last_analysis_time = None
        self._data_cache = None
        self._data_cache_time = None
        self._cache_ttl = 60  # Cache data for 60 seconds
        self._initialize()
    
    def _initialize(self):
        """Initialize the data analyzer and LLM agent"""
        try:
            # Initialize data analyzer
            self.analyzer = DataAnalyzer(str(self.base_dir))
            print("✅ LLM Agent API: Data analyzer initialized")
            
            # Try OpenRouter first (MiMo/Mistral dual-model)
            openrouter_key = os.getenv('OPENROUTER_API_KEY')
            if openrouter_key and openrouter_key.startswith('sk-or-v1-') and len(openrouter_key) > 20:
                try:
                    self.llm_agent = LLMAgent(provider='openrouter', api_key=openrouter_key, enable_reasoning=False)
                    print("✅ LLM Agent API: LLM agent initialized with OpenRouter (MiMo/Mistral dual-model)")
                    return
                except Exception as e:
                    print(f"⚠️  LLM Agent API: OpenRouter failed: {e}")
            
            # Fallback to Google Gemini if OpenRouter not available
            google_key = os.getenv('GOOGLE_API_KEY')
            if google_key:
                try:
                    self.llm_agent = LLMAgent(provider='google', api_key=google_key, enable_reasoning=False)
                    print("✅ LLM Agent API: LLM agent initialized with Google Gemini (fallback)")
                    return
                except Exception as e:
                    print(f"⚠️  LLM Agent API: Google Gemini failed: {e}")
            
            print("⚠️  LLM Agent API: No valid API keys found, LLM features disabled")
            self.llm_agent = None
                
        except Exception as e:
            print(f"❌ LLM Agent API: Initialization failed: {e}")
            self.analyzer = None
            self.llm_agent = None
    
    def get_data_status(self) -> Dict:
        """
        Get current data availability status for UI display
        
        Returns:
            {
                'data_available': bool,
                'unified_count': int,
                'oddsmagnet_count': int,
                'total_matches': int,
                'last_updated': str,
                'error': str (optional)
            }
        """
        try:
            if not self.analyzer:
                return {
                    'data_available': False,
                    'error': 'Data analyzer not initialized',
                    'unified_count': 0,
                    'oddsmagnet_count': 0,
                    'total_matches': 0
                }
            
            # Use cached data if available
            unified_data, oddsmagnet_data = self._get_cached_data()
            
            if not unified_data and not oddsmagnet_data:
                return {
                    'data_available': False,
                    'error': 'No data files found',
                    'unified_count': 0,
                    'oddsmagnet_count': 0,
                    'total_matches': 0
                }
            
            # Calculate counts
            unified_count = 0
            if unified_data:
                unified_count = len(unified_data.get('pregame_matches', [])) + len(unified_data.get('live_matches', []))
            
            oddsmagnet_count = 0
            if oddsmagnet_data:
                oddsmagnet_count = sum(
                    data.get('matches_count', len(data.get('matches', []))) 
                    for data in oddsmagnet_data.values()
                )
            
            return {
                'data_available': True,
                'unified_count': unified_count,
                'oddsmagnet_count': oddsmagnet_count,
                'total_matches': unified_count + oddsmagnet_count,
                'last_updated': datetime.now().isoformat()
            }
        except Exception as e:
            return {
                'data_available': False,
                'error': str(e),
                'unified_count': 0,
                'oddsmagnet_count': 0,
                'total_matches': 0
            }
    
    def load_data(self) -> Dict:
        """Load and analyze current data"""
        if not self.analyzer:
            return {"error": "Analyzer not initialized"}
        
        try:
            # Load unified and oddsmagnet data
            unified_data = self.analyzer.load_unified_data()
            oddsmagnet_data = self.analyzer.load_oddsmagnet_data()
            
            if not unified_data and not oddsmagnet_data:
                return {"error": "Failed to load data"}
            
            # Calculate match counts
            unified_count = len(unified_data.get('pregame_matches', [])) + len(unified_data.get('live_matches', []))
            oddsmagnet_count = sum(
                data.get('matches_count', len(data.get('matches', []))) 
                for data in oddsmagnet_data.values()
            )
            
            # Generate analysis report
            report = self.analyzer.generate_analysis_report()
            
            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "unified_matches": unified_count,
                "oddsmagnet_matches": oddsmagnet_count,
                "report": report
            }
        except Exception as e:
            return {"error": f"Data loading failed: {str(e)}"}
    
    def get_quick_analysis(self, force_refresh: bool = False) -> Dict:
        """
        Get quick correlation analysis (cached for 5 minutes unless forced)
        
        Args:
            force_refresh: Force new analysis even if cached
            
        Returns:
            Dictionary with analysis results
        """
        # Check cache (5 minutes)
        if not force_refresh and self.last_analysis and self.last_analysis_time:
            time_since_last = (datetime.now() - self.last_analysis_time).total_seconds()
            if time_since_last < 300:  # 5 minutes
                return {
                    "success": True,
                    "cached": True,
                    "cache_age_seconds": int(time_since_last),
                    **self.last_analysis
                }
        
        # Load fresh data
        data_result = self.load_data()
        if "error" in data_result:
            return data_result
        
        report = data_result["report"]
        
        # Calculate correlation rate
        total_checked = report['correlations']['matches_found'] + report['correlations']['matches_not_found']
        correlation_rate = 0.0
        if total_checked > 0:
            correlation_rate = (report['correlations']['matches_found'] / total_checked) * 100
        
        # Prepare quick summary
        analysis = {
            "timestamp": data_result["timestamp"],
            "unified_total": data_result["unified_matches"],
            "oddsmagnet_total": data_result["oddsmagnet_matches"],
            "correlation_rate": round(correlation_rate, 1),
            "matches_found": report['correlations']['matches_found'],
            "matches_not_found": report['correlations']['matches_not_found'],
            "unified_sports": report['summary'].get('unified_sports', []),
            "oddsmagnet_sports": report['summary'].get('oddsmagnet_sports', []),
            "insights": report.get('insights', [])
        }
        
        # Cache the result
        self.last_analysis = analysis
        self.last_analysis_time = datetime.now()
        
        return {
            "success": True,
            "cached": False,
            **analysis
        }
    
    def get_llm_analysis(self, force_refresh: bool = False, enable_reasoning: bool = False) -> Dict:
        """
        Get comprehensive LLM-powered analysis
        
        Args:
            force_refresh: Force new LLM analysis
            enable_reasoning: Enable deep reasoning mode
                             False: Ultra-fast Mistral 7B (~3-5s)
                             True: Deep thinking MiMo-V2 (~15-20s)
            
        Returns:
            Dictionary with LLM analysis
        """
        if not self.llm_agent:
            return {
                "success": False,
                "error": "LLM agent not available",
                "message": "Please set OPENROUTER_API_KEY environment variable"
            }
        
        # Get quick analysis first
        quick_result = self.get_quick_analysis(force_refresh)
        if not quick_result.get("success"):
            return quick_result
        
        # Load full report
        data_result = self.load_data()
        if "error" in data_result:
            return data_result
        
        try:
            # Reinitialize agent if reasoning mode differs from current setting
            if self.llm_agent.enable_reasoning != enable_reasoning:
                api_key = os.getenv('OPENROUTER_API_KEY')
                from llm_agent import LLMAgent
                self.llm_agent = LLMAgent(provider='openrouter', api_key=api_key, enable_reasoning=enable_reasoning)
            
            # Get LLM analysis with selected mode
            import time
            start_time = time.time()
            llm_analysis = self.llm_agent.analyze_data_correlation(data_result["report"])
            analysis_time = time.time() - start_time
            
            return {
                "success": True,
                "timestamp": datetime.now().isoformat(),
                "quick_summary": quick_result,
                "llm_analysis": llm_analysis,
                "analysis_time_seconds": round(analysis_time, 2),
                "model_used": self.llm_agent.model,
                "reasoning_mode": enable_reasoning,
                "has_llm": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"LLM analysis failed: {str(e)}",
                "quick_summary": quick_result,
                "has_llm": False
            }
    
    def _get_cached_data(self):
        """Get cached data or load fresh if expired"""
        now = datetime.now()
        
        # Check if cache is valid
        if (self._data_cache is not None and 
            self._data_cache_time is not None and 
            (now - self._data_cache_time).total_seconds() < self._cache_ttl):
            return self._data_cache
        
        # Load fresh data
        unified_data = self.analyzer.load_unified_data() if self.analyzer else None
        oddsmagnet_data = self.analyzer.load_oddsmagnet_data() if self.analyzer else None
        
        self._data_cache = (unified_data, oddsmagnet_data)
        self._data_cache_time = now
        
        return self._data_cache
    
    def _analyze_query_intent(self, question: str) -> Dict:
        """
        Analyze query to determine what data is needed and which model to use
        
        Returns:
            {
                'needs_full_data': bool,
                'query_type': str (count/specific/comparison/general),
                'mentioned_sports': list,
                'use_reasoning': bool (use MiMo for complex queries)
            }
        """
        question_lower = question.lower()
        
        # Detect odds-related queries that need actual odds data
        is_odds_query = any(keyword in question_lower for keyword in [
            'odds', 'highest odds', 'lowest odds', 'best odds', 'value', 'price'
        ])
        
        # Detect query type
        is_count_query = any(keyword in question_lower for keyword in [
            'how many', 'count', 'number of', 'total', 'sum'
        ]) and not is_odds_query  # Don't treat "how many matches with odds >2.0" as count query
        
        is_specific_query = any(keyword in question_lower for keyword in [
            'list all', 'show all', 'every match', 'each match', 'all matches',
            'which matches', 'what matches', 'find matches', 'show me matches',
            'get all', 'display all', 'show me', 'give me'
        ]) or is_odds_query  # Odds queries need specific data
        
        is_comparison_query = any(keyword in question_lower for keyword in [
            'compare', 'difference', 'versus', 'vs', 'better', 'best', 'highest', 'lowest',
            'greater', 'less', 'more', 'above', 'below', 'over', 'under'
        ])
        
        is_analysis_query = any(keyword in question_lower for keyword in [
            'analyze', 'insight', 'pattern', 'trend', 'correlation', 'why', 'explain'
        ])
        
        # Extract sport mentions
        mentioned_sports = []
        common_sports = ['football', 'soccer', 'basketball', 'tennis', 'hockey', 'baseball', 
                        'cricket', 'volleyball', 'handball', 'rugby', 'american-football',
                        'table-tennis', 'boxing', 'mma', 'golf']
        for sport in common_sports:
            if sport in question_lower or sport.replace('-', ' ') in question_lower:
                mentioned_sports.append(sport)
        
        # Determine if full data is needed
        needs_full_data = is_specific_query or (is_comparison_query and mentioned_sports)
        
        # Determine query type
        if is_count_query:
            query_type = 'count'
        elif is_specific_query:
            query_type = 'specific'
        elif is_comparison_query:
            query_type = 'comparison'
        elif is_analysis_query:
            query_type = 'analysis'
        else:
            query_type = 'general'
        
        # Use MiMo reasoning for complex queries requiring full data
        use_reasoning = needs_full_data or is_analysis_query
        
        return {
            'needs_full_data': needs_full_data,
            'query_type': query_type,
            'mentioned_sports': mentioned_sports,
            'use_reasoning': use_reasoning
        }
    
    def _create_smart_context(self, question: str, unified_data: Dict, oddsmagnet_data: Dict) -> Dict:
        """
        Create optimized context with intelligent data sampling based on query analysis
        Reduces payload size by 95%+ while maintaining relevance
        """
        context = {}
        
        # Analyze query intent
        intent = self._analyze_query_intent(question)
        needs_full_data = intent['needs_full_data']
        query_type = intent['query_type']
        mentioned_sports = intent['mentioned_sports']
        question_lower = question.lower()
        
        # Check if query is about odds values
        needs_odds = any(word in question_lower for word in ['odds', 'price', 'value', 'highest', 'lowest', 'best'])
        
        # Helper function to strip unnecessary fields from match data
        def compress_match(match, include_full_odds=False):
            """Keep only essential fields to reduce token count by 90%"""
            # Extract odds information - handle different data structures
            compressed_odds = {}
            
            # Check for unified data structure (bookmakers as top-level keys)
            if 'fanduel' in match or '1xbet' in match or 'bet365' in match:
                # Unified data structure
                bookmakers = ['fanduel', '1xbet', 'bet365']
                for bookie in bookmakers[:3 if include_full_odds else 1]:
                    if bookie in match and match[bookie].get('available'):
                        bookie_odds = match[bookie].get('odds', {})
                        if bookie_odds:
                            if include_full_odds:
                                compressed_odds[bookie] = bookie_odds
                            else:
                                # Keep minimal odds for non-odds queries
                                compressed_odds[bookie] = {
                                    k: v for k, v in list(bookie_odds.items())[:3]
                                }
            
            # Check for OddsMagnet data structure (markets)
            elif 'markets' in match:
                markets = match.get('markets', {})
                if include_full_odds and markets:
                    # For odds queries, extract actual odds values from markets (simplified)
                    simplified_markets = {}
                    for market_type, market_list in list(markets.items())[:3]:  # Limit to 3 market types
                        if isinstance(market_list, list):
                            # Extract just the odds values from first 2 markets of each type
                            odds_list = []
                            for market in market_list[:2]:
                                if isinstance(market, dict) and 'odds' in market:
                                    odds_value = market.get('odds', '')
                                    # Handle odds being a list, string, or other type
                                    if isinstance(odds_value, list):
                                        odds_str = str(odds_value) if odds_value else ''
                                    elif isinstance(odds_value, str):
                                        odds_str = odds_value.strip()
                                    else:
                                        odds_str = str(odds_value) if odds_value else ''
                                    
                                    if odds_str and odds_str != ' ':
                                        odds_list.append({
                                            'name': market.get('name', ''),
                                            'odds': odds_str
                                        })
                            if odds_list:
                                simplified_markets[market_type] = odds_list
                    compressed_odds['markets'] = simplified_markets if simplified_markets else 'Available'
                else:
                    # For non-odds queries, just indicate markets exist
                    market_count = sum(len(v) if isinstance(v, list) else 1 for v in markets.values())
                    compressed_odds['markets'] = f"{market_count} markets"
            
            # Check for standard odds structure (legacy/other formats)
            elif 'odds' in match:
                odds = match.get('odds', {})
                if include_full_odds and odds:
                    # For odds queries, keep more bookmakers and odds types
                    for bookie, bookie_odds in list(odds.items())[:3]:
                        if isinstance(bookie_odds, dict):
                            compressed_odds[bookie] = {}
                            # Keep all main odds types
                            for key in ['home', 'away', 'draw', 'over', 'under', '1', 'X', '2']:
                                if key in bookie_odds:
                                    compressed_odds[bookie][key] = bookie_odds[key]
                elif odds:
                    # For non-odds queries, keep minimal odds
                    for bookie, bookie_odds in list(odds.items())[:1]:
                        if isinstance(bookie_odds, dict):
                            for key in ['home', 'away', 'draw']:
                                if key in bookie_odds:
                                    compressed_odds[key] = bookie_odds[key]
                            break
            
            # Build teams string safely
            teams = match.get('teams') or match.get('name')
            if not teams:
                home_team = match.get('home_team') or match.get('home') or ''
                away_team = match.get('away_team') or match.get('away') or ''
                teams = f"{home_team} vs {away_team}" if home_team or away_team else 'Unknown'
            
            return {
                'teams': teams,
                'sport': match.get('sport', ''),
                'league': match.get('league', ''),
                'odds': compressed_odds if compressed_odds else 'N/A'
            }
        
        if unified_data:
            pregame_matches = unified_data.get('pregame_matches', [])
            live_matches = unified_data.get('live_matches', [])
            
            # Organize by sport
            pregame_by_sport = {}
            for match in pregame_matches:
                sport = match.get('sport', 'unknown')
                if sport not in pregame_by_sport:
                    pregame_by_sport[sport] = []
                pregame_by_sport[sport].append(match)
            
            live_by_sport = {}
            for match in live_matches:
                sport = match.get('sport', 'unknown')
                if sport not in live_by_sport:
                    live_by_sport[sport] = []
                live_by_sport[sport].append(match)
            
            # Smart data selection based on query type
            if query_type == 'count':
                # For count queries, send only summary statistics
                context['unified'] = {
                    'summary': {
                        'total_pregame': len(pregame_matches),
                        'total_live': len(live_matches),
                        'total_matches': len(pregame_matches) + len(live_matches),
                        'sports': list(set(pregame_by_sport.keys()) | set(live_by_sport.keys())),
                        'sport_counts': {
                            'pregame': {sport: len(matches) for sport, matches in pregame_by_sport.items()},
                            'live': {sport: len(matches) for sport, matches in live_by_sport.items()}
                        }
                    }
                }
            elif needs_full_data:
                # Send compressed data only for mentioned sports
                relevant_pregame = {}
                relevant_live = {}
                
                if mentioned_sports:
                    # Filter by mentioned sports and compress - limit matches based on odds query
                    match_limit = 5 if needs_odds else 8
                    for sport in mentioned_sports:
                        for key in pregame_by_sport:
                            if sport.lower() in key.lower():
                                relevant_pregame[key] = [compress_match(m, needs_odds) for m in pregame_by_sport[key][:match_limit]]
                        for key in live_by_sport:
                            if sport.lower() in key.lower():
                                relevant_live[key] = [compress_match(m, needs_odds) for m in live_by_sport[key][:match_limit]]
                else:
                    # Send top 2 sports only, compressed - fewer matches for odds queries
                    match_limit = 3 if needs_odds else 5
                    for k, v in list(pregame_by_sport.items())[:2]:
                        relevant_pregame[k] = [compress_match(m, needs_odds) for m in v[:match_limit]]
                    for k, v in list(live_by_sport.items())[:2]:
                        relevant_live[k] = [compress_match(m, needs_odds) for m in v[:match_limit]]
                
                context['unified'] = {
                    'summary': {
                        'total_pregame': len(pregame_matches),
                        'total_live': len(live_matches),
                        'sports': list(set(pregame_by_sport.keys()) | set(live_by_sport.keys()))
                    },
                    'pregame_by_sport': relevant_pregame,
                    'live_by_sport': relevant_live
                }
            else:
                # For general queries, send only 1 sample from top 2 sports
                pregame_samples = {sport: [compress_match(matches[0], needs_odds)] for sport, matches in list(pregame_by_sport.items())[:2] if matches}
                live_samples = {sport: [compress_match(matches[0], needs_odds)] for sport, matches in list(live_by_sport.items())[:2] if matches}
                
                context['unified'] = {
                    'summary': {
                        'total_pregame': len(pregame_matches),
                        'total_live': len(live_matches),
                        'total_matches': len(pregame_matches) + len(live_matches),
                        'sports': list(set(pregame_by_sport.keys()) | set(live_by_sport.keys())),
                        'sport_counts': {sport: len(matches) for sport, matches in pregame_by_sport.items()}
                    },
                    'sample_pregame': pregame_samples,
                    'sample_live': live_samples
                }
        
        if oddsmagnet_data:
            all_matches_by_sport = {}
            total_matches = 0
            
            for sport, data in oddsmagnet_data.items():
                matches = data.get('matches', [])
                match_count = len(matches)
                total_matches += match_count
                
                # Apply same aggressive compression
                if query_type == 'count':
                    # Only counts for count queries
                    all_matches_by_sport[sport] = {'count': match_count}
                elif needs_full_data and (not mentioned_sports or any(s.lower() in sport.lower() for s in mentioned_sports)):
                    # Compressed data for relevant sports - limit based on odds query (2 for odds, 5 for others)
                    match_limit = 2 if needs_odds else 5
                    all_matches_by_sport[sport] = {
                        'count': match_count,
                        'matches': [compress_match(m, needs_odds) for m in matches[:match_limit]]
                    }
                else:
                    # No samples for general queries to save tokens
                    all_matches_by_sport[sport] = {'count': match_count}
            
            context['oddsmagnet'] = {
                'summary': {
                    'total_sports': len(oddsmagnet_data),
                    'total_matches': total_matches,
                    'sports': list(oddsmagnet_data.keys())
                },
                'matches_by_sport': all_matches_by_sport
            }
        
        # Add query intent to context for better LLM understanding
        context['query_intent'] = intent
        
        return context
    
    def ask_llm_question(self, question: str, context: Optional[Dict] = None, enable_reasoning: bool = None) -> Dict:
        """
        Ask the LLM a specific question about the data with intelligent model selection
        
        Args:
            question: User's question
            context: Additional context (optional)
            enable_reasoning: Enable deep reasoning mode (auto-detected if None)
            
        Returns:
            Dictionary with LLM response
        """
        if not self.llm_agent:
            return {
                "success": False,
                "error": "LLM agent not available"
            }
        
        try:
            # Load current data to provide real context
            if context is None:
                # Use cached data to speed up responses
                unified_data, oddsmagnet_data = self._get_cached_data()
                
                # Create optimized context with smart sampling
                context = self._create_smart_context(question, unified_data, oddsmagnet_data)
            
            # Auto-detect reasoning mode if not specified
            if enable_reasoning is None:
                intent = context.get('query_intent', {})
                enable_reasoning = intent.get('use_reasoning', False)
            
            # Reinitialize agent if reasoning mode differs
            current_reasoning = getattr(self.llm_agent, 'enable_reasoning', False)
            if current_reasoning != enable_reasoning:
                openrouter_key = os.getenv('OPENROUTER_API_KEY')
                google_key = os.getenv('GOOGLE_API_KEY')
                
                if openrouter_key and openrouter_key.startswith('sk-or-v1-') and len(openrouter_key) > 20:
                    from llm_agent import LLMAgent
                    self.llm_agent = LLMAgent(provider='openrouter', api_key=openrouter_key, enable_reasoning=enable_reasoning)
                    model_name = "MiMo-V2 (Deep Reasoning)" if enable_reasoning else "Mistral 7B (Fast)"
                elif google_key:
                    from llm_agent import LLMAgent
                    self.llm_agent = LLMAgent(provider='google', api_key=google_key, enable_reasoning=False)
                    model_name = "Google Gemini"
                    enable_reasoning = False  # Google doesn't support reasoning mode
            else:
                model_name = self.llm_agent.model
            
            # Build enhanced prompt based on query type and available data
            intent = context.get('query_intent', {})
            query_type = intent.get('query_type', 'general')
            
            if query_type == 'count':
                data_info = """You have access to SUMMARY STATISTICS with match counts.

DATA AVAILABLE:
- unified.summary.sport_counts = Match counts per sport (pregame and live)
- oddsmagnet.matches_by_sport = Match counts per sport in OddsMagnet

INSTRUCTIONS: Answer count questions using the summary statistics provided."""
            
            elif intent.get('needs_full_data'):
                data_info = """You have access to DETAILED MATCH DATA for relevant sports.

DATA AVAILABLE:
- unified.pregame_by_sport = Pregame matches organized by sport
- unified.live_by_sport = Live matches organized by sport
- oddsmagnet.matches_by_sport = OddsMagnet matches with full details

INSTRUCTIONS: Analyze the provided matches and give specific, detailed answers."""
            
            else:
                data_info = """You have access to SUMMARY STATISTICS with sample matches.

DATA AVAILABLE:
- unified.summary = Total counts and sport breakdown
- unified.sample_pregame/sample_live = Sample matches for reference
- oddsmagnet.summary = OddsMagnet statistics
- oddsmagnet.matches_by_sport = Counts with sample matches

INSTRUCTIONS: Use summary stats for counts. Reference samples for examples."""
            
            enhanced_question = f"""{data_info}

USER QUESTION: {question}

Provide a clear, concise answer based on the data available."""

            response = self.llm_agent.ask_question(enhanced_question, context)
            return {
                "success": True,
                "question": question,
                "answer": response,
                "timestamp": datetime.now().isoformat(),
                "model_used": model_name,
                "reasoning_enabled": enable_reasoning,
                "query_type": query_type,
                "data_scope": "full" if intent.get('needs_full_data') else "summary"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Question processing failed: {str(e)}"
            }
    
    def get_match_comparison(self, unified_match_id: str, oddsmagnet_match_id: str) -> Dict:
        """
        Get detailed LLM comparison of two specific matches
        
        Args:
            unified_match_id: Match ID from unified system
            oddsmagnet_match_id: Match ID from oddsmagnet
            
        Returns:
            Dictionary with match comparison
        """
        if not self.llm_agent:
            return {
                "success": False,
                "error": "LLM agent not available"
            }
        
        # TODO: Implement match lookup by ID
        # For now, return placeholder
        return {
            "success": False,
            "error": "Feature under development"
        }
    
    def get_status(self) -> Dict:
        """Get current status of LLM Agent API"""
        return {
            "analyzer_ready": self.analyzer is not None,
            "llm_ready": self.llm_agent is not None,
            "has_cached_analysis": self.last_analysis is not None,
            "cache_age_seconds": int((datetime.now() - self.last_analysis_time).total_seconds()) if self.last_analysis_time else None,
            "llm_provider": "google" if self.llm_agent else None,
            "llm_model": self.llm_agent.model if self.llm_agent else None
        }


# Singleton instance
_llm_agent_api = None

def get_llm_agent_api(base_dir: Path) -> LLMAgentAPI:
    """Get or create singleton LLM Agent API instance"""
    global _llm_agent_api
    if _llm_agent_api is None:
        _llm_agent_api = LLMAgentAPI(base_dir)
    return _llm_agent_api
