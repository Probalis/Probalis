"""Test du 22/11/2026 : un classement Elo, seul ou mélangé au modèle relié, prédit-il mieux les matchs sans cotes ?

Compétitions sans cotes gratuites : coupes d'Europe, football féminin, Ligue saoudienne. Le site les calcule avec le
modèle relié (Dixon-Coles : force du pays + écart du club, voir linked.py). On le compare à :
  - un classement Elo : chaque match fait gagner des points au vainqueur (plus s'il gagne largement), avantage du
    terrain, nouveau club au niveau moyen de son pays ; en coupe d'Europe, le pays entier gagne ou perd aussi des
    points (« Elo à deux étages » : niveau du pays + niveau du club) ;
  - un mélange des deux : 1X2 = w × modèle relié + (1 − w) × Elo, puis buts attendus recalculés pour coller à ce 1X2.
Les réglages (K, terrain, mélange w) sont appris sur une première période, puis jugés sur une période jamais vue.
Comme le reste du moteur, le calcul est figé toutes les deux semaines : il ne connaît que les matchs d'avant.

Règle d'adoption (celle du moteur) : log-loss 1X2 et plus/moins 2,5 au moins aussi bons, borne haute à 95 % de
l'écart ≤ +0,0005 (tirage au sort de journées entières).

Usage : python -m probalis.football.elo          (calcul du modèle relié gardé dans data/cache/engine/elo/)
        python -m probalis.football.elo --force  (tout recalculer)
"""
from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from scipy.optimize import minimize

from ..core.implied import implied_rates
from ..core.scores import score_matrix
from . import tune
from .leagues import LEAGUES
from .linked import WOMEN_MAX_DAYS, WORLD_MAX_DAYS, LinkedData, men_cups_data, tsdb_data
from .model import DEFAULT_MAX_DAYS, Game, fit_linked

STEP = 14
DIR = tune.TABLE_DIR / "elo"
TOL = 0.0005


# --- Modèle relié (celui du site), figé toutes les deux semaines --------------------------------------------

def dc_rows(data: LinkedData, kinds: tuple[str, ...], start: date, end: date, max_days: int) -> list[dict]:
    tests = sorted((g for g in data.games if g.kind in kinds and start <= g.date < end), key=lambda g: g.date)
    rows, t = [], start
    while t < end:
        window = [g for g in tests if t <= g.date < t + timedelta(days=STEP)]
        if window:
            model = fit_linked(data.games, data.group_of, t, max_days=max_days, first_half_share=data.first_half_share)
            for g in window:
                if model.weight_by_team.get(g.home, 0) <= 0 or model.weight_by_team.get(g.away, 0) <= 0:
                    continue
                lam, mu = model.view(g.kind, g.neutral).rates(g.home, g.away)
                m = score_matrix(lam, mu, model.rho)
                H, A = np.indices(m.shape)
                s = m.sum()
                rows.append({"d": g.date.isoformat(), "t": t.isoformat(), "h": g.home, "a": g.away, "k": g.kind,
                             "n": g.neutral, "hg": g.hg, "ag": g.ag, "rho": model.rho,
                             "p": [float(m[H > A].sum() / s), float(m[H == A].sum() / s), float(m[H < A].sum() / s)],
                             "over": float(m[(H + A) > 2.5].sum() / s)})
        t += timedelta(days=STEP)
    return rows


def cached_rows(name: str, data_fn, kinds, start: date, end: date, max_days: int, force: bool) -> list[dict]:
    path = DIR / f"dc-{name}-{start}-{end}.json"
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    rows = dc_rows(data_fn(), kinds, start, end, max_days)
    DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


# --- Elo à deux étages ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class EloParams:
    k: float = 25.0          # points en jeu pour le club
    k_group: float = 10.0    # points en jeu pour le pays (matchs de coupe entre pays seulement)
    home: float = 70.0       # avantage du terrain, en points Elo
    margin: bool = True      # victoire large = plus de points (règle du classement Elo mondial)


