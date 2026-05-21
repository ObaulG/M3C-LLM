with open('api_server.py', 'r') as f:
    lines = f.readlines()

# Supprimer la ligne 'import json\n' à la position 1654
# (indice 1653 car on commence à 0)
if lines[1653] == 'import json\n':
    del lines[1653]
    print('import json supprimé')
else:
    print(f'Ligne 1654 est: {repr(lines[1653])}')

with open('api_server.py', 'w') as f:
    f.writelines(lines)
