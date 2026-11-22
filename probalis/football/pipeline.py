"""Chaîne complète : données -> modèles -> prédictions des prochains matchs (avec cotes si disponibles)."""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import date, datetime, timedelta, timezone

from ..core.value import Outcome
from .engine import (LeagueModels, add_counts, analyse, factors as engine_factors, fit_league, load_params,
                     market_rates, mix)
from .data import load_history, load_upcoming_odds, MatchRow
from . import form
from .fixtures import Fixture, finished, league_badge, league_rounds, match_names, upcoming_fixtures
from .leagues import LEAGUES, League, current_season_start, season_codes
from .linked import DOMESTIC_SOURCES, FINAL_ROUND, Linked, men_cups, women, world
from . import oddsapi
from .predict import Prediction, confidence, predict, predict_from_rates

# Fenêtre glissante : chaque lancement analyse les matchs d'aujourd'hui jusqu'à J+8
# (le 19, du 19 au 27 ; le 20, du 20 au 28, etc.).
HORIZON_DAYS = 8


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _odds_markets(row: MatchRow) -> dict:
    """Cotes du fichier football-data.co.uk, rangées par marché : {(clé, ligne): {sélection: {best, avg}}}."""
    o = row.odds
    out: dict = {}

    def pack(key, line, cols):
        sel = {}
        for s, (best, avg) in cols.items():
            if o.get(best) and o.get(avg):
                sel[s] = {"best": o[best], "avg": o[avg]}
        if len(sel) == len(cols):
            out[(key, line)] = sel

    pack("1x2", None, {"1": ("MaxH", "AvgH"), "X": ("MaxD", "AvgD"), "2": ("MaxA", "AvgA")})
    pack("ou", 2.5, {"over": ("Max>2.5", "Avg>2.5"), "under": ("Max<2.5", "Avg<2.5")})
    if row.ah_line is not None:
        pack("ah", row.ah_line, {"1": ("MaxAHH", "AvgAHH"), "2": ("MaxAHA", "AvgAHA")})
    return out


def _priced(pred: Prediction, odds: dict) -> dict:
    """Pour chaque sélection cotée : notre probabilité, la cote juste, la meilleure et la moyenne du marché.

    Pas d'étiquette « valeur » : le test sur la saison 2025/26 montre qu'aucune règle simple ne bat
    les cotes de clôture (voir docs/05-fiabilite.md).
    """
    priced: dict = {}
    for (key, line), sels in odds.items():
        try:
            market = pred.market(key, line)
        except KeyError:
            continue
        keys = list(sels)
        bk_margin = sum(1 / sels[k]["avg"] for k in keys) - 1
        for k in keys:
            outcome: Outcome = market.selections[k]
            priced[f"{key}|{line}|{k}"] = {"key": key, "line": line, "sel": k, "p": outcome.prob,
                                            "fair": outcome.fair_odds, "best": sels[k]["best"],
                                            "avg": sels[k]["avg"], "margin": bk_margin}
    return priced


def _season_teams(hist: list[MatchRow], season_start: int) -> list[str]:
    start = date(season_start, 7, 1)
    return sorted({m.home for m in hist if m.date >= start} | {m.away for m in hist if m.date >= start})


def _upcoming(lg: League, today: date, events: list[dict] | None = None) -> list[Fixture]:
    return upcoming_fixtures(lg, today, today + timedelta(days=HORIZON_DAYS), events)


def _fresh_results(lg: League, events: list[dict], hist: list[MatchRow], names: dict[str, str]) -> list[MatchRow]:
    """Résultats que TheSportsDB connaît déjà mais pas encore le fichier football-data.co.uk (mis à jour
    environ deux fois par semaine). Ainsi, un match joué à 13 h compte dès la relance suivante pour les
    prochains matchs des deux équipes."""
    seen = {(m.home, m.away): m.date for m in hist[-600:]}
    out = []
    for e, ko, (hg, ag) in finished(events):
        h, a = names.get(e.get("strHomeTeam") or ""), names.get(e.get("strAwayTeam") or "")
        d = ko.date()
        if not (h and a) or (h, a) in seen and abs((seen[(h, a)] - d).days) <= 3:
            continue
        out.append(MatchRow(league=lg.code, date=d, home=h, away=a, fthg=hg, ftag=ag))
    return out


