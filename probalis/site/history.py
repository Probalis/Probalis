"""Historique des paris du jour : enregistrés avant les matchs, réglés tout seuls avec le score final.

Le fichier vit sur le site lui-même (/data/history.json) : chaque construction relit la version en ligne,
y ajoute les listes des jours à venir et les résultats des matchs terminés, puis la republie.
La version en ligne ne montre que les paris réglés : les paris en attente sont des contenus Premium, ils n'y
figurent pas (le jour est alors marqué « sealed »). La version complète est gardée dans data/cache/history.json.

Règle d'honnêteté : la liste d'un jour est figée dès le premier calcul fait ce jour-là (ou plus tard) ;
ensuite elle ne change plus, même si le modèle change d'avis. Les listes des jours suivants restent
provisoires jusque-là. Tout pari enregistré a donc été publié avant le coup d'envoi de son match.

Analyses des matchs (« an ») : chaque jour garde aussi les verdicts OUI / NON de chaque match analysé, enregistrés
avant le coup d'envoi (un jour figé reçoit encore les matchs qui n'ont pas commencé, jamais de changement sur
ceux déjà enregistrés). Ils sont réglés avec le score final ; les corners et cartons avec les chiffres publiés par
football-data (championnats seulement : les coupes et les compétitions sans chiffres sont « non vérifiables »).
Les analyses sont publiques une fois le match terminé. Détail gardé AN_DAYS jours, ensuite seulement le bilan.

Copie complète chiffrée (/data/history-full.bin) : la version complète est aussi publiée, chiffrée avec la clé
PROBALIS_HISTORY_KEY (Fernet : AES + HMAC, bibliothèque « cryptography »). Sans la clé, elle est illisible ; avec,
n'importe quel ordinateur qui construit le site (le PC ou GitHub Actions, qui démarre sans copie locale) retrouve
l'historique complet et ne perd pas les listes du jour pas encore réglées. Garde-fou : si seule la version publique
(incomplète) est disponible, la construction s'arrête au lieu de republier un historique amputé.
"""
from __future__ import annotations

import gzip
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core import verdicts as vd
from ..football import fixtures, signals
from ..football.data import CACHE, USER_AGENT, parse_csv
from ..football.leagues import BY_CODE, current_season_start, season_codes
from . import picks

LOCAL = CACHE / "history.json"
FULL_NAME = "history-full.bin"                   # copie complète chiffrée, publiée à côté de history.json
KEY_ENV = "PROBALIS_HISTORY_KEY"                 # clé de chiffrement (secret GitHub et fichier privé du PC)
VERSION = 1
SETTLE_AFTER = timedelta(hours=2, minutes=30)   # un match est fini environ 2 h après le coup d'envoi
GIVE_UP_AFTER = timedelta(days=6)                # sans score au bout de 6 jours (reporté, annulé) : remboursé
MAX_LOOKUPS = 40                                 # appels TheSportsDB par construction pour les scores manquants
AN_DAYS = 30                                     # analyses des matchs gardées en détail (ensuite : le bilan du jour)
NV = "nv"                                        # verdict non vérifiable (pas de chiffres gratuits)


def _empty() -> dict:
    return {"version": VERSION, "days": {}}


