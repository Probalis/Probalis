"""Modèle de Dixon-Coles : force d'attaque et de défense de chaque équipe.

- Chaque équipe a une attaque et une défense ; le domicile donne un avantage.
- Les matchs récents comptent plus (pondération exponentielle dans le temps).
- Une pénalité « ridge » évite les estimations extrêmes pour les équipes avec peu de matchs.
- Le paramètre rho corrige les petits scores (0-0, 1-0, 0-1, 1-1), mal décrits par Poisson.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

import numpy as np
from scipy.optimize import minimize, minimize_scalar

from ..core.scores import dc_tau
from .data import MatchRow

DEFAULT_XI = 0.0019      # demi-vie d'environ 1 an
DEFAULT_RIDGE = 2.0
DEFAULT_MAX_DAYS = 3 * 365


@dataclass
class TeamModel:
    teams: list[str]
    intercept: float
    home_adv: float
    attack: np.ndarray
    defence: np.ndarray
    rho: float
    first_half_share: float
    ref_date: date
    n_matches: int
    weight_by_team: dict[str, float]

    def __post_init__(self) -> None:
        self._idx = {t: i for i, t in enumerate(self.teams)}

    def knows(self, team: str) -> bool:
        return team in self._idx

    def rates(self, home: str, away: str) -> tuple[float, float]:
        """Buts attendus (domicile, extérieur)."""
        i, j = self._idx[home], self._idx[away]
        lam = np.exp(self.intercept + self.home_adv + self.attack[i] + self.defence[j])
        mu = np.exp(self.intercept + self.attack[j] + self.defence[i])
        return float(lam), float(mu)

    def ratings(self) -> list[tuple[str, float, float]]:
        """(équipe, attaque, défense) : attaque haute = marque beaucoup ; défense haute = encaisse beaucoup."""
        return [(t, float(self.attack[i]), float(self.defence[i])) for i, t in enumerate(self.teams)]


def fit(matches: list[MatchRow], ref_date: date, xi: float = DEFAULT_XI, ridge: float = DEFAULT_RIDGE,
        max_days: int = DEFAULT_MAX_DAYS, include_ref_day: bool = False,
        target: Callable[[MatchRow], "tuple[float, float] | None"] | None = None) -> TeamModel:
    """include_ref_day=True : les matchs déjà terminés le jour même comptent aussi (site en direct).
    Les tests de fiabilité gardent False, pour ne jamais utiliser le résultat du match qu'on prédit.

    target : ce que le modèle apprend à prévoir à la place des buts (buts mérités, corners, cartons…),
    sous la forme (domicile, extérieur) ; les matchs sans ce chiffre sont ignorés. Dans ce cas, rho
    (correction des petits scores) n'a pas de sens et vaut 0."""
    ms = [m for m in matches if m.played and (m.date <= ref_date if include_ref_day else m.date < ref_date)
          and (ref_date - m.date).days <= max_days]
    goals = ms
    if target is not None:
        pairs = [(m, t) for m in ms if (t := target(m)) is not None]
        ms = [m for m, _ in pairs]
    if len(ms) < 30:
        raise ValueError(f"Pas assez de matchs pour estimer le modèle ({len(ms)}).")
    teams = sorted({m.home for m in ms} | {m.away for m in ms})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    h = np.array([idx[m.home] for m in ms])
    a = np.array([idx[m.away] for m in ms])
    if target is None:
        x = np.array([m.fthg for m in ms], dtype=float)
        y = np.array([m.ftag for m in ms], dtype=float)
    else:
        x = np.array([t[0] for _, t in pairs], dtype=float)
        y = np.array([t[1] for _, t in pairs], dtype=float)
    w = np.exp(-xi * np.array([(ref_date - m.date).days for m in ms], dtype=float))

    def objective(theta: np.ndarray):
        c, g = theta[0], theta[1]
        att, dfn = theta[2:2 + n], theta[2 + n:]
        ll = c + g + att[h] + dfn[a]
        lm = c + att[a] + dfn[h]
        lam, mu = np.exp(ll), np.exp(lm)
        nll = np.sum(w * (lam - x * ll + mu - y * lm)) + ridge * (att @ att + dfn @ dfn)
        rl, rm = w * (lam - x), w * (mu - y)
        grad = np.concatenate([
            [rl.sum() + rm.sum(), rl.sum()],
            np.bincount(h, rl, n) + np.bincount(a, rm, n) + 2 * ridge * att,
            np.bincount(a, rl, n) + np.bincount(h, rm, n) + 2 * ridge * dfn,
        ])
        return nll, grad

    theta0 = np.zeros(2 + 2 * n)
    theta0[0] = np.log(max((x.sum() + y.sum()) / (2 * len(ms)), 0.1))
    res = minimize(objective, theta0, jac=True, method="L-BFGS-B")
    th = res.x
    c, g, att, dfn = th[0], th[1], th[2:2 + n], th[2 + n:]

    lam = np.exp(c + g + att[h] + dfn[a])
    mu = np.exp(c + att[a] + dfn[h])

    def rho_nll(r: float) -> float:
        tau = dc_tau(x, y, lam, mu, r)
        if np.any(tau <= 0):
            return 1e12
        return -float(np.sum(w * np.log(tau)))

    rho = float(minimize_scalar(rho_nll, bounds=(-0.25, 0.25), method="bounded").x) if target is None else 0.0

    ht = [(m.hthg + m.htag, m.fthg + m.ftag) for m in goals if m.hthg is not None and m.htag is not None]
    total = sum(t for _, t in ht)
    share = sum(f for f, _ in ht) / total if total else 0.45

    wbt = {t: 0.0 for t in teams}
    for m, wi in zip(ms, w):
        wbt[m.home] += wi
        wbt[m.away] += wi

    return TeamModel(teams=teams, intercept=float(c), home_adv=float(g), attack=att.copy(), defence=dfn.copy(),
                     rho=rho, first_half_share=float(share), ref_date=ref_date, n_matches=len(ms),
                     weight_by_team=wbt)


