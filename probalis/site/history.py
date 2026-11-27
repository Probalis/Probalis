"""Historique des paris du jour : enregistrés avant les matchs, réglés tout seuls avec le score final.

Le fichier vit sur le site lui-même (/data/history.json) : chaque construction relit la version en ligne,
y ajoute les listes des jours à venir et les résultats des matchs terminés, puis la republie.
La version en ligne ne montre que les paris réglés : les paris en attente sont des contenus Premium, ils n'y
figurent pas (le jour est alors marqué « sealed »). La version complète est gardée dans data/cache/history.json.

Pendant un match (score en direct de TheSportsDB) : un pari ou un verdict déjà joué d'avance est réglé tout de suite.
Exemple : « plus de 1,5 but » à 2-0 est gagné quoi qu'il arrive ensuite (les buts ne s'effacent pas), « moins de 2,5
buts » à 2-1… perdu dès le 3e but. Un pari qui peut encore changer (1X2, double chance…) attend le score final.
Le score final, quand il arrive, refait tous les calculs (il corrige aussi un but annulé après coup). Un match que
TheSportsDB marque déjà « fini » est réglé tout de suite ; sinon on attend 2 h 30 après le coup d'envoi.

Règle d'honnêteté : la liste d'un jour est figée dès le premier calcul fait ce jour-là (ou plus tard) ;
ensuite elle ne change plus, même si le modèle change d'avis. Les listes des jours suivants restent
provisoires jusque-là. Tout pari enregistré a donc été publié avant le coup d'envoi de son match.

Listes par type (« fam », depuis le 27/11/2026) : les filtres de l'onglet Paris (Résultat, Buts, Les deux marquent,
Une équipe marque) ont aussi leurs listes, figées et réglées comme les autres : leur réussite se prouve de la même façon.
Le jour de leur mise en ligne, la liste d'aujourd'hui (déjà figée) les reçoit une seule fois, pour les matchs pas encore
commencés.

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
from ..football import espn, fixtures, signals
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
ESPN_WAIT = timedelta(hours=24)                  # corners et cartons ESPN (coupes, Arabie, femmes) : un jour au plus


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
    return (bool(e.get("frozen")), not e.get("sealed"), _settled(e), len(e.get("an") or {}), "fam" in e)


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
        fam = {f: {t: [c for c in lst if c.get("res")] for t, lst in by.items()} for f, by in (e.get("fam") or {}).items()}
        coupons = [cp for cp in e.get("coupons") or [] if coupon_shown(cp)]
        ms = e.get("matches") or {}
        an = {mid: rec for mid, rec in (e.get("an") or {}).items() if match_over(ms.get(mid) or {}, now)}
        hidden = sum(len(lst) for lst in (e.get("tiers") or {}).values()) + len(e.get("coupons") or []) \
            - sum(len(lst) for lst in tiers.values()) - len(coupons) + len(e.get("an") or {}) - len(an) \
            + _n_fam(e.get("fam")) - _n_fam(fam)
        used = _used({"tiers": tiers, "fam": fam, "coupons": coupons}) | set(an)
        d = {k: v for k, v in e.items() if k not in ("tiers", "fam", "coupons", "matches", "an")}
        d.update(tiers=tiers, coupons=coupons, matches={mid: mt for mid, mt in ms.items() if mid in used})
        if "fam" in e:
            d["fam"] = fam
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
    """Ce qu'on garde de l'analyse d'un match : ses verdicts, les paris du match montrés sur la fiche (« pk », depuis
    le 27/11/2026 ; « b » = le premier, le plus sûr), le 1X2, le score le plus probable. Tous les verdicts restent
    enregistrés (tests de fiabilité), mais le bilan d'un match qui a « pk » ne compte que ses paris du match."""
    vs = vd.verdicts(m["markets"])
    pk = vd.picks(vs)
    rec = {"v": [_vslim(v) for v in vs], "pk": pk, "b": pk[0] if pk else None, "eng": m.get("engine", "v1")}
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


def _fam_picks(e: dict) -> list[dict]:
    """Tous les paris des listes par type d'un jour (filtre -> niveau -> liste)."""
    return [c for by in (e.get("fam") or {}).values() for lst in by.values() for c in lst]


def _n_fam(fam: dict | None) -> int:
    return len(_fam_picks({"fam": fam}))


