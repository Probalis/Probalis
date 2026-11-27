-- Mise à niveau 4 (27/11/2026) : équipes suivies (favoris), enregistrées dans le compte pour les retrouver sur tous
-- les appareils. Noms d'équipe tels que l'appli les affiche (TheSportsDB). 50 équipes au plus.
alter table public.profiles
  add column if not exists favorite_teams text[] not null default '{}';

alter table public.profiles drop constraint if exists profiles_favorite_teams_check;
alter table public.profiles add constraint profiles_favorite_teams_check
  check (cardinality(favorite_teams) <= 50 and char_length(array_to_string(favorite_teams, '|')) <= 3000);

-- Le membre peut modifier cette colonne de son propre profil (la règle « chacun son profil » existe déjà)
grant update (favorite_teams) on public.profiles to authenticated;
