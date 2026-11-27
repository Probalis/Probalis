"""Apprentissage et test du moteur (football/engine.py) sur des saisons passées.

1. On rejoue chaque saison semaine par semaine : les modèles n'apprennent que sur les matchs d'avant, puis
   on note pour chaque match les buts attendus de chaque indice, les cotes d'avant-match et le résultat
   (tableau mis en cache dans data/cache/engine/).
2. Sur la saison d'apprentissage (--train), on cherche les poids qui donnent les meilleures probabilités
   (log-loss du 1X2 et du plus/moins 2,5 buts).
3. Sur la saison de test (--test), jamais vue pendant l'apprentissage, on compare l'ancien moteur et le
   nouveau, avec et sans les cotes. Le nouveau n'est adopté que s'il est au moins aussi précis partout.
4. Avec --write, on enregistre les réglages et le tableau de fiabilité des verdicts dans engine_params.json.

Usage : python -m probalis.football.tune --train 2425 --test 2526 [--write] [--jobs 6]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace

import numpy as np
from scipy.optimize import minimize, minimize_scalar
from scipy.special import gammaln
from scipy.stats import poisson

from ..core import verdicts as vd
from ..core.implied import implied_rates
from ..core.value import DEVIG, devig_by
from . import signals
from .backtest import _in_season, _odds, _prev_season
from .data import CACHE, load_history
from .engine import PARAMS_PATH, EngineParams, add_counts, load_params, transform
from .leagues import LEAGUES
from .model import fit
from .predict import predict_from_rates

TABLE_DIR = CACHE / "engine"
TABLE_VERSION = 2
XI_FORM = 0.008
PRE_1X2 = (("AvgH", "AvgD", "AvgA"), ("B365H", "B365D", "B365A"))
PRE_OU = (("Avg>2.5", "Avg<2.5"), ("B365>2.5", "B365<2.5"))
G = 11  # 0..10 buts


def _seasons(season: str) -> list[str]:
    out = [season]
    for _ in range(3):
        out.append(_prev_season(out[-1]))
    return out


def _try_fit(*a, **kw):
    try:
        return fit(*a, **kw)
    except ValueError:
        return None


def _pair(m, h, a):
    if m is None or not (m.knows(h) and m.knows(a)):
        return None
    lam, mu = m.rates(h, a)
    return [round(lam, 5), round(mu, 5)]


def _base(m):
    return None if m is None else [round(math.exp(m.intercept + m.home_adv), 5), round(math.exp(m.intercept), 5)]


# --- 1. Tableau « semaine par semaine » ------------------------------------------------------------------

def build_table(code: str, season: str, force: bool = False) -> list[dict]:
    path = TABLE_DIR / f"wf{TABLE_VERSION}-{season}-{code}.json"
    if path.exists() and not force:
        return json.loads(path.read_text(encoding="utf-8"))
    hist = load_history(code, _seasons(season))
    test = sorted((m for m in hist if _in_season(m, season)), key=lambda m: m.date)
    rows: list[dict] = []
    if test:
        corners_ok = signals.has_stat(test, signals.corners)
        cards_ok = signals.has_stat(test, signals.cards)
        week = test[0].date + timedelta(days=21)
        while week <= test[-1].date:
            batch = [m for m in test if week <= m.date < week + timedelta(days=7)]
            if batch:
                past = [m for m in hist if m.date < week]
                recent = [m for m in past if (week - m.date).days <= 365]
                g = fit(hist, week)
                xt = signals.xg_target(past) if signals.has_shots(recent) else None
                x = _try_fit(hist, week, target=xt) if xt else None
                fg = _try_fit(hist, week, xi=XI_FORM)
                fx = _try_fit(hist, week, xi=XI_FORM, target=xt) if xt else None
                co = _try_fit(hist, week, target=signals.corners) if corners_ok else None
                ca = _try_fit(hist, week, target=signals.cards) if cards_ok else None
                for m in batch:
                    if not (g.knows(m.home) and g.knows(m.away)) or m.fthg is None:
                        continue
                    gr = _pair(g, m.home, m.away)
                    r = {"lg": code, "d": m.date.isoformat(), "h": m.home, "a": m.away, "s": [m.fthg, m.ftag],
                         "rho": round(g.rho, 5), "fhs": round(g.first_half_share, 5), "g": gr,
                         "x": _pair(x, m.home, m.away), "fg": _pair(fg, m.home, m.away),
                         "fx": _pair(fx, m.home, m.away), "co": _pair(co, m.home, m.away),
                         "ca": _pair(ca, m.home, m.away), "co0": _base(co), "ca0": _base(ca),
                         "wmin": round(min(g.weight_by_team.get(m.home, 0), g.weight_by_team.get(m.away, 0)), 2),
                         "coA": list(signals.corners(m) or []) or None, "caA": list(signals.cards(m) or []) or None}
                    o12, oou = _odds(m, PRE_1X2), _odds(m, PRE_OU)
                    if o12:
                        r["o12"], r["oou"] = o12, oou
                        r["mk"] = {}
                        for meth in DEVIG:
                            p_over = devig_by(meth, oou)[0] if oou else None
                            lam, mu = implied_rates(devig_by(meth, o12), g.rho, p_over, start=tuple(gr))
                            r["mk"][meth] = [round(lam, 5), round(mu, 5)]
                    rows.append(r)
            week += timedelta(days=7)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    return rows


def _job(args) -> tuple[str, str, int]:
    code, season, force = args
    return code, season, len(build_table(code, season, force))


def load_tables(codes: list[str], seasons: list[str], jobs: int = 1, force: bool = False) -> dict[str, list[dict]]:
    todo = [(c, s, force) for s in seasons for c in codes]
    if jobs > 1:
        with ProcessPoolExecutor(jobs) as ex:
            for code, season, n in ex.map(_job, todo):
                print(f"  {season} {code}: {n} matchs", flush=True)
    else:
        for t in todo:
            code, season, n = _job(t)
            print(f"  {season} {code}: {n} matchs", flush=True)
    return {s: [r for c in codes for r in build_table(c, s)] for s in seasons}


# --- 2. Probabilités en série (rapide) -------------------------------------------------------------------

def _pois(rate: np.ndarray) -> np.ndarray:
    k = np.arange(G)
    p = poisson.pmf(k[None, :], rate[:, None])
    p[:, -1] += np.clip(1 - p.sum(1), 0, None)
    return p


def probs(lam: np.ndarray, mu: np.ndarray, rho: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(N×3 probabilités 1/N/2, N probabilités de plus de 2,5 buts), comme core/scores.score_matrix."""
    m = _pois(lam)[:, :, None] * _pois(mu)[:, None, :]
    m[:, 0, 0] *= 1 - lam * mu * rho
    m[:, 0, 1] *= 1 + lam * rho
    m[:, 1, 0] *= 1 + mu * rho
    m[:, 1, 1] *= 1 - rho
    m = np.clip(m, 0, None)
    m /= m.sum((1, 2), keepdims=True)
    H, A = np.indices((G, G))
    p1 = m[:, H > A].sum(1)
    px = m[:, H == A].sum(1)
    p2 = m[:, H < A].sum(1)
    over = m[:, (H + A) > 2.5].sum(1)
    return np.stack([p1, px, p2], 1), over


