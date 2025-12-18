#!/usr/bin/env python3
"""
JSON Compression Utility
Provides efficient compressed JSON file operations with backward compatibility
"""

import json
import gzip
import os
from pathlib import Path
from typing import Dict, Any, Optional


def save_compressed_json(data: Dict[str, Any], output_file: Path, compress: bool = True) -> bool:
    """
    Save JSON data with optional gzip compression
    
    Args:
        data: Dictionary to save
        output_file: Path to output file
        compress: Whether to create compressed version (default: True)
    
    Returns:
        bool: True if successful, False otherwise
    
    Features:
        - Atomic writes (temp file + rename)
        - Gzip compression (70% size reduction)
        - Backward compatibility (always writes uncompressed too)
        - mtime touch for cache busting
    """
    try:
        # Serialize JSON once
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        json_bytes = json_str.encode('utf-8')
        
        # Atomic write: write to temp file then rename
        temp_file = str(output_file) + '.tmp'
        
        # Write uncompressed (for backward compatibility)
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(json_str)
            f.flush()
            os.fsync(f.fileno())
        
        # Atomic rename (replaces old file)
        os.replace(temp_file, output_file)
        
        # Write compressed version if enabled
        if compress:
            compressed_file = str(output_file) + '.gz'
            temp_compressed = compressed_file + '.tmp'
            
            with gzip.open(temp_compressed, 'wb', compresslevel=6) as f:
                f.write(json_bytes)
                f.flush()
                os.fsync(f.fileno())
            
            # Atomic rename for compressed file
            os.replace(temp_compressed, compressed_file)
        
        # CRITICAL: Touch the file to update mtime for cache busting
        Path(output_file).touch(exist_ok=True)
        
        return True
        
    except Exception as e:
        print(f"⚠️ Error saving JSON: {e}")
        # Clean up temp files
        for temp in [temp_file, temp_compressed if compress else None]:
            if temp and os.path.exists(temp):
                try:
                    os.remove(temp)
                except:
                    pass
        return False


def load_json(file_path: Path, prefer_compressed: bool = True) -> Optional[Dict[str, Any]]:
    """
    Load JSON data, preferring compressed version if available
    
    Args:
        file_path: Path to JSON file
        prefer_compressed: Try loading .gz version first (default: True)
    
    Returns:
        Dict or None if file doesn't exist or can't be loaded
    """
    try:
        compressed_file = Path(str(file_path) + '.gz')
        
        # Try compressed first if preferred and exists
        if prefer_compressed and compressed_file.exists():
            with gzip.open(compressed_file, 'rt', encoding='utf-8') as f:
                return json.load(f)
        
        # Fall back to uncompressed
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return None
        
    except Exception as e:
        print(f"⚠️ Error loading JSON from {file_path}: {e}")
        return None


def get_file_info(file_path: Path) -> Dict[str, Any]:
    """
    Get file information including size savings from compression
    
    Returns:
        Dict with 'size', 'compressed_size', 'savings_percent', 'mtime'
    """
    info = {
        'size': 0,
        'compressed_size': 0,
        'savings_percent': 0,
        'mtime': 0,
        'exists': False,
        'compressed_exists': False
    }
    
    try:
        if file_path.exists():
            info['exists'] = True
            info['size'] = file_path.stat().st_size
            info['mtime'] = file_path.stat().st_mtime
        
        compressed_file = Path(str(file_path) + '.gz')
        if compressed_file.exists():
            info['compressed_exists'] = True
            info['compressed_size'] = compressed_file.stat().st_size
            
            if info['size'] > 0:
                info['savings_percent'] = (1 - info['compressed_size'] / info['size']) * 100
        
        return info
        
    except Exception as e:
        print(f"⚠️ Error getting file info: {e}")
        return info
