"""Nouveau moteur (engine.py), corners et cartons, verdicts OUI / NON et historique des analyses."""
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pytest

from probalis.core import verdicts as vd
from probalis.core.counts import card_markets, corner_markets, count_pmf, settle_count
from probalis.football.data import MatchRow
from probalis.football.engine import EngineParams, analyse, fit_league
from probalis.football.model import fit
from probalis.football.predict import predict
from probalis.site import history

REF = date(2026, 3, 1)


def _history(n_teams=8, seasons=2, seed=5, stats=True):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    rows = []
    for k in range(seasons):
        for i, h in enumerate(teams):
            for j, a in enumerate(teams):
                if h == a:
                    continue
                d = REF - timedelta(days=5 + 150 * k + (i * n_teams + j) % 120)
                st = {}
                if stats:
                    st = {"HS": float(rng.poisson(13)), "AS": float(rng.poisson(10)), "HST": float(rng.poisson(5)),
                          "AST": float(rng.poisson(4)), "HC": float(rng.poisson(5.5)), "AC": float(rng.poisson(4.5)),
                          "HY": float(rng.poisson(1.8)), "AY": float(rng.poisson(2.1)), "HR": 0.0, "AR": 0.0}
                rows.append(MatchRow("E0", d, h, a, int(rng.poisson(1.5)), int(rng.poisson(1.1)), stats=st))
    rows.sort(key=lambda m: m.date)
    return rows


def _p(pred, key, sel, line=None):
    return next(m for m in pred.markets if m.key == key and m.line == line).selections[sel].prob


def test_empty_settings_give_the_old_engine():
    """Réglages vides : exactement l'ancien modèle (buts seuls, pas de corners ni de cartons)."""
    hist = _history()
    p = EngineParams()
    lm = fit_league(hist, REF, p)
    an = analyse(lm, "T0", "T1", params=p)
    old = predict(fit(hist, REF), "T0", "T1")
    assert an.pred.lam == pytest.approx(old.lam, rel=1e-9)
    assert an.pred.mu == pytest.approx(old.mu, rel=1e-9)
    assert _p(an.pred, "1x2", "1") == pytest.approx(_p(old, "1x2", "1"), abs=1e-9)
    assert not an.counts and not any(m.key in ("co", "ca") for m in an.pred.markets)


def test_goal_lines_are_coherent():
    hist = _history()
    p = EngineParams(w_xg=0.2, w_form=0.4, form_target="xg", t=1.3, s=0.99)
    an = analyse(fit_league(hist, REF, p), "T2", "T5", params=p)
    o15, o25, o35 = (_p(an.pred, "ou", "over", ln) for ln in (1.5, 2.5, 3.5))
    assert 1 > o15 >= o25 >= o35 > 0
    x = sum(_p(an.pred, "1x2", s) for s in ("1", "X", "2"))
    assert x == pytest.approx(1, abs=1e-6)


def test_market_mix_with_odds():
    hist = _history()
    p = EngineParams(w_mkt=1.0, devig="power")
    an = analyse(fit_league(hist, REF, p), "T0", "T1", [1.6, 4.0, 5.5], [1.8, 2.05], params=p)
    assert an.source == "market" and an.confidence == "high"
    assert _p(an.pred, "1x2", "1") > 0.5


def test_corners_and_cards_markets():
    hist = _history()
    p = EngineParams(corners_size=11.0, cards_size=None, corners_shrink=0.75, cards_shrink=0.65)
    an = analyse(fit_league(hist, REF, p), "T0", "T1", params=p)
    assert "corners" in an.counts and "cards" not in an.counts
    co = {m.line: m for m in an.pred.markets if m.key == "co"}
    assert co[8.5].selections["over"].prob >= co[9.5].selections["over"].prob >= co[10.5].selections["over"].prob
    total = sum(an.counts["corners"])
    assert 7 < total < 13


def test_count_pmf_sums_to_one():
    for size in (None, 5.0, 11.4, 5000.0):
        assert count_pmf(10.0, size, 40).sum() == pytest.approx(1, abs=1e-4)
    assert card_markets(2.0, 2.2, None) and corner_markets(5.4, 4.6, 11.4)


def test_count_settlement():
    assert settle_count("co", 9.5, "over", 6, 4) == "won"
    assert settle_count("co", 9.5, "under", 6, 4) == "lost"
    assert settle_count("ca1x2", None, "X", 2, 2) == "won"
    assert settle_count("cot2", 4.5, "over", 6, 4) == "lost"