def _remote(site_url: str) -> dict | None:
    """Version en ligne. None si elle n'existe pas encore (le site renvoie alors sa page d'accueil)."""
    req = urllib.request.Request(f"{site_url}/data/history.json", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if "json" not in ctype:
        return None
    data = json.loads(body.decode("utf-8"))
    return data if isinstance(data, dict) and "days" in data else None


class HistoryKeyError(RuntimeError):
    """La copie complète en ligne ne s'ouvre pas avec la clé donnée (clé fausse ou fichier abîmé)."""


def _key() -> str | None:
    return (os.environ.get(KEY_ENV) or "").strip() or None


def new_key() -> str:
    """Nouvelle clé de chiffrement (à ranger dans le dossier des secrets et dans les secrets GitHub)."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode("ascii")


def seal(hist: dict, key: str) -> bytes:
    """Historique complet -> octets chiffrés (JSON compressé puis chiffré)."""
    from cryptography.fernet import Fernet
    raw = json.dumps(hist, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return Fernet(key.encode("ascii")).encrypt(gzip.compress(raw))


def unseal(blob: bytes, key: str) -> dict:
    from cryptography.fernet import Fernet, InvalidToken
    try:
        raw = gzip.decompress(Fernet(key.encode("ascii")).decrypt(blob))
    except (InvalidToken, ValueError, OSError) as e:
        raise HistoryKeyError(f"copie complète de l'historique illisible avec {KEY_ENV} (clé fausse ?)") from e
    data = json.loads(raw.decode("utf-8"))
    if not (isinstance(data, dict) and "days" in data):
        raise HistoryKeyError("copie complète de l'historique abîmée")
    return data


def _remote_full(site_url: str, key: str) -> dict | None:
    """Copie complète chiffrée en ligne. None si elle n'existe pas encore."""
    req = urllib.request.Request(f"{site_url}/data/{FULL_NAME}", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if "html" in ctype:  # page d'accueil ou page d'erreur à la place du fichier
        return None
    return unseal(body, key)


def _settled(entry: dict) -> int:
    return sum(1 for mt in entry.get("matches", {}).values() if mt.get("score") or mt.get("void"))


def _rank(e: dict) -> tuple:
    """Ordre de préférence d'une version d'un jour : figée, complète (pas « sealed »), la plus réglée, puis celle
    qui a le plus d'analyses de matchs enregistrées."""
    return (bool(e.get("frozen")), not e.get("sealed"), _settled(e), len(e.get("an") or {}))


def merge(*versions: dict | None) -> dict:
    """Réunit plusieurs versions : pour chaque jour, la liste figée d'abord, complète ensuite, puis la plus réglée.
    À égalité, la première version donnée l'emporte."""
    out = _empty()
    for src in versions:
        for day, e in ((src or {}).get("days") or {}).items():
            cur = out["days"].get(day)
            if cur is None or _rank(e) > _rank(cur):
                out["days"][day] = e
    return out


def match_over(mt: dict, now: datetime | None) -> bool:
    """Match terminé (score connu, reporté) ou commencé depuis plus de SETTLE_AFTER."""
    if mt.get("score") or mt.get("void"):
        return True
    return now is not None and now >= datetime.fromisoformat(mt["kickoff"]) + SETTLE_AFTER


def public_copy(hist: dict, now: datetime | None = None) -> dict:
    """Ce qui est publié : seulement les paris et coupons déjà réglés (les autres sont réservés au Premium),
    et les analyses des matchs terminés."""
    out = {k: v for k, v in hist.items() if k != "days"}
    out["days"] = {}
    for day, e in (hist.get("days") or {}).items():
        tiers = {t: [c for c in lst if c.get("res")] for t, lst in (e.get("tiers") or {}).items()}
        coupons = [cp for cp in e.get("coupons") or [] if cp.get("res")]
        ms = e.get("matches") or {}
        an = {mid: rec for mid, rec in (e.get("an") or {}).items() if match_over(ms.get(mid) or {}, now)}
        hidden = sum(len(lst) for lst in (e.get("tiers") or {}).values()) + len(e.get("coupons") or []) \
            - sum(len(lst) for lst in tiers.values()) - len(coupons) + len(e.get("an") or {}) - len(an)
        used = {c["mid"] for lst in tiers.values() for c in lst} | {c["mid"] for cp in coupons for c in cp["legs"]} \
            | set(an)
        d = {k: v for k, v in e.items() if k not in ("tiers", "coupons", "matches", "an")}
        d.update(tiers=tiers, coupons=coupons, matches={mid: mt for mid, mt in ms.items() if mid in used})
        if an:
            d["an"] = an
        if hidden:
            d["sealed"] = hidden
        out["days"][day] = d
    return out


def load(site_url: str) -> dict:
    """Historique actuel : version publique en ligne + copie locale + copie complète chiffrée en ligne.

    Arrêts voulus (on ne republie jamais un historique vide ou amputé par erreur) :
      - site injoignable et pas de copie locale ;
      - copie complète en ligne qui ne s'ouvre pas avec la clé (clé fausse) ;
      - seule la version publique disponible (ni copie locale, ni copie complète) alors qu'elle contient des jours :
        elle n'a pas les paris en attente, la republier les effacerait.
    """
    local = None
    if LOCAL.exists():
        try:
            local = json.loads(LOCAL.read_text(encoding="utf-8"))
        except ValueError:
            local = None
    remote = full = None
    if site_url:
        try:
            remote = _remote(site_url)
        except Exception as e:  # réseau, page cassée…
            if local is None:
                raise RuntimeError(f"Historique en ligne illisible ({e}) et pas de copie locale : arrêt.") from e
            print(f"  (historique en ligne illisible : {e} ; copie locale utilisée)")
        key = _key()
        if key:
            try:
                full = _remote_full(site_url, key)
            except HistoryKeyError:
                raise
            except Exception as e:  # réseau
                if local is None:
                    raise RuntimeError(f"Copie complète de l'historique injoignable ({e}) et pas de copie locale : "
                                       "arrêt.") from e
                print(f"  (copie complète de l'historique injoignable : {e} ; copie locale utilisée)")
    if local is None and full is None and remote and remote.get("days"):
        raise RuntimeError("Historique complet introuvable : ni copie locale (data/cache/history.json), ni copie "
                           f"complète en ligne lisible (clé {KEY_ENV} absente ou copie pas encore publiée). "
                           "Arrêt pour ne pas effacer les paris en attente.")
    return merge(remote, local, full)


def _match_info(m: dict) -> dict:
    info = {"slug": m["slug"], "league": m["league"], "kickoff": m["kickoff"], "conf": m.get("confidence"),
            "home": {"name": m["home"]["name"], "badge": m["home"].get("badge")},
            "away": {"name": m["away"]["name"], "badge": m["away"].get("badge")}}
    if m["home"].get("fd") and m["away"].get("fd"):
        info["fd"] = [m["home"]["fd"], m["away"]["fd"]]
    return info


def _vslim(v: dict) -> dict:
    d = {"f": v["fam"], "k": v["key"], "l": v["line"], "s": v["sel"], "y": int(bool(v["yes"])), "p": round(v["p"], 3)}
    if v["open"]:
        d["o"] = 1
    return d


def verdict_of(d: dict) -> dict:
    """Verdict enregistré -> même forme que core.verdicts (pour les textes et le règlement)."""
    return {"fam": d["f"], "key": d["k"], "line": d["l"], "sel": d["s"], "yes": bool(d["y"]), "p": d["p"],
            "open": bool(d.get("o"))}


def analysis_record(m: dict, rel: dict) -> dict:
    """Ce qu'on garde de l'analyse d'un match : ses verdicts, le plus sûr, le 1X2, le score le plus probable."""
    vs = vd.verdicts(m["markets"])
    b = vd.best(vs, rel)
    rec = {"v": [_vslim(v) for v in vs], "b": next((i for i, v in enumerate(vs) if v is b), None),
           "eng": m.get("engine", "v1")}
    x = next((mk for mk in m["markets"] if mk["key"] == "1x2" and mk.get("line") is None), None)
    if x:
        rec["x"] = [round(x["sel"][s]["p"], 3) for s in ("1", "X", "2")]
    if m.get("top_score"):
        rec["ts"] = m["top_score"][0][0]
    c = m.get("counts") or {}
    if c.get("corners") or c.get("cards"):
        rec["c"] = {k: c[k] for k in ("corners", "cards", "partial") if c.get(k)}
    return rec


def _analyses(day: dict, ms: list[dict], now: datetime, rel: dict, keep: bool) -> None:
    """Ajoute l'analyse des matchs pas encore commencés. keep : un jour figé ne change jamais ce qui est déjà là."""
    an = day.setdefault("an", {}) if keep else {}
    for m in ms:
        if m["league"] not in BY_CODE or datetime.fromisoformat(m["kickoff"]) <= now:
            continue
        if keep and m["id"] in an:
            continue
        an[m["id"]] = analysis_record(m, rel)
        day.setdefault("matches", {}).setdefault(m["id"], _match_info(m))
    if not keep:
        day["an"] = an


def _slim(c: dict) -> dict:
    return {k: c[k] for k in ("id", "mid", "key", "line", "sel", "p", "fair")}


def day_lists(matches: list[dict], after: datetime | None) -> dict:
    """Les trois listes et les coupons d'un jour, avec ce qu'il faut pour les afficher plus tard."""
    tiers = {t: [_slim(c) for c in picks.tier_picks(matches, t, after=after)] for t in picks.TIERS}
    coupons = [{"target": cp["target"], "p": cp["p"], "fair": cp["fair"], "book": cp["book"],
                "legs": [_slim(c) for c in cp["legs"]]} for cp in picks.day_coupons(matches, after=after)]
    used = {c["mid"] for lst in tiers.values() for c in lst} | {c["mid"] for cp in coupons for c in cp["legs"]}
    by_id = {m["id"]: m for m in matches}
    return {"tiers": tiers, "coupons": coupons, "matches": {mid: _match_info(by_id[mid]) for mid in sorted(used)}}


def update(hist: dict, matches: list[dict], now: datetime, rel: dict | None = None) -> dict:
    """Ajoute ou recalcule les listes des jours à venir ; fige celles d'aujourd'hui et des jours passés.
    Enregistre aussi l'analyse de chaque match à venir (rel : tableau de fiabilité du moteur)."""
    if rel is None:
        from ..football.engine import load_params
        rel = load_params().reliability
    today = picks.day_key(now)
    days = hist.setdefault("days", {})
    for day, e in days.items():
        if day <= today:
            e["frozen"] = True
    by_day: dict[str, list[dict]] = {}
    for m in matches:
        by_day.setdefault(picks.day_key(m["kickoff"]), []).append(m)
    for day, ms in sorted(by_day.items()):
        if day < today:
            continue
        cur = days.get(day)
        if cur and cur.get("frozen"):
            _analyses(cur, ms, now, rel, keep=True)
            continue
        lists = day_lists(ms, after=now)
        entry = {"built": now.isoformat(timespec="seconds"), "frozen": day == today, "eng": _engine(ms), **lists}
        _analyses(entry, ms, now, rel, keep=False)
        if not entry["matches"]:
            continue
        days[day] = entry
    compact(hist, today)
    return hist


def _engine(ms: list[dict]) -> str:
    return next((m.get("engine") for m in ms if m.get("engine")), "v1")


def compact(hist: dict, today: str) -> None:
    """Au-delà de AN_DAYS jours : on ne garde que le bilan des analyses du jour (et les matchs des paris)."""
    limit = (datetime.fromisoformat(today) - timedelta(days=AN_DAYS)).date().isoformat()
    for day, e in (hist.get("days") or {}).items():
        if day >= limit or "an" not in e:
            continue
        e["an_sum"] = an_stats(e)
        used = {c["mid"] for lst in (e.get("tiers") or {}).values() for c in lst} \
            | {c["mid"] for cp in e.get("coupons") or [] for c in cp["legs"]}
        e["matches"] = {mid: mt for mid, mt in (e.get("matches") or {}).items() if mid in used}
        del e["an"]


def _scores_from_cache() -> dict[str, dict]:
    """Matchs déjà téléchargés (journées de championnat, coupes) : idEvent -> événement TheSportsDB."""
    out = {}
    for f in (CACHE / "tsdb").glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        for e in (data.get("events") or []) if isinstance(data, dict) else []:
            if isinstance(e, dict) and e.get("idEvent"):
                out[str(e["idEvent"])] = e
    return out


_VOID_STATUS = {"postponed", "pst", "cancelled", "canc", "abandoned", "abd"}


class _FdRows:
    """Matchs joués des fichiers football-data déjà téléchargés : (championnat, date, domicile, extérieur) -> ligne."""

    def __init__(self):
        self.files: dict[tuple[str, str], dict] = {}

    def find(self, code: str, kickoff: str, home: str, away: str):
        ko = datetime.fromisoformat(kickoff)
        season = season_codes(current_season_start(ko.date()), 1)[0]
        rows = self.files.get((code, season))
        if rows is None:
            path = CACHE / f"{code}_{season}.csv"
            rows = {}
            if path.exists():
                for r in parse_csv(path.read_bytes(), code):
                    if r.played:
                        rows[(r.date.isoformat(), r.home, r.away)] = r
            self.files[(code, season)] = rows
        for d in (ko.date(), (ko - timedelta(hours=12)).date(), (ko + timedelta(hours=12)).date()):
            r = rows.get((d.isoformat(), home, away))
            if r:
                return r
        return None


def _has_counts(e: dict, mid: str) -> bool:
    return any(d["k"] in ("co", "ca") for d in ((e.get("an") or {}).get(mid) or {}).get("v", []))


def settle(hist: dict, now: datetime, lookups: int = MAX_LOOKUPS) -> int:
    """Remplit les scores des matchs terminés, puis le résultat de chaque pari et de chaque coupon."""
    known = None
    fd = _FdRows()
    filled = 0
    for day in sorted(hist.get("days", {})):
        e = hist["days"][day]
        if not e.get("frozen"):
            continue
        for mid, mt in e.get("matches", {}).items():
            ko = datetime.fromisoformat(mt["kickoff"])
            lg = BY_CODE.get(mt["league"])
            domestic = bool(lg and lg.category == "domestic" and mt.get("fd"))
            # Corners et cartons : chiffres de football-data (championnats), sinon « non vérifiable »
            if mt.get("score") and not mt.get("st") and not mt.get("nost") and _has_counts(e, mid):
                row = fd.find(mt["league"], mt["kickoff"], *mt["fd"]) if domestic else None
                st = {}
                if row:
                    if (c := signals.corners(row)):
                        st["corners"] = [int(c[0]), int(c[1])]
                    if (c := signals.cards(row)):
                        st["cards"] = [int(c[0]), int(c[1])]
                if st:
                    mt["st"] = st
                elif not domestic or now > ko + GIVE_UP_AFTER:
                    mt["nost"] = True
            if mt.get("score") or mt.get("void"):
                continue
            if now < ko + SETTLE_AFTER:
                continue
            if known is None:
                known = _scores_from_cache()
            ev = known.get(mid)
            sc = fixtures.score(ev) if ev else None
            if sc is None and domestic:
                row = fd.find(mt["league"], mt["kickoff"], *mt["fd"])
                if row:
                    sc = (row.fthg, row.ftag)
            if sc is None and lookups > 0:
                lookups -= 1
                res = fixtures._get("lookupevent", {"id": mid}, 2)
                ev = ((res or {}).get("events") or [None])[0]
                if ev:
                    known[mid] = ev
                    sc = fixtures.score(ev)
            status = ((ev or {}).get("strStatus") or "").strip().lower()
            if sc:
                mt["score"] = list(sc)
                filled += 1
            elif status in _VOID_STATUS or now > ko + GIVE_UP_AFTER:
                mt["void"] = True
                filled += 1
        _apply_results(e)
    return filled


def _leg_result(e: dict, c: dict) -> str | None:
    mt = e["matches"].get(c["mid"]) or {}
    if mt.get("void"):
        return "void"
    if not mt.get("score"):
        return None
    hg, ag = mt["score"]
    return picks.settle(c["key"], c["line"], c["sel"], hg, ag)


def verdict_results(e: dict, mid: str, rec: dict) -> list:
    """Résultat de chaque verdict d'un match : won, lost, void, nv (non vérifiable) ou None (en attente)."""
    mt = (e.get("matches") or {}).get(mid) or {}
    out = []
    for d in rec.get("v", []):
        if mt.get("void"):
            out.append("void")
            continue
        if not mt.get("score"):
            out.append(None)
            continue
        r = vd.settle(verdict_of(d), *mt["score"], mt.get("st"))
        if r is None and d["k"] in ("co", "ca") and (mt.get("nost") or mt.get("st")):
            r = NV
        out.append(r)
    return out


def an_stats(e: dict) -> dict:
    """Bilan des analyses d'un jour : verdicts justes (hors « serré » et non vérifiables), et le plus sûr."""
    if "an" not in e:
        return e.get("an_sum") or {"n": 0, "won": 0, "ann": None, "bn": 0, "bw": 0, "m": 0}
    n = won = bn = bw = 0
    ann = 0.0
    for rec in e["an"].values():
        for i, (d, r) in enumerate(zip(rec.get("v", []), rec.get("r") or [])):
            if d.get("o") or r not in ("won", "lost"):
                continue
            n += 1
            won += r == "won"
            ann += d["p"]
            if i == rec.get("b"):
                bn += 1
                bw += r == "won"
    return {"n": n, "won": won, "ann": ann / n if n else None, "bn": bn, "bw": bw, "m": len(e["an"])}


def _apply_results(e: dict) -> None:
    for mid, rec in (e.get("an") or {}).items():
        rec["r"] = verdict_results(e, mid, rec)
    for lst in e.get("tiers", {}).values():
        for c in lst:
            c["res"] = _leg_result(e, c)
    for cp in e.get("coupons", []):
        for c in cp["legs"]:
            c["res"] = _leg_result(e, c)
        cp["res"] = picks.coupon_result([c["res"] for c in cp["legs"]])


def save(hist: dict, public_dir: Path, now: datetime) -> None:
    hist["version"] = VERSION
    hist["updated"] = now.isoformat(timespec="seconds")
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    LOCAL.write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    public_dir.mkdir(parents=True, exist_ok=True)
    (public_dir / "history.json").write_text(json.dumps(public_copy(hist, now), ensure_ascii=False,
                                                        separators=(",", ":")), encoding="utf-8")
    key = _key()
    if key:
        (public_dir / FULL_NAME).write_bytes(seal(hist, key))
    else:
        print(f"  Attention : {KEY_ENV} absente, copie complète de l'historique non publiée "
              "(la mise à jour automatique ne pourrait pas reprendre l'historique).")


# --- Bilan ------------------------------------------------------------------------------------------------

def _rate(items: list[tuple[float, str]]) -> dict:
    done = [(p, r) for p, r in items if r in ("won", "lost")]
    n, won = len(done), sum(1 for _, r in done if r == "won")
    return {"n": n, "won": won, "rate": won / n if n else None,
            "announced": sum(p for p, _ in done) / n if n else None}


def summary(days: dict) -> dict:
    """Taux de réussite par niveau et par coupon, comparé à la chance annoncée."""
    tiers = {t: _rate([(c["p"], c.get("res")) for e in days.values() if e.get("frozen")
                       for c in e.get("tiers", {}).get(t, [])]) for t in picks.TIERS}
    coupons = {}
    for target in picks.COUPON_TARGETS:
        coupons[target] = _rate([(cp["p"], cp.get("res")) for e in days.values() if e.get("frozen")
                                 for cp in e.get("coupons", []) if cp["target"] == target])
    return {"tiers": tiers, "coupons": coupons,
            "days": sum(1 for e in days.values() if e.get("frozen"))}
