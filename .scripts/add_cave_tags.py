#!/usr/bin/env python3
"""
Add cave tags to YAML files missing them.
"""
import yaml
import tkinter as tk
from tkinter import filedialog
from pathlib import Path

def select_folder():
    root = tk.Tk()
    root.withdraw()
    return filedialog.askdirectory(title="Select folder containing YAML files")

def add_cave_tags(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        data = yaml.safe_load(content)
        if not isinstance(data, dict):
            return False
        
        required_tags = ['LAND_CAVES', 'SPECIAL_CAVES']
        
        # Check filename and ID for mountain/plateau variants
        filename = file_path.stem.lower()
        file_id = str(data.get('id', '')).lower()
        text_to_check = f"{filename} {file_id}"
        
        if any(word in text_to_check for word in ['mountain', 'plateau', 'peak', 'ridge', 'cliff', 'mesa']):
            required_tags.append('DEEP_DARK')
        
        if any(word in text_to_check for word in ['forest', 'wood', 'tree', 'grove', 'jungle']):
            required_tags.append('DEEP_DARK_GROVE')
        
        existing_tags = data.get('tags', [])
        missing_tags = [tag for tag in required_tags if tag not in existing_tags]
        
        if not missing_tags:
            return False
        
        data['tags'] = existing_tags + missing_tags
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        
        return True
    except:
        return False

def main():
    folder = select_folder()
    if not folder:
        return
    
    folder_path = Path(folder)
    modified_count = 0
    
    for yml_file in folder_path.rglob('*.yml'):
        if add_cave_tags(yml_file):
            print(f"Added tags to: {yml_file}")
            modified_count += 1
    
    print(f"\nModified {modified_count} files")

if __name__ == "__main__":
    main()