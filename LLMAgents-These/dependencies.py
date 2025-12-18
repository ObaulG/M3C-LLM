from database import Database
from functools import lru_cache

# Configuration de la base de données (à mettre dans un fichier .env)
DATABASE_URL = "postgresql://user:password@localhost/dbname"


@lru_cache  
def get_db():
    return Database(DATABASE_URL)
