"""Paris du jour : les plus sûrs de chaque niveau, les coupons du jour, et le règlement des paris (historique).

Règles (les mêmes pour les matchs à venir, l'historique et la simulation sur 2025/26) :
- marchés classiques seulement, faciles à trouver chez tous les bookmakers et réglés sur le score final :
  1X2, double chance, plus/moins de 1,5 / 2,5 / 3,5 buts, les deux équipes marquent, une équipe marque (1 ou 2 buts) ;
- jamais de match à faible confiance ni de football féminin (trop peu de données ; règle gardée même quand
  The Odds API donne les cotes de la Ligue des champions féminine ou de la Frauen-Bundesliga) ;
- un seul pari par match dans chaque liste, et pas plus de deux paris du même type parmi les cinq ;
- cote « bookmaker » estimée = cote juste moins une marge de 5 % (marge moyenne d'un marché classique).
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from ..football.leagues import BY_CODE

# Jour « Probalis » : heure d'Afrique de l'Ouest et d'Europe centrale en hiver (UTC+1).
DAY_TZ = timezone(timedelta(hours=1))
BOOK_MARGIN = 0.05
N_PICKS = 5

STANDARD = (("1x2", None, ("1", "2")), ("dc", None, ("1X", "X2", "12")),
            ("ou", 1.5, ("over", "under")), ("ou", 2.5, ("over", "under")), ("ou", 3.5, ("over", "under")),
            ("btts", None, ("yes", "no")), ("tt1", 0.5, ("over",)), ("tt2", 0.5, ("over",)),
            ("tt1", 1.5, ("over",)), ("tt2", 1.5, ("over",)))
# Corners et cartons : seulement au Ticket (pas dans les paris du jour, tant que l'historique n'a pas montré leur fiabilité)
COUNTS = (("co", 8.5, ("over", "under")), ("co", 9.5, ("over", "under")), ("co", 10.5, ("over", "under")),
          ("ca", 3.5, ("over", "under")), ("ca", 4.5, ("over", "under")))
FAMILY = {"1x2": "result", "dc": "dc", "ou": "goals", "btts": "btts", "tt1": "team", "tt2": "team",
          "co": "corners", "ca": "cards"}

# Niveaux : fourchette de probabilité (cote juste ≈ 1,25–1,47 / 1,47–1,82 / 2–2,8)
TIERS = {"safe": (0.68, 0.80), "balanced": (0.55, 0.68), "bold": (0.36, 0.50)}
COUPON_TARGETS = (2, 3, 5)


def day_key(kickoff: str | datetime) -> str:
    ko = datetime.fromisoformat(kickoff) if isinstance(kickoff, str) else kickoff
    return ko.astimezone(DAY_TZ).date().isoformat()


def book_odds(fair: float) -> float:
    """Cote qu'un bookmaker propose en général pour une cote juste donnée (marge d'environ 5 %)."""
    return fair / (1 + BOOK_MARGIN)


def eligible(m: dict) -> bool:
    lg = BY_CODE.get(m["league"])
    return bool(lg) and lg.category != "women" and m.get("confidence") != "low"


def _find(m: dict, key: str, line) -> dict | None:
    return next((mk for mk in m["markets"] if mk["key"] == key and mk.get("line") == line), None)


def pick_id(mid: str, key: str, line, sel: str) -> str:
    return f"{mid}|{key}|{'' if line is None else line}|{sel}"


def candidates(m: dict, counts: bool = False) -> list[dict]:
    """Paris classiques d'un match, avec leur probabilité et leur cote juste (counts : corners et cartons en plus)."""
    out = []
    for key, line, sels in STANDARD + (COUNTS if counts else ()):
        mk = _find(m, key, line)
        if not mk:
            continue
        for s in sels:
            v = mk["sel"].get(s)
            if not v or not v.get("p") or v["p"] <= 0.01 or v["p"] >= 0.995:
                continue
            p = float(v["p"])
            out.append({"id": pick_id(m["id"], key, line, s), "mid": m["id"], "key": key, "line": line, "sel": s,
                        "p": round(p, 4), "fair": round(1 / p, 3)})
    return out


def _score(c: dict, m: dict) -> float:
    """Classement dans un niveau : le plus probable d'abord, un léger bonus aux matchs à confiance élevée."""
    return c["p"] + (0.015 if m.get("confidence") == "high" else 0.0) - (0.01 if c["sel"] == "12" else 0.0)


def tier_picks(matches: list[dict], tier: str, n: int = N_PICKS, after: datetime | None = None) -> list[dict]:
    """Les n paris les plus sûrs d'un niveau (un par match, au plus deux du même type)."""
    lo, hi = TIERS[tier]
    pool = []
    for m in matches:
        if not eligible(m) or (after and datetime.fromisoformat(m["kickoff"]) <= after):
            continue
        for c in candidates(m):
            if lo <= c["p"] <= hi:
                pool.append((_score(c, m), c))
    pool.sort(key=lambda x: -x[0])
    used, fam, out = set(), {}, []
    for _, c in pool:
        f = FAMILY[c["key"]]
        if c["mid"] in used or fam.get(f, 0) >= 2:
            continue
        used.add(c["mid"])
        fam[f] = fam.get(f, 0) + 1
        out.append(c)
        if len(out) == n:
            break
    return out


