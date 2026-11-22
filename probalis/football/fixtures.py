"""Matchs à venir et logos (TheSportsDB, clé publique gratuite) + rapprochement des noms d'équipes."""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher

import numpy as np
from scipy.optimize import linear_sum_assignment

from .data import CACHE, FRESH_HOURS, USER_AGENT, download
from .leagues import League

TSDB = "https://www.thesportsdb.com/api/v1/json/123/{endpoint}.php?{query}"
_MIN_INTERVAL = 6.5  # en pratique l'offre gratuite bloque au-delà d'une dizaine d'appels par minute
_last_call = 0.0

# Noms difficiles : nom TheSportsDB (normalisé) -> nom football-data.co.uk
ALIASES = {
    "wolverhampton wanderers": "Wolves",
    "nottingham forest": "Nott'm Forest",
    "sheffield wednesday": "Sheffield Weds",
    "queens park rangers": "QPR",
    "west bromwich albion": "West Brom",
    "borussia monchengladbach": "M'gladbach",
    "eintracht frankfurt": "Ein Frankfurt",
    "fortuna dusseldorf": "Fortuna Dusseldorf",
    "atletico madrid": "Ath Madrid",
    "deportivo alaves": "Alaves",
    "deportivo de a coruna": "La Coruna",
    "deportivo la coruna": "La Coruna",
    "racing santander": "Santander",
    "real betis": "Betis",
    "athletic bilbao": "Ath Bilbao",
    "rayo vallecano": "Vallecano",
    "espanyol": "Espanol",
    "paris saint germain": "Paris SG",
    "inter milan": "Inter",
    "internazionale": "Inter",
    "ac milan": "Milan",
    "sporting cp": "Sp Lisbon",
    "sporting lisbon": "Sp Lisbon",
    "sporting braga": "Sp Braga",
    "vitoria guimaraes": "Guimaraes",
    "union saint gilloise": "St. Gilloise",
    "royale union saint gilloise": "St. Gilloise",
    "royal antwerp": "Antwerp",
    "istanbul basaksehir": "Buyuksehyr",
    "corum": "Corum",
    "corum fk": "Corum",
    "universitatea cluj": "U. Cluj",
    "heart of midlothian": "Hearts",
    "celta fortuna": "Celta B",
    "celta vigo b": "Celta B",
    "real sociedad b": "Sociedad B",
    "sanse": "Sociedad B",
    "sporting gijon": "Sp Gijon",
    "real sporting de gijon": "Sp Gijon",
}
_ABBREV = {"man": "manchester", "utd": "united", "nottm": "nottingham", "weds": "wednesday", "sp": "sporting",
           "ath": "athletic", "ein": "eintracht", "st": "saint"}
_DROP = {"fc", "afc", "cf", "sc", "ac", "club", "de", "the", "and", "calcio", "sv", "vfb", "vfl", "tsg", "fk", "sk",
         "rc", "rcd", "ud", "cd", "sd", "ca", "us", "as", "ssc", "1", "kv", "krc", "kaa", "rsc", "osc", "ogc", "hsc"}


def _cache_path(endpoint: str, query: dict):
    q = urllib.parse.urlencode(query)
    return CACHE / "tsdb" / f"{endpoint}_{q.replace('&', '_').replace('=', '-')}.json"


