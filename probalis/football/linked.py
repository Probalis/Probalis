"""Coupes d'Europe et football féminin : données et modèle qui relient plusieurs pays.

- Coupes d'Europe masculines : championnats nationaux (football-data.co.uk, 21 pays) + matchs européens des
  trois dernières saisons (TheSportsDB). Les clubs européens sont reliés aux équipes des championnats par
  leur nom, pays par pays.
- Football féminin : tout vient de TheSportsDB (cinq grands championnats + Ligue des champions féminine),
  les équipes sont identifiées par leur numéro TheSportsDB.
- Championnats « TheSportsDB seul » (Ligue saoudienne) : même principe que le football féminin.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from .data import MatchRow, load_extra, load_history
from .fixtures import match_names, next_event, round_events, score
from .leagues import LEAGUES, League, season_codes
from .model import Game, LinkedModel, fit_linked

CUP_ROUNDS = (1, 2, 3, 4, 5, 6, 7, 8, 32, 16, 125, 150, 200, 400)  # numérotation TheSportsDB des tours
FINAL_ROUND = "200"
_CODE_OF_TSDB = {str(lg.tsdb_id): lg.code for lg in LEAGUES}  # numéro de ligue TheSportsDB -> notre code
MAX_ROUNDS = 40
WOMEN_MAX_DAYS = 2 * 365
WORLD_MAX_DAYS = 2 * 365

# Championnats nationaux masculins qui servent à situer les clubs : pays -> (fichier, code football-data)
DOMESTIC_SOURCES = {
    "england": ("main", "E0"), "spain": ("main", "SP1"), "italy": ("main", "I1"), "germany": ("main", "D1"),
    "france": ("main", "F1"), "netherlands": ("main", "N1"), "portugal": ("main", "P1"),
    "belgium": ("main", "B1"), "turkey": ("main", "T1"), "scotland": ("main", "SC0"), "greece": ("main", "G1"),
    "austria": ("extra", "AUT"), "switzerland": ("extra", "SWZ"), "denmark": ("extra", "DNK"),
    "norway": ("extra", "NOR"), "sweden": ("extra", "SWE"), "poland": ("extra", "POL"),
    "romania": ("extra", "ROU"), "ireland": ("extra", "IRL"), "finland": ("extra", "FIN"),
}
_COUNTRY_ALIASES = {"the netherlands": "netherlands", "holland": "netherlands", "turkiye": "turkey",
                    "republic of ireland": "ireland", "monaco": "france", "czech republic": "czechia"}


def country_key(name: str | None) -> str | None:
    if not name:
        return None
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower().strip()
    s = re.sub(r"\s+", " ", s)
    return _COUNTRY_ALIASES.get(s, s) or None


def _season_start(season: str) -> int:
    return int(season[:4])


def _prev(season: str, k: int) -> str:
    y = _season_start(season) - k
    return f"{y}-{y + 1}"


def _current_season(lg: League, today: date) -> tuple[str, int | None]:
    """Saison en cours selon TheSportsDB et numéro de la prochaine journée."""
    e = next_event(lg.tsdb_id)
    y = today.year if today.month >= 7 else today.year - 1
    season = (e or {}).get("strSeason") or f"{y}-{y + 1}"
    try:
        nxt = int((e or {}).get("intRound"))
    except (TypeError, ValueError):
        nxt = None
    return season, nxt


def cup_events(lg: League, seasons: list[str], current: str) -> list[dict]:
    """Tous les matchs connus d'une coupe (joués ou non) sur les saisons demandées."""
    out = []
    for s in seasons:
        for r in CUP_ROUNDS:
            out += round_events(lg.tsdb_id, s, r, past_season=(s != current))
    return out


def league_events(lg: League, seasons: list[str], current: str, next_round: int | None) -> list[dict]:
    """Matchs d'un championnat : journées 1, 2, 3… jusqu'à la fin (saison passée) ou la journée en cours."""
    out = []
    for s in seasons:
        past = s != current
        last = MAX_ROUNDS if past or next_round is None else min(next_round, MAX_ROUNDS)
        empty = 0
        for r in range(1, last + 1):
            ev = round_events(lg.tsdb_id, s, r, past_season=past)
            out += ev
            empty = 0 if ev else empty + 1
            if empty >= 2:
                break
    return out


