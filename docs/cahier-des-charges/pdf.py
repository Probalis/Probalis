"""Fabrique le PDF du cahier des charges à partir de sa source HTML, avec Google Chrome (ou Edge) sans fenêtre.

    .venv\\Scripts\\python.exe docs\\cahier-des-charges\\pdf.py

Source : docs/cahier-des-charges/cahier-des-charges.html (à modifier à chaque évolution du projet).
Résultat : docs/cahier-des-charges/Probalis-cahier-des-charges.pdf
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "cahier-des-charges.html"
OUT = HERE / "Probalis-cahier-des-charges.pdf"
BROWSERS = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]


def main() -> None:
    browser = next((b for b in BROWSERS if Path(b).exists()), None)
    if not browser:
        sys.exit("Ni Chrome ni Edge trouvé : ouvre cahier-des-charges.html dans un navigateur et fais Imprimer → PDF.")
    with tempfile.TemporaryDirectory(prefix="probalis-cdc-") as profile:
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={profile}",
                        "--no-pdf-header-footer", "--virtual-time-budget=4000", f"--print-to-pdf={OUT}",
                        SRC.as_uri()], check=True, timeout=180, capture_output=True)
    if not OUT.exists():
        sys.exit("Le navigateur n'a pas écrit le PDF.")
    print(f"{OUT} ({OUT.stat().st_size // 1024} Ko)")


if __name__ == "__main__":
    main()
