with open('api_server.py', 'r') as f:
    lines = f.readlines()

# Supprimer la ligne 'import json\n' à l'indice 1654 (ligne 1655)
if lines[1654] == 'import json\n':
    del lines[1654]
    print('import json à la ligne 1655 supprimé')
else:
    print(f'Ligne 1655 est: {repr(lines[1654])}')

with open('api_server.py', 'w') as f:
    f.writelines(lines)
