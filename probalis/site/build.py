"""Construit le site PWA statique dans public/ (une version française et une version anglaise).

Usage : python -m probalis build      (récupère les données, calcule, génère le site)
        python -m probalis serve      (aperçu local sur http://localhost:8000)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
import secrets
import shutil
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from ..core import verdicts as vd
from ..football.engine import load_params
from ..football.leagues import BY_CODE, LEAGUES
from . import config, explain, history, i18n, picks, qr, site_text
from .logos import Logos
from .lock import Locker
from .icons import GOOGLE_G, icon, logo_mark

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / "public"
HERE = Path(__file__).resolve().parent
BRAND = ROOT / "brand"

CREST_COLORS = ("#1F2937", "#15803D", "#0E7490", "#7C3AED", "#B45309", "#BE123C", "#1D4ED8", "#4D7C0F")
COMPARE_MARKETS = (("1x2", None), ("dc", None), ("dnb", None), ("ou", 1.5), ("ou", 2.5), ("ou", 3.5), ("btts", None),
                   ("co", 8.5), ("co", 9.5), ("co", 10.5), ("ca", 3.5), ("ca", 4.5))
RING = 2 * math.pi * 23  # anneau de probabilité (rayon 23 px) sur la page Paris
LEGAL_PAGES = (("confidentialite", "privacy_title"), ("conditions", "terms_title"),
               ("jeu-responsable", "responsible_page_title"))


LOGOS: Logos | None = None   # logos servis par notre site (voir logos.py), préparés au début de build()


def _img(url: str | None, size: str) -> str | None:
    """Logo : notre copie (/logos/…, 64 ou 128 px), sinon TheSportsDB (/tiny = 100 px, /small = 200 px)."""
    if LOGOS is not None:
        return LOGOS.src(url, size)
    return f"{url}/{size}" if url else None


def _crest(team: dict) -> dict:
    name = team["name"]
    words = [w for w in name.replace("-", " ").split() if w[0].isalnum()]
    initials = (words[0][:1] + (words[1][:1] if len(words) > 1 else words[0][1:2])).upper() if words else "?"
    color = CREST_COLORS[int(hashlib.md5(name.encode()).hexdigest(), 16) % len(CREST_COLORS)]
    badge = LOGOS.team_url(name, team.get("badge")) if LOGOS is not None else team.get("badge")
    return {"initials": initials, "color": color, "img": _img(badge, "tiny"), "img_lg": _img(badge, "small"),
            "dark": bool(LOGOS is not None and LOGOS.light(badge))}


def _league_badge(code: str, info: dict) -> tuple[str | None, bool]:
    """(adresse du logo, à afficher sur fond foncé ?) d'un championnat."""
    e = info.get(code) or {}
    url = LOGOS.league_url(code, e.get("badge")) if LOGOS is not None else e.get("badge")
    return url, bool(e.get("badge_on_dark")) or bool(LOGOS is not None and LOGOS.light(url))


def _logo_urls(data: dict, hist: dict) -> set[str]:
    """Tous les logos dont les pages auront besoin (matchs à venir, historique, championnats)."""
    lg = Logos() if LOGOS is None else LOGOS
    urls = set()
    teams = [t for m in data["matches"] for t in (m["home"], m["away"])]
    teams += [t for e in (hist.get("days") or {}).values() for mt in (e.get("matches") or {}).values()
              for t in (mt["home"], mt["away"])]
    for t in teams:
        urls.add(lg.team_url(t["name"], t.get("badge")))
    for code, e in (data.get("leagues") or {}).items():
        urls.add(lg.league_url(code, (e or {}).get("badge")))
    return {u for u in urls if u}


# --- Championnats : rubriques de la feuille « Championnats » et ordre d'affichage --------------------------

def category(lg) -> str:
    return getattr(lg, "category", None) or "domestic"


def league_sections() -> list[tuple[str, list]]:
    """Les plus suivis (5 premiers championnats), coupes d'Europe, autres championnats, divisions inférieures,
    féminin."""
    domestic = [lg for lg in LEAGUES if category(lg) == "domestic" and getattr(lg, "tier", 1) == 1]
    lower = [lg for lg in LEAGUES if category(lg) == "domestic" and getattr(lg, "tier", 1) != 1]
    europe = [lg for lg in LEAGUES if category(lg) == "europe"]
    women = [lg for lg in LEAGUES if category(lg) == "women"]
    other = [lg for lg in LEAGUES if category(lg) not in ("domestic", "europe", "women")]
    return [("popular", domestic[:5]), ("europe", europe), ("others", domestic[5:] + other), ("lower", lower),
            ("women", women)]


def _section_of() -> dict[str, str]:
    return {lg.code: key for key, lgs in league_sections() for lg in lgs}


def _league_view(lg, lang: str, info: dict, count: int) -> dict:
    fr = lang == "fr"
    name = lg.name_fr if fr else lg.name_en
    country = lg.country_fr if fr else lg.country_en
    badge, dark = _league_badge(lg.code, info)
    words = [w for w in name.replace("-", " ").split() if w[:1].isalnum()]
    return {"code": lg.code, "name": name, "country": country, "logo": _img(badge, "tiny"),
            "on_dark": dark,
            "initials": "".join(w[0] for w in words[:2]).upper() or "?", "count": count,
            "search": i18n.fold(f"{name} {country} {lg.name_en} {lg.country_en} {lg.name_fr} {lg.country_fr}")}


# --- Vues d'un match ------------------------------------------------------------------------------------

def _level(p: float) -> str:
    return "hi" if p >= 0.7 else "mid" if p >= 0.5 else "lo"


def _sel_view(m: dict, mk: dict, key_sel: str, lang: str) -> dict:
    s = mk["sel"][key_sel]
    line = mk.get("line")
    return {
        "label": i18n.selection_label(mk["key"], key_sel, line, lang, m["home"]["name"], m["away"]["name"]),
        "p": s["p"], "pct": i18n.pct(s["p"], lang), "w": round(min(max(s["p"], 0), 1) * 100, 1), "level": _level(s["p"]),
        "fair": i18n.odds(s["fair"], lang) if s.get("fair") and s["fair"] < 1000 else "—",
        "push": i18n.pct(s["pu"], lang) if s.get("pu") else None,
    }


def _market_view(m: dict, mk: dict, lang: str) -> dict:
    sels = list(mk["sel"])
    is_score = mk["key"] in ("score", "score_1h", "score_2h")
    if is_score:
        sels = sorted((s for s in sels if s != "other"), key=lambda s: -mk["sel"][s]["p"])[:12] + ["other"]
    return {"title": i18n.market_title(mk["key"], mk.get("line"), lang, m["home"]["name"], m["away"]["name"]),
            "rows": [_sel_view(m, mk, s, lang) for s in sels], "tiles": is_score,
            "free": mk["key"] in config.FREE_MARKETS}


def _find(m: dict, key: str, line=None) -> dict | None:
    return next((mk for mk in m["markets"] if mk["key"] == key and mk.get("line") == line), None)


def _key_markets(m: dict, lang: str) -> list[dict]:
    """Les six marchés du résumé : double chance du favori, buts, les deux marquent, l'outsider marque, la pause."""
    t = i18n.UI[lang]
    home, away = m["home"]["name"], m["away"]["name"]
    x12 = _find(m, "1x2")["sel"]
    fav_home = x12["1"]["p"] >= x12["2"]["p"]
    out = []

    def add(key, line, sel, label=None, market=None):
        mk = _find(m, key, line)
        if not mk or sel not in mk["sel"]:
            return
        sv = _sel_view(m, mk, sel, lang)
        out.append({**sv, "label": label or sv["label"], "free": key in config.FREE_MARKETS,
                    "market": market or i18n.market_title(key, line, lang, home, away)})

    def most(key, line=None):
        sel = _find(m, key, line)["sel"]
        return max(sel, key=lambda k: sel[k]["p"])

    add("dc", None, "1X" if fav_home else "X2")
    for line, sel in ((1.5, "over"), (2.5, most("ou", 2.5))):
        add("ou", line, sel, label=f"{i18n.selection_label('ou', sel, line, lang, home, away)} {t['goals_word']}",
            market=t["total_goals"])
    add("btts", None, most("btts"))
    underdog = away if fav_home else home
    add("tt2" if fav_home else "tt1", 0.5, "over", label=t["team_scores"].format(team=underdog),
        market=t["goals_of"].format(team=underdog))
    ht = most("1x2_1h")
    add("1x2_1h", None, ht, market=t["first_half"],
        label=t["ht_draw"] if ht == "X" else t["ht_lead"].format(team=home if ht == "1" else away))
    return out


