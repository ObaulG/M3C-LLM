with open('api_server.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'import json' in line:
        print(f'Ligne {i+1}: {repr(line)}')
