# 06 · Comptes, Premium, paiements et e-mails

Ce guide explique comment passer du **mode démo** (tout est simulé sur le téléphone) au **vrai fonctionnement** :
connexion Google, Premium payant, e-mails. Tu n'as rien à programmer : il faut créer des comptes, copier des clés
au bon endroit, puis lancer quelques commandes (je peux les lancer avec toi).

> Règle d'or : **aucune clé secrète dans le code**. Les clés vont dans les « secrets » de Supabase et de GitHub.
> Seules deux valeurs sont publiques et faites pour être dans le site : l'adresse du projet Supabase et sa clé
> « anon » (ou « publishable »).

---

## 1. Ce qui marche déjà, sans rien configurer

Tant que Supabase n'est pas branché, le site est en **mode démo** (un bandeau le signale sur Mon compte et Premium) :

- connexion simulée (case 18+ obligatoire), page Mon compte complète, préférences, suppression du compte ;
- page Premium : prix selon le pays (détecté automatiquement), paiement simulé, Premium activé sur le téléphone ;
- version gratuite : **avec un compte**, **1 analyse complète par jour**, sur le match choisi (bouton « Voir
  l'analyse de ce match » ; sans compte, le bouton propose de se connecter puis débloque le match au retour),
  avec quelques pubs « maison » pour Premium. Ailleurs, les chiffres sont floutés : pages des autres matchs,
  probabilités de la liste des matchs, paris les plus probables. Le compteur repart chaque jour à minuit (heure
  du téléphone). En vrai mode, le match choisi est gardé dans le profil : il ne change plus de la journée, même
  sur un autre appareil ;
- aperçus des e-mails : ouvre `docs/emails/index.html` dans le navigateur.

## 2. Les comptes à créer et ce qu'ils coûtent

| Service | À quoi il sert | Prix pour démarrer |
|---|---|---|
| **Supabase** (supabase.com) | comptes, connexion Google, base de données, petites fonctions serveur | gratuit (jusqu'à 50 000 utilisateurs actifs par mois) |
| **Google Cloud** (console.cloud.google.com) | le bouton « Continuer avec Google » | gratuit |
| **Nom de domaine** (Cloudflare, Namecheap, OVH…) | obligatoire pour envoyer des e-mails qui n'arrivent pas en spam | environ 10 $ par an |
| **Resend** (resend.com) | envoi des e-mails | gratuit jusqu'à 100 e-mails par jour et 3 000 par mois, puis environ 20 $ par mois |
| **Stripe** (stripe.com) | cartes, Apple Pay, Google Pay dans le monde entier | pas d'abonnement, une commission par paiement |
| **Flutterwave** (flutterwave.com) | mobile money (Orange Money, MTN, Wave, M-Pesa…) et cartes en Afrique | pas d'abonnement, une commission par paiement |

Les commissions changent selon le pays et le moyen de paiement (en général quelques pour cent par paiement) :
regarde la page « Pricing » de Stripe et de Flutterwave pour tes pays.

> ⚠️ **À vérifier avant de lancer les paiements.** Stripe et Flutterwave surveillent les activités liées aux
> paris. Probalis ne prend aucun pari et vend de l'analyse statistique, mais Stripe range les « prévisions
> sportives et cotes » parmi les activités liées au jeu, qui demandent son accord. Explique clairement
> l'activité lors de l'inscription (site d'information et de probabilités, sans mise d'argent, réservé aux
> majeurs) et demande la confirmation écrite au support de Stripe et de Flutterwave avant d'encaisser.

## 3. Supabase (comptes et base de données)

1. Crée un compte sur supabase.com, puis **New project** : nom `probalis`, région proche de tes utilisateurs
   (par exemple *West EU (Paris)* ou *Frankfurt*), un mot de passe de base de données (garde-le pour toi).
2. Ouvre **SQL Editor** → **New query**, colle tout le fichier
   `supabase/migrations/20261119120000_comptes_premium.sql`, puis **Run**. Cela crée les profils, les paiements,
   le journal des e-mails et les règles de sécurité.
3. Ouvre **Project Settings → API** (ou **API Keys**) et note :
   - **Project URL**, par exemple `https://abcd1234.supabase.co` (publique) ;
   - la clé **anon** ou **publishable** (publique, faite pour le site) ;
   - la clé **service_role** ou **secret** (SECRÈTE : seulement pour les fonctions et GitHub).
4. **Authentication → URL Configuration** :
   - *Site URL* : l'adresse du site, par exemple `https://probalis.pages.dev` (ou ton domaine) ;
   - *Redirect URLs* : ajoute `https://probalis.pages.dev/**` (et `http://localhost:8000/**` pour les essais).

Bon à savoir : un projet gratuit inactif pendant une semaine est mis en pause. La tâche quotidienne des e-mails
l'utilise chaque jour, ce qui le garde éveillé.

## 4. Google (bouton « Continuer avec Google »)

1. Sur console.cloud.google.com, crée un projet `Probalis`.
2. **APIs & Services → OAuth consent screen** (ou *Google Auth Platform*) : type *External*, nom « Probalis »,
   e-mail de contact, logo (`brand/`), liens vers les pages `confidentialite.html` et `conditions.html` du site.
   Les seules informations demandées sont `email`, `profile` et `openid`.
3. **Credentials → Create credentials → OAuth client ID** : type *Web application*.
   - *Authorized JavaScript origins* : l'adresse du site.
   - *Authorized redirect URIs* : `https://abcd1234.supabase.co/auth/v1/callback` (ton Project URL + `/auth/v1/callback`).
4. Copie le *Client ID* et le *Client secret* dans Supabase : **Authentication → Providers → Google** → active,
   colle les deux valeurs, **Save**.
5. Publie l'écran de consentement (*Publish app*) pour que tout le monde puisse se connecter.

## 5. Resend (e-mails)

1. Achète un nom de domaine (par exemple `probalis.app`) si tu n'en as pas.
2. Sur resend.com : **Domains → Add domain**, de préférence un sous-domaine comme `mail.probalis.app`. Resend
   affiche 3 ou 4 lignes DNS (SPF, DKIM, MX) à ajouter chez ton fournisseur de domaine. Attends le « Verified ».
3. **API Keys → Create API key** (droit *Sending access*). C'est la clé `RESEND_API_KEY` (SECRÈTE).
4. Choisis l'expéditeur, par exemple `Probalis <alertes@mail.probalis.app>` : c'est `EMAIL_FROM`.

Les e-mails envoyés :

| E-mail | Quand | Qui le reçoit |
|---|---|---|
| Bienvenue | une seule fois, après la première connexion | tout nouveau compte |
| Reçu d'achat | après chaque paiement confirmé | l'acheteur |
| Rappel « ton Premium se termine » | 1 à 3 jours avant la fin du pass | Premium avec le rappel activé (par défaut) |
| Grand choc demain | la veille d'un très grand match (sinon rien) | majeurs ayant activé les alertes |

Chaque alerte contient un lien « Me désinscrire » qui marche sans se connecter, et Gmail ou Outlook proposent
aussi leur bouton « Se désabonner ». Personne ne reçoit deux fois le même e-mail.
Pour changer les textes : `probalis/site/emails/__init__.py`, puis `python -m probalis.site.emails generate`.

## 6. Stripe (cartes, Apple Pay, Google Pay)

> **Pays de l'entreprise.** Stripe n'ouvre des comptes qu'aux entreprises installées dans une cinquantaine de pays
> (liste sur stripe.com/global : Europe, Royaume-Uni, États-Unis, Canada, etc.). En Afrique, seuls la Côte d'Ivoire,
> le Ghana, le Kenya, le Nigeria et l'Afrique du Sud sont acceptés, et ils passent par Paystack (filiale de Stripe,
> autre branchement technique à prévoir). Si ton activité est enregistrée ailleurs (Cameroun, Sénégal…), Stripe direct
> n'est pas possible : on peut alors tout faire passer par Flutterwave (cartes du monde entier + mobile money), en
> changeant seulement `supabase/functions/_shared/prices.json`.
> Stripe interdit les « prévisions sportives avec un gain à la clé » ; Probalis ne fait gagner aucun lot, mais fais
> confirmer l'activité par le support de Stripe avant d'encaisser.

1. Crée le compte sur stripe.com, renseigne l'activité (voir l'avertissement du point 2) et ton compte bancaire.
2. **Settings → Payment methods** : vérifie que *Cards*, *Apple Pay*, *Google Pay* (et *Link*) sont actifs. Stripe
   affiche ensuite automatiquement les bons moyens selon le pays de l'acheteur.
