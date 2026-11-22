"""Cotes des compétitions absentes des fichiers football-data.co.uk : coupes d'Europe, Ligue des champions féminine,
Frauen-Bundesliga, Ligue saoudienne. Source : The Odds API, offre gratuite (500 crédits par mois, conditions lues
le 22/11/2026 : affichage et calculs dérivés permis, y compris sur un site payant ; revente des données brutes
interdite).

- Clé : variable PROBALIS_ODDS_API_KEY (secret GitHub ; sur le PC, fichier cotes.env du dossier des secrets).
  Sans clé, rien n'est demandé : ces matchs restent calculés par le modèle seul, comme avant.
- Coût : 1 crédit par marché demandé, donc 2 crédits (1X2 + plus/moins de buts) par compétition et par appel ;
  une réponse sans match est gratuite.
- Quota gardé : une compétition n'est redemandée que si elle a un match dans les 3 jours, au plus toutes les 12 h
  (toutes les 24 h si son prochain match est à plus d'un jour) ; budget mensuel par compétition (BUDGET) ; plus
  aucun appel sous RESERVE crédits restants (chiffre renvoyé par The Odds API à chaque appel).
- La clé n'est jamais écrite dans un message ni dans le cache.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from .data import CACHE, USER_AGENT
from .fixtures import Fixture, match_names

KEY_ENV = "PROBALIS_ODDS_API_KEY"
URL = "https://api.the-odds-api.com/v4/sports/{sport}/odds/"
SPORTS = {  # notre code -> clé de la compétition chez The Odds API
    "UCL": "soccer_uefa_champs_league",
    "UEL": "soccer_uefa_europa_league",
    "UECL": "soccer_uefa_europa_conference_league",
    "UWCL": "soccer_uefa_champs_league_women",
    "FBL": "soccer_germany_bundesliga_women",
    "SA": "soccer_saudi_arabia_pro_league",
}
REGION = "eu"                # bookmakers européens (1xBet, Pinnacle, Unibet, Betclic, Winamax…)
MARKETS = ("h2h", "totals")  # 1X2 et plus/moins de buts
COST = len(MARKETS)
BUDGET = {"UCL": 90, "UEL": 80, "UECL": 80, "UWCL": 40, "FBL": 60, "SA": 80}  # crédits par mois (total 430)
RESERVE = 40                 # crédits jamais dépensés (marge pour les lancements depuis le PC)
AHEAD_H = 72                 # on ne demande les cotes que pour un match dans les 3 jours
FRESH_NEAR_H = 12            # match dans les 24 h : cotes redemandées au plus toutes les 12 h
FRESH_FAR_H = 24             # match dans 1 à 3 jours : au plus toutes les 24 h
KEEP_H = 30                  # cotes gardées au plus 30 h sans nouvel appel
MIN_BOOKS = 2                # moyenne sur au moins 2 bookmakers
MATCH_WINDOW_H = 6           # écart d'horaire toléré entre The Odds API et TheSportsDB
DIR = CACHE / "oddsapi"
STATE = DIR / "quota.json"


def _key() -> str:
    return (os.environ.get(KEY_ENV) or "").strip()


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _state(now: datetime) -> dict:
    s = _read(STATE, {})
    month = now.strftime("%Y-%m")
    if s.get("month") != month:  # nouveau mois : le quota gratuit repart à 500
        s = {"month": month, "used": {}, "remaining": None}
    return s


def needs_refresh(next_ko: datetime | None, fetched_at: datetime | None, now: datetime) -> bool:
    """Faut-il redemander les cotes d'une compétition ? (prochain match, date des cotes gardées)"""
    if next_ko is None:
        return False
    ahead = (next_ko - now).total_seconds() / 3600
    if ahead < -2 or ahead > AHEAD_H:
        return False
    if fetched_at is None:
        return True
    limit = FRESH_NEAR_H if ahead <= 24 else FRESH_FAR_H
    return (now - fetched_at).total_seconds() / 3600 >= limit


def can_spend(code: str, state: dict) -> bool:
    if state.get("remaining") is not None and state["remaining"] - COST < RESERVE:
        return False
    return state.get("used", {}).get(code, 0) + COST <= BUDGET.get(code, 0)


