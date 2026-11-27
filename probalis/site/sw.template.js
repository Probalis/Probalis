/* Service worker Probalis.
   - L'appli ne marche pas hors connexion : chaque page vient du réseau. Sans Internet, on montre un écran qui
     demande de se reconnecter (et la page se recharge toute seule au retour du réseau).
   - Seuls les fichiers qui ne changent pas d'une page à l'autre (styles, scripts, polices, icônes, logos des
     équipes) sont gardés sur le téléphone, pour que les pages s'ouvrent plus vite.
   - Notifications : affichage des messages envoyés par Probalis et ouverture de la bonne page au toucher. */
const VERSION = '__VERSION__';
const CORE = `probalis-core-${VERSION}`;
const CRESTS = 'probalis-crests';
const PRECACHE = [`/assets/style.css?v=${VERSION}`, `/assets/app.js?v=${VERSION}`, '/manifest.webmanifest',
  '/icons/icone-192.png', '/icons/probalis-icone.svg', '__FONTS__'];
const MAX_CRESTS = 600;

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CORE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  // Les pages enregistrées par les anciennes versions (probalis-pages) sont effacées
  e.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((k) => k !== CORE && k !== CRESTS).map((k) => caches.delete(k))
  )).then(() => self.clients.claim()));
});

const trim = (name, max) => caches.open(name).then((c) => c.keys().then((keys) =>
  Promise.all(keys.slice(0, Math.max(0, keys.length - max)).map((k) => c.delete(k)))));

const OFF = {
  fr: { t: 'Pas de connexion Internet', p: 'Probalis a besoin d’Internet pour afficher les analyses du jour. Vérifie ta connexion (données mobiles ou Wi-Fi), puis réessaie.', b: 'Réessayer', w: 'La page se rechargera toute seule dès que le réseau revient.' },
  en: { t: 'No internet connection', p: 'Probalis needs the internet to show today’s analyses. Check your connection (mobile data or Wi-Fi), then try again.', b: 'Try again', w: 'The page will reload by itself as soon as you’re back online.' }
};

const offlinePage = (lang) => {
  const o = OFF[lang] || OFF.fr;
  return new Response(
    `<!doctype html><html lang="${lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">` +
    `<meta name="robots" content="noindex"><title>Probalis · ${o.t}</title><style>` +
    ':root{--bg:#F3F5F8;--card:#fff;--ink:#0B1F3A;--muted:#5B6B82;--line:#E3E8EF;--green:#16A34A}' +
    '@media (prefers-color-scheme:dark){:root{--bg:#071426;--card:#0E2140;--ink:#EAF0F8;--muted:#A3B1C6;--line:#1C3358;--green:#22C55E}}' +
    '*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;padding:24px 16px;background:var(--bg);color:var(--ink);' +
    'font-family:"Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}' +
    '.c{max-width:420px;width:100%;background:var(--card);border:1px solid var(--line);border-radius:22px;padding:30px 24px;text-align:center}' +
    '.i{width:64px;height:64px;margin:0 auto 16px;border-radius:50%;display:grid;place-items:center;background:rgba(34,197,94,.12);color:var(--green)}' +
    'h1{font-size:1.25rem;margin:0 0 10px}p{margin:0 0 18px;color:var(--muted);line-height:1.55}' +
    'button{font:inherit;font-weight:700;border:0;border-radius:14px;padding:13px 22px;background:var(--green);color:#fff;cursor:pointer;min-height:48px}' +
    'small{display:block;margin-top:14px;color:var(--muted)}</style></head><body><main class="c">' +
    '<div class="i"><svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M3 3l18 18M8.5 16.5a5 5 0 0 1 7 0M5 12.5a10 10 0 0 1 4-2.4M19 12.5a10 10 0 0 0-2.3-1.7M2 8.8a14.5 14.5 0 0 1 4.2-2.6M22 8.8a14.6 14.6 0 0 0-10-3.8M12 20h.01"/></svg></div>' +
    `<h1>${o.t}</h1><p>${o.p}</p><button type="button" onclick="location.reload()">${o.b}</button><small>${o.w}</small>` +
    '<script>addEventListener("online",function(){location.reload()})</script></main></body></html>',
    { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
};

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  if (url.origin !== location.origin) {
    // Logos des équipes : gardés sur le téléphone (ils changent rarement)
    if (req.destination === 'image') {
      e.respondWith(caches.open(CRESTS).then((c) => c.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok || res.type === 'opaque') {
          c.put(req, res.clone());
          e.waitUntil(trim(CRESTS, MAX_CRESTS));
        }
        return res;
      }))));
    }
    return;
  }

  // Nos copies des logos (/logos/…) : le nom change avec l'image, on peut les garder longtemps
  if (url.pathname.startsWith('/logos/')) {
    e.respondWith(caches.open(CRESTS).then((c) => c.match(req).then((hit) => hit || fetch(req).then((res) => {
      if (res.ok) {
        c.put(req, res.clone());
        e.waitUntil(trim(CRESTS, MAX_CRESTS));
      }
      return res;
    }))));
    return;
  }

  // Chiffres protégés et données : toujours demandés au serveur
  if (url.pathname.startsWith('/lk/') || url.pathname.startsWith('/data/') || url.pathname.startsWith('/live/')) return;

  // Pages : seulement depuis le réseau ; sans Internet, l'écran « Pas de connexion »
  if (req.mode === 'navigate' || req.destination === 'document') {
    const lang = url.pathname.split('/')[1] === 'en' || url.pathname.startsWith('/welcome') ? 'en' : 'fr';
    e.respondWith(fetch(req).catch(() => offlinePage(lang)));
    return;
  }
  if (req.headers.get('X-Probalis-Nav') || url.pathname.endsWith('.html') || url.pathname.endsWith('/')) return;

  // Styles, scripts, polices : la version demandée (?v=…) exactement, gardée pour aller plus vite
  e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
    if (res.ok && res.type === 'basic' && url.search) {
      const copy = res.clone();
      e.waitUntil(caches.open(CORE).then((c) => c.put(req, copy)));
    }
    return res;
  })));
});

// ---------- Notifications ----------
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (err) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'Probalis', {
    body: d.body || '',
    icon: '/icons/icone-192.png',
    badge: '/icons/badge-96.png',
    tag: d.tag || 'probalis',
    renotify: !!d.tag,
    lang: d.lang || undefined,
    data: { url: d.url || '/' }
  }));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const target = new URL((e.notification.data && e.notification.data.url) || '/', self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((list) => {
    for (const c of list) if (c.url === target && 'focus' in c) return c.focus();
    for (const c of list) if ('navigate' in c && new URL(c.url).origin === self.location.origin) {
      return c.navigate(target).then((w) => (w ? w.focus() : self.clients.openWindow(target)));
    }
    return self.clients.openWindow(target);
  }));
});
