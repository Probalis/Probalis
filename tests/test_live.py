"""Paris et verdicts déjà joués d'avance pendant un match (score en direct de TheSportsDB)."""
from datetime import datetime, timedelta, timezone

from probalis.football import fixtures
from probalis.site import history, picks

KO = datetime(2026, 11, 24, 17, 45, tzinfo=timezone.utc)  # mardi, 18 h 45 heure du Cameroun


def _pick(key, line, sel):
    return lambda h, a: picks.settle(key, line, sel, h, a)


def test_live_result_only_when_nothing_can_change():
    assert history.live_result(_pick("ou", 1.5, "over"), 2, 0) == "won"      # les buts ne s'effacent pas
    assert history.live_result(_pick("ou", 2.5, "under"), 2, 0) is None      # peut encore gagner ou perdre
    assert history.live_result(_pick("ou", 2.5, "under"), 2, 1) == "lost"
    assert history.live_result(_pick("btts", None, "yes"), 1, 1) == "won"
    assert history.live_result(_pick("btts", None, "no"), 1, 1) == "lost"
    assert history.live_result(_pick("btts", None, "no"), 1, 0) is None
    assert history.live_result(_pick("tt1", 0.5, "over"), 1, 0) == "won"
    assert history.live_result(_pick("1x2", None, "1"), 4, 0) is None        # une remontée reste possible
    assert history.live_result(_pick("dnb", None, "1"), 3, 0) is None
    assert history.live_result(_pick("ou", 2.0, "over"), 2, 0) is None       # 2 buts = remboursé, 3 = gagné
    assert history.live_result(_pick("ou", 2.0, "over"), 3, 0) == "won"


def _ev(status, hs, as_):
    return {"idEvent": "1", "strStatus": status, "intHomeScore": hs, "intAwayScore": as_}


def test_live_and_final_scores_from_thesportsdb():
    assert fixtures.live_score(_ev("2H", "2", "0")) == (2, 0)
    assert fixtures.live_score(_ev("HT", "0", "1")) == (0, 1)
    assert fixtures.live_score(_ev("ET", "2", "2")) is None   # prolongations : les paris portent sur 90 minutes
    assert fixtures.live_score(_ev("Match Finished", "2", "0")) is None
    assert fixtures.live_score(_ev("NS", None, None)) is None
    assert fixtures.final_score(_ev("Match Finished", "2", "1")) == (2, 1)
    assert fixtures.final_score(_ev("FT", "0", "0")) == (0, 0)
    assert fixtures.final_score(_ev("", "2", "1")) is None    # pas marqué « fini » : on attend 2 h 30
    assert fixtures.final_score(_ev("2H", "2", "1")) is None


def _verdict(k, l, s, y, o=0):
    return {"f": "x", "k": k, "l": l, "s": s, "y": y, "p": 0.7, "o": o}


def _hist():
    m1 = {"kickoff": KO.isoformat(), "league": "UCL", "home": {"name": "A"}, "away": {"name": "B"}, "slug": "a-b"}
    m2 = dict(m1, kickoff=(KO + timedelta(hours=2, minutes=15)).isoformat(), slug="c-d")
    leg = {"mid": "1", "key": "ou", "line": 1.5, "sel": "over", "p": 0.7, "fair": 1.4, "id": "p1"}
    return {"days": {"2026-11-24": {
        "frozen": True,
        "matches": {"1": m1, "2": m2},
        "tiers": {"safe": [leg, dict(leg, key="1x2", line=None, sel="1", id="p2")]},
        "coupons": [{"target": 2, "p": 0.5, "fair": 2.0, "book": 1.9, "legs": [
            dict(leg, key="ou", line=0.5, sel="under", id="c1"),  # perdu dès le premier but
            dict(leg, mid="2", key="1x2", line=None, sel="1", id="c2"),  # match de 21 h, pas encore joué
        ]}],
        "an": {"1": {"v": [_verdict("ou", 1.5, "over", 1), _verdict("1x2", None, "1", 1),
                           _verdict("co", 9.5, "over", 1), _verdict("tt1", 0.5, "over", 1, o=1)]}},
    }}}


class _NoFd:
    def find(self, *a):
        return None


def _settle(monkeypatch, hist, now, events):
    monkeypatch.setattr(history, "_scores_from_cache", lambda: dict(events))
    monkeypatch.setattr(history, "_FdRows", _NoFd)
    return history.settle(hist, now, lookups=0)


def test_settle_during_the_match_then_final_score(monkeypatch):
    hist = _hist()
    e = hist["days"]["2026-11-24"]
    now = KO + timedelta(minutes=70)
    _settle(monkeypatch, hist, now, {"1": _ev("2H", "2", "0")})
    assert e["matches"]["1"]["live"] == [2, 0] and "score" not in e["matches"]["1"]
    safe = e["tiers"]["safe"]
    assert safe[0]["res"] == "won"            # plus de 1,5 but : déjà gagné
    assert safe[1]["res"] is None             # victoire de A : peut encore changer
    cp = e["coupons"][0]
    assert cp["res"] == "lost"                # moins de 0,5 but : perdu
    assert history.coupon_shown(cp) is None   # mais le pari du match de 21 h reste caché
    pub = history.public_copy(hist, now)["days"]["2026-11-24"]
    assert pub["coupons"] == [] and [c["id"] for c in pub["tiers"]["safe"]] == ["p1"]
    assert "an" not in pub                    # analyses complètes publiées seulement après le match
    assert e["an"]["1"]["r"] == ["won", None, None, "won"]   # corners : jamais en direct
    assert history.live_scores(hist) == {"1": (2, 0)}
    assert history.live_decided(e["matches"]["1"], e["an"]["1"])

    # Fin du match, marquée « fini » par TheSportsDB : réglé tout de suite, sans attendre 2 h 30
    now = KO + timedelta(hours=1, minutes=55)
    _settle(monkeypatch, hist, now, {"1": _ev("Match Finished", "2", "1")})
    mt = e["matches"]["1"]
    assert mt["score"] == [2, 1] and "live" not in mt
    assert [c["res"] for c in safe] == ["won", "won"]
    assert history.live_scores(hist) == {}


def test_final_score_corrects_a_live_snapshot(monkeypatch):
    """Score en direct relevé avant un but annulé (VAR) : le score final refait le calcul."""
    hist = _hist()
    e = hist["days"]["2026-11-24"]
    _settle(monkeypatch, hist, KO + timedelta(minutes=60), {"1": _ev("2H", "2", "0")})
    assert e["tiers"]["safe"][0]["res"] == "won"
    _settle(monkeypatch, hist, KO + timedelta(hours=3), {"1": _ev("Match Finished", "1", "0")})
    assert e["tiers"]["safe"][0]["res"] == "lost"


def test_not_started_or_unknown_stays_pending(monkeypatch):
    hist = _hist()
    e = hist["days"]["2026-11-24"]
    _settle(monkeypatch, hist, KO - timedelta(minutes=5), {"1": _ev("NS", None, None)})
    assert "live" not in e["matches"]["1"] and e["tiers"]["safe"][0]["res"] is None
    _settle(monkeypatch, hist, KO + timedelta(minutes=30), {})
    assert e["tiers"]["safe"][0]["res"] is None
