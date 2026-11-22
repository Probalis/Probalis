# Lancement à 0 $ : les sources gratuites

État au 19/11/2026. Les sources marquées « testé » ont été appelées pour de vrai ce jour-là.

---

## 1. Les sources retenues

| Besoin | Source gratuite | Ce qu'on obtient | Limite |
|---|---|---|---|
| Calendrier, résultats, classements, **logos** | **football-data.org** (clé gratuite, inscription par e-mail) | 12 compétitions : Premier League, Championship, Liga, Serie A, Bundesliga, Ligue 1, Eredivisie, Primeira Liga, Brasileirão, Ligue des champions, Euro, Coupe du monde. Chaque équipe a son logo (`crest`). | 10 appels par minute, scores en différé, pas de données joueurs. Testé : sans clé, l'API répond « accès refusé » (normal, il faut la clé gratuite). |
| Historique + statistiques pour les moteurs | **football-data.co.uk** (aucune inscription) | Fichiers CSV par saison : scores (mi-temps et fin), tirs, tirs cadrés, **corners, fautes, cartons, arbitre**, cotes 1X2, plus/moins 2,5 et handicap asiatique (Bet365, Betfair, BetVictor, Betway, Paddy Power, Sky Bet…), cotes d'ouverture et de clôture. | Testé : saison 2026/27 à jour (100 matchs de Premier League au 08/11/2026). Le fichier des matchs à venir n'est mis à jour qu'une ou deux fois par semaine. |
| Logos de secours, couleurs des clubs | **TheSportsDB** (clé publique « 123 ») | Logo, écusson et couleur principale de chaque équipe. Testé : Arsenal → logo et couleur #EF0107. | Très limité en calendrier (1 seul match à venir renvoyé en gratuit). D'après des sites tiers, l'offre gratuite serait réservée à un usage non commercial. |
| Compositions, blessures, stats détaillées | **API-Football**, offre gratuite (inscription) | Tous les championnats du monde, y compris africains, plus les logos. | 100 requêtes par jour, saisons récentes peut-être restreintes (à tester avec la clé). À réserver aux gros matchs. |
| Cotes des coupes d'Europe, **dont 1xBet** | **The Odds API**, offre gratuite (inscription) | 500 crédits par mois. Bookmakers européens (1xBet, Pinnacle, Unibet, Betclic…). **Branché le 22/11/2026** (`probalis/football/oddsapi.py`), clé posée le même jour. | 1 crédit par marché et par appel (2 pour 1X2 + plus/moins), réponse vide gratuite. Réservé aux compétitions sans cotes football-data (voir plus bas). |
| Cotes betPawa | Aucune API | — | L'utilisateur saisit sa cote dans le constructeur de ticket, et l'appli calcule la valeur. |

### Coupes d'Europe et football féminin (ajoutés le 19/11/2026, testé)

| Compétition | Calendrier et résultats | Comment on calcule les chances |
|---|---|---|
| Ligue des champions, Ligue Europa, Ligue Conférence | **TheSportsDB** (clé « 123 ») : tous les tours, phase de ligue (journées 1 à 8), barrages, 8es, quarts, demies, finale et qualifications, sur 3 saisons. | Un **modèle relié** : chaque club a sa force propre + la force moyenne de son pays. Les championnats nationaux (football-data.co.uk : 11 pays dans les fichiers habituels + Autriche, Suisse, Danemark, Norvège, Suède, Pologne, Roumanie, Irlande, Finlande) mesurent les écarts entre clubs d'un même pays ; les matchs européens mesurent l'écart entre pays. |
| Ligue des champions féminine, WSL, Frauen-Bundesliga, Arkema Première Ligue, Liga F, Serie A féminine | **TheSportsDB** : résultats journée par journée sur 2 saisons. | Même modèle relié : un groupe par championnat, la Ligue des champions féminine relie les championnats entre eux. |