def _games_from_events(events: list[dict], node_of, kind: str) -> list[Game]:
    seen, out = set(), []
    for e in events:
        eid, sc = e.get("idEvent"), score(e)
        if not eid or eid in seen or sc is None:
            continue
        h, a = node_of(e.get("idHomeTeam")), node_of(e.get("idAwayTeam"))
        try:
            d = date.fromisoformat(e.get("dateEvent") or "")
        except ValueError:
            continue
        if not h or not a or h == a:
            continue
        seen.add(eid)
        out.append(Game(d, h, a, sc[0], sc[1], kind, neutral=str(e.get("intRound")) == FINAL_ROUND,
                        comp=_CODE_OF_TSDB.get(str(e.get("idLeague") or ""), "")))
    return out


@dataclass
class Linked:
    """Modèle relié + correspondance numéro d'équipe TheSportsDB -> équipe du modèle."""
    model: LinkedModel
    node_of_id: dict[str, str]
    names: dict[str, str] = field(default_factory=dict)  # équipe du modèle -> nom affiché
    report: dict = field(default_factory=dict)
    games: list[Game] = field(default_factory=list)  # matchs joués (forme récente et face-à-face)

    def node(self, tsdb_id: str | None) -> str | None:
        n = self.node_of_id.get(str(tsdb_id)) if tsdb_id else None
        return n if n and self.model.knows(n) else None


def _team_countries(events: list[dict]) -> tuple[dict[str, str], dict[str, str]]:
    """Pays de chaque club (pays du stade quand il reçoit, hors finale) et son nom TheSportsDB."""
    seen: dict[str, Counter] = {}
    names: dict[str, str] = {}
    for e in events:
        hid, aid = e.get("idHomeTeam"), e.get("idAwayTeam")
        if hid:
            names[hid] = e.get("strHomeTeam") or names.get(hid, "")
            c = country_key(e.get("strCountry"))
            if c and str(e.get("intRound")) != FINAL_ROUND:
                seen.setdefault(hid, Counter())[c] += 1
        if aid:
            names[aid] = e.get("strAwayTeam") or names.get(aid, "")
    return {t: cnt.most_common(1)[0][0] for t, cnt in seen.items()}, names


def _domestic_rows(country: str, start_year: int) -> list[MatchRow]:
    kind, code = DOMESTIC_SOURCES[country]
    if kind == "main":
        return load_history(code, season_codes(start_year, 3))
    return [m for m in load_extra(code) if m.played]


@dataclass
class LinkedData:
    games: list[Game]
    group_of: dict[str, str]
    node_of_id: dict[str, str]
    names: dict[str, str]
    unmatched: list[str]
    first_half_share: float = 0.45


def men_cups_data(cups: list[League], today: date) -> LinkedData:
    """Matchs (championnats + coupes d'Europe) et correspondance des clubs, pour le modèle des coupes."""
    current, _ = _current_season(cups[0], today)
    seasons = [current, _prev(current, 1), _prev(current, 2)]
    events = []
    for lg in cups:
        events += cup_events(lg, seasons, current)
    country_of, tsdb_name = _team_countries(events)
    start_year = _season_start(current)

    games: list[Game] = []
    group_of: dict[str, str] = {}
    node_of_id: dict[str, str] = {}
    display: dict[str, str] = {}
    unmatched: list[str] = []
    by_country: dict[str, list[str]] = {}
    for tid, c in country_of.items():
        by_country.setdefault(c, []).append(tid)
    for c, (_, code) in DOMESTIC_SOURCES.items():
        rows = _domestic_rows(c, start_year)
        if not rows:
            continue
        recent = [m for m in rows if (today - m.date).days <= 3 * 365]
        fd_names = sorted({m.home for m in recent} | {m.away for m in recent})
        for m in recent:
            games.append(Game(m.date, f"{c}|{m.home}", f"{c}|{m.away}", m.fthg, m.ftag, "dom", comp=m.league))
        for t in fd_names:
            group_of[f"{c}|{t}"] = c
        ids = by_country.get(c, [])
        mapping = match_names(sorted({tsdb_name[t] for t in ids}), fd_names)
        for tid in ids:
            fd = mapping.get(tsdb_name[tid])
            if fd:
                node_of_id[tid] = f"{c}|{fd}"
            else:
                unmatched.append(f"{c}: {tsdb_name[tid]}")
    for tid, name in tsdb_name.items():
        if tid not in node_of_id:
            node_of_id[tid] = f"t{tid}"
            c = country_of.get(tid, "?")
            # Club absent du championnat de ce pays (club gallois qui joue en Angleterre, club ukrainien exilé
            # en Pologne, 2e division…) : on ne lui prête pas la force moyenne de ce championnat.
            group_of[f"t{tid}"] = f"hors:{c}" if c in DOMESTIC_SOURCES else c
        display[node_of_id[tid]] = name
    games += _games_from_events(events, node_of_id.get, "cup")
    return LinkedData(games, group_of, node_of_id, display, unmatched, _first_half_share(start_year))


