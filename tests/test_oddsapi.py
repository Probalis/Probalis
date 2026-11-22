"""Cotes de The Odds API : moyenne des bookmakers, liaison avec les matchs TheSportsDB, quota gardé, calage."""
import random
import urllib.error
from datetime import date, datetime, timedelta, timezone

from probalis.football import oddsapi, pipeline
from probalis.football.fixtures import Fixture
from probalis.football.leagues import BY_CODE
from probalis.football.linked import Linked
from probalis.football.model import Game, fit_linked

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)


def _book(key, h, d, a, over=None, under=None, point=2.5):
    mk = [{"key": "h2h", "outcomes": [{"name": "Paris Saint Germain", "price": h}, {"name": "Draw", "price": d},
                                      {"name": "Bayern Munich", "price": a}]}]
    if over:
        mk.append({"key": "totals", "outcomes": [{"name": "Over", "price": over, "point": point},
                                                 {"name": "Under", "price": under, "point": point}]})
    return {"key": key, "markets": mk}


def _event(books, ko=NOW + timedelta(hours=8)):
    return {"id": "x1", "sport_key": "soccer_uefa_champs_league", "commence_time": ko.isoformat().replace("+00:00", "Z"),
            "home_team": "Paris Saint Germain", "away_team": "Bayern Munich", "bookmakers": books}


def _fixture(ko=NOW + timedelta(hours=8), home="Paris SG", away="Bayern München", eid="2001"):
    return Fixture("UCL", eid, ko, home, away, None, None, "5", None, home_id="1", away_id="2")


def test_consensus_average_and_best():
    e = _event([_book("onexbet", 2.10, 3.60, 3.30, 1.70, 2.20), _book("pinnacle", 2.20, 3.50, 3.20, 1.75, 2.15),
                _book("unibet", 2.00, 3.40, 3.40)])
    mk = oddsapi.consensus(e)
    x = mk[("1x2", None)]
    assert x["1"] == {"best": 2.2, "avg": 2.1} and x["2"]["best"] == 3.4
    ou = mk[("ou", 2.5)]
    assert ou["over"]["avg"] == 1.725 and ou["under"]["best"] == 2.2
    one = oddsapi.consensus(_event([_book("onexbet", 2.1, 3.6, 3.3, 1.7, 2.2)]))
    assert one == {}                               # un seul bookmaker : pas de moyenne fiable
    other_line = oddsapi.consensus(_event([_book("a", 2, 3.5, 3.5, 1.4, 2.8, 1.5), _book("b", 2, 3.5, 3.5, 1.4, 2.8, 1.5)]))
    assert ("ou", 2.5) not in other_line and ("1x2", None) in other_line


def test_match_odds_links_names_and_time():
    e = _event([_book("a", 2.1, 3.6, 3.3), _book("b", 2.2, 3.5, 3.2)])
    got = oddsapi.match_odds([_fixture()], [e])
    assert list(got) == ["2001"] and got["2001"][("1x2", None)]["1"]["avg"] == 2.15
    swapped = oddsapi.match_odds([_fixture(home="Bayern München", away="Paris SG")], [e])
    assert swapped["2001"][("1x2", None)]["1"]["avg"] == 3.25   # domicile et extérieur échangés
    assert oddsapi.match_odds([_fixture(ko=NOW + timedelta(days=2))], [e]) == {}   # pas le même jour


def test_refresh_rules():
    ko = NOW + timedelta(hours=10)
    assert oddsapi.needs_refresh(ko, None, NOW)
    assert not oddsapi.needs_refresh(ko, NOW - timedelta(hours=11), NOW)
    assert oddsapi.needs_refresh(ko, NOW - timedelta(hours=12), NOW)
    far = NOW + timedelta(hours=50)
    assert not oddsapi.needs_refresh(far, NOW - timedelta(hours=20), NOW)
    assert oddsapi.needs_refresh(far, NOW - timedelta(hours=24), NOW)
    assert not oddsapi.needs_refresh(NOW + timedelta(days=4), None, NOW)   # trop loin : rien n'est dépensé
    assert not oddsapi.needs_refresh(None, None, NOW)


def _setup(monkeypatch, tmp_path, key="test-key"):
    monkeypatch.setattr(oddsapi, "DIR", tmp_path)
    monkeypatch.setattr(oddsapi, "STATE", tmp_path / "quota.json")
    if key:
        monkeypatch.setenv(oddsapi.KEY_ENV, key)
    else:
        monkeypatch.delenv(oddsapi.KEY_ENV, raising=False)
    calls = []

    def getter(sport, k, now):
        calls.append((sport, now))
        return [_event([_book("a", 2.1, 3.6, 3.3), _book("b", 2.2, 3.5, 3.2)])], \
            {"x-requests-last": "2", "x-requests-remaining": "300"}
    return calls, getter