class Data:
    """Colonnes du tableau en tableaux numpy."""

    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.n = len(rows)
        g = np.array([r["g"] for r in rows], dtype=float)
        self.g = np.log(g)
        self.x = np.log(np.array([r["x"] or r["g"] for r in rows], dtype=float))
        self.fg = np.log(np.array([r["fg"] or r["g"] for r in rows], dtype=float))
        self.fx = np.log(np.array([r["fx"] or r["fg"] or r["g"] for r in rows], dtype=float))
        self.rho = np.array([r["rho"] for r in rows])
        s = np.array([r["s"] for r in rows])
        self.k = np.where(s[:, 0] > s[:, 1], 0, np.where(s[:, 0] == s[:, 1], 1, 2))
        self.over = (s.sum(1) > 2.5).astype(float)
        self.has_mk = np.array(["mk" in r for r in rows])
        self.mk = {meth: np.log(np.array([r["mk"][meth] if "mk" in r else r["g"] for r in rows], dtype=float))
                   for meth in DEVIG}
        self.dates = np.array([r["d"] for r in rows])

    def subset(self, mask: np.ndarray) -> "Data":
        return Data([r for r, k in zip(self.rows, mask) if k])


def model_logs(d: Data, p: EngineParams) -> tuple[np.ndarray, np.ndarray]:
    f = d.fx if p.form_target == "xg" else d.fg
    l = d.g + p.w_xg * (d.x - d.g) + p.w_form * (f - d.g)
    a = (l[:, 0] + l[:, 1]) / 2 + math.log(p.s)
    df = (l[:, 0] - l[:, 1]) / 2 * p.t
    return a + df, a - df


