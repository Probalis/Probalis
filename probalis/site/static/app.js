(function () {
  'use strict';
  var doc = document;
  var win = window;
  var root = doc.documentElement;
  var lang = root.lang || 'fr';
  var T = {};
  var CFG = {};
  try { T = JSON.parse(doc.getElementById('pb-i18n').textContent); } catch (e) {}
  try { CFG = JSON.parse(doc.getElementById('pb-config').textContent); } catch (e) {}
  var $$ = function (sel, el) { return Array.prototype.slice.call((el || doc).querySelectorAll(sel)); };
  var fmt = function (s, o) { return String(s || '').replace(/\{(\w+)\}/g, function (_, k) { return o[k]; }); };
  var cap = function (s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; };
  var noop = function () {};
  var store = function (area) {
    return {
      get: function (k) { try { return win[area].getItem(k); } catch (e) { return null; } },
      set: function (k, v) { try { win[area].setItem(k, v); } catch (e) {} },
      del: function (k) { try { win[area].removeItem(k); } catch (e) {} }
    };
  };
  var local = store('localStorage');
  var session = store('sessionStorage');
  var reduced = win.matchMedia ? win.matchMedia('(prefers-reduced-motion: reduce)') : { matches: false };
  var loc = lang === 'fr' ? 'fr-FR' : 'en-GB';
  var F = {
    time: new Intl.DateTimeFormat(loc, { hour: '2-digit', minute: '2-digit' }),
    short: new Intl.DateTimeFormat(loc, { weekday: 'short', day: 'numeric' }),
    med: new Intl.DateTimeFormat(loc, { weekday: 'short', day: 'numeric', month: 'short' }),
    long: new Intl.DateTimeFormat(loc, { weekday: 'long', day: 'numeric', month: 'long' }),
    wd: new Intl.DateTimeFormat(loc, { weekday: 'short' }),
    dt: new Intl.DateTimeFormat(loc, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }),
    date: new Intl.DateTimeFormat(loc, { day: 'numeric', month: 'long', year: 'numeric' })
  };

  // ---------- Petits messages ----------
  var toast = function (msg) {
    var el = doc.createElement('div');
    el.className = 'toast';
    el.setAttribute('role', 'status');
    el.textContent = msg;
    doc.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 2600);
  };
  var live = doc.createElement('div');
  live.className = 'sr-only';
  live.setAttribute('aria-live', 'polite');
  doc.body.appendChild(live);

  // ---------- Thème clair / sombre (mémorisé sur l'appareil) ----------
  var media = win.matchMedia ? win.matchMedia('(prefers-color-scheme: dark)') : null;
  var isDark = function () { return root.dataset.theme ? root.dataset.theme === 'dark' : !!(media && media.matches); };
  var syncThemeColor = function () {
    var c = isDark() ? '#071426' : '#F3F5F8';
    $$('meta[name="theme-color"]').forEach(function (m) { m.setAttribute('content', c); });
  };
  if (root.dataset.theme) syncThemeColor();
  doc.addEventListener('click', function (e) {
    if (!e.target.closest('.theme')) return;
    root.dataset.theme = isDark() ? 'light' : 'dark';
    local.set('theme', root.dataset.theme);
    syncThemeColor();
  });

  // ---------- Barre de progression (comme YouTube) ----------
  // Elle suit le téléchargement réel de la page quand le serveur annonce sa taille, sinon elle avance
  // doucement à chaque morceau reçu. Elle ne recule jamais.
  var progress = (function () {
    var el, bar, val = 0, timer, hideT;
    var ensure = function () {
      if (el) return;
      el = doc.createElement('div');
      el.className = 'pb-progress';
      el.setAttribute('aria-hidden', 'true');
      bar = doc.createElement('i');
      el.appendChild(bar);
      doc.body.appendChild(el);
    };
    var set = function (v) {
      val = Math.max(val, Math.min(v, 0.994));
      bar.style.width = (val * 100).toFixed(1) + '%';
    };
    return {
      start: function () {
        ensure();
        clearTimeout(hideT);
        clearInterval(timer);
        val = 0;
        el.className = 'pb-progress on';
        bar.style.transition = 'none';
        bar.style.width = '0';
        void bar.offsetWidth;
        bar.style.transition = '';
        set(0.08);
        timer = setInterval(function () { set(val + (0.82 - val) * 0.045); }, 260);
      },
      data: function (ratio) { if (!el) return; if (ratio == null) set(val + (0.9 - val) * 0.12); else set(0.1 + 0.85 * Math.min(ratio, 1)); },
      done: function (failed) {
        if (!el) return;
        clearInterval(timer);
        val = 1;
        bar.style.width = '100%';
        if (failed) el.className = 'pb-progress on fail';
        hideT = setTimeout(function () { el.className = 'pb-progress'; }, failed ? 600 : 260);
      }
    };
  })();

  // ---------- Connexion lente ou coupée ----------
  var conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  var slowNet = function () { return !!conn && (!!conn.saveData || /(^|-)2g$/.test(conn.effectiveType || '')); };
  var goodNet = function () {
    if (root.classList.contains('lite') || (navigator.onLine === false)) return false;
    return !conn || (!conn.saveData && (!conn.effectiveType || conn.effectiveType === '4g'));
  };
  var netbar = (function () {
    var el, txt, hideT;
    var icons = {
      slow: '<svg class="ic" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M5 19v-3M10 19v-6M15 19V9" /><path d="M20 19V5" opacity=".35"/></svg>',
      offline: '<svg class="ic" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" aria-hidden="true"><path d="M3 3l18 18M8.5 16.5a5 5 0 0 1 7 0M5 12.5a10 10 0 0 1 4-2.4M19 12.5a10 10 0 0 0-2.3-1.7M2 8.8a14.5 14.5 0 0 1 4.2-2.6M22 8.8a14.6 14.6 0 0 0-10-3.8M12 20h.01"/></svg>',
      ok: '<svg class="ic" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 5 5 9-10"/></svg>'
    };
    var show = function (kind, msg, ms) {
      if (!el) {
        el = doc.createElement('div');
        el.className = 'netbar';
        el.setAttribute('role', 'status');
        el.innerHTML = '<span class="nb-ic"></span><span class="nb-txt"></span><button type="button"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg></button>';
        el.querySelector('button').setAttribute('aria-label', T.net_close || 'OK');
        el.querySelector('button').addEventListener('click', hide);
        txt = el.querySelector('.nb-txt');
        doc.body.appendChild(el);
      }
      clearTimeout(hideT);
      el.querySelector('.nb-ic').innerHTML = icons[kind];
      txt.textContent = msg;
      el.classList.toggle('ok', kind === 'ok');
      void el.offsetWidth;
      el.classList.add('on');
      if (ms) hideT = setTimeout(hide, ms);
    };
    var hide = function () { if (el) el.classList.remove('on'); };
    // L'appli ne marche pas hors connexion : un écran couvre la page tant qu'Internet manque
    var screen = null;
    // Vraie vérification : le téléphone peut se dire « en ligne » sans Internet (Wi-Fi sans accès)
    var check = function () {
      if (navigator.onLine === false || !win.fetch) return Promise.resolve(navigator.onLine !== false);
      return fetch('/manifest.webmanifest?ping=' + Date.now(), { method: 'HEAD', cache: 'no-store' })
        .then(function (r) { return r.ok; }, function () { return false; });
    };
    var offline = function () {
      hide();
      if (!screen) {
        screen = doc.createElement('div');
        screen.className = 'offline-screen';
        screen.setAttribute('role', 'alertdialog');
        screen.setAttribute('aria-modal', 'true');
        screen.setAttribute('aria-labelledby', 'off-title');
        screen.innerHTML = '<div class="off-card"><span class="off-ic">' + icons.offline.replace(/width="18" height="18"/, 'width="30" height="30"') +
          '</span><h2 id="off-title"></h2><p></p><button type="button" class="btn"></button><small></small></div>';
        screen.querySelector('h2').textContent = T.off_title || 'Offline';
        screen.querySelector('p').textContent = T.off_text || '';
        screen.querySelector('small').textContent = T.off_wait || '';
        var b = screen.querySelector('button');
        b.textContent = T.off_retry || 'Retry';
        b.addEventListener('click', function () { b.disabled = true; check().then(function (ok) { b.disabled = false; if (ok) online(); }); });
      }
      if (!screen.isConnected) doc.body.appendChild(screen);
      root.classList.add('is-offline');
      screen.querySelector('button').focus({ preventScroll: true });
    };
    var online = function () {
      if (!screen || !screen.isConnected) return;
      screen.remove();
      root.classList.remove('is-offline');
      show('ok', T.net_online, 2500);
    };
    return {
      slow: function () {
        if (session.get('pb-slow-shown')) return;
        session.set('pb-slow-shown', '1');
        show('slow', T.net_slow, 6000);
      },
      offline: offline,
      online: online,
      hide: hide
    };
  })();
  win.addEventListener('offline', function () { netbar.offline(); });
  win.addEventListener('online', function () { netbar.online(); });
  win.addEventListener('pageshow', function (e) { if (e.persisted && navigator.onLine === false) netbar.offline(); });
  if (navigator.onLine === false) netbar.offline();
  else if (slowNet()) setTimeout(netbar.slow, 800);
  if (conn && conn.addEventListener) {
    conn.addEventListener('change', function () { root.classList.toggle('lite', slowNet()); if (slowNet()) netbar.slow(); });
  }

  // ---------- Prix dans la monnaie du pays ----------
  var P = CFG.prices || { currencies: {}, countries: {}, plans: {}, default_currency: {} };
  var TZ = {
    'Africa/Dakar': 'SN', 'Africa/Abidjan': 'CI', 'Africa/Porto-Novo': 'BJ', 'Africa/Ouagadougou': 'BF', 'Africa/Bamako': 'ML',
    'Africa/Niamey': 'NE', 'Africa/Lome': 'TG', 'Africa/Bissau': 'GW', 'Africa/Douala': 'CM', 'Africa/Libreville': 'GA',
    'Africa/Brazzaville': 'CG', 'Africa/Ndjamena': 'TD', 'Africa/Bangui': 'CF', 'Africa/Malabo': 'GQ', 'Africa/Lagos': 'NG',
    'Africa/Accra': 'GH', 'Africa/Nairobi': 'KE', 'Africa/Kampala': 'UG', 'Africa/Dar_es_Salaam': 'TZ', 'Africa/Kigali': 'RW',
    'Africa/Lusaka': 'ZM', 'Africa/Johannesburg': 'ZA', 'Africa/Casablanca': 'MA', 'Africa/Algiers': 'DZ', 'Africa/Tunis': 'TN',
    'Africa/Kinshasa': 'CD', 'Africa/Lubumbashi': 'CD', 'Indian/Antananarivo': 'MG', 'America/Port-au-Prince': 'HT',
    'Europe/London': 'GB', 'Europe/Paris': 'FR', 'Europe/Brussels': 'BE', 'Europe/Luxembourg': 'LU', 'Europe/Berlin': 'DE',
    'Europe/Madrid': 'ES', 'Europe/Rome': 'IT', 'Europe/Lisbon': 'PT', 'Europe/Amsterdam': 'NL', 'Europe/Dublin': 'IE',
    'Europe/Vienna': 'AT', 'Europe/Helsinki': 'FI', 'Europe/Athens': 'GR', 'Europe/Monaco': 'MC', 'Europe/Zurich': 'CH',
    'America/Toronto': 'CA', 'America/Montreal': 'CA', 'America/Vancouver': 'CA', 'America/New_York': 'US',
    'America/Chicago': 'US', 'America/Denver': 'US', 'America/Los_Angeles': 'US'
  };
  var guessCountry = function () {
    var saved = local.get('pb-country');
    if (saved !== null && (saved === '' || P.countries[saved])) return saved;
    var tz = '';
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) {}
    if (TZ[tz]) return TZ[tz];
    var m = /-([A-Z]{2})$/.exec(navigator.language || '');
    return m && P.countries[m[1]] ? m[1] : '';
  };
  var currencyOf = function (country) { return (country && P.countries[country]) || P.default_currency[lang] || 'EUR'; };
  var money = function (v, code, digits) {
    try {
      return new Intl.NumberFormat(lang === 'fr' ? 'fr-FR' : 'en-US', { style: 'currency', currency: code, minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v);
    } catch (e) { return v + ' ' + code; }
  };

  // ---------- Compte : état gardé sur l'appareil, Supabase chargé seulement si besoin ----------
  var Acct = (function () {
    var KEY = 'pb-acct';
    var listeners = [];
    var state = null;
    try { state = JSON.parse(local.get(KEY) || 'null'); } catch (e) {}
    var demo = !!CFG.demo || !CFG.sb;
    if (state && !!state.demo !== demo) state = null;  // on est passé du mode démo au vrai mode (ou l'inverse)

    var defaults = function () {
      return { premium_until: null, email_news: false, email_reminders: true, favorite_leagues: [], favorite_teams: [], lang: lang, country: null,
        is_adult: false, welcome_sent_at: null, tz: null, free_day: null, free_match: null,
        bonus_analyses: 0, extra_matches: [], ref_code: null, role: 'member', push_daily: true };
    };
    var isPremium = function (s) {
      s = s === undefined ? state : s;
      var u = s && s.profile && s.profile.premium_until;
      return !!u && new Date(u).getTime() > Date.now();
    };
    var apply = function () {
      root.classList.toggle('signed', !!(state && state.user));
      root.classList.toggle('premium', isPremium());
    };
    var save = function (s) {
      state = s;
      if (s) local.set(KEY, JSON.stringify(s)); else local.del(KEY);
      apply();
      listeners = listeners.filter(function (l) { return l.alive(); });
      listeners.forEach(function (l) { l.fn(state); });
      return s;
    };
    var clone = function (o) { return JSON.parse(JSON.stringify(o)); };
    var addDays = function (until, days) {
      var base = Math.max(Date.now(), until ? new Date(until).getTime() : 0);
      return new Date(base + days * 864e5).toISOString();
    };
    apply();

    // Mode démo : tout se passe sur le téléphone
    var Demo = {
      session: function () { return Promise.resolve(state); },
      signIn: function () {
        return Promise.resolve(save({ demo: true, t: Date.now(),
          user: { id: 'demo', email: 'demo@probalis.app', name: T.demo_name, avatar: null },
          profile: Object.assign(defaults(), { is_adult: true, welcome_sent_at: new Date().toISOString() }) }));
      },
      update: function (patch) { var s = clone(state); Object.assign(s.profile, patch); return Promise.resolve(save(s)); },
      // Analyse gratuite du jour : un seul match par jour, impossible à changer avant le lendemain
      useFree: function (slug, day) {
        var s = clone(state);
        if (!s.profile.free_day || s.profile.free_day < day) { s.profile.free_day = day; s.profile.free_match = slug; }
        return Promise.resolve(save(s));
      },
      signOut: function () { return Promise.resolve(save(null)); },
      remove: function () { return Promise.resolve(save(null)); },
      welcome: function () { return Promise.resolve(); },
      checkout: function (plan) {
        var s = clone(state);
        s.profile.premium_until = addDays(s.profile.premium_until, (P.plans[plan] || { days: 7 }).days);
        save(s);
        return Promise.resolve({ demo: true, until: s.profile.premium_until });
      },
      confirm: function () { return Promise.resolve(); },
      // Récompenses simulées : un bonus d'exemple, et le cadeau d'un lien d'e-mail (?r=…&t=…)
      rewards: function () {
        var s = clone(state);
        if (!s.demoRewards) {
          s.demoRewards = [{ id: 'demo-welcome', kind: 'analyses', amount: 2, plan: null, days: null, source: 'welcome_bonus',
            note: null, status: 'available', created_at: new Date().toISOString(), used_at: null, expires_at: null }];
          save(s);
        }
        return Promise.resolve(clone(s.demoRewards));
      },
      member: function (body) {
        var s = clone(state);
        var list = s.demoRewards || [];
        var find = function (id) { return list.filter(function (r) { return r.id === id; })[0]; };
        if (body.action === 'claim') {
          if (!find(body.id)) list.unshift({ id: body.id, kind: 'premium', plan: 'week', days: 7, amount: null, source: 'gift',
            note: null, status: 'available', created_at: new Date().toISOString(), used_at: null, expires_at: null });
          s.demoRewards = list;
          save(s);
          return Promise.resolve({ ok: true, status: 'available' });
        }
        if (body.action === 'activate') {
          var r = find(body.id);
          if (!r || r.status !== 'available') return Promise.reject(Object.assign(new Error('not_available'), { code: 'not_available' }));
          r.status = 'used';
          r.used_at = new Date().toISOString();
          if (r.kind === 'premium') s.profile.premium_until = addDays(s.profile.premium_until, r.days);
          else s.profile.bonus_analyses = (s.profile.bonus_analyses || 0) + r.amount;
          s.demoRewards = list;
          save(s);
          return Promise.resolve({ ok: true, kind: r.kind, plan: r.plan, premium_until: s.profile.premium_until,
            bonus_analyses: s.profile.bonus_analyses, applied: true });
        }
        return Promise.resolve({ ok: true });
      },
      useBonus: function (slug) {
        var s = clone(state);
        var ex = s.profile.extra_matches || [];
        if (ex.indexOf(slug) < 0) {
          if (!(s.profile.bonus_analyses > 0)) return Promise.reject(new Error('none'));
          s.profile.bonus_analyses -= 1;
          s.profile.extra_matches = ex.concat([slug]).slice(-60);
        }
        return Promise.resolve(save(s));
      },
      referral: function () { return Promise.resolve(null); }
    };

    // Vrai mode : Supabase (connexion Google, profil, fonctions de paiement et d'e-mail)
    var lib = null;
    var sb = function () {
      if (lib) return lib;
      lib = new Promise(function (resolve, reject) {
        var make = function () {
          return win.supabase.createClient(CFG.sb.url, CFG.sb.key, {
            auth: { flowType: 'pkce', detectSessionInUrl: true, persistSession: true, autoRefreshToken: true } });
        };
        if (win.supabase && win.supabase.createClient) { resolve(make()); return; }
        var s = doc.createElement('script');
        s.src = CFG.sb.lib;
        if (CFG.sb.sri) s.integrity = CFG.sb.sri;
        s.crossOrigin = 'anonymous';
        s.async = true;
        s.onload = function () { try { resolve(make()); } catch (e) { reject(e); } };
        s.onerror = function () { lib = null; reject(new Error('supabase-js')); };
        doc.head.appendChild(s);
      });
      return lib;
    };
    var check = function (r) { if (r && r.error) throw r.error; return r; };
    var Real = {
      session: function () {
        return sb().then(function (c) {
          return c.auth.getSession().then(function (r) {
            var ses = r.data && r.data.session;
            if (!ses) return save(null);
            var u = ses.user;
            var md = u.user_metadata || {};
            return c.from('profiles').select('*').eq('id', u.id).maybeSingle().then(check).then(function (pr) {
              return save({ t: Date.now(), user: { id: u.id, email: u.email,
                name: md.full_name || md.name || (u.email || '').split('@')[0], avatar: md.avatar_url || md.picture || null },
                profile: Object.assign(defaults(), pr.data || {}) });
            });
          });
        });
      },
      signIn: function (back) {
        return sb().then(function (c) {
          return c.auth.signInWithOAuth({ provider: 'google',
            options: { redirectTo: location.origin + (back || '/' + lang + '/compte.html') } }).then(check);
        });
      },
      update: function (patch) {
        return sb().then(function (c) {
          return c.from('profiles').update(patch).eq('id', state.user.id).select().single();
        }).then(check).then(function (r) {
          var s = clone(state);
          s.profile = Object.assign(defaults(), r.data);
          return save(s);
        });
      },
      useFree: function (slug, day) {
        return sb().then(function (c) {
          return c.rpc('use_free_analysis', { p_match: slug, p_day: day });
        }).then(check).then(function (r) {
          var row = (r.data && r.data[0]) || {};
          var s = clone(state);
          s.profile.free_day = row.free_day || null;
          s.profile.free_match = row.free_match || null;
          return save(s);
        });
      },
      signOut: function () {
        return sb().then(function (c) { return c.auth.signOut(); }).then(function () { return save(null); }, function () { return save(null); });
      },
      remove: function () {
        return sb().then(function (c) {
          return c.rpc('delete_my_account').then(check).then(function () { return c.auth.signOut(); });
        }).then(function () { return save(null); });
      },
      welcome: function () {
        return sb().then(function (c) { return c.functions.invoke('welcome', { body: { lang: lang } }); });
      },
      checkout: function (plan, country) {
        return sb().then(function (c) {
          return c.functions.invoke('checkout', { body: { plan: plan, country: country, lang: lang } });
        }).then(check).then(function (r) { return r.data; });
      },
      confirm: function (params) {
        return sb().then(function (c) { return c.functions.invoke('confirm-payment', { body: params }); });
      },
      // Fonction « member » (parrainage, activité du jour, cadeaux, notifications) ; l'erreur garde son code
      member: function (body) { return Real.fn('member', body); },
      fn: function (name, body) {
        return sb().then(function (c) { return c.functions.invoke(name, { body: body }); }).then(function (r) {
          if (!r.error) return r.data;
          var ctx = r.error.context;
          var fail = function (code) { var e = new Error(code || 'error'); e.code = code; throw e; };
          if (ctx && ctx.json) return ctx.json().then(function (d) { fail(d && d.error); }, function () { fail('server'); });
          fail('server');
        });
      },
      rewards: function () {
        return sb().then(function (c) {
          return c.from('rewards').select('id,kind,plan,days,amount,source,note,status,created_at,expires_at,claimed_at,used_at')
            .order('created_at', { ascending: false }).limit(60);
        }).then(check).then(function (r) { return r.data || []; });
      },
      useBonus: function (slug) {
        return sb().then(function (c) { return c.rpc('use_bonus_analysis', { p_match: slug }); }).then(check).then(function (r) {
          var row = (r.data && r.data[0]) || {};
          var s = clone(state);
          s.profile.bonus_analyses = row.bonus_analyses || 0;
          s.profile.extra_matches = row.extra_matches || [];
          return save(s);
        });
      },
      referral: function () {
        return sb().then(function (c) { return c.from('settings').select('value').eq('key', 'referral').maybeSingle(); })
          .then(check).then(function (r) { return r.data && r.data.value; });
      }
    };
    var B = demo ? Demo : Real;
    var hasToken = function () {
      try {
        for (var i = 0; i < localStorage.length; i++) if (/^sb-.+-auth-token$/.test(localStorage.key(i))) return true;
      } catch (e) {}
      return false;
    };
    // Jeton de connexion, envoyé au serveur des chiffres protégés (qui le vérifie auprès de Supabase)
    var token = function () {
      if (demo) return Promise.resolve(state && state.user ? 'demo' : null);
      if (!hasToken()) return Promise.resolve(null);
      try {
        for (var i = 0; i < localStorage.length; i++) {
          var k = localStorage.key(i);
          if (!/^sb-.+-auth-token$/.test(k)) continue;
          var o = JSON.parse(localStorage.getItem(k) || 'null');
          if (o && o.access_token && o.expires_at && o.expires_at * 1000 > Date.now() + 60e3) return Promise.resolve(o.access_token);
        }
      } catch (e) {}
      return sb().then(function (c) { return c.auth.getSession(); }).then(function (r) {
        var ses = r && r.data && r.data.session;
        return ses ? ses.access_token : null;
      }, function () { return null; });
    };
    return {
      demo: demo,
      get: function () { return state; },
      premium: isPremium,
      token: token,
      on: function (fn, alive) { listeners.push({ fn: fn, alive: alive }); },
      api: B,
      hasToken: hasToken,
      // Appel d'une fonction Supabase (page d'administration)
      fn: function (name, body) { return B.fn ? B.fn(name, body) : Promise.reject(new Error('demo')); },
      // En arrière-plan : on rafraîchit le profil (Premium acheté sur un autre appareil, etc.)
      boot: function () {
        if (demo) return;
        if (!hasToken()) { if (state) save(null); return; }
        if (state && Date.now() - (state.t || 0) < 30 * 60e3) return;
        var go = function () { B.session().catch(noop); };
        if (win.requestIdleCallback) win.requestIdleCallback(go, { timeout: 4000 }); else setTimeout(go, 1500);
      }
    };
  })();

  // ---------- Favoris : équipes suivies et championnats favoris, enregistrés dans le compte (tous les appareils) ----------
  var Favs = {
    q: Promise.resolve(),
    prof: function () { var s = Acct.get(); return s && s.user ? s.profile || {} : null; },
    teams: function () { var p = Favs.prof(); return (p && p.favorite_teams) || []; },
    leagues: function () { var p = Favs.prof(); return (p && p.favorite_leagues) || []; },
    // on : true pour suivre, false pour ne plus suivre. Les changements partent l'un après l'autre (rien ne se perd
    // quand on touche plusieurs étoiles très vite). Renvoie true si c'est enregistré.
    set: function (kind, v, on) {
      if (!Favs.prof()) { toast(T.fav_signin); return Promise.resolve(false); }
      var k = kind === 'team' ? 'favorite_teams' : 'favorite_leagues';
      var run = function () {
        var p = Favs.prof();
        if (!p) return false;
        var list = (p[k] || []).slice();
        var i = list.indexOf(v);
        if (on ? i >= 0 : i < 0) return true;
        if (on && list.length >= 50) { toast(T.fav_full); return false; }
        if (on) list.push(v); else list.splice(i, 1);
        var patch = {};
        patch[k] = list;
        return Acct.api.update(patch).then(function () {
          toast(on ? (kind === 'team' ? fmt(T.fav_team_on, { n: v }) : T.fav_lg_on) : T.fav_off);
          return true;
        }, function () { toast(T.error); return false; });
      };
      Favs.q = Favs.q.then(run, run);
      return Favs.q;
    }
  };

  // =====================================================================================================
  // Initialisation d'une page (au premier chargement, puis après chaque changement de page)
  // =====================================================================================================
  var shortDay = function (d) { return cap(F.short.format(d)).replace(/^(\p{L}+)(?!\.)\s/u, lang === 'fr' ? '$1. ' : '$1 '); };
  var pad = function (n) { return (n < 10 ? '0' : '') + n; };
  var dayKey = function (d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); };
  var fromKey = function (k) { var p = k.split('-'); return new Date(+p[0], +p[1] - 1, +p[2], 12); };

  var initDates = function (scope) {
    // Heures et dates dans le fuseau horaire du téléphone
    $$('time[data-ko]', scope).forEach(function (el) { el.textContent = F.time.format(new Date(el.dataset.ko)); });
    $$('[data-dshort]', scope).forEach(function (el) { el.textContent = shortDay(new Date(el.dataset.dshort)); });
    $$('[data-dmed]', scope).forEach(function (el) { el.textContent = cap(F.med.format(new Date(el.dataset.dmed))); });
    $$('[data-dt]', scope).forEach(function (el) { el.textContent = F.dt.format(new Date(el.dataset.dt)); });
    // Matchs déjà joués (plus de 2 h après le coup d'envoi) : retirés des listes
    var now = Date.now();
    $$('[data-expire]', scope).forEach(function (el) {
      if (new Date(el.dataset.expire).getTime() + 2 * 3600e3 < now) el.hidden = true;
    });
  };

  // Logos : petit repère qui pulse pendant le chargement, fondu à l'arrivée, initiales si l'image manque
  var initImages = function (scope) {
    $$('.crest img, .lgl img', scope).forEach(function (img) {
      var box = img.parentNode;
      var ok = function () { img.classList.add('ld'); box.classList.remove('wait'); };
      var drop = function () { box.classList.remove('wait'); box.classList.add('noimg'); img.remove(); };
      if (img.complete) { if (img.naturalWidth) ok(); else drop(); return; }
      box.classList.add('wait');
      img.addEventListener('load', ok);
      img.addEventListener('error', drop);
    });
  };

  var initPrices = function (scope) {
    var els = $$('[data-from-price]', scope);
    if (!els.length) return;
    var code = currencyOf(guessCountry());
    var c = P.currencies[code];
    if (!c) return;
    var txt = fmt(T.from_price, { p: money(c.week, code, c.decimals) });
    els.forEach(function (el) { el.textContent = txt; });
  };

  // ---------- Accueil : filtres par jour et par championnat ----------
  var initHome = function (scope) {
    var list = scope.querySelector('#list');
    if (!list) return;
    var cards = $$('.mcard', list);
    var groups = $$('section.lg', list);
    var ad = list.querySelector('.ad');
    var feats = $$('.featured', scope);
    var chips = $$('#chips .chip:not(.favs-chip)', scope);
    var favChip = scope.querySelector('#chips .favs-chip');
    var mt = scope.querySelector('#myteams');
    var mtList = mt && mt.querySelector('.mt-list');
    var mtNone = mt && mt.querySelector('.mt-none');
    var daysEl = scope.querySelector('#days');
    var weekBtn = daysEl.querySelector('.week');
    var empty = scope.querySelector('#empty');
    var emptyP = empty.querySelector('p');
    var emptyB = empty.querySelector('#reset-filter');
    var emptyTxt = [emptyP.textContent, emptyB.textContent];
    var home = scope.querySelector('.home-wrap');
    var label = scope.querySelector('#day-label');
    var dot = scope.querySelector('#open-sheet .dot');
    var sheet = scope.querySelector('#sheet');
    var rows = $$('.lrow', sheet);
    var boxes = $$('input[type="checkbox"]', sheet);
    var applyBtn = scope.querySelector('#sheet-apply');
    var search = scope.querySelector('#sheet-search');
    var known = rows.map(function (r) { return r.dataset.league; });
    var today = dayKey(new Date());
    var qIn = scope.querySelector('#q');  // recherche d'équipe (tablette et ordinateur)
    var fold = function (s) { return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim(); };

    cards.forEach(function (c) {
      c._d = dayKey(new Date(c.dataset.ko));
      c._t = $$('.team .nm', c).map(function (n) { return n.textContent.trim(); });
      c._n = fold(c._t.join(' '));
    });
    feats.forEach(function (f) {
      f._d = dayKey(new Date(f.dataset.ko));
      f._t = $$('.side .nm', f).map(function (n) { return n.textContent.trim(); });
    });
    // Championnats favoris en premier (liste et pastilles), une fois à l'arrivée sur la page : rien ne bouge sous le doigt
    var favL0 = Favs.leagues();
    if (favL0.length) {
      groups.filter(function (g) { return favL0.indexOf(g.dataset.league) >= 0; }).reverse()
        .forEach(function (g) { list.insertBefore(g, list.firstChild); });
      groups = $$('section.lg', list);
      var chipBox = scope.querySelector('#chips');
      var after = favChip || chips[0];
      chips.filter(function (ch) { return favL0.indexOf(ch.dataset.league) >= 0; }).reverse()
        .forEach(function (ch) { chipBox.insertBefore(ch, after.nextSibling); });
    }
    var days = cards.map(function (c) { return c._d; })
      .filter(function (d, i, a) { return d >= today && a.indexOf(d) === i; }).sort();

    var sel = [];
    try { sel = JSON.parse(local.get('leagues') || '[]').filter(function (c) { return known.indexOf(c) >= 0; }); } catch (e) {}
    var saved = session.get('day');
    var state = { day: saved === 'all' || days.indexOf(saved) >= 0 ? saved : (days[0] || 'all'), sel: sel, q: '',
      fav: session.get('mfav') === '1' };
    // Choisir un jour ou un championnat met fin à la recherche d'équipe
    var clearQ = function () { state.q = ''; if (qIn) qIn.value = ''; };

    var pills = days.map(function (d) {
      var b = doc.createElement('button');
      var dt = fromKey(d);
      b.type = 'button';
      b.className = 'day';
      b.dataset.day = d;
      b.setAttribute('aria-label', cap(F.long.format(dt)));
      var s = doc.createElement('small');
      s.textContent = d === today ? T.today : cap(F.wd.format(dt));
      var n = doc.createElement('b');
      n.textContent = dt.getDate();
      b.appendChild(s);
      b.appendChild(n);
      daysEl.insertBefore(b, weekBtn);
      return b;
    });
    pills.push(weekBtn);

    var inSel = function (code, s) { s = s || state.sel; return !s.length || s.indexOf(code) >= 0; };
    var onDay = function (d) { return d >= today && (state.day === 'all' || d === state.day); };
    var plural = function (n) { return n === 1 ? T.one_match : fmt(T.n_matches, { n: n }); };
    var save = function () {
      local.set('leagues', JSON.stringify(state.sel));
      session.set('day', state.day);
      session.set('mfav', state.fav ? '1' : '0');
    };
    // Favoris du compte : équipes suivies (noms) et championnats favoris (codes)
    var favT = [], favL = [];
    var hasTeam = function (el) { return el._t.some(function (n) { return favT.indexOf(n) >= 0; }); };
    var isFav = function (el) { return favL.indexOf(el.dataset.league) >= 0 || hasTeam(el); };
    var pass = function (el) { return state.fav ? isFav(el) : inSel(el.dataset.league); };
    // « Mes équipes » : une ligne par match (heure, équipes), vers la page du match
    var mtRow = function (c) {
      var a = doc.createElement('a');
      a.className = 'mt-row';
      a.href = c.getAttribute('href');
      a.appendChild(c.querySelector('.time').cloneNode(true));
      var tm = c.querySelector('.mc-teams').cloneNode(true);
      $$('.sc', tm).forEach(function (x) { x.remove(); });
      a.appendChild(tm);
      initImages(a);  // logos copiés avant d'être chargés : on suit leur chargement
      return a;
    };

    var render = function () {
      favT = Favs.teams();
      favL = Favs.leagues();
      var hasFav = !!(favT.length || favL.length);
      if (!hasFav) state.fav = false;
      pills.forEach(function (p) {
        var on = p.dataset.day === state.day;
        p.classList.toggle('on', on);
        p.setAttribute('aria-pressed', on);
      });
      var counts = {};
      cards.forEach(function (c) { if (onDay(c._d)) counts[c.dataset.league] = (counts[c.dataset.league] || 0) + 1; });
      chips.forEach(function (ch) {
        var code = ch.dataset.league;
        var on = code ? state.sel.indexOf(code) >= 0 : !state.sel.length && !state.fav;
        if (code) {
          var n = counts[code] || 0;
          ch.hidden = !n && !on;
          ch.querySelector('.count').textContent = n;
        }
        ch.classList.toggle('on', on);
        ch.setAttribute('aria-pressed', on);
      });
      if (favChip) {
        favChip.hidden = !hasFav;
        favChip.classList.toggle('on', state.fav);
        favChip.setAttribute('aria-pressed', state.fav);
        favChip.querySelector('.count').textContent = cards.filter(function (c) { return onDay(c._d) && isFav(c); }).length;
      }
      var shown = 0;
      // Recherche : toute la semaine et tous les championnats, seulement les matchs de l'équipe cherchée
      cards.forEach(function (c) {
        var v = state.q ? c._d >= today && c._n.indexOf(state.q) >= 0 : onDay(c._d) && pass(c);
        c.hidden = !v;
        if (v) shown++;
        // Étoile à côté des équipes suivies
        $$('.team', c).forEach(function (tm, i) {
          var on = favT.indexOf(c._t[i]) >= 0;
          tm.classList.toggle('fav', on);
          if (on && !tm.querySelector('.tm-star')) {
            var st = doc.createElement('i');
            st.className = 'tm-star';
            st.setAttribute('aria-hidden', 'true');
            st.innerHTML = IC_STAR;
            tm.querySelector('.nm').insertAdjacentElement('afterend', st);
          }
        });
      });
      // « Mes équipes » en haut : les matchs des équipes suivies, pour le jour choisi (ou la semaine)
      if (mt) {
        var mine = favT.length && !state.q && !state.fav ? cards.filter(function (c) { return onDay(c._d) && hasTeam(c); })
          .sort(function (a, b) { return a.dataset.ko < b.dataset.ko ? -1 : a.dataset.ko > b.dataset.ko ? 1 : 0; }) : [];
        mt.hidden = !favT.length || !!state.q || state.fav;
        var mk = mine.map(function (c) { return c.getAttribute('href'); }).join('|');
        if (mt._k !== mk) {
          mt._k = mk;
          mtList.textContent = '';
          mine.slice(0, 12).forEach(function (c) { mtList.appendChild(mtRow(c)); });
        }
        mtNone.hidden = mine.length > 0;
      }
      list.classList.toggle('searching', !!state.q);
      groups.forEach(function (g) {
        g.hidden = !g.querySelector('.mcard:not([hidden])');
        var lf = g.querySelector('.lg-fav');
        if (lf) lf.setAttribute('aria-pressed', favL.indexOf(g.dataset.league) >= 0);
        var sa = g.querySelector('.see-all');
        if (sa) sa.hidden = state.day === 'all' && state.sel.length === 1 && state.sel[0] === g.dataset.league;
      });
      // La pub reste discrète : après le 2e championnat affiché, jamais en tête de liste
      if (ad) {
        var vis = groups.filter(function (g) { return !g.hidden; });
        ad.hidden = vis.length < 3;
        if (!ad.hidden && vis[1].nextElementSibling !== ad) vis[1].parentNode.insertBefore(ad, vis[1].nextElementSibling);
      }
      list.classList.toggle('week', state.day === 'all' || !!state.q);
      // À la une : la plus belle affiche parmi les matchs affichés, grands championnats d'abord
      var pool = feats.filter(function (f) { f.hidden = true; return onDay(f._d) && pass(f); });
      var prime = pool.filter(function (f) { return f.dataset.prime === '1'; });
      var best = null;
      (prime.length ? prime : pool).forEach(function (f) {
        if (!best || +f.dataset.stature > +best.dataset.stature) best = f;
      });
      if (best && !state.q) best.hidden = false;
      if (ad && state.q) ad.hidden = true;
      empty.hidden = shown > 0;
      // Pendant une recherche : jours et championnats en retrait, message propre à la recherche
      if (home) home.classList.toggle('q-on', !!state.q);
      emptyP.textContent = state.q ? T.q_none.replace('{q}', qIn.value.trim()) : emptyTxt[0];
      emptyB.textContent = state.q ? T.q_clear : emptyTxt[1];
      label.textContent = state.day === 'all' ? T.all_week : cap(F.long.format(fromKey(state.day)));
      dot.hidden = !state.sel.length;
      rows.forEach(function (r) {
        var n = counts[r.dataset.league] || 0;
        r.querySelector('.lr-count').textContent = n ? plural(n) : T.no_match_day;
        r.classList.toggle('zero', !n);
      });
    };

    daysEl.addEventListener('click', function (e) {
      var b = e.target.closest('.day');
      if (!b) return;
      state.day = b.dataset.day;
      clearQ();
      save();
      render();
    });
    scope.querySelector('#chips').addEventListener('click', function (e) {
      var ch = e.target.closest('.chip');
      if (!ch) return;
      clearQ();
      if (ch === favChip) {
        state.fav = !state.fav;
        state.sel = [];
      } else {
        state.fav = false;
        var code = ch.dataset.league;
        state.sel = !code || (state.sel.length === 1 && state.sel[0] === code) ? [] : [code];
      }
      save();
      render();
    });
    list.addEventListener('click', function (e) {
      var f = e.target.closest('.lg-fav');
      if (f) {
        if (!Favs.prof()) { toast(T.fav_signin); return; }
        var on = f.getAttribute('aria-pressed') !== 'true';
        f.setAttribute('aria-pressed', on);
        Favs.set('league', f.dataset.favLeague, on).then(function (ok) { if (!ok) render(); });
        return;
      }
      var b = e.target.closest('.see-all');
      if (!b) return;
      state.fav = false;
      state.sel = [b.dataset.league];
      state.day = 'all';
      save();
      render();
      daysEl.scrollIntoView({ block: 'start', behavior: reduced.matches ? 'auto' : 'smooth' });
    });
    scope.querySelector('#reset-filter').addEventListener('click', function () {
      state.sel = [];
      state.fav = false;
      state.q = '';
      if (qIn) qIn.value = '';
      save();
      render();
    });
    if (qIn) {
      qIn.value = '';
      qIn.addEventListener('input', function () { state.q = fold(qIn.value); render(); });
      // « / » : aller tout de suite à la recherche (ordinateur) ; Échap : effacer
      var onKey = function (e) {
        if (!doc.body.contains(qIn)) { doc.removeEventListener('keydown', onKey); return; }
        if (e.key === '/' && !/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName || '') && qIn.offsetParent) { e.preventDefault(); qIn.focus(); }
        if (e.key === 'Escape' && e.target === qIn && qIn.value) { qIn.value = ''; state.q = ''; render(); }
      };
      doc.addEventListener('keydown', onKey);
    }

    // Feuille « Championnats » : cases à cocher, recherche, nombre de matchs
    var checked = function () { return boxes.filter(function (b) { return b.checked; }).map(function (b) { return b.value; }); };
    var updateApply = function () {
      var s = checked();
      var n = cards.filter(function (c) { return onDay(c._d) && inSel(c.dataset.league, s); }).length;
      applyBtn.textContent = n === 1 ? T.show_one : n ? fmt(T.show_n, { n: n }) : T.show_none;
    };
    var filterRows = function () {
      var q = fold(search.value);
      var any = false;
      rows.forEach(function (r) { r.hidden = !!q && r.dataset.search.indexOf(q) < 0; if (!r.hidden) any = true; });
      $$('.sec', sheet).forEach(function (s) { s.hidden = !s.querySelector('.lrow:not([hidden])'); });
      sheet.querySelector('.sheet-none').hidden = any;
    };
    scope.querySelector('#open-sheet').addEventListener('click', function () {
      boxes.forEach(function (b) { b.checked = state.sel.indexOf(b.value) >= 0; });
      search.value = '';
      filterRows();
      updateApply();
      if (sheet.showModal) sheet.showModal(); else sheet.setAttribute('open', '');
    });
    sheet.addEventListener('change', updateApply);
    search.addEventListener('input', filterRows);
    scope.querySelector('#sheet-reset').addEventListener('click', function () {
      boxes.forEach(function (b) { b.checked = false; });
      updateApply();
    });
    applyBtn.addEventListener('click', function () {
      state.sel = checked();
      state.fav = false;
      save();
      render();
      if (sheet.close) sheet.close(); else sheet.removeAttribute('open');
    });
    sheet.addEventListener('click', function (e) { if (e.target === sheet && sheet.close) sheet.close(); });

    render();
    var on = daysEl.querySelector('.day.on');
    if (on && on.offsetLeft > daysEl.clientWidth - 60) daysEl.scrollLeft = on.offsetLeft - 20;
    Acct.on(render, function () { return list.isConnected; });
  };

  // ---------- Page d'un match : « Suivre » sous chaque équipe (équipes suivies, enregistrées dans le compte) ----------
  var initFollow = function (scope) {
    var btns = $$('button[data-follow]', scope);
    if (!btns.length) return;
    var show = function (b, on) {
      b.classList.toggle('on', on);
      b.querySelector('span').textContent = on ? T.followed : T.follow;
      b.setAttribute('aria-label', fmt(on ? T.unfollow_team : T.follow_team, { n: b.dataset.follow }));
    };
    var render = function () {
      var fav = Favs.teams();
      btns.forEach(function (b) { show(b, fav.indexOf(b.dataset.follow) >= 0); });
    };
    btns.forEach(function (b) {
      b.addEventListener('click', function () {
        if (!Favs.prof()) { toast(T.fav_signin); return; }
        var on = !b.classList.contains('on');
        show(b, on);
        Favs.set('team', b.dataset.follow, on).then(function (ok) { if (!ok) render(); });
      });
    });
    render();
    Acct.on(render, function () { return btns[0].isConnected; });
  };

  // ---------- Page match : onglets ----------
  var initTabs = function (scope) {
    var tabNav = scope.querySelector('.ptabs');
    if (!tabNav) return;
    var links = $$('a', tabNav);
    var panels = links.map(function (a) { return scope.querySelector('#' + a.hash.slice(1)); });
    var anchor = scope.querySelector('#tabs-anchor');
    tabNav.setAttribute('role', 'tablist');
    links.forEach(function (a, i) {
      a.setAttribute('role', 'tab');
      a.setAttribute('aria-controls', panels[i].id);
      panels[i].setAttribute('role', 'tabpanel');
      panels[i].setAttribute('aria-labelledby', a.id);
      panels[i].removeAttribute('aria-label');
    });
    var show = function (i, user) {
      links.forEach(function (a, j) {
        var on = i === j;
        a.classList.toggle('on', on);
        a.setAttribute('aria-selected', on);
        a.tabIndex = on ? 0 : -1;
        panels[j].hidden = !on;
      });
      tabNav.scrollTo({ left: Math.max(0, links[i].offsetLeft - 20), behavior: user && !reduced.matches ? 'smooth' : 'auto' });
      if (user) {
        history.replaceState(history.state, '', i ? links[i].hash : location.pathname + location.search);
        var top = anchor.getBoundingClientRect().top + win.scrollY;
        if (win.scrollY > top) win.scrollTo(0, top);
      }
    };
    tabNav.addEventListener('click', function (e) {
      var a = e.target.closest('a');
      if (!a) return;
      e.preventDefault();
      show(links.indexOf(a), true);
    });
    tabNav.addEventListener('keydown', function (e) {
      var i = links.indexOf(doc.activeElement);
      if (i < 0 || (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft')) return;
      var j = (i + (e.key === 'ArrowRight' ? 1 : links.length - 1)) % links.length;
      show(j, true);
      links[j].focus();
      e.preventDefault();
    });
    $$('[data-tab]', scope).forEach(function (a) {
      if (a.closest('.tabbar')) return;
      a.addEventListener('click', function (e) {
        var i = panels.map(function (p) { return p.id; }).indexOf(a.dataset.tab);
        if (i < 0) return;
        e.preventDefault();
        show(i, true);
      });
    });
    var start = links.map(function (a) { return a.hash; }).indexOf(location.hash);
    show(start > 0 ? start : 0, false);
  };

  // ---------- Compare ta cote ----------
  var initCompare = function (scope) {
    var cmp = scope.querySelector('#compare');
    if (!cmp) return;
    var data = {};
    try { data = JSON.parse(scope.querySelector('#cmp-data').textContent); } catch (e) { return; }
    var select = scope.querySelector('#cmp-sel');
    var input = scope.querySelector('#cmp-odds');
    var chance = scope.querySelector('#cmp-chance');
    var out = scope.querySelector('#cmp-verdict');
    var txt = out.querySelector('.v-txt');
    var nf = new Intl.NumberFormat(loc, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    var pct = function (p) { var v = Math.round(p * 100); return lang === 'fr' ? v + ' %' : v + '%'; };
    var run = function () {
      var it = data.items[select.value];
      if (!it) return;
      chance.textContent = fmt(T.chance, { p: pct(it.p), fair: nf.format(it.fair) });
      var raw = input.value.trim().replace(',', '.');
      if (!raw) { out.hidden = true; return; }
      var odds = parseFloat(raw);
      var kind, msg;
      if (!isFinite(odds) || odds <= 1 || !/^\d+(\.\d*)?$/.test(raw)) {
        kind = 'warn';
        msg = '<b>' + T.v_invalid + '</b>' + T.colon + T.v_invalid_txt;
      } else {
        var r = odds / it.fair;
        kind = r >= 1.02 ? 'good' : r >= 0.98 ? 'fair' : 'bad';
        msg = '<b>' + T['v_' + kind] + '</b>' + T.colon +
          fmt(T['v_' + kind + '_txt'], { odds: nf.format(odds), fair: nf.format(it.fair), m: pct(1 - r) }) +
          ' ' + T.v_note + (data.source === 'model' ? ' ' + T.v_model : '');
      }
      out.className = 'verdict ' + kind;
      txt.innerHTML = msg;
      out.hidden = false;
    };
    select.addEventListener('change', run);
    input.addEventListener('input', run);
    run();
  };

  // ---------- Partager un match ----------
  doc.addEventListener('click', function (e) {
    if (!e.target.closest('.share')) return;
    var url = location.href.split('#')[0];
    if (navigator.share) {
      navigator.share({ title: doc.title, url: url }).catch(noop);
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(function () { toast(T.link_copied); }, noop);
    }
  });

  var flash = function (scope, msg, kind) {
    var el = scope.querySelector('#flash');
    if (!el) { toast(msg); return; }
    el.className = 'flash' + (kind ? ' ' + kind : '');
    el.textContent = msg;
    el.hidden = false;
  };
  var params = function () {
    var o = {};
    location.search.slice(1).split('&').forEach(function (kv) {
      if (!kv) return;
      var p = kv.split('=');
      o[decodeURIComponent(p[0])] = decodeURIComponent((p[1] || '').replace(/\+/g, ' '));
    });
    return o;
  };
  var cleanUrl = function () { history.replaceState(history.state, '', location.pathname + location.hash); };
  var untilTxt = function (s) { return F.date.format(new Date(s.profile.premium_until)); };

  // ---------- Mon compte ----------
  var initAccount = function (scope) {
    var box = scope.querySelector('#acct');
    if (!box) return;
    var api = Acct.api;
    var adult = box.querySelector('#adult');
    var gbtn = box.querySelector('#google');
    var render = function (s) {
      box.dataset.state = s && s.user ? 'in' : 'out';
      if (!s || !s.user) { gbtn.disabled = false; return; }
      var u = s.user;
      var p = s.profile || {};
      box.querySelector('#acct-name').textContent = u.name || u.email;
      box.querySelector('#acct-email').textContent = u.email || '';
      var av = box.querySelector('#acct-avatar');
      av.textContent = '';
      if (u.avatar) {
        var img = doc.createElement('img');
        img.alt = '';
        img.referrerPolicy = 'no-referrer';
        img.src = u.avatar;
        img.onerror = function () { av.textContent = (u.name || '?').charAt(0).toUpperCase(); };
        av.appendChild(img);
      } else av.textContent = (u.name || u.email || '?').charAt(0).toUpperCase();
      var prem = Acct.premium(s);
      var badge = box.querySelector('#plan-badge');
      badge.className = 'plan-badge' + (prem ? ' prem' : '');
      badge.textContent = prem ? T.plan_premium : T.plan_free;
      var pt = box.querySelector('#plan-text');
      pt.textContent = prem ? fmt(T.premium_until, { d: untilTxt(s) }) : pt.dataset.free;
      var cta = box.querySelector('#plan-cta');
      cta.querySelector('span').textContent = prem ? cta.dataset.extend : cta.dataset.go;
      var dp = box.querySelector('#demo-premium');
      if (dp) dp.checked = prem;
      $$('[data-pref]', box).forEach(function (el) {
        var k = el.dataset.pref;
        if (el.type === 'checkbox') el.checked = !!p[k];
        else if (p[k]) el.value = p[k];
      });
      var fav = p.favorite_leagues || [];
      $$('.fav-chip[data-league]', box).forEach(function (b) { b.setAttribute('aria-pressed', fav.indexOf(b.dataset.league) >= 0); });
      var ft = p.favorite_teams || [];
      var tb = box.querySelector('#fav-teams');
      if (tb) {
        tb.innerHTML = ft.map(function (n) {
          var lbl = esc(fmt(T.unfollow_team, { n: n }));
          return '<button class="fav-chip team" type="button" data-team="' + esc(n) + '" aria-label="' + lbl + '" title="' + lbl + '">' +
            IC_STAR + '<span>' + esc(n) + '</span>' + IC_X + '</button>';
        }).join('');
        box.querySelector('#fav-teams-none').hidden = ft.length > 0;
      }
      var adm = box.querySelector('#admin-link');
      if (adm) adm.hidden = p.role !== 'admin';
    };
    var s0 = Acct.get();
    var returning = /[?&]code=/.test(location.search);
    var check = !Acct.demo && (Acct.hasToken() || returning);
    if (check && !s0) box.dataset.state = '';  // squelette le temps de vérifier la connexion
    else render(s0);
    Acct.on(render, function () { return box.isConnected; });

    var afterLogin = function (s) {
      if (!s || !s.user) return;
      var steps = Promise.resolve(s);
      var patch = {};
      if (local.get('pb-adult') === '1' && !s.profile.is_adult) patch.is_adult = true;
      local.del('pb-adult');
      // Fuseau horaire du téléphone : pour écrire l'heure des matchs dans les e-mails
      var tz = ''; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) {}
      if (tz && s.profile.tz !== tz) patch.tz = tz;
      if (!s.profile.country) patch.country = guessCountry();
      if (Object.keys(patch).length) steps = steps.then(function () { return api.update(patch); }).catch(noop);
      if (!s.profile.welcome_sent_at) {
        api.welcome().catch(noop);
        toast(fmt(T.welcome, { n: (s.user.name || '').split(' ')[0] || '' }));
      }
      steps = steps.then(function () { return Member.start(true); }).catch(noop);
      var next = local.get('pb-next');
      if (next) { local.del('pb-next'); steps.then(function () { router.go(next); }); }
      return steps;
    };

    // Retour d'un paiement
    var q = params();
    var payReturn = function () {
      // Stripe revient avec ?paiement=ok&session_id=… ; Flutterwave avec ?status=…&tx_ref=…&transaction_id=…
      if (q.paiement === 'annule' || q.status === 'cancelled' || q.status === 'failed') { flash(scope, T.pay_cancel, 'warn'); cleanUrl(); return; }
      if (q.paiement !== 'ok' && !q.transaction_id) return;
      flash(scope, T.pay_pending);
      var tries = 0;
      var confirmP = q.session_id ? api.confirm({ provider: 'stripe', session_id: q.session_id })
        : q.transaction_id ? api.confirm({ provider: 'flutterwave', transaction_id: q.transaction_id, tx_ref: q.tx_ref || '' })
          : Promise.resolve();
      cleanUrl();
      var poll = function () {
        api.session().then(function (s) {
          if (Acct.premium(s)) { flash(scope, fmt(T.pay_ok, { d: untilTxt(s) })); return; }
          if (++tries < 8) setTimeout(poll, 3500); else flash(scope, T.pay_slow, 'warn');
        }, function () { flash(scope, T.pay_slow, 'warn'); });
      };
      confirmP.then(poll, poll);
    };

    // Lien « Me désinscrire » d'une alerte : marche même sans être connecté (lien signé)
    if (q.desabo && q.u && q.t) {
      var kind = q.desabo === 'reminders' ? 'reminders' : 'news';
      var unsub = Acct.demo ? Promise.resolve(true) : fetch(CFG.sb.url + '/functions/v1/unsubscribe', {
        method: 'POST', headers: { 'Content-Type': 'application/json', apikey: CFG.sb.key },
        body: JSON.stringify({ u: q.u, k: kind, t: q.t }) }).then(function (r) { return r.ok; });
      cleanUrl();
      unsub.then(function (ok) {
        flash(scope, ok ? T['unsub_' + kind] : T.unsub_bad, ok ? undefined : 'warn');
        var st = Acct.get();
        if (ok && !Acct.demo && st && st.user && st.user.id === q.u) api.session().then(render, noop);
      }, function () { flash(scope, T.error, 'bad'); });
    }

    if (check) {
      api.session().then(function (s) {
        render(s);
        if (s && returning) { cleanUrl(); afterLogin(s); }
        payReturn();
      }, function () { render(Acct.get()); flash(scope, T.error, 'bad'); });
    } else payReturn();

    gbtn.addEventListener('click', function () {
      if (!adult.checked) {
        var lab = adult.closest('.adult');
        lab.classList.remove('shake');
        void lab.offsetWidth;
        lab.classList.add('shake');
        toast(T.adult_required);
        adult.focus();
        return;
      }
      local.set('pb-adult', '1');
      gbtn.disabled = true;
      api.signIn().then(function (s) {
        if (Acct.demo) { toast(T.demo_welcome); afterLogin(Object.assign({}, s, { profile: Object.assign({}, s.profile, { welcome_sent_at: 'x' }) })); }
      }, function () { gbtn.disabled = false; toast(T.error); });
    });

    var saveTimer;
    var savePatch = function (patch, undo) {
      api.update(patch).then(function () { toast(T.saved); }, function () { if (undo) undo(); toast(T.error); });
    };
    $$('[data-pref]', box).forEach(function (el) {
      el.addEventListener('change', function () {
        var k = el.dataset.pref;
        var patch = {};
        if (el.type === 'checkbox') {
          patch[k] = el.checked;
          savePatch(patch, function () { el.checked = !el.checked; });
        } else if (k === 'lang') {
          api.update({ lang: el.value }).then(function () { location.href = '/' + el.value + '/compte.html'; }, function () { toast(T.error); });
        }
      });
    });
    box.querySelector('#favs').addEventListener('click', function (e) {
      var b = e.target.closest('.fav-chip');
      if (!b) return;
      b.setAttribute('aria-pressed', b.getAttribute('aria-pressed') !== 'true');
      clearTimeout(saveTimer);
      saveTimer = setTimeout(function () {
        var list = $$('.fav-chip[data-league][aria-pressed="true"]', box).map(function (x) { return x.dataset.league; });
        savePatch({ favorite_leagues: list });
      }, 700);
    });
    var ftb = box.querySelector('#fav-teams');
    if (ftb) ftb.addEventListener('click', function (e) {
      var b = e.target.closest('[data-team]');
      if (!b) return;
      b.disabled = true;
      Favs.set('team', b.dataset.team, false).then(function (ok) { if (!ok) b.disabled = false; });
    });
    var dp = box.querySelector('#demo-premium');
    if (dp) dp.addEventListener('change', function () {
      api.update({ premium_until: dp.checked ? new Date(Date.now() + 7 * 864e5).toISOString() : null });
    });
    box.querySelector('#signout').addEventListener('click', function () {
      api.signOut().then(function () { toast(T.signed_out); win.scrollTo(0, 0); });
    });
    box.querySelector('#delete').addEventListener('click', function () {
      if (!win.confirm(T.delete_confirm)) return;
      api.remove().then(function () { toast(T.deleted); win.scrollTo(0, 0); }, function () { toast(T.error); });
    });
  };

  // ---------- Offres Premium ----------
  var initPremium = function (scope) {
    var plansEl = scope.querySelector('#plans');
    if (!plansEl) return;
    var select = scope.querySelector('#pay-country');
    var payBtn = scope.querySelector('#pay-btn');
    var methods = scope.querySelector('#pay-methods');
    var secure = scope.querySelector('#pay-secure');
    var plan = 'month';
    // Paiement en ligne pas encore branché : le bouton ouvre WhatsApp avec un message prêt
    var wa = payBtn && payBtn.getAttribute('data-wa');
    var names = null;
    try { names = new Intl.DisplayNames([lang], { type: 'region' }); } catch (e) {}
    var countries = Object.keys(P.countries).map(function (c) { return { c: c, n: names ? names.of(c) : c }; });
    countries.sort(function (a, b) { return a.n.localeCompare(b.n, lang); });
    countries.forEach(function (o) {
      var opt = doc.createElement('option');
      opt.value = o.c;
      opt.textContent = o.n;
      select.appendChild(opt);
    });
    var s = Acct.get();
    select.value = (s && s.profile && s.profile.country && P.countries[s.profile.country]) ? s.profile.country : guessCountry();
    var render = function () {
      var code = currencyOf(select.value);
      var c = P.currencies[code];
      if (!c) return;
      $$('[data-price]', scope).forEach(function (el) { el.textContent = money(c[el.dataset.price], code, c.decimals); });
      $$('[data-perday]', scope).forEach(function (el) {
        var k = el.dataset.perday;
        var days = (P.plans[k] || { days: 1 }).days;
        el.textContent = fmt(T.per_day, { p: money(c[k] / days, code, c.decimals ? 2 : 0) });
      });
      var monthDay = c.month / (P.plans.month || { days: 30 }).days;
      $$('[data-save]', scope).forEach(function (el) {
        var k = el.dataset.save;
        var n = Math.round((1 - c[k] / (P.plans[k] || { days: 1 }).days / monthDay) * 100);
        el.hidden = !(n >= 5);
        el.textContent = fmt(T.save, { n: n });
      });
      $$('.plan', plansEl).forEach(function (b) {
        var on = b.dataset.plan === plan;
        b.classList.toggle('on', on);
        b.setAttribute('aria-checked', on);
      });
      if (wa) { payBtn.setAttribute('href', waLink()); return; }
      methods.textContent = methods.dataset[c.provider] || methods.textContent;
      secure.textContent = secure.dataset[c.provider] || secure.textContent;
      payBtn.querySelector('span').textContent = fmt(T.pay_btn, { p: money(c[plan], code, c.decimals) });
    };
    var waLink = function () {
      var code = currencyOf(select.value);
      var c = P.currencies[code] || {};
      var b = plansEl.querySelector('.plan[data-plan="' + plan + '"] b');
      var st = Acct.get();
      var u = st && st.user;
      var msg = fmt(T.wa_msg, {
        plan: b ? b.textContent.trim() : plan,
        price: c[plan] != null ? money(c[plan], code, c.decimals) : '',
        who: u ? [u.name, u.email].filter(Boolean).join(' · ') : '—'
      });
      return 'https://wa.me/' + wa + '?text=' + encodeURIComponent(msg);
    };
    plansEl.addEventListener('click', function (e) {
      var b = e.target.closest('.plan');
      if (!b) return;
      plan = b.dataset.plan;
      render();
    });
    select.addEventListener('change', function () {
      local.set('pb-country', select.value);
      var st = Acct.get();
      if (st && st.user) Acct.api.update({ country: select.value || null }).catch(noop);
      render();
    });
    var showStatus = function (st) {
      if (Acct.premium(st)) flash(scope, fmt(T.already_premium, { d: untilTxt(st) }));
    };
    showStatus(s);
    var q = params();
    if (q.paiement === 'annule') { flash(scope, T.pay_cancel, 'warn'); cleanUrl(); }
    payBtn.addEventListener('click', function (e) {
      var st = Acct.get();
      if (wa) {
        if (!st || !st.user) {
          e.preventDefault();
          toast(T.wa_need_signin);
          local.set('pb-next', location.pathname);
          router.go('compte.html');
          return;
        }
        payBtn.setAttribute('href', waLink());
        toast(T.wa_open);
        return;
      }
      if (!st || !st.user) {
        toast(T.need_signin);
        local.set('pb-next', location.pathname);
        router.go('compte.html');
        return;
      }
      payBtn.disabled = true;
      if (!Acct.demo) toast(T.pay_redirect);
      Acct.api.checkout(plan, select.value).then(function (r) {
        if (r && r.demo) {
          payBtn.disabled = false;
          flash(scope, fmt(T.demo_paid, { d: untilTxt(Acct.get()) }));
          win.scrollTo({ top: 0, behavior: reduced.matches ? 'auto' : 'smooth' });
        } else if (r && r.url) location.href = r.url;
        else throw new Error('checkout');
      }).catch(function () { payBtn.disabled = false; toast(T.error); });
    });
    render();
  };

  // ---------- Gratuit : 1 analyse complète par jour, avec un compte, sur le match choisi ----------
  // Le choix est gardé dans le profil (free_day, free_match) : il suit le compte sur tous ses appareils.
  var Free = {
    today: function () { return dayKey(new Date()); },
    // null : pas connecté ; sinon { m: match choisi aujourd'hui, ou null s'il reste à choisir }
    get: function () {
      var s = Acct.get();
      if (!s || !s.user) return null;
      var p = s.profile || {};
      return { m: p.free_day === Free.today() && p.free_match ? p.free_match : null };
    },
    // Matchs ouverts avec une analyse offerte (parrainage, cadeau), et analyses offertes restantes
    extra: function () { var s = Acct.get(); return (s && s.user && s.profile && s.profile.extra_matches) || []; },
    bonus: function () { var s = Acct.get(); return (s && s.user && s.profile && s.profile.bonus_analyses) || 0; },
    // Nom du match choisi (pour le lien « tu l'as utilisée sur … »), gardé sur le téléphone
    name: function (slug, name) {
      if (name) local.set('pb-free-name', JSON.stringify({ m: slug, n: name }));
      try { var o = JSON.parse(local.get('pb-free-name') || 'null'); return o && o.m === slug ? o.n : null; } catch (e) { return null; }
    }
  };
  var slugOf = function (href) { var r = /match\/([^\/?#]+)\.html/.exec(href || ''); return r ? r[1] : null; };
  var initFree = function (scope) {
    var card = scope.querySelector('#free-card');
    var app = card && card.closest('.app');
    var slug = card && card.dataset.slug;
    var busy = false;
    var use = function () {
      if (busy) return;
      busy = true;
      Acct.api.useFree(slug, Free.today()).then(function () {
        busy = false;
        var f = Free.get();
        if (f && f.m === slug) { Free.name(slug, card.dataset.name); toast(T.free_unlocked); }
        render();
      }, function () { busy = false; toast(T.error); });
    };
    var render = function () {
      var f = Free.get();
      var m = f && f.m;
      var ex = Free.extra();
      $$('a.mcard, a.featured, .pick', scope).forEach(function (a) {
        var link = a.matches('a') ? a : a.querySelector('a.pk-main');
        var sl = link && slugOf(link.getAttribute('href'));
        a.classList.toggle('free-ok', !!sl && ((!!m && sl === m) || ex.indexOf(sl) >= 0));
      });
      if (!card) return;
      var mine = !!m && m === slug;
      var extra = !mine && !!f && ex.indexOf(slug) >= 0;
      if (app) app.classList.toggle('free-ok', mine || extra);
      card.dataset.state = !f ? 'signin' : mine ? 'this' : extra ? 'extra' : m ? 'used' : 'new';
      var nb = Free.bonus();
      card.classList.toggle('has-bonus', nb > 0);
      var left = card.querySelector('[data-bonus-left]');
      if (left) left.textContent = fmt(nb === 1 ? T.bonus_left1 : T.bonus_leftN, { n: nb });
      if (m && !mine) {
        var a = card.querySelector('[data-free-link]');
        a.textContent = Free.name(m) || T.free_other;
        a.setAttribute('href', m + '.html');
      }
      // Retour après la connexion lancée depuis ce match : on le débloque directement
      if (f && !m && local.get('pb-free-want') === slug) { local.del('pb-free-want'); use(); }
    };
    render();
    Acct.on(render, function () { return card ? card.isConnected : scope !== doc && scope.isConnected; });
    if (!card) return;
    card.querySelector('#free-use').addEventListener('click', use);
    var bonusBtn = card.querySelector('#bonus-use');
    if (bonusBtn) bonusBtn.addEventListener('click', function () {
      if (busy) return;
      busy = true;
      bonusBtn.disabled = true;
      Acct.api.useBonus(slug).then(function () {
        busy = false;
        bonusBtn.disabled = false;
        toast(T.bonus_done);
        render();
      }, function () { busy = false; bonusBtn.disabled = false; toast(Free.bonus() > 0 ? T.error : T.bonus_none); });
    });
    card.querySelector('#free-signin').addEventListener('click', function () {
      local.set('pb-free-want', slug);
      local.set('pb-next', location.pathname);
      router.go(card.dataset.account);
    });
  };

  // =====================================================================================================
  // Chiffres protégés. La page publique n'a que des formes vides sous cadenas (<!--lk:N--> … <!--/lk-->) :
  // aucun chiffre Premium n'est dans le code de la page. Pour un compte qui y a droit, on demande les vrais
  // blocs au serveur (/lk/…), qui vérifie le compte auprès de Supabase avant de répondre, puis on les remet à
  // leur place. Rien n'est enregistré sur le téléphone (seulement gardé en mémoire quelques minutes).
  // =====================================================================================================
  var Lk = (function () {
    var mem = {};
    var memLvl = null;
    var retried = {};
    // '' : pas connecté ; 'p' : Premium ; 'f' ou 'f:<match>' : gratuit (avec l'analyse gratuite du jour)
    var level = function () {
      var s = Acct.get();
      if (!s || !s.user) return '';
      if (Acct.premium()) return 'p';
      var f = Free.get();
      var ex = Free.extra();
      return 'f' + (f && f.m ? ':' + f.m : '') + (ex.length ? '+' + ex.length + ':' + ex[ex.length - 1] : '');
    };
    var json = function (url) {
      var lvl = level();
      if (memLvl !== lvl) { mem = {}; memLvl = lvl; }
      var hit = mem[url];
      if (hit && Date.now() - hit.t < 5 * 60e3) return hit.p;
      var p = Acct.token().then(function (tok) {
        if (!tok) throw new Error('token');
        return fetch(url, { credentials: 'same-origin', cache: 'no-store', headers: { Authorization: 'Bearer ' + tok } });
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
      mem[url] = { p: p, t: Date.now() };
      p.catch(function () { if (mem[url] && mem[url].p === p) delete mem[url]; });
      return p;
    };
    var pageOf = function (path) {
      var rest = path.replace(/^\/[a-z]{2}(\/|$)/, '').replace(/\.html$/, '').replace(/\/$/, '');
      return rest || 'index';
    };
    // Les vrais blocs d'une page pour ce compte : { v: version du site, b: { n° du bloc: html } }, ou null
    var forPage = function (path) {
      var lvl = level();
      if (!lvl) return Promise.resolve(null);
      var pg = pageOf(path);
      var base = '/lk/' + lang + '/';
      if (lvl === 'p') {
        return json(base + pg + '.json').then(function (j) { return { v: j.v, b: j.b || {} }; }, function () { return null; });
      }
      var f = Free.get();
      var parts = [json(base + 'free.json').catch(function () { return null; })];
      if (f && f.m) parts.push(json(base + 'm/' + f.m + '.json').catch(function () { return null; }));
      // Page d'un match ouvert avec une analyse offerte
      var mm = /^match\/([a-z0-9-]+)$/.exec(pg);
      if (mm && (!f || mm[1] !== f.m) && Free.extra().indexOf(mm[1]) >= 0) {
        parts.push(json(base + 'm/' + mm[1] + '.json').catch(function () { return null; }));
      }
      return Promise.all(parts).then(function (all) {
        var out = { v: null, b: {} };
        all.forEach(function (j) {
          if (!j) return;
          out.v = out.v || j.v;
          Object.assign(out.b, (j.p || {})[pg] || {});
        });
        return out.v ? out : null;
      });
    };
    // Données du constructeur de coupons : tous les matchs (Premium), le match de l'analyse gratuite, ou rien
    var ticket = function (src) {
      var lvl = level();
      if (lvl === 'p') return json(src);
      var f = Free.get();
      // Le match du jour et les 10 derniers matchs ouverts avec une analyse offerte (ceux déjà joués n'existent plus)
      var slugs = (f && f.m ? [f.m] : []).concat(Free.extra().slice(-10).reverse())
        .filter(function (x, i, a) { return a.indexOf(x) === i; });
      if (!slugs.length) return Promise.resolve({ matches: [], limited: lvl ? 'none' : 'anon' });
      return Promise.all(slugs.map(function (sl) {
        return json('/lk/' + lang + '/m/' + sl + '.json').then(function (j) { return j.tk || null; }, function () { return null; });
      })).then(function (all) {
        var ms = all.filter(Boolean);
        return { matches: ms, limited: ms.length ? 'free' : 'none' };
      });
    };
    var marks = function (root) {
      var out = [];
      if (!root) return out;
      var w = doc.createTreeWalker(root, 128);  // NodeFilter.SHOW_COMMENT
      var n;
      while ((n = w.nextNode())) if (n.data.slice(0, 3) === 'lk:') out.push(n);
      return out;
    };
    var has = function (root) { return marks(root).length > 0; };
    // Remet les vrais blocs. false si la page et les blocs ne viennent pas de la même version du site.
    var apply = function (app, fr) {
      if (!fr || !fr.b || !app) return true;
      if (app.dataset.v && fr.v && app.dataset.v !== fr.v) return false;
      marks(app).forEach(function (c) {
        var html = fr.b[c.data.slice(3)];
        if (html == null) return;
        var old = [];
        var n = c.nextSibling;
        while (n && !(n.nodeType === 8 && n.data === '/lk')) { old.push(n); n = n.nextSibling; }
        if (!n) return;
        var tpl = doc.createElement('template');
        tpl.innerHTML = html;
        old.forEach(function (x) { x.parentNode.removeChild(x); });
        n.parentNode.insertBefore(tpl.content, n);
      });
      return true;
    };
    // Page d'une autre version (gardée sur le téléphone) : on la recharge une fois
    var stale = function () {
      var k = location.pathname;
      mem = {};
      if (retried[k]) return;
      retried[k] = 1;
      setTimeout(function () { router.reload(); }, 30);
    };
    // Premier affichage : on attend un peu les vrais blocs avant de préparer la page, sinon on la recharge à leur arrivée
    var boot = function (start) {
      var app0 = doc.querySelector('.app');
      if (!level() || !has(app0)) { start(); return; }
      var done = false;
      var run = function () { if (app0.isConnected) start(); };
      var t = setTimeout(function () { done = true; run(); }, 1500);
      forPage(location.pathname).then(function (fr) {
        if (!done) {
          done = true;
          clearTimeout(t);
          if (fr && !apply(app0, fr)) stale();
          run();
        } else if (fr && app0.isConnected) router.reload();
      });
    };
    // Compte changé (connexion, Premium, analyse gratuite choisie, déconnexion) : la page est reconstruite
    var lastLvl = level();
    Acct.on(function () {
      var l = level();
      if (l === lastLvl) return;
      lastLvl = l;
      mem = {};
      if (has(doc.querySelector('.app'))) router.reload();
    }, function () { return true; });
    return { level: level, forPage: forPage, ticket: ticket, apply: apply, stale: stale, boot: boot };
  })();

  // =====================================================================================================
  // Ticket : enregistré sur le téléphone, rempli depuis l'onglet Paris, les pages de match et l'onglet Ticket
  // =====================================================================================================
  var MARGIN = 0.05;     // marge moyenne d'un bookmaker sur un marché classique
  var MAX_LEGS = 10;
  var FREE_LEGS = 3;
  var TIER_RANGE = { safe: [0.68, 0.80], balanced: [0.55, 0.68], bold: [0.36, 0.50] };
  var FAM = { '1x2': 'result', dc: 'dc', dnb: 'result', ou: 'goals', btts: 'btts', tt1: 'team', tt2: 'team', co: 'corners', ca: 'cards' };
  var bySafe = function (a, b) { return b.p - a.p; };  // du plus sûr au moins sûr
  var nf2 = new Intl.NumberFormat(loc, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  var oddsTxt = function (x) { return nf2.format(x); };
  var pctTxt = function (p) {
    var v = Math.round(Math.min(p, 0.99) * 100);
    if (p > 0 && v < 1) return lang === 'fr' ? '<1 %' : '<1%';
    return lang === 'fr' ? v + ' %' : v + '%';
  };
  var timesTxt = function (p) {
    if (p >= 0.095) return fmt(T.tk_times, { n: Math.max(1, Math.min(9, Math.round(p * 10))) });
    return fmt(T.tk_times100, { n: Math.max(1, Math.round(p * 100)) });
  };
  // « Sur 10 tickets comme celui-ci, environ 2 passent et 8 perdent » : le vrai chiffre du ticket, pas un exemple
  var explainTxt = function (p) {
    var win = function (n) { return n > 1 ? T.tk_winN : T.tk_win1; };
    if (p >= 0.095) {
      var w = Math.max(1, Math.min(9, Math.round(p * 10))), l = 10 - w;
      return fmt(T.tk_explain10, { w: w, l: l, wv: win(w), lv: l > 1 ? T.tk_loseN : T.tk_lose1 });
    }
    var h = Math.max(1, Math.round(p * 100));
    return fmt(T.tk_explain100, { w: h, wv: win(h) });
  };
  var esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  var svg = function (d, size, sw) {
    return '<svg class="ic" width="' + size + '" height="' + size + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="' +
      sw + '" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">' + d + '</svg>';
  };
  var IC_X = svg('<path d="M6 6l12 12M18 6 6 18"/>', 18, 2.6);
  var IC_PLUS = svg('<path d="M12 5v14M5 12h14"/>', 18, 2.6);
  var IC_STAR = svg('<path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3l-5.6 2.9 1.1-6.2L3 9.6l6.2-.9Z"/>', 14, 2.2);
  var RING_C = 2 * Math.PI * 23;
  var ringHtml = function (p, cls) {
    var shown = Math.min(p, 0.99);
    return '<span class="ring' + (cls ? ' ' + cls : '') + '"><svg width="54" height="54" viewBox="0 0 54 54" aria-hidden="true">' +
      '<circle class="trk" cx="27" cy="27" r="23" fill="none" stroke-width="6"/><circle class="val" cx="27" cy="27" r="23" fill="none" ' +
      'stroke-width="6" stroke-linecap="round" stroke-dasharray="' + (RING_C * shown).toFixed(1) + ' ' + RING_C.toFixed(1) +
      '" transform="rotate(-90 27 27)"/></svg><b>' + pctTxt(p) + '</b></span>';
  };
  var whenTxt = function (ko) { var d = new Date(ko); return shortDay(d) + ' ' + F.time.format(d); };

  var Coupon = {
    KEY: 'pb-coupon',
    fns: [],
    get: function () {
      var legs = [];
      try { legs = JSON.parse(local.get(Coupon.KEY) || '[]'); } catch (e) {}
      if (!Array.isArray(legs)) return [];
      var old = Date.now() - 3 * 864e5;  // matchs joués il y a plus de 3 jours : retirés tout seuls
      return legs.filter(function (l) { return l && l.id && l.mid && l.p > 0 && new Date(l.ko).getTime() > old; });
    },
    set: function (legs) { local.set(Coupon.KEY, JSON.stringify(legs)); Coupon.badge(); Coupon.emit(); },
    has: function (id) { return Coupon.get().some(function (l) { return l.id === id; }); },
    add: function (leg) {
      if (new Date(leg.ko).getTime() <= Date.now()) { toast(T.tk_started); return false; }
      var legs = Coupon.get();
      var i = legs.map(function (l) { return l.mid; }).indexOf(leg.mid);
      if (i >= 0) {  // un seul pari par match : le nouveau remplace l'ancien
        legs[i] = leg;
        Coupon.set(legs);
        toast(fmt(T.tk_replaced, { n: legs.length }));
        return true;
      }
      if (legs.length >= MAX_LEGS) { toast(T.tk_full); return false; }
      legs.push(leg);
      Coupon.set(legs);
      toast(fmt(T.tk_added, { n: legs.length }));
      return true;
    },
    remove: function (id, quiet) {
      Coupon.set(Coupon.get().filter(function (l) { return l.id !== id; }));
      if (!quiet) toast(T.tk_removed);
    },
    load: function (legs) {
      var now = Date.now();
      Coupon.set(legs.filter(function (l) { return new Date(l.ko).getTime() > now; }).slice(0, MAX_LEGS));
      toast(T.tk_loaded);
    },
    badge: function () {
      var n = Coupon.get().length;
      $$('.tabbar a[data-tab="ticket"]').forEach(function (a) {
        if (n) a.setAttribute('data-count', n); else a.removeAttribute('data-count');
      });
    },
    on: function (fn, alive) { Coupon.fns.push({ fn: fn, alive: alive }); },
    emit: function () {
      Coupon.fns = Coupon.fns.filter(function (l) { return l.alive(); });
      Coupon.fns.forEach(function (l) { l.fn(); });
    },
    stats: function (legs) {
      var p = 1, fair = 1;
      legs.forEach(function (l) { p *= l.p; fair *= l.fair; });
      return { p: p, fair: fair, book: fair / Math.pow(1 + MARGIN, legs.length) };
    }
  };
  win.addEventListener('storage', function (e) { if (e.key === Coupon.KEY) { Coupon.badge(); Coupon.emit(); } });

  var markAdded = function (scope) {
    var ids = Coupon.get().map(function (l) { return l.id; });
    $$('button[data-add]', scope).forEach(function (b) {
      var on = ids.indexOf(b.dataset.id) >= 0;
      b.classList.toggle('in', on);
      b.setAttribute('aria-pressed', on);
    });
  };

  // Boutons « + » (un pari) et « Mettre dans mon ticket » (un coupon entier), partout sur le site
  doc.addEventListener('click', function (e) {
    var b = e.target.closest('button[data-add]');
    if (b) {
      e.preventDefault();
      var leg;
      try { leg = JSON.parse(b.dataset.add); } catch (err) { return; }
      if (Coupon.has(leg.id)) Coupon.remove(leg.id); else Coupon.add(leg);
      return;
    }
    var c = e.target.closest('button[data-legs]');
    if (c) {
      e.preventDefault();
      try { Coupon.load(JSON.parse(c.dataset.legs)); } catch (err) {}
    }
  });

  // ---------- Calcul des coupons (mêmes règles que probalis/site/picks.py) ----------
  var candsOf = function (m) {
    return m.c.map(function (c) {
      return { id: m.id + '|' + c[0] + '|' + (c[1] == null ? '' : c[1]) + '|' + c[2], mid: m.id, key: c[0], line: c[1], sel: c[2],
        p: c[3], fair: c[4], l: c[5], m: c[6], h: m.h, a: m.a, ko: m.k, s: m.s };
    });
  };
  var openMatches = function (data, day) {
    var now = Date.now();
    return data.matches.filter(function (m) { return (!day || m.d === day) && new Date(m.k).getTime() > now; });
  };
  // keep : filtre des paris (types, cote minimale) ; free : pas de limite par type (l'utilisateur a choisi ses types)
  var tierPicks = function (ms, range, n, keep, free) {
    var pool = [];
    ms.forEach(function (m) {
      if (!m.e) return;
      candsOf(m).forEach(function (c) {
        if (c.p >= range[0] && c.p <= range[1] && (!keep || keep(c))) {
          pool.push({ s: c.p + (m.q === 'high' ? 0.015 : 0) - (c.sel === '12' ? 0.01 : 0), c: c });
        }
      });
    });
    pool.sort(function (a, b) { return b.s - a.s; });
    var used = {}, fam = {}, out = [], max = free ? n : Math.max(2, Math.ceil(n * 0.4));
    for (var i = 0; i < pool.length && out.length < n; i++) {
      var c = pool[i].c, f = FAM[c.key];
      if (used[c.mid] || (fam[f] || 0) >= max) continue;
      used[c.mid] = 1;
      fam[f] = (fam[f] || 0) + 1;
      out.push(c);
    }
    return out.sort(bySafe);
  };
  // Coupon de k matchs dont la cote bookmaker estimée tombe près de la cible, avec des sélections équilibrées
  var buildCoupon = function (pool, target, k, conf) {
    var mids = {};
    pool.forEach(function (c) { mids[c.mid] = 1; });
    if (Object.keys(mids).length < k) return null;
    var goal = Math.log(target * 1.04);
    var lf = Math.log(Math.pow(target * 1.04 * Math.pow(1 + MARGIN, k), 1 / k));
    var lc = pool.map(function (c) {
      var d = Math.log(c.fair) - lf;
      return d * d + (conf[c.mid] !== 'high' ? 0.02 : 0) + (c.sel === '12' ? 0.03 : 0);
    });
    var lfair = pool.map(function (c) { return Math.log(c.fair); });
    var best = {};
    pool.forEach(function (c, i) { if (best[c.mid] === undefined || lc[i] < lc[best[c.mid]]) best[c.mid] = i; });
    var legs = Object.keys(best).map(function (m) { return best[m]; }).sort(function (a, b) { return lc[a] - lc[b]; }).slice(0, k);
    var famCount = function (idx) { var f = {}; idx.forEach(function (i) { var x = FAM[pool[i].key]; f[x] = (f[x] || 0) + 1; }); return f; };
    var costOf = function (tot, lcs, dup) { return 6 * Math.abs(tot - k * Math.log(1 + MARGIN) - goal) + lcs + 0.04 * dup; };
    var tot = 0, lcs = 0;
    legs.forEach(function (i) { tot += lfair[i]; lcs += lc[i]; });
    var fams = famCount(legs);
    var dupOf = function (f) { var d = 0; Object.keys(f).forEach(function (x) { if (f[x] > 1) d += f[x] - 1; }); return d; };
    var cur = costOf(tot, lcs, dupOf(fams));
    for (var it = 0; it < 60; it++) {
      var imp = null;
      for (var a = 0; a < k; a++) {
        var i0 = legs[a], f0 = FAM[pool[i0].key];
        var others = {};
        legs.forEach(function (i, j) { if (j !== a) others[pool[i].mid] = 1; });
        var baseDup = dupOf(fams) - ((fams[f0] || 0) > 1 ? 1 : 0);
        for (var q = 0; q < pool.length; q++) {
          if (q === i0 || others[pool[q].mid]) continue;
          var fq = FAM[pool[q].key];
          var cntq = (fams[fq] || 0) - (fq === f0 ? 1 : 0);
          var dup = baseDup + (cntq >= 1 ? 1 : 0);
          var t = costOf(tot - lfair[i0] + lfair[q], lcs - lc[i0] + lc[q], dup);
          if (t < cur - 1e-9 && (!imp || t < imp[0])) imp = [t, a, q];
        }
      }
      if (!imp) break;
      var old = legs[imp[1]];
      tot += lfair[imp[2]] - lfair[old];
      lcs += lc[imp[2]] - lc[old];
      legs[imp[1]] = imp[2];
      fams = famCount(legs);
      cur = imp[0];
    }
    var out = legs.map(function (i) { return pool[i]; });
    var st = Coupon.stats(out);
    if (st.book < 0.9 * target || st.book > 1.35 * target) return null;
    return out.sort(bySafe);
  };
  // Le moins de matchs possible, avec chaque sélection à 50 % ou plus
  var autoCoupon = function (ms, target, keep) {
    var pool = [], conf = {};
    ms.forEach(function (m) {
      if (!m.e) return;
      conf[m.id] = m.q;
      candsOf(m).forEach(function (c) { if (c.p >= 0.4 && c.p <= 0.9 && (!keep || keep(c))) pool.push(c); });
    });
    var chosen = null;
    for (var k = 2; k <= MAX_LEGS; k++) {
      var legs = buildCoupon(pool, target, k, conf);
      if (!legs) continue;
      chosen = legs;
      if (Math.min.apply(null, legs.map(function (c) { return c.p; })) >= 0.5) break;
    }
    return chosen;
  };
  var legOf = function (c) {
    return { id: c.id, mid: c.mid, key: c.key, line: c.line, sel: c.sel, p: c.p, fair: c.fair, l: c.l, m: c.m, h: c.h, a: c.a, ko: c.ko, s: c.s };
  };
  // « À cote égale, moins de matchs = plus de chance » : chance d'un coupon de cote bookmaker B en k matchs
  var sameOdds = function (book, current) {
    var rows = '';
    var ks = [2, 3, 5, 8, 10];
    if (current > 1 && ks.indexOf(current) < 0) ks.push(current);
    ks.sort(function (a, b) { return a - b; }).forEach(function (k) {
      var p = 1 / (book * Math.pow(1 + MARGIN, k));
      rows += '<li' + (k === current ? ' class="on"' : '') + '><span>' + fmt(T.tk_k, { k: k }) + '</span><i class="meter"><i class="' +
        (p >= 0.5 ? 'hi' : p >= 0.3 ? 'mid' : '') + '" style="width: ' + (Math.min(p, 1) * 100).toFixed(1) + '%"></i></i><b>' + pctTxt(p) + '</b></li>';
    });
    return rows;
  };

  var TData = {
    p: null,
    lvl: null,
    get: function (src) {
      var lvl = Lk.level();
      if (TData.lvl !== lvl) { TData.p = null; TData.lvl = lvl; }
      if (!TData.p) {
        TData.p = Lk.ticket(src);
        TData.p.catch(function () { TData.p = null; });
      }
      return TData.p;
    }
  };

  // ---------- Onglet Paris : jour, niveau, boutons « + » ----------
  var initBets = function (scope) {
    var daysEl = scope.querySelector('#pdays');
    if (!daysEl) return;
    var pills = $$('.day', daysEl);
    var secs = $$('.pday', scope);
    var tiersEl = scope.querySelector('#ptiers');
    var tierBtns = $$('button', tiersEl);
    var famsEl = scope.querySelector('#pfams');
    var famBtns = famsEl ? $$('button[data-fam]', famsEl) : [];
    var FAMS = famBtns.map(function (b) { return b.dataset.fam; });
    var today = dayKey(new Date());
    var now = Date.now();
    $$('.pick[data-ko], .dc-legs li[data-ko]', scope).forEach(function (el) {
      if (new Date(el.dataset.ko).getTime() <= now) el.classList.add('started');
    });
    $$('button[data-add]', scope).forEach(function (b) {
      try { b.dataset.id = JSON.parse(b.dataset.add).id; } catch (e) {}
    });
    pills.forEach(function (p) {
      var d = p.dataset.day;
      p.hidden = d < today;
      p.querySelector('small').textContent = d === today ? T.today : cap(F.wd.format(fromKey(d)));
    });
    var keys = pills.filter(function (p) { return !p.hidden; }).map(function (p) { return p.dataset.day; });
    if (!keys.length) keys = pills.slice(-1).map(function (p) { p.hidden = false; return p.dataset.day; });
    var open = function (k) {
      var sec = secs.filter(function (s) { return s.dataset.day === k; })[0];
      return !!sec && $$('.pick, .dc-legs li', sec).some(function (el) { return !el.classList.contains('started'); });
    };
    var saved = session.get('pday');
    var state = {
      day: keys.indexOf(saved) >= 0 ? saved : (keys.filter(open)[0] || keys[0]),
      tier: TIER_RANGE[session.get('ptier')] ? session.get('ptier') : 'safe',
      fam: FAMS.indexOf(session.get('pfam')) >= 0 ? session.get('pfam') : 'all'
    };
    var render = function () {
      pills.forEach(function (p) {
        var on = p.dataset.day === state.day;
        p.classList.toggle('on', on);
        p.setAttribute('aria-pressed', on);
      });
      secs.forEach(function (s) { s.classList.toggle('on', s.dataset.day === state.day); });
      tierBtns.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.tier === state.tier); });
      $$('.plist', scope).forEach(function (l) { l.classList.toggle('on', l.dataset.tier === state.tier); });
      famBtns.forEach(function (b) {
        var on = b.dataset.fam === state.fam;
        b.classList.toggle('on', on);
        b.setAttribute('aria-pressed', on);
      });
      $$('.pfam', scope).forEach(function (l) { l.classList.toggle('on', l.dataset.fam === state.fam); });
      // « Le n° 1 de chaque liste » ne concerne que « Tous » (les listes par type sont Premium)
      $$('.list-lock', scope).forEach(function (l) { l.classList.toggle('fam-hide', state.fam !== 'all'); });
      session.set('pday', state.day);
      session.set('ptier', state.tier);
      session.set('pfam', state.fam);
    };
    daysEl.addEventListener('click', function (e) {
      var p = e.target.closest('.day');
      if (!p) return;
      state.day = p.dataset.day;
      render();
    });
    tiersEl.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-tier]');
      if (!b) return;
      state.tier = b.dataset.tier;
      render();
    });
    if (famsEl) famsEl.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-fam]');
      if (!b) return;
      state.fam = b.dataset.fam;
      render();
    });
    render();
    var fon = famBtns.filter(function (b) { return b.dataset.fam === state.fam; })[0];
    if (fon && famsEl) {
      famsEl.scrollLeft = Math.max(0, fon.getBoundingClientRect().left - famsEl.getBoundingClientRect().left - 20);
    }
    var on = pills.filter(function (p) { return p.classList.contains('on'); })[0];
    if (on) daysEl.scrollLeft = Math.max(0, on.offsetLeft - 20);
    markAdded(scope);
    Coupon.on(function () { markAdded(scope); }, function () { return daysEl.isConnected; });
  };

  // ---------- Page d'un match : « Ajouter au ticket » à côté de « Compare ta cote » ----------
  var initMatchAdd = function (scope) {
    var btn = scope.querySelector('#cmp-add');
    if (!btn) return;
    var data = {};
    try { data = JSON.parse(scope.querySelector('#cmp-data').textContent); } catch (e) { return; }
    var select = scope.querySelector('#cmp-sel');
    var sync = function () {
      var id = select.value;
      var it = data.items && data.items[id];
      if (!it) { btn.removeAttribute('data-add'); return; }
      var parts = id.split('|');
      var line = parts[1] === 'None' ? null : parseFloat(parts[1]);
      var opt = select.options[select.selectedIndex];
      var leg = { id: data.mid + '|' + parts[0] + '|' + (line == null ? '' : line) + '|' + parts[2], mid: data.mid, key: parts[0], line: line,
        sel: parts[2], p: it.p, fair: it.fair, l: opt ? opt.textContent : '', m: opt && opt.parentNode.label || '', h: data.h, a: data.a,
        ko: data.ko, s: data.s };
      btn.dataset.add = JSON.stringify(leg);
      btn.dataset.id = leg.id;
      markAdded(scope);
    };
    btn.hidden = new Date(data.ko).getTime() <= Date.now();
    select.addEventListener('change', sync);
    sync();
    Coupon.on(function () { markAdded(scope); }, function () { return btn.isConnected; });
  };

  // ---------- Onglet Ticket ----------
  var initTicket = function (scope) {
    var box = scope.querySelector('#tk');
    if (!box) return;
    var src = box.dataset.src;
    var $ = function (s) { return box.querySelector(s); };
    var modes = $$('#tk-modes button', box);
    var panels = $$('.tk-panel', box);
    var alive = function () { return box.isConnected; };
    var mode = session.get('tkmode');
    if (mode === 'target' || mode === 'count') mode = 'gen';  // anciens modes, réunis dans le générateur
    if (['mine', 'gen'].indexOf(mode) < 0) mode = 'mine';
    var showMode = function () {
      modes.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.mode === mode); });
      panels.forEach(function (p) { p.hidden = p.dataset.panel !== mode; });
      session.set('tkmode', mode);
      if (mode !== 'mine' && Acct.premium()) prepAuto();
    };
    $('#tk-modes').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-mode]');
      if (!b) return;
      mode = b.dataset.mode;
      showMode();
    });

    // --- Jours proposés (à partir des matchs à venir) ---
    var fillDays = function (sel, data) {
      var today = dayKey(new Date());
      var tom = dayKey(new Date(Date.now() + 864e5));
      var days = [];
      openMatches(data).forEach(function (m) { if (days.indexOf(m.d) < 0) days.push(m.d); });
      days.sort();
      var keep = sel.value;
      sel.innerHTML = days.map(function (d) {
        var lbl = d === today ? T.tk_today : d === tom ? T.tk_tomorrow : cap(F.long.format(fromKey(d)));
        return '<option value="' + d + '">' + esc(lbl) + '</option>';
      }).join('');
      if (days.indexOf(keep) >= 0) sel.value = keep;
      return days;
    };
    var withData = function (fn, out) {
      if (out) out.innerHTML = '<p class="note">' + esc(T.tk_loading) + '</p>';
      TData.get(src).then(function (d) { if (alive()) { if (out) out.innerHTML = ''; fn(d); } }, function () {
        if (out && alive()) out.innerHTML = '<p class="empty">' + esc(T.tk_load_err) + '</p>';
      });
    };

    // --- Mon coupon : liste ---
    var legsEl = $('#tk-legs');
    var emptyEl = $('#tk-empty');
    var an = $('#tk-an');
    var lockMore = $('#tk-lock-more');
    var weakEl = $('#tk-weak');
    var oddsIn = $('#tk-odds');
    var verdict = $('#tk-verdict');
    var weakId = null;
    var legHtml = function (l, weak) {
      var started = new Date(l.ko).getTime() <= Date.now();
      return '<div class="tleg' + (weak ? ' weak' : '') + (started ? ' started' : '') + '">' +
        '<span class="tl-txt"><b>' + esc(l.l) + '</b><small>' + esc(l.m) + '</small><span class="tl-match">' + esc(l.h + ' – ' + l.a) +
        ' · ' + esc(whenTxt(l.ko)) + (started ? ' · ' + esc(T.tk_started_short) : '') + '</span></span>' +
        '<span class="tl-p">' + pctTxt(l.p) + '</span>' +
        '<button class="tl-x" type="button" data-remove="' + esc(l.id) + '" aria-label="' + esc(T.tk_remove + T.colon + l.l) + '" title="' +
        esc(T.tk_remove) + '">' + IC_X + '</button></div>';
    };
    var renderVerdict = function (st) {
      var raw = oddsIn.value.trim().replace(',', '.');
      if (!raw) { verdict.hidden = true; return; }
      var odds = parseFloat(raw);
      var kind, msg;
      if (!isFinite(odds) || odds <= 1 || !/^\d+(\.\d*)?$/.test(raw)) {
        kind = 'warn';
        msg = '<b>' + T.v_invalid + '</b>' + T.colon + T.v_invalid_txt;
      } else {
        var r = odds / st.fair;
        kind = r >= 1.02 ? 'good' : r >= 0.98 ? 'fair' : 'bad';
        msg = '<b>' + T['v_' + kind] + '</b>' + T.colon +
          fmt(T['v_' + kind + '_txt'], { odds: oddsTxt(odds), fair: oddsTxt(st.fair), m: pctTxt(1 - r) }) + ' ' + T.v_note;
      }
      verdict.className = 'verdict ' + kind;
      verdict.querySelector('.v-txt').innerHTML = msg;
      verdict.hidden = false;
    };
    var renderWeak = function (legs, st) {
      weakEl.hidden = legs.length < 2;
      if (legs.length < 2) return;
      var w = legs.reduce(function (a, b) { return b.p < a.p ? b : a; });
      var drop = { p: st.p / w.p, book: st.book / (w.fair / (1 + MARGIN)) };
      weakEl.querySelector('.wk-txt').innerHTML = esc(fmt(T.tk_weak, { l: w.l + ' (' + w.h + ' – ' + w.a + ')', p: pctTxt(w.p) })) + ' ' +
        esc(fmt(T.tk_drop, { c: pctTxt(drop.p), o: oddsTxt(drop.book) }));
      var swapEl = weakEl.querySelector('.wk-swap');
      swapEl.hidden = true;
      TData.get(src).then(function (data) {
        if (!alive()) return;
        var m = data.matches.filter(function (x) { return x.id === w.mid; })[0];
        if (!m) return;
        var alt = candsOf(m).filter(function (c) { return c.p > w.p + 0.05 && c.p <= 0.86 && c.fair >= 1.12; })
          .sort(function (a, b) { return b.p - a.p; })[0];
        if (!alt) return;
        var np = st.p / w.p * alt.p;
        var nb = st.book / w.fair * alt.fair;
        swapEl.querySelector('span').textContent = fmt(T.tk_swap, { l: alt.l, p: pctTxt(alt.p), c: pctTxt(np), o: oddsTxt(nb) });
        var b = swapEl.querySelector('button');
        b.dataset.add = JSON.stringify(legOf(alt));
        b.dataset.id = alt.id;
        swapEl.hidden = false;
      }, noop);
    };
    var renderMine = function () {
      var legs = Coupon.get();
      var st = Coupon.stats(legs);
      var weak = legs.length >= 2 ? legs.reduce(function (a, b) { return b.p < a.p ? b : a; }).id : null;
      legsEl.innerHTML = legs.slice().sort(bySafe).map(function (l) { return legHtml(l, l.id === weak); }).join('');
      emptyEl.hidden = !!legs.length;
      $('#tk-clear').hidden = !legs.length;
      $('#tk-share').hidden = !legs.length;
      an.hidden = !legs.length;
      if (!legs.length) return;
      var over = !Acct.premium() && legs.length > FREE_LEGS;
      an.classList.toggle('over', over);
      lockMore.hidden = !over;
      $('#tk-ring').innerHTML = ringHtml(st.p, 'big');
      $('#tk-times').textContent = timesTxt(st.p);
      $('#tk-explain').textContent = explainTxt(st.p);
      $('#tk-count').textContent = legs.length === 1 ? T.tk_1 : fmt(T.tk_n, { n: legs.length });
      $('#tk-fair').textContent = oddsTxt(st.fair);
      $('#tk-book').textContent = '≈ ' + oddsTxt(st.book);
      $('#tk-same').innerHTML = sameOdds(st.book, legs.length);
      $('#tk-same-box').hidden = legs.length < 2;
      renderVerdict(st);
      if (weak !== weakId || !legs.length) weakId = weak;
      renderWeak(legs, st);
    };
    legsEl.addEventListener('click', function (e) {
      var x = e.target.closest('[data-remove]');
      if (x) Coupon.remove(x.dataset.remove);
    });
    $('#tk-clear').addEventListener('click', function () { Coupon.set([]); toast(T.tk_cleared); });
    oddsIn.addEventListener('input', function () { renderVerdict(Coupon.stats(Coupon.get())); });
    $('#tk-share').addEventListener('click', function () {
      var legs = Coupon.get();
      if (!legs.length) return;
      var st = Coupon.stats(legs);
      var lines = [T.tk_share_head];
      legs.forEach(function (l, i) { lines.push((i + 1) + '. ' + l.h + ' – ' + l.a + T.colon + l.l + ' (' + pctTxt(l.p) + ')'); });
      lines.push(fmt(T.tk_share_chance, { p: pctTxt(st.p), f: oddsTxt(st.fair) }));
      lines.push(location.origin + '/' + lang + '/');
      var text = lines.join('\n');
      if (navigator.share) navigator.share({ text: text }).catch(noop);
      else win.open('https://wa.me/?text=' + encodeURIComponent(text), '_blank', 'noopener');
    });

    // --- Mon coupon : ajouter un pari depuis la liste des matchs ---
    var picker = $('#tk-picker');
    var daySel = $('#tk-day'), matchSel = $('#tk-match'), betSel = $('#tk-bet'), betInfo = $('#tk-bet-info');
    var pdata = null, pcands = [];
    var fillMatches = function () {
      var ms = openMatches(pdata, daySel.value);
      matchSel.innerHTML = ms.map(function (m) {
        return '<option value="' + esc(m.id) + '">' + esc(F.time.format(new Date(m.k)) + ' · ' + m.h + ' – ' + m.a + ' (' + m.lg + ')' +
          (m.q === 'low' ? ' · ' + T.tk_low : '')) + '</option>';
      }).join('');
      fillBets();
    };
    var fillBets = function () {
      var m = pdata.matches.filter(function (x) { return x.id === matchSel.value; })[0];
      pcands = m ? candsOf(m) : [];
      var groups = [], html = '';
      pcands.forEach(function (c, i) {
        var g = groups.filter(function (x) { return x.t === c.m; })[0];
        if (!g) { g = { t: c.m, o: [] }; groups.push(g); }
        g.o.push('<option value="' + i + '">' + esc(c.l + (Acct.premium() ? ' — ' + pctTxt(c.p) : '')) + '</option>');
      });
      groups.forEach(function (g) { html += '<optgroup label="' + esc(g.t) + '">' + g.o.join('') + '</optgroup>'; });
      betSel.innerHTML = html;
      showBet();
    };
    var showBet = function () {
      var c = pcands[+betSel.value];
      betInfo.textContent = c && Acct.premium() ? fmt(T.chance, { p: pctTxt(c.p), fair: oddsTxt(c.fair) }) : '';
    };
    $('#tk-open').addEventListener('click', function () {
      picker.hidden = !picker.hidden;
      if (picker.hidden || pdata) return;
      withData(function (d) {
        pdata = d;
        var lim = $('#tk-limit');
        if (lim) {
          lim.hidden = !d.limited;
          lim.textContent = d.limited ? T['tk_lim_' + d.limited] : '';
        }
        fillDays(daySel, d);
        fillMatches();
      });
    });
    daySel.addEventListener('change', fillMatches);
    matchSel.addEventListener('change', fillBets);
    betSel.addEventListener('change', showBet);
    $('#tk-add').addEventListener('click', function () {
      var c = pcands[+betSel.value];
      if (c) Coupon.add(legOf(c));
    });

    // --- Générateur (Premium) : un ou plusieurs jours, nombre de matchs ou cote visée, filtres ---
    var autoReady = false;
    var couponCard = function (legs, out, sub, none) {
      if (!legs || !legs.length) { out.innerHTML = '<p class="empty">' + esc(none || T.tk_none) + '</p>'; return; }
      var st = Coupon.stats(legs);
      out.innerHTML = '<article class="dcoupon">' +
        '<div class="dc-head"><span class="dc-target">≈ ' + oddsTxt(st.book) + '</span><span class="dc-meta">' +
        esc((legs.length === 1 ? T.tk_1 : fmt(T.tk_n, { n: legs.length })) + ' · ' + fmt(T.tk_kc, { p: pctTxt(st.p) })) + '</span></div>' +
        (sub ? '<p class="dc-per">' + esc(sub) + '</p>' : '') +
        '<ol class="dc-legs">' + legs.map(function (c) {
          return '<li><span class="dc-l"><b>' + esc(c.l) + '</b><small>' + esc(c.h + ' – ' + c.a + ' · ' + whenTxt(c.ko)) + '</small></span>' +
            '<span class="dc-p">' + pctTxt(c.p) + '</span></li>';
        }).join('') + '</ol>' +
        '<div class="dc-foot"><span class="dc-odds"><small>' + esc(T.tk_book) + '</small><b>≈ ' + oddsTxt(st.book) + '</b><small>' +
        esc(T.tk_fair + ' ' + oddsTxt(st.fair) + ' · ' + timesTxt(st.p)) + '</small></span>' +
        '<button class="btn dc-load" type="button" data-legs="' + esc(JSON.stringify(legs.map(legOf))) + '">' + IC_PLUS + esc(T.tk_use) + '</button></div>' +
        '<div class="same-box"><h3>' + esc(T.tk_same_title) + '</h3><p>' + esc(T.tk_same_text) + '</p><ul class="same">' +
        sameOdds(st.book, legs.length) + '</ul></div></article>';
    };
    var gen = $('#gen');
    var gout = $('#gen-out');
    // Types de pari du générateur -> familles (FAM)
    var GFAM = { result: ['result', 'dc'], goals: ['goals'], btts: ['btts'], team: ['team'], corners: ['corners'], cards: ['cards'] };
    var G = { per: '', from: '', to: '', goal: 'count', n: 3, tier: 'safe', odds: '3', lcs: [], fams: [], min: 0, favs: false };
    try {
      var g0 = JSON.parse(session.get('tkgen') || 'null');
      if (g0 && typeof g0 === 'object') {
        Object.keys(G).forEach(function (k) {
          if (g0[k] !== undefined && typeof g0[k] === typeof G[k] && Array.isArray(g0[k]) === Array.isArray(G[k])) G[k] = g0[k];
        });
      }
    } catch (e) {}
    if (!TIER_RANGE[G.tier]) G.tier = 'safe';
    if (!(G.n >= 2 && G.n <= MAX_LEGS)) G.n = 3;
    if (G.goal !== 'odds') G.goal = 'count';
    G.fams = G.fams.filter(function (f) { return GFAM[f]; });
    var gdata = null, gdays = [];
    var gsave = function () { session.set('tkgen', JSON.stringify(G)); };
    var addKey = function (k, n) { var d = fromKey(k); d.setDate(d.getDate() + n); return dayKey(d); };
    var medDay = function (d) { return F.med.format(fromKey(d)); };  // « Du sam. 28 nov. au … » (minuscule au milieu de la phrase)
    // Jours de la période choisie, parmi ceux qui ont encore des matchs à venir
    var perDays = function () {
      var today = dayKey(new Date()), a = today, b = today;
      if (G.per === 'tomorrow') a = b = addKey(today, 1);
      else if (G.per === '3' || G.per === '7') b = addKey(today, +G.per - 1);
      else if (G.per === 'custom' && G.from && G.to) { a = G.from < G.to ? G.from : G.to; b = G.from < G.to ? G.to : G.from; }
      return { a: a, b: b, days: gdays.filter(function (d) { return d >= a && d <= b; }) };
    };
    var perTxt = function (r) {
      var today = dayKey(new Date());
      if (r.a === r.b) return r.a === today ? T.tk_today : r.a === addKey(today, 1) ? T.tk_tomorrow : cap(F.long.format(fromKey(r.a)));
      return fmt(T.gen_range, { a: medDay(r.a), b: medDay(r.b) });
    };
    var lcOf = function (m) { return m.lc || m.lg; };
    // Matchs fiables de la période, puis favoris et compétitions choisies
    var genPool = function (withLg) {
      var r = perDays(), ft = Favs.teams(), fl = Favs.leagues();
      return openMatches(gdata).filter(function (m) {
        if (!m.e || r.days.indexOf(m.d) < 0) return false;
        if (G.favs && ft.indexOf(m.h) < 0 && ft.indexOf(m.a) < 0 && fl.indexOf(lcOf(m)) < 0) return false;
        return !withLg || !G.lcs.length || G.lcs.indexOf(lcOf(m)) >= 0;
      });
    };
    // Paris gardés : types choisis, cote bookmaker estimée d'au moins la cote minimale
    var keepCand = function (c) {
      if (G.fams.length && !G.fams.some(function (f) { return GFAM[f].indexOf(FAM[c.key]) >= 0; })) return false;
      return !G.min || c.fair / (1 + MARGIN) >= G.min - 1e-9;
    };
    var nOf = function (n) { return n ? (n === 1 ? T.tk_1 : fmt(T.tk_n, { n: n })) : T.gen_zero; };
    var renderGen = function () {
      if (!gdata) return;
      var today = dayKey(new Date());
      if (!G.per) G.per = gdays.indexOf(today) >= 0 || !gdays.length ? 'today' : 'tomorrow';
      if (G.per === 'custom') {
        if (gdays.indexOf(G.from) < 0) G.from = gdays[0] || today;
        if (gdays.indexOf(G.to) < 0) G.to = gdays[Math.min(gdays.length - 1, gdays.indexOf(G.from) + 6)] || G.from;
      }
      var fl = Favs.leagues();
      var hasFav = !!(Favs.teams().length || fl.length);
      if (!hasFav) G.favs = false;
      $$('#gp-quick .chip', gen).forEach(function (b) {
        var on = b.dataset.per === G.per;
        b.classList.toggle('on', on);
        b.setAttribute('aria-pressed', on);
      });
      $('#gp-range').hidden = G.per !== 'custom';
      var opts = gdays.map(function (d) { return '<option value="' + d + '">' + esc(cap(F.long.format(fromKey(d)))) + '</option>'; }).join('');
      ['#gp-from', '#gp-to'].forEach(function (id, i) {
        var sel = $(id);
        if (sel._o !== opts) { sel.innerHTML = opts; sel._o = opts; }
        sel.value = i ? G.to : G.from;
      });
      var ms = genPool(false);
      $('#gp-sum').textContent = perTxt(perDays()) + ' · ' + nOf(genPool(true).length);
      $$('#gg-seg button', gen).forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.goal === G.goal); });
      $$('.gg', gen).forEach(function (p) { p.hidden = p.dataset.goal !== G.goal; });
      $('#gg-n').value = String(G.n);
      $$('#gl-tier button', gen).forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.tier === G.tier); });
      if (doc.activeElement !== $('#gg-odds')) $('#gg-odds').value = G.odds;
      // Compétitions de la période : favoris d'abord, puis les plus fournies
      var lgs = {};
      ms.forEach(function (m) { var k = lcOf(m); if (!lgs[k]) lgs[k] = { k: k, name: m.lg, n: 0 }; lgs[k].n++; });
      G.lcs.forEach(function (k) {
        if (lgs[k]) return;
        var m0 = gdata.matches.filter(function (m) { return lcOf(m) === k; })[0];
        lgs[k] = { k: k, name: m0 ? m0.lg : k, n: 0 };
      });
      var lgl = Object.keys(lgs).map(function (k) { return lgs[k]; }).sort(function (x, y) {
        return (fl.indexOf(y.k) >= 0) - (fl.indexOf(x.k) >= 0) || y.n - x.n || (x.name < y.name ? -1 : 1);
      });
      $('#gm-lg').innerHTML = lgl.map(function (l) {
        var on = G.lcs.indexOf(l.k) >= 0;
        return '<button class="chip' + (on ? ' on' : '') + '" type="button" data-lc="' + esc(l.k) + '" aria-pressed="' + on + '">' +
          esc(l.name) + '<span class="count">' + l.n + '</span></button>';
      }).join('') || '<p class="note">' + esc(T.gen_no_match) + '</p>';
      $$('#gm-fam .chip', gen).forEach(function (b) {
        var on = G.fams.indexOf(b.dataset.fam) >= 0;
        b.classList.toggle('on', on);
        b.setAttribute('aria-pressed', on);
      });
      $('#gm-min').value = G.min ? G.min.toFixed(2) : '0';
      var fs = $('#gm-favs');
      fs.checked = G.favs;
      fs.disabled = !hasFav;
      $('#gm-favs-help').textContent = hasFav ? T.gen_favs_help : T.gen_favs_empty;
      var nf = (G.lcs.length ? 1 : 0) + (G.fams.length ? 1 : 0) + (G.min ? 1 : 0) + (G.favs ? 1 : 0);
      var badge = $('#gm-n');
      badge.hidden = !nf;
      badge.textContent = nf;
      gsave();
    };
    // Un réglage change : l'ancien coupon n'est plus le bon
    var changed = function () { gout.textContent = ''; renderGen(); };
    var prepAuto = function () {
      if (autoReady) return;
      autoReady = true;
      withData(function (d) {
        gdata = d;
        gdays = [];
        openMatches(d).forEach(function (m) { if (gdays.indexOf(m.d) < 0) gdays.push(m.d); });
        gdays.sort();
        renderGen();
      }, gout);
    };
    var generate = function () {
      if (!gdata) { autoReady = false; prepAuto(); return; }
      var target = 0;
      if (G.goal === 'odds') {
        target = parseFloat(String(G.odds).trim().replace(',', '.'));
        if (!isFinite(target) || target < 1.5 || target > 100) { gout.innerHTML = '<p class="empty">' + esc(T.tk_bad_target) + '</p>'; return; }
      }
      gout.innerHTML = '<p class="note">' + esc(T.gen_calc) + '</p>';
      setTimeout(function () {
        if (!alive()) return;
        var ms = genPool(true);
        var sub = perTxt(perDays());
        if (!ms.length) couponCard(null, gout, '', T.gen_no_match);
        else if (G.goal === 'odds') couponCard(autoCoupon(ms, target, keepCand), gout, sub, T.gen_none_odds);
        else {
          var legs = tierPicks(ms, TIER_RANGE[G.tier], G.n, keepCand, G.fams.length > 0);
          if (legs.length < G.n) couponCard(null, gout, '', legs.length ? fmt(T.gen_few, { k: legs.length, n: G.n }) : T.gen_few0);
          else couponCard(legs, gout, sub);
        }
        markAdded(box);
        if (gout.getBoundingClientRect().top > win.innerHeight - 120) {
          gout.scrollIntoView({ block: 'nearest', behavior: reduced.matches ? 'auto' : 'smooth' });
        }
      }, 30);
    };
    $('#gp-quick').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-per]');
      if (!b) return;
      G.per = b.dataset.per;
      changed();
    });
    ['#gp-from', '#gp-to'].forEach(function (id, i) {
      $(id).addEventListener('change', function (e) { if (i) G.to = e.target.value; else G.from = e.target.value; changed(); });
    });
    $('#gg-seg').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-goal]');
      if (!b) return;
      G.goal = b.dataset.goal;
      changed();
    });
    $('#gg-n').addEventListener('change', function (e) { G.n = +e.target.value; changed(); });
    $('#gl-tier').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-tier]');
      if (!b) return;
      G.tier = b.dataset.tier;
      changed();
    });
    $('#gg-odds').addEventListener('input', function (e) { G.odds = e.target.value; gout.textContent = ''; gsave(); });
    $('#gg-odds').addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); generate(); } });
    $('#gg-quick').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-odds]');
      if (!b) return;
      G.odds = b.dataset.odds;
      $('#gg-odds').value = G.odds;
      gsave();
      generate();
    });
    $('#gm-lg').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-lc]');
      if (!b) return;
      var k = b.dataset.lc, i = G.lcs.indexOf(k);
      if (i >= 0) G.lcs.splice(i, 1); else G.lcs.push(k);
      changed();
      var nb = $$('#gm-lg .chip', gen).filter(function (x) { return x.dataset.lc === k; })[0];
      if (nb) nb.focus();
    });
    $('#gm-fam').addEventListener('click', function (e) {
      var b = e.target.closest('button[data-fam]');
      if (!b) return;
      var i = G.fams.indexOf(b.dataset.fam);
      if (i >= 0) G.fams.splice(i, 1); else G.fams.push(b.dataset.fam);
      changed();
    });
    $('#gm-min').addEventListener('change', function (e) { G.min = parseFloat(e.target.value) || 0; changed(); });
    $('#gm-favs').addEventListener('change', function (e) { G.favs = e.target.checked; changed(); });
    $('#gen-go').addEventListener('click', generate);

    showMode();
    renderMine();
    Coupon.on(function () { renderMine(); markAdded(box); }, alive);
    Acct.on(function () { renderMine(); if (mode !== 'mine' && Acct.premium()) prepAuto(); renderGen(); }, alive);
  };


  // =====================================================================================================
  // Membre : jour d'utilisation et parrainage (une fois par jour), récompenses, invitation, notifications
  // =====================================================================================================
  // Code d'un lien d'invitation (/i/CODE), gardé 7 jours sur le téléphone jusqu'à la création du compte
  var refCode = function () {
    try {
      var o = JSON.parse(local.get('pb-ref') || 'null');
      if (o && o.c && Date.now() - o.t < 7 * 864e5) return o.c;
    } catch (e) {}
    return null;
  };
  var Member = {
    start: function (force) {
      var s = Acct.get();
      if (!s || !s.user || Acct.demo || !Acct.api.member) return Promise.resolve();
      var code = refCode();
      var key = s.user.id + ':' + dayKey(new Date());
      if (!force && !code && local.get('pb-start') === key) return Promise.resolve();
      local.set('pb-start', key);
      return Acct.api.member({ action: 'start', day: dayKey(new Date()), code: code || undefined }).then(function (r) {
        if (code) {
          local.del('pb-ref');
          if (r && r.rewards) toast(T.ref_ok);
        }
        if (r && r.rewards) Rw.badge(null);
      }, function () { local.del('pb-start'); });
    }
  };

  // Récompenses : liste, activation, pastille de l'onglet
  var Rw = {
    label: function (r) {
      if (r.kind === 'premium') return fmt(T.rw_premium, { d: (T.rw_dur || {})[r.plan] || '' });
      return fmt(r.amount === 1 ? T.rw_an1 : T.rw_anN, { n: r.amount });
    },
    // Nombre de récompenses à activer (null : à recalculer), affiché sur l'onglet « Récompenses »
    badge: function (n) {
      if (n === null) {
        local.del('pb-rw-n');
        if (Acct.get() && Acct.get().user) Acct.api.rewards().then(function (l) {
          Rw.badge(l.filter(function (r) { return r.status === 'available'; }).length);
        }, noop);
        return;
      }
      if (n !== undefined) local.set('pb-rw-n', String(n));
      var v = +(local.get('pb-rw-n') || 0);
      var signed = !!(Acct.get() && Acct.get().user);
      $$('[data-rw-badge]').forEach(function (b) { b.hidden = !signed || !v; b.textContent = v > 9 ? '9+' : String(v); });
    }
  };

  var initRewards = function (scope) {
    var box = scope.querySelector('#rw');
    if (!box) return;
    var api = Acct.api;
    var q = params();
    if (q.r && q.t) {
      local.set('pb-claim', JSON.stringify({ r: q.r, t: q.t }));
      cleanUrl();
    }
    var pendingClaim = function () { try { return JSON.parse(local.get('pb-claim') || 'null'); } catch (e) { return null; } };
    var cfgRef = {};
    try { cfgRef = JSON.parse(scope.querySelector('#pb-ref-cfg').textContent); } catch (e) {}
    var icon = function (kind) { var t = scope.querySelector('#rw-ic-' + kind); return t ? t.innerHTML : ''; };
    var list = [];
    var busy = false;

    var item = function (r) {
      var el = doc.createElement('article');
      el.className = 'rw-item ' + r.kind + ' st-' + r.status;
      var when = r.status === 'used' && r.used_at ? fmt(T.rw_used, { d: F.date.format(new Date(r.used_at)) })
        : r.status === 'expired' ? T.rw_expired : r.status === 'cancelled' ? T.rw_cancelled
          : F.date.format(new Date(r.created_at));
      el.innerHTML = '<span class="ri-ic" aria-hidden="true">' + icon(r.kind) + '</span>' +
        '<div class="ri-txt"><b></b><small></small>' + (r.note ? '<q></q>' : '') + '</div>';
      el.querySelector('b').textContent = Rw.label(r);
      el.querySelector('small').textContent = ((T.rw_src || {})[r.source] || '') + ' · ' + when;
      if (r.note) el.querySelector('q').textContent = r.note;
      if (r.status === 'available') {
        var b = doc.createElement('button');
        b.type = 'button';
        b.className = 'btn ri-go';
        b.textContent = r.kind === 'premium' ? T.rw_act_premium : T.rw_act_analyses;
        b.addEventListener('click', function () { activate(r, b); });
        el.appendChild(b);
      }
      return el;
    };
    var renderList = function () {
      var open = list.filter(function (r) { return r.status === 'available'; });
      var past = list.filter(function (r) { return r.status !== 'available'; });
      var fill = function (id, rows) {
        var c = scope.querySelector('#' + id);
        c.textContent = '';
        rows.forEach(function (r) { c.appendChild(item(r)); });
        scope.querySelector('#' + id + '-box').hidden = !rows.length;
      };
      fill('rw-waiting', open);
      fill('rw-history', past);
      scope.querySelector('#rw-empty').hidden = list.length > 0;
      var friends = list.filter(function (r) { return r.source === 'referral_signup'; }).length;
      var cnt = scope.querySelector('#inv-count');
      cnt.hidden = !friends;
      cnt.textContent = fmt(friends === 1 ? T.inv_friends1 : T.inv_friendsN, { n: friends });
      Rw.badge(open.length);
    };
    var load = function () {
      return api.rewards().then(function (l) { list = l; renderList(); }, function () { flash(scope, T.error, 'bad'); });
    };
    var activate = function (r, b) {
      if (busy) return;
      busy = true;
      b.disabled = true;
      api.member({ action: 'activate', id: r.id }).then(function (res) {
        busy = false;
        if (res && res.kind === 'premium' && res.premium_until) flash(scope, fmt(T.rw_done_premium, { d: F.date.format(new Date(res.premium_until)) }));
        else flash(scope, fmt(T.rw_done_analyses, { n: r.amount }));
        win.scrollTo({ top: 0, behavior: reduced.matches ? 'auto' : 'smooth' });
        return (Acct.demo ? Promise.resolve() : api.session()).then(load);
      }).catch(function () { busy = false; b.disabled = false; toast(T.error); });
    };
    // Lien de l'e-mail cadeau : on valide, puis le cadeau apparaît dans la liste
    var claim = function () {
      var c = pendingClaim();
      if (!c) return Promise.resolve();
      flash(scope, T.rw_claim_wait);
      return api.member({ action: 'claim', id: c.r, token: c.t }).then(function (res) {
        local.del('pb-claim');
        flash(scope, res && res.status === 'expired' ? T.rw_claim_expired : T.rw_claim_ok, res && res.status === 'expired' ? 'warn' : undefined);
      }, function (e) {
        if (e && e.code === 'other_account') { flash(scope, T.rw_claim_other, 'warn'); return; }
        local.del('pb-claim');
        flash(scope, e && (e.code === 'bad_link' || e.code === 'unknown') ? T.rw_claim_bad : T.error, 'warn');
      });
    };
    // Barème du parrainage (réglable dans l'admin) : les chiffres de la page suivent la base
    var showRef = function (v) {
      if (!v) return;
      cfgRef = v;
      var buy = Object.keys(v.purchase || {}).map(function (k) { return v.purchase[k]; }).filter(function (n) { return n > 0; });
      var set = function (k, txt) { var el = scope.querySelector('[data-ref="' + k + '"]'); if (el) el.textContent = txt; };
      set('signup', '+' + v.signup);
      set('active', '+' + v.active);
      if (buy.length) set('buy', '+' + Math.min.apply(null, buy) + (lang === 'fr' ? ' à ' : ' to ') + '+' + Math.max.apply(null, buy));
      var t1 = scope.querySelector('[data-ref-text="active"]');
      if (t1) t1.textContent = fmt(T.inv_active_js || t1.textContent.replace(/\d+/, '{d}'), { d: v.active_days });
      var t2 = scope.querySelector('[data-ref-text="welcome"] span');
      if (t2) t2.textContent = t2.textContent.replace(/\d+/, String(v.welcome));
      var t3 = scope.querySelector('[data-ref-text="cap"]');
      if (t3) t3.textContent = t3.textContent.replace(/\d+/, String(v.monthly_cap));
    };
    var invite = function (s) {
      // En démo, un code d'exemple (le vrai est donné par la base à la création du compte)
      var code = (s.profile && s.profile.ref_code) || (Acct.demo ? 'DEMO23' : null);
      var url = location.origin + '/i/' + (code || '');
      var input = scope.querySelector('#inv-url');
      input.value = code ? url : '…';
      var msg = fmt(T.inv_msg, { n: cfgRef.welcome || 2, u: url });
      scope.querySelector('#inv-wa').setAttribute('href', 'https://wa.me/?text=' + encodeURIComponent(msg));
      var sh = scope.querySelector('#inv-share');
      sh.hidden = !navigator.share;
      sh.onclick = function () { navigator.share({ title: 'Probalis', text: msg }).catch(noop); };
      scope.querySelector('#inv-copy').onclick = function () {
        var done = function () { toast(T.inv_copied); };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(done, function () { input.select(); });
        else { input.select(); try { doc.execCommand('copy'); done(); } catch (e) {} }
      };
    };
    var render = function (s) {
      box.dataset.state = s && s.user ? 'in' : 'out';
      if (!s || !s.user) {
        if (pendingClaim()) flash(scope, T.rw_claim_signin, 'warn');
        return;
      }
      scope.querySelector('#rw-bonus').textContent = String((s.profile && s.profile.bonus_analyses) || 0);
      invite(s);
    };
    scope.querySelector('#rw-signin').addEventListener('click', function () { local.set('pb-next', location.pathname); });
    var first = function (s) {
      render(s);
      if (!s || !s.user) return;
      claim().then(load);
      api.referral().then(showRef, noop);
    };
    var s0 = Acct.get();
    if (!Acct.demo && Acct.hasToken() && !s0) api.session().then(first, function () { first(Acct.get()); });
    else first(s0);
    Acct.on(render, function () { return box.isConnected; });
  };

  // Page d'invitation (/i/CODE) : le code est gardé jusqu'à la création du compte
  var initInvite = function (scope) {
    var box = scope.querySelector('#invp');
    if (!box) return;
    var q = params();
    var code = String(q.c || '').toUpperCase();
    if (/^[A-Z0-9]{4,12}$/.test(code)) {
      // Visiteur non francophone : la même invitation en anglais (une seule fois)
      if (lang === 'fr' && !/^fr/i.test(navigator.language || 'fr') && !session.get('pb-inv-lang')) {
        session.set('pb-inv-lang', '1');
        location.replace('/en/invite.html?c=' + code);
        return;
      }
      local.set('pb-ref', JSON.stringify({ c: code, t: Date.now() }));
      cleanUrl();
    }
    var render = function (s) {
      box.dataset.state = s && s.user ? 'have' : refCode() ? '' : 'bad';
    };
    render(Acct.get());
    Acct.on(render, function () { return box.isConnected; });
    scope.querySelector('#invp-go').addEventListener('click', function () {
      local.set('pb-next', '/' + lang + '/recompenses.html');
    });
  };

  // Notifications : abonnement de ce téléphone (clé publique demandée à la fonction « member »)
  var Push = {
    ok: function () { return 'serviceWorker' in navigator && 'PushManager' in win && 'Notification' in win; },
    key: function (b64) {
      var pad = '='.repeat((4 - b64.length % 4) % 4);
      var raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
      var out = new Uint8Array(raw.length);
      for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
      return out;
    },
    current: function () {
      if (!Push.ok()) return Promise.resolve(null);
      return navigator.serviceWorker.ready.then(function (reg) { return reg.pushManager.getSubscription(); }).catch(function () { return null; });
    },
    enable: function () {
      return Notification.requestPermission().then(function (perm) {
        if (perm !== 'granted') { var e = new Error('denied'); e.code = 'denied'; throw e; }
        return Promise.all([navigator.serviceWorker.ready, Acct.api.member({ action: 'push_key' })]);
      }).then(function (a) {
        var reg = a[0];
        var key = a[1] && a[1].key;
        if (!key) throw new Error('key');
        return reg.pushManager.getSubscription().then(function (old) {
          // Abonnement fait avec une autre clé : on le refait
          if (old && local.get('pb-push-key') === key) return old;
          return (old ? old.unsubscribe() : Promise.resolve()).then(function () {
            return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: Push.key(key) });
          });
        }).then(function (sub) {
          local.set('pb-push-key', key);
          return Acct.api.member({ action: 'push_sub', sub: sub.toJSON(), lang: lang });
        });
      });
    },
    disable: function () {
      return Push.current().then(function (sub) {
        if (!sub) return;
        var ep = sub.endpoint;
        return sub.unsubscribe().then(function () { return Acct.api.member({ action: 'push_unsub', endpoint: ep }).catch(noop); });
      });
    }
  };
  var initPush = function (scope) {
    var card = scope.querySelector('#push-card');
    if (!card) return;
    var dev = card.querySelector('#push-device');
    var ua = navigator.userAgent || '';
    var ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    var standalone = (win.matchMedia && win.matchMedia('(display-mode: standalone)').matches) || navigator.standalone;
    var set = function (st) { card.dataset.state = st; dev.checked = st === 'on'; };
    if (Acct.demo) {
      set(local.get('pb-demo-push') ? 'on' : 'off');
      dev.addEventListener('change', function () {
        if (dev.checked) local.set('pb-demo-push', '1'); else local.del('pb-demo-push');
        set(dev.checked ? 'on' : 'off');
        toast(dev.checked ? T.push_on : T.push_off);
      });
      return;
    }
    if (!Push.ok()) { set(ios && !standalone ? 'ios' : 'unsupported'); return; }
    if (Notification.permission === 'denied') set('blocked');
    else Push.current().then(function (sub) { set(sub ? 'on' : 'off'); });
    dev.addEventListener('change', function () {
      dev.disabled = true;
      var want = dev.checked;
      (want ? Push.enable() : Push.disable()).then(function () {
        dev.disabled = false;
        set(want ? 'on' : 'off');
        toast(want ? T.push_on : T.push_off);
        if (want) Acct.api.member({ action: 'push_test' }).catch(noop);
      }, function (e) {
        dev.disabled = false;
        if (e && e.code === 'denied') { set('blocked'); toast(T.push_blocked); return; }
        set(want ? 'off' : 'on');
        toast(T.error);
      });
    });
  };

  // --- Historique des analyses : onglets Aujourd'hui / Hier / Avant-hier / 7 jours ---
  // ---------- Historique : réussite par période (hier, 7 jours, 30 jours, depuis le début) ----------
  var initHistPer = function (scope) {
    var seg = (scope || doc).querySelector('#hper');
    if (!seg) return;
    var btns = $$('button[data-per]', seg);
    var blocks = $$('.hper', seg.parentNode);
    var keys = btns.map(function (b) { return b.dataset.per; });
    var show = function (key) {
      btns.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.per === key); });
      blocks.forEach(function (p) { p.classList.toggle('on', p.dataset.per === key); });
      session.set('hper', key);
    };
    show(keys.indexOf(session.get('hper')) >= 0 ? session.get('hper') : 'all');
    seg.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-per]');
      if (b) show(b.dataset.per);
    });
  };

  var initHistAn = function (scope) {
    var seg = (scope || doc).querySelector('#ha-seg');
    if (!seg) return;
    var box = seg.parentNode;
    var panels = $$('.ha-panel', box);
    var show = function (key) {
      $$('button', seg).forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.ha === key); });
      panels.forEach(function (p) { p.hidden = p.dataset.ha !== key; });
    };
    var first = seg.querySelector('button');
    show(first ? first.dataset.ha : 'w');
    seg.addEventListener('click', function (e) {
      var b = e.target.closest('button[data-ha]');
      if (b) show(b.dataset.ha);
    });
  };

  // =====================================================================================================
  // Match en direct (ESPN, par notre relais /live/ : le téléphone ne parle jamais à ESPN directement).
  // Liste des matchs : minute et score sur les cartes des matchs en cours ou finis depuis peu.
  // Fiche : score et minute en tête, onglet « Match » (temps forts, statistiques, compositions).
  // Mis à jour chaque minute pendant le match, en pause quand l'appli n'est pas à l'écran.
  // Les noms venus d'ESPN ne sont jamais écrits comme du code : textContent seulement.
  // =====================================================================================================
  var Live = (function () {
    var MIN = 60e3;
    var gen = 0;
    var timers = [];
    var resume = null;
    var BAD = { STATUS_POSTPONED: 'lv_postponed', STATUS_CANCELED: 'lv_canceled', STATUS_ABANDONED: 'lv_abandoned',
      STATUS_FORFEIT: 'lv_abandoned', STATUS_SUSPENDED: 'lv_delayed', STATUS_DELAYED: 'lv_delayed' };
    var get = function (path) {
      return fetch('/live/' + path + '.json', { credentials: 'omit' })
        .then(function (r) { return r.ok ? r.json() : (r.status === 404 ? { gone: true } : null); })
        .catch(function () { return null; });
    };
    var ref = function (el) {
      var p = (el.dataset.espn || '').split('/');
      return p.length === 3 ? { slug: p[0], id: p[1], day: p[2] } : null;
    };
    var later = function (g, fn, ms) {
      timers.push(setTimeout(function () {
        if (g !== gen) return;
        if (doc.hidden) { resume = fn; return; }
        fn();
      }, Math.max(1000, ms)));
    };
    var el = function (tag, cls, txt) {
      var e = doc.createElement(tag);
      if (cls) e.className = cls;
      if (txt != null) e.textContent = txt;
      return e;
    };
    // Ce qu'on montre de l'état d'un match : { live, done, txt, long, sc }
    var label = function (e) {
      if (!e || !e.s) return null;
      if (BAD[e.sn]) return { done: e.s !== 'in', bad: true, txt: T[BAD[e.sn]], long: T[BAD[e.sn]] };
      if (e.s === 'pre') return null;
      var sc = e.sc && e.sc[0] != null && e.sc[1] != null ? e.sc : null;
      if (e.s === 'in') {
        var ht = e.sn === 'STATUS_HALFTIME';
        return { live: true, sc: sc, txt: ht ? T.lv_ht : (e.cl || T.lv_live), long: ht ? T.lv_ht_long : (e.cl || T.lv_live) };
      }
      var end = e.sn === 'STATUS_FINAL_AET' ? T.lv_aet : e.sn === 'STATUS_FINAL_PEN' ? T.lv_pen : null;
      return { done: true, sc: sc, txt: end || T.lv_ft, long: end || T.lv_ft_long };
    };

    // ---------- Liste des matchs ----------
    var paintCard = function (card, e) {
      var l = label(e);
      if (!l) return null;
      card.classList.toggle('is-live', !!l.live);
      card.classList.toggle('is-done', !!l.done);
      var host = card.querySelector('.mc-top .time, .f-when');
      var b = host && host.querySelector('.lvb');
      if (host && !b) { b = el('span', 'lvb'); host.insertBefore(b, host.firstChild); }
      if (b) b.textContent = l.txt;
      var scs = card.querySelectorAll('.team .sc');
      if (scs.length === 2 && l.sc) {
        scs[0].textContent = l.sc[0];
        scs[1].textContent = l.sc[1];
        scs[0].hidden = scs[1].hidden = false;
      }
      var fs = card.querySelector('.f-sc');
      if (fs && l.sc) { fs.textContent = l.sc[0] + ' – ' + l.sc[1]; fs.hidden = false; }
      return l;
    };
    var cards = function (list, g) {
      var now = Date.now();
      var groups = {};
      var next = Infinity;
      list.forEach(function (c) {
        var r = ref(c);
        var ko = new Date(c.dataset.ko).getTime();
        if (c._lvEnd || !r || isNaN(ko) || !c.isConnected) return;
        if (now < ko - 2 * MIN) { next = Math.min(next, ko - 2 * MIN); return; }
        var k = r.slug + '/' + r.day;
        (groups[k] = groups[k] || []).push([c, r]);
      });
      var keys = Object.keys(groups);
      if (!keys.length) {
        if (next < Infinity) later(g, function () { cards(list, g); }, Math.min(next - now, 30 * MIN));
        return;
      }
      Promise.all(keys.map(function (k) {
        return get('sb/' + k).then(function (d) {
          if (g !== gen || !d || !d.ev) return;
          groups[k].forEach(function (cr) {
            var l = paintCard(cr[0], d.ev[cr[1].id]);
            if (l && l.done) cr[0]._lvEnd = true;  // fini : plus la peine de redemander
          });
        });
      })).then(function () {
        if (g === gen) later(g, function () { cards(list, g); }, MIN);
      });
    };

    // ---------- Fiche : onglet « Match » ----------
    var POS = function (p) {
      p = String(p || '').toUpperCase();
      if (p === 'G' || p.indexOf('GK') === 0) return 'g';
      if (/^(DM|CM|AM|LM|RM|M)/.test(p)) return 'm';
      if (/^(CD|CB|LB|RB|LWB|RWB|WB|SW|D)/.test(p)) return 'd';
      return p ? 'a' : '';
    };
    var pct = function (v) { var n = parseFloat(v); return isNaN(n) ? v : Math.round(n) + ' %'; };
    var statRows = function (st) {
      var by = {};
      st.forEach(function (s) { by[s[0]] = s; });
      return st.filter(function (s) { return s[0] !== 'accuratePasses'; }).map(function (s) {
        var h = s[1];
        var a = s[2];
        var nh = parseFloat(h);
        var na = parseFloat(a);
        if (s[0] === 'possessionPct') { h = pct(h); a = pct(a); }
        if (s[0] === 'passPct') {
          var acc = by.accuratePasses;
          var tot = by.totalPasses;
          if (acc && tot && +tot[1] && +tot[2]) { nh = 100 * acc[1] / tot[1]; na = 100 * acc[2] / tot[2]; } else { nh *= 100; na *= 100; }
          h = Math.round(nh) + ' %';
          a = Math.round(na) + ' %';
        }
        return { k: s[0], h: h, a: a, nh: isNaN(nh) ? 0 : nh, na: isNaN(na) ? 0 : na };
      });
    };
    var paneEvents = function (d) {
      var box = el('div', 'lv-pane');
      box.dataset.pane = 'ev';
      if (!d.ev || !d.ev.length) { box.appendChild(el('p', 'lv-msg', d.s === 'pre' ? T.lv_pre : T.lv_no_ev)); return box; }
      var ol = el('ol', 'lv-evs');
      var period = 1;
      d.ev.forEach(function (e) {
        if (e.p && e.p > period) {
          ol.appendChild(el('li', 'lv-sep', e.p === 2 ? T.lv_ht_long : T.lv_et));
          period = e.p;
        }
        var li = el('li', 'lv-ev ' + (e.e === 'a' ? 'a' : 'h') + ' k-' + e.k);
        li.appendChild(el('span', 'm', e.m));
        var ic = el('span', 'ic');
        ic.setAttribute('aria-hidden', 'true');
        li.appendChild(ic);
        var tx = el('span', 'tx');
        var n = e.n || [];
        if (e.k === 'c') {
          tx.appendChild(el('b', 'in', '↑ ' + (n[0] || '')));
          if (n[1]) tx.appendChild(el('small', 'out', '↓ ' + n[1]));
        } else {
          tx.appendChild(el('b', null, n[0] || ''));
          var sub = e.k === 'b' ? (e.x === 'csc' ? T.lv_og : e.x === 'pen' ? T.lv_pen_goal : (n[1] ? fmt(T.lv_assist, { n: n[1] }) : ''))
            : e.k === 'jr' ? T.lv_2y : '';
          if (sub) tx.appendChild(el('small', null, sub));
        }
        li.appendChild(tx);
        ol.appendChild(li);
      });
      box.appendChild(ol);
      return box;
    };
    var paneStats = function (d) {
      var box = el('div', 'lv-pane');
      box.dataset.pane = 'st';
      var rows = statRows(d.st || []);
      if (!rows.length) { box.appendChild(el('p', 'lv-msg', d.s === 'pre' ? T.lv_pre : T.lv_no_st)); return box; }
      rows.forEach(function (r) {
        var row = el('div', 'lv-st');
        var top = el('div', 'lv-st-top');
        var tot = r.nh + r.na;
        var sh = tot > 0 ? r.nh / tot : 0.5;
        top.appendChild(el('b', sh > 0.5 ? 'lv-lead' : null, r.h));
        top.appendChild(el('span', null, T['st_' + r.k] || r.k));
        top.appendChild(el('b', sh < 0.5 ? 'lv-lead' : null, r.a));
        row.appendChild(top);
        var bar = el('div', 'lv-bar');
        var bh = el('i', sh > 0.5 ? 'lv-lead' : null);
        var ba = el('i', sh < 0.5 ? 'lv-lead' : null);
        bh.style.width = (100 * sh).toFixed(1) + '%';
        ba.style.width = (100 * (1 - sh)).toFixed(1) + '%';
        bar.appendChild(bh);
        bar.appendChild(ba);
        row.appendChild(bar);
        box.appendChild(row);
      });
      return box;
    };
    var paneLineups = function (d, names) {
      var box = el('div', 'lv-pane');
      box.dataset.pane = 'lu';
      if (!d.lu) { box.appendChild(el('p', 'lv-msg', d.s === 'pre' ? T.lv_pre_lu : T.lv_no_lu)); return box; }
      var sw = el('div', 'seg lv-teams');
      var lists = [];
      ['h', 'a'].forEach(function (side, i) {
        var t = d.lu[side];
        var b = el('button', i ? null : 'on', names[i] || (i ? '2' : '1'));
        b.type = 'button';
        b.setAttribute('aria-pressed', i ? 'false' : 'true');
        sw.appendChild(b);
        var wrap = el('div', 'lv-lu');
        wrap.hidden = !!i;
        if (t.f) wrap.appendChild(el('p', 'lv-f', fmt(T.lv_coach_formation, { f: t.f })));
        var add = function (players, subs) {
          var ul = el('ul', 'lv-pl' + (subs ? ' subs' : ''));
          players.forEach(function (p) {
            var li = el('li', p[3] === 1 ? 'out' : p[3] === 2 ? 'in' : null);
            li.appendChild(el('span', 'no', p[0]));
            li.appendChild(el('span', 'nm', p[1]));
            var g = POS(p[2]);
            if (g && !subs) li.appendChild(el('span', 'po', T['pos_' + g] || ''));
            if (p[3] === 1) li.appendChild(el('span', 'mk', '↓')).setAttribute('aria-label', T.lv_out);
            if (p[3] === 2) li.appendChild(el('span', 'mk', '↑')).setAttribute('aria-label', T.lv_in);
            ul.appendChild(li);
          });
          wrap.appendChild(ul);
        };
        add(t.xi || [], false);
        if (t.sub && t.sub.length) {
          wrap.appendChild(el('h3', null, T.lv_subs));
          add(t.sub, true);
        }
        lists.push(wrap);
      });
      sw.addEventListener('click', function (e) {
        var b = e.target.closest('button');
        if (!b) return;
        $$('button', sw).forEach(function (x, i) {
          var on = x === b;
          x.classList.toggle('on', on);
          x.setAttribute('aria-pressed', on);
          lists[i].hidden = !on;
        });
      });
      box.appendChild(sw);
      lists.forEach(function (w) { box.appendChild(w); });
      return box;
    };
    var render = function (box, d, scope) {
      var l = label(d);
      var state = box.querySelector('.lv-state');
      state.hidden = !l;
      if (l) {
        state.className = 'lv-state' + (l.live ? ' live' : '');
        state.textContent = l.long + (l.sc && !l.live ? ' · ' + l.sc[0] + '-' + l.sc[1] : '');
      }
      var names = $$('.hero-teams .nm', scope).map(function (n) { return n.textContent; });
      var panes = [paneEvents(d), paneStats(d), paneLineups(d, names)];
      var seg = box.querySelector('.lv-seg');
      var cur = seg.querySelector('button.on');
      var want = box._lvPane || (d.s === 'pre' && d.lu ? 'lu' : 'ev');
      var body = box.querySelector('.lv-body');
      body.textContent = '';
      panes.forEach(function (p) { p.hidden = p.dataset.pane !== want; body.appendChild(p); });
      $$('button', seg).forEach(function (b) {
        var on = b.dataset.lv === want;
        b.classList.toggle('on', on);
        b.setAttribute('aria-selected', on);
      });
      seg.hidden = false;
      if (!seg._lv) {
        seg._lv = true;
        seg.addEventListener('click', function (e) {
          var b = e.target.closest('button[data-lv]');
          if (!b) return;
          box._lvPane = b.dataset.lv;
          $$('button', seg).forEach(function (x) { var on = x === b; x.classList.toggle('on', on); x.setAttribute('aria-selected', on); });
          $$('.lv-pane', body).forEach(function (p) { p.hidden = p.dataset.pane !== b.dataset.lv; });
        });
      }
      box.removeAttribute('aria-busy');
      var src = box.querySelector('.lv-src');
      var upd = src.querySelector('.lv-upd') || src.appendChild(el('span', 'lv-upd'));
      upd.textContent = ' ' + fmt(T.lv_updated, { t: F.time.format(new Date()) });
      // En-tête de la fiche : score et minute à la place de l'heure du coup d'envoi
      var hw = scope.querySelector('.hero-when');
      var hs = hw && hw.querySelector('.lv-sc');
      if (hs && l && (l.sc || l.bad)) {
        var hc = hw.querySelector('.lv-cl');
        hs.textContent = l.sc ? l.sc[0] + ' – ' + l.sc[1] : '–';
        hc.textContent = l.txt;
        hc.className = 'lv-cl' + (l.live ? ' live' : '');
        hs.hidden = hc.hidden = false;
        hw.classList.add('lv-on');
      }
      var dot = scope.querySelector('#tab-match .tab-live');
      if (dot) dot.hidden = !(l && l.live);
    };
    var match = function (box, scope, g) {
      var r = ref(box);
      var ko = new Date(box.dataset.ko).getTime();
      var now = Date.now();
      if (!r) return;
      // Plus de 2 h avant le coup d'envoi : rien à demander (les compositions arrivent environ 1 h avant)
      if (!box.dataset.past && now < ko - 2 * 3600e3) {
        render(box, { s: 'pre' }, scope);
        later(g, function () { match(box, scope, g); }, Math.min(ko - 2 * 3600e3 - now, 30 * MIN));
        return;
      }
      get('ev/' + r.slug + '/' + r.id).then(function (d) {
        if (g !== gen || !box.isConnected) return;
        if (!d) {
          if (!box._lvOk) {
            var body = box.querySelector('.lv-body');
            body.textContent = '';
            body.appendChild(el('p', 'lv-msg', T.lv_err));
          }
          later(g, function () { match(box, scope, g); }, MIN);
          return;
        }
        if (d.gone) {
          var b2 = box.querySelector('.lv-body');
          b2.textContent = '';
          b2.appendChild(el('p', 'lv-msg', T.lv_gone));
          box.removeAttribute('aria-busy');
          return;
        }
        box._lvOk = true;
        render(box, d, scope);
        var l = label(d);
        if (l && l.done) return;  // fini : plus de mise à jour
        later(g, function () { match(box, scope, g); }, d.s === 'in' ? MIN : 5 * MIN);
      });
    };

    doc.addEventListener('visibilitychange', function () {
      if (!doc.hidden && resume) {
        var f = resume;
        resume = null;
        f();
      }
    });
    return {
      start: function (scope) {
        gen++;
        timers.forEach(clearTimeout);
        timers = [];
        resume = null;
        if (!win.fetch) return;
        var g = gen;
        var list = $$('.mcard[data-espn], .featured[data-espn]', scope);
        if (list.length) cards(list, g);
        $$('.lv[data-espn]', scope).forEach(function (box) { match(box, scope, g); });
      }
    };
  })();

  // Colonne de droite de la page Matchs (ordinateur) : résumé du ticket en cours
  var initTkMini = function (scope) {
    var box = scope.querySelector('#tk-mini');
    if (!box) return;
    var body = box.querySelector('.tkm-body');
    var draw = function () {
      var legs = Coupon.get();
      if (!legs.length) { body.innerHTML = '<p class="sb-empty">' + esc(T.side_tk_empty) + '</p>'; return; }
      var st = Coupon.stats(legs);
      body.innerHTML = '<ul class="tkm-legs">' + legs.slice(0, 5).map(function (l) {
        return '<li><span><b>' + esc(l.l) + '</b><small>' + esc(l.h + ' – ' + l.a) + '</small></span><span class="tkm-p">' + pctTxt(l.p) + '</span></li>';
      }).join('') + '</ul>' + (legs.length > 5 ? '<p class="tkm-more">+ ' + (legs.length - 5) + '</p>' : '') +
        '<div class="tkm-sum"><span><small>' + esc(T.side_tk_chance) + '</small><b>' + pctTxt(st.p) + '</b></span>' +
        '<span><small>' + esc(T.side_tk_odds) + '</small><b>≈ ' + oddsTxt(st.book) + '</b></span></div>';
    };
    draw();
    Coupon.on(draw, function () { return doc.body.contains(box); });
  };

  var init = function (scope) {
    initHistAn(scope);
    initHistPer(scope);
    initTkMini(scope);
    initDates(scope);
    initImages(scope);
    initPrices(scope);
    initHome(scope);
    initFollow(scope);
    initTabs(scope);
    Live.start(scope);
    initCompare(scope);
    initAccount(scope);
    initPremium(scope);
    initFree(scope);
    initRewards(scope);
    initInvite(scope);
    initPush(scope);
    initBets(scope);
    initMatchAdd(scope);
    initTicket(scope);
    Coupon.badge();
    Rw.badge();
    Member.start(false);
  };

  // =====================================================================================================
  // Navigation façon appli : on télécharge la page suivante en arrière-plan, on montre tout de suite un
  // squelette et la barre de progression, puis on remplace le contenu sans recharger tout le site.
  // =====================================================================================================
  var router = (function () {
    var supported = !!(win.history && history.pushState && win.fetch && win.DOMParser && doc.body.replaceWith);
    var cache = {};
    var inflight = {};
    var ctrl = null;
    var seq = 0;
    var currentKey = location.pathname + location.search;
    var FRESH = 5 * 60e3;

    var keyOf = function (href) {
      var u;
      try { u = new URL(href, location.href); } catch (e) { return null; }
      if (u.origin !== location.origin) return null;
      if (!/(\.html|\/)$/.test(u.pathname)) return null;
      if (u.pathname.split('/')[1] !== lang) return null;  // autre langue : chargement complet
      // Probalis Office (appli à part : styles, script et manifeste) : on en sort par un chargement complet
      if (/^\/office\//.test(location.pathname)) return null;
      return { key: u.pathname + u.search, url: u };
    };
    var linkOf = function (e) {
      var a = e.target.closest && e.target.closest('a[href]');
      if (!a || (a.target && a.target !== '_self') || a.hasAttribute('download') || a.dataset.lang || a.hasAttribute('data-reload')) return null;
      var k = keyOf(a.href);
      if (!k) return null;
      if (k.key === currentKey && k.url.hash) return null;  // ancre dans la même page
      return k;
    };
    var trim = function () {
      var keys = Object.keys(cache);
      if (keys.length <= 14) return;
      keys.sort(function (a, b) { return cache[a].t - cache[b].t; }).slice(0, keys.length - 14).forEach(function (k) { delete cache[k]; });
    };
    var load = function (key, signal, onData, low) {
      if (inflight[key]) return inflight[key];
      var opts = { credentials: 'same-origin', headers: { 'X-Probalis-Nav': '1' } };
      if (signal) opts.signal = signal;
      if (low) opts.priority = 'low';
      var p = fetch(key, opts).then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status);
        if ((res.headers.get('content-type') || '').indexOf('text/html') < 0) throw new Error('type');
        var total = res.headers.get('content-encoding') ? 0 : +(res.headers.get('content-length') || 0);
        if (!res.body || !res.body.getReader || !win.TextDecoder) return res.text();
        var reader = res.body.getReader();
        var dec = new TextDecoder();
        var html = '';
        var got = 0;
        var pump = function () {
          return reader.read().then(function (r) {
            if (r.done) return html + dec.decode();
            got += r.value.length;
            html += dec.decode(r.value, { stream: true });
            if (onData) onData(total ? got / total : null);
            return pump();
          });
        };
        return pump();
      }).then(function (html) {
        cache[key] = { html: html, t: Date.now() };
        trim();
        delete inflight[key];
        return html;
      }, function (err) { delete inflight[key]; throw err; });
      inflight[key] = p;
      return p;
    };

    // Squelettes : la forme de la page suivante, affichée tout de suite
    var rep = function (s, n) { var o = ''; for (var i = 0; i < n; i++) o += s; return o; };
    var SK_TOP = '<div class="sk-top"><span class="sk sk-logo"></span><span class="sk-row"><span class="sk sk-round"></span><span class="sk sk-round"></span></span></div>';
    var skeleton = function (path) {
      if (/\/match\//.test(path)) {
        return '<div class="hero sk-hero"><div class="hero-top"><span class="sk sk-round"></span><span class="sk sk-line"></span><span class="sk sk-round"></span></div>' +
          '<div class="hero-teams"><div class="side"><span class="sk sk-disc"></span><span class="sk sk-line"></span></div><div class="hero-when"><span class="sk sk-time"></span></div>' +
          '<div class="side"><span class="sk sk-disc"></span><span class="sk sk-line"></span></div></div><span class="sk sk-bar"></span></div>' +
          '<div class="sk-row sk-days">' + rep('<span class="sk sk-tab"></span>', 4) + '</div>' + rep('<span class="sk sk-block"></span>', 3);
      }
      if (/\/(index\.html)?$/.test(path)) {
        return SK_TOP + '<span class="sk sk-kicker"></span><span class="sk sk-h1"></span>' +
          '<div class="sk-row sk-days">' + rep('<span class="sk sk-day"></span>', 7) + '</div>' +
          '<div class="sk-row sk-days">' + rep('<span class="sk sk-chip"></span>', 4) + '</div>' +
          '<span class="sk sk-feat"></span><span class="sk sk-lg"></span>' + rep('<span class="sk sk-mcard"></span>', 4);
      }
      return SK_TOP + '<span class="sk sk-kicker"></span><span class="sk sk-h1"></span><span class="sk sk-line" style="width: 92%"></span>' +
        '<span class="sk sk-line" style="width: 68%"></span>' + rep('<span class="sk sk-block"></span>', 3);
    };
    var setTab = function (path) {
      var name = path.split('/').pop() || 'index.html';
      var tab = { 'index.html': 'matches', 'paris.html': 'bets', 'ticket.html': 'ticket', 'historique.html': 'historique', 'compte.html': 'compte' }[name];
      if (!tab && /\/match\//.test(path)) tab = 'matches';
      if (!tab) return;
      $$('.tabbar a').forEach(function (a) {
        if (a.dataset.tab === tab) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
      });
    };
    var saveScroll = function () {
      try { history.replaceState(Object.assign({}, history.state, { pb: 1, scroll: win.scrollY }), ''); } catch (e) {}
    };

    var swap = function (html, k, opts, fr) {
      var d = new DOMParser().parseFromString(html, 'text/html');
      var app = d.querySelector('.app');
      var bar = d.querySelector('.tabbar');
      var css = d.querySelector('link[rel="stylesheet"]');
      var cur = doc.querySelector('link[rel="stylesheet"]');
      // Nouvelle version du site (styles ou scripts changés) : chargement complet
      if (!app || !bar || !css || !cur || css.getAttribute('href') !== cur.getAttribute('href') || d.documentElement.lang !== lang) return false;
      doc.title = d.title;
      var desc = d.querySelector('meta[name="description"]');
      var myDesc = doc.querySelector('meta[name="description"]');
      if (desc && myDesc) myDesc.setAttribute('content', desc.getAttribute('content'));
      var alt = d.querySelector('link[rel="alternate"]');
      var myAlt = doc.querySelector('link[rel="alternate"]');
      if (alt && myAlt) myAlt.setAttribute('href', alt.getAttribute('href'));
      doc.body.className = d.body.className;
      app = doc.adoptNode(app);
      if (fr && !Lk.apply(app, fr)) Lk.stale();
      doc.querySelector('.app').replaceWith(app);
      doc.querySelector('.tabbar').replaceWith(doc.adoptNode(bar));
      if (opts.push) history.pushState({ pb: 1, scroll: 0 }, '', k.url.href);
      currentKey = k.key;
      init(app);
      if (opts.pop && opts.scroll != null) win.scrollTo(0, opts.scroll);
      else if (k.url.hash && doc.getElementById(k.url.hash.slice(1)) && !doc.querySelector('.ptabs')) doc.getElementById(k.url.hash.slice(1)).scrollIntoView();
      else win.scrollTo(0, 0);
      if (!reduced.matches && !opts.pop) {
        app.classList.add('enter');
        setTimeout(function () { app.classList.remove('enter'); }, 400);
      }
      if (opts.push) { var main = doc.getElementById('main'); if (main) main.focus({ preventScroll: true }); }
      live.textContent = fmt(T.loaded, { t: d.title });
      return true;
    };

    var go = function (href, opts) {
      opts = opts || { push: true };
      var k = keyOf(href);
      if (!supported || !k) { location.href = href; return; }
      var my = ++seq;
      if (ctrl) ctrl.abort();
      ctrl = win.AbortController ? new AbortController() : null;
      if (!opts.pop) saveScroll();
      setTab(k.url.pathname);
      var frP = Lk.forPage(k.url.pathname);
      var hit = cache[k.key];
      var maxAge = opts.pop ? 30 * 60e3 : FRESH;
      if (hit && !opts.fresh && Date.now() - hit.t < maxAge) {
        frP.then(function (fr) {
          if (my !== seq) return;
          if (!swap(hit.html, k, opts, fr)) location.href = k.url.href;
        });
        return;
      }
      progress.start();
      var old = doc.querySelector('.app');
      var sk = null;
      var skT = setTimeout(function () {
        if (my !== seq) return;
        sk = doc.createElement('div');
        sk.className = 'app skel';
        sk.setAttribute('aria-busy', 'true');
        sk.innerHTML = skeleton(k.url.pathname);
        old.replaceWith(sk);
        win.scrollTo(0, 0);
      }, 120);
      var slowT = setTimeout(function () { if (my === seq) netbar.slow(); }, 3000);
      Promise.all([load(k.key, ctrl && ctrl.signal, progress.data), frP]).then(function (r) {
        clearTimeout(skT);
        clearTimeout(slowT);
        if (my !== seq) return;
        if (!swap(r[0], k, opts, r[1])) { location.href = k.url.href; return; }
        progress.done();
      }).catch(function (err) {
        clearTimeout(skT);
        clearTimeout(slowT);
        if (my !== seq || (err && err.name === 'AbortError')) return;
        progress.done(true);
        if (sk) sk.replaceWith(old);
        setTab(location.pathname);
        if (opts.pop) { location.reload(); return; }
        if (navigator.onLine === false) netbar.offline(); else toast(T.nav_error);
      });
    };

    var prefetch = function (k) {
      if (!k || !goodNet() || inflight[k.key] || (cache[k.key] && Date.now() - cache[k.key].t < FRESH)) return;
      load(k.key, null, null, true).catch(noop);
    };

    var start = function () {
      if (!supported) return;
      try { history.scrollRestoration = 'manual'; } catch (e) {}
      history.replaceState(Object.assign({}, history.state, { pb: 1, scroll: win.scrollY }), '');
      doc.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var k = linkOf(e);
        if (!k) {
          // Changement de langue : la barre de progression montre que ça charge
          if (e.target.closest && e.target.closest('a[data-lang]')) { local.set('lang', e.target.closest('a[data-lang]').dataset.lang); progress.start(); }
          return;
        }
        e.preventDefault();
        go(k.url.href, { push: true });
      });
      win.addEventListener('popstate', function (e) {
        var key = location.pathname + location.search;
        if (key === currentKey) return;  // simple changement d'onglet (#)
        go(location.href, { pop: true, scroll: e.state && e.state.scroll });
      });
      // Préchargement au survol ou au toucher (seulement avec une bonne connexion)
      var hoverT;
      doc.addEventListener('mouseover', function (e) {
        var k = linkOf(e);
        if (!k) return;
        clearTimeout(hoverT);
        hoverT = setTimeout(function () { prefetch(k); }, 70);
      });
      doc.addEventListener('touchstart', function (e) { prefetch(linkOf(e)); }, { passive: true });
      // Les pages légères de la barre d'onglets sont préparées quand le téléphone ne fait rien
      var idle = function () {
        $$('.tabbar a:not([aria-current])').forEach(function (a) {
          var k = keyOf(a.href);
          if (k && !/\/(index\.html)?$/.test(k.url.pathname)) prefetch(k);
        });
      };
      if (win.requestIdleCallback) win.requestIdleCallback(idle, { timeout: 6000 }); else setTimeout(idle, 3000);
    };
    // Même page, reconstruite (compte changé, vrais chiffres arrivés) en gardant la position
    var reload = function () { if (supported) go(location.href, { pop: true, fresh: true, scroll: win.scrollY }); };
    return { start: start, go: go, reload: reload };
  })();

  win.Probalis = { acct: Acct, toast: toast, fmt: fmt, money: money, esc: esc, F: F, T: T, CFG: CFG, P: P, local: local,
    session: session, params: params, cleanUrl: cleanUrl, reduced: reduced };
  router.start();
  Lk.boot(function () { init(doc); });
  Acct.boot();

  // ---------- Application installable (elle a besoin d'Internet : rien n'est gardé pour le mode hors connexion) ----------
  if ('serviceWorker' in navigator && location.protocol !== 'file:') {
    win.addEventListener('load', function () { navigator.serviceWorker.register('/sw.js').catch(noop); });
  }
})();
