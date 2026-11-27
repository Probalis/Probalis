"""La vitrine : chaque chapitre de la visite a son icône, sa capture et son texte de remplacement.

Ajouter un chapitre (comme « Le match en direct » le 26/11/2026) ne doit pas faire planter la construction.
"""
import re
from pathlib import Path

from probalis.site import icons, site_text, i18n

TEMPLATE = Path(__file__).resolve().parents[1] / "probalis" / "site" / "templates" / "site.html"


def _chapter_icons() -> dict[str, str]:
    html = TEMPLATE.read_text(encoding="utf-8")
    m = re.search(r"icon\(\{([^}]*)\}\.get\(c\.shot", html)
    assert m, "les icônes des chapitres doivent être choisies par capture, pas par numéro"
    return dict(re.findall(r"'([a-z_]+)':\s*'([a-z_]+)'", m.group(1)))


def test_every_tour_chapter_has_icon_shot_and_alt_text():
    chosen = _chapter_icons()
    for name in chosen.values():
        assert name in icons.PATHS, name
    for lang in i18n.LANGS:
        s = site_text.SITE[lang]
        assert len(s["tour"]) >= 5
        for c in s["tour"]:
            assert c["shot"] in chosen, (lang, c["shot"])
            assert s.get("shot_alt_" + c["shot"]), (lang, c["shot"])
            assert c["tab"] and c["h3"] and c["p"]
    assert [c["shot"] for c in site_text.SITE["fr"]["tour"]] == [c["shot"] for c in site_text.SITE["en"]["tour"]]
