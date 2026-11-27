"""Match en direct (ESPN) : rapprochement de nos matchs, corners et cartons comptés comme football-data, règlement
des verdicts dès la fin du match, relais Cloudflare (tests JavaScript)."""
import json
import re
import shutil
import subprocess
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from probalis.football import espn
from probalis.site import history

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
KO = datetime(2026, 11, 22, 14, 0, tzinfo=timezone.utc)


# --- Relais Cloudflare (probalis/site/live.mjs) ---------------------------------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js absent")
def test_relais_du_direct():
    r = subprocess.run(["node", str(ROOT / "probalis" / "site" / "live.test.mjs")], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "tous les tests réussis" in r.stdout


def test_same_leagues_in_python_and_in_the_relay():
    js = (ROOT / "probalis" / "site" / "live.mjs").read_text(encoding="utf-8")
    block = re.search(r"export const SLUGS = \[(.*?)\];", js, re.S).group(1)
    assert sorted(re.findall(r"'([a-z0-9.]+)'", block)) == sorted(espn.SLUGS.values())


# --- Corners et cartons d'un vrai match (Hull City 2-0 Brighton, 22/11/2026) ----------------------------------

def _summary():
    return json.loads((FIX / "espn_summary_hull_brighton.json").read_text(encoding="utf-8"))


def test_box_counts_cards_like_football_data():
    b = espn.box(_summary())
    assert b["st"] == "post" and b["sn"] == "STATUS_FULL_TIME" and b["full"] is True
    assert b["corners"] == [3, 5]
    # Brighton : 3 jaunes (Vuskovic, Costinha, Chema Andrés) puis 2e jaune de Costinha. ESPN : 2 jaunes + 1 rouge ;
    # football-data (AY 4, AR 1) : 5. Hull : 2 jaunes des deux côtés.
    assert b["cards"] == [2, 5]


def test_box_ignores_thin_coverage():
    s = _summary()
    for t in s["boxscore"]["teams"]:
        for st in t["statistics"]:
            if st["name"] == "possessionPct":
                st["displayValue"] = "0"
    assert espn.box(s)["full"] is False


def _write_box(ref, **b):
    espn.DIR.mkdir(parents=True, exist_ok=True)
    (espn.DIR / f"ev_{ref[0]}_{ref[1]}.json").write_text(json.dumps(b), encoding="utf-8")


def test_counts_only_after_a_normal_full_time():
    ref = ["uefa.champions", "1", "20261124"]
    _write_box(ref, st="post", sn="STATUS_FULL_TIME", full=True, corners=[4, 0], cards=[1, 1])
    assert espn.counts(ref) == {"corners": [4, 0], "cards": [1, 1]}
    assert espn.finished_badly(ref) is False
    _write_box(ref, st="post", sn="STATUS_FINAL_AET", full=True, corners=[9, 7], cards=[3, 4])
    assert espn.counts(ref) is None and espn.finished_badly(ref) is True       # prolongation : pas sur 90 min
    _write_box(ref, st="post", sn="STATUS_FULL_TIME", full=False, cards=[2, 1])
    assert espn.counts(ref) is None and espn.finished_badly(ref) is True       # suivi incomplet
    _write_box(ref, st="in", sn="STATUS_SECOND_HALF", full=True, corners=[2, 2], cards=[0, 1])
    assert espn.counts(ref) is None and espn.finished_badly(ref) is False      # pas fini : on attend (panne réseau)


# --- Rapprochement de nos matchs et de ceux d'ESPN ------------------------------------------------------------

def _ev(i, ko, home, away):
    return {"id": str(i), "ko": ko.strftime("%Y-%m-%dT%H:%MZ"), "st": "pre", "sn": "STATUS_SCHEDULED",
            "h": home, "a": away, "sc": [None, None]}


BOARD = {
    ("ger.1", date(2026, 11, 20)): [_ev(11, datetime(2026, 11, 20, 19, 30), ["Bayern Munich"], ["FC Cologne"])],
    ("eng.1", date(2026, 11, 22)): [
        _ev(21, KO, ["Hull City", "Hull"], ["Brighton & Hove Albion", "Brighton"]),
        _ev(22, KO + timedelta(hours=2, minutes=30), ["Liverpool"], ["Manchester United", "Man United"]),
        _ev(23, KO + timedelta(hours=2, minutes=30), ["Manchester City", "Man City"], ["Chelsea"]),
    ],
}


def _link(monkeypatch, items):
    monkeypatch.setattr(espn, "scoreboard", lambda slug, day, now=None: BOARD.get((slug, day), []))
    return espn.link(items, KO)


def test_link_by_kickoff_and_names(monkeypatch):
    items = [
        {"key": "a", "league": "E0", "kickoff": KO.isoformat(), "home": "Hull City", "away": "Brighton and Hove Albion"},
        {"key": "b", "league": "E0", "kickoff": (KO + timedelta(hours=2, minutes=30)).isoformat(),
         "home": "Liverpool", "away": "Manchester United"},
        {"key": "c", "league": "E0", "kickoff": (KO + timedelta(hours=2, minutes=30)).isoformat(),
         "home": "Manchester City", "away": "Chelsea"},
        # « Köln » / « FC Cologne » : un des deux noms suffit à la même heure
        {"key": "d", "league": "D1", "kickoff": "2026-11-20T19:30:00+00:00", "home": "Bayern Munich", "away": "Köln"},
        # Pas chez ESPN (Frauen-Bundesliga), ou heure trop éloignée : pas de lien
        {"key": "e", "league": "FBL", "kickoff": KO.isoformat(), "home": "Wolfsburg", "away": "Bayern"},
        {"key": "f", "league": "E0", "kickoff": (KO + timedelta(days=1)).isoformat(), "home": "Hull City",
         "away": "Brighton and Hove Albion"},
    ]
    refs = _link(monkeypatch, items)
    assert refs == {"a": ["eng.1", "21", "20261122"], "b": ["eng.1", "22", "20261122"],
                    "c": ["eng.1", "23", "20261122"], "d": ["ger.1", "11", "20261120"]}


def test_link_refuses_a_different_match_at_the_same_time(monkeypatch):
    items = [{"key": "x", "league": "E0", "kickoff": (KO + timedelta(hours=2, minutes=30)).isoformat(),
              "home": "Arsenal", "away": "Tottenham Hotspur"}]
    assert _link(monkeypatch, items) == {}


def test_scoreboard_keeps_the_old_copy_when_espn_is_down():
    day = date(2026, 11, 22)
    espn.DIR.mkdir(parents=True, exist_ok=True)
    (espn.DIR / "sb_eng.1_20261122.json").write_text(json.dumps([_ev(21, KO, ["Hull City"], ["Brighton"])]),
                                                     encoding="utf-8")
    now = datetime(2026, 11, 22, 18, 0, tzinfo=timezone.utc)
    old = (espn.DIR / "sb_eng.1_20261122.json").stat().st_mtime - 3600
    import os
    os.utime(espn.DIR / "sb_eng.1_20261122.json", (old, old))   # trop vieux : redemandé, ESPN muet (tests)
    assert [e["id"] for e in espn.scoreboard("eng.1", day, now)] == ["21"]


# --- Règlement des verdicts de corners et cartons ---------------------------------------------------------------

def _hist(league="UCL", espn_ref=None, nost=False):
    mt = {"kickoff": KO.isoformat(), "league": league, "slug": "2026-11-22-hull-city-brighton",
          "home": {"name": "Hull City"}, "away": {"name": "Brighton and Hove Albion"}, "score": [2, 0]}
    if espn_ref:
        mt["espn"] = espn_ref
    if nost:
        mt["nost"] = True
    v = [{"f": "co", "k": "co", "l": 8.5, "s": "over", "y": 0, "p": 0.6},       # 3 + 5 = 8 : NON plus de 8,5 juste
         {"f": "ca", "k": "ca", "l": 3.5, "s": "over", "y": 1, "p": 0.6},        # 2 + 5 = 7 : OUI plus de 3,5 juste
         {"f": "btts", "k": "btts", "l": None, "s": "yes", "y": 1, "p": 0.55}]
    return {"days": {"2026-11-22": {"frozen": True, "matches": {"1": mt}, "an": {"1": {"v": v, "b": 0}}}}}


def _settle(monkeypatch, hist, now):
    monkeypatch.setattr(history, "_scores_from_cache", lambda: {})
    history.settle(hist, now, lookups=0)
    return hist["days"]["2026-11-22"]


REF = ["uefa.champions", "401915380", "20261122"]


def test_cup_match_settled_with_espn_two_hours_after(monkeypatch):
    _write_box(REF, st="post", sn="STATUS_FULL_TIME", full=True, corners=[3, 5], cards=[2, 5])
    hist = _hist(espn_ref=REF)
    e = _settle(monkeypatch, hist, KO + timedelta(hours=2, minutes=40))
    assert e["matches"]["1"]["st"] == {"corners": [3, 5], "cards": [2, 5]}
    assert e["an"]["1"]["r"] == ["won", "won", "lost"]


def test_cup_match_after_extra_time_not_verifiable(monkeypatch):
    _write_box(REF, st="post", sn="STATUS_FINAL_AET", full=True, corners=[9, 7], cards=[3, 4])
    e = _settle(monkeypatch, _hist(espn_ref=REF), KO + timedelta(hours=3))
    assert e["matches"]["1"]["nost"] is True and e["an"]["1"]["r"][:2] == ["nv", "nv"]


def test_domestic_league_prefers_espn_then_falls_back_to_football_data(monkeypatch):
    ref = ["eng.1", "21", "20261122"]
    _write_box(ref, st="post", sn="STATUS_FULL_TIME", full=True, corners=[3, 5], cards=[2, 5])
    called = []
    monkeypatch.setattr(history, "_fd_row", lambda fd, mt: called.append(1))
    e = _settle(monkeypatch, _hist("E0", espn_ref=ref), KO + timedelta(hours=3))
    assert e["matches"]["1"]["st"] == {"corners": [3, 5], "cards": [2, 5]} and not called
    # Petit championnat suivi en partie par ESPN (National League) : on attend football-data, pas « non vérifiable »
    ref2 = ["eng.5", "31", "20261122"]
    _write_box(ref2, st="post", sn="STATUS_FULL_TIME", full=False, cards=[0, 3])
    e = _settle(monkeypatch, _hist("EC", espn_ref=ref2), KO + timedelta(days=2))
    assert "st" not in e["matches"]["1"] and "nost" not in e["matches"]["1"]


def test_link_espn_reopens_old_cup_matches(monkeypatch):
    hist = _hist(nost=True)          # marqué « non vérifiable » tout de suite par la règle d'avant le 26/11/2026
    monkeypatch.setattr(espn, "link", lambda items, now: {it["key"]: REF for it in items})
    assert history.link_espn(hist, KO + timedelta(days=1)) == 1
    mt = hist["days"]["2026-11-22"]["matches"]["1"]
    assert mt["espn"] == REF and "nost" not in mt
    assert history.espn_refs(hist) == {"1": REF}
    # Déjà relié : pas redemandé
    assert history.link_espn(hist, KO + timedelta(days=1)) == 0
    # Trop vieux (plus de 6 jours) : laissé tel quel
    hist = _hist(nost=True)
    assert history.link_espn(hist, KO + timedelta(days=8)) == 0
    assert hist["days"]["2026-11-22"]["matches"]["1"]["nost"] is True
