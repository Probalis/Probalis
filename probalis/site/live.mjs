/* Relais du match en direct (ESPN) : Cloudflare Pages Function, copiée par probalis/site/build.py dans
   functions/live/[[path]].js (ne pas modifier le fichier copié : il est refait à chaque construction).

   Les téléphones des membres ne parlent jamais à ESPN : ils demandent à notre site, qui demande à ESPN, garde la
   réponse quelques secondes et n'en renvoie que l'utile (quelques Ko au lieu de 420 Ko pour un match).
   - /live/sb/<championnat>/<AAAAMMJJ>.json : les matchs d'un jour (état, minute, score) pour la liste des matchs ;
   - /live/ev/<championnat>/<n° du match>.json : un match (état, minute, score, temps forts, statistiques des deux
     équipes, compositions) pour l'onglet « Match » de la fiche.
   Seuls nos championnats sont acceptés (SLUGS, mêmes noms que probalis/football/espn.py, vérifié par les tests).
   Tests : node probalis/site/live.test.mjs (lancés aussi par tests/test_espn.py). */

export const SLUGS = [
  'eng.1', 'esp.1', 'ita.1', 'ger.1', 'fra.1', 'eng.2', 'ned.1', 'por.1', 'bel.1', 'tur.1', 'fra.2', 'esp.2',
  'eng.3', 'eng.4', 'eng.5', 'ksa.1', 'uefa.champions', 'uefa.europa', 'uefa.europa.conf', 'uefa.wchampions',
  'eng.w.1', 'fra.w.1', 'esp.w.1'
];
const API = 'https://site.api.espn.com/apis/site/v2/sports/soccer/';
const PATH = /^\/live\/(sb|ev)\/([a-z0-9.]{3,24})\/(\d{5,12})\.json$/;
// Nom simple et honnête : ESPN refuse les noms « Mozilla … Bot », pas celui-ci.
const UA = 'Probalis/0.1';

// Statistiques montrées, dans l'ordre (noms ESPN). Les libellés sont traduits par l'appli.
export const STATS = ['possessionPct', 'totalShots', 'shotsOnTarget', 'wonCorners', 'foulsCommitted', 'yellowCards',
  'redCards', 'offsides', 'saves', 'totalPasses', 'accuratePasses', 'passPct'];

// Durée de garde d'une réponse, en secondes : courte pendant le match, longue une fois fini.
export const ttl = (states) => (states.includes('in') ? 30 : states.length && states.every((s) => s === 'post') ? 3600 : 120);

export const route = (pathname) => {
  const m = PATH.exec(pathname);
  if (!m || !SLUGS.includes(m[2])) return null;
  if (m[1] === 'sb' && !/^\d{8}$/.test(m[3])) return null;
  return {
    kind: m[1], slug: m[2], id: m[3],
    url: API + m[2] + (m[1] === 'sb' ? '/scoreboard?dates=' + m[3] : '/summary?event=' + m[3])
  };
};

const int = (v) => {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : null;
};

const status = (st) => {
  const t = (st && st.type) || {};
  return { s: t.state || null, sn: t.name || null, cl: (st && st.displayClock) || null, d: t.shortDetail || null };
};

// Liste des matchs d'un jour : { t, ev: { n° : { s, sn, cl, d, sc } } }
export const compactScoreboard = (data, now = Date.now()) => {
  const ev = {};
  for (const e of (data && data.events) || []) {
    const comp = (e.competitions || [])[0] || {};
    const side = {};
    for (const c of comp.competitors || []) side[c.homeAway] = c;
    const st = status(e.status || comp.status);
    ev[String(e.id)] = { ...st, sc: side.home && side.away ? [int(side.home.score), int(side.away.score)] : null };
  }
  return { t: now, ev };
};

const who = (k, i) => {
  const p = (k.participants || [])[i];
  return (p && p.athlete && p.athlete.displayName) || null;
};

// Temps forts : buts (b), cartons jaunes (j), rouges (r), rouges sur deuxième jaune (jr), remplacements (c).
const events = (data, sideOf) => {
  const out = [];
  const booked = new Set();
  for (const k of data.keyEvents || []) {
    const type = ((k.type && k.type.type) || '').toLowerCase();
    const text = ((k.type && k.type.text) || '') + ' ' + (k.text || '');
    const side = sideOf[String((k.team && k.team.id) || '')] || null;
    const base = { m: (k.clock && k.clock.displayValue) || '', p: (k.period && k.period.number) || null, e: side };
    if (k.scoringPlay || type.startsWith('goal') || type.includes('penalty---scored') || type.includes('own-goal')) {
      const own = type.includes('own') || /own goal/i.test(text);
      const pen = type.includes('penalty') || /penalty/i.test(k.type && k.type.text || '');
      out.push({ ...base, k: 'b', n: [who(k, 0), own ? null : who(k, 1)].filter(Boolean), x: own ? 'csc' : pen ? 'pen' : '' });
    } else if (type === 'yellow-card') {
      booked.add(side + '|' + who(k, 0));
      out.push({ ...base, k: 'j', n: [who(k, 0)].filter(Boolean) });
    } else if (type === 'red-card') {
      out.push({ ...base, k: booked.has(side + '|' + who(k, 0)) ? 'jr' : 'r', n: [who(k, 0)].filter(Boolean) });
    } else if (type === 'substitution') {
      out.push({ ...base, k: 'c', n: [who(k, 0), who(k, 1)] });  // [entre, sort]
    }
  }
  return out;
};

