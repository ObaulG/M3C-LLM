with open('api_server.py', 'r') as f:
    lines = f.readlines()
print(f'Total lines: {len(lines)}')
for i in range(1650, min(1660, len(lines))):
    print(f'{i}: {repr(lines[i])}')