def test_fetch_without_key_asks_nothing(monkeypatch, tmp_path):
    calls, getter = _setup(monkeypatch, tmp_path, key=None)
    assert oddsapi.fetch("UCL", NOW + timedelta(hours=8), NOW, False, getter) == []
    assert calls == []


def test_fetch_uses_cache_and_budget(monkeypatch, tmp_path):
    calls, getter = _setup(monkeypatch, tmp_path)
    ko = NOW + timedelta(hours=8)
    assert len(oddsapi.fetch("UCL", ko, NOW, False, getter)) == 1 and len(calls) == 1
    assert len(oddsapi.fetch("UCL", ko, NOW + timedelta(hours=3), False, getter)) == 1 and len(calls) == 1
    state = oddsapi._state(NOW)
    assert state["used"]["UCL"] == 2 and state["remaining"] == 300
    # Budget du mois atteint : plus d'appel, les cotes gardées servent encore
    state["used"]["UCL"] = oddsapi.BUDGET["UCL"]
    oddsapi._save_state(state)
    assert len(oddsapi.fetch("UCL", ko, NOW + timedelta(hours=13), False, getter)) == 1 and len(calls) == 1
    # Cotes trop vieilles (plus de 30 h) : plus utilisées
    assert oddsapi.fetch("UCL", ko, NOW + timedelta(hours=31), False, getter) == []
    # Nouveau mois : le budget repart
    later = datetime(2026, 12, 1, 9, 0, tzinfo=timezone.utc)
    assert oddsapi.fetch("UCL", later + timedelta(hours=8), later, False, getter) and len(calls) == 2


def test_fetch_stops_under_reserve_and_on_refusal(monkeypatch, tmp_path):
    calls, getter = _setup(monkeypatch, tmp_path)
    oddsapi._save_state({"month": NOW.strftime("%Y-%m"), "used": {}, "remaining": oddsapi.RESERVE + 1})
    assert oddsapi.fetch("UEL", NOW + timedelta(hours=8), NOW, False, getter) == [] and calls == []

    def refused(sport, k, now):
        raise urllib.error.HTTPError("https://example.invalid", 401, "Unauthorized", {}, None)
    oddsapi._save_state({"month": NOW.strftime("%Y-%m"), "used": {}, "remaining": None})
    assert oddsapi.fetch("UEL", NOW + timedelta(hours=8), NOW, False, refused) == []
    assert oddsapi._state(NOW)["remaining"] == 0     # clé refusée : plus d'appel ce mois-ci


def _linked():
    rnd = random.Random(3)
    teams = ["c|A", "c|B", "d|C", "d|D", "e|E", "e|F"]
    games = [Game(date(2026, 1, 1) + timedelta(days=4 * i), *rnd.sample(teams, 2), rnd.randint(0, 3), rnd.randint(0, 2),
                  "cup") for i in range(80)]
    model = fit_linked(games, {t: t[0] for t in teams}, date(2026, 11, 23))
    return Linked(model, {"1": "c|A", "2": "d|C"}, {"c|A": "Paris SG", "d|C": "Bayern München"}, {}, games)


def test_cup_match_is_calibrated_on_odds(monkeypatch):
    fx = _fixture()
    monkeypatch.setattr(pipeline, "_upcoming", lambda lg, today, events=None: [fx])
    odds = {("1x2", None): {"1": {"best": 2.2, "avg": 2.1}, "X": {"best": 3.6, "avg": 3.5},
                            "2": {"best": 3.4, "avg": 3.3}},
            ("ou", 2.5): {"over": {"best": 1.75, "avg": 1.72}, "under": {"best": 2.2, "avg": 2.15}}}
    linked = _linked()
    report = {"unmatched": [], "leagues": {}}
    monkeypatch.setattr(pipeline.oddsapi, "odds_for", lambda code, fixtures, *a, **k: {})
    plain, _ = pipeline._linked_matches(BY_CODE["UCL"], linked, date(2026, 11, 24), report)
    monkeypatch.setattr(pipeline.oddsapi, "odds_for", lambda code, fixtures, *a, **k: {"2001": odds})
    calib, _ = pipeline._linked_matches(BY_CODE["UCL"], linked, date(2026, 11, 24), report)
    assert plain[0]["source"] == "model" and plain[0]["confidence"] != "high"
    m = calib[0]
    assert m["source"] == "market" and m["confidence"] == "high"
    assert m["odds_src"] == "oddsapi" and "odds_src" not in plain[0]   # la page du match cite The Odds API
    assert report["leagues"]["UCL"]["odds"] == 1
    p1 = next(mk for mk in m["markets"] if mk["key"] == "1x2")["sel"]["1"]["p"]
    assert 0.43 < p1 < 0.49                     # cote moyenne 2,10 sans la marge : environ 46 %
    assert m["priced"] and m["model_1x2"] == plain[0]["model_1x2"]
