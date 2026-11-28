"""Chance en direct : test sur de vrais matchs passés, minute par minute (mise à niveau 5, 27/11/2026).

Pendant un match, la fiche recalcule la chance de chaque pari du match selon le score et la minute (app.js,
`InPlay`). Le calcul : les buts déjà marqués sont acquis ; ceux qui restent suivent la même loi de Poisson que
l'analyse d'avant-match (buts attendus `xg`), réduite à la part du match qui reste à jouer. Cette part n'est pas
proportionnelle au temps : on marque plus en fin de match. Le « profil » des buts minute par minute est appris
sur la saison 2025/26 et testé sur 2026/27 (jamais vue), avec les minutes des buts et des cartons publiées par
ESPN (accès ouvert). Un réglage n'est gardé que s'il améliore la saison de test (règle du projet).

Usage :
  python -m probalis.football.endirect --fetch     (relève les minutes des buts et cartons chez ESPN, ~25 min)
  python -m probalis.football.endirect             (apprend, teste, écrit probalis/site/inplay.json)
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..core import inplay
from ..core.verdicts import picks, verdicts
from . import espn, fixtures
from .backtest import _in_season, _odds, _prev_season
from .data import CACHE, load_history
from .engine import analyse, fit_league, load_params

DIR = CACHE / "espn_hist"
OUT = Path(__file__).resolve().parents[1] / "site" / "inplay.json"
CODES = ("E0", "SP1", "I1", "D1", "F1", "E1", "N1", "P1", "B1", "T1", "F2", "SP2", "E2", "E3", "EC")
TRAIN, TEST = "2526", "2627"
CHECKS = ("15", "30", "ht", "60", "70", "80", "85")   # moments du test (« ht » : à la mi-temps)
PRE_1X2 = (("AvgH", "AvgD", "AvgA"), ("B365H", "B365D", "B365A"))
PRE_OU = (("Avg>2.5", "Avg<2.5"), ("B365>2.5", "B365<2.5"))


# ---------------------------------------------------------------------------------------------------------------
# 1. Relevé ESPN : pour chaque journée, les matchs, leur score et la minute de chaque but et de chaque carton
# ---------------------------------------------------------------------------------------------------------------
def _minute(clock: dict) -> tuple[int, int, int] | None:
    """(minute, temps additionnel, mi-temps) d'un temps fort : « 45'+2' » -> (45, 2, 1), « 67' » -> (67, 0, 2)."""
    disp = str((clock or {}).get("displayValue") or "").replace("'", "")
    try:
        base, _, extra = disp.partition("+")
        m, x = int(base), int(extra or 0)
    except ValueError:
        return None
    if m > 120:
        return None
    period = 1 if m <= 45 and not (m == 45 and (clock or {}).get("value", 0) > 2760) else 2
    if m > 90:
        period = 3
    return m, x, period


def _slim(ev: dict) -> dict | None:
    comp = (ev.get("competitions") or [{}])[0]
    sides = {c.get("homeAway"): c for c in comp.get("competitors") or []}
    if "home" not in sides or "away" not in sides:
        return None
    side_of = {str((sides[k].get("team") or {}).get("id")): k[0] for k in ("home", "away")}
    try:
        sc = [int(sides["home"].get("score")), int(sides["away"].get("score"))]
    except (TypeError, ValueError):
        return None
    det = []
    for d in comp.get("details") or []:
        mn = _minute(d.get("clock") or {})
        side = side_of.get(str((d.get("team") or {}).get("id")))
        if not mn or not side:
            continue
        if d.get("scoringPlay"):
            kind = "o" if d.get("ownGoal") else "g"
        elif d.get("redCard"):
            kind = "r"
        elif d.get("yellowCard"):
            kind = "y"
        else:
            continue
        det.append([kind, mn[0], mn[1], mn[2], side])
    st = (ev.get("status") or {}).get("type") or {}
    return {"h": espn._names(sides["home"].get("team") or {}), "a": espn._names(sides["away"].get("team") or {}),
            "sc": sc, "sn": st.get("name"), "d": det}


def _get(url: str) -> dict | None:
    """Comme espn._fetch (demandes espacées), mais en réponse compressée : 8 fois moins à télécharger."""
    for attempt in range(3):
        wait = espn._MIN_INTERVAL - (time.time() - espn._state["last"])
        if wait > 0:
            time.sleep(wait)
        espn._state["last"] = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": espn.USER_AGENT, "Accept": "application/json",
                                                   "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                if resp.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                return {"events": []}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            pass
        time.sleep(10 * (attempt + 1))
    return None


def _read(path: Path) -> list[dict] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None   # fichier coupé (relevé interrompu) : redemandé


def _day(slug: str, day) -> list[dict] | None:
    path = DIR / f"{slug}_{day:%Y%m%d}.json"
    if path.exists() and (old := _read(path)) is not None:
        return old
    data = _get(espn.API.format(slug=slug, what="scoreboard") + f"?dates={day:%Y%m%d}")
    if data is None:
        return None
    out = [s for s in (_slim(e) for e in data.get("events") or []) if s]
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)
    return out


def fetch() -> None:
    days = []
    for code in CODES:
        hist = load_history(code, [TRAIN, TEST])
        for d in sorted({m.date for m in hist if _in_season(m, TRAIN) or _in_season(m, TEST)}):
            days.append((espn.SLUGS[code], d))
    todo = [x for x in days if _read(DIR / f"{x[0]}_{x[1]:%Y%m%d}.json") is None]
    print(f"{len(days)} journées, {len(todo)} à demander à ESPN", flush=True)
    t0 = time.time()
    for i, (slug, d) in enumerate(todo, 1):
        if _day(slug, d) is None:
            print(f"  pas de réponse : {slug} {d}", flush=True)
        if i % 100 == 0:
            print(f"  {i}/{len(todo)} ({(time.time() - t0) / 60:.0f} min)", flush=True)
    print("Relevé terminé.", flush=True)


# ---------------------------------------------------------------------------------------------------------------
# 2. Chaque match football-data relié à son match ESPN (même jour, mêmes noms, même score)
# ---------------------------------------------------------------------------------------------------------------
def _goals_ok(e: dict) -> list[list] | None:
    """Les buts du match, chacun avec l'équipe qui en profite ; None si les minutes ne collent pas au score."""
    goals = [list(x) for x in e["d"] if x[0] in ("g", "o")]
    for flip_own in (False, True):
        out = []
        for g in goals:
            side = g[4]
            if g[0] == "o" and flip_own:
                side = "a" if side == "h" else "h"
            out.append([g[1], g[2], g[3], side])
        if [sum(1 for g in out if g[3] == "h"), sum(1 for g in out if g[3] == "a")] == e["sc"]:
            return out
    return None


