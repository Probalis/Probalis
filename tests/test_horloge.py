"""Horloge des calculs (minuteur Cloudflare, cloudflare/horloge/worker.mjs) : ses tests sont en JavaScript."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js absent")
def test_horloge_cloudflare():
    r = subprocess.run(["node", str(ROOT / "cloudflare" / "horloge" / "test.mjs")], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "tous les tests réussis" in r.stdout