def _get(sport: str, key: str, now: datetime) -> tuple[list[dict], dict]:
    q = {"apiKey": key, "regions": REGION, "markets": ",".join(MARKETS), "oddsFormat": "decimal",
         "dateFormat": "iso", "commenceTimeFrom": (now - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
         "commenceTimeTo": (now + timedelta(hours=AHEAD_H + 24)).strftime("%Y-%m-%dT%H:%M:%SZ")}
    req = urllib.request.Request(URL.format(sport=sport) + "?" + urllib.parse.urlencode(q),
                                 headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        h = {k.lower(): v for k, v in resp.headers.items()}
    return (body if isinstance(body, list) else []), h


def fetch(code: str, next_ko: datetime | None, now: datetime | None = None, verbose: bool = True,
          getter=_get) -> list[dict]:
    """Matchs cotés d'une compétition (format The Odds API), depuis le cache ou un nouvel appel si utile."""
    now = now or datetime.now(timezone.utc)
    sport = SPORTS.get(code)
    if not sport:
        return []
    path = DIR / f"{code}.json"
    cached = _read(path, {})
    fetched_at = datetime.fromisoformat(cached["at"]) if cached.get("at") else None
    key = _key()
    if key and needs_refresh(next_ko, fetched_at, now):
        state = _state(now)
        if can_spend(code, state):
            try:
                events, headers = getter(sport, key, now)
            except urllib.error.HTTPError as e:  # 401 : clé refusée ; 429 : quota épuisé
                if verbose:
                    print(f"  Cotes {code} : The Odds API a refusé la demande (erreur {e.code})")
                if e.code in (401, 429):
                    state["remaining"] = 0
                    _save_state(state)
                events = None
            except (urllib.error.URLError, TimeoutError, ValueError) as e:
                if verbose:
                    print(f"  Cotes {code} : The Odds API injoignable ({type(e).__name__})")
                events = None
            if events is not None:
                last = _int(headers.get("x-requests-last"))
                state["used"][code] = state["used"].get(code, 0) + (COST if last is None else last)
                rem = _int(headers.get("x-requests-remaining"))
                if rem is not None:
                    state["remaining"] = rem
                _save_state(state)
                cached = {"at": now.isoformat(timespec="seconds"), "events": events}
                DIR.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
                fetched_at = now
                if verbose:
                    print(f"  Cotes {code} : {len(events)} matchs reçus (crédits restants ce mois : "
                          f"{state.get('remaining', '?')})")
        elif verbose:
            print(f"  Cotes {code} : budget du mois atteint, cotes gardées réutilisées")
    if fetched_at is None or (now - fetched_at).total_seconds() / 3600 > KEEP_H:
        return []
    return cached.get("events") or []


def _save_state(state: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")


def _int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def consensus(e: dict) -> dict:
    """Cotes d'un match rangées comme celles de football-data : {(clé, ligne): {sélection: {best, avg}}}."""
    home, away = e.get("home_team"), e.get("away_team")
    h2h: dict[str, list[float]] = {"1": [], "X": [], "2": []}
    ou: dict[str, list[float]] = {"over": [], "under": []}
    for b in e.get("bookmakers") or []:
        for mk in b.get("markets") or []:
            outs = mk.get("outcomes") or []
            if mk.get("key") == "h2h":
                price = {o.get("name"): o.get("price") for o in outs}
                trio = [price.get(home), price.get("Draw"), price.get(away)]
                if all(isinstance(x, (int, float)) and x > 1 for x in trio):
                    for s, x in zip(("1", "X", "2"), trio):
                        h2h[s].append(float(x))
            elif mk.get("key") == "totals":
                pair = {o.get("name"): o.get("price") for o in outs if o.get("point") == 2.5}
                o_, u_ = pair.get("Over"), pair.get("Under")
                if all(isinstance(x, (int, float)) and x > 1 for x in (o_, u_)):
                    ou["over"].append(float(o_))
                    ou["under"].append(float(u_))
    out = {}
    for (key, line), sels in ((("1x2", None), h2h), (("ou", 2.5), ou)):
        n = min(len(v) for v in sels.values())
        if n >= MIN_BOOKS:
            out[(key, line)] = {s: {"best": round(max(v), 3), "avg": round(sum(v) / len(v), 3)}
                                for s, v in sels.items()}
    return out


def _swap(markets: dict) -> dict:
    """Match annoncé à l'envers (terrain neutre) : domicile et extérieur échangés."""
    out = dict(markets)
    if ("1x2", None) in out:
        m = dict(out[("1x2", None)])
        m["1"], m["2"] = m["2"], m["1"]
        out[("1x2", None)] = m
    return out


def match_odds(fixtures: list[Fixture], events: list[dict]) -> dict[str, dict]:
    """Numéro TheSportsDB du match -> cotes, en reliant les noms des équipes et l'horaire."""
    if not fixtures or not events:
        return {}
    names = match_names(sorted({n for e in events for n in (e.get("home_team"), e.get("away_team")) if n}),
                        sorted({n for f in fixtures for n in (f.home_tsdb, f.away_tsdb)}))
    out: dict[str, dict] = {}
    for e in events:
        h, a = names.get(e.get("home_team") or ""), names.get(e.get("away_team") or "")
        try:
            ko = datetime.fromisoformat((e.get("commence_time") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        if not (h and a):
            continue
        for f in fixtures:
            if abs((f.kickoff_utc - ko).total_seconds()) > MATCH_WINDOW_H * 3600:
                continue
            if (f.home_tsdb, f.away_tsdb) == (h, a):
                mk = consensus(e)
            elif (f.home_tsdb, f.away_tsdb) == (a, h):
                mk = _swap(consensus(e))
            else:
                continue
            if ("1x2", None) in mk:
                out[f.event_id] = mk
    return out


def odds_for(code: str, fixtures: list[Fixture], now: datetime | None = None, verbose: bool = True) -> dict[str, dict]:
    """Cotes des prochains matchs d'une compétition (vide sans clé, ou si The Odds API ne la couvre pas)."""
    if code not in SPORTS:
        return {}
    now = now or datetime.now(timezone.utc)
    upcoming = sorted(f.kickoff_utc for f in fixtures if f.kickoff_utc >= now - timedelta(hours=2))
    events = fetch(code, upcoming[0] if upcoming else None, now, verbose)
    return match_odds(fixtures, events)
