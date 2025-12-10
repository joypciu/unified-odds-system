#!/usr/bin/env python3
"""
Cache Auto-Update Hook
Import this module in any scraper to automatically trigger cache updates
Runs silently in the background without manual intervention
"""

import os
import sys
from pathlib import Path
import threading
import time
from datetime import datetime

# Flag to ensure only one update thread runs
_update_thread = None
_update_lock = threading.Lock()
_is_updating = False


def _run_cache_update_silent(source_name: str, data_file: Path):
    """
    Silently update cache in background thread
    Called automatically when scrapers save data
    """
    global _is_updating
    
    # Prevent concurrent updates
    with _update_lock:
        if _is_updating:
            return
        _is_updating = True
    
    try:
        # Find base directory
        if 'main' in str(data_file):
            # We're in a subdirectory (1xbet, bet365, fanduel)
            base_dir = data_file.parent.parent
        else:
            base_dir = data_file.parent
        
        # Import cache manager
        sys.path.insert(0, str(base_dir))
        
        try:
            from enhanced_cache_manager import EnhancedCacheManager
            use_enhanced = True
        except ImportError:
            try:
                from dynamic_cache_manager import DynamicCacheManager
                use_enhanced = False
            except ImportError:
                # Cache system not available
                return
        
        # Initialize and update cache
        if use_enhanced:
            cache_manager = EnhancedCacheManager(base_dir)
            if data_file.exists():
                # Update silently (quiet=True)
                cache_manager.auto_update_from_json(data_file, source_name, quiet=True)
        else:
            cache_manager = DynamicCacheManager(base_dir)
            if data_file.exists():
                cache_manager.auto_update_from_file(data_file, source_name)
        
    except Exception as e:
        # Silent failure - don't interrupt scraper
        pass
    finally:
        with _update_lock:
            _is_updating = False


def trigger_cache_update(source_name: str, data_file: Path, async_mode: bool = True):
    """
    Trigger cache update after scraper saves data
    
    Args:
        source_name: Source identifier ('1xbet', 'bet365', 'fanduel')
        data_file: Path to the JSON file that was just saved
        async_mode: Run in background thread (default: True)
    """
    global _update_thread
    
    if not data_file.exists():
        return
    
    if async_mode:
        # Run in background thread to not block scraper
        _update_thread = threading.Thread(
            target=_run_cache_update_silent,
            args=(source_name, data_file),
            daemon=True
        )
        _update_thread.start()
    else:
        # Run synchronously
        _run_cache_update_silent(source_name, data_file)


def on_data_saved(source_name: str, file_path: str):
    """
    Hook function to call after saving scraper data
    
    Usage in scrapers:
        from cache_auto_update_hook import on_data_saved
        
        # After saving your JSON data:
        on_data_saved('1xbet', '1xbet/1xbet_pregame.json')
    
    Args:
        source_name: Source identifier ('1xbet', 'bet365', 'fanduel')
        file_path: Relative or absolute path to saved JSON file
    """
    data_file = Path(file_path)
    if not data_file.is_absolute():
        # Make absolute path
        data_file = Path.cwd() / data_file
    
    # Trigger cache update in background
    trigger_cache_update(source_name, data_file, async_mode=True)


# Auto-execute on import (for simple integration)
def auto_setup():
    """
    Automatically called on module import
    Sets up monitoring for JSON file changes
    """
    pass


# Convenience function for scrapers
def register_scraper(source_name: str):
    """
    Register a scraper for automatic cache updates
    Returns a callback function to use after saving data
    
    Usage:
        from cache_auto_update_hook import register_scraper
        
        cache_callback = register_scraper('1xbet')
        
        # After saving data:
        cache_callback('1xbet/1xbet_pregame.json')
    """
    def callback(file_path: str):
        on_data_saved(source_name, file_path)
    
    return callback


if __name__ == "__main__":
    # Test the hook
    print("Cache Auto-Update Hook - Test Mode")
    print("=" * 60)
    
    test_file = Path(__file__).parent / "unified_odds.json"
    
    if test_file.exists():
        print(f"Testing cache update with: {test_file.name}")
        trigger_cache_update("test", test_file, async_mode=False)
        print("✅ Test complete")
    else:
        print(f"⚠️  Test file not found: {test_file}")
