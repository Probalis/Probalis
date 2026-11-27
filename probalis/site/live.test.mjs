// Tests du relais du match en direct :  node probalis/site/live.test.mjs
// (lancés aussi par tests/test_espn.py, donc à chaque calcul et à chaque envoi sur GitHub)
// Données : un vrai match ESPN allégé (Hull City 2-0 Brighton, 22/11/2026), dans tests/fixtures/.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { compactScoreboard, compactSummary, onRequest, route, ttl, SLUGS } from './live.mjs';

const FIX = new URL('../../tests/fixtures/', import.meta.url);
const load = (name) => JSON.parse(readFileSync(fileURLToPath(new URL(name, FIX)), 'utf-8'));
const summary = load('espn_summary_hull_brighton.json');
const board = load('espn_scoreboard_eng1_20261122.json');

// 1. Adresses : seulement nos championnats, et des numéros
assert.equal(route('/live/sb/eng.1/20261122.json').url,
  'https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=20261122');
assert.equal(route('/live/ev/uefa.champions/401915380.json').url,
  'https://site.api.espn.com/apis/site/v2/sports/soccer/uefa.champions/summary?event=401915380');
for (const bad of ['/live/sb/usa.1/20261122.json', '/live/ev/eng.1/12ab.json', '/live/sb/eng.1/2026112.json',
  '/live/ev/eng.1/401915380', '/live/ev/../401915380.json', '/live/xx/eng.1/20261122.json', '/lk/fr/free.json']) {
  assert.equal(route(bad), null, bad);
}
assert.equal(SLUGS.length, 23);

// 2. Garde : 30 s pendant le match, 1 h une fois fini, 2 min sinon
assert.equal(ttl(['post', 'in']), 30);
assert.equal(ttl(['post', 'post']), 3600);
assert.equal(ttl(['pre', 'post']), 120);
assert.equal(ttl([]), 120);

// 3. Liste des matchs du jour
const sb = compactScoreboard(board, 1);
assert.deepEqual(Object.keys(sb.ev).length, 2);
const hull = Object.values(sb.ev).find((e) => e.sc && e.sc[0] === 2 && e.sc[1] === 0);
assert.ok(hull, 'Hull 2-0 Brighton');
assert.equal(hull.s, 'post');
assert.equal(hull.d, 'FT');

// 4. Un match : score, état, temps forts, statistiques, compositions
const m = compactSummary(summary, 1);
assert.deepEqual(m.sc, [2, 0]);
assert.equal(m.s, 'post');
assert.equal(m.sn, 'STATUS_FULL_TIME');
const goals = m.ev.filter((e) => e.k === 'b');
assert.equal(goals.length, 2);
assert.ok(goals.every((g) => g.e === 'h' && g.n.length >= 1), 'deux buts de Hull');
assert.equal(m.ev.filter((e) => e.k === 'j').length, 5, 'cinq jaunes');
const red = m.ev.filter((e) => e.k === 'jr');
assert.equal(red.length, 1, 'rouge sur deuxième jaune');
assert.deepEqual([red[0].n[0], red[0].e, red[0].m], ['Costinha', 'a', "89'"]);
const sub = m.ev.find((e) => e.k === 'c');
assert.deepEqual(sub.n, ['Lucas Gourna-Douath', 'Tim Iroegbunam']);  // [entre, sort]
assert.equal(sub.e, 'h');
const st = Object.fromEntries(m.st.map(([k, h, a]) => [k, [h, a]]));
assert.deepEqual(st.possessionPct, ['29.8', '70.2']);
assert.deepEqual(st.wonCorners, ['3', '5']);
assert.ok(m.st[0][0] === 'possessionPct');
assert.equal(m.lu.h.xi.length, 11);
assert.equal(m.lu.a.xi.length, 11);
assert.ok(m.lu.h.f.includes('-'), 'schéma de jeu');
assert.ok(m.lu.h.xi.some((p) => p[1] === 'Tim Iroegbunam' && p[3] === 1), 'sorti');
assert.ok(m.lu.h.sub.some((p) => p[1] === 'Lucas Gourna-Douath' && p[3] === 2), 'entré');
const size = JSON.stringify(m).length;
assert.ok(size < 8000, `réponse légère (${size} octets)`);

// Suivi incomplet (petit championnat) : pas de statistiques montrées
const thin = structuredClone(summary);
for (const t of thin.boxscore.teams) for (const s of t.statistics) s.displayValue = '0';
assert.deepEqual(compactSummary(thin).st, []);

// 5. Le relais : demande à ESPN une seule fois, garde la réponse, refuse le reste
const store = new Map();
globalThis.caches = {
  default: {
    match: async (req) => (store.has(req.url) ? store.get(req.url).clone() : undefined),
    put: async (req, res) => { store.set(req.url, res); }
  }
};
let calls = 0;
let seenUA = null;
globalThis.fetch = async (url, init) => {
  calls++;
  seenUA = init.headers['User-Agent'];
  return new Response(JSON.stringify(url.includes('summary') ? summary : board), { status: 200 });
};
const req = (path, method = 'GET') => ({ request: new Request('https://probalis.example' + path, { method }) });
let res = await onRequest(req('/live/ev/eng.1/401878999.json'));
assert.equal(res.status, 200);
assert.equal(res.headers.get('Cache-Control'), 'public, max-age=3600');
assert.deepEqual((await res.json()).sc, [2, 0]);
res = await onRequest(req('/live/ev/eng.1/401878999.json?x=1'));
assert.equal(res.status, 200);
assert.equal(calls, 1, 'deuxième demande servie par la garde');
assert.equal(seenUA, 'Probalis/0.1');
res = await onRequest(req('/live/sb/eng.1/20261122.json'));
assert.equal(Object.keys((await res.json()).ev).length, 2);
assert.equal((await onRequest(req('/live/sb/usa.1/20261122.json'))).status, 404);
assert.equal((await onRequest(req('/live/ev/eng.1/401878999.json', 'POST'))).status, 405);
globalThis.fetch = async () => { throw new Error('panne'); };
assert.equal((await onRequest(req('/live/ev/eng.1/1234567.json'))).status, 502);
let misses = 0;
globalThis.fetch = async () => { misses++; return new Response('Not found', { status: 404 }); };
assert.equal((await onRequest(req('/live/ev/eng.1/7654321.json'))).status, 404);
assert.equal((await onRequest(req('/live/ev/eng.1/7654321.json'))).status, 404);
assert.equal(misses, 1, 'match inconnu gardé aussi');

console.log('Relais du direct : tous les tests réussis');