def _badge(lg: League, fixtures: list[Fixture]) -> dict:
    return {"badge": next((f.league_badge for f in fixtures if f.league_badge), None) or league_badge(lg.tsdb_id),
            "badge_on_dark": lg.logo_on_dark}


def _match_dict(lg: League, f: Fixture, h: str, a: str, pred: Prediction, model_pred: Prediction, source: str,
                stature: float, conf: str, priced: dict, factors: list | None = None, counts: dict | None = None,
                engine: str = "v1") -> dict:
    return {
        "id": f.event_id,
        "slug": f"{f.kickoff_utc.date().isoformat()}-{slugify(f.home_tsdb)}-{slugify(f.away_tsdb)}",
        "league": lg.code, "kickoff": f.kickoff_utc.isoformat(), "round": f.round, "venue": f.venue,
        "home": {"name": f.home_tsdb, "fd": h, "badge": f.home_badge},
        "away": {"name": f.away_tsdb, "fd": a, "badge": f.away_badge},
        "xg": [round(pred.lam, 3), round(pred.mu, 3)],
        "source": source,
        "stature": round(stature, 3),
        "model_1x2": [round(model_pred.p("1x2", s), 4) for s in ("1", "X", "2")],
        "confidence": conf,
        "top_score": _top_scores(pred, 3),
        "markets": [m.to_dict() for m in pred.markets],
        "priced": priced,
        "factors": factors or [],
        "counts": counts or {},
        "engine": engine,
    }


def _cup_count_rates(h: str, a: str, league_models: dict, kind: str, neutral: bool) -> tuple | None:
    """Corners (ou cartons) attendus d'un match de coupe d'Europe, à partir du championnat de chaque club.

    Chaque club garde son écart à la moyenne de son championnat (obtenir des corners, en concéder) ;
    la base est la moyenne des deux championnats. Un club dont le championnat n'a pas ces chiffres compte
    comme un club moyen (« estimation moins sûre »)."""
    def side(node: str):
        if "|" not in node:
            return None
        country, team = node.split("|", 1)
        src = DOMESTIC_SOURCES.get(country)
        lm = league_models.get(src[1]) if src and src[0] == "main" else None
        m = getattr(lm, kind) if lm else None
        if m is None or not m.knows(team):
            return None
        i = m._idx[team]  # noqa: SLF001
        return m, float(m.attack[i]), float(m.defence[i])

    sh, sa = side(h), side(a)
    if not (sh or sa):
        return None
    ms = [x[0] for x in (sh, sa) if x]
    c = sum(m.intercept for m in ms) / len(ms)
    g = 0.0 if neutral else sum(m.home_adv for m in ms) / len(ms)
    ah, dh = (sh[1], sh[2]) if sh else (0.0, 0.0)
    aa, da = (sa[1], sa[2]) if sa else (0.0, 0.0)
    rates = (math.exp(c + g + ah + da), math.exp(c + aa + dh)), (math.exp(c + g), math.exp(c))
    return rates, bool(sh and sa)