3. **Developers → API keys** : la *Secret key* (`sk_live_…`, ou `sk_test_…` pour les essais) est `STRIPE_SECRET_KEY`.
4. **Developers → Webhooks → Add endpoint** :
   - adresse : `https://abcd1234.supabase.co/functions/v1/payment-webhook?provider=stripe` ;
   - événements : `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
     `checkout.session.async_payment_failed`, `checkout.session.expired` ;
   - le *Signing secret* (`whsec_…`) est `STRIPE_WEBHOOK_SECRET`.

Pays servis par Stripe dans `prices.json` : zone euro, Suisse, Maghreb, Madagascar (en euros), Royaume-Uni, États-Unis,
Canada, RD Congo et Haïti (en dollars), et tous les pays non listés.

## 7. Flutterwave (mobile money et cartes en Afrique)

1. Crée le compte sur flutterwave.com et termine la vérification (documents de l'entreprise ou de la personne).
2. **Settings → API Keys** : la *Secret key* est `FLW_SECRET_KEY`.
3. **Settings → Webhooks** :
   - adresse : `https://abcd1234.supabase.co/functions/v1/payment-webhook?provider=flutterwave` ;
   - invente un *Secret hash* (une longue phrase au hasard) : c'est `FLW_WEBHOOK_HASH`.
