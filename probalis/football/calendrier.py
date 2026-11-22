"""Le calendrier change-t-il les résultats ? Repos, match européen juste avant ou juste après.

Usage : python -m probalis.football.calendrier [--train 2425 --test 2526]

Idée testée (porteur du projet, 21/11/2026) : une équipe qui joue la Ligue des champions en semaine ne joue pas
« à fond » le week-end d'avant (elle fait tourner), et elle est fatiguée le week-end d'après.

Méthode, la même que pour le moteur (football/tune.py) :
1. Pour chaque match de championnat des tableaux « semaine par semaine » (data/cache/engine/), on note pour chaque
   équipe : match européen dans les 4 jours d'après (rotation), dans les 4 jours d'avant (fatigue), repos court
   (3 jours ou moins depuis son dernier match, championnat ou coupe d'Europe).
2. Ces indices corrigent les buts attendus (marqués et encaissés). Les corrections sont apprises sur --train,
   puis mesurées sur --test, une saison jamais vue, contre le calcul actuel : moteur seul et calé sur les cotes.
3. Adoption seulement si le calcul corrigé est nettement meilleur sur --test (borne haute à 95 % de l'écart de
   log-loss sous 0, bootstrap par journée).

Limites : les coupes nationales (FA Cup, Coupe de France…) et les matchs de sélection ne sont pas dans nos
données ; seuls les clubs européens reliés à un championnat suivi sont comptés.
"""
from __future__ import annotations

import argparse
import bisect
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
from scipy.optimize import minimize

from . import tune
from .data import load_history
from .engine import load_params
from .leagues import LEAGUES, current_season_start, season_codes
from .linked import men_cups_data

COUNTRY = {"E0": "england", "E1": "england", "E2": "england", "E3": "england", "EC": "england",
           "SP1": "spain", "SP2": "spain", "I1": "italy", "D1": "germany", "F1": "france", "F2": "france",
           "N1": "netherlands", "P1": "portugal", "B1": "belgium", "T1": "turkey"}
CODES = tuple(COUNTRY)
WINDOW = 4          # jours : match européen « juste avant » ou « juste après »
SHORT_REST = 3      # jours : repos court
FEATURES = ("eu_after", "eu_before", "short")
NAMES = {"eu_after": "Match européen dans les 4 jours d'après (rotation)",
         "eu_before": "Match européen dans les 4 jours d'avant (fatigue)",
         "short": "Repos de 3 jours ou moins"}


@dataclass
class Calendar:
    played: dict[str, list[date]]           # équipe -> dates de tous ses matchs (championnat + Europe)
    europe: dict[str, list[tuple[date, str]]]  # équipe -> (date, compétition) de ses matchs européens

    def flags(self, node: str, d: date) -> dict[str, int]:
        eu = [x for x, _ in self.europe.get(node, [])]
        after = any(d < x <= d + timedelta(days=WINDOW) for x in eu)
        before = any(d - timedelta(days=WINDOW) <= x < d for x in eu)
        ds = self.played.get(node, [])
        i = bisect.bisect_left(ds, d)
        rest = (d - ds[i - 1]).days if i > 0 else 99
        return {"eu_after": int(after), "eu_before": int(before), "short": int(rest <= SHORT_REST)}


def build_calendar(seasons: list[str], today: date) -> tuple[Calendar, int]:
    played: dict[str, set[date]] = defaultdict(set)
    for code, country in COUNTRY.items():
        for m in load_history(code, seasons):
            played[f"{country}|{m.home}"].add(m.date)
            played[f"{country}|{m.away}"].add(m.date)
    cups = [lg for lg in LEAGUES if lg.category == "europe"]
    data = men_cups_data(cups, today)
    europe: dict[str, list[tuple[date, str]]] = defaultdict(list)
    n = 0
    for g in data.games:
        if g.kind != "cup":
            continue
        for node in (g.home, g.away):
            if "|" in node:  # club relié à un championnat suivi
                europe[node].append((g.date, g.comp))
                played[node].add(g.date)
                n += 1
    return Calendar({k: sorted(v) for k, v in played.items()}, {k: sorted(v) for k, v in europe.items()}), n


