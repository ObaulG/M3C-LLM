with open('api_server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
prev_empty = False

for line in lines:
    if line.strip() == '':
        # Ligne vide
        if not prev_empty:
            new_lines.append(line)
            prev_empty = True
        # else: on saute cette ligne vide supplémentaire
    else:
        new_lines.append(line)
        prev_empty = False

with open('api_server.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Lignes vides réduites')