4. Vérifie dans le tableau de bord quels moyens sont ouverts pour ton compte (mobile money franc CFA, Ghana,
   Kenya, Ouganda, Tanzanie, Rwanda, Zambie ; cartes ; virement et USSD au Nigeria).

Pays servis par Flutterwave dans `prices.json` : zone franc CFA (XOF et XAF), Nigeria, Ghana, Kenya, Ouganda,
Tanzanie, Rwanda, Zambie et Afrique du Sud. Pour déplacer un pays d'un service à l'autre, change sa devise dans
`supabase/functions/_shared/prices.json`.

## 8. Installer les fonctions Supabase

Il faut Node.js (nodejs.org) pour la commande `npx`. Dans le dossier du projet :

```powershell
npx supabase login
```

```powershell
npx supabase link --project-ref abcd1234
```

Invente un secret de désinscription (une longue phrase au hasard, 40 caractères ou plus) pour `UNSUBSCRIBE_SECRET`,
puis enregistre les secrets des fonctions (remplace chaque valeur) :

```powershell
npx supabase secrets set SITE_URL=https://probalis.pages.dev EMAIL_FROM="Probalis <alertes@mail.probalis.app>" RESEND_API_KEY=re_xxx STRIPE_SECRET_KEY=sk_live_xxx STRIPE_WEBHOOK_SECRET=whsec_xxx FLW_SECRET_KEY=FLWSECK-xxx FLW_WEBHOOK_HASH=xxx UNSUBSCRIBE_SECRET=xxx CONTACT_EMAIL=contact@probalis.app
```

Puis envoie les cinq fonctions (`welcome`, `checkout`, `confirm-payment`, `payment-webhook`, `unsubscribe`) :

```powershell
npx supabase functions deploy --no-verify-jwt
```

(`SUPABASE_URL` et la clé secrète sont fournies automatiquement aux fonctions par Supabase.)
Si tu changes un prix ou un texte d'e-mail, relance cette dernière commande.

## 9. GitHub : brancher le site et la tâche des e-mails

Dans le dépôt GitHub → **Settings → Secrets and variables → Actions**.

**Variables** (onglet *Variables*, valeurs publiques) :

