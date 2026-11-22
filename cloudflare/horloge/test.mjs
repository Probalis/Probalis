// Tests de l'horloge des calculs :  node cloudflare/horloge/test.mjs
// (lancés aussi par tests/test_horloge.py, donc à chaque calcul et à chaque envoi sur GitHub)
import assert from "node:assert/strict";
import { workflowsFor, dispatch, tick, localTime } from "./worker.mjs";

// 1. Mêmes heures que l'ancienne horloge de GitHub (lignes « cron » de build.yml jusqu'au 22/11/2026, en UTC).
const CRONS = [
  { hours: [23], days: [0, 1, 2, 3, 4] },                 // 0 h 05 au Cameroun, du lundi au vendredi
  { hours: [5, 11, 17, 20, 22], days: [1, 2, 3, 4, 5] },   // 6 h 05, 12 h 05, 18 h 05, 21 h 05, 23 h 05 en semaine
  { hours: [23], days: [5] },                               // samedi 0 h 05
  { hours: [...Array(24).keys()], days: [6] },              // samedi 1 h 05 → dimanche 0 h 05
  { hours: [...Array(23).keys()], days: [0] },              // dimanche 1 h 05 → 23 h 05
];
const start = Date.UTC(2026, 10, 23, 0, 5); // lundi 23/11/2026 à 0 h 05 UTC
let runs = 0;
for (let h = 0; h < 24 * 7 * 2; h++) {   // deux semaines, heure par heure
  const d = new Date(start + h * 3600 * 1000);
  const expected = CRONS.some((c) => c.hours.includes(d.getUTCHours()) && c.days.includes(d.getUTCDay()));
  const got = workflowsFor(d).some((w) => w.file === "build.yml");
  assert.equal(got, expected, `calcul à ${d.toISOString()} : attendu ${expected}`);
  if (got) runs++;
}
assert.equal(runs, 2 * 78, "78 calculs par semaine");

// 2. Heure du Cameroun et e-mails du jour (10 h 05 au Cameroun = 9 h 05 UTC, chaque jour, avec envoi réel).
assert.deepEqual(localTime(new Date("2026-11-22T23:05:00Z")), { day: 1, hour: 0 }); // dimanche 23 h UTC = lundi 0 h
for (let day = 0; day < 7; day++) {
  for (let hour = 0; hour < 24; hour++) {
    const d = new Date(Date.UTC(2026, 10, 22 + day, hour, 5));
    const mails = workflowsFor(d).filter((w) => w.file === "emails.yml");
    assert.equal(mails.length, hour === 9 ? 1 : 0, `e-mails à ${d.toISOString()}`);
    if (mails.length) assert.deepEqual(mails[0].inputs, { dry_run: "false" });
  }
}

// 3. Appel à GitHub : adresse, clé, contenu ; nouvel essai si GitHub a un souci passager ; arrêt si la clé est refusée.
const quiet = () => {};
const fake = (codes) => {
  const calls = [];
  const fetcher = async (url, init) => {
    calls.push({ url, init });
    const c = codes.shift();
    if (c === "coupure") throw new Error("réseau");
    return { status: c };
  };
  return { calls, fetcher };
};
const noSleep = async () => {};

let f = fake([204]);
assert.equal(await dispatch("CLE", { file: "build.yml" }, { fetcher: f.fetcher, sleep: noSleep, log: quiet }), true);
assert.equal(f.calls.length, 1);
assert.equal(f.calls[0].url, "https://api.github.com/repos/Probalis/Probalis/actions/workflows/build.yml/dispatches");
assert.equal(f.calls[0].init.method, "POST");
assert.equal(f.calls[0].init.headers.Authorization, "Bearer CLE");
assert.deepEqual(JSON.parse(f.calls[0].init.body), { ref: "main" });

f = fake([204]);
await dispatch("CLE", { file: "emails.yml", inputs: { dry_run: "false" } }, { fetcher: f.fetcher, sleep: noSleep, log: quiet });
assert.deepEqual(JSON.parse(f.calls[0].init.body), { ref: "main", inputs: { dry_run: "false" } });

f = fake([502, "coupure", 204]);
assert.equal(await dispatch("CLE", { file: "build.yml" }, { fetcher: f.fetcher, sleep: noSleep, log: quiet }), true);
assert.equal(f.calls.length, 3);

f = fake([500, 500, 500, 204]);
assert.equal(await dispatch("CLE", { file: "build.yml" }, { fetcher: f.fetcher, sleep: noSleep, log: quiet }), false);
assert.equal(f.calls.length, 3, "trois essais au plus");

for (const code of [401, 403, 404, 422]) {
  f = fake([code, 204]);
  assert.equal(await dispatch("CLE", { file: "build.yml" }, { fetcher: f.fetcher, sleep: noSleep, log: quiet }), false);
  assert.equal(f.calls.length, 1, `pas de nouvel essai après le code ${code}`);
}

// 4. Passage du minuteur : rien hors des heures prévues, rien sans clé, sinon un appel par programme.
f = fake([]);
assert.deepEqual(await tick(new Date("2026-11-24T08:05:00Z"), { GITHUB_TOKEN: "CLE" }, { fetcher: f.fetcher, log: quiet }), []);
assert.equal(f.calls.length, 0, "mardi 9 h 05 au Cameroun : rien");
f = fake([]);
const sans = await tick(new Date("2026-11-24T05:05:00Z"), {}, { fetcher: f.fetcher, log: quiet });
assert.deepEqual(sans, [{ file: "build.yml", ok: false }]);
assert.equal(f.calls.length, 0, "sans clé : aucun appel");
f = fake([204, 204]);
const both = await tick(new Date("2026-11-28T09:05:00Z"), { GITHUB_TOKEN: "CLE" }, { fetcher: f.fetcher, sleep: noSleep, log: quiet });
assert.deepEqual(both, [{ file: "build.yml", ok: true }, { file: "emails.yml", ok: true }], "samedi 10 h 05 : calcul et e-mails");

console.log("horloge : tous les tests réussis");
