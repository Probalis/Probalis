"""Match en direct, corners et cartons (ESPN, accès ouvert et sans clé).

ESPN publie pour chaque championnat la liste des matchs d'une journée (« scoreboard ») et, pour chaque match, son
déroulé (« summary » : temps forts, statistiques des deux équipes, compositions). Ce module :
- relie nos matchs (TheSportsDB) à ceux d'ESPN, par la date, l'heure du coup d'envoi et le nom des équipes ;
- relève les corners et les cartons d'un match fini, pour régler nos verdicts environ 2 h après le match, y compris
  en coupe d'Europe, en Arabie saoudite et chez les femmes (football-data ne couvre que les championnats).

Le direct lui-même (score, minute, temps forts, compositions) est lu par le navigateur des membres, à travers notre
relais probalis/site/live.mjs (Cloudflare) : jamais d'appel direct d'un téléphone vers ESPN.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone

import numpy as np
from scipy.optimize import linear_sum_assignment

from . import fixtures
from .data import CACHE

API = "https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/{what}"
DIR = CACHE / "espn"
# Nom simple et honnête : ESPN refuse les noms « Mozilla … Bot » (403), pas celui-ci.
USER_AGENT = "Probalis/0.1"

# Nos championnats -> nom ESPN (vérifiés le 23/11/2026). Absents d'ESPN : Frauen-Bundesliga, Serie A féminine.
SLUGS = {
    "E0": "eng.1", "SP1": "esp.1", "I1": "ita.1", "D1": "ger.1", "F1": "fra.1", "E1": "eng.2", "N1": "ned.1",
    "P1": "por.1", "B1": "bel.1", "T1": "tur.1", "F2": "fra.2", "SP2": "esp.2", "E2": "eng.3", "E3": "eng.4",
    "EC": "eng.5", "SA": "ksa.1", "UCL": "uefa.champions", "UEL": "uefa.europa", "UECL": "uefa.europa.conf",
    "UWCL": "uefa.wchampions", "WSL": "eng.w.1", "WD1": "fra.w.1", "LIGAF": "esp.w.1",
}
WINDOW = (-3, 2)                     # jours reliés autour d'aujourd'hui (matchs passés affichés, matchs proches)
KICKOFF_GAP = timedelta(hours=3)     # écart d'heure de coup d'envoi toléré (heure changée, données en retard)
MIN_NAME = 0.35                      # ressemblance minimale de chaque nom d'équipe
MIN_PAIR = 1.0                       # ressemblance minimale des deux noms ensemble (bonus si même heure)
NORMAL_END = {"STATUS_FULL_TIME", "STATUS_FINAL"}  # fini après 90 minutes (pas de prolongation ni de tirs au but)
_TIMEOUT = 20
_MIN_INTERVAL = 0.6                  # ESPN cesse de répondre un moment après ~80 demandes très rapprochées
_PAUSE = 45                          # pause avant de réessayer une adresse qui n'a pas répondu
MAX_FAILS = 6                        # au-delà, ESPN est considéré en panne pour ce calcul
_down: set[str] = set()              # adresses en panne pendant ce calcul : pas redemandées
_state = {"last": 0.0, "fails": 0}
errors: dict[str, int] = {}          # erreurs de ce calcul, pour le journal (« HTTP 403 » : 2…)


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(timezone.utc)


def _dt(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _fetch(url: str) -> dict | None:
    """Réponse JSON d'ESPN, ou None (panne, réponse illisible). Demandes espacées ; une adresse qui ne répond pas
    est réessayée une fois après une pause, puis plus redemandée pendant ce calcul."""
    if url in _down or _state["fails"] >= MAX_FAILS:
        return None
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(2):
        wait = _MIN_INTERVAL - (time.time() - _state["last"])
        if wait > 0:
            time.sleep(wait)
        _state["last"] = time.time()
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            kind = f"HTTP {e.code}"
            if e.code in (400, 404):      # adresse inconnue (championnat absent, match retiré) : pas la peine
                errors[kind] = errors.get(kind, 0) + 1
                _down.add(url)
                return None
        except Exception as e:
            kind = type(e).__name__
        errors[kind] = errors.get(kind, 0) + 1
        if attempt == 0:
            time.sleep(_PAUSE)
    _down.add(url)
    _state["fails"] += 1
    return None


def _cached(name: str, max_age_hours: float | None, make) -> object:
    """Fichier du cache s'il est assez récent (None : toujours bon), sinon make() ; l'ancien fichier en cas de panne."""
    path = DIR / name
    old = None
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            old = None
        age = (time.time() - path.stat().st_mtime) / 3600
        if old is not None and (max_age_hours is None or age < max_age_hours):
            return old
    new = make()
    if new is None:
        return old
    DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(new, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return new


def espn_day(t: datetime) -> date:
    """Jour sous lequel ESPN range un match (heure de la côte est des États-Unis, à une heure près)."""
    return (t - timedelta(hours=5)).date()


def _names(team: dict) -> list[str]:
    return [n for n in {team.get("displayName"), team.get("shortDisplayName"), team.get("name"),
                        team.get("location")} if n]


def _slim_event(ev: dict) -> dict | None:
    comp = (ev.get("competitions") or [{}])[0]
    sides = {c.get("homeAway"): c for c in comp.get("competitors") or []}
    if "home" not in sides or "away" not in sides:
        return None
    st = (ev.get("status") or {}).get("type") or {}

    def goals(c):
        try:
            return int(c.get("score"))
        except (TypeError, ValueError):
            return None
    return {"id": str(ev.get("id")), "ko": ev.get("date"), "st": st.get("state"), "sn": st.get("name"),
            "h": _names(sides["home"].get("team") or {}), "a": _names(sides["away"].get("team") or {}),
            "sc": [goals(sides["home"]), goals(sides["away"])]}


def scoreboard(slug: str, day: date, now: datetime | None = None) -> list[dict]:
    """Matchs d'un championnat ESPN pour un jour : [{id, ko, st, sn, h: [noms], a: [noms], sc}]."""
    today = espn_day(_now(now))
    if day < today - timedelta(days=1):
        max_age = 24.0      # jours passés : les matchs ne bougent plus (sauf report)
    elif day <= today:
        max_age = 0.2       # hier et aujourd'hui : redemandé à chaque calcul (scores, matchs finis)
    else:
        max_age = 6.0       # jours à venir : heures et adversaires
    url = API.format(slug=slug, what="scoreboard") + f"?dates={day:%Y%m%d}"

    def make():
        data = _fetch(url)
        if data is None:
            return None
        return [s for s in (_slim_event(e) for e in data.get("events") or []) if s]
    return _cached(f"sb_{slug}_{day:%Y%m%d}.json", max_age, make) or []


