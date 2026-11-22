"""Test du 22/11/2026 : le modèle relié (coupes d'Europe, football féminin, Ligue saoudienne) gagne-t-il à accentuer
l'écart entre équipes, comme le moteur des championnats (t = 1,313, voir engine_params.json) ?

Pour chaque match, on reprend les buts attendus du modèle relié (calcul figé toutes les deux semaines, gardé par
football/elo.py dans data/cache/engine/elo/), puis :
    log buts domicile  = moyenne + t × demi-écart + log s
    log buts extérieur = moyenne − t × demi-écart + log s
t > 1 accentue l'écart entre les deux équipes (favoris plus favoris), s change le total de buts.
t et s sont appris sur une période, jugés sur l'autre, dans les deux sens, puis les deux sens réunis. Règle
d'adoption du moteur : log-loss 1X2 et plus/moins 2,5 au moins aussi bons, borne haute à 95 % ≤ +0,0005.

Usage : python -m probalis.football.relie   (lancer d'abord python -m probalis.football.elo)
"""
from __future__ import annotations

import json
from datetime import date

import numpy as np
from scipy.optimize import minimize

from ..core.implied import implied_rates
from . import tune
from .elo import DIR, TOL

STUDIES = (("coupes", (date(2025, 7, 1), date(2026, 6, 15))),
           ("feminin-championnats", (date(2026, 1, 1), date(2026, 7, 1))),
           ("feminin-ldc", (date(2026, 1, 1), date(2026, 7, 1))),
           ("saoudienne", (date(2026, 1, 1), date(2026, 7, 1))))


def load(name: str, start: date) -> tuple[list[dict], list[dict]]:
    """(première période, seconde période) des matchs prédits par le modèle relié."""
    files = sorted(DIR.glob(f"dc-{name}-*.json"))
    first = [f for f in files if f.name.startswith(f"dc-{name}-{start}")]
    second = [f for f in files if f not in first]
    return (json.loads(first[0].read_text(encoding="utf-8")), json.loads(second[-1].read_text(encoding="utf-8")))


class Rows:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        lm = np.array([implied_rates(r["p"], r["rho"], r["over"]) for r in rows])
        self.l0, self.l1 = np.log(lm[:, 0]), np.log(lm[:, 1])
        self.rho = np.array([r["rho"] for r in rows])
        self.k = np.array([0 if r["hg"] > r["ag"] else (1 if r["hg"] == r["ag"] else 2) for r in rows])
        self.over = np.array([r["hg"] + r["ag"] > 2.5 for r in rows])
        self.dates = np.array([r["d"] for r in rows])
        self.n = len(rows)


def losses(d: Rows, t: float, s: float) -> tuple[np.ndarray, np.ndarray]:
    m, h = (d.l0 + d.l1) / 2, (d.l0 - d.l1) / 2
    p3, over = tune.probs(np.exp(m + t * h + np.log(s)), np.exp(m - t * h + np.log(s)), d.rho)
    l1 = -np.log(np.clip(p3[np.arange(d.n), d.k], 1e-12, None))
    lo = -np.log(np.clip(np.where(d.over, over, 1 - over), 1e-12, None))
    return l1, lo


def fit(d: Rows) -> tuple[float, float]:
    res = minimize(lambda x: float(sum(v.mean() for v in losses(d, x[0], x[1]))), np.array([1.0, 1.0]),
                   method="L-BFGS-B", bounds=[(0.6, 2.0), (0.7, 1.4)])
    return float(res.x[0]), float(res.x[1])


def main() -> None:
    out = []
    for name, (start, _) in STUDIES:
        a, b = load(name, start)
        A, B = Rows(a), Rows(b)
        print(f"\n[{name}] {A.n} + {B.n} matchs")
        d1s, dos, dates = [], [], []
        ts = []
        for tr, te, label in ((A, B, "appris sur l'ancienne période, jugé sur la récente"),
                              (B, A, "appris sur la récente, jugé sur l'ancienne")):
            t, s = fit(tr)
            ts.append((t, s))
            o1, oo = losses(te, 1.0, 1.0)
            n1, no = losses(te, t, s)
            d1s.append(n1 - o1)
            dos.append(no - oo)
            dates.append(te.dates)
            print(f"  {label} : t = {t:.3f}, s = {s:.3f} | 1X2 {o1.mean():.5f} -> {n1.mean():.5f} "
                  f"(borne 95 % {tune.upper95(n1 - o1, te.dates):+.5f}) | plus/moins 2,5 {oo.mean():.5f} -> "
                  f"{no.mean():.5f} (borne 95 % {tune.upper95(no - oo, te.dates):+.5f})")
        d1, do, dd = np.concatenate(d1s), np.concatenate(dos), np.concatenate(dates)
        u1, uo = tune.upper95(d1, dd), tune.upper95(do, dd)
        ok = bool(d1.mean() <= 0 and do.mean() <= 0 and u1 <= TOL and uo <= TOL)
        print(f"  Les deux sens réunis ({len(d1)} matchs) : 1X2 {d1.mean():+.5f} (borne 95 % {u1:+.5f}) | "
              f"plus/moins 2,5 {do.mean():+.5f} (borne 95 % {uo:+.5f})  ->  {'ADOPTÉ' if ok else 'pas adopté'}")
        out.append({"name": name, "t_s": ts, "ecart_1x2": float(d1.mean()), "up95_1x2": u1,
                    "ecart_ou25": float(do.mean()), "up95_ou25": uo, "adopt": ok})
    (DIR / "relie-resultats.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
