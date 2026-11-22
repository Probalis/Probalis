# Probalis · La science du pari

PWA d'analyse de paris sportifs. Football d'abord, en français et en anglais.

## Démarrer (Windows)

L'environnement Python est dans `.venv` (Python 3.14). Pour le recréer :

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Commandes

```powershell
.\.venv\Scripts\python.exe -m probalis build
```
Télécharge les données, calcule les analyses d'aujourd'hui jusqu'à J+8 (en tenant compte des matchs déjà
joués dans la journée) et génère le site dans `public/`.
Le tout premier lancement dure environ 30 minutes : TheSportsDB n'accepte qu'une dizaine d'appels par minute,
et il faut récupérer l'historique des coupes d'Europe et du football féminin. Ensuite, tout est en cache et un
lancement prend quelques minutes.

```powershell
.\.venv\Scripts\python.exe -m probalis serve
```
Aperçu local sur http://localhost:8000.

```powershell
.\.venv\Scripts\python.exe -m probalis backtest --season 2526
```
Test de fiabilité sur une saison passée (voir `docs/05-fiabilite.md`).

```powershell
.\.venv\Scripts\python.exe -m probalis.football.backtest_linked
.\.venv\Scripts\python.exe -m probalis.football.backtest_linked --women
```
Test de fiabilité des coupes d'Europe, puis du football féminin.

```powershell
.\.venv\Scripts\python.exe -m probalis.football.tendance
```
Vérifie si les premiers matchs d'une journée annoncent les suivants (réponse : non, voir `docs/05-fiabilite.md`).

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
Tests automatiques.

Si la console affiche des accents cassés, lance d'abord `$env:PYTHONIOENCODING = "utf-8"`.

## Mise à jour automatique

`.github/workflows/build.yml` relance l'analyse puis met le site en ligne sur Cloudflare Pages. Il est lancé par
un minuteur Cloudflare (`cloudflare/horloge/`), car l'horloge de GitHub lançait très mal les calculs : du lundi au
vendredi à 0 h 05, 6 h 05, 12 h 05, 18 h 05, 21 h 05 et 23 h 05, le week-end toutes les heures (heure du Cameroun).
Mise en route et coûts : `docs/03-sources-gratuites.md`, parties 4 et 5, et `cloudflare/horloge/README.md`.

## Organisation

| Dossier | Contenu |
|---|---|
| `probalis/core` | Calculs communs : matrice des scores, tous les marchés, cotes justes, marge, combinés |
| `probalis/football` | Données, modèle Dixon-Coles, modèle « relié » (coupes d'Europe, féminin), matchs à venir et logos, chaîne complète, tests de fiabilité |
| `probalis/site` | Générateur du site PWA (gabarits, styles, textes FR/EN) |
| `docs` | Catalogue des marchés, budget, sources gratuites, identité visuelle, fiabilité |
| `brand` | Logo et icônes |
| `data/cache` | Données téléchargées (non versionnées) |
| `public` | Site généré (non versionné) |
| `.github/workflows` | Relance automatique des analyses et mise en ligne du site |

## Sources de données (gratuites)

- football-data.co.uk : résultats, statistiques et cotes de 10 championnats, plus les résultats de 11 autres
  championnats européens (pour situer les clubs des coupes d'Europe).
- TheSportsDB (clé publique) : calendrier et logos des équipes ; résultats des coupes d'Europe et des
  championnats féminins.
