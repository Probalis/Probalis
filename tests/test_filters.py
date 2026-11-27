"""Filtres par type de pari (onglet Paris) et réussite par période (Historique) : mise à niveau 3."""
import copy
from datetime import datetime, timezone

from probalis.site import build, history, picks


def _match(mid, p_home, ko="2026-11-27T19:00:00+00:00", p_over15=0.75, p_btts=0.5):
    def sel(**ps):
        return {k: {"p": v, "fair": round(1 / v, 3)} for k, v in ps.items()}
    p_away = round((1 - p_home) * 0.55, 4)
    p_draw = round(1 - p_home - p_away, 4)
    return {"id": mid, "slug": f"s-{mid}", "league": "E0", "kickoff": ko, "confidence": "high",
            "home": {"name": f"H{mid}"}, "away": {"name": f"A{mid}"},
            "markets": [
                {"key": "1x2", "sel": sel(**{"1": p_home, "X": p_draw, "2": p_away})},
                {"key": "dc", "sel": sel(**{"1X": p_home + p_draw, "X2": p_draw + p_away, "12": p_home + p_away})},
                {"key": "ou", "line": 1.5, "sel": sel(over=p_over15, under=1 - p_over15)},
                {"key": "btts", "sel": sel(yes=p_btts, no=1 - p_btts)},
            ]}


MS = [_match(f"m{i}", 0.30 + 0.04 * i, p_over15=0.66 + 0.015 * i) for i in range(10)]


def test_filter_keeps_one_type_without_the_two_per_type_limit():
    goals = picks.tier_picks(MS, "safe", fams=picks.FILTERS["goals"])
    assert goals and all(picks.FAMILY[c["key"]] == "goals" for c in goals)
    assert len(goals) > 2  # la limite de deux du même type ne compte pas dans une liste par type
    assert len({c["mid"] for c in goals}) == len(goals)  # toujours un seul pari par match
    res = picks.tier_picks(MS, "safe", fams=picks.FILTERS["result"])
    assert {picks.FAMILY[c["key"]] for c in res} <= {"result", "dc"}
    # Pas de corners ni de cartons dans les filtres
    assert not {"corners", "cards"} & {f for fs in picks.FILTERS.values() for f in fs}


def test_day_lists_record_filter_lists_and_their_matches():
    lists = history.day_lists(MS, after=None)
    assert set(lists["fam"]) == set(picks.FILTERS)
    assert all(set(by) == set(picks.TIERS) for by in lists["fam"].values())
    for c in history._fam_picks(lists):
        assert c["mid"] in lists["matches"]


def test_today_already_frozen_gets_filter_lists_once_for_matches_not_started():
    day = "2026-11-27"
    started = _match("old", 0.62, ko="2026-11-27T10:00:00+00:00", p_over15=0.75)
    ms = MS + [started]
    hist = {"days": {day: {"frozen": True, "built": "2026-11-27T04:05:00+00:00", "tiers": {"safe": []},
                           "coupons": [], "matches": {}}}}
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    history.update(hist, ms, now, rel={})
    e = hist["days"][day]
    assert e["tiers"] == {"safe": []}  # la liste figée ne change pas
    fam = copy.deepcopy(e["fam"])
    mids = {c["mid"] for c in history._fam_picks(e)}
    assert mids and "old" not in mids  # rien sur un match déjà commencé
    # Calcul suivant, le modèle a changé d'avis : les listes par type restent figées
    later = [_match(m["id"], 0.5, p_over15=0.9) for m in MS]
    history.update(hist, later, datetime(2026, 11, 27, 16, 0, tzinfo=timezone.utc), rel={})
    assert hist["days"][day]["fam"] == fam