def _link(rows: list, events: list[dict]) -> dict:
    if not rows or not events:
        return {}
    cost = np.full((len(rows), len(events)), 9.0)
    for i, r in enumerate(rows):
        for j, e in enumerate(events):
            if e["sc"] != [r.fthg, r.ftag]:
                continue
            sh, sa = espn._name_score(r.home, e["h"]), espn._name_score(r.away, e["a"])
            if min(sh, sa) >= 0.3:
                cost[i, j] = -(sh + sa)
    out = {}
    for i, j in zip(*linear_sum_assignment(cost)):
        if cost[i, j] < 0:
            out[i] = events[j]
    return out


# ---------------------------------------------------------------------------------------------------------------
# 3. Chaque match avec son analyse d'avant-match (même moteur que le site, calé sur les cotes) et ses temps forts
# ---------------------------------------------------------------------------------------------------------------
def matches(season: str, verbose: bool = True) -> list[dict]:
    seasons = [season, _prev_season(season), _prev_season(_prev_season(season)),
               _prev_season(_prev_season(_prev_season(season)))]
    params = load_params()
    out = []
    for code in CODES:
        slug = espn.SLUGS[code]
        hist = load_history(code, seasons)
        test = sorted((m for m in hist if _in_season(m, season) and m.fthg is not None), key=lambda m: m.date)
        if not test:
            continue
        by_day = defaultdict(list)
        for m in test:
            by_day[m.date].append(m)
        linked = {}
        for d, rows in by_day.items():
            path = DIR / f"{slug}_{d:%Y%m%d}.json"
            day_evs = _read(path) if path.exists() else None
            if not day_evs:
                continue
            evs = [e for e in day_evs if e.get("sn") in espn.NORMAL_END]
            for i, e in _link(rows, evs).items():
                linked[id(rows[i])] = e
        week = test[0].date + timedelta(days=21)
        n = 0
        while week <= test[-1].date:
            batch = [m for m in test if week <= m.date < week + timedelta(days=7) and id(m) in linked]
            if batch:
                lm = fit_league(hist, week, params, counts=False)
                for m in batch:
                    if not (lm.goals.knows(m.home) and lm.goals.knows(m.away)):
                        continue
                    e = linked[id(m)]
                    goals = _goals_ok(e)
                    if goals is None:
                        continue
                    o12 = _odds(m, PRE_1X2)
                    oou = _odds(m, PRE_OU) if o12 else None
                    an = analyse(lm, m.home, m.away, o12, oou, params)
                    reds = [[x[1], x[2], x[3], x[4]] for x in e["d"] if x[0] == "r"]
                    out.append({"lg": code, "date": m.date.isoformat(), "lam": an.pred.lam, "mu": an.pred.mu,
                                "rho": lm.goals.rho, "sc": [m.fthg, m.ftag], "goals": goals, "reds": reds,
                                "markets": [mk.to_dict() for mk in an.pred.markets]})
                    n += 1
            week += timedelta(days=7)
        if verbose:
            print(f"  {code} {season} : {n} matchs reliés", flush=True)
    return out


