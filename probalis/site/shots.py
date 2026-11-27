"""Captures d'écran de l'appli pour le site vitrine (outil de développement, pas utilisé par la construction).

Prend de vraies captures de l'appli avec Google Chrome (ou Edge) sans fenêtre, sur une version du site servie
en local, avec un compte Premium de démonstration pour que rien ne soit sous cadenas. Les images (JPEG, 600 et
360 px de large) vont dans probalis/site/static/shots/ et sont ensuite servies dans /assets/shots/.

Les captures montrent de VRAIS matchs et leurs VRAIES analyses (choix de l'utilisateur, 21 novembre 2026 : rien
d'inventé sur la vitrine). Elles sont figées au jour où elles sont prises : inutile de les refaire à chaque mise à
jour. Le jour où elles ont été prises est écrit dans static/shots/shots.json et affiché sous les captures de la vitrine.

Usage (depuis le dossier du dépôt, après une construction normale qui a laissé data/cache/) :
  1. python -m probalis.site.shots --prepare shots-public       (copie du vrai site, en mode démo : rien sous cadenas)
  2. le servir avec le relais du direct (capture « live ») : python -m probalis.site.shots --serve shots-public
     (Wrangler, port 8766 ; sans la capture « live », python -m http.server 8766 --directory shots-public suffit)
  3. python -m probalis.site.shots --base http://127.0.0.1:8766 --public shots-public
  4. reconstruire le site pour publier les nouvelles images (elles sont copiées dans /assets/shots/).
Capture « live » : la carte « Le match » (ESPN) d'un vrai match fini des 3 derniers jours, grand championnat d'abord.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "static" / "shots"
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
WIDTH, HEIGHT, SCALE = 390, 844, 2
OUT_WIDTHS = (600, 360)  # deux tailles : la petite pour les téléphones et les connexions lentes

# Petite page posée à côté du site, seulement pendant les captures : elle prépare le navigateur (compte Premium
# de démonstration, thème clair, coupon d'exemple, jour choisi), puis ouvre la page à photographier.
HELPER = """<!doctype html><meta charset="utf-8"><title>shot</title><script>
(async function () {
  var q = new URLSearchParams(location.search), lang = q.get('lang') || 'fr';
  var until = new Date(Date.now() + 30 * 864e5).toISOString();
  localStorage.setItem('pb-acct', JSON.stringify({ demo: true, t: Date.now(),
    user: { id: 'demo', email: 'demo@probalis.app', name: lang === 'fr' ? 'Démo' : 'Demo', avatar: null },
    profile: { premium_until: until, email_news: false, email_reminders: true, favorite_leagues: [], favorite_teams: [], lang: lang,
      country: null, is_adult: true, welcome_sent_at: new Date().toISOString(), tz: null, free_day: null, free_match: null } }));
  localStorage.setItem('theme', q.get('theme') || 'light');
  localStorage.setItem('lang', lang);
  localStorage.removeItem('pb-coupon');
  if (q.get('coupon')) {
    // Les vrais blocs (coupons du jour) sont dans /lk/ : servis sans vérification par le serveur local de démo
    var blocks = (await (await fetch('/lk/' + lang + '/paris.json')).json()).b || {};
    var d = new DOMParser().parseFromString(Object.keys(blocks).map(function (k) { return blocks[k]; }).join(''), 'text/html');
    var btn = Array.prototype.find.call(d.querySelectorAll('button[data-legs]'), function (b) {
      try { var legs = JSON.parse(b.getAttribute('data-legs')); return legs.length >= 3 && legs.every(function (l) { return new Date(l.ko) > Date.now(); }); }
      catch (e) { return false; }
    });
    if (btn) localStorage.setItem('pb-coupon', btn.getAttribute('data-legs'));
  }
  if (q.get('day')) sessionStorage.setItem('pday', q.get('day'));
  if (q.get('tier')) sessionStorage.setItem('ptier', q.get('tier'));
  sessionStorage.setItem('tkmode', 'mine');
  location.replace(q.get('go'));
})();
</script>"""


def prepare(src_public: Path, out: Path) -> None:
    """Construit dans `out` une copie du vrai site à photographier : mêmes matchs, mêmes analyses, même historique,
    mais en mode démo (sans Supabase) pour qu'un compte Premium de démonstration voie tout."""
    for k in ("PROBALIS_SUPABASE_URL", "PROBALIS_SUPABASE_ANON_KEY"):
        os.environ.pop(k, None)
    from . import build, history
    src = build.full_data_file()
    if not src.exists():
        src = build.locked_dir(src_public) / "data" / "matches.json"
    data = json.loads(src.read_text(encoding="utf-8"))
    out = out.resolve()
    build.PUBLIC = out
    build.ROOT = out.parent / f"{out.name}-root"
    real = history.LOCAL
    history.LOCAL = out.parent / f"{out.name}-history.json"  # copie : le vrai historique n'est jamais modifié ici
    history.LOCAL.unlink(missing_ok=True)
    if real.exists():
        shutil.copyfile(real, history.LOCAL)
    load = history.load
    history.load = lambda site_url: load("")  # copie locale seulement, sans relire le site en ligne
    build.build(data)
    print(f"Copie du vrai site prête dans {out}")


