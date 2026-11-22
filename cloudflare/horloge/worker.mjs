// Probalis : horloge des calculs, sur Cloudflare (Workers, offre gratuite).
//
// Pourquoi : l'horloge de GitHub (« schedule ») lance très mal les calculs à heure fixe sur ce dépôt (constaté le
// 22/11/2026 : 1 calcul sur 9 prévus, et les e-mails du jour avec 7 à 8 heures de retard). Les lancements « à la main »
// (bouton « Run workflow »), eux, démarrent tout de suite. Ce minuteur Cloudflare tourne toutes les heures à la 5e
// minute et appuie sur ce bouton à notre place, aux heures voulues par le porteur du projet (heure du Cameroun, UTC+1,
// sans heure d'été) :
//   - calcul et mise en ligne (build.yml) : du lundi au vendredi à 0 h 05, 6 h 05, 12 h 05, 18 h 05, 21 h 05 et 23 h 05 ;
//     le samedi et le dimanche, toutes les heures ;
//   - e-mails du jour (emails.yml) : tous les jours à 10 h 05.
//
// Secret : GITHUB_TOKEN, une clé GitHub limitée au dépôt Probalis/Probalis avec le seul droit « Actions : lecture et
// écriture ». Le porteur du projet la pose lui-même dans Cloudflare ; elle n'est jamais dans le code.
// Mise en ligne et réglages : voir README.md dans ce dossier.

export const REPO = "Probalis/Probalis";
export const OFFSET_H = 1;                              // heure du Cameroun = UTC + 1
export const WEEKDAY_HOURS = [0, 6, 12, 18, 21, 23];    // heures du calcul en semaine (heure du Cameroun)
export const EMAIL_HOUR = 10;                           // e-mails du jour à 10 h 05 (heure du Cameroun)

/** Jour (0 = dimanche … 6 = samedi) et heure au Cameroun pour un instant donné. */
export function localTime(date) {
  const d = new Date(date.getTime() + OFFSET_H * 3600 * 1000);
  return { day: d.getUTCDay(), hour: d.getUTCHours() };
}

/** Programmes GitHub à lancer à cet instant (liste vide en dehors des heures prévues). */
export function workflowsFor(date) {
  const { day, hour } = localTime(date);
  const out = [];
  const weekend = day === 0 || day === 6;
  if (weekend || WEEKDAY_HOURS.includes(hour)) out.push({ file: "build.yml" });
  if (hour === EMAIL_HOUR) out.push({ file: "emails.yml", inputs: { dry_run: "false" } });
  return out;
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

/** Appuie sur « Run workflow » pour un programme. Réessaie deux fois si GitHub a un souci passager. */
export async function dispatch(token, wf, { fetcher = fetch, sleep = wait, log = console.log } = {}) {
  const url = `https://api.github.com/repos/${REPO}/actions/workflows/${wf.file}/dispatches`;
  const body = { ref: "main" };
  if (wf.inputs) body.inputs = wf.inputs;
  for (let attempt = 1; attempt <= 3; attempt++) {
    let status = 0;
    try {
      const r = await fetcher(url, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
          "User-Agent": "probalis-horloge",
        },
        body: JSON.stringify(body),
      });
      status = r.status;
    } catch (e) {
      log(`${wf.file} : GitHub injoignable (${e}), essai ${attempt}/3`);
    }
    if (status === 204) {
      log(`${wf.file} : lancé`);
      return true;
    }
    if (status) log(`${wf.file} : refusé par GitHub (code ${status}), essai ${attempt}/3`);
    // Clé absente, expirée, sans le bon droit, ou programme introuvable : réessayer ne servirait à rien.
    if ([401, 403, 404, 422].includes(status)) {
      log("Vérifier la clé GITHUB_TOKEN (expirée ? droit « Actions : lecture et écriture » sur Probalis/Probalis ?)");
      return false;
    }
    if (attempt < 3) await sleep(10000 * attempt);
  }
  return false;
}

/** Ce que fait le minuteur à chaque passage (toutes les heures à la 5e minute, heure UTC). */
export async function tick(date, env, deps = {}) {
  const wfs = workflowsFor(date);
  const log = deps.log || console.log;
  if (!wfs.length) return [];
  if (!env.GITHUB_TOKEN) {
    log("Clé GITHUB_TOKEN absente : rien n'est lancé.");
    return wfs.map((wf) => ({ file: wf.file, ok: false }));
  }
  const out = [];
  for (const wf of wfs) out.push({ file: wf.file, ok: await dispatch(env.GITHUB_TOKEN, wf, deps) });
  return out;
}

export default {
  async scheduled(event, env) {
    const results = await tick(new Date(event.scheduledTime), env);
    // Un échec apparaît en rouge dans le tableau de bord de Cloudflare (Workers → probalis-horloge → journaux).
    if (results.some((r) => !r.ok)) throw new Error("Lancement refusé : " + results.filter((r) => !r.ok).map((r) => r.file).join(", "));
  },
};