# ---------------------------------------------------------------------------------------------------------------
# 4. Profil des buts, état du match à chaque moment du test, et note des différentes façons de calculer
# ---------------------------------------------------------------------------------------------------------------
def _slot(minute: int, extra: int, period: int) -> int:
    """Case du profil (1 à 90) : le temps additionnel compte dans la 45e ou la 90e minute."""
    if period == 1:
        return min(minute, 45)
    return max(46, min(minute, 90))


def learn_profile(ms: list[dict], smooth: int = 3) -> list[float]:
    """Part des buts marqués à chaque minute (1 à 90), lissée sauf la 45e et la 90e (temps additionnel)."""
    c = np.zeros(91)
    for m in ms:
        for g in m["goals"]:
            if g[2] <= 2:
                c[_slot(g[0], g[1], g[2])] += 1
    out = c.copy()
    for k in range(1, 91):
        if k in (45, 90):
            continue
        lo, hi = max(1, k - smooth), min(90, k + smooth)
        idx = [i for i in range(lo, hi + 1) if i not in (45, 90) and (i <= 45) == (k <= 45)]
        out[k] = c[idx].mean()
    out = out[1:] / out[1:].sum()
    return [round(float(x), 6) for x in out]


def state(m: dict, check: str) -> tuple[int, int, int, list] | None:
    """(buts domicile, buts extérieur, case du profil déjà jouée, rouges) au moment `check`."""
    played = 45 if check == "ht" else int(check)
    def done(minute, extra, period):
        if check == "ht":
            return period == 1
        return _slot(minute, extra, period) <= played and not (period == 2 and minute > played)
    h = sum(1 for g in m["goals"] if g[3] == "h" and done(*g[:3]))
    a = sum(1 for g in m["goals"] if g[3] == "a" and done(*g[:3]))
    reds = [r[3] for r in m["reds"] if done(*r[:3])]
    return h, a, played, reds


def _picks_of(m: dict) -> list[dict]:
    vs = verdicts(m["markets"])
    return [vs[i] for i in picks(vs) if vs[i]["key"] not in ("co", "ca")]


def _goal_verdicts(m: dict) -> list[dict]:
    return [v for v in verdicts(m["markets"]) if v["key"] not in ("co", "ca")]


def _final(m: dict, check: str, cfg: dict):
    h, a, played, rd = state(m, check)
    return inplay.final_matrix(m["lam"], m["mu"], h, a, played, cfg.get("profile"), rd if cfg.get("reds") else (),
                               cfg.get("reds"), m["rho"], cfg.get("kappa"), cfg.get("kmode", "total"))


def evaluate(ms: list[dict], cfg: dict, which: str = "picks") -> dict:
    """Note (perte logarithmique moyenne, plus bas = mieux) et tableau annoncé / réel, par moment du test.
    which : « picks » (les paris du match, buts seulement) ou « all » (tous les verdicts sur les buts)."""
    res = {}
    for check in CHECKS:
        ll, n, bands = 0.0, 0, defaultdict(lambda: [0, 0, 0.0])
        for m in ms:
            vs = m["_picks"] if which == "picks" else m["_all"]
            if not vs:
                continue
            final = _final(m, check, cfg)
            for v in vs:
                p_yes = inplay.prob(final, v["key"], v["line"], v["sel"])
                p = min(max(p_yes if v["yes"] else 1 - p_yes, 1e-4), 1 - 1e-4)
                won = inplay.outcome(v["key"], v["line"], v["sel"], *m["sc"]) == v["yes"]
                ll -= math.log(p if won else 1 - p)
                n += 1
                b = bands[min(9, int(p * 10))]
                b[0] += 1
                b[1] += won
                b[2] += p
        res[check] = {"n": n, "ll": ll / max(n, 1),
                      "bands": {k: (v[0], v[1] / v[0], v[2] / v[0]) for k, v in sorted(bands.items()) if v[0]}}
    return res


def score(ms: list[dict], cfg: dict) -> float:
    """Perte moyenne sur tous les verdicts buts et tous les moments du test (plus bas = mieux)."""
    r = evaluate(ms, cfg, "all")
    return sum(v["ll"] * v["n"] for v in r.values()) / max(1, sum(v["n"] for v in r.values()))