def elo_snapshots(games: list[Game], group_of: dict[str, str], cutoffs: list[date], p: EloParams):
    """Classement figé à chaque date (matchs strictement avant) : {date: (club, pays)}."""
    gs = sorted(games, key=lambda g: g.date)
    club: dict[str, float] = {}
    grp: dict[str, float] = defaultdict(float)
    gsum: dict[str, float] = defaultdict(float)
    gcnt: dict[str, int] = defaultdict(int)
    snaps, i = {}, 0
    for t in sorted(set(cutoffs)):
        while i < len(gs) and gs[i].date < t:
            g = gs[i]
            i += 1
            for team in (g.home, g.away):
                if team not in club:
                    k = group_of.get(team, "?")
                    club[team] = gsum[k] / gcnt[k] if gcnt[k] else 0.0  # nouveau club : niveau moyen de son pays
                    gsum[k] += club[team]
                    gcnt[k] += 1
            kh, ka = group_of.get(g.home, "?"), group_of.get(g.away, "?")
            dr = club[g.home] + grp[kh] - club[g.away] - grp[ka] + (0.0 if g.neutral else p.home)
            e = 1.0 / (1.0 + 10 ** (-dr / 400))
            s = 1.0 if g.hg > g.ag else (0.5 if g.hg == g.ag else 0.0)
            gd = abs(g.hg - g.ag)
            mult = 1.0 if not p.margin or gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
            delta = mult * (s - e)
            club[g.home] += p.k * delta
            club[g.away] -= p.k * delta
            gsum[kh] += p.k * delta
            gsum[ka] -= p.k * delta
            if g.kind == "cup" and kh != ka:
                grp[kh] += p.k_group * delta
                grp[ka] -= p.k_group * delta
        snaps[t] = (dict(club), dict(grp))
    return snaps


def elo_diffs(rows: list[dict], snaps, group_of: dict[str, str], p: EloParams) -> np.ndarray:
    """Écart Elo de chaque match (domicile − extérieur + terrain), en centaines de points."""
    out = []
    for r in rows:
        club, grp = snaps[date.fromisoformat(r["t"])]
        h = club.get(r["h"], 0.0) + grp.get(group_of.get(r["h"], "?"), 0.0)
        a = club.get(r["a"], 0.0) + grp.get(group_of.get(r["a"], "?"), 0.0)
        out.append((h - a + (0.0 if r["n"] else p.home)) / 100)
    return np.array(out)


def elo_probs(x: np.ndarray, th: np.ndarray) -> np.ndarray:
    """1X2 à partir de l'écart Elo (logit ordonné) : P(1) = σ(a·x − c), P(2) = σ(−a·x − c)."""
    a, c = th[0], abs(th[1])
    p1 = 1 / (1 + np.exp(-(a * x - c)))
    p2 = 1 / (1 + np.exp(-(-a * x - c)))
    p = np.stack([p1, np.clip(1 - p1 - p2, 1e-6, 1), p2], 1)
    return p / p.sum(1, keepdims=True)


def outcomes(rows: list[dict]) -> np.ndarray:
    return np.array([0 if r["hg"] > r["ag"] else (1 if r["hg"] == r["ag"] else 2) for r in rows])


def ll(p: np.ndarray, k: np.ndarray) -> np.ndarray:
    return -np.log(np.maximum(p[np.arange(len(k)), k], 1e-12))


def fit_link(x: np.ndarray, k: np.ndarray) -> np.ndarray:
    return minimize(lambda th: ll(elo_probs(x, th), k).mean(), np.array([0.4, 0.5]), method="Nelder-Mead").x


# --- Mélange et mesure -----------------------------------------------------------------------------------------

def over_after_blend(rows: list[dict], p: np.ndarray) -> np.ndarray:
    """Plus de 2,5 buts une fois les buts attendus recalculés pour coller au 1X2 mélangé (comme avec des cotes)."""
    out = []
    for r, pi in zip(rows, p):
        lam, mu = implied_rates(list(pi), r["rho"], r["over"])
        m = score_matrix(lam, mu, r["rho"])
        H, A = np.indices(m.shape)
        out.append(float(m[(H + A) > 2.5].sum() / m.sum()))
    return np.array(out)


def ou_ll(over: np.ndarray, rows: list[dict]) -> np.ndarray:
    y = np.array([r["hg"] + r["ag"] > 2.5 for r in rows])
    o = np.clip(over, 1e-6, 1 - 1e-6)
    return -np.where(y, np.log(o), np.log(1 - o))