def test_filter_lists_are_settled_and_only_settled_ones_published():
    e = {"frozen": True, "tiers": {"safe": []}, "coupons": [],
         "fam": {"goals": {"safe": [{"id": "1|ou|1.5|over", "mid": "1", "key": "ou", "line": 1.5, "sel": "over",
                                     "p": 0.75, "fair": 1.33},
                                    {"id": "2|ou|1.5|over", "mid": "2", "key": "ou", "line": 1.5, "sel": "over",
                                     "p": 0.72, "fair": 1.39}]}},
         "matches": {"1": {"kickoff": "2026-11-27T13:00:00+00:00", "score": [2, 1]},
                     "2": {"kickoff": "2026-11-27T20:00:00+00:00"}}}
    history._apply_results(e)
    lst = e["fam"]["goals"]["safe"]
    assert lst[0]["res"] == "won" and lst[1]["res"] is None
    pub = history.public_copy({"days": {"2026-11-27": e}})["days"]["2026-11-27"]
    assert [c["mid"] for c in pub["fam"]["goals"]["safe"]] == ["1"]  # le pari en attente reste Premium
    assert pub["sealed"] == 1 and set(pub["matches"]) == {"1"}


def _day(res_tier, res_fam):
    return {"frozen": True, "tiers": {"safe": [{"p": 0.7, "res": r} for r in res_tier]}, "coupons": [],
            "fam": {"btts": {"safe": [{"p": 0.7, "res": r} for r in res_fam]}}}


def test_periods_count_only_their_days():
    days = {"2026-11-26": _day(["won", "lost"], ["won"]),   # hier
            "2026-11-22": _day(["won"], ["lost"]),          # dans les 7 jours
            "2026-11-01": _day(["lost", "lost"], [])}       # dans les 30 jours
    per = {p["key"]: p for p in (build._period(days, "2026-11-27", k, n, "fr", "1 nov.") for k, n in build.PERIODS)}
    safe = {k: next(r for r in p["tiers"] if r["key"] == "safe") for k, p in per.items()}
    assert (safe["yday"]["won"], safe["yday"]["n"]) == (1, 2)
    assert (safe["d7"]["won"], safe["d7"]["n"]) == (2, 3)
    assert (safe["d30"]["won"], safe["d30"]["n"]) == (2, 5)
    assert safe["all"]["n"] == 5
    btts = next(r for r in per["d7"]["fams"] if r["key"] == "btts")
    assert (btts["won"], btts["n"]) == (1, 2)
    assert per["yday"]["short"] and per["d7"]["short"] and not per["d30"]["short"]
    assert per["d7"]["range"].startswith("Du ") and per["all"]["range"] == "Depuis le 1 nov."
    assert history.summary(days)["has_fam"]


def test_filter_list_is_one_premium_only_block():
    """Page publique : une liste par type n'est qu'un cadenas ; le vrai bloc (les cartes) va aux seuls comptes Premium."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from probalis.site import i18n
    from probalis.site.lock import Locker
    env = Environment(loader=FileSystemLoader(build.HERE / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    lk = Locker()
    lk.start("paris")
    env.globals.update(icon=build.icon, lk=lk)
    tpl = env.from_string(
        '{% from "_picks.html" import pick_card with context %}'
        '{% call lk(own=true) %}{% if lk.pub %}<p class="fam-lock">verrou</p>{% else %}<div class="picks">'
        '{% for e in lst %}{{ pick_card(e, open=true) }}{% endfor %}</div>{% endif %}{% endcall %}')
    c = {"id": "m1|ou|1.5|over", "mid": "m1", "key": "ou", "line": 1.5, "sel": "over", "p": 0.77, "fair": 1.3}
    e = build._pick_view(c, history._match_info(MS[0]), "fr", {"s-m1"})
    html = tpl.render(lst=[e], t=i18n.UI["fr"], root="")
    assert "verrou" in html and "data-add" not in html and "1,30" not in html and "77" not in html
    blocks = lk.all_of("paris")
    assert len(blocks) == 1  # pas de petits cadenas à l'intérieur de la liste
    assert "data-add" in blocks["1"] and "1,30" in blocks["1"] and "<!--lk:" not in blocks["1"]
    assert lk.free_of() == {} and lk.by_match() == {}  # ni offert, ni débloqué par l'analyse gratuite
