"""Usage : python -m probalis.football.tendance_grands (résultats : docs/05-fiabilite.md)

Test ciblé de l'idée : « quand les grandes équipes peinent dans les matchs de la journée,
elles peinent aussi le soir, et les petites équipes marquent ».

Différences avec probalis/football/tendance.py (test du 19/11) :
- tous les championnats ensemble (la journée entière, pas un seul championnat) ;
- seulement les matchs avec un vrai favori (au moins 55 % de chances d'après les cotes) ;
- mesures centrées sur l'idée : victoire du favori, buts de l'outsider, l'outsider marque ;
- la référence = cotes moyennes relevées AVANT la journée (colonnes Avg), donc sans la « tendance ».
Journée = date ; matchs de la journée = coup d'envoi jusqu'à 15 h (heure anglaise) ;
matchs du soir = coup d'envoi à partir de 17 h 30 (les matchs de 15 h sont finis).
"""
import csv
import io
import math
import random
from collections import defaultdict

from ..core.implied import implied_rates
from ..core.value import devig_power
from .data import CACHE

CODES = ("E0", "E1", "E2", "E3", "EC", "SP1", "SP2", "I1", "D1", "F1", "F2", "N1", "P1", "B1", "T1", "G1", "SC0")
SEASONS = ("2122", "2223", "2324", "2425", "2526", "2627")
FAV_MIN = 0.55
EARLY_MAX = 15 * 60
LATE_MIN = 17 * 60 + 30


def f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


rows = []
for code in CODES:
    for season in SEASONS:
        path = CACHE / f"{code}_{season}.csv"
        if not path.exists():
            continue
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        for r in csv.DictReader(io.StringIO(text)):
            t, d = (r.get("Time") or "").strip(), (r.get("Date") or "").strip()
            hg, ag = f(r.get("FTHG")), f(r.get("FTAG"))
            o = [f(r.get(k)) for k in ("AvgH", "AvgD", "AvgA")]
            oo, ou = f(r.get("Avg>2.5")), f(r.get("Avg<2.5"))
            if not (t and d and ":" in t and hg is not None and ag is not None and all(o)):
                continue
            if min(o) <= 1.01 or (oo and oo <= 1.01) or (ou and ou <= 1.01):
                continue
            try:
                p = devig_power(o)
                p_over = devig_power([oo, ou])[0] if (oo and ou) else None
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            home_fav = p[0] >= p[2]
            pf = max(p[0], p[2])
            if pf < FAV_MIN:
                continue
            try:
                lam, mu = implied_rates(p, 0.0, p_over)
            except Exception:
                continue
            dog_rate = mu if home_fav else lam
            fav_g, dog_g = (hg, ag) if home_fav else (ag, hg)
            dd, mm, yy = d.split("/")
            day = (int(yy) + (2000 if len(yy) == 2 else 0), int(mm), int(dd))
            hh, mi = t.split(":")[:2]
            rows.append({"day": day, "min": int(hh) * 60 + int(mi), "code": code,
                         "fav": float(fav_g > dog_g) - pf,
                         "dog_goals": dog_g - dog_rate,
                         "dog_scored": float(dog_g > 0) - (1 - math.exp(-dog_rate))})

days = defaultdict(list)
for r in rows:
    days[r["day"]].append(r)

KEYS = (("fav", "Favori qui gagne (points de %)", 100), ("dog_goals", "Buts de l'outsider", 1),
        ("dog_scored", "L'outsider marque (points de %)", 100))
pairs = []  # (moyenne de la journée, match du soir, jour)
for day, ms in days.items():
    early = [m for m in ms if m["min"] <= EARLY_MAX]
    late = [m for m in ms if m["min"] >= LATE_MIN]
    if len(early) < 3 or not late:
        continue
    mean = {k: sum(e[k] for e in early) / len(early) for k, _, _ in KEYS}
    pairs += [(mean, m, day) for m in late]

print(f"{len(rows)} matchs avec un vrai favori (>= {FAV_MIN:.0%}), {len(SEASONS)} saisons, {len(CODES)} championnats")
print(f"{len({p[2] for p in pairs})} journées avec au moins 3 matchs en journée ; {len(pairs)} matchs du soir comparés\n")


def corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return sxy / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))


rng = random.Random(7)
by_day = defaultdict(list)
for i, (_, _, day) in enumerate(pairs):
    by_day[day].append(i)
day_keys = list(by_day)


def boot(stat, n=500):
    vals = []
    for _ in range(n):
        idx = [i for dk in (rng.choice(day_keys) for _ in day_keys) for i in by_day[dk]]
        vals.append(stat(idx))
    vals.sort()
    return vals[int(0.025 * n)], vals[int(0.975 * n) - 1]


for k, label, scale in KEYS:
    xs = [e[k] for e, _, _ in pairs]
    ys = [m[k] for _, m, _ in pairs]
    c = corr(xs, ys)
    lo, hi = boot(lambda idx: corr([xs[i] for i in idx], [ys[i] for i in idx]))
    print(f"{label} : corrélation journée -> soir {c:+.3f} (95 % : {lo:+.3f} à {hi:+.3f})")

print("\nJournées où les favoris ont PEINÉ (au moins 15 points sous les cotes en moyenne)")
print("comparées aux journées où ils ont bien tenu (au moins 15 points au-dessus) :")
for k, label, scale in KEYS:
    bad = [i for i, (e, _, _) in enumerate(pairs) if e["fav"] <= -0.15]
    good = [i for i, (e, _, _) in enumerate(pairs) if e["fav"] >= 0.15]
    mb = sum(pairs[i][1][k] for i in bad) / len(bad)
    mg = sum(pairs[i][1][k] for i in good) / len(good)
    lo, hi = boot(lambda idx: (lambda b: sum(pairs[i][1][k] for i in b) / max(len(b), 1))(
        [i for i in idx if pairs[i][0]["fav"] <= -0.15]))
    unit = "pt" if scale == 100 else "but"
    print(f"  {label} le soir : jours difficiles {mb * scale:+.2f} {unit} ({len(bad)} matchs, 95 % : "
          f"{lo * scale:+.2f} à {hi * scale:+.2f}) | jours faciles {mg * scale:+.2f} {unit} ({len(good)} matchs)")

today = days.get((2026, 11, 21), [])
if today:
    e = [m for m in today if m["min"] <= EARLY_MAX]
    l = [m for m in today if m["min"] >= LATE_MIN]
    print(f"\nAujourd'hui (21/11/2026) dans nos fichiers : {len(e)} matchs de journée avec un vrai favori, "
          f"{len(l)} matchs du soir")
    if e:
        print(f"  journée : favori {100 * sum(m['fav'] for m in e) / len(e):+.1f} pts, outsider "
              f"{sum(m['dog_goals'] for m in e) / len(e):+.2f} but par rapport aux cotes")
    if l:
        print(f"  soir    : favori {100 * sum(m['fav'] for m in l) / len(l):+.1f} pts, outsider "
              f"{sum(m['dog_goals'] for m in l) / len(l):+.2f} but par rapport aux cotes")
