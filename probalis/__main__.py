"""Commandes Probalis.

  python -m probalis build      Récupère les données, calcule les analyses et génère le site dans public/
  python -m probalis serve      Aperçu local du site sur http://localhost:8000
  python -m probalis backtest   Test de fiabilité sur une saison passée (voir probalis/football/backtest.py)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Fichiers privés lus avant la construction sur le PC (dossier des secrets, à côté du dépôt, jamais versionné).
# Sur GitHub Actions, ces réglages viennent des variables et secrets du dépôt : le dossier n'existe pas.
SECRETS_DIR = Path(os.environ.get("PROBALIS_SECRETS_DIR") or Path(__file__).resolve().parents[2] / "Probalis-secrets")
ENV_FILES = ("site-public.env", "historique.env")


def load_env_files(folder: Path = SECRETS_DIR) -> list[str]:
    """Charge les réglages NOM=valeur des fichiers privés, sans écraser ceux déjà définis. Renvoie les fichiers lus."""
    read = []
    for name in ENV_FILES:
        f = folder / name
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and v and not os.environ.get(k):
                os.environ[k] = v
        read.append(name)
    return read


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        read = load_env_files()
        if read:
            print("Réglages privés chargés :", ", ".join(read))
        from .football.pipeline import run
        from .site.build import build
        print("Analyse des prochains matchs…")
        data = run()
        rep = data["report"]
        if rep["unmatched"]:
            print("Équipes non reconnues :", *rep["unmatched"], sep="\n  ")
        if not data["matches"]:
            # Sources en panne : on ne remplace pas le site en ligne par un site vide.
            print("Aucun match analysé : site non généré.")
            sys.exit(1)
        out = build(data)
        print(f"{len(data['matches'])} matchs analysés. Site généré dans {out}")
    elif cmd == "serve":
        import functools
        import http.server
        from .site.build import PUBLIC
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(PUBLIC))
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
        print(f"Aperçu : http://localhost:{port}")
        http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
    elif cmd == "backtest":
        from .football import backtest
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        backtest.main()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