def _season_label(code: str | None) -> str:
    return f"20{code[:2]}/{code[2:]}" if code and len(code) == 4 else ""


def verdict_question(v: dict, lang: str, home: str, away: str) -> str:
    t = i18n.UI[lang]
    fam = v["fam"]
    if fam == "win":
        return t["vd_q_win"].format(team=home if v["sel"] == "1" else away)
    if fam == "dc":
        return t["vd_q_dc"].format(sel=i18n.selection_label("dc", v["sel"], None, lang, home, away))
    if fam.startswith("ou"):
        return t["vd_q_ou"].format(line=i18n.line_txt(v["line"], lang))
    if fam == "btts":
        return t["vd_q_btts"]
    if fam == "tt":
        return t["vd_q_tt"].format(team=home if v["key"] == "tt1" else away)
    if fam in ("co", "ca"):
        return t[f"vd_q_{fam}"].format(line=i18n.line_txt(v["line"], lang))
    return fam


def verdict_answer(v: dict, lang: str) -> tuple[str, str]:
    """(texte, classe) : OUI / NON / SERRÉ."""
    t = i18n.UI[lang]
    if v.get("open"):
        return t["vd_open"], "open"
    return (t["vd_yes"], "yes") if v["yes"] else (t["vd_no"], "no")


def _live_verdict(v: dict, live: tuple | None) -> str | None:
    """« won » / « lost » si le verdict est déjà joué pendant le match (score en direct), sinon None."""
    if not live or v.get("open") or v["key"] in ("co", "ca"):  # corners et cartons : pas de chiffres en direct
        return None
    return history.live_result(lambda h, a: vd.settle(v, h, a), *live)


def _verdicts_view(m: dict, lang: str, live: tuple | None = None) -> dict:
    """Les verdicts OUI / NON de la fiche, et le plus sûr avec sa preuve (verdicts comparables du passé).
    live : score en direct du match en cours ; les verdicts déjà joués d'avance portent « Déjà validé / perdu »."""
    t = i18n.UI[lang]
    home, away = m["home"]["name"], m["away"]["name"]
    params = load_params()
    rel = params.reliability
    vs = vd.verdicts(m["markets"])
    best = vd.best(vs, rel)
    rows = []
    for v in vs:
        ans, cls = verdict_answer(v, lang)
        rows.append({"q": verdict_question(v, lang, home, away), "ans": ans, "cls": cls,
                     "pct": i18n.pct(v["p"], lang), "w": round(min(max(v["p"], 0), 1) * 100, 1),
                     "level": _level(v["p"]), "best": v is best, "live": _live_verdict(v, live)})
    top = None
    if best:
        ans, cls = verdict_answer(best, lang)
        rec = vd.record(rel, best)
        if rec:
            proof = t["vd_proof"].format(won=i18n.num(rec[1], lang, 0), n=i18n.num(rec[0], lang, 0),
                                         rate=i18n.pct(rec[1] / rec[0], lang),
                                         season=_season_label((params.meta or {}).get("test")))
        else:
            proof = t["vd_proof_none"].format(pct=i18n.pct(best["p"], lang), miss=max(1, round((1 - best["p"]) * 10)))
        top = {"q": verdict_question(best, lang, home, away), "ans": ans, "cls": cls,
               "pct": i18n.pct(best["p"], lang), "proof": proof, "live": _live_verdict(best, live)}
    counts = m.get("counts") or {}
    counts_txt = None
    if counts.get("corners") and counts.get("cards"):
        counts_txt = t["counts_line"].format(h=i18n.num(counts["corners"][0], lang, 1),
                                             a=i18n.num(counts["corners"][1], lang, 1),
                                             ch=i18n.num(counts["cards"][0], lang, 1),
                                             ca=i18n.num(counts["cards"][1], lang, 1))
    lg = BY_CODE.get(m["league"])
    none_txt = t["counts_none_cup" if lg and lg.category == "europe" else "counts_none"]
    return {"rows": rows, "top": top, "counts_txt": counts_txt, "partial": bool(counts.get("partial")),
            "no_counts": not counts, "none_txt": none_txt}


def _compare_label(key: str, s: str, line, lang: str, home: str, away: str) -> str:
    """Libellé sans ambiguïté dans la liste déroulante (« Victoire Arsenal », « Plus de 2,5 buts »…)."""
    t = i18n.UI[lang]
    base = i18n.selection_label(key, s, line, lang, home, away)
    if key == "1x2":
        return t["draw_long"] if s == "X" else t["home_win"].format(team=base)
    if key == "dnb":
        return f"{base} ({t['dnb_short']})"
    if key == "ou":
        return f"{base} {t['goals_word']}"
    if key == "btts":
        return f"{t['btts_short']}{i18n.JS_COLON[lang]}{base.lower()}"
    if key in ("co", "ca"):
        return i18n.pick_label(key, s, line, lang, home, away)
    return base


def _compare(m: dict, lang: str, best: int) -> dict:
    """Sélections proposées dans « Compare ta cote » : probabilité et cote juste de chacune."""
    home, away = m["home"]["name"], m["away"]["name"]
    groups, items = [], {}
    for key, line in COMPARE_MARKETS:
        mk = _find(m, key, line)
        if not mk:
            continue
        opts = []
        for s, v in mk["sel"].items():
            if not v.get("fair"):
                continue
            sid = f"{key}|{line}|{s}"
            items[sid] = {"p": round(v["p"], 5), "fair": round(v["fair"], 4)}
            opts.append({"id": sid, "label": _compare_label(key, s, line, lang, home, away)})
        groups.append({"title": i18n.market_title(key, line, lang, home, away), "opts": opts})
    return {"groups": groups, "items": items, "default": f"1x2|None|{'1X2'[best]}", "source": m["source"]}


def _round_txt(m: dict, lang: str) -> str | None:
    r = str(m.get("round") or "")
    if r == "200":  # TheSportsDB : 200 = finale des coupes
        return i18n.UI[lang]["final"]
    if r.isdigit() and 0 < int(r) <= 50:
        return i18n.UI[lang]["round"].format(n=int(r))
    return None


def _match_view(m: dict, lang: str, info: dict, sections: dict, live: dict | None = None) -> dict:
    lg = BY_CODE[m["league"]]
    t = i18n.UI[lang]
    x12 = _find(m, "1x2")["sel"]
    ou = _find(m, "ou", 2.5)["sel"]
    btts = _find(m, "btts")["sel"]
    ps = [x12[k]["p"] for k in ("1", "X", "2")]
    best = ps.index(max(ps))
    groups = []
    for g in i18n.GROUP_ORDER:
        mks = [_market_view(m, mk, lang) for mk in m["markets"] if mk["group"] == g]
        if mks:
            groups.append({"key": g, "title": t["groups"][g], "markets": mks,
                           "locked": not any(mk["free"] for mk in mks)})
    priced = [dict(e, label=i18n.selection_label(e["key"], e["sel"], e["line"], lang, m["home"]["name"], m["away"]["name"]),
                   market=i18n.market_title(e["key"], e["line"], lang, m["home"]["name"], m["away"]["name"]),
                   pct=i18n.pct(e["p"], lang), fair_txt=i18n.odds(e["fair"], lang), best_txt=i18n.odds(e["best"], lang),
                   margin_txt=i18n.pct(e["margin"], lang), better=e["best"] > e["fair"])
              for e in (m.get("priced") or {}).values()]
    lam, mu = m["xg"]
    badge, dark = _league_badge(m["league"], info)
    ko = datetime.fromisoformat(m["kickoff"])
    return {
        **m,
        "section": sections.get(m["league"], "others"),
        "league_name": lg.name_fr if lang == "fr" else lg.name_en,
        "country": lg.country_fr if lang == "fr" else lg.country_en,
        "league_logo": _img(badge, "tiny"),
        "league_on_dark": dark,  # logo blanc (coupes UEFA, Eredivisie…) : sur fond foncé
        "round_txt": _round_txt(m, lang),
        "home_crest": _crest(m["home"]), "away_crest": _crest(m["away"]),
        "p1": ps[0], "px": ps[1], "p2": ps[2], "best": best,
        "p1_txt": i18n.pct(ps[0], lang), "px_txt": i18n.pct(ps[1], lang), "p2_txt": i18n.pct(ps[2], lang),
        "over25": i18n.pct(ou["over"]["p"], lang), "btts_yes": i18n.pct(btts["yes"]["p"], lang),
        "xg_home": i18n.dec(lam, lang, 1), "xg_away": i18n.dec(mu, lang, 1), "xg_total": i18n.dec(lam + mu, lang, 1),
        "xg_share": round(100 * lam / (lam + mu), 1) if lam + mu > 0 else 50,
        "xg_txt": f"{i18n.num(lam, lang, 1)} – {i18n.num(mu, lang, 1)}",
        "top_scores": [(s.replace("-", " - "), i18n.pct(p, lang)) for s, p in m["top_score"]],
        "day_short": i18n.day_short(ko, lang), "day_med": i18n.day_med(ko, lang),
        "groups": groups, "priced_view": priced, "n_markets": len(m["markets"]),
        "odds_note": t["odds_note_api" if m.get("odds_src") == "oddsapi" else "odds_note"],
        "key_markets": _key_markets(m, lang), "compare": _compare(m, lang, best),
        "vd": _verdicts_view(m, lang, (live or {}).get(m["id"])),
        "why": explain.render(m.get("factors"), lang, m["home"]["name"], m["away"]["name"]),
        "form": _form_view(m, lang),
    }