def rates(d: Data, p: EngineParams, market: bool) -> tuple[np.ndarray, np.ndarray]:
    l0, l1 = model_logs(d, p)
    if market:
        mk = d.mk[p.devig]
        l0 = np.where(d.has_mk, p.w_mkt * mk[:, 0] + (1 - p.w_mkt) * l0, l0)
        l1 = np.where(d.has_mk, p.w_mkt * mk[:, 1] + (1 - p.w_mkt) * l1, l1)
    return np.exp(l0), np.exp(l1)


def row_losses(d: Data, p: EngineParams, market: bool) -> tuple[np.ndarray, np.ndarray]:
    lam, mu = rates(d, p, market)
    p3, over = probs(lam, mu, d.rho)
    ll1 = -np.log(np.clip(p3[np.arange(d.n), d.k], 1e-12, None))
    llo = -np.log(np.clip(np.where(d.over > 0, over, 1 - over), 1e-12, None))
    return ll1, llo


def brier(d: Data, p: EngineParams, market: bool) -> tuple[float, float]:
    lam, mu = rates(d, p, market)
    p3, over = probs(lam, mu, d.rho)
    e = np.zeros_like(p3)
    e[np.arange(d.n), d.k] = 1
    return float(((p3 - e) ** 2).sum(1).mean()), float(((over - d.over) ** 2).mean())


# --- 3. Apprentissage -----------------------------------------------------------------------------------

def fit_model_params(d: Data, base: EngineParams) -> EngineParams:
    best = None
    for form_target in ("goals", "xg"):
        def obj(th):
            p = replace(base, w_xg=th[0], w_form=th[1], t=th[2], s=th[3], form_target=form_target)
            ll1, llo = row_losses(d, p, market=False)
            return float(ll1.mean() + llo.mean())
        res = minimize(obj, np.array([0.3, 0.2, 1.0, 1.0]), method="L-BFGS-B",
                       bounds=[(0, 1), (0, 1), (0.7, 2.0), (0.85, 1.15)], options={"eps": 1e-4})
        if best is None or res.fun < best[0]:
            best = (res.fun, form_target, res.x)
    _, ft, th = best
    return replace(base, w_xg=round(float(th[0]), 3), w_form=round(float(th[1]), 3), t=round(float(th[2]), 3),
                   s=round(float(th[3]), 3), form_target=ft)


def fit_market_params(d: Data, p: EngineParams) -> EngineParams:
    dm = d.subset(d.has_mk)
    best = None
    for meth in DEVIG:
        def obj(w):
            ll1, llo = row_losses(dm, replace(p, devig=meth, w_mkt=float(w)), market=True)
            return float(ll1.mean() + llo.mean())
        res = minimize_scalar(obj, bounds=(0.0, 1.0), method="bounded")
        if best is None or res.fun < best[0]:
            best = (res.fun, meth, res.x)
    return replace(p, devig=best[1], w_mkt=round(float(best[2]), 3))


