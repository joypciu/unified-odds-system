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
    
    def _create_smart_context(self, question: str, unified_data: Dict, oddsmagnet_data: Dict) -> Dict:
        """
        Create optimized context with smart data sampling based on question
        Reduces payload size by 90% while maintaining relevance
        """
        context = {}
        question_lower = question.lower()
        
        # Detect if user wants specific sport or match details
        needs_full_data = any(keyword in question_lower for keyword in [
            'list all', 'show all', 'every match', 'each match', 'all matches',
            'compare', 'which matches', 'what matches', 'find matches'
        ])
        
        # Extract sport mentions
        mentioned_sports = []
        common_sports = ['football', 'soccer', 'basketball', 'tennis', 'hockey', 'baseball', 
                        'cricket', 'volleyball', 'handball', 'rugby']
        for sport in common_sports:
            if sport in question_lower:
                mentioned_sports.append(sport)
        
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
            
            # Smart sampling: send only relevant data
            if needs_full_data or mentioned_sports:
                # Send filtered data for mentioned sports
                relevant_pregame = {}
                relevant_live = {}
                
                if mentioned_sports:
                    for sport in mentioned_sports:
                        for key in pregame_by_sport:
                            if sport.lower() in key.lower():
                                relevant_pregame[key] = pregame_by_sport[key]
                        for key in live_by_sport:
                            if sport.lower() in key.lower():
                                relevant_live[key] = live_by_sport[key]
                else:
                    relevant_pregame = pregame_by_sport
                    relevant_live = live_by_sport
                
                context['unified'] = {
                    'summary': {
                        'total_pregame': len(pregame_matches),
                        'total_live': len(live_matches),
                        'total_matches': len(pregame_matches) + len(live_matches),
                        'sports': list(set(pregame_by_sport.keys()) | set(live_by_sport.keys()))
                    },
                    'pregame_by_sport': relevant_pregame,
                    'live_by_sport': relevant_live
                }
            else:
                # Send only summary + samples for quick questions
                pregame_samples = {sport: matches[:3] for sport, matches in list(pregame_by_sport.items())[:5]}
                live_samples = {sport: matches[:3] for sport, matches in list(live_by_sport.items())[:5]}
                
                context['unified'] = {
                    'summary': {
                        'total_pregame': len(pregame_matches),
                        'total_live': len(live_matches),
                        'total_matches': len(pregame_matches) + len(live_matches),
                        'sports': list(set(pregame_by_sport.keys()) | set(live_by_sport.keys())),
                        'sport_counts': {sport: len(matches) for sport, matches in pregame_by_sport.items()}
                    },
                    'samples': {
                        'pregame': pregame_samples,
                        'live': live_samples
                    }
                }
        
        if oddsmagnet_data:
            all_matches_by_sport = {}
            total_matches = 0
            
            for sport, data in oddsmagnet_data.items():
                matches = data.get('matches', [])
                match_count = len(matches)
                total_matches += match_count
                
                # Smart sampling for oddsmagnet too
                if needs_full_data or (mentioned_sports and any(s.lower() in sport.lower() for s in mentioned_sports)):
                    all_matches_by_sport[sport] = {
                        'count': match_count,
                        'matches': matches
                    }
                else:
                    # Send only samples for quick responses
                    all_matches_by_sport[sport] = {
                        'count': match_count,
                        'sample_matches': matches[:3]  # Just 3 examples
                    }
            
            context['oddsmagnet'] = {
                'summary': {
                    'total_sports': len(oddsmagnet_data),
                    'total_matches': total_matches,
                    'sports': list(oddsmagnet_data.keys())
                },
                'matches_by_sport': all_matches_by_sport
            }
        
        return context
    
    def ask_llm_question(self, question: str, context: Optional[Dict] = None, enable_reasoning: bool = False) -> Dict:
        """
        Ask the LLM a specific question about the data with optimized RAG support
        
        Args:
            question: User's question
            context: Additional context (optional)
            enable_reasoning: Enable deep reasoning mode (slower but more thorough)
            
        Returns:
            Dictionary with LLM response
        """
        if not self.llm_agent:
            return {
                "success": False,
                "error": "LLM agent not available"
            }
        
        try:
            # Reinitialize agent if reasoning mode differs
            if self.llm_agent.enable_reasoning != enable_reasoning:
                api_key = os.getenv('OPENROUTER_API_KEY')
                from llm_agent import LLMAgent
                self.llm_agent = LLMAgent(provider='openrouter', api_key=api_key, enable_reasoning=enable_reasoning)
            
            # Load current data to provide real context
            if context is None:
                # Use cached data to speed up responses
                unified_data, oddsmagnet_data = self._get_cached_data()
                
                # Create optimized context with smart sampling
                context = self._create_smart_context(question, unified_data, oddsmagnet_data)
            
            # Enhanced RAG prompt with smart instructions
            has_full_data = 'pregame_by_sport' in context.get('unified', {})
            
            if has_full_data:
                data_info = """You have access to FULL odds data for relevant sports.

DATA STRUCTURE:
- unified.summary = Total counts and sports list
- unified.pregame_by_sport = Complete pregame matches by sport
- unified.live_by_sport = Complete live matches by sport  
- oddsmagnet.matches_by_sport = Complete OddsMagnet matches by sport"""
            else:
                data_info = """You have access to SUMMARY statistics with sample matches.

DATA STRUCTURE:
- unified.summary = Total counts, sports list, and match counts per sport
- unified.samples = Sample matches from top sports (for reference)
- oddsmagnet.summary = Total OddsMagnet statistics
- oddsmagnet.matches_by_sport = Match counts with samples"""
            
            enhanced_question = f"""{data_info}

INSTRUCTIONS:
1. Use summary statistics for counts and totals
2. Reference sample matches to provide specific examples
3. Answer accurately based on the data provided
4. If asked for specific details not in samples, use summary counts

USER QUESTION: {question}"""

            response = self.llm_agent.ask_question(enhanced_question, context)
            return {
                "success": True,
                "question": question,
                "answer": response,
                "timestamp": datetime.now().isoformat(),
                "used_real_data": bool(context.get('unified_sample') or context.get('oddsmagnet_sample'))
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