def _date_short(iso: str, lang: str, ref_year: int) -> str:
    """« 7 nov. » (« 25 avr. 2025 » quand ce n'est pas l'année du match)."""
    d = date.fromisoformat(iso)
    s = f"{d.day} {i18n._MONTHS[lang][d.month - 1]}"  # noqa: SLF001
    return s if d.year == ref_year else f"{s} {d.year}"


def _comp_name(code: str, lang: str) -> str:
    lg = BY_CODE.get(code)
    if lg:
        return lg.name_fr if lang == "fr" else lg.name_en
    return i18n.UI[lang]["form_comp_other"] if code else ""


def _plural(n: int, word: str, lang: str) -> str:
    """« 0 victoire », « 2 victoires » (le français ne met pas de « s » à 0 ou 1) ; « 1 win », « 0 wins »."""
    many = n > 1 if lang == "fr" else n != 1
    return f"{n} {word}{'s' if many else ''}"


def _form_view(m: dict, lang: str) -> dict | None:
    """Forme récente des deux équipes et leurs dernières rencontres (rappel des résultats, gratuit)."""
    f = m.get("form")
    if not f:
        return None
    t = i18n.UI[lang]
    year = int(m["kickoff"][:4])
    teams = []
    for side in ("home", "away"):
        rows = []
        gf = ga = 0
        for r in f.get(side) or []:
            home = bool(r["h"])
            a, b = (r["s"][0], r["s"][1]) if home else (r["s"][1], r["s"][0])
            gf, ga = gf + a, ga + b
            sub = " · ".join(x for x in (_date_short(r["d"], lang, year), _comp_name(r.get("c", ""), lang),
                                         t["form_home" if home else "form_away"]) if x)
            rows.append({"r": r["r"], "l": t["form_r_" + r["r"]], "rl": t["form_rl_" + r["r"]], "o": r["o"],
                         "sub": sub, "score": f"{a}-{b}",
                         "tip": f"{t['form_rl_' + r['r']]} {a}-{b} · {r['o']} · {_date_short(r['d'], lang, year)}"})
        team = m[side]
        teams.append({"name": team["name"], "crest": _crest(team), "rows": rows,
                      "chips": list(reversed(rows)),  # pastilles : du plus ancien au plus récent
                      "aria": ", ".join(r["rl"] for r in reversed(rows)),
                      "goals": t["form_goals"].format(gf=gf, ga=ga) if rows else "",
                      "see": t["form_see"].format(n=len(rows))})
    h2h = m.get("h2h") or []
    meetings = []
    wins = {"home": 0, "draw": 0, "away": 0}
    for r in h2h:
        hn, an = (m["home"]["name"], m["away"]["name"]) if r["x"] else (m["away"]["name"], m["home"]["name"])
        wins[r["w"]] += 1
        meetings.append({"date": _date_short(r["d"], lang, year), "home": hn, "away": an,
                         "score": f"{r['s'][0]}-{r['s'][1]}", "comp": _comp_name(r.get("c", ""), lang),
                         "w": r["w"], "hw": r["s"][0] > r["s"][1], "aw": r["s"][1] > r["s"][0]})
    n = len(h2h)
    win_word = "victoire" if lang == "fr" else "win"
    summary = None
    if n:
        summary = {"lead": t["h2h_last1"] if n == 1 else t["h2h_last"].format(n=n),
                   "home": _plural(wins["home"], win_word, lang), "draw": _plural(wins["draw"], t["h2h_draws"], lang),
                   "away": _plural(wins["away"], win_word, lang),
                   "w": [round(100 * wins[k] / n, 1) for k in ("home", "draw", "away")]}
    return {"teams": teams, "h2h": meetings, "sum": summary}


def _money(amount: float, cur: str, decimals: int, lang: str) -> str:
    """Prix affiché sans JavaScript (le téléphone le remplace ensuite par celui de son pays)."""
    n = f"{amount:,.{decimals}f}"
    n = n.replace(",", " ").replace(".", ",") if lang == "fr" else n
    sym = {"EUR": "€", "USD": "$", "GBP": "£"}.get(cur)
    if not sym:
        return f"{n} {cur}"
    return f"{n} {sym}" if lang == "fr" else f"{sym}{n}"


def _save_pct(prices: dict, c: dict, plan: str) -> int:
    """Remise par jour d'un pass, par rapport au pass 30 jours (0 si moins de 5 %)."""
    days = prices["plans"]
    n = round((1 - (c[plan] / days[plan]["days"]) / (c["month"] / days["month"]["days"])) * 100)
    return n if n >= 5 else 0


def _save_txt(prices: dict, c: dict, plan: str, lang: str) -> str:
    n = _save_pct(prices, c, plan)
    if not n:
        return ""
    return f"\u2212{n}\u00a0%" if lang == "fr" else f"\u2212{n}%"


def _featured(views: list[dict]) -> tuple[list[dict], str | None]:
    """Candidats « à la une » : la plus belle affiche de chaque championnat, chaque jour.

    Le téléphone choisit ensuite selon le jour et les championnats affichés, en préférant les grands
    championnats et les coupes d'Europe. Sans JavaScript, on montre la plus belle affiche du premier jour.
    """
    best: dict[tuple, dict] = {}
    for v in views:
        k = (v["kickoff"][:10], v["league"])
        if k not in best or (v.get("stature") or 0) > (best[k].get("stature") or 0):
            best[k] = v
    cands = sorted(best.values(), key=lambda v: v["kickoff"])
    if not cands:
        return [], None
    first = [v for v in cands if v["kickoff"][:10] == cands[0]["kickoff"][:10]]
    lead = max([v for v in first if v["section"] in ("popular", "europe")] or first, key=lambda v: v.get("stature") or 0)
    return cands, lead["id"]


# --- Paris du jour, historique, ticket -------------------------------------------------------------------

def _mini_match(mt: dict, lang: str, slugs: set) -> dict:
    """Ce qu'il faut pour afficher un match dans une liste de paris (aussi pour les matchs déjà joués)."""
    ko = datetime.fromisoformat(mt["kickoff"])
    lg = BY_CODE.get(mt["league"])
    return {"slug": mt["slug"] if mt["slug"] in slugs else None, "kickoff": mt["kickoff"],
            "home": mt["home"]["name"], "away": mt["away"]["name"],
            "home_crest": _crest(mt["home"]), "away_crest": _crest(mt["away"]),
            "day_short": i18n.day_short(ko, lang), "score": mt.get("score"), "void": mt.get("void"),
            "live": bool(mt.get("live")) and not mt.get("score") and not mt.get("void"),  # match en cours
            "league_name": (lg.name_fr if lang == "fr" else lg.name_en) if lg else ""}


def _times(p: float, lang: str) -> str:
    return i18n.UI[lang]["times_ten"].format(n=max(1, min(9, round(p * 10))))