def _get(endpoint: str, query: dict, max_age_hours: float) -> dict:
    """Appel TheSportsDB avec cache, espacement des appels et nouvelles tentatives si limite atteinte."""
    global _last_call
    q = urllib.parse.urlencode(query)
    path = _cache_path(endpoint, query)
    for attempt in range(4):
        fresh = path.exists() and (time.time() - path.stat().st_mtime) / 3600 < max_age_hours
        if not fresh:
            wait = _MIN_INTERVAL - (time.time() - _last_call)
            if wait > 0:
                time.sleep(wait)
            _last_call = time.time()
        try:
            download(TSDB.format(endpoint=endpoint, query=q), path, max_age_hours)
            return json.loads(path.read_text(encoding="utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                print("    (TheSportsDB : trop d'appels, pause d'une minute)", flush=True)
                time.sleep(60)
                continue
            return {}
        except Exception:
            return {}
    return {}


def normalize(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s.replace("'", ""))
    tokens = [_ABBREV.get(t, t) for t in s.split()]
    return " ".join(t for t in tokens if t not in _DROP)


def _similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / max(len(ta | tb), 1)
    contained = 1.0 if (na and nb and (na in nb or nb in na)) else 0.0
    return 0.5 * SequenceMatcher(None, na, nb).ratio() + 0.35 * jacc + 0.15 * contained


def match_names(tsdb_names: list[str], fd_names: list[str], min_score: float = 0.45) -> dict[str, str]:
    """Associe chaque nom TheSportsDB au nom football-data.co.uk le plus proche (affectation optimale)."""
    out: dict[str, str] = {}
    rest = []
    fd_set = set(fd_names)
    for t in tsdb_names:
        alias = ALIASES.get(re.sub(r"\s+", " ", unicodedata.normalize("NFKD", t).encode("ascii", "ignore")
                                   .decode().lower().replace("-", " ").replace(".", "")).strip())
        if alias and alias in fd_set:
            out[t] = alias
        elif t in fd_set:
            out[t] = t
        else:
            rest.append(t)
    cands = [f for f in fd_names if f not in out.values()]
    if rest and cands:
        cost = np.array([[-_similarity(t, f) for f in cands] for t in rest])
        rows, cols = linear_sum_assignment(cost)
        for r, c in zip(rows, cols):
            if -cost[r, c] >= min_score:
                out[rest[r]] = cands[c]
    return out


@dataclass
class Fixture:
    league: str
    event_id: str
    kickoff_utc: datetime
    home_tsdb: str
    away_tsdb: str
    home_badge: str | None
    away_badge: str | None
    round: str | None
    venue: str | None
    league_badge: str | None = None
    home_id: str | None = None
    away_id: str | None = None
    country: str | None = None   # pays du stade (sert à situer les clubs en coupe d'Europe)


def _kickoff(e: dict) -> datetime | None:
    ts = e.get("strTimestamp")
    if ts:
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    d, t = e.get("dateEvent"), (e.get("strTime") or "00:00:00")
    if not d:
        return None
    try:
        return datetime.fromisoformat(f"{d}T{t[:8]}").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def league_rounds(league: League, horizon_end: date, max_rounds: int = 6) -> list[dict]:
    """Matchs de la journée précédente, de la journée en cours et des suivantes jusqu'à horizon_end.

    On avance journée par journée tant que la fenêtre n'est pas couverte : en période chargée
    (fêtes de fin d'année, matchs en semaine), il peut y avoir trois journées en huit jours.
    """
    nxt = _get("eventsnextleague", {"id": league.tsdb_id}, 6).get("events") or []
    if not nxt:
        return []
    season = nxt[0].get("strSeason")
    try:
        first_round = int(nxt[0].get("intRound"))
    except (TypeError, ValueError):
        first_round = None
    events = list(nxt)
    if first_round is not None and season:
        if first_round > 1:  # résultats récents, pas toujours encore dans les fichiers football-data.co.uk
            events += round_events(league.tsdb_id, season, first_round - 1, past_season=False)
        for r in range(first_round, first_round + max_rounds):
            ev = round_events(league.tsdb_id, season, r, past_season=False)
            events += ev
            kos = [k for k in map(_kickoff, ev) if k]
            if not kos or min(kos).date() > horizon_end:
                break
    return events


def finished(events: list[dict]) -> list[tuple[dict, datetime, tuple[int, int]]]:
    """Matchs terminés (avec leur coup d'envoi et leur score), sans doublon."""
    seen, out = set(), []
    for e in events:
        eid, sc, ko = e.get("idEvent"), score(e), _kickoff(e)
        if eid and sc and ko and eid not in seen:
            seen.add(eid)
            out.append((e, ko, sc))
    return out


def upcoming_fixtures(league: League, today: date, horizon_end: date | None = None,
                      events: list[dict] | None = None) -> list[Fixture]:
    """Matchs pas encore joués, d'aujourd'hui à horizon_end (par défaut : huit jours)."""
    horizon_end = horizon_end or today + timedelta(days=8)
    if events is None:
        events = league_rounds(league, horizon_end)
    seen, out = set(), []
    for e in events:
        eid = e.get("idEvent")
        ko = _kickoff(e)
        if not eid or eid in seen or ko is None or ko.date() < today or ko.date() > horizon_end:
            continue
        if (e.get("strStatus") or "").lower() in {"match finished", "ft", "aet", "pen", "postponed", "cancelled"}:
            continue
        seen.add(eid)
        out.append(Fixture(league=league.code, event_id=eid, kickoff_utc=ko,
                           home_tsdb=e.get("strHomeTeam") or "", away_tsdb=e.get("strAwayTeam") or "",
                           home_badge=e.get("strHomeTeamBadge"), away_badge=e.get("strAwayTeamBadge"),
                           round=e.get("intRound"), venue=e.get("strVenue"),
                           league_badge=e.get("strLeagueBadge"), home_id=e.get("idHomeTeam"),
                           away_id=e.get("idAwayTeam"), country=e.get("strCountry")))
    out.sort(key=lambda f: f.kickoff_utc)
    return out


_PLAYED = {"match finished", "ft", "aet", "pen", "ap", "aw", "awarded"}
_LIVE_OR_LATER = {"ns", "not started", "tbd", "1h", "2h", "ht", "et", "bt", "p", "live", "susp", "int",
                  "postponed", "pst", "cancelled", "canc", "abandoned", "abd"}


# Match en cours dans le temps réglementaire. Pas les prolongations ni les tirs au but : les paris portent sur les
# 90 minutes, le score du temps réglementaire reste alors celui relevé juste avant.
_IN_PLAY = {"1h", "ht", "2h", "live"}
LIVE_HOURS = 0.25  # cache d'une journée dont un match se joue : redemandée à chaque relance (score en direct)


def final_score(e: dict) -> tuple[int, int] | None:
    """Score final seulement si TheSportsDB marque clairement le match comme fini (« FT »…) : réglé sans attendre."""
    status = (e.get("strStatus") or "").strip().lower()
    return score(e) if status in _PLAYED else None


def live_score(e: dict) -> tuple[int, int] | None:
    """Score d'un match en cours (TheSportsDB le donne dans ses journées, sans clé payante), sinon None."""
    status = (e.get("strStatus") or "").strip().lower()
    hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
    if status not in _IN_PLAY or hs in (None, "") or as_ in (None, ""):
        return None
    try:
        return int(hs), int(as_)
    except (TypeError, ValueError):
        return None


def score(e: dict) -> tuple[int, int] | None:
    """Score final d'un match terminé, sinon None."""
    status = (e.get("strStatus") or "").strip().lower()
    hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
    if hs in (None, "") or as_ in (None, "") or status in _LIVE_OR_LATER:
        return None
    if status and status not in _PLAYED:
        return None
    try:
        return int(hs), int(as_)
    except (TypeError, ValueError):
        return None


def _round_max_age(events: list[dict] | None) -> float:
    """Durée de cache d'une journée pas encore terminée.

    Très courte si un de ses matchs a commencé il y a moins de 4 heures sans score final : chaque relance récupère
    le score en direct (paris déjà gagnés ou perdus réglés tout de suite). Courte si un de ses matchs se joue dans
    les 36 heures ou vient de se jouer sans résultat connu : chaque relance récupère alors les scores et les
    changements d'horaire.
    """
    if not events:
        return 24 if events is not None else 6
    now = datetime.now(timezone.utc)
    pending = [k for e in events if not score(e) and (k := _kickoff(e))]
    if any(-4 * 3600 <= (k - now).total_seconds() <= 0 for k in pending):
        return LIVE_HOURS
    if any(-3 * 86400 <= (k - now).total_seconds() <= 36 * 3600 for k in pending):
        return FRESH_HOURS
    return 6 if any(k > now for k in pending) else 24  # 24 h : il ne manque que des matchs reportés


def round_events(league_id: int, season: str, rnd: int, past_season: bool) -> list[dict]:
    """Matchs d'une journée (ou d'un tour). Une saison finie, ou une journée entièrement jouée,
    est gardée en cache sans limite : on ne la redemande jamais."""
    q = {"id": league_id, "r": rnd, "s": season}
    path = _cache_path("eventsround", q)
    ev = None
    if path.exists():
        try:
            ev = json.loads(path.read_text(encoding="utf-8")).get("events") or []
        except ValueError:
            ev = None
        if ev is not None and (past_season or (ev and all(score(e) for e in ev))):
            return ev
    return _get("eventsround", q, 24 * 365 if past_season else _round_max_age(ev)).get("events") or []


def next_event(league_id: int) -> dict | None:
    """Prochain match annoncé de la compétition (donne la saison et la journée en cours)."""
    ev = _get("eventsnextleague", {"id": league_id}, 6).get("events") or []
    return ev[0] if ev else None


def league_badge(league_id: int) -> str | None:
    """Logo de la compétition (gardé un mois en cache)."""
    lg = (_get("lookupleague", {"id": league_id}, 24 * 30).get("leagues") or [{}])[0]
    return lg.get("strBadge")