def _used(e: dict) -> set:
    """Matchs des paris d'un jour : listes des niveaux, listes par type, coupons."""
    return ({c["mid"] for lst in (e.get("tiers") or {}).values() for c in lst} | {c["mid"] for c in _fam_picks(e)}
            | {c["mid"] for cp in e.get("coupons") or [] for c in cp["legs"]})


def fam_lists(matches: list[dict], after: datetime | None) -> dict:
    """Listes des filtres de l'onglet Paris : filtre -> niveau -> les 5 plus sûrs de ce type."""
    return {f: {t: [_slim(c) for c in picks.tier_picks(matches, t, after=after, fams=fs)] for t in picks.TIERS}
            for f, fs in picks.FILTERS.items()}


def day_lists(matches: list[dict], after: datetime | None) -> dict:
    """Les trois listes, les listes par type et les coupons d'un jour, avec ce qu'il faut pour les afficher plus tard."""
    out = {"tiers": {t: [_slim(c) for c in picks.tier_picks(matches, t, after=after)] for t in picks.TIERS},
           "fam": fam_lists(matches, after),
           "coupons": [{"target": cp["target"], "p": cp["p"], "fair": cp["fair"], "book": cp["book"],
                        "legs": [_slim(c) for c in cp["legs"]]} for cp in picks.day_coupons(matches, after=after)]}
    by_id = {m["id"]: m for m in matches}
    out["matches"] = {mid: _match_info(by_id[mid]) for mid in sorted(_used(out))}
    return out


def _add_fam(e: dict, ms: list[dict], now: datetime) -> None:
    """Listes par type ajoutées une seule fois à un jour déjà figé qui n'en a pas (jour de la mise en ligne des filtres) :
    seulement les matchs pas encore commencés ; rien de ce qui est déjà enregistré ne change."""
    e["fam"] = fam_lists(ms, after=now)
    by_id = {m["id"]: m for m in ms}
    for c in _fam_picks(e):
        e.setdefault("matches", {}).setdefault(c["mid"], _match_info(by_id[c["mid"]]))


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
            if "fam" not in cur:
                _add_fam(cur, ms, now)
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
        used = _used(e)
        e["matches"] = {mid: mt for mid, mt in (e.get("matches") or {}).items() if mid in used}
        del e["an"]


LIVE_EXTRA = 10  # buts encore possibles pour chaque équipe, pour savoir si un pari est déjà joué d'avance


def live_result(settle_fn, hg: int, ag: int) -> str | None:
    """« won » ou « lost » si le pari a le même résultat quel que soit le nombre de buts encore à venir (score en
    direct hg-ag) ; None s'il peut encore changer. settle_fn(buts domicile, buts extérieur) -> won / lost / void…"""
    seen = set()
    for i in range(LIVE_EXTRA + 1):
        for j in range(LIVE_EXTRA + 1):
            seen.add(settle_fn(hg + i, ag + j))
            if len(seen) > 1:
                return None
    r = seen.pop()
    return r if r in ("won", "lost") else None


def live_scores(hist: dict) -> dict[str, tuple[int, int]]:
    """Matchs en cours avec leur score en direct (relevé par settle) : id -> (buts domicile, buts extérieur)."""
    return {mid: tuple(mt["live"]) for e in (hist.get("days") or {}).values()
            for mid, mt in (e.get("matches") or {}).items() if mt.get("live") and not mt.get("score")}


def shown(rec: dict) -> list[int]:
    """Verdicts d'une analyse montrés et comptés : ses paris du match (depuis le 27/11/2026), sinon tous (avant)."""
    return list(rec["pk"]) if "pk" in rec else list(range(len(rec.get("v") or [])))


def live_decided(mt: dict, rec: dict) -> bool:
    """Match en cours avec au moins un verdict déjà joué d'avance (affiché tout de suite dans l'historique)."""
    vs, res = rec.get("v") or [], rec.get("r") or []
    return (bool(mt.get("live")) and not mt.get("score") and not mt.get("void")
            and any(i < len(res) and res[i] in ("won", "lost") and not vs[i].get("o") for i in shown(rec)))