def features(rows: list[dict], cal: Calendar) -> np.ndarray:
    """N × 2 × len(FEATURES) : indices de l'équipe à domicile [:, 0] et à l'extérieur [:, 1]."""
    out = np.zeros((len(rows), 2, len(FEATURES)))
    for i, r in enumerate(rows):
        d, c = date.fromisoformat(r["d"]), COUNTRY[r["lg"]]
        for side, team in ((0, r["h"]), (1, r["a"])):
            f = cal.flags(f"{c}|{team}", d)
            out[i, side] = [f[k] for k in FEATURES]
    return out


# Variantes testées : (nom, indices utilisés, « séparé » = buts marqués et encaissés corrigés à part ;
# sinon une seule correction de force : ce que l'équipe gagne en buts marqués, elle le perd en buts encaissés).
VARIANTS = (("Trois indices, buts marqués et encaissés à part", FEATURES, True),
            ("Trois indices, une seule correction de force", FEATURES, False),
            ("Rotation seule (match européen juste après)", ("eu_after",), False),
            ("Fatigue seule (match européen juste avant)", ("eu_before",), False),
            ("Repos court seul", ("short",), False))


def expand(th: np.ndarray, keys: tuple[str, ...], separate: bool) -> np.ndarray:
    """Paramètres d'une variante -> vecteur complet [attaque × FEATURES, défense × FEATURES]."""
    k = len(FEATURES)
    full = np.zeros(2 * k)
    n = len(keys)
    for i, key in enumerate(keys):
        j = FEATURES.index(key)
        full[j] = th[i]
        full[k + j] = th[n + i] if separate else -th[i]
    return full


