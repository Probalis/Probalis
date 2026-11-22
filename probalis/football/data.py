"""Données historiques gratuites de football-data.co.uk (résultats, stats, cotes)."""
from __future__ import annotations

import csv
import io
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache"
SEASON_URL = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
EXTRA_URL = "https://www.football-data.co.uk/new/{code}.csv"
USER_AGENT = "Mozilla/5.0 (compatible; ProbalisBot/0.1)"
FRESH_HOURS = 1.5  # données du jour pas plus vieilles qu'1 h 30 (relances toutes les heures le week-end, toutes les 6 h en semaine)

STAT_COLUMNS = ("HS", "AS", "HST", "AST", "HC", "AC", "HF", "AF", "HY", "AY", "HR", "AR")
NON_ODDS = {"Div", "Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "HTHG", "HTAG", "HTR",
            "Referee", "Attendance", "HxG", "AxG", "AHh", "AHCh", *STAT_COLUMNS, "HHW", "AHW", "HO", "AO", "HBP", "ABP"}


@dataclass
class MatchRow:
    league: str
    date: date
    home: str
    away: str
    fthg: int | None = None
    ftag: int | None = None
    hthg: int | None = None
    htag: int | None = None
    referee: str = ""
    stats: dict[str, float] = field(default_factory=dict)
    odds: dict[str, float] = field(default_factory=dict)
    ah_line: float | None = None
    ah_line_close: float | None = None

    @property
    def played(self) -> bool:
        return self.fthg is not None and self.ftag is not None


def download(url: str, path: Path, max_age_hours: float | None) -> Path:
    """Télécharge avec cache. max_age_hours=None : ne jamais re-télécharger si le fichier existe."""
    if path.exists():
        age_h = (time.time() - path.stat().st_mtime) / 3600
        if max_age_hours is None or age_h < max_age_hours:
            return path
    path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
    except Exception:
        if path.exists():  # hors ligne : on garde l'ancienne version
            return path
        raise
    path.write_bytes(data)
    return path


def _parse_date(s: str) -> date | None:
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _num(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _int(s: str | None) -> int | None:
    v = _num(s)
    return None if v is None else int(v)


def parse_csv(raw: bytes, league: str | None = None) -> list[MatchRow]:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    rows: list[MatchRow] = []
    for r in csv.DictReader(io.StringIO(text)):
        r = {(k or "").strip().lstrip("﻿"): v for k, v in r.items()}
        d = _parse_date(r.get("Date") or "")
        home, away = (r.get("HomeTeam") or "").strip(), (r.get("AwayTeam") or "").strip()
        if not d or not home or not away:
            continue
        stats = {c: v for c in STAT_COLUMNS if (v := _num(r.get(c))) is not None}
        odds = {k: v for k, val in r.items()
                if k and k not in NON_ODDS and isinstance(val, str) and (v := _num(val)) is not None and v > 1.0}
        rows.append(MatchRow(
            league=league or (r.get("Div") or "").strip(), date=d, home=home, away=away,
            fthg=_int(r.get("FTHG")), ftag=_int(r.get("FTAG")),
            hthg=_int(r.get("HTHG")), htag=_int(r.get("HTAG")),
            referee=(r.get("Referee") or "").strip(), stats=stats, odds=odds,
            ah_line=_num(r.get("AHh")), ah_line_close=_num(r.get("AHCh")),
        ))
    return rows


def load_season(code: str, season: str, is_current: bool) -> list[MatchRow]:
    path = CACHE / f"{code}_{season}.csv"
    try:
        download(SEASON_URL.format(season=season, code=code), path, FRESH_HOURS if is_current else None)
    except Exception:
        return []
    return parse_csv(path.read_bytes(), code)


def load_history(code: str, seasons: list[str]) -> list[MatchRow]:
    """Matchs joués de plusieurs saisons (seasons[0] = saison en cours), triés par date."""
    rows: list[MatchRow] = []
    for i, s in enumerate(seasons):
        rows += [m for m in load_season(code, s, is_current=(i == 0)) if m.played]
    rows.sort(key=lambda m: m.date)
    return rows


def load_extra(code: str) -> list[MatchRow]:
    """Autres championnats (Autriche, Suisse, pays nordiques…) : un seul fichier pour toutes les saisons,
    avec les résultats seulement (pas de mi-temps). Sert à relier les pays dans le modèle des coupes d'Europe."""
    path = CACHE / f"new_{code}.csv"
    try:
        download(EXTRA_URL.format(code=code), path, 12)
    except Exception:
        return []
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    rows: list[MatchRow] = []
    for r in csv.DictReader(io.StringIO(text)):
        r = {(k or "").strip().lstrip("﻿"): v for k, v in r.items()}
        d = _parse_date(r.get("Date") or "")
        home, away = (r.get("Home") or "").strip(), (r.get("Away") or "").strip()
        hg, ag = _int(r.get("HG")), _int(r.get("AG"))
        if d and home and away and hg is not None and ag is not None:
            rows.append(MatchRow(league=code, date=d, home=home, away=away, fthg=hg, ftag=ag))
    rows.sort(key=lambda m: m.date)
    return rows


def load_upcoming_odds() -> list[MatchRow]:
    """Matchs à venir avec cotes (fichier mis à jour le vendredi et le mardi)."""
    path = CACHE / "fixtures.csv"
    try:
        download(FIXTURES_URL, path, FRESH_HOURS)
    except Exception:
        return []
    return parse_csv(path.read_bytes())
