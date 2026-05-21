with open('api_server.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Lignes à supprimer complètement
to_remove = ['import copy\n', 'import uuid\n', 'from unittest import case\n']

# Pour les doublons, on garde la première occurrence
seen = {}
duplicates = ['from typing import Optional, List, Dict, Tuple\n', 
              'from datetime import datetime\n', 
              'import asyncio\n']

new_lines = []
for line in lines:
    # Supprimer les lignes inutiles
    if line in to_remove:
        continue
    
    # Gérer les doublons
    if line in duplicates:
        if line not in seen:
            seen[line] = True
            new_lines.append(line)
        continue
    
    new_lines.append(line)

with open('api_server.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Nettoyage terminé')
