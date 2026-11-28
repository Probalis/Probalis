"""Chance en direct des paris du match (mise à niveau 5)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from probalis.core import inplay
from probalis.core.markets import full_time_markets
from probalis.core.scores import score_matrix
from probalis.football import endirect
from probalis.site import build, i18n

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "probalis" / "site"
PROFILE = [1 / 90] * 90


def _market(ft, key, line, sel):
    m = next(m for m in full_time_markets(ft) if m.key == key and m.line == line)
    return m.selections[sel].prob


def test_at_kickoff_same_chances_as_the_analysis():
    """Au coup d'envoi (0-0, 0 minute), la chance en direct est celle de l'analyse d'avant-match."""
    lam, mu, rho = 1.62, 1.08, -0.09
    ft = score_matrix(lam, mu, rho)
    live = inplay.final_matrix(lam, mu, 0, 0, 0, PROFILE, rho=rho)
    for key, line, sel in (("1x2", None, "1"), ("1x2", None, "X"), ("ou", 2.5, "over"), ("btts", None, "yes"),
                           ("dc", None, "1X"), ("tt2", 0.5, "over")):
        assert inplay.prob(live, key, line, sel) == pytest.approx(_market(ft, key, line, sel), abs=2e-4), (key, sel)


def test_goals_already_scored_count_and_time_running_out():
    lam, mu = 1.5, 1.2
    two_nil = inplay.final_matrix(lam, mu, 2, 0, 60, PROFILE)
    assert inplay.prob(two_nil, "ou", 1.5, "over") == pytest.approx(1.0)
    assert inplay.prob(two_nil, "1x2", None, "1") > 0.85
    one_one = inplay.final_matrix(lam, mu, 1, 1, 30, PROFILE)
    assert inplay.prob(one_one, "btts", None, "yes") == pytest.approx(1.0)
    # À la 90e, le score ne bouge plus ; plus le temps passe à 0-0, moins « plus de 2,5 buts » a de chance
    end = inplay.final_matrix(lam, mu, 0, 0, 90, PROFILE)
    assert inplay.prob(end, "1x2", None, "X") == pytest.approx(1.0)
    p = [inplay.prob(inplay.final_matrix(lam, mu, 0, 0, t, PROFILE), "ou", 2.5, "over") for t in (0, 30, 60, 80)]
    assert p == sorted(p, reverse=True)


def test_goals_scored_tell_about_the_match():
    """Avec kappa, un 0-0 à la 60e fait baisser les buts attendus ; un 3-2 les fait monter. Rien ne change au coup d'envoi."""
    lam, mu = 1.5, 1.2
    plain = inplay.prob(inplay.final_matrix(lam, mu, 0, 0, 60, PROFILE), "ou", 0.5, "over")
    closed = inplay.prob(inplay.final_matrix(lam, mu, 0, 0, 60, PROFILE, kappa=4), "ou", 0.5, "over")
    assert closed < plain
    open_ = inplay.prob(inplay.final_matrix(lam, mu, 3, 2, 60, PROFILE, kappa=4), "ou", 5.5, "over")
    assert open_ > inplay.prob(inplay.final_matrix(lam, mu, 3, 2, 60, PROFILE), "ou", 5.5, "over")
    k0 = inplay.final_matrix(lam, mu, 0, 0, 0, PROFILE, kappa=4, kmode="team")
    assert np.allclose(k0, inplay.final_matrix(lam, mu, 0, 0, 0, PROFILE))


def test_red_card_helps_the_other_team():
    base = inplay.final_matrix(1.4, 1.4, 0, 0, 30, PROFILE)
    red_home = inplay.final_matrix(1.4, 1.4, 0, 0, 30, PROFILE, ["h"], (0.7, 1.3))
    assert inplay.prob(red_home, "1x2", None, "2") > inplay.prob(base, "1x2", None, "2")


def test_espn_minutes_and_match_state():
    assert endirect._minute({"displayValue": "45'+2'", "value": 2700}) == (45, 2, 1)
    assert endirect._minute({"displayValue": "90'+3'", "value": 5400}) == (90, 3, 2)
    assert endirect._minute({"displayValue": "67'", "value": 3979}) == (67, 0, 2)
    m = {"goals": [[12, 0, 1, "h"], [45, 2, 1, "a"], [58, 0, 2, "h"], [90, 4, 2, "a"]], "reds": [[50, 0, 2, "a"]]}
    assert endirect.state(m, "30")[:2] == (1, 0)
    assert endirect.state(m, "ht")[:3] == (1, 1, 45)
    assert endirect.state(m, "60") == (2, 1, 60, ["a"])
    assert endirect.state(m, "85")[:2] == (2, 1)
    # Un but contre son camp peut être rangé du côté du joueur : on retourne ces buts-là si le score ne colle pas
    e = {"sc": [1, 1], "d": [["g", 10, 0, 1, "h"], ["o", 70, 0, 2, "h"]]}
    assert endirect._goals_ok(e) == [[10, 0, 1, "h"], [70, 0, 2, "a"]]


