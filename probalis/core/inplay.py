"""Chance en direct d'un pari : score final probable selon le score et la minute (mise à niveau 5, 27/11/2026).

Les buts déjà marqués sont acquis. Ceux qui restent suivent la loi de Poisson de l'analyse d'avant-match (buts
attendus lam, mu), réduite à la part du match qui reste à jouer selon le « profil » des buts minute par minute
(appris par football/endirect.py, enregistré dans site/inplay.json). La correction de Dixon-Coles (rho) des petits
scores s'efface à mesure que le match avance. Même calcul que `InPlay` dans site/static/app.js (vérifié par les
tests sur les mêmes exemples).
"""
from __future__ import annotations

import numpy as np

from .scores import dc_tau, poisson_vector
from .verdicts import _outcome

N = 10  # buts qui peuvent encore être marqués (la dernière case reçoit la queue)


def remaining_share(profile: list[float] | None, played: int) -> float:
    """Part des buts du match qui reste à marquer après `played` minutes (45 : mi-temps, 90 : fin du temps réglementaire)."""
    played = max(0, min(90, int(played)))
    if not profile:
        return (90 - played) / 90
    return float(sum(profile[played:]))


def final_matrix(lam: float, mu: float, h: int, a: int, played: int, profile: list[float] | None,
                 reds: list | tuple = (), red_factors: tuple[float, float] | None = None, rho: float = 0.0,
                 kappa: float | None = None, kmode: str = "total") -> np.ndarray:
    """M[x, y] = P(score final x-y) sachant le score h-a après `played` minutes.

    kappa : les buts déjà marqués renseignent sur le match (un 0-0 à la 60e est souvent un match fermé). Le rythme qui
    reste est multiplié par (kappa + buts marqués) / (kappa + buts attendus jusque-là) : 1 au coup d'envoi, d'autant plus
    corrigé que kappa est petit. kmode « total » (les deux équipes ensemble) ou « team » (chaque équipe à part)."""
    r = remaining_share(profile, played)
    lr, mr = lam * r, mu * r
    if kappa:
        done = 1 - r
        if kmode == "team":
            lr *= (kappa + h) / (kappa + lam * done)
            mr *= (kappa + a) / (kappa + mu * done)
        else:
            f = (kappa + h + a) / (kappa + (lam + mu) * done)
            lr, mr = lr * f, mr * f
    if red_factors:
        own, opp = red_factors
        for side in reds:
            if side == "h":
                lr, mr = lr * own, mr * opp
            elif side == "a":
                lr, mr = lr * opp, mr * own
    rem = np.outer(poisson_vector(lr, N), poisson_vector(mr, N))
    if rho and r > 0:
        g = np.arange(N + 1)
        rem = np.clip(rem * dc_tau(g[:, None], g[None, :], lr, mr, rho * r), 0.0, None)
    rem /= rem.sum()
    out = np.zeros((h + N + 1, a + N + 1))
    out[h:, a:] = rem
    return out


def prob(final: np.ndarray, key: str, line, sel: str) -> float:
    """Chance que la sélection (key, line, sel) soit gagnante, d'après la matrice du score final."""
    H, A = np.indices(final.shape)
    D, T = H - A, H + A
    if key == "1x2":
        mask = {"1": D > 0, "X": D == 0, "2": D < 0}[sel]
    elif key == "dc":
        mask = {"1X": D >= 0, "12": D != 0, "X2": D <= 0}[sel]
    elif key == "ou":
        mask = T > line if sel == "over" else T < line
    elif key == "btts":
        mask = (H > 0) & (A > 0) if sel == "yes" else (H == 0) | (A == 0)
    elif key in ("tt1", "tt2"):
        g = H if key == "tt1" else A
        mask = g > line if sel == "over" else g < line
    else:
        raise KeyError(key)
    return float(final[mask].sum())


def outcome(key: str, line, sel: str, hg: int, ag: int) -> bool:
    return _outcome(key, line, sel, hg, ag)
