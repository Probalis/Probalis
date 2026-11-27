// Capture d'une page comme sur un téléphone, en pilotant Chrome par le protocole DevTools (aucun paquet à installer).
// Appelé par shots.py : node shots_cdp.mjs <chrome.exe> <dossier-profil> <sortie.png> <adresse> [largeur] [hauteur] [échelle]
import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';

const [browser, profile, out, url, w = '390', h = '844', scale = '2'] = process.argv.slice(2);
const port = 9300 + Math.floor(Math.random() * 500);
const chrome = spawn(browser, ['--headless', '--disable-gpu', '--hide-scrollbars', '--no-first-run',
  '--no-default-browser-check', '--disable-extensions', `--user-data-dir=${profile}`,
  `--remote-debugging-port=${port}`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function target() {
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find((t) => t.type === 'page');
      if (page) return page.webSocketDebuggerUrl;
    } catch (e) { /* Chrome démarre encore */ }
    await sleep(250);
  }
  throw new Error('Chrome ne répond pas');
}

try {
  const ws = new WebSocket(await target());
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0;
  const waiting = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && waiting.has(msg.id)) { waiting.get(msg.id)(msg); waiting.delete(msg.id); }
  };
  const send = (method, params = {}) => new Promise((r) => { id += 1; waiting.set(id, r); ws.send(JSON.stringify({ id, method, params })); });
  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: +w, height: +h, deviceScaleFactor: +scale, mobile: +w < 700 });
  if (+w < 700) await send('Emulation.setTouchEmulationEnabled', { enabled: true, maxTouchPoints: 5 });
  await send('Page.navigate', { url });
  // La page d'aide prépare le navigateur puis redirige : on attend que la vraie page soit chargée et posée.
  const goal = (new URL(url).searchParams.get('go') || '').split('#')[0];
  for (let i = 0; i < 80; i++) {
    const r = await send('Runtime.evaluate', { expression: 'location.pathname + "|" + document.readyState', returnByValue: true });
    const [path, state] = String(r.result?.result?.value || '').split('|');
    if ((!goal || path === goal || path === goal.replace(/\.html$/, '')) && state === 'complete') break;
    await sleep(250);
  }
  await sleep(2500);
  await send('Runtime.evaluate', { expression: 'document.fonts && document.fonts.ready', awaitPromise: true });
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(out, Buffer.from(shot.result.data, 'base64'));
  ws.close();
} finally {
  chrome.kill();
}