def _count_arrays(rows: list[dict], key: str):
    """(chiffres attendus, moyenne du championnat, chiffres réels), une ligne par équipe et par match."""
    rows = [r for r in rows if r.get(key) and r.get(key + "0") and r.get(key + "A")]
    rate = np.array([v for r in rows for v in r[key]], dtype=float)
    base = np.array([v for r in rows for v in r[key + "0"]], dtype=float)
    obs = np.array([v for r in rows for v in r[key + "A"]], dtype=float)
    return rate, base, obs


def nb_fit(rows: list[dict], key: str) -> tuple[float, float] | None:
    """Prudence (k) et dispersion (loi binomiale négative) qui expliquent le mieux les chiffres réels."""
    rate, base, obs = _count_arrays(rows, key)
    if not len(obs):
        return None

    def nll(th) -> float:
        k, r = th[0], math.exp(th[1])
        mean = np.exp(np.log(base) + k * (np.log(rate) - np.log(base)))
        return -float(np.sum(gammaln(obs + r) - gammaln(r) - gammaln(obs + 1)
                             + r * np.log(r / (r + mean)) + obs * np.log(mean / (r + mean))))

    res = minimize(nll, np.array([0.5, math.log(20.0)]), method="L-BFGS-B",
                   bounds=[(0.0, 1.0), (math.log(1.0), math.log(5000.0))])
    return round(float(res.x[0]), 3), round(math.exp(res.x[1]), 2)


# --- 4. Test et fiabilité -------------------------------------------------------------------------------

def upper95(diff: np.ndarray, dates: np.ndarray, n_boot: int = 2000, seed: int = 7) -> float:
    """Borne haute à 95 % de la différence moyenne, en tirant au sort des journées entières."""
    days = defaultdict(list)
    for v, dt in zip(diff, dates):
        days[dt].append(v)
    keys = list(days)
    sums = np.array([sum(days[k]) for k in keys])
    cnts = np.array([len(days[k]) for k in keys])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(keys), size=(n_boot, len(keys)))
    means = sums[idx].sum(1) / cnts[idx].sum(1)
    return float(np.quantile(means, 0.95))


def compare(d: Data, old: EngineParams, new: EngineParams) -> dict:
    out = {}
    for path, market, dd in (("model", False, d), ("market", True, d.subset(d.has_mk))):
        if dd.n == 0:
            continue
        o1, oo = row_losses(dd, old, market)
        n1, no = row_losses(dd, new, market)
        bo, bn = brier(dd, old, market), brier(dd, new, market)
        out[path] = {"n": dd.n,
                     "1x2": {"old": round(float(o1.mean()), 5), "new": round(float(n1.mean()), 5),
                             "up95": round(upper95(n1 - o1, dd.dates), 5),
                             "brier_old": round(bo[0], 5), "brier_new": round(bn[0], 5)},
                     "ou25": {"old": round(float(oo.mean()), 5), "new": round(float(no.mean()), 5),
                              "up95": round(upper95(no - oo, dd.dates), 5),
                              "brier_old": round(bo[1], 5), "brier_new": round(bn[1], 5)}}
    return out


def passes(cmp: dict, tol: float = 0.0005) -> dict[str, bool]:
    return {path: all(v[mk]["new"] <= v[mk]["old"] and v[mk]["up95"] <= tol for mk in ("1x2", "ou25"))
            for path, v in cmp.items()}


def _stub(r: dict):
    return SimpleNamespace(rho=r["rho"], first_half_share=r["fhs"])


def predictions(d: Data, p: EngineParams, market: bool) -> list[tuple[dict, list[dict]]]:
    """Les marchés publiés de chaque match (comme sur le site), avec corners et cartons si possible."""
    lam, mu = rates(d, p, market)
    out = []
    for r, l, m in zip(d.rows, lam, mu):
        pred = predict_from_rates(_stub(r), r["h"], r["a"], float(l), float(m))
        known = {k: (tuple(r[k2]), tuple(r[k2 + "0"])) for k, k2 in (("corners", "co"), ("cards", "ca"))
                 if r.get(k2) and r.get(k2 + "0")}
        add_counts(pred, None, None, r["h"], r["a"], p, rates=known)
        out.append((r, [mk.to_dict() for mk in pred.markets]))
    return out