# --- Coupons -----------------------------------------------------------------------------------------------

def coupon_stats(legs: list[dict]) -> dict:
    fair = math.prod(c["fair"] for c in legs)
    return {"p": round(math.prod(c["p"] for c in legs), 4), "fair": round(fair, 3),
            "book": round(fair / (1 + BOOK_MARGIN) ** len(legs), 3)}


def build_coupon(pool: list[dict], target: float, k: int, conf: dict | None = None) -> list[dict] | None:
    """Coupon de k matchs dont la cote bookmaker estimée tombe près de la cible, avec des sélections équilibrées.

    pool : paris possibles (plusieurs par match), conf : confiance par match (pénalise « moyenne »).
    """
    conf = conf or {}
    mids = {c["mid"] for c in pool}
    if len(mids) < k:
        return None
    goal = math.log(target * 1.04)   # un peu au-dessus de la cible : les bookmakers arrondissent vers le bas
    leg_fair = (target * 1.04 * (1 + BOOK_MARGIN) ** k) ** (1 / k)
    lf = math.log(leg_fair)

    def leg_cost(c):
        return (math.log(c["fair"]) - lf) ** 2 + (0.02 if conf.get(c["mid"]) != "high" else 0) \
            + (0.03 if c["sel"] == "12" else 0)

    def cost(legs):
        tot = sum(math.log(c["fair"]) for c in legs) - k * math.log(1 + BOOK_MARGIN)
        fams = [FAMILY[c["key"]] for c in legs]
        dup = len(fams) - len(set(fams))
        return 6 * abs(tot - goal) + sum(leg_cost(c) for c in legs) + 0.04 * dup

    best_per_match: dict[str, dict] = {}
    for c in pool:
        b = best_per_match.get(c["mid"])
        if b is None or leg_cost(c) < leg_cost(b):
            best_per_match[c["mid"]] = c
    legs = sorted(best_per_match.values(), key=leg_cost)[:k]
    cur = cost(legs)
    for _ in range(60):
        improved = None
        for i in range(k):
            others = {c["mid"] for j, c in enumerate(legs) if j != i}
            for c in pool:
                if c["mid"] in others or c is legs[i]:
                    continue
                trial = legs[:i] + [c] + legs[i + 1:]
                t = cost(trial)
                if t < cur - 1e-9 and (improved is None or t < improved[0]):
                    improved = (t, trial)
        if not improved:
            break
        cur, legs = improved
    st = coupon_stats(legs)
    if not (0.9 * target <= st["book"] <= 1.35 * target):
        return None
    return sorted(legs, key=lambda c: c["mid"])


def day_coupons(matches: list[dict], after: datetime | None = None) -> list[dict]:
    """Coupons du jour (cote ≈ 2, 3 et 5) : le moins de matchs possible, chaque sélection à 50 % ou plus."""
    pool, conf, kos = [], {}, {}
    for m in matches:
        if not eligible(m) or (after and datetime.fromisoformat(m["kickoff"]) <= after):
            continue
        conf[m["id"]] = m.get("confidence")
        kos[m["id"]] = m["kickoff"]
        pool += [c for c in candidates(m) if 0.4 <= c["p"] <= 0.9]
    out = []
    for target in COUPON_TARGETS:
        chosen = None
        for k in range(2, 7):
            legs = build_coupon(pool, target, k, conf)
            if legs is None:
                continue
            chosen = legs
            if min(c["p"] for c in legs) >= 0.5:
                break
        if chosen:
            chosen = sorted(chosen, key=lambda c: kos[c["mid"]])
            out.append({"target": target, "legs": chosen, **coupon_stats(chosen)})
    return out


# --- Règlement (historique) ----------------------------------------------------------------------------------

def settle(key: str, line, sel: str, hg: int, ag: int) -> str:
    """Résultat d'un pari sur le score final : 'won', 'lost' ou 'void' (remboursé)."""
    tot = hg + ag
    if key == "1x2":
        ok = {"1": hg > ag, "X": hg == ag, "2": ag > hg}[sel]
    elif key == "dc":
        ok = {"1X": hg >= ag, "X2": ag >= hg, "12": hg != ag}[sel]
    elif key == "dnb":
        if hg == ag:
            return "void"
        ok = (hg > ag) if sel == "1" else (ag > hg)
    elif key == "ou":
        if tot == line:
            return "void"
        ok = tot > line if sel == "over" else tot < line
    elif key == "btts":
        ok = (hg > 0 and ag > 0) == (sel == "yes")
    elif key in ("tt1", "tt2"):
        g = hg if key == "tt1" else ag
        if g == line:
            return "void"
        ok = g > line if sel == "over" else g < line
    else:
        raise ValueError(key)
    return "won" if ok else "lost"


def coupon_result(states: list[str | None]) -> str | None:
    """Un coupon est perdu dès qu'une sélection perd, gagné quand toutes sont gagnées (ou remboursées)."""
    if any(s == "lost" for s in states):
        return "lost"
    if any(s is None for s in states):
        return None
    return "void" if all(s == "void" for s in states) else "won"
