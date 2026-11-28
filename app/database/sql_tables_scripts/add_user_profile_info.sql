-- Informations de profil collectées à l'inscription et modifiables
-- depuis la page de profil : sexe, tranche d'âge, statut universitaire
-- et objectifs de recherche sur la M3C (liste de cases à cocher).
ALTER TABLE user ADD COLUMN IF NOT EXISTS gender VARCHAR(100);
ALTER TABLE user ADD COLUMN IF NOT EXISTS age_range VARCHAR(50);
ALTER TABLE user ADD COLUMN IF NOT EXISTS academic_status VARCHAR(100);
ALTER TABLE user ADD COLUMN IF NOT EXISTS search_goals TEXT;