def judge(data: LinkedData, cut: list[date], tr: list[dict], te: list[dict]) -> dict:
    """Réglages Elo et part du mélange appris sur tr, jugés sur te (jamais vu pendant l'apprentissage)."""
    ktr, kte = outcomes(tr), outcomes(te)
    ptr_dc = np.array([r["p"] for r in tr])
    pte_dc = np.array([r["p"] for r in te])

    # 1. Réglages Elo
    best = None
    for k, kg, home in itertools.product((15, 25, 40), (0, 10, 25), (50, 80)):
        p = EloParams(k, kg, home)
        snaps = elo_snapshots(data.games, data.group_of, cut, p)
        x = elo_diffs(tr, snaps, data.group_of, p)
        th = fit_link(x, ktr)
        score = ll(elo_probs(x, th), ktr).mean()
        if best is None or score < best[0]:
            best = (score, p, th, snaps)
    _, p, th, snaps = best
    xtr, xte = elo_diffs(tr, snaps, data.group_of, p), elo_diffs(te, snaps, data.group_of, p)
    ptr_elo, pte_elo = elo_probs(xtr, th), elo_probs(xte, th)

    # 2. Part du modèle relié dans le mélange, apprise sur la première période
    ws = np.round(np.arange(0, 1.0001, 0.05), 2)
    w = float(min(ws, key=lambda w: ll(w * ptr_dc + (1 - w) * ptr_elo, ktr).mean()))

    # 3. Jugement sur la période jamais vue
    pte_mix = w * pte_dc + (1 - w) * pte_elo
    l_dc, l_elo, l_mix = ll(pte_dc, kte), ll(pte_elo, kte), ll(pte_mix, kte)
    dates = np.array([r["d"] for r in te])
    o_dc = ou_ll(np.array([r["over"] for r in te]), te)
    o_mix = ou_ll(over_after_blend(te, pte_mix), te) if w < 1 else o_dc
    res = {
        "n_train": len(tr), "n_test": len(te), "elo": {"k": p.k, "k_group": p.k_group, "home": p.home,
                                                      "a": round(float(th[0]), 4), "c": round(abs(float(th[1])), 4)},
        "w_model": w,
        "test_1x2": {"modele": round(float(l_dc.mean()), 5), "elo": round(float(l_elo.mean()), 5),
                     "melange": round(float(l_mix.mean()), 5),
                     "up95_melange": round(tune.upper95(l_mix - l_dc, dates), 5),
                     "up95_elo": round(tune.upper95(l_elo - l_dc, dates), 5)},
        "test_ou25": {"modele": round(float(o_dc.mean()), 5), "melange": round(float(o_mix.mean()), 5),
                      "up95_melange": round(tune.upper95(o_mix - o_dc, dates), 5)},
        "hit": {"modele": round(float((pte_dc.argmax(1) == kte).mean()), 4),
                "elo": round(float((pte_elo.argmax(1) == kte).mean()), 4),
                "melange": round(float((pte_mix.argmax(1) == kte).mean()), 4)},
    }
    t1, to = res["test_1x2"], res["test_ou25"]
    res["adopt"] = bool(w < 1 and t1["melange"] <= t1["modele"] and t1["up95_melange"] <= TOL
                        and to["melange"] <= to["modele"] + 1e-9 and to["up95_melange"] <= TOL)
    res["_d1"], res["_do"], res["_dates"] = l_mix - l_dc, o_mix - o_dc, dates  # écarts match par match
    return res


def study(name: str, data_fn, kinds, train: tuple[date, date], test: tuple[date, date], max_days: int,
          force: bool) -> dict:
    """Appris sur train, jugé sur test ; puis l'inverse (appris sur test, jugé sur train), pour vérifier."""
    tr = cached_rows(name, data_fn, kinds, *train, max_days, force)
    te = cached_rows(name, data_fn, kinds, *test, max_days, force)
    data = data_fn()
    cut = sorted({date.fromisoformat(r["t"]) for r in tr + te})
    res = {"name": name, "train": [str(d) for d in train], "test": [str(d) for d in test],
           **judge(data, cut, tr, te)}
    res["inverse"] = judge(data, cut, te, tr)
    # Les deux sens réunis (validation croisée) : chaque match est prédit par des réglages appris sans lui.
    inv = res["inverse"]
    d1 = np.concatenate([res["_d1"], inv["_d1"]])
    do = np.concatenate([res["_do"], inv["_do"]])
    dates = np.concatenate([res["_dates"], inv["_dates"]])
    res["croise"] = {"n": int(len(d1)), "ecart_1x2": round(float(d1.mean()), 5),
                     "up95_1x2": round(tune.upper95(d1, dates), 5), "ecart_ou25": round(float(do.mean()), 5),
                     "up95_ou25": round(tune.upper95(do, dates), 5)}
    c = res["croise"]
    res["adopt_croise"] = bool(res["w_model"] < 1 and inv["w_model"] < 1 and c["ecart_1x2"] <= 0
                               and c["up95_1x2"] <= TOL and c["ecart_ou25"] <= 0 and c["up95_ou25"] <= TOL)
    return res