def _pick_view(c: dict, mt: dict, lang: str, slugs: set, why: dict | None = None) -> dict:
    home, away = mt["home"]["name"], mt["away"]["name"]
    p = c["p"]
    shown = min(p, 0.99)  # jamais « 100 % » : rien n'est certain
    label = i18n.pick_label(c["key"], c["sel"], c["line"], lang, home, away)
    market = i18n.market_title(c["key"], c["line"], lang, home, away)
    mm = _mini_match(mt, lang, slugs)
    return {"id": c["id"], "label": label, "market": market, "p": p, "pct": i18n.pct(shown, lang),
            "dash": f"{RING * shown:.1f} {RING:.1f}", "fair": i18n.odds(c["fair"], lang),
            "book": i18n.odds(picks.book_odds(c["fair"]), lang), "times": _times(p, lang),
            "res": c.get("res"), "match": mm, "why": None if c.get("res") else (why or {}).get(c["mid"]),
            "add": {"id": c["id"], "mid": c["mid"], "key": c["key"], "line": c["line"], "sel": c["sel"], "p": p,
                    "fair": c["fair"], "l": label, "m": market, "h": home, "a": away, "ko": mt["kickoff"],
                    "s": mm["slug"]}}


def _coupon_view(cp: dict, ms: dict, lang: str, slugs: set) -> dict:
    t = i18n.UI[lang]
    legs = [_pick_view(c, ms[c["mid"]], lang, slugs) for c in cp["legs"]]
    p = min(cp["p"], 0.99)
    # Coupon dévoilé seulement quand chacun de ses paris est réglé : un coupon déjà perdu ne montre pas
    # les paris de ses matchs encore à jouer (réservés au Premium).
    return {"target": cp["target"], "n": len(legs), "legs": legs, "res": history.coupon_shown(cp),
            "title": t["coupon_target"].format(n=cp["target"]),
            "meta": t["coupon_meta"].format(n=len(legs), p=i18n.pct(p, lang)), "times": _times(p, lang),
            "book": i18n.odds(cp["book"], lang), "fair": t["coupon_fair"].format(o=i18n.odds(cp["fair"], lang)),
            "add": [leg["add"] for leg in legs]}


def _day_view(day: str, e: dict, lang: str, slugs: set, why: dict | None = None) -> dict:
    ms = e.get("matches", {})
    tiers = {tier: [_pick_view(c, ms[c["mid"]], lang, slugs, why) for c in e.get("tiers", {}).get(tier, [])]
             for tier in picks.TIERS}
    coupons = [_coupon_view(cp, ms, lang, slugs) for cp in e.get("coupons", [])]
    d = date.fromisoformat(day)
    return {"key": day, "label": i18n.day_med(d, lang), "wd": i18n.weekday_short(d, lang), "dnum": d.day,
            "tiers": tiers, "coupons": coupons, "empty": not any(tiers.values())}


def _paris_days(hist: dict, today: str, lang: str, slugs: set, horizon: int = 7, why: dict | None = None) -> list[dict]:
    """Jours affichés dans l'onglet Paris : aujourd'hui (liste figée) et les jours suivants."""
    last = (date.fromisoformat(today) + timedelta(days=horizon)).isoformat()
    return [_day_view(day, e, lang, slugs, why) for day, e in sorted(hist.get("days", {}).items())
            if today <= day <= last and (any(e.get("tiers", {}).values()) or e.get("coupons"))]


def _why_map(matches: list[dict], lang: str) -> dict:
    """Raison principale de chaque match (premier « pourquoi » du moteur)."""
    out = {}
    for m in matches:
        r = explain.render(m.get("factors"), lang, m["home"]["name"], m["away"]["name"])
        if r:
            out[m["id"]] = r[0]["text"]
    return out


def _yesterday(hist: dict, today: str, lang: str) -> dict | None:
    """Bilan des paris du jour d'hier (onglet Paris)."""
    day = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    e = (hist.get("days") or {}).get(day)
    if not e:
        return None
    res = [c.get("res") for lst in (e.get("tiers") or {}).values() for c in lst]
    done = [r for r in res if r in ("won", "lost")]
    if not done:
        return None
    won = sum(1 for r in done if r == "won")
    t = i18n.UI[lang]
    return {"txt": t["yesterday_line"].format(won=won, n=len(done), rate=i18n.pct(won / len(done), lang)),
            "wait": len(res) - len(done) - sum(1 for r in res if r == "void"), "rate": won / len(done),
            "label": i18n.day_med(date.fromisoformat(day), lang)}


def _reliability(lang: str) -> dict:
    """Chiffres de la carte « fiabilité » de l'onglet Paris, tirés du test du moteur (saison jamais vue)."""
    p = load_params()
    meta = p.meta or {}
    b = (p.reliability or {}).get("_best") or [0, 0, 0]
    n = (meta.get("matches") or {}).get("test") or b[0]
    out = {"n": i18n.num(n, lang, 0) if n else None, "season": _season_label(meta.get("test"))}
    if b[0]:
        out["best"] = i18n.pct(b[1] / b[0], lang)
        out["best_ann"] = i18n.pct(b[2] / b[0], lang)
    return out


def _rate_view(r: dict, lang: str) -> dict:
    return {**r, "rate_txt": i18n.pct(r["rate"], lang) if r["rate"] is not None else "—",
            "announced_txt": i18n.pct(r["announced"], lang) if r["announced"] is not None else "—"}


def _history_view(hist: dict, today: str, lang: str, slugs: set, n_days: int = 30) -> dict:
    t = i18n.UI[lang]
    s = history.summary(hist.get("days", {}))
    frozen = sorted((d for d, e in hist.get("days", {}).items()
                     if e.get("frozen") and (any((e.get("tiers") or {}).values()) or e.get("coupons"))), reverse=True)
    days = []
    for day in frozen[:n_days]:
        v = _day_view(day, hist["days"][day], lang, slugs)
        items = [c for lst in v["tiers"].values() for c in lst]
        v["won"] = sum(1 for c in items if c["res"] == "won")
        v["lost"] = sum(1 for c in items if c["res"] == "lost")
        v["wait"] = sum(1 for c in items if not c["res"])
        v["is_today"] = day == today
        v["old_engine"] = "eng" not in hist["days"][day] and bool(items)
        days.append(v)
    return {"tiers": [{"key": k, "name": t["tier_" + k], **_rate_view(r, lang)} for k, r in s["tiers"].items()],
            "coupons": [{"target": k, "title": t["coupon_target"].format(n=k), **_rate_view(r, lang)}
                        for k, r in s["coupons"].items()],
            "days": days, "since": i18n.day_med(date.fromisoformat(frozen[-1]), lang) if frozen else None,
            "settled": sum(r["n"] for r in s["tiers"].values())}


PAST_DAYS = 3   # matchs terminés qui gardent leur page (aujourd'hui, hier, avant-hier) ; plus vieux : page 404


def _an_rows(rec: dict, lang: str, home: str, away: str) -> list[dict]:
    res = rec.get("r") or [None] * len(rec.get("v", []))
    rows = []
    for i, (d, r) in enumerate(zip(rec.get("v", []), res)):
        v = history.verdict_of(d)
        ans, cls = verdict_answer(v, lang)
        rows.append({"q": verdict_question(v, lang, home, away), "ans": ans, "cls": cls, "pct": i18n.pct(v["p"], lang),
                     "res": "open" if v["open"] and r in ("won", "lost") else r, "best": i == rec.get("b"),
                     "open": v["open"], "k": v["key"]})
    return rows