- **Cotes : The Odds API** (code prêt et clé posée le 22/11/2026 ; en ligne après le commit du code). football-data.co.uk ne couvre que les championnats nationaux masculins. Avec la clé `PROBALIS_ODDS_API_KEY`, la Ligue des champions, la Ligue Europa, la Ligue Conférence, la Ligue des champions féminine, la Frauen-Bundesliga et la Ligue saoudienne sont **calées sur les cotes** (moyenne d'au moins deux bookmakers, marge retirée, même calage que les grands championnats ; étiquette « Calé sur les cotes »). La WSL et les autres championnats féminins ne sont pas proposés : ils restent au modèle seul (« Modèle statistique seul », confiance plafonnée à « moyenne »), comme tout match sans cotes.
- **Quota gratuit gardé (500 crédits par mois) :** une compétition n'est redemandée que si elle a un match dans les 3 jours, au plus toutes les 12 h (24 h si le match est à plus d'un jour) ; budget par compétition (UCL 90, UEL 80, UECL 80, UWCL 40, Frauen-Bundesliga 60, Ligue saoudienne 80 crédits, soit 430) ; plus aucun appel sous 40 crédits restants ; cotes gardées 30 h au plus. Une semaine de Ligue des champions coûte environ 14 crédits.
- **Conditions de The Odds API (lues le 22/11/2026) :** affichage et calculs dérivés permis, y compris sur un site payant ; revente des cotes brutes interdite. La source est citée sur la page du match et en bas des pages.
- **Sportradar (regardé le 22/11/2026) :** essai gratuit de 30 jours (1 000 requêtes, 1 par seconde, un produit),
  mais réservé à un test interne : interdit de publier ou d'afficher les données. Ensuite, contrat payant sans prix
  public. Pas retenu.
- **Sources écartées :** ClubElo (son service de calendrier est fermé et son API ne répondait plus le 19/11/2026) ; API-Football gratuit (100 appels par jour et, à vérifier avec une clé, saisons en cours peut-être réservées aux offres payantes).
- **Premier lancement plus long** (environ 30 minutes : TheSportsDB bloque au-delà d'une dizaine d'appels par minute) : il faut télécharger toutes les anciennes journées. Elles sont ensuite gardées en cache pour toujours, les lancements suivants ne demandent que les journées en cours.

**Affichage des équipes :** chaque match montre les deux logos, le nom des équipes et la compétition. Si un logo manque, l'appli affiche un **badge avec les initiales du club dans ses couleurs**, donc jamais d'image cassée.

---

## 2. Héberger et faire tourner l'appli à 0 $

| Élément | Solution gratuite | Pourquoi |
|---|---|---|
| Site PWA | **Cloudflare Pages** | Gratuit, rapide en Afrique comme en Europe, et d'après les comparatifs l'usage commercial est autorisé (à confirmer dans les conditions de Cloudflare). On écarte **Vercel Hobby** : réservé à l'usage non commercial, donc incompatible avec la pub et le Premium. |
| Calcul des analyses | **GitHub Actions** (tâches programmées) | Toutes les 2 heures pendant la journée, les moteurs Python récupèrent les données, recalculent les analyses des 8 prochains jours et remettent le site en ligne (voir partie 5). Pas besoin de serveur. |
| Base de données | Aucune au début | Les analyses sont des fichiers statiques. Une base gratuite (Supabase) viendra avec les comptes et le Premium. |
| Textes d'analyse | Générés par des modèles de phrases | Gratuit. L'IA pourra être ajoutée plus tard. |
| Adresse du site | Sous-domaine gratuit `….pages.dev` | Un vrai nom de domaine coûte environ 10 $ par an, en option. |

---

## 3. Ce qu'on accepte en lançant à 0 $

1. **12 compétitions au départ.** Ce sont celles où se placent la majorité des paris. Les autres championnats arriveront avec un budget, ou via le quota gratuit d'API-Football pour quelques matchs.
2. **Analyses avant-match uniquement**, pas de direct.
3. **Cotes rafraîchies environ une fois par jour**, et pas pour tous les bookmakers.
4. **Compositions et blessures** seulement pour les gros matchs (100 requêtes par jour).
5. **Conditions d'utilisation à vérifier avant de gagner de l'argent.** Les offres gratuites de certaines sources sont peut-être réservées à un usage non commercial. Une bêta gratuite ne pose pas de problème. Au moment d'activer la pub ou le Premium, il faudra peut-être passer une source en payant (environ 9 à 19 $ par mois). On le fera à ce moment-là, payé par les premiers revenus.
6. **Les logos appartiennent aux clubs.** Les afficher pour identifier une équipe est la pratique courante des applis de sport, mais ce n'est pas un droit garanti. Le badge à initiales sert de solution de repli.

---

## 4. Comptes gratuits à créer (par le porteur du projet, le moment venu)

