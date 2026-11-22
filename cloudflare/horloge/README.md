# Horloge des calculs (Cloudflare)

Minuteur gratuit de Cloudflare (Workers, « Cron Trigger ») qui lance les calculs de Probalis sur GitHub à l'heure.

**Pourquoi :** l'horloge de GitHub (`schedule`) lance très mal les programmes à heure fixe sur ce dépôt. Le 22/11/2026, on a compté 1 calcul sur 9 prévus, et les e-mails du jour sont partis avec 7 à 8 heures de retard. Les lancements à la main, avec le bouton « Run workflow », démarrent tout de suite : le minuteur appuie sur ce bouton à notre place.

## Heures (heure du Cameroun, UTC+1)

| Programme | Quand |
|---|---|
| Calcul et mise en ligne (`build.yml`) | Du lundi au vendredi à 0 h 05, 6 h 05, 12 h 05, 18 h 05, 21 h 05 et 23 h 05. Le samedi et le dimanche, toutes les heures. |
| E-mails du jour (`emails.yml`) | Tous les jours à 10 h 05. |

Le minuteur tourne toutes les heures à la 5e minute, et `worker.mjs` choisit à quelles heures il lance un programme. Pour changer les heures, il faut modifier `WEEKDAY_HOURS` ou `EMAIL_HOUR` dans `worker.mjs`, mettre à jour les tests (`test.mjs`), puis remettre le minuteur en ligne.

## Fichiers

- `worker.mjs` : le minuteur.
- `test.mjs` : ses tests, à lancer avec `node cloudflare/horloge/test.mjs`. Ils sont aussi lancés par `tests/test_horloge.py`.
- `wrangler.toml` : son nom (`probalis-horloge`) et le passage toutes les heures. Il ne contient aucun identifiant de compte.

## Clé GitHub (secret `GITHUB_TOKEN`)

La clé est posée par le porteur du projet lui-même, jamais dans le code ni dans une conversation.

1. **Créer la clé.** Sur GitHub, aller dans Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token, puis remplir :
   - Token name : `Probalis horloge` ;
   - Resource owner : **Probalis** ;
   - Expiration : la plus longue proposée (noter la date dans le cahier des charges) ;
   - Repository access : Only select repositories → `Probalis/Probalis` ;
   - Permissions → Repository permissions → **Actions : Read and write**. Rien d'autre.
2. **La poser dans Cloudflare.** Dans un terminal, lancer la commande ci-dessous, puis coller la clé et appuyer sur Entrée :

   ```
   npx --yes wrangler@4.165.0 secret put GITHUB_TOKEN --name probalis-horloge
   ```

   Autre possibilité, dans le tableau de bord Cloudflare : Workers & Pages → `probalis-horloge` → Settings → Variables and Secrets → Add, type « Secret », nom `GITHUB_TOKEN`.

**Si la clé expire ou est refusée**, plus aucun calcul ne se lance tout seul. On le voit à la date « Mis à jour le » en bas des pages du site. Les journaux de Cloudflare montrent alors le message « refusé par GitHub (code 401 ou 403) ». Pour réparer, il faut créer une nouvelle clé et la reposer de la même façon.

## Mise en ligne du minuteur

Le PC doit être connecté à Cloudflare avec le droit de gérer les Workers (`npx --yes wrangler@4.165.0 login`). Ensuite, dans ce dossier :

```
npx --yes wrangler@4.165.0 deploy
```

**Journaux :** tableau de bord Cloudflare → Workers & Pages → `probalis-horloge` → Observability. On y voit « build.yml : lancé » à chaque passage.
