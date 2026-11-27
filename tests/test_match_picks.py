"""Paris du match (27/11/2026) : au plus 3 par match, cote estimée d'au moins 1,30, chance d'au moins 60 %, types
différents, au plus un sur les corners ou les cartons. Demandé par le porteur du projet : trop de verdicts à 1,10
embrouillaient le choix."""
from probalis.core import verdicts as vd


def _v(fam, p, key=None, line=None, yes=True, open_=False):
    return {"fam": fam, "key": key or fam, "line": line, "sel": "over", "yes": yes, "p": p, "open": open_}


def test_book_odds_is_fair_odds_over_margin():
    assert round(vd.book_odds(0.5), 3) == 1.905          # cote juste 2,00 / 1,05
    assert vd.book_odds(0.733) < 1.30 < vd.book_odds(0.732)


def test_low_odds_close_calls_and_weak_chances_are_left_out():
    vs = [_v("tt", 0.90, "tt1", 0.5),        # cote ≈ 1,06 : trop basse
          _v("dc", 0.82, "dc"),              # cote ≈ 1,16 : trop basse
          _v("ou1.5", 0.58, "ou", 1.5),      # moins de 60 %
          _v("btts", 0.52, open_=True)]      # serré
    assert vd.picks(vs) == []


def test_at_most_three_picks_of_different_kinds_safest_first():
    vs = [_v("win", 0.62, "1x2"), _v("dc", 0.72, "dc"),              # même type (résultat) : un seul
          _v("ou1.5", 0.70, "ou", 1.5), _v("ou3.5", 0.71, "ou", 3.5, yes=False),   # même type (buts) : un seul
          _v("btts", 0.64), _v("tt", 0.66, "tt2", 0.5),
          _v("co", 0.69, "co", 9.5), _v("ca", 0.68, "ca", 4.5)]
    got = vd.picks(vs)
    assert len(got) == vd.PICK_MAX == 3
    assert [vs[i]["fam"] for i in got] == ["dc", "ou3.5", "co"]      # 72 %, 71 %, 69 % : types différents
    assert all(vd.book_odds(vs[i]["p"]) >= 1.30 for i in got)


def test_corners_and_cards_count_as_one_kind():
    vs = [_v("co", 0.70, "co", 8.5), _v("ca", 0.69, "ca", 3.5), _v("btts", 0.61)]
    got = vd.picks(vs)
    assert [vs[i]["fam"] for i in got] == ["co", "btts"]


def test_match_page_shows_only_the_picks_with_their_odds():
    from probalis.site import build
    markets = [
        {"key": "1x2", "line": None, "sel": {"1": {"p": 0.62}, "X": {"p": 0.22}, "2": {"p": 0.16}}},
        {"key": "dc", "line": None, "sel": {"1X": {"p": 0.84}, "X2": {"p": 0.38}, "12": {"p": 0.78}}},
        {"key": "ou", "line": 1.5, "sel": {"over": {"p": 0.80}, "under": {"p": 0.20}}},
        {"key": "ou", "line": 2.5, "sel": {"over": {"p": 0.57}, "under": {"p": 0.43}}},
        {"key": "ou", "line": 3.5, "sel": {"over": {"p": 0.33}, "under": {"p": 0.67}}},
        {"key": "btts", "line": None, "sel": {"yes": {"p": 0.52}, "no": {"p": 0.48}}},
        {"key": "tt1", "line": 0.5, "sel": {"over": {"p": 0.88}, "under": {"p": 0.12}}},
        {"key": "tt2", "line": 0.5, "sel": {"over": {"p": 0.65}, "under": {"p": 0.35}}},
    ]
    m = {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}, "markets": markets, "league": "E0"}
    view = build._verdicts_view(m, "fr")
    shown = [view["top"]] + view["rows"]
    assert 1 <= len(shown) <= 3
    # 1X à 84 % (≈ 1,13), plus de 1,5 buts à 80 % (≈ 1,19), Arsenal marque à 88 % : jamais montrés
    assert not any(r["q"] in ("Arsenal ou nul ?", "Plus de 1,5 buts ?", "Arsenal marque ?") for r in shown)
    assert view["top"]["q"] == "Plus de 3,5 buts ?" and view["top"]["ans"] == "NON"   # 67 % : le plus sûr qui passe
    for r in shown:
        assert float(r["odds"].replace(",", ".")) >= 1.30


def test_history_shows_and_counts_only_the_picks_of_new_analyses():
    from probalis.site import build, history
    v = [{"f": "win", "k": "1x2", "l": None, "s": "1", "y": 1, "p": 0.85},
         {"f": "ou3.5", "k": "ou", "l": 3.5, "s": "over", "y": 0, "p": 0.68},
         {"f": "btts", "k": "btts", "l": None, "s": "yes", "y": 1, "p": 0.63}]
    new = {"v": v, "pk": [1, 2], "b": 1, "r": ["won", "won", "lost"]}
    rows = build._an_rows(new, "fr", "Arsenal", "Chelsea")
    assert [r["q"] for r in rows] == ["Plus de 3,5 buts ?", "Les deux équipes marquent ?"]
    assert rows[0]["best"] and rows[0]["odds"] == "1,40"
    s = history.an_stats({"an": {"m": new}})
    assert (s["n"], s["won"], s["bn"], s["bw"]) == (2, 1, 1, 1)
    old = {"v": v, "b": 0, "r": ["won", "won", "lost"]}           # enregistrée avant le 27/11/2026
    assert len(build._an_rows(old, "fr", "Arsenal", "Chelsea")) == 3
    assert build._an_rows(old, "fr", "Arsenal", "Chelsea")[0]["odds"] is None
    assert history.an_stats({"an": {"m": old}})["n"] == 3