# --- Modèle « relié » : plusieurs pays (ou championnats) dans un seul modèle -----------------------------
#
# Force d'une équipe = force moyenne de son groupe (pays, championnat) + écart propre à l'équipe.
# Les matchs de championnat mesurent les écarts entre équipes d'un même groupe ; les matchs de coupe
# d'Europe (clubs de pays différents) mesurent l'écart entre les groupes. Un club dont on ne connaît
# que quelques matchs européens est ramené vers la moyenne de son pays.

@dataclass
class Game:
    date: date
    home: str
    away: str
    hg: int
    ag: int
    kind: str = "dom"        # "dom" : championnat ; "cup" : coupe entre pays
    neutral: bool = False    # terrain neutre (finale)
    comp: str = ""           # code de la compétition (E0, UCL…), pour la forme affichée ; sans effet sur le calcul


@dataclass
class LinkedModel:
    teams: list[str]
    group_of: dict[str, str]
    intercept: float
    home_dom: float
    home_cup: float
    attack: np.ndarray       # force du groupe + écart de l'équipe
    defence: np.ndarray
    group_attack: dict[str, float]
    group_defence: dict[str, float]
    rho: float
    first_half_share: float
    ref_date: date
    n_matches: int
    weight_by_team: dict[str, float]

    def knows(self, team: str) -> bool:
        return team in self.weight_by_team

    def view(self, kind: str = "dom", neutral: bool = False) -> TeamModel:
        """Le modèle vu comme un modèle de championnat ordinaire (pour les prédictions)."""
        home = 0.0 if neutral else (self.home_cup if kind == "cup" else self.home_dom)
        return TeamModel(teams=self.teams, intercept=self.intercept, home_adv=home, attack=self.attack,
                         defence=self.defence, rho=self.rho, first_half_share=self.first_half_share,
                         ref_date=self.ref_date, n_matches=self.n_matches, weight_by_team=self.weight_by_team)


