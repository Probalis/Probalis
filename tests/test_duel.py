"""Les deux équipes en chiffres (fiche, « Forme et face-à-face ») : barres et meilleure des deux."""
from probalis.site import build

M = {"home": {"name": "Alpha"}, "away": {"name": "Beta"}}


def _raw(n, pts, gf, ga, cs, btts, o25):
    return {"n": n, "pts": pts, "gf": gf, "ga": ga, "cs": cs, "btts": btts, "o25": o25}


def test_duel_values_and_leader():
    raw = {"home": _raw(5, 10, 9, 3, 2, 3, 4), "away": _raw(5, 4, 5, 8, 0, 4, 4)}
    d = build._duel_view(raw, M, "fr")
    rows = {r["label"]: r for r in d["rows"]}
    pts = rows["Points par match"]
    assert (pts["h"], pts["a"], pts["lead"]) == ("2,0", "0,8", "home")
    assert abs(pts["w"] - 71.4) < 0.05 and abs(pts["w"] + pts["wa"] - 100) < 0.05
    # Buts encaissés : la meilleure est celle qui en prend le moins
    assert rows["Buts encaissés par match"]["lead"] == "home"
    assert rows["Matchs sans encaisser"]["h"] == "2/5"
    # Ni mieux ni moins bien : pas de couleur
    btts = rows["Les deux équipes ont marqué"]
    assert btts["neutral"] and btts["lead"] is None
    assert d["lead"].startswith("Sur leurs 5 derniers matchs")


def test_duel_equal_zero_and_mixed_counts():
    raw = {"home": _raw(5, 5, 0, 5, 0, 0, 1), "away": _raw(3, 3, 0, 3, 0, 0, 0)}
    d = build._duel_view(raw, M, "en")
    gf = next(r for r in d["rows"] if r["label"] == "Goals scored per match")
    assert gf["w"] == 50.0 and gf["lead"] is None  # 0 contre 0 : moitié-moitié, personne devant
    pts = next(r for r in d["rows"] if r["label"] == "Points per match")
    assert pts["lead"] is None  # 1 point par match des deux côtés (taux, pas totaux)
    assert "5 for Alpha, 3 for Beta" in d["lead"]