def _name_score(ours: str, theirs: list[str]) -> float:
    return max((fixtures._similarity(ours, n) for n in theirs), default=0.0)


def link(items: list[dict], now: datetime | None = None) -> dict[str, list]:
    """Relie nos matchs à ceux d'ESPN. items : [{key, league, kickoff, home, away}] (noms TheSportsDB).
    Renvoie {key: [nom ESPN du championnat, n° ESPN du match, jour ESPN AAAAMMJJ]} pour les matchs retrouvés.
    Les matchs d'un même championnat sont répartis ensemble (affectation optimale) : un match ESPN ne sert qu'une
    fois, et un match sans équivalent sûr (heure trop éloignée, noms trop différents) reste sans lien."""
    by_slug: dict[str, list[tuple[dict, datetime]]] = {}
    for it in items:
        slug = SLUGS.get(it.get("league"))
        if slug:
            by_slug.setdefault(slug, []).append((it, _dt(it["kickoff"])))
    out: dict[str, list] = {}
    for slug, ours in by_slug.items():
        days = sorted({d for _, ko in ours for d in (espn_day(ko), ko.date())})
        events, seen = [], set()
        for d in days:
            for ev in scoreboard(slug, d, now):
                if ev["id"] not in seen and ev.get("ko"):
                    seen.add(ev["id"])
                    events.append((ev, d))
        if not events:
            continue
        cost = np.full((len(ours), len(events)), 10.0)
        ok = np.zeros(cost.shape, dtype=bool)
        for i, (it, ko) in enumerate(ours):
            for j, (ev, _) in enumerate(events):
                gap = abs(_dt(ev["ko"]) - ko)
                if gap > KICKOFF_GAP:
                    continue
                sh, sa = _name_score(it["home"], ev["h"]), _name_score(it["away"], ev["a"])
                same_time = gap <= timedelta(minutes=20)
                score = sh + sa + (0.3 if same_time else 0.0)
                # Les deux noms se ressemblent, ou l'un des deux est sans doute possible à la même heure
                # (« Köln » / « FC Cologne », « Crvena Zvezda » / « Red Star Belgrade »)
                if (sh >= MIN_NAME and sa >= MIN_NAME and score >= MIN_PAIR) or (same_time and max(sh, sa) >= 0.8):
                    cost[i, j], ok[i, j] = -score, True
        rows, cols = linear_sum_assignment(cost)
        for r, c in zip(rows, cols):
            if ok[r, c]:
                ev, d = events[c]
                out[ours[r][0]["key"]] = [slug, ev["id"], espn_day(_dt(ev["ko"])).strftime("%Y%m%d")]
    return out