def men_cups(cups: list[League], today: date, verbose: bool = True) -> Linked | None:
    """Modèle des coupes d'Europe masculines."""
    if not cups:
        return None
    d = men_cups_data(cups, today)
    model = fit_linked(d.games, d.group_of, today, first_half_share=d.first_half_share,
                       include_ref_day=True)
    if verbose:
        n_cup = sum(g.kind == "cup" for g in d.games)
        print(f"  Coupes d'Europe : {n_cup} matchs européens + {len(d.games) - n_cup} matchs de championnat, "
              f"{len(model.teams)} équipes")
    return Linked(model, d.node_of_id, d.names, {"unmatched_teams": d.unmatched,
                                                  "countries": _group_table(model)}, d.games)


def _first_half_share(start_year: int) -> float:
    """Part des buts marqués en 1re mi-temps, mesurée sur les cinq grands championnats."""
    ht = tot = 0
    for code in ("E0", "SP1", "I1", "D1", "F1"):
        for m in load_history(code, season_codes(start_year, 2)):
            if m.hthg is not None and m.htag is not None:
                ht += m.hthg + m.htag
                tot += m.fthg + m.ftag
    return ht / tot if tot else 0.45


def _group_table(model: LinkedModel) -> list[list]:
    """Pays classés par force moyenne (attaque moins défense), pour vérifier que le modèle est sensé."""
    rows = [[g, round(model.group_attack[g] - model.group_defence[g], 3)] for g in model.group_attack]
    return sorted(rows, key=lambda r: -r[1])


def tsdb_data(leagues: list[League], today: date) -> LinkedData:
    """Matchs de championnats (et de coupes) suivis par TheSportsDB seul : football féminin, Ligue saoudienne.
    Les équipes sont identifiées par leur numéro TheSportsDB ; deux saisons."""
    games: list[Game] = []
    group_of: dict[str, str] = {}
    display: dict[str, str] = {}
    cup_ev: list[dict] = []
    for lg in leagues:
        current, nxt = _current_season(lg, today)
        if lg.cup:
            ev = cup_events(lg, [current, _prev(current, 1)], current)
            cup_ev += ev
            games += _games_from_events(ev, lambda t: f"t{t}" if t else None, "cup")
        else:
            ev = league_events(lg, [current, _prev(current, 1)], current, nxt)
            games += _games_from_events(ev, lambda t: f"t{t}" if t else None, "dom")
            for e in ev:
                for side in ("Home", "Away"):
                    tid = e.get(f"id{side}Team")
                    if tid:
                        group_of[f"t{tid}"] = lg.code
                        display[f"t{tid}"] = e.get(f"str{side}Team") or ""
    country_of, names = _team_countries(cup_ev)
    for tid, name in names.items():
        node = f"t{tid}"
        group_of.setdefault(node, "pays:" + (country_of.get(tid) or "?"))
        display.setdefault(node, name)
    return LinkedData(games, group_of, {n[1:]: n for n in group_of}, display, [])


women_data = tsdb_data


def women(leagues: list[League], today: date, verbose: bool = True) -> Linked | None:
    """Modèle commun à tous les championnats féminins et à la Ligue des champions féminine."""
    if not leagues:
        return None
    d = tsdb_data(leagues, today)
    model = fit_linked(d.games, d.group_of, today, max_days=WOMEN_MAX_DAYS, include_ref_day=True)
    if verbose:
        n_cup = sum(g.kind == "cup" for g in d.games)
        print(f"  Football féminin : {len(d.games) - n_cup} matchs de championnat + {n_cup} matchs européens, "
              f"{len(model.teams)} équipes")
    return Linked(model, d.node_of_id, d.names, {"countries": _group_table(model)}, d.games)


def world(leagues: list[League], today: date, verbose: bool = True) -> Linked | None:
    """Championnats masculins suivis par TheSportsDB seul (Ligue saoudienne) : un modèle par lot, sans cotes."""
    if not leagues:
        return None
    d = tsdb_data(leagues, today)
    current, _ = _current_season(leagues[0], today)
    model = fit_linked(d.games, d.group_of, today, max_days=WORLD_MAX_DAYS, include_ref_day=True,
                       first_half_share=_first_half_share(_season_start(current)))
    if verbose:
        print(f"  Autres championnats (TheSportsDB) : {len(d.games)} matchs, {len(model.teams)} équipes")
    return Linked(model, d.node_of_id, d.names, {"countries": _group_table(model)}, d.games)
