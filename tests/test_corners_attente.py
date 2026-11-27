"""Corners et cartons des matchs de championnat : retrouvés dans football-data même pour un match enregistré sans ses
noms football-data (listes faites avant le 21/11/2026), au lieu d'être marqués « non vérifiables » tout de suite."""
from datetime import date, datetime, timedelta, timezone

from probalis.football.data import MatchRow
from probalis.site import build, history

KO = datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)


def _row(home, away, hg, ag, hc, ac, hy, ay, day=date(2026, 11, 21)):
    return MatchRow("E0", day, home, away, hg, ag, stats={"HC": hc, "AC": ac, "HY": hy, "AY": ay})


ROWS = [_row("Chelsea", "Leeds", 1, 4, 7, 3, 2, 1), _row("Coventry", "Crystal Palace", 3, 2, 5, 6, 1, 3),
        _row("Man City", "Fulham", 2, 0, 9, 2, 0, 2), _row("Newcastle", "Arsenal", 1, 1, 4, 4, 3, 3),
        _row("Chelsea", "Arsenal", 0, 0, 1, 1, 0, 0, day=date(2026, 10, 3))]


class _Rows(history._FdRows):
    def __init__(self, rows=ROWS):
        super().__init__()
        self.data = {(r.date.isoformat(), r.home, r.away): r for r in rows}

    def _rows(self, code, ko):
        return self.data if code == "E0" else {}


def test_find_named_links_thesportsdb_names_to_the_right_match():
    fd = _Rows()
    r = fd.find_named("E0", KO.isoformat(), "Chelsea", "Leeds United")
    assert (r.home, r.away, r.fthg, r.ftag) == ("Chelsea", "Leeds", 1, 4)
    r = fd.find_named("E0", KO.isoformat(), "Manchester City", "Fulham")
    assert (r.home, r.away) == ("Man City", "Fulham")
    r = fd.find_named("E0", KO.isoformat(), "Coventry City", "Crystal Palace")
    assert (r.home, r.away) == ("Coventry", "Crystal Palace")
    # Pas encore publié, ou les deux équipes ne tombent pas sur le même match : rien plutôt qu'un mauvais match
    assert fd.find_named("E0", (KO + timedelta(days=7)).isoformat(), "Chelsea", "Leeds United") is None
    assert fd.find_named("E0", KO.isoformat(), "Chelsea", "Fulham") is None
    assert fd.find_named("SP1", KO.isoformat(), "Chelsea", "Leeds United") is None


def _hist(fd_names=None, nost=False, score=(1, 4)):
    mt = {"kickoff": KO.isoformat(), "league": "E0", "slug": "2026-11-21-chelsea-leeds-united",
          "home": {"name": "Chelsea"}, "away": {"name": "Leeds United"}, "score": list(score)}
    if fd_names:
        mt["fd"] = fd_names
    if nost:
        mt["nost"] = True
    v = [{"f": "co", "k": "co", "l": 8.5, "s": "over", "y": 1, "p": 0.66},
         {"f": "ca", "k": "ca", "l": 3.5, "s": "over", "y": 0, "p": 0.6},
         {"f": "btts", "k": "btts", "l": None, "s": "yes", "y": 1, "p": 0.55}]
    return {"days": {"2026-11-21": {"frozen": True, "matches": {"1": mt}, "an": {"1": {"v": v, "b": 0}}}}}


def _settle(monkeypatch, hist, now, rows):
    monkeypatch.setattr(history, "_scores_from_cache", lambda: {})
    monkeypatch.setattr(history, "_FdRows", lambda: _Rows(rows))
    history.settle(hist, now, lookups=0)
    return hist["days"]["2026-11-21"]


def test_match_without_fd_names_waits_for_figures_then_is_settled(monkeypatch):
    # Marqué « non vérifiable » par l'ancienne règle, chiffres pas encore publiés : remis en attente
    hist = _hist(nost=True)
    e = _settle(monkeypatch, hist, KO + timedelta(days=1), rows=[])
    mt = e["matches"]["1"]
    assert "nost" not in mt and "st" not in mt
    assert e["an"]["1"]["r"] == [None, None, "won"]      # corners, cartons : en attente ; BTTS : réglé
    # Chiffres publiés le lendemain : corners 7 + 3 = 10 (> 8,5 : OUI juste), cartons 2 + 1 = 3 (≤ 3,5 : NON juste)
    e = _settle(monkeypatch, hist, KO + timedelta(days=2), rows=ROWS)
    assert e["matches"]["1"]["st"] == {"corners": [7, 3], "cards": [2, 1]}
    assert e["an"]["1"]["r"] == ["won", "won", "won"]


def test_match_with_fd_names_unchanged_and_give_up_after_six_days(monkeypatch):
    hist = _hist(fd_names=["Chelsea", "Leeds"])
    e = _settle(monkeypatch, hist, KO + timedelta(days=2), rows=ROWS)
    assert e["matches"]["1"]["st"] == {"corners": [7, 3], "cards": [2, 1]}
    # Jamais publié : non vérifiable au bout de 6 jours, et plus remis en attente ensuite
    hist = _hist()
    e = _settle(monkeypatch, hist, KO + timedelta(days=7), rows=[])
    assert e["matches"]["1"]["nost"] is True and e["an"]["1"]["r"] == ["nv", "nv", "won"]
    e = _settle(monkeypatch, hist, KO + timedelta(days=8), rows=[])
    assert e["matches"]["1"]["nost"] is True


def test_cup_match_waits_a_day_for_espn_then_not_verifiable(monkeypatch):
    # Depuis le 26/11/2026, ESPN donne les corners et cartons des coupes d'Europe : on attend ses chiffres
    hist = _hist()
    hist["days"]["2026-11-21"]["matches"]["1"]["league"] = "UCL"
    e = _settle(monkeypatch, hist, KO + timedelta(hours=3), rows=ROWS)
    assert "nost" not in e["matches"]["1"] and e["an"]["1"]["r"][:2] == [None, None]
    e = _settle(monkeypatch, hist, KO + timedelta(hours=25), rows=ROWS)
    assert e["matches"]["1"]["nost"] is True and e["an"]["1"]["r"][:2] == ["nv", "nv"]


def test_women_league_without_espn_still_not_verifiable_at_once(monkeypatch):
    hist = _hist()
    hist["days"]["2026-11-21"]["matches"]["1"]["league"] = "FBL"   # Frauen-Bundesliga : ni ESPN ni football-data
    e = _settle(monkeypatch, hist, KO + timedelta(hours=3), rows=ROWS)
    assert e["matches"]["1"]["nost"] is True and e["an"]["1"]["r"][:2] == ["nv", "nv"]


def test_past_match_page_explains_pending_corners():
    hist = _hist()
    e = hist["days"]["2026-11-21"]
    history._apply_results(e)
    v = build._an_match(e, "1", e["an"]["1"], "fr", set())
    assert v["status"] == "done" and v["wait_st"] is True
    assert [r["k"] for r in v["rows"]] == ["co", "ca", "btts"]
    e["matches"]["1"]["st"] = {"corners": [7, 3], "cards": [2, 1]}
    history._apply_results(e)
    assert build._an_match(e, "1", e["an"]["1"], "fr", set())["wait_st"] is False