const stats = (teams) => {
  const val = (t, name) => {
    const s = ((t && t.statistics) || []).find((x) => x.name === name);
    return s ? s.displayValue : null;
  };
  const out = [];
  for (const name of STATS) {
    const h = val(teams.home, name);
    const a = val(teams.away, name);
    if (h != null && a != null) out.push([name, h, a]);
  }
  // Suivi incomplet (petits championnats) : possession et tirs à zéro des deux côtés, rien de fiable à montrer
  const poss = out.find((s) => s[0] === 'possessionPct');
  return poss && parseFloat(poss[1]) > 0 ? out : [];
};

const lineup = (r) => {
  const players = (r.roster || []).map((p) => ({
    j: p.jersey || '', n: (p.athlete && p.athlete.displayName) || '', po: (p.position && p.position.abbreviation) || '',
    xi: !!p.starter, in: !!p.subbedIn, out: !!p.subbedOut, fp: int(p.formationPlace)
  }));
  const xi = players.filter((p) => p.xi).sort((a, b) => (a.fp ?? 99) - (b.fp ?? 99));
  const sub = players.filter((p) => !p.xi);
  const slim = (p) => [p.j, p.n, p.po, p.out ? 1 : p.in ? 2 : 0];
  return { f: r.formation || '', xi: xi.map(slim), sub: sub.map(slim) };
};

// Un match : { t, s, sn, cl, d, sc, ev, st, lu }
export const compactSummary = (data, now = Date.now()) => {
  const comp = (((data && data.header) || {}).competitions || [])[0] || {};
  const side = {};
  const sideOf = {};
  for (const c of comp.competitors || []) {
    side[c.homeAway] = c;
    sideOf[String(c.id || (c.team && c.team.id) || '')] = c.homeAway === 'home' ? 'h' : 'a';
  }
  const teams = {};
  for (const t of ((data && data.boxscore) || {}).teams || []) teams[t.homeAway] = t;
  const lu = {};
  for (const r of (data && data.rosters) || []) {
    if ((r.roster || []).length) lu[r.homeAway === 'home' ? 'h' : 'a'] = lineup(r);
  }
  return {
    t: now,
    ...status(comp.status),
    sc: side.home && side.away ? [int(side.home.score), int(side.away.score)] : null,
    ev: events(data || {}, sideOf),
    st: stats(teams),
    lu: lu.h && lu.a ? lu : null
  };
};

const reply = (body, status, maxAge) => new Response(body, {
  status,
  headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': maxAge ? `public, max-age=${maxAge}` : 'no-store',
    'X-Robots-Tag': 'noindex',
    'X-Content-Type-Options': 'nosniff'
  }
});

export async function onRequest(ctx) {
  const { request } = ctx;
  if (request.method !== 'GET' && request.method !== 'HEAD') return reply('{}', 405, 0);
  const url = new URL(request.url);
  const r = route(url.pathname);
  if (!r) return reply('{}', 404, 0);
  const cache = typeof caches !== 'undefined' ? caches.default : null;
  const key = new Request(url.origin + url.pathname, { method: 'GET' });
  if (cache) {
    const hit = await cache.match(key);
    if (hit) return hit;
  }
  const keep = async (res) => {
    if (cache) {
      const put = cache.put(key, res.clone());
      if (ctx.waitUntil) ctx.waitUntil(put); else await put;
    }
    return request.method === 'HEAD' ? new Response(null, { status: res.status, headers: res.headers }) : res;
  };
  let data;
  try {
    const res = await fetch(r.url, { headers: { 'User-Agent': UA, Accept: 'application/json' } });
    // Match ou jour inconnu d'ESPN : gardé 10 min aussi, pour ne pas lui renvoyer la même demande à chaque visite
    if (res.status === 404 || res.status === 400) return keep(reply('{}', 404, 600));
    if (!res.ok) return reply('{}', 502, 0);
    data = await res.json();
  } catch (e) {
    return reply('{}', 502, 0);
  }
  const out = r.kind === 'sb' ? compactScoreboard(data) : compactSummary(data);
  const states = r.kind === 'sb' ? Object.values(out.ev).map((e) => e.s) : [out.s];
  return keep(reply(JSON.stringify(out), 200, ttl(states)));
}