def reliability(d: Data, p: EngineParams) -> dict:
    """Pour chaque famille de verdicts et chaque tranche de 5 points : combien, combien de réussis, annoncé."""
    table: dict = defaultdict(lambda: defaultdict(lambda: [0, 0, 0.0]))
    best = [0, 0, 0.0]
    pk = [0, 0, 0.0, 0.0]  # paris du match (vd.picks) : nombre, réussis, chance annoncée, cote estimée (sommes)
    for r, markets in predictions(d, p, market=True):
        stats = {"corners": r.get("coA"), "cards": r.get("caA")}
        vs = vd.verdicts(markets)
        for v in vs:
            res = vd.settle(v, r["s"][0], r["s"][1], stats)
            if res not in ("won", "lost"):
                continue
            cell = table[v["fam"]][str(vd.band(v["p"]))]
            cell[0] += 1
            cell[1] += res == "won"
            cell[2] += v["p"]
        for i in vd.picks(vs):
            res = vd.settle(vs[i], r["s"][0], r["s"][1], stats)
            if res in ("won", "lost"):
                pk[0] += 1
                pk[1] += res == "won"
                pk[2] += vs[i]["p"]
                pk[3] += vd.book_odds(vs[i]["p"])
        b = vd.best(vs, {})
        if b:
            res = vd.settle(b, r["s"][0], r["s"][1], stats)
            if res in ("won", "lost"):
                best[0] += 1
                best[1] += res == "won"
                best[2] += b["p"]
    out = {fam: {bd: [c[0], c[1], round(c[2], 3)] for bd, c in sorted(cells.items())}
           for fam, cells in sorted(table.items())}
    out["_best"] = [best[0], best[1], round(best[2], 3)]
    out["_picks"] = [pk[0], pk[1], round(pk[2], 3), round(pk[3], 3)]
    return out