def in_window(kickoff: str, now: datetime | None = None) -> bool:
    ko, n = _dt(kickoff), _now(now)
    return n + timedelta(days=WINDOW[0]) <= ko <= n + timedelta(days=WINDOW[1])


def _stat(team: dict, name: str) -> float | None:
    for s in team.get("statistics") or []:
        if s.get("name") == name:
            try:
                return float(s.get("displayValue"))
            except (TypeError, ValueError):
                return None
    return None


def _second_yellows(summary: dict, side_of: dict) -> dict[str, int]:
    """Rouges sur deuxième jaune, par équipe : joueur déjà averti dans les temps forts du match."""
    out = {"home": 0, "away": 0}
    booked = set()
    for k in summary.get("keyEvents") or []:
        kind = (k.get("type") or {}).get("type") or ""
        side = side_of.get(str((k.get("team") or {}).get("id")))
        parts = k.get("participants") or []
        who = ((parts[0].get("athlete") or {}).get("displayName")) if parts else None
        if not side or not who:
            continue
        if kind == "yellow-card":
            booked.add((side, who))
        elif kind == "red-card" and (side, who) in booked:
            out[side] += 1
    return out


def box(summary: dict) -> dict:
    """Bilan d'un match ESPN : état, fin normale ou non, corners et cartons comptés comme football-data (les
    données du calcul) : jaunes + rouges, et un rouge sur deuxième jaune vaut 3 (jaune, jaune, rouge) alors
    qu'ESPN n'y compte que le rouge (vérifié sur 140 matchs du 20 au 26/11/2026).
    Les chiffres ne comptent que si ESPN a suivi le match en entier (possession relevée) : certains petits
    championnats n'ont que les cartons, avec des zéros partout ailleurs."""
    comp = (((summary.get("header") or {}).get("competitions")) or [{}])[0]
    st = ((comp.get("status") or {}).get("type")) or {}
    out = {"st": st.get("state"), "sn": st.get("name")}
    teams = {t.get("homeAway"): t for t in ((summary.get("boxscore") or {}).get("teams")) or []}
    if "home" not in teams or "away" not in teams:
        return out
    h, a = teams["home"], teams["away"]
    poss = [_stat(h, "possessionPct"), _stat(a, "possessionPct")]
    out["full"] = all(p is not None and p > 0 for p in poss)
    corners = [_stat(h, "wonCorners"), _stat(a, "wonCorners")]
    yellow = [_stat(h, "yellowCards"), _stat(a, "yellowCards")]
    red = [_stat(h, "redCards"), _stat(a, "redCards")]
    if None not in corners:
        out["corners"] = [int(c) for c in corners]
    if None not in yellow:
        side_of = {str((t.get("team") or {}).get("id")): side for side, t in teams.items()}
        sy = _second_yellows(summary, side_of)
        out["cards"] = [int(y + (r or 0)) + 2 * sy[side] for y, r, side in zip(yellow, red, ("home", "away"))]
    return out


def event_box(slug: str, event_id: str) -> dict | None:
    """Bilan (box) d'un match ESPN, gardé sans limite une fois le match fini, redemandé sinon."""
    name = f"ev_{slug}_{event_id}.json"
    path = DIR / name
    max_age = 0.2
    if path.exists():
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("st") == "post":
                max_age = None
        except ValueError:
            pass
    url = API.format(slug=slug, what="summary") + f"?event={event_id}"

    def make():
        data = _fetch(url)
        return box(data) if data is not None else None
    return _cached(name, max_age, make)


def counts(ref: list) -> dict | None:
    """Corners et cartons d'un match fini après 90 minutes, suivi en entier par ESPN : {corners, cards} ou None
    (pas encore fini, prolongation ou tirs au but, chiffres incomplets, panne)."""
    b = event_box(ref[0], ref[1]) if ref and len(ref) >= 2 else None
    if not b or b.get("st") != "post" or b.get("sn") not in NORMAL_END or not b.get("full"):
        return None
    st = {k: b[k] for k in ("corners", "cards") if k in b}
    return st or None


def finished_badly(ref: list) -> bool:
    """Match fini chez ESPN mais dont les corners et cartons ne serviront pas (prolongation, tirs au but, suivi
    incomplet) : inutile d'attendre."""
    path = DIR / f"ev_{ref[0]}_{ref[1]}.json" if ref and len(ref) >= 2 else None
    if not path or not path.exists():
        return False
    try:
        b = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return b.get("st") == "post" and (b.get("sn") not in NORMAL_END or b.get("full") is False)