def learn_reds(ms: list[dict], cfg: dict) -> tuple[float, float]:
    """Effet d'un carton rouge sur les buts qui restent : (équipe à 10, son adversaire), appris sur les matchs avec rouge."""
    with_red = [m for m in ms if m["reds"]]
    best, best_ll = (1.0, 1.0), None
    for own in (0.55, 0.65, 0.75, 0.85, 1.0):
        for opp in (1.0, 1.15, 1.3, 1.45, 1.6):
            ll = score(with_red, {**cfg, "reds": (own, opp)})
            if best_ll is None or ll < best_ll:
                best, best_ll = (own, opp), ll
    return best


def _prepare(ms: list[dict]) -> None:
    for m in ms:
        m["_picks"] = _picks_of(m)
        m["_all"] = _goal_verdicts(m)


def _show(name: str, r: dict) -> None:
    print(f"  {name}")
    for check, v in r.items():
        print(f"    {check:>3} : {v['n']:>5} paris, perte {v['ll']:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="relever les minutes des buts et cartons chez ESPN")
    args = ap.parse_args()
    if args.fetch:
        fetch()
        return
    print("Analyses d'avant-match de la saison d'apprentissage et de la saison de test…", flush=True)
    train, test = matches(TRAIN), matches(TEST)
    _prepare(train)
    _prepare(test)
    print(f"{len(train)} matchs pour apprendre ({TRAIN}), {len(test)} pour tester ({TEST})", flush=True)
    # Chaque réglage est appris sur la saison d'apprentissage, puis gardé seulement s'il fait mieux sur la saison de
    # test (jamais vue), l'un après l'autre.
    def step_profile(cfg):
        return "Profil appris (on marque plus en fin de match)", {**cfg, "profile": learn_profile(train)}

    def step_kappa(cfg):
        grid = [(k, mode) for mode in ("total", "team") for k in (2, 4, 8, 16, 32)]
        tr = {g: score(train, {**cfg, "kappa": g[0], "kmode": g[1]}) for g in grid}
        tr[(None, "total")] = score(train, cfg)
        k, mode = min(tr, key=tr.get)
        if k is None:   # ne fait pas mieux à l'apprentissage : rien à tester
            return None, None
        return f"Buts déjà marqués (kappa {k}, {mode})", {**cfg, "kappa": k, "kmode": mode}

    def step_reds(cfg):
        reds = learn_reds(train, cfg)
        return f"Cartons rouges (équipe à 10 x{reds[0]}, adversaire x{reds[1]})", {**cfg, "reds": reds}

    kept = {"profile": [1 / 90] * 90}
    kept_score = score(test, kept)
    print(f"\nSaison de test {TEST} (perte moyenne, tous les verdicts buts, 7 moments du match) :")
    print(f"  Temps régulier (même part de buts à chaque minute) : {kept_score:.4f}", flush=True)
    log = [{"step": "Temps régulier", "test": round(kept_score, 5), "kept": True}]
    for step in (step_profile, step_kappa, step_reds):
        name, trial = step(kept)
        if trial is None:
            print("  Buts déjà marqués : pas mieux sur la saison d'apprentissage -> écarté", flush=True)
            log.append({"step": "Buts déjà marqués", "test": None, "kept": False})
            continue
        sc = score(test, trial)
        ok = sc < kept_score
        print(f"  {name} : {sc:.4f} -> {'gardé' if ok else 'écarté'}", flush=True)
        log.append({"step": name, "test": round(sc, 5), "kept": ok})
        if ok:
            kept, kept_score = trial, sc
    final = evaluate(test, kept, "picks")
    _show("\nParis du match avec les réglages gardés", final)
    print("\nAnnoncé / réel des paris du match (saison de test) :")
    tot = {"n": 0, "won": 0.0, "ann": 0.0}
    for check, v in final.items():
        print(f"  {check:>3} : " + "  ".join(f"{int(b) * 10}-{int(b) * 10 + 10} % : {n} ({a:.0%} annoncé, {w:.0%} réel)"
                                            for b, (n, w, a) in v["bands"].items() if n >= 30))
        for b, (n, w, a) in v["bands"].items():
            tot["n"] += n
            tot["won"] += w * n
            tot["ann"] += a * n
    out = {"profile": kept["profile"], "kappa": kept.get("kappa"), "kmode": kept.get("kmode", "total"),
           "reds": list(kept["reds"]) if kept.get("reds") else None, "steps": log,
           "tested": {"season": f"20{TEST[:2]}/{TEST[2:]}", "train": f"20{TRAIN[:2]}/{TRAIN[2:]}",
                      "matches": len(test), "bets": tot["n"], "picks": final["15"]["n"],
                      "announced": round(tot["ann"] / tot["n"], 4),
                      "rate": round(tot["won"] / tot["n"], 4)}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nEnregistré dans {OUT} : {out['tested']}")


if __name__ == "__main__":
    main()
