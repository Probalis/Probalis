"""« Le mot de Probalis » (27/11/2026) : meilleur angle, risque principal, à éviter, tirés des chiffres de l'analyse."""
from probalis.core import mot
from probalis.core import verdicts as vd


def _markets(p1, px, p2, over25=0.5, btts=0.5, tt1=0.8, tt2=0.7, over15=0.7, over35=0.3):
    return [
        {"key": "1x2", "line": None, "sel": {"1": {"p": p1}, "X": {"p": px}, "2": {"p": p2}}},
        {"key": "dc", "line": None, "sel": {"1X": {"p": p1 + px}, "X2": {"p": px + p2}, "12": {"p": p1 + p2}}},
        {"key": "ou", "line": 1.5, "sel": {"over": {"p": over15}, "under": {"p": 1 - over15}}},
        {"key": "ou", "line": 2.5, "sel": {"over": {"p": over25}, "under": {"p": 1 - over25}}},
        {"key": "ou", "line": 3.5, "sel": {"over": {"p": over35}, "under": {"p": 1 - over35}}},
        {"key": "btts", "line": None, "sel": {"yes": {"p": btts}, "no": {"p": 1 - btts}}},
        {"key": "tt1", "line": 0.5, "sel": {"over": {"p": tt1}, "under": {"p": 1 - tt1}}},
        {"key": "tt2", "line": 0.5, "sel": {"over": {"p": tt2}, "under": {"p": 1 - tt2}}},
        {"key": "score", "line": None, "sel": {"1-1": {"p": 0.12}, "1-0": {"p": 0.10}, "other": {"p": 0.78}}},
    ]


def test_angle_is_the_first_match_pick_and_risk_is_how_it_loses():
    mk = _markets(0.45, 0.27, 0.28, over35=0.31)
    w = mot.mot(mk)
    vs = vd.verdicts(mk)
    assert w["angle"] == vs[vd.picks(vs)[0]]
    a = w["angle"]
    if a["fam"] == "dc":                          # une double chance ne perd que sur le 3e résultat
        assert w["risk"]["k"] in ("win", "draw") and abs(w["risk"]["p"] - (1 - a["p"])) < 1e-6
    else:                                         # moins de 3,5 buts à 69 % : il perd à 4 buts ou plus
        assert w["risk"]["k"] == "goals_min" and w["risk"]["n"] == 4


def test_risk_of_each_kind_of_bet():
    mk = _markets(0.6, 0.22, 0.18)
    win = {"fam": "win", "key": "1x2", "line": None, "sel": "1", "yes": True, "p": 0.6, "side": "1"}
    assert mot.risk(mk, win) == {"k": "draw", "p": 0.22}
    over = {"fam": "ou1.5", "key": "ou", "line": 1.5, "sel": "over", "yes": True, "p": 0.7}
    assert mot.risk(mk, over) == {"k": "goals_max", "n": 1, "p": 0.30000000000000004} or \
        mot.risk(mk, over)["k"] == "goals_max"
    btts = {"fam": "btts", "key": "btts", "line": None, "sel": "yes", "yes": True, "p": 0.62}
    assert mot.risk(mk, btts)["k"] == "blank" and mot.risk(mk, btts)["side"] == "2"   # l'équipe 2 marque moins
    co = {"fam": "co", "key": "co", "line": 9.5, "sel": "over", "yes": False, "p": 0.66}
    assert mot.risk(mk, co)["k"] == "corners_min" and mot.risk(mk, co)["n"] == 10


def test_avoid_shaky_favourite_then_coin_flip_then_exact_score():
    assert mot.mot(_markets(0.48, 0.27, 0.25))["avoid"]["k"] == "fav"
    w = mot.mot(_markets(0.62, 0.22, 0.16, btts=0.51))
    assert w["avoid"]["k"] == "coin" and w["avoid"]["fam"] == "btts"
    w = mot.mot(_markets(0.62, 0.22, 0.16, btts=0.40, over25=0.40))
    assert w["avoid"] == {"k": "score", "score": "1-1", "p": 0.12}


def test_happened_settles_risks_and_avoids():
    assert mot.happened({"k": "draw", "p": 0.2}, 1, 1)
    assert mot.happened({"k": "goals_min", "n": 4, "p": 0.3}, 3, 1)
    assert not mot.happened({"k": "blank", "side": "2", "p": 0.3}, 0, 1)
    assert mot.happened({"k": "score", "score": "2-1", "p": 0.1}, 2, 1)
    assert mot.happened({"k": "corners_max", "n": 9, "p": 0.3}, 0, 0, {"corners": [4, 5]})
    assert mot.happened({"k": "cards_min", "n": 5, "p": 0.3}, 0, 0, {}) is None


def test_match_page_sentences_fr_and_en():
    from probalis.site import build, i18n
    m = {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}, "markets": _markets(0.45, 0.27, 0.28, over35=0.31)}
    fr = build._mot_view(m, "fr")
    assert fr["angle"].startswith("« ") and "cote ≈ 1," in fr["angle"]
    assert fr["risk"][0].isupper() and "fois sur 10" in fr["risk"]
    assert fr["avoid"] == f"Victoire Arsenal : seulement {i18n.pct(0.45, 'fr')}, presque pile ou face."
    en = build._mot_view(m, "en")
    assert en["avoid"] == "Arsenal win: only 45%, close to a coin flip."
    none = build._mot_view({**m, "markets": _markets(0.44, 0.14, 0.42, over15=0.58, over25=0.45, over35=0.45,
                                                    tt1=0.58, tt2=0.58, btts=0.45)}, "fr")
    assert none["angle"] == "Aucun pari assez sûr à une cote de 1,30 ou plus sur ce match."
    assert "risk" not in none
