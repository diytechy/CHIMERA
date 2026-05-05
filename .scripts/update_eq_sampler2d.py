#!/usr/bin/env python3
import os
import re
from pathlib import Path

# The sampler-2d block to append
SAMPLER_2D_BLOCK = """
  sampler-2d:
    dimensions: 2
    type: CONSTANT
    value: 0"""

def has_sampler_2d(content):
    """Check if file contains sampler-2d"""
    return "sampler-2d:" in content

def update_file(filepath):
    """Update a single file if needed"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if has_sampler_2d(content):
        return False  # Already has sampler-2d
    
    # Check if it's a terrain sampler file (has terrain: section)
    if "terrain:" not in content:
        return False  # Not a terrain file
    
    # Check if it has carving instead of terrain sampler
    if "carving:" in content and "terrain:" in content:
        # Check if terrain has a sampler
        terrain_match = re.search(r'terrain:\s*\n(.*?)(?=\n[a-z]|\Z)', content, re.DOTALL)
        if terrain_match and "sampler:" not in terrain_match.group(1):
            return False  # Carving-only terrain
    
    # Append sampler-2d block
    content = content.rstrip() + SAMPLER_2D_BLOCK + "\n"
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

def main():
    base_path = Path("c:\\Projects\\ORIGEN2\\biomes")
    
    updated_count = 0
    skipped_count = 0
    
    # Find all eq_ files
    for filepath in base_path.rglob("eq_*.yml"):
        if update_file(str(filepath)):
            print(f"Updated: {filepath.relative_to(base_path)}")
            updated_count += 1
        else:
            skipped_count += 1
    
    print(f"\nTotal updated: {updated_count}")
    print(f"Total skipped: {skipped_count}")

if __name__ == "__main__":
    main()