def coupon_shown(cp: dict) -> str | None:
    """Résultat d'un coupon à afficher (et à publier) : seulement quand chacun de ses paris est réglé. Un coupon
    perdu dès son premier match ne dévoile pas les paris de ses matchs encore à jouer."""
    return cp.get("res") if all(c.get("res") for c in cp.get("legs") or []) else None


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

    def _rows(self, code: str, ko: datetime) -> dict:
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
        return rows

    @staticmethod
    def _days(ko: datetime) -> list[str]:
        return [d.isoformat() for d in (ko.date(), (ko - timedelta(hours=12)).date(), (ko + timedelta(hours=12)).date())]

    def find(self, code: str, kickoff: str, home: str, away: str):
        ko = datetime.fromisoformat(kickoff)
        rows = self._rows(code, ko)
        for d in self._days(ko):
            r = rows.get((d, home, away))
            if r:
                return r
        return None

    def find_named(self, code: str, kickoff: str, home: str, away: str):
        """Même recherche avec les noms TheSportsDB, pour un match enregistré sans ses noms football-data (avant le
        21/11/2026). Les deux équipes doivent tomber sur le même match de ce jour-là : pas de mauvais rapprochement."""
        ko = datetime.fromisoformat(kickoff)
        days = set(self._days(ko))
        cands = [r for (d, _, _), r in self._rows(code, ko).items() if d in days]
        if not cands:
            return None
        names = fixtures.match_names([home, away], sorted({n for r in cands for n in (r.home, r.away)}))
        h, a = names.get(home), names.get(away)
        return next((r for r in cands if (r.home, r.away) == (h, a)), None) if h and a else None


def _has_counts(e: dict, mid: str) -> bool:
    return any(d["k"] in ("co", "ca") for d in ((e.get("an") or {}).get(mid) or {}).get("v", []))


def _fd_row(fd: _FdRows, mt: dict):
    """Ligne football-data d'un match de championnat (score, corners, cartons), ou None."""
    lg = BY_CODE.get(mt["league"])
    if not (lg and lg.category == "domestic"):
        return None
    if mt.get("fd"):
        return fd.find(mt["league"], mt["kickoff"], *mt["fd"])
    return fd.find_named(mt["league"], mt["kickoff"], mt["home"]["name"], mt["away"]["name"])


def link_espn(hist: dict, now: datetime) -> int:
    """Relie à ESPN les matchs de l'historique qui ne le sont pas encore (des 6 derniers jours aux 2 prochains) :
    leur n° ESPN sert au direct des fiches et aux corners et cartons. Un match de coupe, d'Arabie saoudite ou
    féminin marqué « non vérifiable » avant ESPN (règle d'avant le 26/11/2026) est remis en attente de ses chiffres."""
    items, where = [], {}
    for day, e in (hist.get("days") or {}).items():
        for mid, mt in (e.get("matches") or {}).items():
            if mt.get("espn") or mt.get("league") not in espn.SLUGS:
                continue
            ko = datetime.fromisoformat(mt["kickoff"])
            if not (now - GIVE_UP_AFTER <= ko <= now + timedelta(days=espn.WINDOW[1])):
                continue
            key = f"{day}|{mid}"
            items.append({"key": key, "league": mt["league"], "kickoff": mt["kickoff"],
                          "home": mt["home"]["name"], "away": mt["away"]["name"]})
            where[key] = mt
    refs = espn.link(items, now) if items else {}
    for key, ref in refs.items():
        mt = where[key]
        mt["espn"] = ref
        if mt.get("nost") and not mt.get("st"):
            mt.pop("nost")
    return len(refs)


def espn_refs(hist: dict) -> dict[str, list]:
    """N° ESPN de chaque match de l'historique : id TheSportsDB -> [championnat ESPN, n° du match, jour]."""
    return {mid: mt["espn"] for e in (hist.get("days") or {}).values()
            for mid, mt in (e.get("matches") or {}).items() if mt.get("espn")}


