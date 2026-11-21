"""Forme récente et face-à-face : bons matchs, bon ordre, bon point de vue, aucun match du jour ou futur."""
from datetime import date

from probalis.football import form
from probalis.football.data import MatchRow
from probalis.football.model import Game
from probalis.site import build


def _rows():
    d = date(2026, 11, 1)
    return [
        MatchRow("E0", date(2026, 10, 4), "Arsenal", "Chelsea", 2, 0),
        MatchRow("E0", date(2026, 10, 18), "Newcastle", "Arsenal", 1, 1),
        MatchRow("E0", date(2026, 10, 25), "Everton", "Newcastle", 3, 1),
        MatchRow("E0", d, "Arsenal", "Everton", 0, 1),
        MatchRow("E0", date(2026, 11, 21), "Newcastle", "Arsenal", 2, 2),  # jour du match : jamais compté
        MatchRow("E0", date(2026, 11, 28), "Chelsea", "Arsenal", None, None),  # pas encore joué
        MatchRow("E1", date(2025, 3, 1), "Newcastle", "Arsenal", 0, 3),  # autre division, même pays : même clé
    ]


def _book():
    b = form.Book()
    b.add_rows("england", _rows())
    b.names["england|Newcastle"] = "Newcastle United"
    return b


def test_form_order_and_point_of_view():
    rows = form.form_rows(_book(), "england|Arsenal", date(2026, 11, 21))
    assert [r["d"] for r in rows] == ["2026-11-01", "2026-10-18", "2026-10-04", "2025-03-01"]
    assert [r["r"] for r in rows] == ["L", "D", "W", "W"]  # défaite 0-1, nul 1-1, victoire 2-0, victoire 3-0 à l'extérieur
    assert rows[0]["h"] == 1 and rows[0]["s"] == [0, 1] and rows[0]["o"] == "Everton"
    assert rows[1]["h"] == 0 and rows[1]["o"] == "Newcastle United"  # nom affiché quand on le connaît
    assert rows[3]["c"] == "E1"


def test_form_keeps_five_and_ignores_same_day():
    b = form.Book()
    b.add_rows("spain", [MatchRow("SP1", date(2026, 9, i), "Betis", f"Club {i}", i % 3, 1) for i in range(1, 9)])
    rows = form.form_rows(b, "spain|Betis", date(2026, 9, 8))
    assert len(rows) == form.N_FORM and rows[0]["d"] == "2026-09-07"


def test_h2h_from_today_home_side():
    h = form.h2h_rows(_book(), "england|Newcastle", "england|Arsenal", date(2026, 11, 21))
    assert [r["d"] for r in h] == ["2026-10-18", "2025-03-01"]
    assert h[0] == {"d": "2026-10-18", "s": [1, 1], "x": 1, "w": "draw", "c": "E0"}
    assert h[1]["w"] == "away" and h[1]["x"] == 1  # Arsenal (l'équipe qui se déplace aujourd'hui) avait gagné 0-3


def test_duplicate_sources_kept_once():
    b = _book()
    b.add_games([Game(date(2026, 10, 18), "england|Newcastle", "england|Arsenal", 1, 1, "dom", comp="E0"),
                 Game(date(2026, 10, 21), "germany|Bayern Munich", "england|Arsenal", 2, 2, "cup", comp="UCL")])
    rows = form.form_rows(b, "england|Arsenal", date(2026, 11, 21))
    assert [r["d"] for r in rows].count("2026-10-18") == 1
    assert any(r["c"] == "UCL" and r["r"] == "D" for r in rows)


def test_attach_uses_country_key_for_domestic_and_node_for_cups():
    b = _book()
    b.add_games([Game(date(2026, 10, 21), "germany|Bayern Munich", "england|Arsenal", 2, 2, "cup", comp="UCL")])
    ms = [{"league": "E0", "kickoff": "2026-11-21T17:30:00+00:00",
           "home": {"name": "Newcastle United", "fd": "Newcastle"}, "away": {"name": "Arsenal", "fd": "Arsenal"}},
          {"league": "UCL", "kickoff": "2026-11-25T20:00:00+00:00",
           "home": {"name": "Bayern", "fd": "germany|Bayern Munich"}, "away": {"name": "Arsenal", "fd": "england|Arsenal"}},
          {"league": "WSL", "kickoff": "2026-11-22T12:00:00+00:00",
           "home": {"name": "X", "fd": "t1"}, "away": {"name": "Y", "fd": "t2"}}]
    assert form.attach(ms, b) == 2
    assert ms[0]["h2h"] and ms[1]["form"]["home"][0]["c"] == "UCL"
    assert "form" not in ms[2]  # aucun match connu : pas de carte


def test_view_counts_goals_and_wins():
    m = {"kickoff": "2026-11-21T17:30:00+00:00", "league": "E0",
         "home": {"name": "Newcastle United"}, "away": {"name": "Arsenal"}}
    b = _book()
    m["form"] = {"home": form.form_rows(b, "england|Newcastle", date(2026, 11, 21)),
                 "away": form.form_rows(b, "england|Arsenal", date(2026, 11, 21))}
    m["h2h"] = form.h2h_rows(b, "england|Newcastle", "england|Arsenal", date(2026, 11, 21))
    v = build._form_view(m, "fr")
    home = v["teams"][0]
    assert home["goals"] == "2 buts marqués, 7 encaissés"  # 1-1, 1-3 à Everton, 0-3
    assert [c["r"] for c in home["chips"]] == ["L", "D", "L"]  # du plus ancien au plus récent
    assert v["sum"]["home"] == "0 victoire" and v["sum"]["draw"] == "1 nul" and v["sum"]["away"] == "1 victoire"
    assert v["h2h"][1]["date"] == "1 mars 2025"
    en = build._form_view(m, "en")
    assert en["sum"]["home"] == "0 wins" and en["teams"][1]["chips"][-1]["l"] == "L"