def _markets(p1=0.55, px=0.25, p_over25=0.6, btts=0.52):
    p2 = 1 - p1 - px
    return [
        {"key": "1x2", "line": None, "sel": {"1": {"p": p1}, "X": {"p": px}, "2": {"p": p2}}},
        {"key": "dc", "line": None, "sel": {"1X": {"p": p1 + px}, "X2": {"p": px + p2}, "12": {"p": p1 + p2}}},
        {"key": "ou", "line": 1.5, "sel": {"over": {"p": 0.8}, "under": {"p": 0.2}}},
        {"key": "ou", "line": 2.5, "sel": {"over": {"p": p_over25}, "under": {"p": 1 - p_over25}}},
        {"key": "ou", "line": 3.5, "sel": {"over": {"p": 0.32}, "under": {"p": 0.68}}},
        {"key": "btts", "line": None, "sel": {"yes": {"p": btts}, "no": {"p": 1 - btts}}},
        {"key": "tt1", "line": 0.5, "sel": {"over": {"p": 0.82}, "under": {"p": 0.18}}},
        {"key": "tt2", "line": 0.5, "sel": {"over": {"p": 0.6}, "under": {"p": 0.4}}},
        {"key": "co", "line": 9.5, "sel": {"over": {"p": 0.45}, "under": {"p": 0.55}}},
        {"key": "ca", "line": 4.5, "sel": {"over": {"p": 0.3}, "under": {"p": 0.7}}},
    ]


def test_verdicts_and_best():
    vs = vd.verdicts(_markets())
    fams = [v["fam"] for v in vs]
    assert fams == ["win", "dc", "ou1.5", "ou2.5", "ou3.5", "btts", "tt", "tt", "co", "ca"]
    btts = vs[5]
    assert btts["yes"] and btts["open"]                      # 52 % : trop serré
    ca = vs[-1]
    assert not ca["yes"] and ca["p"] == pytest.approx(0.7)   # NON à 70 %
    best = vd.best(vs, {})
    assert best["key"] == "tt1" and best["yes"]              # Arsenal marque : 82 %, le plus haut
    assert vd.settle(vs[3], 2, 1) == "won"                   # plus de 2,5 buts : 3 buts
    assert vd.settle(vs[-1], 1, 0, {"cards": (2, 1)}) == "won"   # NON plus de 4,5 cartons : 3 cartons
    assert vd.settle(vs[-2], 1, 0) is None                   # corners inconnus


def test_reliability_record_needs_enough_cases():
    v = {"fam": "ou1.5", "p": 0.76}
    assert vd.record({"ou1.5": {"15": [12, 9, 9.1]}}, v) is None
    assert vd.record({"ou1.5": {"15": [400, 310, 304.0]}}, v) == (400, 310)


def _match(mid, ko, markets):
    return {"id": mid, "slug": f"x-{mid}", "league": "E0", "kickoff": ko.isoformat(), "confidence": "high",
            "home": {"name": "Arsenal", "fd": "Arsenal", "badge": None},
            "away": {"name": "Chelsea", "fd": "Chelsea", "badge": None},
            "markets": markets, "top_score": [["1-0", 0.12]], "engine": "v2", "counts": {}}


def test_history_records_and_settles_analyses():
    now = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)
    ko = now + timedelta(hours=6)
    m = _match("e1", ko, _markets())
    hist = {"version": 1, "days": {}}
    history.update(hist, [m], now, rel={})
    day = hist["days"]["2026-11-21"]
    rec = day["an"]["e1"]
    assert len(rec["v"]) == 10 and rec["b"] is not None and rec["eng"] == "v2"
    assert 1 <= len(rec["pk"]) <= 3 and rec["b"] == rec["pk"][0]   # paris du match (27/11/2026)
    # Avant la fin du match : rien de public
    pub = history.public_copy(hist, now)
    assert "an" not in pub["days"]["2026-11-21"]
    # Match joué 2-1, corners et cartons inconnus (pas de fichier football-data ici)
    day["matches"]["e1"]["score"] = [2, 1]
    history._apply_results(day)
    res = dict(zip((d["f"] for d in rec["v"]), rec["r"]))
    assert res["ou2.5"] == "won" and res["win"] == "won" and res["co"] is None
    day["matches"]["e1"]["nost"] = True
    history._apply_results(day)
    assert rec["r"][-1] == history.NV
    s = history.an_stats(day)
    settled = [i for i in rec["pk"] if rec["r"][i] in ("won", "lost") and not rec["v"][i].get("o")]
    assert s["n"] == len(settled) and s["won"] <= s["n"]   # seuls les paris du match comptent
    # Analyse enregistrée avant le 27/11/2026 (sans « pk ») : tous ses verdicts comptent, comme avant
    old = {k: v for k, v in rec.items() if k != "pk"}
    s_old = history.an_stats({"an": {"e1": old}})
    assert s_old["n"] >= 6
    later = ko + timedelta(hours=3)
    pub = history.public_copy(hist, later)
    assert "e1" in pub["days"]["2026-11-21"]["an"]


def test_frozen_day_never_rewrites_a_recorded_analysis():
    now = datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc)
    m = _match("e1", now + timedelta(hours=6), _markets(p_over25=0.6))
    hist = {"version": 1, "days": {}}
    history.update(hist, [m], now, rel={})
    first = hist["days"]["2026-11-21"]["an"]["e1"]["v"][3]["p"]
    m2 = _match("e1", now + timedelta(hours=6), _markets(p_over25=0.3))
    m3 = _match("e2", now + timedelta(hours=8), _markets())
    history.update(hist, [m2, m3], now + timedelta(hours=1), rel={})
    an = hist["days"]["2026-11-21"]["an"]
    assert an["e1"]["v"][3]["p"] == first          # déjà enregistré : inchangé
    assert "e2" in an                               # match pas encore commencé : ajouté