1. GitHub : stockage du code et calculs automatiques.
2. Cloudflare : hébergement du site.
3. football-data.org : calendrier et logos.
4. API-Football : compositions et blessures.
5. The Odds API : cotes des coupes d'Europe. Compte gratuit, puis la clé dans `D:\Projets\Probalis-secrets\cotes.env`
   (`PROBALIS_ODDS_API_KEY=…`) et dans le secret GitHub `PROBALIS_ODDS_API_KEY`.

Les clés d'accès ne seront jamais écrites dans le code. Elles seront rangées dans les « secrets » de GitHub.

### Activer la relance automatique (une fois les comptes GitHub et Cloudflare créés)

1. Mettre le projet dans un dépôt GitHub (Claude peut s'en charger une fois le compte créé). Dépôt privé conseillé.
2. Sur Cloudflare : *My Profile → API Tokens → Create Token*, modèle personnalisé avec le droit
   **Account · Cloudflare Pages · Edit**. Noter aussi l'**Account ID** (affiché dans le tableau de bord).
3. Dans le dépôt GitHub : *Settings → Secrets and variables → Actions*, ajouter deux secrets :
   `CLOUDFLARE_API_TOKEN` et `CLOUDFLARE_ACCOUNT_ID`.
4. Onglet *Actions* → « Analyses et site » → *Run workflow*. Ce premier lancement crée le site (adresse en `….pages.dev`)
   et dure environ 30 minutes (tout l'historique est téléchargé). Ensuite, GitHub relance tout seul.

Sans les secrets Cloudflare, les analyses tournent quand même, mais le site n'est pas mis en ligne.

---

## 5. Rythme des analyses (depuis le 19/11/2026)

- **Fenêtre glissante de 8 jours.** Chaque lancement analyse les matchs d'aujourd'hui jusqu'à J+8 : le 19, du 19
  au 27 ; le 20, du 20 au 28, etc. L'appli avance journée par journée dans le calendrier jusqu'à couvrir les 8 jours,
  même quand un championnat joue trois journées en une semaine (fêtes de fin d'année).
- **Rythme des relances (depuis le 22/11/2026, heure du Cameroun = UTC+1)** (fichier `.github/workflows/build.yml`) :
  du lundi au vendredi à 0 h 05, 6 h 05, 12 h 05, 18 h 05, 21 h 05 et 23 h 05 (les deux du soir pour les coupes
  d'Europe de 18 h 45 et 21 h) ; le samedi et le dimanche toutes les heures. GitHub peut décaler un lancement,
  parfois de plus d'une heure.
- **Pendant un match :** le score en direct de TheSportsDB (gratuit, dans les journées) sert à régler tout de suite
  les paris et verdicts déjà joués d'avance (voir `probalis/site/history.py`).
- **À chaque relance :**
  - les matchs déjà commencés ou terminés disparaissent des listes ;
  - les résultats déjà connus, **y compris ceux du jour même**, mettent à jour la force des équipes qui viennent de
    jouer. Les fichiers football-data.co.uk n'étant complétés qu'environ deux fois par semaine, les derniers scores
    sont repris de TheSportsDB (testé : 95 résultats sur 95 identiques au fichier officiel) ;
  - les changements d'horaire et les reports sont pris en compte ;
  - les nouvelles cotes sont reprises dès que football-data.co.uk les publie.
- **Pas de « tendance du jour » :** sur 14 320 matchs, les premiers résultats d'une journée n'annoncent rien pour
  les matchs suivants (voir `docs/05-fiabilite.md`). Un résultat compte seulement pour les deux équipes qui ont joué.
- **Limite des cotes gratuites :** le fichier de cotes de football-data.co.uk n'est mis à jour que le mardi et le
  vendredi. Entre deux, les chances des championnats calés sur les cotes bougent peu. The Odds API (clé gratuite,
  500 crédits par mois) est réservée aux coupes d'Europe et aux autres compétitions sans cotes : ses cotes sont
  relues au plus toutes les 12 h la veille et le jour du match. Suivre aussi les grands championnats en continu
  demanderait une offre payante.
- **Coût : 0 $.** Un lancement mesuré le 19/11/2026 : 3 minutes de calcul (27 appels à TheSportsDB, limité à un
  appel toutes les 6,5 secondes), soit environ 5 minutes avec l'installation et la mise en ligne. Depuis le
  22/11/2026 : 78 lancements par semaine (environ 340 par mois), 1 à 4 minutes chacun avec les données gardées.
  Illimité pour un dépôt public ; en privé, en général sous les 2 000 minutes gratuites. Côté Cloudflare, environ
  340 mises en ligne par mois (limite gratuite : 500).
