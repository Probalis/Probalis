"""L'enjeu change-t-il les résultats ? Fin de saison : rien à jouer, lutte pour le maintien, course aux places.

Usage : python -m probalis.football.enjeu [--train 2425 --test 2526]

Idée testée (porteur du projet, 21/11/2026) : une équipe qui n'a plus rien à jouer en fin de saison lève le pied ;
une équipe qui lutte pour le maintien (ou pour une place européenne, une montée) joue « à fond ».

Méthode, la même que pour le calendrier (football/calendrier.py) et le moteur (football/tune.py) :
1. Classement de chaque championnat recalculé avant chaque match (points des matchs déjà joués de la saison).
2. Dans les LATE dernières journées de chaque équipe, on note :
   - « rien à jouer » : ne peut plus atteindre les places du haut (titre, Europe, montée ou barrages) et ne peut plus
     tomber dans la zone de relégation (ou y est déjà condamnée) ;
   - « maintien » : peut encore finir dans la zone de relégation, ou en sortir ;
   - « course » : peut encore gagner ou perdre une place du haut.
3. Ces indices corrigent les buts attendus. Corrections apprises sur --train, mesurées sur --test (saison jamais vue),
   contre le calcul actuel : moteur seul et calé sur les cotes. Adoption seulement si la borne haute à 95 % de l'écart
   de log-loss est sous 0 (bootstrap par journée).

Limites : places du haut et du bas approchées (formats de la saison 2025/26, barrages compris) ; la Belgique (play-offs
au milieu de la saison) n'est pas testée ; les points retirés par sanction ne sont pas connus.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date

import numpy as np
from scipy.optimize import minimize

from . import tune
from .data import load_season
from .engine import load_params

# (places du haut avec un enjeu : titre, Europe, montée, barrages ; places du bas : relégation et barrage)
ZONES = {"E0": (7, 3), "SP1": (7, 3), "I1": (7, 3), "D1": (7, 3), "F1": (6, 3), "N1": (8, 3), "P1": (5, 3),
         "T1": (5, 4), "E1": (6, 3), "E2": (6, 4), "E3": (7, 2), "EC": (7, 4), "SP2": (6, 4), "F2": (5, 3)}
CODES = tuple(ZONES)
LATE = 8            # dernières journées d'une équipe où l'on regarde l'enjeu
FEATURES = ("rien", "maintien", "course")
NAMES = {"rien": "Plus rien à jouer", "maintien": "Lutte pour le maintien", "course": "Course aux places du haut"}


def standings_flags(code: str, season: str) -> dict[tuple[str, str], dict[str, int]]:
    """(date, équipe) -> indices d'enjeu avant son match ce jour-là."""
    ms = sorted((m for m in load_season(code, season, is_current=False) if m.played), key=lambda m: m.date)
    if not ms:
        return {}
    teams = sorted({m.home for m in ms} | {m.away for m in ms})
    n = len(teams)
    total = 2 * (n - 1)
    top, bottom = ZONES[code]
    pts = {t: 0 for t in teams}
    played = {t: 0 for t in teams}
    out = {}
    by_day = defaultdict(list)
    for m in ms:
        by_day[m.date].append(m)
    for d in sorted(by_day):
        table = sorted(pts.values(), reverse=True)
        p_top, p_top_next = table[top - 1], table[top] if top < n else -1
        safe_line = table[n - bottom - 1]   # dernière place sauvée
        zone_top = table[n - bottom]        # première place de la zone de relégation
        for m in by_day[d]:
            for t in (m.home, m.away):
                rem = total - played[t]
                if rem > LATE or rem <= 0:
                    continue
                p = pts[t]
                can_top = p + 3 * rem >= p_top
                sure_top = p > p_top_next + 3 * rem
                relegated = p + 3 * rem < safe_line
                safe = p > zone_top + 3 * rem
                course = can_top and not sure_top
                maintien = not safe and not relegated
                rien = not can_top and (safe or relegated)
                out[(d.isoformat(), t)] = {"rien": int(rien), "maintien": int(maintien), "course": int(course)}
        for m in by_day[d]:
            played[m.home] += 1
            played[m.away] += 1
            if m.fthg > m.ftag:
                pts[m.home] += 3
            elif m.fthg < m.ftag:
                pts[m.away] += 3
            else:
                pts[m.home] += 1
                pts[m.away] += 1
    return out


def features(rows: list[dict], season: str) -> np.ndarray:
    flags = {code: standings_flags(code, season) for code in {r["lg"] for r in rows}}
    out = np.zeros((len(rows), 2, len(FEATURES)))
    for i, r in enumerate(rows):
        for side, team in ((0, r["h"]), (1, r["a"])):
            f = flags[r["lg"]].get((r["d"], team))
            if f:
                out[i, side] = [f[k] for k in FEATURES]
    return out


VARIANTS = (("Rien à jouer seul, une seule correction de force", ("rien",), False),
            ("Rien à jouer seul, buts marqués et encaissés à part", ("rien",), True),
            ("Rien à jouer et maintien, une seule correction", ("rien", "maintien"), False),
            ("Trois indices, une seule correction", FEATURES, False),
            ("Trois indices, buts marqués et encaissés à part", FEATURES, True))