def test_learned_profile_and_config():
    ms = [{"goals": [[10, 0, 1, "h"], [45, 1, 1, "a"], [88, 0, 2, "h"], [90, 5, 2, "a"]]}] * 3
    prof = endirect.learn_profile(ms)
    assert len(prof) == 90 and sum(prof) == pytest.approx(1.0, abs=1e-4)
    cfg = build._inplay_cfg({"profile": prof, "reds": [0.7, 1.3]})
    assert cfg["r"][0] == pytest.approx(1.0) and cfg["r"][90] == 0
    assert all(a >= b for a, b in zip(cfg["r"], cfg["r"][1:]))
    v = {"key": "ou", "line": 2.5, "sel": "over", "yes": False, "p": 0.61}
    assert build._ip_code(v) == "ou|2.5|over|0|0.61"
    assert build._ip_code({"key": "btts", "line": None, "sel": "yes", "yes": True, "p": 0.6}) == "btts||yes|1|0.6"


def test_saved_settings_if_present():
    """Le fichier appris (s'il existe) : un profil complet, testé sur une saison jamais vue."""
    path = SITE / "inplay.json"
    if not path.exists():
        pytest.skip("inplay.json pas encore appris")
    ip = json.loads(path.read_text(encoding="utf-8"))
    assert len(ip["profile"]) == 90 and sum(ip["profile"]) == pytest.approx(1.0, abs=1e-3)
    t = ip["tested"]
    assert t["season"] != t["train"] and t["bets"] > 1000 and abs(t["rate"] - t["announced"]) < 0.03


@pytest.mark.skipif(not shutil.which("node"), reason="node absent")
def test_app_js_computes_like_python():
    """Le calcul de app.js (InPlay) donne les mêmes chances que probalis/core/inplay.py."""
    js = (SITE / "static" / "app.js").read_text(encoding="utf-8")
    calc = re.search(r"// <inplay-calc>.*?\n(.*?)// </inplay-calc>", js, re.S).group(1)
    raw = [0.008 + k * 0.00006 for k in range(90)]  # on marque un peu plus en fin de match
    prof = [x / sum(raw) for x in raw]
    rest = build._inplay_cfg({"profile": prof, "reds": [0.7, 1.3], "kappa": 6, "kmode": "team"})
    cases = [(1.7, 1.1, -0.08, 0, 0, 0, [], "1x2", None, "1"), (1.7, 1.1, -0.08, 1, 0, 37, [], "ou", 2.5, "over"),
             (1.2, 1.4, -0.05, 0, 1, 45, ["h"], "btts", None, "yes"), (0.9, 1.6, 0.0, 2, 2, 78, ["a", "h"], "dc", None, "X2"),
             (1.3, 1.3, -0.1, 0, 0, 88, [], "tt1", 0.5, "over")]
    script = ("var CFG = { ip: " + json.dumps(rest) + " };\nvar svg = function () { return ''; };\n" + calc +
              "\nconsole.log(JSON.stringify(" + json.dumps(cases) + ".map(function (c) {"
              " return chance([c[0], c[1]], c[2], c[3], c[4], c[5], c[6], c[7], c[8], c[9]); })));")
    out = json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)
    red = tuple(rest["red"])
    for c, got in zip(cases, out):
        lam, mu, rho, h, a, t, reds, key, line, sel = c
        fm = inplay.final_matrix(lam, mu, h, a, t, prof, reds, red, rho, 6, "team")
        assert got == pytest.approx(inplay.prob(fm, key, line, sel), abs=1e-3), c


def test_page_carries_live_data_only_inside_premium_block():
    tpl = (SITE / "templates" / "match.html").read_text(encoding="utf-8")
    block = tpl.split('{% call lk(m=m.slug) %}<div class="vd-wrap', 1)[1].split("{% endcall %}", 1)[0]
    assert 'data-xg="{{ m.vd.xg }}"' in block and 'data-ip="{{ m.vd.top.ip }}"' in block and 'data-ip="{{ v.ip }}"' in block
    js = (SITE / "static" / "app.js").read_text(encoding="utf-8")
    assert "InPlay.paint(scope, d, l);" in js


def test_texts_in_both_languages():
    for lang in i18n.LANGS:
        assert all(i18n._JS[lang].get(k) for k in ("ip_live", "ip_now_won", "ip_now_lost", "ip_won", "ip_lost",
                                                   "ip_count_co", "ip_count_ca", "ip_hero", "ip_et", "ip_up", "ip_down"))
        assert "{n}" in i18n.UI[lang]["ip_proof"] and i18n.UI[lang]["ip_proof_counts"]