| Nom | Exemple |
|---|---|
| `PROBALIS_SITE_URL` | `https://probalis.pages.dev` |
| `PROBALIS_SUPABASE_URL` | `https://abcd1234.supabase.co` |
| `PROBALIS_SUPABASE_ANON_KEY` | la clé anon / publishable |
| `PROBALIS_CONTACT_EMAIL` | `contact@probalis.app` (affichée dans les pages légales) |
| `PROBALIS_OWNER_NAME` | ton nom ou celui de ta société (pages légales) |
| `EMAIL_DAILY_CAP` | facultatif : 90 par défaut (offre gratuite de Resend : 100 par jour) |

**Secrets** (onglet *Secrets*) : `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (clé secrète), `RESEND_API_KEY`,
`EMAIL_FROM`, `UNSUBSCRIBE_SECRET` (le même que dans Supabase).

Le site lit les variables `PROBALIS_…` au moment de sa construction : la tâche « Analyses et site »
(`.github/workflows/build.yml`) doit les recevoir dans son bloc `env:` :

```yaml
      PROBALIS_SITE_URL: ${{ vars.PROBALIS_SITE_URL }}
      PROBALIS_SUPABASE_URL: ${{ vars.PROBALIS_SUPABASE_URL }}
      PROBALIS_SUPABASE_ANON_KEY: ${{ vars.PROBALIS_SUPABASE_ANON_KEY }}
      PROBALIS_CONTACT_EMAIL: ${{ vars.PROBALIS_CONTACT_EMAIL }}
      PROBALIS_OWNER_NAME: ${{ vars.PROBALIS_OWNER_NAME }}
```

Dès que ces valeurs sont là, le prochain build passe le site du mode démo au vrai mode.

La tâche « E-mails du jour » (`.github/workflows/emails.yml`) tourne chaque jour à 10 h 05 heure du Cameroun (9 h 05 UTC),
lancée par le minuteur Cloudflare `probalis-horloge` (voir `cloudflare/horloge/README.md`), dès que la variable
`PROBALIS_SUPABASE_URL` existe (avant, elle est sautée sans rien coûter). Pour l'essayer :
**Actions → E-mails du jour → Run workflow** (la case « Simulation » est cochée par défaut : rien n'est envoyé,
le journal montre ce qui partirait).

## 10. Tester avant d'ouvrir au public

1. Utilise d'abord les clés de **test** (`sk_test_…` chez Stripe, mode test chez Flutterwave). Carte de test Stripe :
   `4242 4242 4242 4242`, n'importe quelle date future et n'importe quel code.
2. Connecte-toi avec Google sur le site, coche 18+, vérifie l'e-mail de bienvenue.
3. Achète un pass de test depuis la page Premium (choisis la France pour Stripe, le Sénégal ou le Cameroun pour
   Flutterwave) : le Premium doit s'activer et le reçu arriver.
4. Pour recevoir les 4 e-mails d'exemple d'un coup :

   ```powershell
   $env:RESEND_API_KEY="re_xxx"; $env:EMAIL_FROM="Probalis <alertes@mail.probalis.app>"; .venv\Scripts\python.exe -m probalis.site.emails test --to ton.adresse@exemple.com
   ```

5. Remplace ensuite les clés de test par les vraies (`npx supabase secrets set …`).

## 11. Limites de cette première version

- **Le verrou est dans le navigateur.** Les pages du site sont les mêmes pour tout le monde : une personne qui sait
  lire le code d'une page peut voir les chiffres floutés. L'analyse gratuite du jour, elle, est comptée sur le
  compte (impossible de la remettre à zéro en changeant d'appareil). Pour un verrou complet, il faudra servir les
  analyses par une fonction Supabase qui vérifie le compte (étape suivante possible).
- Les pass ne se renouvellent pas tout seuls (choix volontaire : pas d'abonnement caché). Le rappel avant la fin
  invite à reprendre un pass.
- Les remboursements se font à la main depuis le tableau de bord Stripe ou Flutterwave.
- Les pages légales (`confidentialite`, `conditions`, `jeu-responsable`) sont des modèles : complète le nom de
  l'éditeur et l'adresse de contact, et fais-les relire si possible.
