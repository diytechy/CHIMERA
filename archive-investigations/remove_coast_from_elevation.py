import yaml
import re

file_path = "C:/Projects/ORIGEN2/biome-distribution/stages/climate/elevation.yml"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find all entries containing "coast"
coast_entries = set()
for match in re.finditer(r'^\s+(\S*coast\S*):', content, re.MULTILINE):
    coast_entries.add(match.group(1))

print("Coast-related entries found:")
for entry in sorted(coast_entries):
    print(f"  - {entry}")

# Remove coast entries from the file
lines = content.split('\n')
new_lines = []
skip_until_outdent = False
current_indent = 0

for i, line in enumerate(lines):
    # Check if line contains a coast entry as a key
    match = re.match(r'^(\s+)(\S*coast\S*):', line)
    if match:
        # Get indent level
        current_indent = len(match.group(1))
        skip_until_outdent = True
        continue
    
    if skip_until_outdent:
        # Check if we've outdented back to same or less indent
        if line.strip():
            line_indent = len(line) - len(line.lstrip())
            if line_indent <= current_indent:
                skip_until_outdent = False
            else:
                continue
        else:
            continue
    
    new_lines.append(line)

# Write back
with open(file_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))

print(f"\nRemoved {len(coast_entries)} coast-related sections from elevation.yml")