def _counts_hopeless(mt: dict, ko: datetime, now: datetime, domestic: bool) -> bool:
    """Plus la peine d'attendre les corners et cartons d'un match fini : « non vérifiable »."""
    if now > ko + GIVE_UP_AFTER:
        return True
    if domestic:
        return False                      # football-data les publie dans les jours qui suivent
    if mt.get("league") not in espn.SLUGS:
        return True                       # ni ESPN ni football-data (Frauen-Bundesliga, Serie A féminine)
    ref = mt.get("espn")
    if ref and espn.finished_badly(ref):
        return True                       # prolongation, tirs au but ou suivi incomplet chez ESPN
    return now > ko + ESPN_WAIT


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
            domestic = bool(lg and lg.category == "domestic")
            # Match de championnat enregistré sans ses noms football-data (listes faites avant le 21/11/2026) et marqué
            # « non vérifiable » trop tôt : on recherche ses chiffres jusqu'à GIVE_UP_AFTER, comme les autres.
            if domestic and mt.get("nost") and not mt.get("fd") and not mt.get("st") and now <= ko + GIVE_UP_AFTER:
                mt.pop("nost")
            # Corners et cartons : ESPN dès la fin du match (championnats, coupes d'Europe, Arabie saoudite, femmes),
            # sinon football-data (championnats, quelques jours après), sinon « non vérifiable »
            if mt.get("score") and not mt.get("st") and not mt.get("nost") and _has_counts(e, mid):
                st = (espn.counts(mt["espn"]) if mt.get("espn") else None) or {}
                if not st and (row := _fd_row(fd, mt)):
                    if (c := signals.corners(row)):
                        st["corners"] = [int(c[0]), int(c[1])]
                    if (c := signals.cards(row)):
                        st["cards"] = [int(c[0]), int(c[1])]
                if st:
                    mt["st"] = st
                elif _counts_hopeless(mt, ko, now, domestic):
                    mt["nost"] = True
            if mt.get("score") or mt.get("void"):
                mt.pop("live", None)
                continue
            if now < ko:
                continue
            if known is None:
                known = _scores_from_cache()
            ev = known.get(mid)
            live = fixtures.live_score(ev) if ev else None
            if live:
                mt["live"] = list(live)  # match en cours : paris déjà joués d'avance réglés plus bas
            if now < ko + SETTLE_AFTER:
                sc = fixtures.final_score(ev) if ev else None  # déjà marqué « fini » : réglé tout de suite
                if not sc:
                    continue
            else:
                sc = fixtures.score(ev) if ev else None
            if sc is None and domestic:
                row = _fd_row(fd, mt)
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
                mt.pop("live", None)
                filled += 1
            elif (live := fixtures.live_score(ev) if ev else None):
                mt["live"] = list(live)  # match pas encore fini (prolongations, retard)
            elif status in _VOID_STATUS or now > ko + GIVE_UP_AFTER:
                mt["void"] = True
                mt.pop("live", None)
                filled += 1
        _apply_results(e)
    return filled


def _leg_result(e: dict, c: dict) -> str | None:
    mt = e["matches"].get(c["mid"]) or {}
    if mt.get("void"):
        return "void"
    if not mt.get("score"):
        if mt.get("live"):
            return live_result(lambda h, a: picks.settle(c["key"], c["line"], c["sel"], h, a), *mt["live"])
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
            live = mt.get("live")
            ok = live and d["k"] not in ("co", "ca")  # corners et cartons : pas de chiffres en direct
            out.append(live_result(lambda h, a, v=verdict_of(d): vd.settle(v, h, a), *live) if ok else None)
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
        vs, res = rec.get("v", []), rec.get("r") or []
        for i in shown(rec):
            if i >= len(res):
                continue
            d, r = vs[i], res[i]
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
    for c in _fam_picks(e):
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
    """Taux de réussite par niveau, par coupon et par type de pari (listes des filtres), comparé à la chance annoncée."""
    tiers = {t: _rate([(c["p"], c.get("res")) for e in days.values() if e.get("frozen")
                       for c in e.get("tiers", {}).get(t, [])]) for t in picks.TIERS}
    fams = {f: _rate([(c["p"], c.get("res")) for e in days.values() if e.get("frozen")
                      for lst in ((e.get("fam") or {}).get(f) or {}).values() for c in lst]) for f in picks.FILTERS}
    coupons = {}
    for target in picks.COUPON_TARGETS:
        coupons[target] = _rate([(cp["p"], cp.get("res")) for e in days.values() if e.get("frozen")
                                 for cp in e.get("coupons", []) if cp["target"] == target])
    return {"tiers": tiers, "coupons": coupons, "fams": fams,
            "has_fam": any("fam" in e for e in days.values() if e.get("frozen")),
            "days": sum(1 for e in days.values() if e.get("frozen"))}