def _linked_matches(lg: League, linked: Linked, today: date, report: dict,
                    league_models: dict | None = None) -> tuple[list[dict], dict]:
    """Matchs d'une coupe d'Europe, d'un championnat féminin ou de la Ligue saoudienne, analysés par le modèle relié.

    Pas de fichier de cotes football-data.co.uk pour ces compétitions. Avec la clé gratuite de The Odds API
    (football/oddsapi.py), l'analyse est calée sur les cotes comme en championnat (même règle : engine.market_rates
    puis mix) ; sans cotes, elle vient du modèle seul et la confiance est plafonnée à « moyenne ».
    """
    fixtures = _upcoming(lg, today)
    odds_by_id = oddsapi.odds_for(lg.code, fixtures)
    kind = "cup" if lg.cup else "dom"
    m = linked.model
    quality = {t: float(m.attack[i] - m.defence[i]) for i, t in enumerate(m.teams)}
    out = []
    p = load_params()
    nodes = [n for f in fixtures for n in (linked.node(f.home_id), linked.node(f.away_id)) if n]
    pool = sorted(set(nodes)) if lg.cup else [t for t in m.teams if m.group_of.get(t) == lg.code]
    for f in fixtures:
        h, a = linked.node(f.home_id), linked.node(f.away_id)
        if not (h and a):
            report["unmatched"].append(f"{lg.code}: {f.home_tsdb} - {f.away_tsdb}")
            continue
        view = m.view(kind, neutral=str(f.round) == FINAL_ROUND)
        model_pred = pred = predict(view, h, a)
        conf = confidence(view, h, a)
        conf = "medium" if conf == "high" else conf
        odds = odds_by_id.get(f.event_id, {})
        source, mkt_terms = "model", None
        if ("1x2", None) in odds:
            o12 = [odds[("1x2", None)][k]["avg"] for k in ("1", "X", "2")]
            ou = odds.get(("ou", 2.5))
            oou = [ou["over"]["avg"], ou["under"]["avg"]] if ou else None
            lam_m, mu_m = market_rates(o12, oou, view.rho, p, start=(pred.lam, pred.mu))
            lam, mu = mix((pred.lam, pred.mu), (lam_m, mu_m), p.w_mkt)
            pred = predict_from_rates(view, h, a, lam, mu)
            source, conf = "market", "high"
            mkt_terms = (math.log(lam / model_pred.lam), math.log(mu / model_pred.mu))
        rates, partial = {}, False
        if lg.category == "europe" and league_models:
            for k in ("corners", "cards"):
                r = _cup_count_rates(h, a, league_models, k, str(f.round) == FINAL_ROUND)
                if r:
                    rates[k] = r[0]
                    partial = partial or not r[1]
        counts = add_counts(pred, None, None, h, a, p, rates=rates)
        if counts and partial:
            counts["partial"] = True
        facts = engine_factors(LeagueModels(view, season_teams=pool), h, a, pred.lam, pred.mu, {}, mkt_terms, conf)
        d = _match_dict(lg, f, h, a, pred, model_pred, source, quality[h] + quality[a], conf,
                        _priced(pred, odds), facts, counts, p.version)
        if source == "market":
            d["odds_src"] = "oddsapi"   # cotes de The Odds API (les championnats : football-data.co.uk)
        out.append(d)
    report["leagues"][lg.code] = {"fixtures": len(fixtures), "predicted": len(out), "train_matches": m.n_matches,
                                  "odds": sum(1 for x in out if x["source"] == "market"),
                                  "rho": round(m.rho, 3),
                                  "home_adv": round(m.home_cup if lg.cup else m.home_dom, 3)}
    return out, _badge(lg, fixtures)


def _run_linked(name: str, builder, lgs: list[League], today: date, matches: list, report: dict,
                league_info: dict, verbose: bool, league_models: dict | None = None,
                book: form.Book | None = None) -> None:
    if not lgs:
        return
    try:
        linked = builder(lgs, today, verbose)
    except Exception as e:  # une source en panne ne doit pas bloquer le reste du site
        for lg in lgs:
            report["leagues"][lg.code] = f"indisponible ({type(e).__name__}: {e})"
        if verbose:
            print(f"  {name} : indisponible ({e})")
        return
    report[name] = linked.report
    if book is not None:
        book.add_games(linked.games)
        for node, shown in linked.names.items():
            if shown:
                book.names.setdefault(node, shown)
    for lg in lgs:
        ms, league_info[lg.code] = _linked_matches(lg, linked, today, report, league_models)
        matches += ms
        if verbose:
            n_odds = report["leagues"][lg.code].get("odds") or 0
            extra = f", dont {n_odds} calés sur les cotes" if n_odds else ""
            print(f"  {lg.code:>5} {lg.name_fr:<28} {len(ms)}/{report['leagues'][lg.code]['fixtures']} matchs analysés"
                  f"{extra}")


