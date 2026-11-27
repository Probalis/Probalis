"""« Le mot de Probalis » : trois phrases tirées des chiffres d'un match, en haut de la fiche (mise à niveau 2, 27/11/2026).

- le meilleur angle : le premier des paris du match (core.verdicts.picks) ;
- le risque principal : la façon la plus probable dont ce meilleur angle peut perdre, avec sa chance ;
- à éviter : le pari tentant qui est en réalité presque pile ou face (la victoire du favori, les deux équipes
  marquent, plus de 2,5 buts), sinon le score exact (même le plus probable arrive rarement).

Rien n'est inventé : chaque phrase reprend une probabilité de l'analyse. Le même code sert au site et au test de
fiabilité (football/tune.py, « _mot » du tableau de fiabilité).
"""
from __future__ import annotations

import math

from . import verdicts as vd

FAV_SHAKY = 0.55     # sous cette chance, la victoire du favori est « à éviter »
COIN = (0.45, 0.55)  # « presque pile ou face »


def _find(markets: list[dict], key: str, line=None) -> dict | None:
    return next((m for m in markets if m["key"] == key and m.get("line") == line), None)


def _p(markets: list[dict], key: str, sel: str, line=None) -> float | None:
    m = _find(markets, key, line)
    return m["sel"][sel]["p"] if m and sel in m["sel"] else None


def risk(markets: list[dict], v: dict) -> dict | None:
    """La façon la plus probable dont le verdict `v` peut perdre : {"k", "p", ...} (voir i18n.mot_risk)."""
    fam, yes = v["fam"], v["yes"]
    x12 = _find(markets, "1x2")
    if fam == "win" and x12:
        side = v["side"]
        if not yes:  # « X gagne ? NON » perd si X gagne
            return {"k": "win", "side": side, "p": x12["sel"][side]["p"]}
        other = "2" if side == "1" else "1"
        px, po = x12["sel"]["X"]["p"], x12["sel"][other]["p"]
        return {"k": "draw", "p": px} if px >= po else {"k": "win", "side": other, "p": po}
    if fam == "dc" and x12:
        miss = next(s for s in ("1", "X", "2") if s not in v["sel"])
        if not yes:
            return None
        return {"k": "draw", "p": x12["sel"]["X"]["p"]} if miss == "X" else \
            {"k": "win", "side": miss, "p": x12["sel"][miss]["p"]}
    if fam.startswith("ou"):
        n = math.floor(v["line"])
        return {"k": "goals_max", "n": n, "p": 1 - v["p"]} if yes else {"k": "goals_min", "n": n + 1, "p": 1 - v["p"]}
    if fam == "btts":
        if not yes:
            return {"k": "btts", "p": 1 - v["p"]}
        blank = [(1 - p, s) for s in ("1", "2") if (p := _p(markets, f"tt{s}", "over", 0.5)) is not None]
        if not blank:
            return {"k": "btts_no", "p": 1 - v["p"]}
        p, s = max(blank)
        return {"k": "blank", "side": s, "p": p}
    if fam == "tt":
        side = v["key"][-1]
        return {"k": "blank", "side": side, "p": 1 - v["p"]} if yes else {"k": "scores", "side": side, "p": 1 - v["p"]}
    if fam in ("co", "ca"):
        n = math.floor(v["line"])
        k = "corners" if fam == "co" else "cards"
        return {"k": f"{k}_max", "n": n, "p": 1 - v["p"]} if yes else {"k": f"{k}_min", "n": n + 1, "p": 1 - v["p"]}
    return None


def avoid(markets: list[dict], vs: list[dict], picks: list[int]) -> dict | None:
    """Le pari tentant qui est presque pile ou face ; à défaut, le score exact le plus probable."""
    taken = {vs[i]["fam"] for i in picks}
    x12 = _find(markets, "1x2")
    if x12 and "win" not in taken:
        fav = "1" if x12["sel"]["1"]["p"] >= x12["sel"]["2"]["p"] else "2"
        p = x12["sel"][fav]["p"]
        if p < FAV_SHAKY:
            return {"k": "fav", "side": fav, "p": p}
    for fam, key, sel, line in (("btts", "btts", "yes", None), ("ou2.5", "ou", "over", 2.5)):
        p = _p(markets, key, sel, line)
        if p is not None and fam not in taken and COIN[0] <= p <= COIN[1]:
            return {"k": "coin", "fam": fam, "key": key, "sel": sel, "line": line, "p": p}
    sc = _find(markets, "score")
    if sc:
        s = max((s for s in sc["sel"] if s != "other"), key=lambda s: sc["sel"][s]["p"], default=None)
        if s:
            return {"k": "score", "score": s, "p": sc["sel"][s]["p"]}
    return None


def mot(markets: list[dict]) -> dict:
    """{"angle": verdict ou None, "risk": dict ou None, "avoid": dict ou None}."""
    vs = vd.verdicts(markets)
    pk = vd.picks(vs)
    angle = vs[pk[0]] if pk else None
    return {"angle": angle, "risk": risk(markets, angle) if angle else None, "avoid": avoid(markets, vs, pk)}


def happened(r: dict, hg: int, ag: int, stats: dict | None = None) -> bool | None:
    """Le risque ou le pari « à éviter » `r` s'est-il produit ? (None si on ne connaît pas le chiffre)"""
    k, t = r["k"], hg + ag
    res = "1" if hg > ag else ("X" if hg == ag else "2")
    if k == "draw":
        return res == "X"
    if k in ("win", "fav"):
        return res == r["side"]
    if k == "goals_max":
        return t <= r["n"]
    if k == "goals_min":
        return t >= r["n"]
    if k == "btts":
        return hg > 0 and ag > 0
    if k == "btts_no":
        return not (hg > 0 and ag > 0)
    if k == "blank":
        return (hg if r["side"] == "1" else ag) == 0
    if k == "scores":
        return (hg if r["side"] == "1" else ag) > 0
    if k == "coin":
        return vd._outcome(r["key"], r["line"], r["sel"], hg, ag)
    if k == "score":
        return r["score"] == f"{hg}-{ag}"
    for name in ("corners", "cards"):
        if k.startswith(name):
            pair = (stats or {}).get(name)
            if not pair:
                return None
            tot = pair[0] + pair[1]
            return tot <= r["n"] if k.endswith("_max") else tot >= r["n"]
    return None