def count_check(d: Data, p: EngineParams) -> dict:
    """Corners et cartons : le moteur fait-il mieux que la moyenne du championnat (connue avant le match) ?
    Log-loss des lignes classiques."""
    out = {}
    from ..core.counts import count_pmf
    from .engine import shrink
    for key, actual, lines, size, k in (("co", "coA", (8.5, 9.5, 10.5), p.corners_size, p.corners_shrink),
                                        ("ca", "caA", (3.5, 4.5), p.cards_size, p.cards_shrink)):
        rows = [r for r in d.rows if r.get(key) and r.get(key + "0") and r.get(actual)]
        if not rows or size is None:
            continue
        res = {}
        for line in lines:
            llm = llb = 0.0
            for r in rows:
                tot = r[actual][0] + r[actual][1]
                for kind, (mh, ma) in (("m", shrink(tuple(r[key]), tuple(r[key + "0"]), k)),
                                       ("b", tuple(r[key + "0"]))):
                    ph, pa = count_pmf(mh, size, 30), count_pmf(ma, size, 30)
                    conv = np.convolve(ph, pa)
                    po = float(conv[int(line) + 1:].sum())
                    pr = po if tot > line else 1 - po
                    if kind == "m":
                        llm -= math.log(max(pr, 1e-12))
                    else:
                        llb -= math.log(max(pr, 1e-12))
            res[str(line)] = {"model": round(llm / len(rows), 5), "average": round(llb / len(rows), 5)}
        out[key] = {"n": len(rows), "lines": res}
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="2425")
    ap.add_argument("--test", default="2526")
    ap.add_argument("--leagues", nargs="*", default=[lg.code for lg in LEAGUES if lg.category == "domestic"])
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--rebuild", action="store_true", help="recalcule les tableaux semaine par semaine")
    ap.add_argument("--write", action="store_true", help="enregistre engine_params.json si le test est réussi")
    args = ap.parse_args()

    print("Tableaux semaine par semaine…", flush=True)
    tabs = load_tables(args.leagues, [args.train, args.test], args.jobs, args.rebuild)
    train, test = Data(tabs[args.train]), Data(tabs[args.test])
    print(f"Apprentissage {args.train} : {train.n} matchs ; test {args.test} : {test.n} matchs", flush=True)

    old = EngineParams()
    new = fit_model_params(train, old)
    new = fit_market_params(train, new)
    co, ca = nb_fit(train.rows, "co"), nb_fit(train.rows, "ca")
    new = replace(new, corners_shrink=co[0] if co else 1.0, corners_size=co[1] if co else None,
                  cards_shrink=ca[0] if ca else 1.0, cards_size=ca[1] if ca else None)
    print("Réglages appris :", json.dumps({k: v for k, v in new.to_dict().items()
                                          if k not in ("reliability", "meta")}), flush=True)

    cmp = compare(test, old, new)
    ok = passes(cmp)
    print("Test sur une saison jamais vue (log-loss, plus bas = mieux) :")
    for path, v in cmp.items():
        for mk in ("1x2", "ou25"):
            x = v[mk]
            print(f"  [{path:<6} {mk:<4}] {v['n']:>5} matchs | ancien {x['old']:.5f} | nouveau {x['new']:.5f} | "
                  f"écart max probable {x['up95']:+.5f} | Brier {x['brier_old']:.4f} → {x['brier_new']:.4f}")
        print(f"  => {path} : {'ADOPTÉ' if ok[path] else 'REFUSÉ'}")
    # Repli : chemin refusé = ancien comportement pour ce chemin
    final = new
    if not ok.get("market", True):
        final = replace(final, w_mkt=1.0, devig="proportional")
    if not ok.get("model", True):
        final = replace(final, w_xg=0.0, w_form=0.0, t=1.0, s=1.0)
    counts = count_check(test, final)
    for key, v in counts.items():
        good = all(x["model"] <= x["average"] for x in v["lines"].values())
        print(f"  [{key}] {v['n']} matchs : " + " | ".join(f"{ln}: {x['model']:.4f} (moyenne {x['average']:.4f})"
                                                        for ln, x in v["lines"].items())
              + f" => {'ADOPTÉ' if good else 'REFUSÉ'}")
        if not good:
            final = replace(final, **{("corners_size" if key == "co" else "cards_size"): None})
    final = replace(final, version="v2" if (ok.get("model") or ok.get("market")) else "v1")
    rel = reliability(test, final)
    final = replace(final, reliability=rel, meta={
        "train": args.train, "test": args.test, "leagues": args.leagues, "compare": cmp, "passes": ok,
        "counts": counts, "matches": {"train": train.n, "test": test.n}})
    b = rel.get("_best") or [0, 0, 0]
    if b[0]:
        print(f"Verdict « le plus sûr » sur {args.test} : {b[1]}/{b[0]} réussis ({b[1] / b[0]:.1%}) "
              f"pour {b[2] / b[0]:.1%} annoncés")
    pk = rel.get("_picks") or [0, 0, 0, 0]
    if pk[0]:
        print(f"Paris du match (au plus {vd.PICK_MAX}, cote {vd.PICK_MIN_ODDS} ou plus) sur {args.test} : {pk[1]}/{pk[0]} "
              f"réussis ({pk[1] / pk[0]:.1%}) pour {pk[2] / pk[0]:.1%} annoncés, cote estimée moyenne {pk[3] / pk[0]:.2f}")
    for fam, cells in rel.items():
        if fam.startswith("_"):
            continue
        n = sum(c[0] for c in cells.values())
        w = sum(c[1] for c in cells.values())
        a = sum(c[2] for c in cells.values())
        if n:
            print(f"  {fam:<6} {n:>5} verdicts | réussis {w / n:.1%} | annoncés {a / n:.1%}")
    if args.write:
        PARAMS_PATH.write_text(json.dumps(final.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"Enregistré : {PARAMS_PATH}")
    else:
        print("(rien d'enregistré : ajouter --write)")


if __name__ == "__main__":
    main()
