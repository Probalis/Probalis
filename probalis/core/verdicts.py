"""Verdicts « OUI / NON » d'un match, tirés de ses marchés, et leur règlement.

Chaque verdict répond à une question simple (« Plus de 2,5 buts ? », « Les deux équipes marquent ? »…) :
- sel / key / line : la sélection qui correspond au « OUI » de la question ;
- yes : True si le moteur répond OUI, False s'il répond NON ;
- p : la probabilité que la réponse donnée soit la bonne ;
- open : True quand c'est trop serré pour trancher (moins de OPEN_BELOW).
Le même code sert au site (fiche match, historique) et aux tests de fiabilité (football/tune.py).

La fiche ne montre que les « paris du match » (picks, depuis le 27/11/2026, demandé par le porteur du projet : trop de
verdicts à 1,10 embrouillaient) : au plus PICK_MAX verdicts, de types différents, avec au moins PICK_MIN_P de chance et
une cote estimée chez le bookmaker d'au moins PICK_MIN_ODDS, au plus un sur les corners ou les cartons.
"""
from __future__ import annotations

OPEN_BELOW = 0.55
GOAL_LINES = (1.5, 2.5, 3.5)
CORNER_LINES = (8.5, 9.5, 10.5)
CARD_LINES = (3.5, 4.5)
MIN_CELL = 30  # verdicts comparables nécessaires pour s'appuyer sur le passé

BOOK_MARGIN = 0.05     # cote « bookmaker » estimée = cote juste / 1,05 (marge moyenne d'un marché classique)
PICK_MAX = 3
PICK_MIN_P = 0.60
PICK_MIN_ODDS = 1.30   # soit une chance d'au plus 73,2 %
# Types de paris : jamais deux du même type parmi les paris du match (corners et cartons comptent pour un seul)
PICK_GROUP = {"win": "result", "dc": "result", "ou1.5": "goals", "ou2.5": "goals", "ou3.5": "goals",
              "btts": "btts", "tt": "team", "co": "counts", "ca": "counts"}


def _find(markets: list[dict], key: str, line=None) -> dict | None:
    return next((m for m in markets if m["key"] == key and m.get("line") == line), None)


def _yn(fam: str, key: str, line, sel: str, p_yes: float, **extra) -> dict:
    yes = p_yes >= 0.5
    p = p_yes if yes else 1 - p_yes
    return {"fam": fam, "key": key, "line": line, "sel": sel, "yes": yes, "p": round(p, 4),
            "open": p < OPEN_BELOW, **extra}


def verdicts(markets: list[dict]) -> list[dict]:
    """Les verdicts d'un match, dans l'ordre d'affichage."""
    out = []
    x12 = _find(markets, "1x2")
    if x12:
        s = x12["sel"]
        fav = "1" if s["1"]["p"] >= s["2"]["p"] else "2"
        out.append(_yn("win", "1x2", None, fav, s[fav]["p"], side=fav))
    dc = _find(markets, "dc")
    if dc:
        sel = max(dc["sel"], key=lambda k: dc["sel"][k]["p"])
        out.append(_yn("dc", "dc", None, sel, dc["sel"][sel]["p"]))
    for line in GOAL_LINES:
        ou = _find(markets, "ou", line)
        if ou:
            out.append(_yn(f"ou{line}", "ou", line, "over", ou["sel"]["over"]["p"]))
    bt = _find(markets, "btts")
    if bt:
        out.append(_yn("btts", "btts", None, "yes", bt["sel"]["yes"]["p"]))
    for side in ("1", "2"):
        tt = _find(markets, f"tt{side}", 0.5)
        if tt:
            out.append(_yn("tt", f"tt{side}", 0.5, "over", tt["sel"]["over"]["p"], side=side))
    for fam, key, lines in (("co", "co", CORNER_LINES), ("ca", "ca", CARD_LINES)):
        cands = [m for ln in lines if (m := _find(markets, key, ln))]
        if cands:
            m = max(cands, key=lambda m: abs(m["sel"]["over"]["p"] - 0.5))
            out.append(_yn(fam, key, m["line"], "over", m["sel"]["over"]["p"]))
    return out


def band(p: float) -> int:
    """Tranche de 5 points : 14 = 70 à 75 %."""
    return min(19, max(0, int(p * 20)))


def record(rel: dict, v: dict) -> tuple[int, int] | None:
    """(nombre, réussis) des verdicts comparables dans le tableau de fiabilité, s'il y en a assez."""
    cell = ((rel or {}).get(v["fam"]) or {}).get(str(band(v["p"])))
    if not cell or cell[0] < MIN_CELL:
        return None
    return int(cell[0]), int(cell[1])


def expected(rel: dict, v: dict) -> float:
    """Chance de réussite attendue : l'annonce, corrigée par ce qui s'est vraiment passé sur les verdicts
    comparables (avec un peu de prudence quand ils sont peu nombreux)."""
    r = record(rel, v)
    if not r:
        return v["p"] - 0.02
    n, won = r
    return (won + 10 * v["p"]) / (n + 10)


def best(vs: list[dict], rel: dict) -> dict | None:
    """Le verdict le plus sûr du match, toutes cotes confondues (règle d'avant le 27/11/2026, gardée pour les tests)."""
    cands = [v for v in vs if not v["open"]]
    if not cands:
        return None
    return max(cands, key=lambda v: expected(rel, v))


def book_odds(p: float) -> float:
    """Cote estimée chez le bookmaker pour une chance p : cote juste (1 / p) divisée par 1 + marge (comme
    site/picks.book_odds, onglets Paris et Ticket)."""
    return (1 / p) / (1 + BOOK_MARGIN) if p > 0 else 0.0


def picks(vs: list[dict]) -> list[int]:
    """Les paris du match : positions dans `vs`, le plus sûr d'abord (chance annoncée la plus haute)."""
    cands = sorted((i for i, v in enumerate(vs)
                    if not v["open"] and v["p"] >= PICK_MIN_P and book_odds(v["p"]) >= PICK_MIN_ODDS - 1e-9),
                   key=lambda i: (-vs[i]["p"], i))
    out, groups = [], set()
    for i in cands:
        g = PICK_GROUP.get(vs[i]["fam"], vs[i]["fam"])
        if g in groups:
            continue
        out.append(i)
        groups.add(g)
        if len(out) == PICK_MAX:
            break
    return out


def _outcome(key: str, line, sel: str, hg: int, ag: int) -> bool:
    t = hg + ag
    if key == "1x2":
        r = "1" if hg > ag else ("X" if hg == ag else "2")
        return r == sel
    if key == "dc":
        r = "1" if hg > ag else ("X" if hg == ag else "2")
        return r in sel
    if key == "ou":
        return t > line
    if key == "btts":
        return hg > 0 and ag > 0
    if key == "tt1":
        return hg > line
    if key == "tt2":
        return ag > line
    raise KeyError(key)


def settle(v: dict, hg: int | None, ag: int | None, stats: dict | None = None) -> str | None:
    """"won" ou "lost" ; None si on ne connaît pas encore le chiffre (score, corners, cartons)."""
    if v["key"] in ("co", "ca"):
        pair = (stats or {}).get("corners" if v["key"] == "co" else "cards")
        if not pair:
            return None
        happened = pair[0] + pair[1] > v["line"]
    else:
        if hg is None or ag is None:
            return None
        happened = _outcome(v["key"], v["line"], v["sel"], hg, ag)
    return "won" if happened == v["yes"] else "lost"
