import os
import yaml
from pathlib import Path

def find_non_constant_sampler_2d(root_dir):
    """Find all sampler-2d entries that are not type CONSTANT"""
    results = []
    
    for root, dirs, files in os.walk(root_dir):
        # Skip certain directories
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'node_modules', '.scripts']]
        
        for file in files:
            if file.endswith('.yml'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = yaml.safe_load(f)
                    
                    if content and isinstance(content, dict):
                        terrain = content.get('terrain', {})
                        if isinstance(terrain, dict):
                            sampler_2d = terrain.get('sampler-2d')
                            if sampler_2d:
                                sampler_type = sampler_2d.get('type') if isinstance(sampler_2d, dict) else None
                                if sampler_type != 'CONSTANT':
                                    results.append({
                                        'file': filepath,
                                        'type': sampler_type,
                                        'has_sampler_2d': True
                                    })
                except Exception as e:
                    pass
    
    return results

if __name__ == '__main__':
    root = r'c:\Projects\ORIGEN2'
    results = find_non_constant_sampler_2d(root)
    
    print(f"Found {len(results)} files with non-CONSTANT sampler-2d:\n")
    for result in sorted(results, key=lambda x: x['file']):
        rel_path = os.path.relpath(result['file'], root)
        print(f"{rel_path}")
        print(f"  Type: {result['type']}\n")
