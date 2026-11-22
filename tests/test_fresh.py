"""Relance toutes les 2 heures : fenêtre de 8 jours, résultats du jour pris en compte, cache court."""
from datetime import date, datetime, timedelta, timezone

import numpy as np

from probalis.football.data import FRESH_HOURS, MatchRow
from probalis.football.fixtures import LIVE_HOURS, _round_max_age, finished, upcoming_fixtures
from probalis.football.leagues import BY_CODE
from probalis.football.model import fit
from probalis.football.pipeline import _fresh_results


def _event(eid, home, away, ko: datetime, score=None, status=None):
    return {"idEvent": eid, "strHomeTeam": home, "strAwayTeam": away,
            "strTimestamp": ko.strftime("%Y-%m-%dT%H:%M:%S"), "dateEvent": ko.date().isoformat(),
            "intHomeScore": None if score is None else str(score[0]),
            "intAwayScore": None if score is None else str(score[1]),
            "strStatus": status or ("Match Finished" if score else "Not Started"), "intRound": "12"}


def _history(ref: date, n_teams=8, seasons=3, seed=3):
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    rows = []
    for k in range(seasons):
        for i, h in enumerate(teams):
            for j, a in enumerate(teams):
                if h != a:
                    d = ref - timedelta(days=5 + 100 * k + (i * n_teams + j) % 90)
                    rows.append(MatchRow("E0", d, h, a, int(rng.poisson(1.5)), int(rng.poisson(1.1))))
    return sorted(rows, key=lambda m: m.date)


def test_same_day_results_count_only_when_asked():
    ref = date(2026, 11, 22)
    hist = _history(ref) + [MatchRow("E0", ref, "T0", "T1", 5, 0)]
    live = fit(hist, ref, include_ref_day=True)
    replay = fit(hist, ref)  # tests de fiabilité : jamais le résultat du jour même
    assert live.n_matches == replay.n_matches + 1


def test_fresh_results_fill_the_gap_without_duplicates():
    ref = date(2026, 11, 22)
    hist = _history(ref)
    known = hist[-1]
    ko = datetime(2026, 11, 22, 12, 30, tzinfo=timezone.utc)
    events = [
        _event("1", "Team Zero", "Team One", ko, (2, 1)),                    # pas encore dans le fichier
        _event("2", "Known Home", "Known Away", datetime.combine(known.date, datetime.min.time(), timezone.utc),
               (known.fthg, known.ftag)),                                    # déjà dans le fichier
        _event("3", "Team Two", "Team Three", ko + timedelta(hours=3)),      # pas encore joué
        _event("4", "Unknown", "Team One", ko, (0, 0)),                      # équipe non reconnue
    ]
    names = {"Team Zero": "T0", "Team One": "T1", "Team Two": "T2", "Team Three": "T3",
             "Known Home": known.home, "Known Away": known.away}
    fresh = _fresh_results(BY_CODE["E0"], events, hist, names)
    assert [(m.home, m.away, m.fthg, m.ftag, m.date) for m in fresh] == [("T0", "T1", 2, 1, ref)]


def test_window_keeps_today_to_day_eight_and_drops_finished():
    today = date(2026, 11, 19)
    base = datetime(2026, 11, 19, 18, 0, tzinfo=timezone.utc)
    events = [_event("a", "A", "B", base - timedelta(hours=4), (1, 0)),     # joué plus tôt dans la journée
              _event("b", "C", "D", base),                                   # ce soir
              _event("c", "E", "F", base + timedelta(days=8)),               # le 27 : dans la fenêtre
              _event("d", "G", "H", base + timedelta(days=9)),               # le 28 : hors fenêtre
              _event("e", "I", "J", base - timedelta(days=1))]               # hier
    fx = upcoming_fixtures(BY_CODE["E0"], today, today + timedelta(days=8), events)
    assert [f.event_id for f in fx] == ["b", "c"]
    assert [e["idEvent"] for e, _, _ in finished(events)] == ["a"]


def test_round_cache_is_short_only_while_matches_are_close():
    now = datetime.now(timezone.utc)
    soon = [_event("1", "A", "B", now + timedelta(hours=10))]
    in_play = [_event("1", "A", "B", now - timedelta(hours=1), status="2H")]
    just_played = [_event("1", "A", "B", now - timedelta(hours=3), status="Not Started")]
    played_no_result = [_event("1", "A", "B", now - timedelta(hours=6), status="Not Started")]
    later = [_event("1", "A", "B", now + timedelta(days=5))]
    old_postponed = [_event("1", "A", "B", now - timedelta(days=20), status="Postponed"),
                     _event("2", "C", "D", now - timedelta(days=20), (1, 1))]
    assert _round_max_age(soon) == FRESH_HOURS
    assert _round_max_age(in_play) == LIVE_HOURS        # match en cours : score en direct à chaque relance
    assert _round_max_age(just_played) == LIVE_HOURS
    assert _round_max_age(played_no_result) == FRESH_HOURS
    assert _round_max_age(later) == 6
    assert _round_max_age(old_postponed) == 24
    assert _round_max_age([]) == 24
