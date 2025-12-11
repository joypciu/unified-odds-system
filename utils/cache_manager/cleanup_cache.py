#!/usr/bin/env python3
"""
Cache Cleanup and Deduplication Utility
Runs intelligent cleanup on existing cache to merge duplicates like:
- "Manchester City", "Man City", "Man City FC" -> "Manchester City"
- "LA Lakers", "Los Angeles Lakers" -> "Los Angeles Lakers"
"""

import sys
from pathlib import Path
from enhanced_cache_manager import EnhancedCacheManager


def main():
    print("=" * 80)
    print("CACHE CLEANUP AND DEDUPLICATION UTILITY")
    print("=" * 80)
    print()
    
    # Initialize enhanced cache manager
    print("[1/4] Loading cache and initializing intelligent name mapper...")
    manager = EnhancedCacheManager()
    
    # Show stats before cleanup
    print("\n[2/4] Current cache statistics:")
    stats_before = manager.get_stats()
    print(f"  - Sports: {stats_before['total_sports']}")
    print(f"  - Teams: {stats_before['total_teams']}")
    print(f"  - Aliases: {stats_before['total_aliases']}")
    print(f"  - Canonical names in mapper: {stats_before['mapper_canonical_names']}")
    
    # Run cleanup and deduplication
    print("\n[3/4] Running intelligent cleanup and deduplication...")
    print("  This will:")
    print("    • Identify duplicate team entries (e.g., 'Man City' vs 'Manchester City')")
    print("    • Merge duplicates into canonical names")
    print("    • Update all aliases and references")
    print("    • Preserve all data (sources, match counts, etc.)")
    print()
    
    result = manager.cleanup_and_deduplicate()
    
    # Show results
    print("\n[4/4] Cleanup complete!")
    print(f"  - Duplicates merged: {result['duplicates_merged']}")
    print(f"  - Teams before: {result['teams_before']}")
    print(f"  - Teams after: {result['teams_after']}")
    print(f"  - Reduction: {result['teams_before'] - result['teams_after']} teams")
    
    # Show stats after cleanup
    print("\n" + "=" * 80)
    print("FINAL CACHE STATISTICS")
    print("=" * 80)
    stats_after = manager.get_stats()
    print(f"  - Sports: {stats_after['total_sports']}")
    print(f"  - Teams: {stats_after['total_teams']}")
    print(f"  - Aliases: {stats_after['total_aliases']}")
    print(f"  - Canonical names in mapper: {stats_after['mapper_canonical_names']}")
    print(f"  - Average aliases per team: {stats_after['total_aliases'] / max(stats_after['total_teams'], 1):.2f}")
    
    print("\n✅ Cache has been cleaned and deduplicated!")
    print(f"   Backup saved to: {manager.cache_backup_dir}")
    print(f"   Mappings saved to: {manager.mappings_file}")
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
