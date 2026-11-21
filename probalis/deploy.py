"""Mise en ligne du dossier public/ sur Cloudflare Pages, par petits paquets (connexion lente ou instable).

    .venv\\Scripts\\python.exe -m probalis.deploy

Pourquoi : Wrangler envoie les fichiers par paquets d'environ 40 Mo, trois à la fois. Sur une connexion à ~1 Mbit/s
qui coupe de temps en temps (ECONNRESET), un paquet met plus de 10 minutes et la coupure arrive avant la fin : l'envoi
échoue à chaque fois (constaté le 21 novembre 2026). Ce programme fabrique, à côté de l'original et sans le modifier,
une copie de Wrangler qui :
  - envoie des paquets de 2 Mo au plus, deux à la fois ;
  - réessaie un paquet jusqu'à 60 fois, en attendant 8 secondes au plus entre deux essais ;
  - renouvelle le jeton d'envoi de Cloudflare 5 minutes avant qu'il expire (il dure environ 30 minutes) ;
  - enregistre chaque paquet reçu tout de suite, pour qu'un nouvel essai ne le renvoie pas.
Puis il lance la mise en ligne, et la relance jusqu'à 6 fois si elle échoue quand même.

Il faut que l'ordinateur soit connecté à Cloudflare (wrangler login, déjà fait une fois) et que le site soit construit.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

WRANGLER = "4.165.0"  # version testée : les motifs remplacés ci-dessous viennent de cette version
PROJECT, BRANCH = "probalis", "main"
ROOT = Path(__file__).resolve().parents[1]
PATCHED = "cli-petits-paquets.js"
TRIES = 6

REPLACE = [
    ("MAX_BUCKET_SIZE$1 = 41943040;", "MAX_BUCKET_SIZE$1 = 2097152;"),
    ("MAX_BUCKET_FILE_COUNT = isWindows$3 ? 1e3 : 2e3;", "MAX_BUCKET_FILE_COUNT = 200;"),
    ("const queue = new PQueue({ concurrency: 3 });", "const queue = new PQueue({ concurrency: 2 });"),
    ('if (attempts < 5) {\n\t\t\t\t\t\tlogger$4.debug("failed:", e, "retrying...");\n'
     '\t\t\t\t\t\tawait new Promise((resolvePromise) => setTimeout(resolvePromise, Math.pow(2, attempts) * 1e3));',
     'if (attempts < 60) {\n\t\t\t\t\t\tlogger$4.debug("failed:", e, "retrying...");\n'
     '\t\t\t\t\t\tawait new Promise((resolvePromise) => setTimeout(resolvePromise, Math.min(Math.pow(2, attempts), 8) * 1e3));'),
    ('logger$4.debug("POST /pages/assets/upload");',
     'try { if (decodeJwtPayload(jwt).exp - Date.now() / 1e3 < 300) jwt = await fetchJwt(); } catch (_e) {}\n'
     '\t\t\t\t\tlogger$4.debug("POST /pages/assets/upload");'),
    ('logger$4.debug("result:", res);',
     'logger$4.debug("result:", res);\n'
     '\t\t\t\t\ttry { await fetchResult$2(COMPLIANCE_REGION_CONFIG_PUBLIC, `/pages/assets/upsert-hashes`, { method: "POST", '
     'headers: { "Content-Type": "application/json", Authorization: `Bearer ${jwt}` }, '
     'body: JSON.stringify({ hashes: bucket.files.map(({ hash }) => hash) }) }); } catch (_e) {}'),
]


def _find_cli() -> Path | None:
    """cli.js de Wrangler WRANGLER dans le cache de npx."""
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "npm-cache" / "_npx"
    for pkg in base.glob("*/node_modules/wrangler/package.json"):
        try:
            if json.loads(pkg.read_text(encoding="utf-8")).get("version") == WRANGLER:
                return pkg.parent / "wrangler-dist" / "cli.js"
        except (OSError, ValueError):
            continue
    return None


def patched_cli() -> Path:
    cli = _find_cli()
    if cli is None:  # premier usage : npx télécharge Wrangler dans son cache
        subprocess.run(f"npx --yes wrangler@{WRANGLER} --version", shell=True, check=True)
        cli = _find_cli()
    if cli is None:
        sys.exit(f"Wrangler {WRANGLER} introuvable dans le cache de npx.")
    s = cli.read_text(encoding="utf-8")
    for old, new in REPLACE:
        if s.count(old) != 1:
            sys.exit(f"Wrangler a changé : motif introuvable ({old[:50]!r}). Garder la version {WRANGLER}.")
        s = s.replace(old, new)
    out = cli.with_name(PATCHED)  # à côté de l'original, pour que ses chemins relatifs marchent
    out.write_text(s, encoding="utf-8")
    return out


def main() -> None:
    public = ROOT / "public"
    if not (public / "index.html").exists():
        sys.exit("Site pas construit : lancer d'abord  python -m probalis build")
    cli = patched_cli()
    cmd = ["node", "--no-warnings", str(cli), "pages", "deploy", str(public), f"--project-name={PROJECT}",
           f"--branch={BRANCH}", "--commit-dirty=true"]
    for i in range(1, TRIES + 1):
        print(f"Mise en ligne, essai {i}/{TRIES}…", flush=True)
        if subprocess.run(cmd, cwd=ROOT).returncode == 0:
            print("Site en ligne.")
            return
        time.sleep(10)
    sys.exit("La mise en ligne a échoué plusieurs fois : vérifier la connexion internet, puis relancer.")


if __name__ == "__main__":
    main()