def _browser() -> str:
    for b in BROWSERS:
        if Path(b).exists():
            return b
    raise SystemExit("Ni Edge ni Chrome trouvé.")


def _big_match(public: Path) -> dict:
    data = json.loads((public / "lk" / "data" / "matches.json").read_text(encoding="utf-8"))  # mode démo : lk/
    now = datetime.now(timezone.utc)
    soon = [m for m in data["matches"] if datetime.fromisoformat(m["kickoff"]) > now + timedelta(hours=2)
            and m["league"] in ("E0", "SP1", "I1", "D1", "F1", "UCL") and m.get("confidence") == "high"]
    soon.sort(key=lambda m: (-(m.get("stature") or 0), m["kickoff"]))
    if not soon:
        raise SystemExit("Aucun grand match à venir pour la capture.")
    return soon[0]


PRIME = ("E0", "SP1", "I1", "D1", "F1", "UCL", "UEL")


def _live_match(public: Path) -> dict | None:
    """Match fini le plus récent (3 derniers jours) relié à ESPN, grand championnat d'abord, pour la capture « live »."""
    hist = json.loads((public / "data" / "history.json").read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    cands = []
    for e in (hist.get("days") or {}).values():
        for mid, mt in (e.get("matches") or {}).items():
            ko = datetime.fromisoformat(mt["kickoff"])
            if mt.get("espn") and mt.get("score") and mid in (e.get("an") or {}) and now - timedelta(days=3) < ko < now:
                cands.append((mt["league"] in PRIME, ko, mt))
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return cands[0][2]


def serve(public: Path, port: int = 8766) -> None:
    """Sert `public` avec le seul relais du direct (/live/), comme en ligne, pour les captures. Le gardien /lk/ n'y est
    pas : en mode démo, l'appli lit les blocs Premium directement."""
    from . import build
    from ..deploy import patched_cli
    root = Path(tempfile.mkdtemp(prefix="probalis-live-"))
    fn = root / "functions" / "live"
    fn.mkdir(parents=True)
    shutil.copy2(build.LIVE_FN, fn / "[[path]].js")
    cli = patched_cli()
    print(f"Site servi avec le relais du direct : http://127.0.0.1:{port}")
    try:
        subprocess.run(["node", "--no-warnings", str(cli), "pages", "dev", str(public.resolve()), "--port", str(port),
                        "--ip", "127.0.0.1"], cwd=root, check=False)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _jpeg(src: Path, dst: Path, width: int) -> None:
    """Réduit la capture et l'enregistre en JPEG avec les outils de Windows (aucune bibliothèque à installer)."""
    script = (
        "Add-Type -AssemblyName System.Drawing;"
        "$s=[System.Drawing.Image]::FromFile($env:SHOT_IN);$w=[int]$env:SHOT_W;$h=[int]($s.Height*$w/$s.Width);"
        "$b=New-Object System.Drawing.Bitmap $w,$h;$g=[System.Drawing.Graphics]::FromImage($b);"
        "$g.InterpolationMode='HighQualityBicubic';$g.SmoothingMode='HighQuality';$g.PixelOffsetMode='HighQuality';"
        "$g.DrawImage($s,0,0,$w,$h);"
        "$c=[System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders()|Where-Object{$_.MimeType -eq 'image/jpeg'};"
        "$p=New-Object System.Drawing.Imaging.EncoderParameters 1;"
        "$p.Param[0]=New-Object System.Drawing.Imaging.EncoderParameter([System.Drawing.Imaging.Encoder]::Quality,[long]80);"
        "$b.Save($env:SHOT_OUT,$c,$p);$g.Dispose();$b.Dispose();$s.Dispose()")
    env = dict(os.environ, SHOT_IN=str(src), SHOT_OUT=str(dst), SHOT_W=str(width))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True, env=env)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8766")
    ap.add_argument("--public", default="public", help="dossier servi à l'adresse --base")
    ap.add_argument("--only", nargs="*", help="noms des captures à refaire (matches, match, bets, ticket, history, live)")
    ap.add_argument("--serve", metavar="DOSSIER", help="servir ce dossier avec le relais du direct, puis rien d'autre")
    ap.add_argument("--prepare", metavar="DOSSIER", help="construire d'abord le site d'exemple dans ce dossier")
    args = ap.parse_args()
    if args.prepare:
        prepare(Path(args.public), Path(args.prepare))
        return
    if args.serve:
        serve(Path(args.serve))
        return
    public = Path(args.public)
    big = _big_match(public)
    days = sorted({m["kickoff"][:10] for m in json.loads((public / "lk" / "data" / "matches.json").read_text(encoding="utf-8"))["matches"]})
    day = big["kickoff"][:10] if big["kickoff"][:10] in days else days[0]  # le jour du grand match photographié
    shots = {
        "matches": ("index.html", {}),
        "match": (f"match/{big['slug']}.html", {}),
        "bets": ("paris.html", {"day": day, "tier": "safe"}),
        "ticket": ("ticket.html", {"coupon": "1"}),
        "history": ("historique.html", {}),
    }
    live = _live_match(public)
    if live:  # la carte « Le match » d'un vrai match fini, en haut de l'écran
        shots["live"] = (f"match/{live['slug']}.html%23lv-title-{live['slug']}", {})
    elif not args.only or "live" in args.only:
        raise SystemExit("Aucun match fini relié à ESPN pour la capture « live ».")
    helper = public / "__shot.html"
    helper.write_text(HELPER, encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="probalis-shots-"))
    try:
        for lang in ("fr", "en"):
            for name, (path, extra) in shots.items():
                if args.only and name not in args.only:
                    continue
                q = "&".join(f"{k}={v}" for k, v in {"lang": lang, **extra}.items())
                url = f"{args.base}/__shot.html?{q}&go=/{lang}/{path}"
                png = tmp / f"{lang}-{name}.png"
                profile = tmp / f"profile-{lang}-{name}"
                # Chrome est piloté par shots_cdp.mjs (Node) : seule façon fiable d'avoir un vrai écran de téléphone.
                subprocess.run(["node", str(HERE / "shots_cdp.mjs"), _browser(), str(profile), str(png), url,
                                str(WIDTH), str(HEIGHT), str(SCALE)], check=True, timeout=180)
                if not png.exists():
                    raise SystemExit(f"Le navigateur n'a pas écrit la capture {png.name}.")
                for width in OUT_WIDTHS:
                    dst = OUT / f"{lang}-{name}-{width}.jpg"
                    _jpeg(png, dst, width)
                    print(f"{dst.name} : {dst.stat().st_size // 1024} Ko ({path})")
        if not args.only:
            # Jour où les captures ont été prises (heure d'Afrique centrale et de l'Ouest, UTC+1) : elles montrent des
            # matchs de plusieurs jours (aujourd'hui, demain, le grand match de la semaine), d'où la date de prise de vue.
            taken = datetime.now(timezone(timedelta(hours=1))).date().isoformat()
            (OUT / "shots.json").write_text(json.dumps({"day": taken, "match": big["slug"], "live": live["slug"]}, indent=1),
                                            encoding="utf-8")
    finally:
        helper.unlink(missing_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