def run(today: date | None = None, leagues: tuple[League, ...] = LEAGUES, verbose: bool = True) -> dict:
    today = today or date.today()
    start = current_season_start(today)
    seasons = season_codes(start, 4)
    odds_rows = load_upcoming_odds()
    matches, report = [], {"unmatched": [], "leagues": {}}
    league_info: dict[str, dict] = {}
    league_models: dict[str, LeagueModels] = {}
    book = form.Book()  # tous les matchs joués : forme récente et face-à-face affichés dans les fiches
    for lg in (lg for lg in leagues if lg.category == "domestic"):
        hist = load_history(lg.code, seasons)
        if len(hist) < 100:
            report["leagues"][lg.code] = "pas assez de données"
            continue
        events = league_rounds(lg, today + timedelta(days=HORIZON_DAYS))
        fixtures = _upcoming(lg, today, events)
        league_info[lg.code] = _badge(lg, fixtures)
        tsdb_teams = {f.home_tsdb for f in fixtures} | {f.away_tsdb for f in fixtures}
        tsdb_teams |= {n for e, _, _ in finished(events) for n in (e.get("strHomeTeam"), e.get("strAwayTeam")) if n}
        names = match_names(sorted(tsdb_teams), _season_teams(hist, start))
        fresh = _fresh_results(lg, events, hist, names)
        if fresh:
            hist = sorted(hist + fresh, key=lambda m: m.date)
        country = form.league_country(lg.code)
        book.add_rows(country, hist)
        for shown, fd in names.items():
            book.names.setdefault(f"{country}|{fd}", shown)
        params = load_params()
        lm = fit_league(hist, today, params, include_ref_day=True, season_teams=_season_teams(hist, start))
        league_models[lg.code] = lm
        model = lm.goals
        quality = {t: a - d for t, a, d in model.ratings()}  # attaque moins défense : sert à choisir le match à la une
        n_ok = 0
        for f in fixtures:
            h, a = names.get(f.home_tsdb), names.get(f.away_tsdb)
            if not (h and a and model.knows(h) and model.knows(a)):
                report["unmatched"].append(f"{lg.code}: {f.home_tsdb} - {f.away_tsdb}")
                continue
            row = next((r for r in odds_rows if r.league == lg.code and r.home == h and r.away == a
                        and abs((r.date - f.kickoff_utc.date()).days) <= 1), None)
            odds = _odds_markets(row) if row else {}
            # Avec les cotes, le moteur mélange son analyse et celle du marché (poids appris sur le passé,
            # voir football/engine.py et docs/05-fiabilite.md), puis en déduit tous les autres marchés.
            o12 = [odds[("1x2", None)][k]["avg"] for k in ("1", "X", "2")] if ("1x2", None) in odds else None
            ou = odds.get(("ou", 2.5))
            oou = [ou["over"]["avg"], ou["under"]["avg"]] if ou else None
            an = analyse(lm, h, a, o12, oou, params)
            matches.append(_match_dict(lg, f, h, a, an.pred, an.model_pred, an.source, quality[h] + quality[a],
                                       an.confidence, _priced(an.pred, odds), an.factors, an.counts,
                                       params.version))
            n_ok += 1
        report["leagues"][lg.code] = {"fixtures": len(fixtures), "predicted": n_ok, "train_matches": model.n_matches,
                                      "fresh_results": len(fresh), "engine": params.version,
                                      "shots": lm.xg is not None, "corners": lm.corners is not None,
                                      "cards": lm.cards is not None,
                                      "rho": round(model.rho, 3), "home_adv": round(model.home_adv, 3),
                                      "first_half_share": round(model.first_half_share, 3)}
        if verbose:
            extra = f", dont {len(fresh)} résultats tout récents" if fresh else ""
            print(f"  {lg.code:>3} {lg.name_fr:<15} {n_ok}/{len(fixtures)} matchs analysés "
                  f"({model.n_matches} matchs d'entraînement{extra})")
    _run_linked("europe", men_cups, [lg for lg in leagues if lg.category == "europe"], today, matches, report,
                league_info, verbose, league_models, book)
    _run_linked("world", world, [lg for lg in leagues if lg.category == "world"], today, matches, report,
                league_info, verbose, book=book)
    _run_linked("women", women, [lg for lg in leagues if lg.category == "women"], today, matches, report,
                league_info, verbose, book=book)
    report["form"] = form.attach(matches, book)
    if verbose:
        print(f"  Forme et face-à-face : {report['form']}/{len(matches)} matchs")
    matches.sort(key=lambda m: m["kickoff"])
    return {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "leagues": league_info, "matches": matches, "report": report}


def _top_scores(pred: Prediction, n: int) -> list[list]:
    ft = pred.ft
    cells = sorted(((float(ft[h, a]), h, a) for h in range(6) for a in range(6)), reverse=True)[:n]
    return [[f"{h}-{a}", round(p, 4)] for p, h, a in cells]