def adjust(l0: np.ndarray, l1: np.ndarray, X: np.ndarray, th: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """th = [attaque × indices, défense × indices] : buts marqués par l'équipe touchée, buts qu'elle encaisse."""
    k = len(FEATURES)
    att, dfn = th[:k], th[k:]
    return (l0 + X[:, 0] @ att + X[:, 1] @ dfn,
            l1 + X[:, 1] @ att + X[:, 0] @ dfn)


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


def fit_adjust(d: tune.Data, X: np.ndarray, market: bool, keys: tuple[str, ...] = FEATURES,
               separate: bool = True) -> np.ndarray:
    l0, l1 = base_logs(d, market)
    n = len(keys) * (2 if separate else 1)

    def obj(th):
        a0, a1 = adjust(l0, l1, X, expand(th, keys, separate))
        return float(losses(a0, a1, d).mean())
    res = minimize(obj, np.zeros(n), method="L-BFGS-B", bounds=[(-0.5, 0.5)] * n, options={"eps": 1e-5})
    return expand(res.x, keys, separate)


def describe(d: tune.Data, X: np.ndarray, market: bool) -> list[tuple[str, int, float, float, float, float]]:
    """Pour chaque indice : nb de cas, victoires réelles de l'équipe touchée / annoncées, buts marqués réels /
    annoncés."""
    l0, l1 = base_logs(d, market)
    p3, _ = tune.probs(np.exp(l0), np.exp(l1), d.rho)
    s = np.array([r["s"] for r in d.rows], dtype=float)
    out = []
    for j, key in enumerate(FEATURES):
        won = exp_won = goals = exp_goals = 0.0
        n = 0
        for side in (0, 1):
            m = X[:, side, j] > 0
            if not m.any():
                continue
            n += int(m.sum())
            win = (d.k == (0 if side == 0 else 2))
            won += win[m].sum()
            exp_won += p3[m, 0 if side == 0 else 2].sum()
            goals += s[m, side].sum()
            exp_goals += np.exp(l0 if side == 0 else l1)[m].sum()
        if n:
            out.append((key, n, won / n, exp_won / n, goals / n, exp_goals / n))
    return out


def evaluate(dtr: tune.Data, Xtr: np.ndarray, dte: tune.Data, Xte: np.ndarray, market: bool, test: str) -> None:
    """Apprend chaque variante sur (dtr, Xtr) et la mesure sur (dte, Xte), contre le calcul actuel."""
    l0, l1 = base_logs(dte, market)
    old = losses(l0, l1, dte)
    k = len(FEATURES)
    for vname, keys, separate in VARIANTS:
        th = fit_adjust(dtr, Xtr, market, keys, separate)
        a0, a1 = adjust(l0, l1, Xte, th)
        diff = losses(a0, a1, dte) - old
        up = tune.upper95(diff, dte.dates)
        corr = ", ".join(f"{key} : marqués {100 * (np.exp(th[FEATURES.index(key)]) - 1):+.1f} % / encaissés "
                         f"{100 * (np.exp(th[k + FEATURES.index(key)]) - 1):+.1f} %" for key in keys)
        print(f"  - {vname} [{corr}]")
        print(f"      test {test} ({dte.n} matchs) : écart de log-loss {diff.mean():+.5f} "
              f"(borne haute à 95 % {up:+.5f}) : {'ADOPTÉ' if up < 0 else 'pas adopté'}")


def partial_tables(season: str) -> list[dict]:
    """Tableau « semaine par semaine » d'une saison en cours, rangé à part (data/cache/engine/partiel/) pour ne
    jamais être pris pour le tableau complet de la saison par football/tune.py."""
    saved = tune.TABLE_DIR
    tune.TABLE_DIR = saved / "partiel" / date.today().isoformat()
    try:
        rows = []
        for code in CODES:
            got = tune.build_table(code, season)
            print(f"  {season} {code}: {len(got)} matchs (saison en cours)", flush=True)
            rows += got
        return rows
    finally:
        tune.TABLE_DIR = saved


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="2425")
    ap.add_argument("--test", default="2526")
    ap.add_argument("--check", default="", help="saison en cours pour une vérification de plus (ex. 2627) : "
                    "variantes apprises sur --train et --test réunies, mesurées sur cette saison")
    args = ap.parse_args()
    tables = tune.load_tables(list(CODES), [args.train, args.test])
    if args.check:
        tables[args.check] = partial_tables(args.check)
    today = date.today()
    current = season_codes(current_season_start(today), 1)[0]  # saison en cours en tête (load_history)
    seasons = [current] + sorted({args.train, args.test, tune._prev_season(args.train)} - {current},  # noqa: SLF001
                                 reverse=True)
    cal, n_eu = build_calendar(seasons, today)
    print(f"\n{n_eu} matchs européens de clubs reliés à nos championnats ; "
          f"{sum(len(v) for v in tables.values())} matchs de championnat\n")
    data = {s: tune.Data(rows) for s, rows in tables.items()}
    X = {s: features(tables[s], cal) for s in data}

    def pick(season: str, market: bool) -> tuple[tune.Data, np.ndarray]:
        d, x = data[season], X[season]
        return (d.subset(d.has_mk), x[d.has_mk]) if market else (d, x)

    for market in (True, False):
        print(f"=== {'Calé sur les cotes' if market else 'Moteur seul'} ===")
        for season in data:
            dd, XX = pick(season, market)
            for key, n, won, ew, g, eg in describe(dd, XX, market):
                print(f"  {season} | {NAMES[key]} : {n} cas | victoires {100 * won:.1f} % pour {100 * ew:.1f} % "
                      f"annoncés | buts marqués {g:.2f} pour {eg:.2f} annoncés")
        (dtr, Xtr), (dte, Xte) = pick(args.train, market), pick(args.test, market)
        print(f"  Appris sur {args.train} :")
        evaluate(dtr, Xtr, dte, Xte, market, args.test)
        if args.check:
            both = tune.Data(dtr.rows + dte.rows)
            dch, Xch = pick(args.check, market)
            print(f"  Appris sur {args.train} + {args.test} :")
            evaluate(both, np.concatenate([Xtr, Xte]), dch, Xch, market, args.check)
        print()


if __name__ == "__main__":
    main()