def _an_match(e: dict, mid: str, rec: dict, lang: str, links: set) -> dict:
    """Un match terminé de l'historique des analyses : score, le plus sûr, et ses verdicts justes / faux."""
    mt = e["matches"][mid]
    mm = _mini_match(mt, lang, links)
    rows = _an_rows(rec, lang, mm["home"], mm["away"])
    done = [r for r in rows if r["res"] in ("won", "lost")]
    best = next((r for r in rows if r["best"]), None)
    status = "void" if mt.get("void") else ("done" if mt.get("score") else ("live" if mm["live"] else "wait"))
    if status == "live":  # match en cours : seulement les verdicts déjà joués d'avance (les autres restent Premium)
        rows = [r for r in rows if r["res"] in ("won", "lost")]
        done = rows
        best = next((r for r in rows if r["best"]), None)
    return {**mm, "id": mid, "league": mt["league"], "rows": rows, "best": best, "status": status,
            "ok": sum(1 for r in done if r["res"] == "won"), "n": len(done),
            "nv": any(r["res"] == history.NV for r in rows),
            # Match fini, corners ou cartons pas encore publiés (football-data, 2 à 4 jours) : on l'explique
            "wait_st": status == "done" and any(r["res"] is None and r["k"] in ("co", "ca") for r in rows),
            "score_txt": f"{mt['score'][0]} - {mt['score'][1]}" if mt.get("score") else None,
            "x": [i18n.pct(p, lang) for p in rec.get("x") or []], "ts": (rec.get("ts") or "").replace("-", " - "),
            "st": mt.get("st"), "eng_old": rec.get("eng") == "v1"}


def _an_sum_txt(s: dict, lang: str) -> dict:
    t = i18n.UI[lang]
    out = {"n": s["n"], "won": s["won"], "rate": s["won"] / s["n"] if s["n"] else None}
    out["txt"] = t["ha_day"].format(won=i18n.num(s["won"], lang, 0), n=i18n.num(s["n"], lang, 0),
                                    rate=i18n.pct(out["rate"], lang), ann=i18n.pct(s["ann"], lang)) if s["n"] else None
    out["best"] = t["ha_best"].format(won=s["bw"], n=s["bn"], rate=i18n.pct(s["bw"] / s["bn"], lang)) if s["bn"] else None
    out["rate_txt"] = i18n.pct(out["rate"], lang) if out["rate"] is not None else "—"
    return out


def _analyses_view(hist: dict, now: datetime, lang: str, links: set) -> dict:
    """Onglets Aujourd'hui (matchs déjà finis) / Hier / Avant-hier / 7 derniers jours."""
    t = i18n.UI[lang]
    days = hist.get("days") or {}
    td = date.fromisoformat(picks.day_key(now))
    order = {lg.code: i for i, lg in enumerate(LEAGUES)}
    tabs = []
    for off, label in ((0, t["tk_today"]), (1, t["ha_yesterday"]), (2, t["ha_before"])):
        d = td - timedelta(days=off)
        e = days.get(d.isoformat()) or {}
        ms = e.get("matches") or {}
        shown = {mid: rec for mid, rec in (e.get("an") or {}).items()
                 if history.match_over(ms.get(mid) or {}, now) or history.live_decided(ms.get(mid) or {}, rec)}
        if off == 0 and not shown:
            continue
        items = sorted((_an_match(e, mid, rec, lang, links) for mid, rec in shown.items()),
                       key=lambda x: (order.get(x["league"], 99), x["kickoff"]))
        leagues = []
        for it in items:
            if not leagues or leagues[-1]["code"] != it["league"]:
                leagues.append({"code": it["league"], "name": it["league_name"], "matches": []})
            leagues[-1]["matches"].append(it)
        s = history.an_stats({"an": shown})
        tabs.append({"key": f"d{off}", "label": label, "date": i18n.day_med(d, lang), "leagues": leagues,
                     "n_matches": len(items), "sum": _an_sum_txt(s, lang), "old": bool(e) and "an" not in e})
    week, tot = [], {"n": 0, "won": 0, "ann": 0.0, "bn": 0, "bw": 0}
    for off in range(1, 8):
        d = td - timedelta(days=off)
        e = days.get(d.isoformat())
        if not e:
            continue
        s = history.an_stats(e)
        if not s["n"] and "an" not in e and "an_sum" not in e:
            week.append({"label": i18n.day_med(d, lang), "old": True})
            continue
        for k in ("n", "won", "bn", "bw"):
            tot[k] += s[k]
        tot["ann"] += (s["ann"] or 0) * s["n"]
        week.append({"label": i18n.day_med(d, lang), "old": False, **_an_sum_txt(s, lang), "m": s.get("m", 0)})
    tot["ann"] = tot["ann"] / tot["n"] if tot["n"] else None
    return {"tabs": tabs, "week": week, "week_sum": _an_sum_txt(tot, lang)}


def past_matches(hist: dict, now: datetime, live: set) -> list[tuple[dict, str, dict]]:
    """(jour, id, analyse) des matchs terminés des PAST_DAYS derniers jours qui n'ont plus de fiche à jour."""
    td = date.fromisoformat(picks.day_key(now))
    out = []
    for off in range(PAST_DAYS):
        e = (hist.get("days") or {}).get((td - timedelta(days=off)).isoformat()) or {}
        for mid, rec in (e.get("an") or {}).items():
            mt = (e.get("matches") or {}).get(mid) or {}
            if mt.get("slug") and mt["slug"] not in live and history.match_over(mt, now):
                out.append((e, mid, rec))
    return out


def _past_view(e: dict, mid: str, rec: dict, lang: str, links: set) -> dict:
    v = _an_match(e, mid, rec, lang, links)
    mt = e["matches"][mid]
    lg = BY_CODE.get(mt["league"])
    ko = datetime.fromisoformat(mt["kickoff"])
    t = i18n.UI[lang]
    st = mt.get("st") or {}
    stats = []
    if st.get("corners"):
        stats.append(f"{st['corners'][0]} – {st['corners'][1]} {t['corners_word']}")
    if st.get("cards"):
        stats.append(f"{st['cards'][0]} – {st['cards'][1]} {t['cards_word']}")
    return {**v, "slug": mt["slug"], "day_med": i18n.day_med(ko, lang), "stats": " · ".join(stats),
            "league_name": (lg.name_fr if lang == "fr" else lg.name_en) if lg else ""}


def _ticket_data(matches: list[dict], lang: str, now: datetime) -> dict:
    """Matchs à venir et leurs paris classiques, pour le constructeur de coupons (chargé à la demande)."""
    out = []
    for m in sorted(matches, key=lambda m: m["kickoff"]):
        lg = BY_CODE.get(m["league"])
        if not lg or datetime.fromisoformat(m["kickoff"]) <= now:
            continue
        home, away = m["home"]["name"], m["away"]["name"]
        hc, ac = _crest(m["home"]), _crest(m["away"])
        out.append({"id": m["id"], "s": m["slug"], "k": m["kickoff"], "d": picks.day_key(m["kickoff"]),
                    "lg": lg.name_fr if lang == "fr" else lg.name_en, "h": home, "a": away,
                    "hc": [hc["initials"], hc["color"], hc["img"]], "ac": [ac["initials"], ac["color"], ac["img"]],
                    "q": m.get("confidence"), "e": 1 if picks.eligible(m) else 0,
                    "c": [[c["key"], c["line"], c["sel"], c["p"], c["fair"],
                           i18n.pick_label(c["key"], c["sel"], c["line"], lang, home, away),
                           i18n.market_title(c["key"], c["line"], lang, home, away)]
                          for c in picks.candidates(m, counts=True)]})
    return {"built": now.isoformat(timespec="seconds"), "margin": picks.BOOK_MARGIN,
            "tiers": {k: list(v) for k, v in picks.TIERS.items()}, "matches": out}


