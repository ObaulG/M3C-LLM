with open('api_server.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line == 'import json\n':
        print(f'Trouvé à la ligne {i+1} (indice {i}): {repr(line)}')
        break