def fit_linked(games: list[Game], group_of: dict[str, str], ref_date: date, xi: float = DEFAULT_XI,
               ridge: float = DEFAULT_RIDGE, group_ridge: float = 0.5, max_days: int = DEFAULT_MAX_DAYS,
               first_half_share: float = 0.45, include_ref_day: bool = False) -> LinkedModel:
    gs = [g for g in games if (g.date <= ref_date if include_ref_day else g.date < ref_date)
          and (ref_date - g.date).days <= max_days]
    if len(gs) < 30:
        raise ValueError(f"Pas assez de matchs pour estimer le modèle ({len(gs)}).")
    teams = sorted({g.home for g in gs} | {g.away for g in gs})
    idx = {t: i for i, t in enumerate(teams)}
    groups = sorted({group_of.get(t, "?") for t in teams})
    gidx = {g: i for i, g in enumerate(groups)}
    n, ng = len(teams), len(groups)
    tg = np.array([gidx[group_of.get(t, "?")] for t in teams])
    h = np.array([idx[g.home] for g in gs])
    a = np.array([idx[g.away] for g in gs])
    gh, ga = tg[h], tg[a]
    x = np.array([g.hg for g in gs], dtype=float)
    y = np.array([g.ag for g in gs], dtype=float)
    w = np.exp(-xi * np.array([(ref_date - g.date).days for g in gs], dtype=float))
    on = np.array([not g.neutral for g in gs])
    cup = np.array([g.kind == "cup" for g in gs])
    hd, hc = (on & ~cup).astype(float), (on & cup).astype(float)

    def unpack(theta):
        c, gd_, gc_ = theta[0], theta[1], theta[2]
        GA, GD = theta[3:3 + ng], theta[3 + ng:3 + 2 * ng]
        ta, td = theta[3 + 2 * ng:3 + 2 * ng + n], theta[3 + 2 * ng + n:]
        return c, gd_, gc_, GA, GD, ta, td

    def objective(theta: np.ndarray):
        c, gd_, gc_, GA, GD, ta, td = unpack(theta)
        ll = c + gd_ * hd + gc_ * hc + GA[gh] + ta[h] + GD[ga] + td[a]
        lm = c + GA[ga] + ta[a] + GD[gh] + td[h]
        lam, mu = np.exp(ll), np.exp(lm)
        nll = (np.sum(w * (lam - x * ll + mu - y * lm)) + ridge * (ta @ ta + td @ td)
               + group_ridge * (GA @ GA + GD @ GD))
        rl, rm = w * (lam - x), w * (mu - y)
        grad = np.concatenate([
            [rl.sum() + rm.sum(), (rl * hd).sum(), (rl * hc).sum()],
            np.bincount(gh, rl, ng) + np.bincount(ga, rm, ng) + 2 * group_ridge * GA,
            np.bincount(ga, rl, ng) + np.bincount(gh, rm, ng) + 2 * group_ridge * GD,
            np.bincount(h, rl, n) + np.bincount(a, rm, n) + 2 * ridge * ta,
            np.bincount(a, rl, n) + np.bincount(h, rm, n) + 2 * ridge * td,
        ])
        return nll, grad

    theta0 = np.zeros(3 + 2 * ng + 2 * n)
    theta0[0] = np.log(max((x.sum() + y.sum()) / (2 * len(gs)), 0.1))
    res = minimize(objective, theta0, jac=True, method="L-BFGS-B", options={"maxiter": 5000})
    c, gd_, gc_, GA, GD, ta, td = unpack(res.x)
    att, dfn = GA[tg] + ta, GD[tg] + td

    lam = np.exp(c + gd_ * hd + gc_ * hc + att[h] + dfn[a])
    mu = np.exp(c + att[a] + dfn[h])

    def rho_nll(r: float) -> float:
        tau = dc_tau(x, y, lam, mu, r)
        if np.any(tau <= 0):
            return 1e12
        return -float(np.sum(w * np.log(tau)))

    rho = float(minimize_scalar(rho_nll, bounds=(-0.25, 0.25), method="bounded").x)
    wbt = {t: 0.0 for t in teams}
    for g, wi in zip(gs, w):
        wbt[g.home] += wi
        wbt[g.away] += wi
    return LinkedModel(teams=teams, group_of={t: group_of.get(t, "?") for t in teams}, intercept=float(c),
                       home_dom=float(gd_), home_cup=float(gc_), attack=att.copy(), defence=dfn.copy(),
                       group_attack={g: float(GA[i]) for i, g in enumerate(groups)},
                       group_defence={g: float(GD[i]) for i, g in enumerate(groups)},
                       rho=rho, first_half_share=first_half_share, ref_date=ref_date, n_matches=len(gs),
                       weight_by_team=wbt)