def _dump(path: Path, obj, gz: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if gz:
        path.with_name(path.name + ".gz").write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    else:
        path.write_bytes(raw)


def full_data_file() -> Path:
    """Copie des données complètes (toutes les probabilités) gardée sur l'ordinateur qui construit le site, jamais
    publiée : elle sert aux e-mails du jour et aux captures de la vitrine."""
    return ROOT / "data" / "cache" / "site-matches.json"


def _lk_dir(cfg: dict) -> str:
    """Nom du dossier des chiffres protégés, dans public/. En ligne (Supabase configuré) : un nom tiré au hasard à
    chaque construction, que seul le gardien connaît. Cloudflare sert n'importe quel fichier du site à qui connaît
    son adresse, et certaines façons d'écrire une adresse (//lk/…, /%6ck/…) arrivent aux fichiers sans passer par
    le gardien : un nom impossible à deviner ferme cette porte. En mode démo (appli servie en local, sans
    Supabase) : lk/, lu directement par l'appli."""
    sb = cfg.get("sb") or {}
    return "lk-" + secrets.token_hex(20) if sb.get("url") and sb.get("key") else "lk"


def locked_dir(public: Path | None = None) -> Path:
    """Dossier des chiffres protégés d'un site construit (pour les outils qui lisent les données complètes)."""
    public = public or PUBLIC
    found = [public / "lk"] if (public / "lk").is_dir() else sorted(public.glob("lk-*"))
    return found[0] if found else public / "lk"


def _write_locked(lk: Locker, tk: dict, version: str, data: dict, base: Path) -> None:
    """Dans `base` (voir _lk_dir) : les vrais blocs de chaque page (Premium), ceux offerts à tout compte
    (free.json), ceux de chaque match (analyse gratuite du jour) et les données du constructeur de coupons. Rien de
    tout ça n'est envoyé sans vérification du compte par le gardien. En ligne, les fichiers sont compressés (.gz,
    dix fois plus légers à envoyer sur Cloudflare) : le gardien les décompresse avant de répondre. Les données
    complètes ne sont pas publiées (full_data_file), sauf en mode démo pour les captures."""
    gz = base.name != "lk"
    pages = [p for p in lk.pages if "/" in p and p.split("/", 1)[0] in i18n.LANGS]
    for page in pages:
        blocks = lk.all_of(page)
        if blocks:
            _dump(base / f"{page}.json", {"v": version, "b": blocks}, gz)
    for lang in i18n.LANGS:
        free = {p.split("/", 1)[1]: b for p, b in lk.free_of().items() if p.startswith(lang + "/")}
        _dump(base / lang / "free.json", {"v": version, "p": free}, gz)
        _dump(base / "data" / f"ticket-{lang}.json", tk[lang], gz)
    by_slug = {lang: {m["s"]: m for m in tk[lang]["matches"]} for lang in i18n.LANGS}
    per: dict[tuple[str, str], dict] = {}
    for slug, by_page in lk.by_match().items():
        for page, blocks in by_page.items():
            lang, rest = page.split("/", 1)
            if lang in i18n.LANGS:
                per.setdefault((lang, slug), {})[rest] = blocks
    for (lang, slug), p in per.items():
        _dump(base / lang / "m" / f"{slug}.json", {"v": version, "p": p, "tk": by_slug[lang].get(slug)}, gz)
    _dump(full_data_file(), data)
    if not gz:
        _dump(base / "data" / "matches.json", data)


GUARD = HERE / "guard.js"


def _write_guard(cfg: dict, lk_dir: str) -> None:
    """Le gardien des adresses /lk/ (Cloudflare Pages Function), avec l'adresse et la clé publique de Supabase et le
    nom du dossier protégé. Sans Supabase (mode démo), il refuse tout."""
    sb = cfg.get("sb") or {}
    js = GUARD.read_text(encoding="utf-8").replace("__LK_DIR__", lk_dir)
    js = js.replace("__SB_URL__", json.dumps(sb.get("url") or "")[1:-1])
    js = js.replace("__SB_KEY__", json.dumps(sb.get("key") or "")[1:-1])
    dst = ROOT / "functions" / "lk" / "[[path]].js"
    if dst.parent.exists():
        shutil.rmtree(dst.parent)
    dst.parent.mkdir(parents=True)
    dst.write_text(js, encoding="utf-8")


SIMULATION = HERE / "simulation.json"


def _simulation() -> dict | None:
    """Résultats de la simulation 2025/26 (mêmes règles que les paris du jour), si le fichier existe."""
    if not SIMULATION.exists():
        return None
    try:
        return json.loads(SIMULATION.read_text(encoding="utf-8"))
    except ValueError:
        return None


def _clear(folder: Path, tries: int = 8) -> None:
    """Vide le dossier du site. Sous Windows, un fichier que l'aperçu local ou l'antivirus vient d'ouvrir peut rester
    verrouillé un court instant : on réessaie au lieu d'échouer (sans effet sur GitHub, sous Linux)."""
    def retry(func, path, _exc):
        for i in range(tries):
            time.sleep(0.15 * (i + 1))
            try:
                func(path)
                return
            except FileNotFoundError:
                return
            except PermissionError:
                continue
        func(path)

    if folder.exists():
        shutil.rmtree(folder, onexc=retry) if sys.version_info >= (3, 12) else shutil.rmtree(folder, onerror=retry)


# --- Site vitrine (page d'accueil publique) ------------------------------------------------------------------

SITE_PAGES = {"fr": "/", "en": "/welcome/"}   # l'appli reste dans /fr/ et /en/
DEFAULT_SITE_URL = "https://probalis.pages.dev"


def _shot_fn(lang: str):
    """Balise <img> d'une capture de l'appli (deux tailles : le téléphone choisit la plus légère qui suffit)."""
    def shot(name: str, alt: str, lazy: bool = True, cls: str = "", idx: int | None = None) -> Markup:
        base = f"/assets/shots/{lang}-{name}"
        attrs = [f'src="{base}-600.jpg"', f'srcset="{base}-360.jpg 360w, {base}-600.jpg 600w"',
                 'sizes="(max-width: 699px) 64vw, 300px"', 'width="600" height="1298"', f'alt="{escape(alt)}"',
                 'decoding="async"', 'loading="lazy"' if lazy else 'fetchpriority="high"']
        if cls:
            attrs.append(f'class="{cls}"')
        if idx is not None:
            attrs.append(f'data-i="{idx}"')
        return Markup("<img " + " ".join(attrs) + ">")
    return shot


def _site_money(amount: float, cur: str, decimals: int, lang: str) -> str:
    n = f"{amount:,.{decimals}f}"
    if lang == "fr":
        n = n.replace(",", "\u00a0").replace(".", ",")
    label = site_text.CURRENCY_LABEL.get(cur, cur)
    if lang == "fr":
        return f"{n}\u00a0{label}"
    return f"{label}\u00a0{n}" if label[-1].isalpha() else f"{label}{n}"


def _site_prices(cfg: dict, lang: str) -> dict:
    cur_cfg = cfg["prices"]["currencies"]
    table, lst = {}, []
    for code in site_text.CURRENCIES[lang]:
        c = cur_cfg.get(code)
        if not c:
            continue
        row = {"free": _site_money(0, code, 0, lang)}
        for k in cfg["prices"]["plans"]:
            row[k] = _site_money(c[k], code, c["decimals"], lang)
            row[k + "_save"] = _save_txt(cfg["prices"], c, k, lang)
        table[code] = row
        lst.append({"code": code, "label": site_text.CURRENCY_LABEL.get(code, code)})
    return {"list": lst, "table": table, "first": table[lst[0]["code"]], "plans": list(cfg["prices"]["plans"])}


def _site_sim(sim: dict | None, lang: str) -> dict | None:
    """Chiffres de la simulation 2025/26 pour le site : annoncé, réel, et gain ou perte à la cote du bookmaker."""
    if not sim:
        return None
    t, s = i18n.UI[lang], site_text.SITE[lang]

    def row(r: dict, key: str | None, name: str) -> dict:
        return {"key": key, "name": name, "ann": r["announced"], "real": r["rate"],
                "ann_txt": r["announced_txt"][lang], "real_txt": r["rate_txt"][lang],
                "ann_int": round(r["announced"] * 100), "real_int": round(r["rate"] * 100),
                "n_txt": r["n_txt"][lang], "roi": r["roi"], "roi_txt": r["roi_txt"][lang]}

    tiers = [row(sim["tiers"][k], k, t["tier_" + k]) for k in picks.TIERS if k in sim["tiers"]]
    coupons = [row(c, None, s["coupon_row"].format(n=c["target"])) for c in sim["coupons"]]
    first = [row(c, None, s["proof_coupon"]) for c in sim["coupons"] if c["target"] == 2]
    losses = sorted(abs(r["roi"]) for r in tiers)
    return {"season": sim["season"], "n_txt": sim["matches_txt"][lang], "rows": tiers + first[:1],
            "n_leagues": len(sim.get("leagues") or []) or 10,
            "table": tiers + coupons, "lo": i18n.pct(losses[0], lang), "hi": i18n.pct(losses[-1], lang)}


_MONTHS_LONG = {"fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                        "novembre", "décembre"),
                 "en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                        "November", "December")}


def _shots_day(lang: str) -> str | None:
    """Jour où les captures de la vitrine ont été prises (écrit par shots.py), ex. « 21 novembre 2026 »."""
    try:
        d = date.fromisoformat(json.loads((HERE / "static" / "shots" / "shots.json").read_text(encoding="utf-8"))["day"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return f"{d.day} {_MONTHS_LONG[lang][d.month - 1]} {d.year}"


def _site_when(iso: str, lang: str) -> str:
    dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
    return f"{i18n.day_med(dt.date(), lang)}, {dt.strftime('%H:%M')} UTC"


def _site_carnet(hist: dict, today: str, lang: str, slugs: set) -> dict | None:
    """La dernière liste figée (aujourd'hui en général) : le n° 1 de chaque niveau, comme pour un compte gratuit."""
    days = hist.get("days", {})
    frozen = sorted(d for d, e in days.items() if e.get("frozen") and d <= today)
    if not frozen:
        return None
    day = frozen[-1]
    e = days[day]
    v = _day_view(day, e, lang, slugs)
    t, s = i18n.UI[lang], site_text.SITE[lang]
    rows = []
    for tier in picks.TIERS:
        lst = v["tiers"].get(tier) or []
        if lst:
            c = lst[0]
            res = c["res"] or "wait"
            # Pari pas encore réglé : réservé aux comptes (n° 1 de chaque liste), donc caché sur la vitrine
            hide = res == "wait"
            rows.append({"tier": tier, "tier_name": t["tier_" + tier], "locked": hide,
                         "label": None if hide else c["label"],
                         "match": f'{c["match"]["home"]} – {c["match"]["away"]}',
                         "pct": None if hide else c["pct"], "times": None if hide else c["times"],
                         "res": res, "res_txt": s["res_" + res]})
    total = sum(len(lst) for lst in v["tiers"].values())
    return {"day": i18n.day_med(date.fromisoformat(day), lang), "built": e.get("built", ""),
            "when": _site_when(e["built"], lang) if e.get("built") else "", "rows": rows,
            "more": total - len(rows), "coupons": len(v["coupons"])}


def _site_record(hist: dict, lang: str) -> str | None:
    days = hist.get("days", {})
    frozen = sorted(d for d, e in days.items() if e.get("frozen"))
    if not frozen:
        return None
    s = site_text.SITE[lang]
    summ = history.summary(days)
    since = i18n.day_med(date.fromisoformat(frozen[0]), lang)
    tiers = list(summ["tiers"].values())
    if any(r["n"] < 30 for r in tiers):
        return s["carnet_record_early"].format(since=since)
    return s["carnet_record"].format(since=since, won=sum(r["won"] for r in tiers), n=sum(r["n"] for r in tiers))


def _site_odds(lang: str, o: float = 1.5) -> dict:
    """État de départ du décodeur de cote (le même calcul est refait dans site.js quand on tape une cote)."""
    s = site_text.SITE[lang]
    b = 1 / o
    n10 = max(1, min(9, round(b * 10)))
    return {"value": i18n.odds(o, lang), "examples": [i18n.odds(x, lang) for x in (1.3, 1.5, 2.0, 3.0, 5.0)],
            "big": s["odds_times10"].format(n=n10), "pct": s["odds_need_pct"].format(p=round(b * 100)),
            "margin": s["odds_margin"].format(f=i18n.pct(b / (1 + picks.BOOK_MARGIN), lang).replace(" %", " %")),
            "fills": [f"{max(0.0, min(1.0, b * 10 - i)):.2f}" for i in range(10)]}


def _office(env, lk, common: dict, cfg: dict) -> None:
    """Probalis Office : l'appli de l'administrateur, à part (/office/), avec son propre manifeste et ses icônes.

    Aucun lien public n'y mène ; le lien n'apparaît que dans « Mon compte » d'un administrateur. Les données ne
    viennent que de la fonction Supabase « admin », qui vérifie l'adresse (secret ADMIN_EMAILS).
    """
    out = PUBLIC / "office"
    out.mkdir()
    lk.start("office")
    (out / "index.html").write_text(env.get_template("office.html").render(
        **common, page="office", root="/fr/", path="", noindex=True, no_lang=True,
        plans=list(cfg["prices"]["plans"]), currencies=sorted(cfg["prices"]["currencies"])), encoding="utf-8")
    (out / "manifest.webmanifest").write_text(json.dumps({
        "name": "Probalis Office", "short_name": "Office", "description": "L'espace de l'administrateur de Probalis",
        "id": "/office/", "start_url": "/office/", "scope": "/office/", "display": "standalone", "lang": "fr",
        "background_color": "#0B1F3A", "theme_color": "#0B1F3A",
        "icons": [{"src": "/icons/office-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                  {"src": "/icons/office-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                  {"src": "/icons/office-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _site_pages(env: Environment, hist: dict, today: str, slugs: set, sim: dict | None, cfg: dict, site: dict,
                version: str, now: datetime, odds_api: bool = False) -> None:
    """Le site vitrine : / en français, /welcome/ en anglais, et /app/ (point d'entrée de l'appli installée)."""
    site_url = site["site_url"] or DEFAULT_SITE_URL
    code = qr.svg(site_url + "/", label="QR")
    for lang in i18n.LANGS:
        s, other = site_text.SITE[lang], ("en" if lang == "fr" else "fr")
        here = SITE_PAGES[lang]
        out = PUBLIC / "index.html" if here == "/" else PUBLIC / here.strip("/") / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        groups = [{"title": i18n.UI[lang]["sec_" + key],
                   "leagues": [{"name": lg.name_fr if lang == "fr" else lg.name_en,
                                "country": lg.country_fr if lang == "fr" else lg.country_en} for lg in lgs]}
                  for key, lgs in league_sections() if lgs]
        ld = {"@context": "https://schema.org", "@type": "WebApplication", "name": "Probalis", "url": site_url + here,
              "applicationCategory": "SportsApplication", "operatingSystem": "Android, iOS, Windows, macOS",
              "inLanguage": lang, "description": s["description"],
              "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"}}
        js = {"lang": lang, "margin": picks.BOOK_MARGIN, "app": f"/{lang}/",
              **{k: s[k] for k in ("odds_times10", "odds_times100", "odds_need_pct", "odds_margin", "odds_error",
                                   "inst_copied")}}
        page = env.get_template("site.html").render(
            lang=lang, s=s, t=i18n.UI[lang], version=version, site_url=site_url, here=here, other=other,
            other_url=SITE_PAGES[other], app=f"/{lang}/", sim=_site_sim(sim, lang),
            carnet=_site_carnet(hist, today, lang, slugs), record=_site_record(hist, lang), groups=groups,
            prices=_site_prices(cfg, lang), odds=_site_odds(lang), shots_day=_shots_day(lang),
            qr=Markup(code.replace('aria-label="QR"', f'aria-label="{escape(s["qr_label"])}"')),
            contact=site.get("contact_email"), year=now.year, ld=ld, js=js, shot=_shot_fn(lang), cfg=cfg,
            credit=i18n.UI[lang]["data_credit_api" if odds_api else "data_credit"], odds_api=odds_api,
            ref=config.referral_view())
        out.write_text(page, encoding="utf-8")
    app_dir = PUBLIC / "app"
    app_dir.mkdir(exist_ok=True)
    (app_dir / "index.html").write_text(env.get_template("launch.html").render(), encoding="utf-8")
    # Lien d'invitation court, à partager : /i/CODE → page d'invitation (Cloudflare Pages, fichier _redirects)
    (PUBLIC / "_redirects").write_text("/i/:code  /fr/invite.html?c=:code  302\n", encoding="utf-8")
    # Probalis Office (l'appli de l'administrateur) : jamais dans les moteurs de recherche
    (PUBLIC / "_headers").write_text("/office/*\n  X-Robots-Tag: noindex, nofollow\n"
                                     "/logos/*\n  Cache-Control: public, max-age=31536000, immutable\n", encoding="utf-8")


def build(data: dict) -> Path:
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                      trim_blocks=True, lstrip_blocks=True)
    lk = Locker()
    env.globals.update(icon=icon, logo_mark=logo_mark, google_g=GOOGLE_G, lk=lk)
    _clear(PUBLIC)
    shutil.copytree(HERE / "static", PUBLIC / "assets")
    icons = PUBLIC / "icons"
    icons.mkdir()
    for f in (BRAND / "png").iterdir():
        shutil.copy2(f, icons / f.name)
    shutil.copy2(BRAND / "probalis-icone.svg", icons / "probalis-icone.svg")
    # Images de partage (WhatsApp, Facebook…), dessinées par brand/og.py
    shutil.copytree(BRAND / "og", PUBLIC / "og")

    version = datetime.now().strftime("%Y%m%d%H%M%S")
    generated = datetime.fromisoformat(data["generated_at"])
    info = data.get("leagues") or {}
    sections = _section_of()
    cfg, site = config.public_config(), config.site()
    now = datetime.now(timezone.utc)
    today = picks.day_key(now)
    hist = history.load(site["site_url"])
    history.update(hist, data["matches"], now)
    settled = history.settle(hist, now)
    if settled:
        print(f"Historique : {settled} résultat(s) de match ajouté(s).")
    live = history.live_scores(hist)  # matchs en cours : paris et verdicts déjà joués d'avance
    if live:
        print(f"Matchs en cours : {len(live)} (paris déjà gagnés ou perdus réglés tout de suite).")
    global LOGOS
    LOGOS = Logos()
    added = LOGOS.prepare(_logo_urls(data, hist))
    if added:
        print(f"Logos : {added} logo(s) ajouté(s) à notre copie.")
    slugs = {m["slug"] for m in data["matches"] if m["league"] in BY_CODE}
    past = past_matches(hist, now, slugs)
    links = slugs | {e["matches"][mid]["slug"] for e, mid, _ in past}
    sim = _simulation()
    odds_api = any(m.get("odds_src") == "oddsapi" for m in data["matches"])  # mention de la source des cotes
    for lang in i18n.LANGS:
        t = i18n.UI[lang]
        views = [_match_view(m, lang, info, sections, live) for m in data["matches"] if m["league"] in BY_CODE]
        common = {"lang": lang, "t": t, "other_lang": "en" if lang == "fr" else "fr", "version": version,
                  "generated": generated, "generated_iso": data["generated_at"], "js": i18n.js_strings(lang),
                  "cfg": cfg, "site": site, "free_markets": sorted(config.FREE_MARKETS),
                  "site_url": site["site_url"] or DEFAULT_SITE_URL,
                  "credit": t["data_credit_api" if odds_api else "data_credit"]}
        out = PUBLIC / lang
        (out / "match").mkdir(parents=True)

        counts: dict[str, int] = {}
        for v in views:
            counts[v["league"]] = counts.get(v["league"], 0) + 1
        sheet, groups, chips = [], [], []
        for key, lgs in league_sections():
            if not lgs:
                continue
            lviews = [_league_view(lg, lang, info, counts.get(lg.code, 0)) for lg in lgs]
            sheet.append({"key": key, "title": t["sec_" + key], "leagues": lviews})
            for lv in lviews:
                if lv["count"]:
                    chips.append(lv)
                    groups.append({**lv, "matches": [v for v in views if v["league"] == lv["code"]]})

        featured, lead = _featured(views)
        lk.start(f"{lang}/index")
        (out / "index.html").write_text(env.get_template("matches.html").render(
            **common, page="matches", root="", path="index.html", groups=groups, chips=chips, sheet=sheet,
            featured=featured, lead=lead, n_matches=len(views)), encoding="utf-8")
        lk.start(f"{lang}/paris")
        (out / "paris.html").write_text(env.get_template("bets.html").render(
            **common, page="bets", root="", path="paris.html",
            days=_paris_days(hist, today, lang, slugs, why=_why_map(data["matches"], lang)),
            today=today, tiers=list(picks.TIERS), yday=_yesterday(hist, today, lang), rel=_reliability(lang)),
            encoding="utf-8")
        lk.start(f"{lang}/ticket")
        (out / "ticket.html").write_text(env.get_template("ticket.html").render(
            **common, page="ticket", root="", path="ticket.html", tiers=list(picks.TIERS)), encoding="utf-8")
        lk.start(f"{lang}/historique")
        (out / "historique.html").write_text(env.get_template("history.html").render(
            **common, page="historique", root="", path="historique.html",
            h=_history_view(hist, today, lang, links), an=_analyses_view(hist, now, lang, links), sim=sim,
            tiers=list(picks.TIERS)), encoding="utf-8")
        # Compte, offres Premium, pages légales
        lk.start(f"{lang}/compte")
        (out / "compte.html").write_text(env.get_template("account.html").render(
            **common, page="compte", root="", path="compte.html", sheet=sheet), encoding="utf-8")
        # Récompenses (onglet du compte) et page d'invitation (lien /i/CODE)
        ref = config.referral_view()
        lk.start(f"{lang}/recompenses")
        (out / "recompenses.html").write_text(env.get_template("rewards.html").render(
            **common, page="compte", root="", path="recompenses.html", ref=ref), encoding="utf-8")
        lk.start(f"{lang}/invite")
        (out / "invite.html").write_text(env.get_template("invite.html").render(
            **common, page="compte", root="", path="invite.html", ref=ref, noindex=True), encoding="utf-8")
        if lang == "fr":
            _office(env, lk, common, cfg)
        cur = cfg["prices"]["default_currency"][lang]
        cp = cfg["prices"]["currencies"][cur]
        lk.start(f"{lang}/premium")
        (out / "premium.html").write_text(env.get_template("premium.html").render(
            **common, page="premium", root="", path="premium.html",
            plans=[{"key": k, "price": _money(cp[k], cur, cp["decimals"], lang),
                    "save": _save_txt(cfg["prices"], cp, k, lang)} for k in cfg["prices"]["plans"]]), encoding="utf-8")
        for doc, key in LEGAL_PAGES:
            lk.start(f"{lang}/{doc}")
            (out / f"{doc}.html").write_text(env.get_template("legal.html").render(
                **common, page="legal", root="", path=f"{doc}.html", doc=doc, title=t[key]), encoding="utf-8")
        for v in views:
            lk.start(f"{lang}/match/{v['slug']}")
            (out / "match" / f"{v['slug']}.html").write_text(env.get_template("match.html").render(
                **common, page="matches", m=v, root="../", path=f"match/{v['slug']}.html"), encoding="utf-8")
        # Matchs terminés : leur ancienne adresse (lien partagé) montre ce que disait l'analyse
        tpl = env.get_template("match_past.html")
        for e, mid, rec in past:
            pv = _past_view(e, mid, rec, lang, links)
            lk.start(f"{lang}/match/{pv['slug']}")
            (out / "match" / f"{pv['slug']}.html").write_text(tpl.render(
                **common, page="historique", m=pv, root="../", path=f"match/{pv['slug']}.html", noindex=True),
                encoding="utf-8")

    lk.start("site")
    _site_pages(env, hist, today, slugs, sim, cfg, site, version, now, odds_api)
    # Adresse inconnue (vieux lien de match…) : page 404 qui renvoie vers l'historique ou l'accueil
    (PUBLIC / "404.html").write_text(env.get_template("404.html").render(
        lang="fr", t=i18n.UI["fr"], t_en=i18n.UI["en"], version=version), encoding="utf-8")
    fonts = sorted(f"/assets/fonts/{f.name}" for f in (HERE / "static" / "fonts").glob("*.woff2"))
    (PUBLIC / "sw.js").write_text((HERE / "sw.template.js").read_text(encoding="utf-8")
                                  .replace("__VERSION__", version).replace("'__FONTS__'", json.dumps(fonts)[1:-1]),
                                  encoding="utf-8")
    (PUBLIC / "manifest.webmanifest").write_text(json.dumps({
        "name": "Probalis", "short_name": "Probalis", "description": "La science du pari · The science of betting",
        "id": "/", "start_url": "/app/", "scope": "/", "display": "standalone", "background_color": "#F3F5F8", "theme_color": "#F3F5F8",
        "icons": [{"src": "/icons/icone-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                  {"src": "/icons/icone-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                  {"src": "/icons/icone-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    # Données complètes (probabilités) : seulement dans le dossier protégé, envoyé après vérification du compte
    tk = {lang: _ticket_data(data["matches"], lang, now) for lang in i18n.LANGS}
    lk_dir = _lk_dir(cfg)
    _write_locked(lk, tk, version, data, PUBLIC / lk_dir)
    _write_guard(cfg, lk_dir)
    history.save(hist, PUBLIC / "data", now)
    n_logos = LOGOS.publish(PUBLIC)
    print(f"Logos : {n_logos // 2} publiés sur notre site" + (f", {len(LOGOS.missing)} encore chez TheSportsDB"
                                                              if LOGOS.missing else ""))
    return PUBLIC
