"""Forme récente et face-à-face : les derniers matchs joués de chaque équipe, et leurs dernières rencontres.

C'est un simple rappel des résultats pour le lecteur. Ces matchs sont déjà dans le calcul (force des équipes,
forme récente du moteur) : ils ne changent aucune probabilité.

Chaque équipe a une clé unique, la même dans toutes les sources :
  - « pays|nom football-data » pour les clubs des championnats à fichiers football-data.co.uk
    (ex. « england|Arsenal ») : la même clé suit un club promu ou relégué d'une division à l'autre,
    et c'est aussi le nom des clubs dans le modèle des coupes d'Europe ;
  - « t<numéro TheSportsDB> » pour les équipes suivies par TheSportsDB seul (football féminin, Ligue saoudienne,
    clubs européens sans fichier de championnat).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .data import MatchRow
from .leagues import BY_CODE
from .linked import country_key
from .model import Game

N_FORM = 5   # derniers matchs de chaque équipe
N_H2H = 5    # dernières rencontres entre les deux équipes


@dataclass(frozen=True)
class Played:
    date: date
    home: str   # clé d'équipe (voir plus haut)
    away: str
    hg: int
    ag: int
    comp: str = ""  # code de la compétition (E0, UCL…) ou "" si inconnue


def league_country(code: str) -> str | None:
    """Pays d'un championnat à fichiers football-data (« england » pour E0, E1, E2, E3, EC…)."""
    lg = BY_CODE.get(code)
    return country_key(lg.country_en) if lg and lg.category == "domestic" else None


def team_key(m: dict, side: str) -> str | None:
    """Clé d'équipe d'un match du site (side = "home" ou "away")."""
    fd = (m.get(side) or {}).get("fd")
    if not fd:
        return None
    country = league_country(m.get("league", ""))
    return f"{country}|{fd}" if country else fd


class Book:
    """Tous les matchs joués connus, rangés par équipe. Un même match venu de deux sources n'est gardé qu'une fois
    (même jour, mêmes équipes) : la première source ajoutée l'emporte."""

    def __init__(self) -> None:
        self._games: dict[tuple, Played] = {}
        self._by_team: dict[str, list[Played]] = {}
        self.names: dict[str, str] = {}  # clé -> nom affiché (TheSportsDB) quand on le connaît

    def add(self, g: Played) -> None:
        if g.hg is None or g.ag is None or not g.home or not g.away or g.home == g.away:
            return
        k = (g.date, g.home, g.away)
        if k in self._games:
            return
        self._games[k] = g
        for t in (g.home, g.away):
            self._by_team.setdefault(t, []).append(g)

    def add_rows(self, country: str, rows: Iterable[MatchRow]) -> None:
        """Matchs d'un championnat à fichiers football-data."""
        for r in rows:
            if r.played:
                self.add(Played(r.date, f"{country}|{r.home}", f"{country}|{r.away}", r.fthg, r.ftag, r.league))

    def add_games(self, games: Iterable[Game]) -> None:
        """Matchs d'un modèle relié (coupes d'Europe, football féminin, Ligue saoudienne)."""
        for g in games:
            self.add(Played(g.date, g.home, g.away, g.hg, g.ag, g.comp))

    def name(self, key: str) -> str:
        if key in self.names:
            return self.names[key]
        return key.split("|", 1)[1] if "|" in key else key

    def last(self, team: str, before: date, n: int = N_FORM) -> list[Played]:
        """Les n derniers matchs de l'équipe joués avant ce jour, du plus récent au plus ancien."""
        gs = [g for g in self._by_team.get(team, ()) if g.date < before]
        return sorted(gs, key=lambda g: g.date, reverse=True)[:n]

    def meetings(self, a: str, b: str, before: date, n: int = N_H2H) -> list[Played]:
        """Les n dernières rencontres entre les deux équipes avant ce jour, de la plus récente à la plus ancienne."""
        gs = [g for g in self._by_team.get(a, ()) if g.date < before and b in (g.home, g.away)]
        return sorted(gs, key=lambda g: g.date, reverse=True)[:n]


def _result(gf: int, ga: int) -> str:
    return "W" if gf > ga else ("D" if gf == ga else "L")


def form_rows(book: Book, team: str, before: date) -> list[dict]:
    """Forme d'une équipe pour le site : d (jour), o (adversaire), h (1 = à domicile), s (score [dom, ext]),
    r (W, D ou L pour cette équipe), c (compétition)."""
    out = []
    for g in book.last(team, before):
        home = g.home == team
        gf, ga = (g.hg, g.ag) if home else (g.ag, g.hg)
        out.append({"d": g.date.isoformat(), "o": book.name(g.away if home else g.home), "h": int(home),
                    "s": [g.hg, g.ag], "r": _result(gf, ga), "c": g.comp})
    return out


def h2h_rows(book: Book, home: str, away: str, before: date) -> list[dict]:
    """Face-à-face pour le site : d, s (score [dom, ext] de ce match-là), x (1 si l'équipe qui reçoit aujourd'hui
    recevait aussi ce jour-là), w (« home », « away » ou « draw » : vainqueur, vu depuis le match d'aujourd'hui), c."""
    out = []
    for g in book.meetings(home, away, before):
        same = g.home == home
        gh, ga = (g.hg, g.ag) if same else (g.ag, g.hg)  # buts de l'équipe qui reçoit aujourd'hui, puis de l'autre
        out.append({"d": g.date.isoformat(), "s": [g.hg, g.ag], "x": int(same),
                    "w": "home" if gh > ga else ("away" if ga > gh else "draw"), "c": g.comp})
    return out


def attach(matches: list[dict], book: Book) -> int:
    """Ajoute « form » et « h2h » à chaque match du site. Renvoie le nombre de matchs complétés."""
    n = 0
    for m in matches:
        kh, ka = team_key(m, "home"), team_key(m, "away")
        if not (kh and ka):
            continue
        before = date.fromisoformat(m["kickoff"][:10])
        fh, fa = form_rows(book, kh, before), form_rows(book, ka, before)
        if not (fh or fa):
            continue
        m["form"] = {"home": fh, "away": fa}
        m["h2h"] = h2h_rows(book, kh, ka, before)
        n += 1
    return n