def show(r: dict) -> None:
    t1, to = r["test_1x2"], r["test_ou25"]
    print(f"  Elo retenu : K={r['elo']['k']}, pays K={r['elo']['k_group']}, terrain {r['elo']['home']} ; "
          f"part du modèle relié dans le mélange : {r['w_model']:.2f}")
    print(f"  1X2 log-loss : modèle relié {t1['modele']:.5f} | Elo seul {t1['elo']:.5f} (borne 95 % "
          f"{t1['up95_elo']:+.5f}) | mélange {t1['melange']:.5f} (borne 95 % {t1['up95_melange']:+.5f})")
    print(f"  Plus/moins 2,5 : modèle relié {to['modele']:.5f} | mélange {to['melange']:.5f} "
          f"(borne 95 % {to['up95_melange']:+.5f})")
    print(f"  Bon pronostic : modèle {r['hit']['modele']:.1%} | Elo {r['hit']['elo']:.1%} | "
          f"mélange {r['hit']['melange']:.1%}  ->  {'ADOPTÉ' if r['adopt'] else 'pas adopté'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    today = date.today()
    cups = [lg for lg in LEAGUES if lg.category == "europe"]
    women = [lg for lg in LEAGUES if lg.category == "women"]
    world = [lg for lg in LEAGUES if lg.category == "world"]
    memo: dict[str, LinkedData] = {}

    def once(key, fn):
        def get():
            if key not in memo:
                memo[key] = fn()
            return memo[key]
        return get

    studies = [
        ("coupes", once("coupes", lambda: men_cups_data(cups, today)), ("cup",),
         (date(2025, 7, 1), date(2026, 6, 15)), (date(2026, 7, 1), today), DEFAULT_MAX_DAYS),
        ("feminin-championnats", once("women", lambda: tsdb_data(women, today)), ("dom",),
         (date(2026, 1, 1), date(2026, 7, 1)), (date(2026, 8, 1), today), WOMEN_MAX_DAYS),
        ("feminin-ldc", once("women", lambda: tsdb_data(women, today)), ("cup",),
         (date(2026, 1, 1), date(2026, 7, 1)), (date(2026, 8, 1), today), WOMEN_MAX_DAYS),
        ("saoudienne", once("world", lambda: tsdb_data(world, today)), ("dom",),
         (date(2026, 1, 1), date(2026, 7, 1)), (date(2026, 8, 1), today), WORLD_MAX_DAYS),
    ]
    out = []
    for name, fn, kinds, train, test, md in studies:
        try:
            r = study(name, fn, kinds, train, test, md, args.force)
        except Exception as e:  # pas assez de matchs, source en panne…
            print(f"[{name}] impossible : {type(e).__name__}: {e}")
            continue
        out.append(r)
        print(f"\n[{name}] appris sur {r['n_train']} matchs ({r['train'][0]} → {r['train'][1]}), "
              f"jugé sur {r['n_test']} matchs jamais vus ({r['test'][0]} → {r['test'][1]})")
        show(r)
        print("  Sens inverse (appris sur la période récente, jugé sur l'ancienne) :")
        show(r["inverse"])
        c = r["croise"]
        print(f"  Les deux sens réunis ({c['n']} matchs) : 1X2 {c['ecart_1x2']:+.5f} (borne 95 % {c['up95_1x2']:+.5f})"
              f" | plus/moins 2,5 {c['ecart_ou25']:+.5f} (borne 95 % {c['up95_ou25']:+.5f})  ->  "
              f"{'ADOPTÉ' if r['adopt_croise'] else 'pas adopté'}")
    DIR.mkdir(parents=True, exist_ok=True)
    def clean(x):
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items() if not k.startswith("_")}
        return x
    (DIR / "resultats.json").write_text(json.dumps([clean(r) for r in out], ensure_ascii=False, indent=1),
                                        encoding="utf-8")


if __name__ == "__main__":
    main()