def expand(th: np.ndarray, keys: tuple[str, ...], separate: bool) -> np.ndarray:
    k, n = len(FEATURES), len(keys)
    full = np.zeros(2 * k)
    for i, key in enumerate(keys):
        j = FEATURES.index(key)
        full[j] = th[i]
        full[k + j] = th[n + i] if separate else -th[i]
    return full


def adjust(l0, l1, X, th):
    k = len(FEATURES)
    att, dfn = th[:k], th[k:]
    return l0 + X[:, 0] @ att + X[:, 1] @ dfn, l1 + X[:, 1] @ att + X[:, 0] @ dfn


def losses(l0, l1, d: tune.Data) -> np.ndarray:
    p3, over = tune.probs(np.exp(l0), np.exp(l1), d.rho)
    ll1 = -np.log(np.clip(p3[np.arange(d.n), d.k], 1e-12, None))
    llo = -np.log(np.clip(np.where(d.over > 0, over, 1 - over), 1e-12, None))
    return ll1 + llo


def base_logs(d: tune.Data, market: bool):
    p = load_params()
    l0, l1 = tune.model_logs(d, p)
    if market:
        mk = d.mk[p.devig]
        l0, l1 = mk[:, 0], mk[:, 1]
    return l0, l1


def fit_adjust(d, X, market, keys, separate):
    l0, l1 = base_logs(d, market)
    n = len(keys) * (2 if separate else 1)
    res = minimize(lambda th: float(losses(*adjust(l0, l1, X, expand(th, keys, separate)), d).mean()),
                   np.zeros(n), method="L-BFGS-B", bounds=[(-0.5, 0.5)] * n, options={"eps": 1e-5})
    return expand(res.x, keys, separate)


def describe(d: tune.Data, X: np.ndarray, market: bool):
    l0, l1 = base_logs(d, market)
    p3, _ = tune.probs(np.exp(l0), np.exp(l1), d.rho)
    s = np.array([r["s"] for r in d.rows], dtype=float)
    out = []
    for j, key in enumerate(FEATURES):
        won = exp_won = goals = exp_goals = conc = exp_conc = 0.0
        n = 0
        for side in (0, 1):
            m = X[:, side, j] > 0
            if not m.any():
                continue
            n += int(m.sum())
            won += (d.k == (0 if side == 0 else 2))[m].sum()
            exp_won += p3[m, 0 if side == 0 else 2].sum()
            goals += s[m, side].sum()
            exp_goals += np.exp(l0 if side == 0 else l1)[m].sum()
            conc += s[m, 1 - side].sum()
            exp_conc += np.exp(l1 if side == 0 else l0)[m].sum()
        if n:
            out.append((key, n, won / n, exp_won / n, goals / n, exp_goals / n, conc / n, exp_conc / n))
    return out


def evaluate(dtr, Xtr, dte, Xte, market, test) -> list[dict]:
    l0, l1 = base_logs(dte, market)
    old = losses(l0, l1, dte)
    k = len(FEATURES)
    res = []
    for vname, keys, separate in VARIANTS:
        th = fit_adjust(dtr, Xtr, market, keys, separate)
        diff = losses(*adjust(l0, l1, Xte, th), dte) - old
        up = tune.upper95(diff, dte.dates)
        corr = ", ".join(f"{key} : marqués {100 * (np.exp(th[FEATURES.index(key)]) - 1):+.1f} % / encaissés "
                         f"{100 * (np.exp(th[k + FEATURES.index(key)]) - 1):+.1f} %" for key in keys)
        print(f"  - {vname} [{corr}]")
        print(f"      test {test} ({dte.n} matchs) : écart de log-loss {diff.mean():+.5f} "
              f"(borne haute à 95 % {up:+.5f}) : {'ADOPTÉ' if up < 0 else 'pas adopté'}")
        res.append({"variant": vname, "diff": float(diff.mean()), "up95": up, "adopt": bool(up < 0)})
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="2425")
    ap.add_argument("--test", default="2526")
    args = ap.parse_args()
    tables = tune.load_tables(list(CODES), [args.train, args.test])
    data = {s: tune.Data(rows) for s, rows in tables.items()}
    X = {s: features(tables[s], s) for s in data}
    for s in data:
        late = (X[s].sum(2) > 0).any(1).sum()
        print(f"{s} : {data[s].n} matchs, dont {late} en fin de saison avec un enjeu noté")

    def pick(season, market):
        d, x = data[season], X[season]
        return (d.subset(d.has_mk), x[d.has_mk]) if market else (d, x)

    for market in (True, False):
        print(f"\n=== {'Calé sur les cotes' if market else 'Moteur seul'} ===")
        for season in data:
            dd, XX = pick(season, market)
            for key, n, won, ew, g, eg, c, ec in describe(dd, XX, market):
                print(f"  {season} | {NAMES[key]} : {n} cas | victoires {100 * won:.1f} % pour {100 * ew:.1f} % "
                      f"annoncés | buts marqués {g:.2f} pour {eg:.2f} | encaissés {c:.2f} pour {ec:.2f}")
        (dtr, Xtr), (dte, Xte) = pick(args.train, market), pick(args.test, market)
        print(f"  Appris sur {args.train} :")
        evaluate(dtr, Xtr, dte, Xte, market, args.test)
        print(f"  Appris sur {args.test}, mesuré sur {args.train} (sens inverse) :")
        evaluate(dte, Xte, dtr, Xtr, market, args.train)


if __name__ == "__main__":
    main()
