"""Textes de l'interface et noms des marchés, en français et en anglais."""
from __future__ import annotations

import unicodedata

LANGS = ("fr", "en")

UI = {
    "fr": {
        "tagline": "La science du pari",
        "tab_matches": "Matchs", "tab_bets": "Paris", "tab_ticket": "Ticket", "tab_history": "Historique",
        "soon": "Bientôt disponible",
        "ticket_soon": "Le constructeur de ticket arrive : ajoute tes sélections, l'appli calcule la vraie chance que ton ticket passe et s'il vaut le coup.",
        "history_soon": "Chaque pronostic sera enregistré ici avec son résultat, pour que tu puisses vérifier notre fiabilité.",
        "upcoming": "Matchs à venir", "no_matches": "Aucun match à venir pour l'instant.",
        "xg": "Buts attendus", "confidence": "Confiance",
        "conf_high": "Élevée", "conf_medium": "Moyenne", "conf_low": "Faible",
        "probability": "Probabilité", "fair_odds": "Cote juste", "best_odds": "Meilleure cote", "margin": "Marge",
        "push": "remboursé",
        "source": "Source",
        "src_market": "Cotes du marché + modèle", "src_model": "Modèle statistique seul",
        "src_market_help": "Les buts attendus sont calés sur les cotes des bookmakers, puis tous les marchés en sont déduits.",
        "src_model_help": "Pas encore de cotes pour ce match : estimation par notre modèle seul, moins précise.",
        "odds_note": "Cotes relevées sur football-data.co.uk (meilleure cote et marge moyenne des bookmakers). Vérifie toujours la cote chez ton bookmaker avant de parier.",
        "odds_note_api": "Cotes relevées sur The Odds API (moyenne d'au moins deux bookmakers européens). Vérifie toujours la cote chez ton bookmaker avant de parier.",
        "no_odds": "Pas encore de cotes bookmaker pour ce match : compare toi-même la cote juste à celle de ton bookmaker.",
        "fair_help": "Cote juste = la cote sans la marge du bookmaker. Si ton bookmaker propose plus, c'est un meilleur prix que la moyenne, pas une garantie de gain.",
        "reliability": "Notre fiabilité, sans maquillage",
        "reliability_text": "Nous avons rejoué toute la saison 2025/26 (3 276 matchs, 10 championnats). Résultat : aucune méthode simple ne bat les cotes des bookmakers juste avant le match. Les « coups sûrs » et « paris en or » promis ailleurs n'existent pas. Probalis te donne donc les vraies probabilités de chaque pari, calées sur le marché, pour que tu saches exactement ce que tu joues.",
        "likely": "Les plus probables", "likely_help": "Les issues les plus probables des prochains matchs. Probable ne veut pas dire rentable : compare toujours ta cote avec la cote juste.",
        "no_likely": "Aucun match à venir pour l'instant.",
        "see_analysis": "Voir l'analyse", "all_markets": "Tous les marchés",
        "draw": "Nul", "kickoff": "Coup d'envoi",
        "responsible": "18+ · Les probabilités ne sont pas des certitudes. Ne mise jamais plus que ce que tu peux perdre.",
        "data_credit": "Données : football-data.co.uk, TheSportsDB.",
        "data_credit_api": "Données : football-data.co.uk, TheSportsDB, The Odds API.",
        "updated": "Mis à jour le",
        "theme": "Changer de thème", "lang_switch": "English", "lang_version": "English version",
        "groups": {"main": "Principaux", "goals": "Buts", "teams": "Équipes", "handicaps": "Handicaps",
                   "scores": "Score exact", "halves": "Mi-temps", "combos": "Combinés",
                   "corners": "Corners & cartons"},
        # Accueil
        "nav_label": "Navigation principale", "site_link": "Découvrir Probalis",
        "this_week": "Cette semaine", "matches_title": "Les matchs du jour", "choose_day": "Choisir le jour",
        "all_week": "Toute la semaine", "all_leagues": "Toutes", "leagues_title": "Championnats",
        "leagues_filter": "Choisir les championnats", "reset": "Réinitialiser",
        "search_league": "Rechercher un championnat ou un pays",
        "sec_popular": "Les plus suivis", "sec_europe": "Coupes d'Europe", "sec_others": "Autres championnats",
        "sec_lower": "Divisions inférieures",
        "sec_women": "Féminin",
        "n_matches": "{n} matchs", "one_match": "1 match", "no_match_week": "Pas de match cette semaine",
        "see_all": "Tout voir", "featured": "À la une", "vs": "VS",
        "over25_short": "+2,5 buts", "btts_short": "Les 2 marquent",
        "empty_filter": "Aucun match pour ces championnats ce jour-là.", "show_all_leagues": "Voir tous les championnats",
        "no_league_found": "Aucun championnat trouvé.",
        # Page match
        "back": "Retour aux matchs", "share": "Partager ce match", "round": "J{n}", "final": "Finale",
        "home_win": "Victoire {team}", "draw_long": "Match nul",
        "chip_market": "Calé sur les cotes", "chip_model": "Modèle statistique",
        "conf_chip_high": "Confiance élevée", "conf_chip_medium": "Confiance moyenne", "conf_chip_low": "Confiance faible",
        "summary": "Résumé", "market_tabs": "Catégories de marchés", "xg_total": "Total attendu : {x} buts",
        "top_scores_title": "Scores les plus probables", "key_markets": "Marchés clés", "chance": "Chance",
        "see_n_markets": "Voir les {n} marchés", "n_markets": "{n} marchés",
        "total_goals": "Total de buts", "goals_word": "buts", "team_scores": "{team} marque", "goals_of": "Buts de {team}",
        "ht_lead": "{team} mène à la pause", "ht_draw": "Nul à la pause", "first_half": "1re mi-temps",
        "compare_title": "Compare ta cote", "compare_text": "Entre la cote de ton bookmaker : on te dit si c'est un bon prix.",
        "compare_pick": "Ton pari", "compare_odds": "Ta cote", "compare_placeholder": "ex. 1,95",
        "dnb_short": "remboursé si nul",
        "market_odds": "Cotes du marché", "ours": "Nous",
        # Paris
        "bets_title": "Paris", "rel_matches": "matchs rejoués (2025/26)", "rel_gold": "pour les « paris en or »",
        "rel_short": "Personne ne bat les bookmakers à coup sûr. On te donne les vraies chances de chaque pari, pour que tu saches ce que tu joues.",
        # Bientôt
        "ticket_title": "Ticket", "history_title": "Historique",
        "ticket_features": ["Ajoute tes sélections depuis n'importe quel match",
                            "La vraie chance que ton ticket passe",
                            "La cote juste du combiné, à comparer à celle de ton bookmaker"],
        "history_features": ["Chaque pronostic enregistré avant le coup d'envoi",
                             "Le vrai résultat juste à côté",
                             "Notre taux de réussite, sans rien cacher"],
    },
    "en": {
        "tagline": "The science of betting",
        "tab_matches": "Matches", "tab_bets": "Bets", "tab_ticket": "Slip", "tab_history": "History",
        "soon": "Coming soon",
        "ticket_soon": "The bet slip builder is on its way: add your picks and the app works out the real chance your slip wins and whether it's worth it.",
        "history_soon": "Every prediction will be recorded here with its result, so you can check how reliable we are.",
        "upcoming": "Upcoming matches", "no_matches": "No upcoming matches yet.",
        "xg": "Expected goals", "confidence": "Confidence",
        "conf_high": "High", "conf_medium": "Medium", "conf_low": "Low",
        "probability": "Probability", "fair_odds": "Fair odds", "best_odds": "Best odds", "margin": "Margin",
        "push": "refund",
        "source": "Source",
        "src_market": "Market odds + model", "src_model": "Statistical model only",
        "src_market_help": "Expected goals are calibrated on bookmaker odds, then every market is derived from them.",
        "src_model_help": "No odds for this match yet: estimate from our model alone, less precise.",
        "odds_note": "Odds collected from football-data.co.uk (best price and average bookmaker margin). Always check the price at your bookmaker before betting.",
        "odds_note_api": "Odds collected from The Odds API (average of at least two European bookmakers). Always check the price at your bookmaker before betting.",
        "no_odds": "No bookmaker odds for this match yet: compare the fair odds with your bookmaker's price yourself.",
        "fair_help": "Fair odds = the price without the bookmaker's margin. If your bookmaker offers more, it's a better price than average, not a guaranteed win.",
        "reliability": "Our track record, no make-up",
        "reliability_text": "We replayed the whole 2025/26 season (3,276 matches, 10 leagues). Result: no simple method beats bookmaker odds just before kick-off. The \"sure bets\" promised elsewhere don't exist. So Probalis gives you the real probability of every bet, calibrated on the market, so you know exactly what you're playing.",
        "likely": "Most likely", "likely_help": "The most likely outcomes of the next matches. Likely doesn't mean profitable: always compare your price with the fair odds.",
        "no_likely": "No upcoming matches yet.",
        "see_analysis": "See analysis", "all_markets": "All markets",
        "draw": "Draw", "kickoff": "Kick-off",
        "responsible": "18+ · Probabilities are not certainties. Never stake more than you can afford to lose.",
        "data_credit": "Data: football-data.co.uk, TheSportsDB.",
        "data_credit_api": "Data: football-data.co.uk, TheSportsDB, The Odds API.",
        "updated": "Updated",
        "theme": "Switch theme", "lang_switch": "Français", "lang_version": "Version française",
        "groups": {"main": "Main", "goals": "Goals", "teams": "Teams", "handicaps": "Handicaps",
                   "scores": "Correct score", "halves": "Halves", "combos": "Combos",
                   "corners": "Corners & cards"},
        # Home
        "nav_label": "Main navigation", "site_link": "About Probalis",
        "this_week": "This week", "matches_title": "Matches of the day", "choose_day": "Pick a day",
        "all_week": "All week", "all_leagues": "All", "leagues_title": "Competitions",
        "leagues_filter": "Choose competitions", "reset": "Reset",
        "search_league": "Search a competition or country",
        "sec_popular": "Most followed", "sec_europe": "European cups", "sec_others": "Other leagues",
        "sec_lower": "Lower divisions",
        "sec_women": "Women",
        "n_matches": "{n} matches", "one_match": "1 match", "no_match_week": "No match this week",
        "see_all": "See all", "featured": "Featured", "vs": "VS",
        "over25_short": "Over 2.5", "btts_short": "BTTS",
        "empty_filter": "No matches for these competitions that day.", "show_all_leagues": "Show all competitions",
        "no_league_found": "No competition found.",
        # Match page
        "back": "Back to matches", "share": "Share this match", "round": "MD{n}", "final": "Final",
        "home_win": "{team} win", "draw_long": "Draw",
        "chip_market": "Market-calibrated", "chip_model": "Statistical model",
        "conf_chip_high": "High confidence", "conf_chip_medium": "Medium confidence", "conf_chip_low": "Low confidence",
        "summary": "Summary", "market_tabs": "Market categories", "xg_total": "Expected total: {x} goals",
        "top_scores_title": "Most likely scores", "key_markets": "Key markets", "chance": "Chance",
        "see_n_markets": "See all {n} markets", "n_markets": "{n} markets",
        "total_goals": "Total goals", "goals_word": "goals", "team_scores": "{team} to score", "goals_of": "{team} goals",
        "ht_lead": "{team} ahead at half-time", "ht_draw": "Level at half-time", "first_half": "1st half",
        "compare_title": "Check your odds", "compare_text": "Enter your bookmaker's price: we'll tell you if it's a good one.",
        "compare_pick": "Your bet", "compare_odds": "Your odds", "compare_placeholder": "e.g. 1.95",
        "dnb_short": "draw no bet",
        "market_odds": "Market odds", "ours": "Us",
        # Bets
        "bets_title": "Bets", "rel_matches": "matches replayed (2025/26)", "rel_gold": "for so-called \"sure bets\"",
        "rel_short": "Nobody beats the bookmakers for sure. We give you the real chance of every bet, so you know exactly what you're playing.",
        # Coming soon
        "ticket_title": "Bet slip", "history_title": "History",
        "ticket_features": ["Add picks from any match",
                            "The real chance your slip wins",
                            "The fair price of the accumulator, to compare with your bookmaker's"],
        "history_features": ["Every prediction recorded before kick-off",
                             "The real result right next to it",
                             "Our hit rate, nothing hidden"],
    },
}

# Textes utilisés par app.js (formatage côté téléphone)
_JS = {
    "fr": {
        "today": "Auj.", "all_week": "Toute la semaine", "show_n": "Afficher {n} matchs", "show_one": "Afficher 1 match",
        "show_none": "Aucun match ce jour", "n_matches": "{n} matchs", "one_match": "1 match", "no_match_day": "Pas de match ce jour",
        "link_copied": "Lien copié", "colon": " : ", "chance": "Chance estimée : {p} · cote juste {fair}",
        "v_good": "Bon prix", "v_good_txt": "{odds} est au-dessus de la cote juste ({fair}).",
        "v_fair": "Prix correct", "v_fair_txt": "{odds} est proche de la cote juste ({fair}).",
        "v_bad": "Prix trop bas", "v_bad_txt": "{odds} est en dessous de la cote juste ({fair}) : le bookmaker garde environ {m} de marge.",
        "v_note": "Ce n'est pas une garantie de gain.",
        "v_model": "Pas encore de cotes pour ce match : estimation de notre modèle seul, moins précise.",
        "v_invalid": "Cote invalide", "v_invalid_txt": "Entre une cote supérieure à 1, par exemple 1,85.",
    },
    "en": {
        "today": "Today", "all_week": "All week", "show_n": "Show {n} matches", "show_one": "Show 1 match",
        "show_none": "No match that day", "n_matches": "{n} matches", "one_match": "1 match", "no_match_day": "No match that day",
        "link_copied": "Link copied", "colon": ": ", "chance": "Estimated chance: {p} · fair odds {fair}",
        "v_good": "Good price", "v_good_txt": "{odds} is above the fair odds ({fair}).",
        "v_fair": "Fair price", "v_fair_txt": "{odds} is close to the fair odds ({fair}).",
        "v_bad": "Price too low", "v_bad_txt": "{odds} is below the fair odds ({fair}): the bookmaker keeps about {m} margin.",
        "v_note": "It's not a guaranteed win.",
        "v_model": "No odds for this match yet: estimate from our model alone, less precise.",
        "v_invalid": "Invalid odds", "v_invalid_txt": "Enter odds above 1, for example 1.85.",
    },
}

JS_COLON = {lang: _JS[lang]["colon"] for lang in _JS}

_WEEKDAYS = {"fr": ("Lun.", "Mar.", "Mer.", "Jeu.", "Ven.", "Sam.", "Dim."),
             "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")}
_MONTHS = {"fr": ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."),
           "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")}


def js_strings(lang: str) -> dict:
    return {"lang": lang, **_JS[lang]}


def fold(s: str) -> str:
    """Texte sans accents ni majuscules, pour la recherche."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def dec(x: float, lang: str, digits: int = 1) -> str:
    s = f"{x:.{digits}f}"
    return s.replace(".", ",") if lang == "fr" else s


def day_short(d, lang: str) -> str:
    """« Sam. 21 » / « Sat 21 » (heure UTC : le téléphone affiche ensuite son heure locale)."""
    return f"{_WEEKDAYS[lang][d.weekday()]} {d.day}"


def weekday_short(d, lang: str) -> str:
    return _WEEKDAYS[lang][d.weekday()]


def day_med(d, lang: str) -> str:
    return f"{_WEEKDAYS[lang][d.weekday()]} {d.day} {_MONTHS[lang][d.month - 1]}"

GROUP_ORDER = ("main", "goals", "teams", "corners", "halves", "handicaps", "scores", "combos")


def num(x: float, lang: str, digits: int = 2) -> str:
    s = f"{x:.{digits}f}".rstrip("0").rstrip(".") if digits else f"{x:.0f}"
    return s.replace(".", ",") if lang == "fr" else s


def odds(x: float, lang: str) -> str:
    """Cote affichée comme chez les bookmakers : toujours deux décimales."""
    s = f"{x:.2f}"
    return s.replace(".", ",") if lang == "fr" else s


def line_txt(x: float, lang: str, signed: bool = False) -> str:
    s = num(abs(x), lang)
    if signed:
        return ("+" if x > 0 else "−" if x < 0 else "") + s
    return s


def pct(p: float, lang: str) -> str:
    v = round(p * 100)
    if 0 < p < 0.005:
        return "<1 %" if lang == "fr" else "<1%"
    return f"{v} %" if lang == "fr" else f"{v}%"


def market_title(key: str, line: float | None, lang: str, home: str, away: str) -> str:
    fr = lang == "fr"
    L = line_txt(line, lang) if line is not None else ""
    Ls = line_txt(line, lang, signed=True) if line is not None else ""
    t = {
        "1x2": ("Résultat du match (1X2)", "Match result (1X2)"),
        "dc": ("Double chance", "Double chance"),
        "dnb": ("Remboursé si match nul", "Draw no bet"),
        "btts": ("Les deux équipes marquent", "Both teams to score"),
        "ou": (f"Plus / moins de {L} buts", f"Over / under {L} goals"),
        "aou": (f"Total asiatique {L}", f"Asian total {L}"),
        "exact": ("Nombre exact de buts", "Exact total goals"),
        "multigoals": ("Multibuts", "Multigoals"),
        "oe": ("Total de buts pair ou impair", "Total goals odd or even"),
        "tt1": (f"{home} : plus / moins de {L} buts", f"{home}: over / under {L} goals"),
        "tt2": (f"{away} : plus / moins de {L} buts", f"{away}: over / under {L} goals"),
        "oe1": (f"{home} : buts pair ou impair", f"{home}: goals odd or even"),
        "oe2": (f"{away} : buts pair ou impair", f"{away}: goals odd or even"),
        "clean1": (f"{home} n'encaisse pas de but", f"{home} clean sheet"),
        "clean2": (f"{away} n'encaisse pas de but", f"{away} clean sheet"),
        "wtn": ("Gagne sans encaisser de but", "Win to nil"),
        "score4": ("Qui va marquer ?", "Teams to score"),
        "margin": ("Écart de victoire", "Winning margin"),
        "ah": (f"Handicap asiatique {home} {Ls}", f"Asian handicap {home} {Ls}"),
        "eh": (f"Handicap européen {home} {Ls}", f"European handicap {home} {Ls}"),
        "score": ("Score exact", "Correct score"),
        "1x2_ou": (f"Résultat + plus / moins de {L} buts", f"Result + over / under {L} goals"),
        "1x2_btts": ("Résultat + les deux équipes marquent", "Result + both teams to score"),
        "dc_btts": ("Double chance + les deux équipes marquent", "Double chance + both teams to score"),
        "dc_ou": (f"Double chance + plus / moins de {L} buts", f"Double chance + over / under {L} goals"),
        "ou_btts": (f"Plus / moins de {L} buts + les deux marquent", f"Over / under {L} + both teams to score"),
        "res_or_ou": (f"Résultat OU plus / moins de {L} buts", f"Result OR over / under {L} goals"),
        "htft": ("Mi-temps / fin de match", "Half-time / full-time"),
        "most_goals_half": ("Mi-temps la plus prolifique", "Highest scoring half"),
        "win_both1": (f"{home} gagne les deux mi-temps", f"{home} to win both halves"),
        "win_both2": (f"{away} gagne les deux mi-temps", f"{away} to win both halves"),
        "win_either1": (f"{home} gagne au moins une mi-temps", f"{home} to win either half"),
        "win_either2": (f"{away} gagne au moins une mi-temps", f"{away} to win either half"),
        "score_both_halves1": (f"{home} marque dans les deux mi-temps", f"{home} to score in both halves"),
        "score_both_halves2": (f"{away} marque dans les deux mi-temps", f"{away} to score in both halves"),
        "both_halves_over": (f"Plus de {L} but(s) dans chaque mi-temps", f"Over {L} goals in both halves"),
        "both_halves_under": (f"Moins de {L} but(s) dans chaque mi-temps", f"Under {L} goals in both halves"),
        "co": (f"Corners : plus / moins de {L}", f"Corners: over / under {L}"),
        "co1x2": ("Équipe qui obtient le plus de corners", "Team with the most corners"),
        "cot1": (f"Corners de {home} : plus / moins de {L}", f"{home} corners: over / under {L}"),
        "cot2": (f"Corners de {away} : plus / moins de {L}", f"{away} corners: over / under {L}"),
        "ca": (f"Cartons : plus / moins de {L}", f"Cards: over / under {L}"),
        "ca1x2": ("Équipe qui reçoit le plus de cartons", "Team with the most cards"),
        "cat1": (f"Cartons de {home} : plus / moins de {L}", f"{home} cards: over / under {L}"),
        "cat2": (f"Cartons de {away} : plus / moins de {L}", f"{away} cards: over / under {L}"),
    }
    for half, (fr_h, en_h) in (("1h", ("1re mi-temps", "1st half")), ("2h", ("2e mi-temps", "2nd half"))):
        t[f"1x2_{half}"] = (f"{fr_h} : résultat", f"{en_h}: result")
        t[f"dc_{half}"] = (f"{fr_h} : double chance", f"{en_h}: double chance")
        t[f"btts_{half}"] = (f"{fr_h} : les deux équipes marquent", f"{en_h}: both teams to score")
        t[f"ou_{half}"] = (f"{fr_h} : plus / moins de {L} buts", f"{en_h}: over / under {L} goals")
        t[f"score_{half}"] = (f"{fr_h} : score exact", f"{en_h}: correct score")
    pair = t.get(key, (key, key))
    return pair[0] if fr else pair[1]


def _atom(tok: str, lang: str, home: str, away: str, line: float | None) -> str:
    fr = lang == "fr"
    L = line_txt(line, lang) if line is not None else ""
    return {
        "1": home, "2": away, "X": "nul" if fr else "draw",
        "1X": f"{home} ou nul" if fr else f"{home} or draw",
        "12": f"{home} ou {away}" if fr else f"{home} or {away}",
        "X2": f"nul ou {away}" if fr else f"draw or {away}",
        "over": f"plus de {L}" if fr else f"over {L}",
        "under": f"moins de {L}" if fr else f"under {L}",
        "yes": "les deux marquent" if fr else "both score",
        "no": "pas les deux" if fr else "not both",
    }.get(tok, tok)


def selection_label(key: str, sel: str, line: float | None, lang: str, home: str, away: str) -> str:
    fr = lang == "fr"
    L = line_txt(line, lang) if line is not None else ""
    if "&" in sel or "|" in sel:
        sep, word = ("&", " et " if fr else " and ") if "&" in sel else ("|", " ou " if fr else " or ")
        parts = [_atom(p, lang, home, away, line) for p in sel.split(sep)]
        txt = word.join(parts)
        return txt[0].upper() + txt[1:]
    if key == "htft":
        a, b = sel.split("/")
        m = {"1": home, "X": "Nul" if fr else "Draw", "2": away}
        return f"{m[a]} / {m[b]}"
    if sel in ("over", "under"):
        return (f"Plus de {L}" if fr else f"Over {L}") if sel == "over" else (f"Moins de {L}" if fr else f"Under {L}")
    if sel in ("yes", "no"):
        return ("Oui" if fr else "Yes") if sel == "yes" else ("Non" if fr else "No")
    if sel in ("odd", "even"):
        return ("Impair" if fr else "Odd") if sel == "odd" else ("Pair" if fr else "Even")
    if key == "score4":
        return {"none": "Aucune équipe" if fr else "Neither",
                "1": f"{home} seulement" if fr else f"{home} only",
                "2": f"{away} seulement" if fr else f"{away} only",
                "both": "Les deux" if fr else "Both"}[sel]
    if key == "margin":
        if sel == "X":
            return "Nul" if fr else "Draw"
        side, n = sel.split("+")
        team = home if side == "1" else away
        if n == "3":
            return f"{team} par 3 buts ou plus" if fr else f"{team} by 3+"
        return (f"{team} par {n} but{'s' if n != '1' else ''}") if fr else f"{team} by {n}"
    if key == "multigoals":
        a, b = sel.split("-")
        return f"{a} à {b} buts" if fr else f"{a}–{b} goals"
    if key == "exact":
        return (f"{sel} but{'s' if sel not in ('0', '1') else ''}") if fr else f"{sel} goal{'s' if sel != '1' else ''}"
    if key == "most_goals_half":
        return {"1h": "1re mi-temps" if fr else "1st half", "2h": "2e mi-temps" if fr else "2nd half",
                "equal": "Égalité" if fr else "Equal"}[sel]
    if key.startswith("score"):
        return ("Autre score" if fr else "Any other score") if sel == "other" else sel
    if key in ("ah", "eh"):
        if sel == "X":
            return "Nul (handicap)" if fr else "Handicap draw"
        if sel == "1":
            return f"{home} {line_txt(line, lang, True)}"
        return f"{away} {line_txt(-line, lang, True)}" if key == "ah" else away
    if sel == "X":
        return "Nul" if fr else "Draw"
    if sel == "1":
        return home
    if sel == "2":
        return away
    txt = _atom(sel, lang, home, away, line)
    return txt[:1].upper() + txt[1:]


# --- Comptes, Premium, publicités, pages légales, chargement (ajoutés le 19/11/2026) ----------------------
_EXTRA = {
    "fr": {
        "tab_account": "Compte",
        "legal_privacy": "Confidentialité", "legal_terms": "Conditions", "legal_responsible": "Jeu responsable",
        "premium": "Premium", "loading": "Chargement…",
        # Publicité maison
        "ad_label": "Publicité", "ad_title": "Probalis Premium",
        "ad_text": "Toutes les analyses de chaque match, sans pub.", "ad_cta": "Découvrir",
        # Marchés verrouillés
        "lock_pill": "Premium", "lock_title": "Analyse verrouillée",
        "lock_text": "Les {n} marchés de ce match (1X2, buts, handicaps, score exact, mi-temps…) sont dans Premium, ou dans ton analyse gratuite du jour.",
        "lock_cta": "Passer Premium", "lock_free": "Avec un compte gratuit : 1 analyse complète par jour, sur le match de ton choix.",
        # Gratuit : 1 analyse complète par jour
        "free_title": "Ton analyse gratuite du jour",
        "free_text": "Avec ton compte gratuit, tu as droit à 1 analyse complète par jour, sur le match de ton choix. Tu l'utilises sur ce match ?",
        "free_signin_text": "Crée ton compte gratuit (avec Google, en quelques secondes) : tu débloques 1 analyse complète par jour, sur le match de ton choix.",
        "free_signin_btn": "Me connecter gratuitement",
        "free_use": "Voir l'analyse de ce match",
        "free_used_title": "Analyse gratuite du jour déjà utilisée",
        "free_used_text": "Tu l'as utilisée sur",
        "free_next": "Prochaine analyse gratuite demain. Avec Premium, tous les matchs sont débloqués.",
        "free_this": "Analyse gratuite du jour : ce match. La prochaine sera disponible demain.",
        # Récompenses, parrainage, notifications
        "tab_account_short": "Mon compte", "tab_rewards": "Récompenses",
        "rw_title": "Récompenses",
        "rw_lead": "Tes cadeaux et tes analyses offertes. Invite tes amis pour en gagner d'autres.",
        "rw_signin": "Connecte-toi pour voir tes récompenses et ton lien d'invitation.",
        "rw_signin_btn": "Me connecter",
        "rw_balance": "Analyses offertes",
        "rw_balance_help": "Chacune ouvre l'analyse complète d'un match de ton choix : sur la page du match, touche « Utiliser une analyse offerte ».",
        "rw_waiting": "À activer", "rw_history": "Historique",
        "rw_empty": "Pas encore de récompense. Invite un ami : tu gagnes des analyses dès son inscription.",
        "inv_title": "Invite tes amis",
        "inv_lead": "Partage ton lien. Tu gagnes des analyses offertes à chaque étape de ton ami :",
        "inv_signup": "Il crée son compte", "inv_active": "Il utilise Probalis {d} jours différents",
        "inv_buy": "Il prend un pass Premium", "inv_buy_detail": "selon la durée du pass",
        "inv_welcome": "Et ton ami reçoit {n} analyses offertes en bienvenue.",
        "inv_cap": "Inscriptions et activité : jusqu'à {n} amis récompensés par mois. Achats : sans limite.",
        "inv_link": "Ton lien d'invitation", "inv_copy": "Copier", "inv_share_wa": "WhatsApp", "inv_share": "Partager",
        "push_title": "Notifications",
        "push_device": "Notifications sur ce téléphone",
        "push_device_help": "Tes récompenses, tes cadeaux et l'activation de ton Premium.",
        "push_daily": "Analyses du jour prêtes", "push_daily_help": "Une notification par jour, le matin.",
        "push_ios": "Sur iPhone : ajoute d'abord Probalis à ton écran d'accueil (bouton Partager, puis « Sur l'écran d'accueil »), ouvre-le depuis là, puis reviens ici.",
        "push_unsupported": "Ce navigateur ne permet pas les notifications. Essaie avec Chrome.",
        "push_blocked": "Les notifications sont bloquées pour Probalis. Autorise-les dans les réglages du navigateur, puis réessaie.",
        "admin_link": "Ouvrir Probalis Office",
        "bonus_use": "Utiliser une analyse offerte",
        "free_extra": "Analyse offerte utilisée sur ce match : il reste ouvert pour toi.",
        "invp_kicker": "Invitation",
        "invp_title": "Ton ami t'invite sur Probalis",
        "invp_lead": "Les vraies probabilités de chaque match de foot, calculées à partir des cotes du marché. Pas de « coup sûr », juste des chiffres honnêtes.",
        "invp_gift": "{n} analyses offertes à ton inscription",
        "invp_gift_help": "En plus de ton analyse gratuite de chaque jour. Tu les utilises sur les matchs de ton choix.",
        "invp_perks": ["1 analyse complète gratuite par jour", "Les paris du jour classés par niveau de risque",
                       "Ton coupon analysé : sa vraie chance de passer", "L'historique de nos résultats, sans filtre"],
        "invp_cta": "Créer mon compte gratuit",
        "invp_have": "Tu as déjà un compte ? Le cadeau d'invitation est réservé aux nouveaux comptes, mais tu peux inviter tes amis à ton tour.",
        "invp_have_btn": "Voir mes récompenses",
        "invp_bad": "Ce lien d'invitation est incomplet. Tu peux quand même créer ton compte gratuit.",
        "list_lock": "Chiffres verrouillés : avec un compte gratuit, tu débloques 1 analyse complète par jour. Ouvre le match de ton choix.",
        "meta_match": "probabilités 1X2, buts, les deux marquent, score exact et cotes justes.",
        "lk_label": "Pari verrouillé", "lk_times": "Chance et marché verrouillés", "lk_coupon_meta": "{n} matchs",
        "picks_lock": "Les paris les plus probables de la semaine sont réservés à Premium (sauf ceux du match de ton analyse gratuite du jour).",
        # Compte
        "account_title": "Mon compte",
        "signin_title": "Crée ton compte gratuit",
        "signin_text": "Débloque 1 analyse gratuite par jour, garde tes championnats favoris et passe Premium quand tu veux.",
        "signin_perks": ["1 analyse complète gratuite chaque jour, sur le match de ton choix",
                         "Tes championnats favoris, sur tous tes appareils",
                         "Un e-mail la veille des plus belles affiches (si tu le veux)",
                         "Le Premium : toutes les analyses, sans pub"],
        "adult_confirm": "J'ai 18 ans ou plus.",
        "google_btn": "Continuer avec Google",
        "signin_legal_a": "En continuant, tu acceptes nos", "signin_legal_b": "et notre",
        "terms_link": "conditions d'utilisation", "privacy_link": "politique de confidentialité",
        "demo_banner": "Mode démo : la connexion Google, le Premium et les paiements sont simulés sur ce téléphone. Rien n'est envoyé.",
        "plan_title": "Ton offre", "plan_free": "Gratuit", "plan_premium": "Premium",
        "free_plan_text": "1 analyse complète par jour, sur le match de ton choix, avec quelques pubs.",
        "go_premium": "Passer Premium", "extend": "Prolonger",
        "emails_title": "E-mails",
        "email_news": "Grands chocs : une alerte la veille",
        "email_news_help": "Au plus un e-mail par jour, seulement pour les plus belles affiches.",
        "email_reminders": "Rappel avant la fin du Premium",
        "email_reminders_help": "Un seul e-mail, deux jours avant la fin de ton pass.",
        "email_note": "Le message de bienvenue et les reçus d'achat sont toujours envoyés. Chaque e-mail contient un lien de désinscription.",
        "prefs_title": "Préférences", "language": "Langue",
        "fav_title": "Championnats favoris",
        "fav_help": "Les alertes des grands chocs ne concerneront que ces championnats. Aucun choisi : tous.",
        "signout": "Se déconnecter", "delete_account": "Supprimer mon compte",
        "responsible_title": "Jeu responsable",
        "responsible_text": "Parier doit rester un loisir. Fixe-toi un budget, ne cherche jamais à te refaire et fais une pause si ça devient une source de stress.",
        "responsible_link": "Conseils et numéros d'aide",
        "demo_premium": "Simuler le Premium (démo)",
        # Offres
        "premium_kicker": "Plus d'analyses, zéro pub",
        "premium_lead": "Premium ne rend aucun pari sûr : il te donne toutes nos probabilités, pour décider en connaissance de cause.",
        "cmp_free": "Gratuit", "cmp_premium": "Premium",
        "cmp_rows": [["Analyse complète d'un match : plus de 90 marchés, cotes justes, compare ta cote (gratuit : avec un compte)", "1 par jour", "Tous les matchs"],
                     ["Probabilités dans la liste des matchs", 0, 1],
                     ["E-mail la veille des grands chocs", 1, 1],
                     ["Aucune publicité", 0, 1],
                     ["Les 5 paris les plus sûrs du jour (3 niveaux), coupons du jour, constructeur de coupons complet", "N°1 de chaque liste", "Tout"],
                     ["Alertes personnalisées (bientôt)", 0, 1]],
        "plans_title": "Choisis ton pass",
        "plan_week": "Pass 7 jours", "plan_month": "Pass 30 jours", "plan_quarter": "Pass 3 mois", "plan_half": "Pass 6 mois",
        "plan_year": "Pass 1 an", "best_value": "Le plus avantageux",
        "save_note": "Les remises sont calculées par jour, par rapport au pass 30 jours.",
        "no_renewal": "Paiement unique, sans abonnement : rien n'est prélevé automatiquement à la fin du pass.",
        "country": "Ton pays", "other_country": "Autre pays",
        "methods_stripe": "Carte bancaire, Apple Pay, Google Pay",
        "methods_flutterwave": "Mobile money (Orange Money, MTN, Wave, M-Pesa…) ou carte",
        "secure_stripe": "Paiement sécurisé par Stripe", "secure_flutterwave": "Paiement sécurisé par Flutterwave",
        "wa_methods": "Mobile money ou autre moyen : on t'explique comment payer sur WhatsApp.",
        "wa_btn": "Contacter {n}",
        "wa_secure": "Ton pass est activé sur ton compte dès que le paiement est reçu.",
        "faq_pay_wa": ["Comment payer Premium ?",
                       "Pour l'instant, le paiement se fait avec nous sur WhatsApp, au {n}. Touche « Contacter » : ton message est déjà prêt avec le pass choisi. "
                       "On t'explique comment payer (mobile money ou autre) et ton pass est activé sur ton compte dès réception. Le paiement en ligne arrive bientôt."],
        "faq_title": "Questions fréquentes",
        "faq": [["Que comprend la version gratuite ?",
                 "Avec un compte gratuit (connexion Google), une analyse complète par jour, sur le match de ton choix : toutes les probabilités, les cotes justes et « Compare ta cote ». Le match choisi ne change plus de la journée, même sur un autre appareil. Le compteur repart chaque jour à minuit (heure de ton téléphone)."],
                ["Puis-je payer avec mon mobile money ?",
                 "Oui, dans une vingtaine de pays d'Afrique (Orange Money, MTN, Wave, M-Pesa…), grâce à Flutterwave. Choisis ton pays ci-dessus : l'appli affiche le prix dans ta monnaie."],
                ["Est-ce un abonnement ?",
                 "Non. Tu achètes un pass de 7 jours, 30 jours, 3 mois, 6 mois ou 1 an. Plus il est long, moins le jour coûte cher. À la fin, tu repasses en gratuit, sauf si tu reprends un pass. Un nouveau pass s'ajoute à la suite du précédent."],
                ["Premium m'aide-t-il à gagner ?",
                 "Personne ne peut garantir un gain. Premium te donne plus d'informations, la décision reste la tienne. Mise seulement ce que tu peux te permettre de perdre."]],
        "adult_only": "Réservé aux 18 ans et plus.",
        # Pages légales
        "privacy_title": "Politique de confidentialité", "terms_title": "Conditions d'utilisation",
        "responsible_page_title": "Jeu responsable",
        "legal_updated": "Dernière mise à jour : 19 novembre 2026",
        "to_complete": "à compléter",
    },
    "en": {
        "tab_account": "Account",
        "legal_privacy": "Privacy", "legal_terms": "Terms", "legal_responsible": "Responsible gambling",
        "premium": "Premium", "loading": "Loading…",
        "ad_label": "Ad", "ad_title": "Probalis Premium",
        "ad_text": "Every analysis of every match, ad-free.", "ad_cta": "See offer",
        "lock_pill": "Premium", "lock_title": "Analysis locked",
        "lock_text": "All {n} markets of this match (1X2, goals, handicaps, correct score, halves…) are in Premium, or in your free analysis of the day.",
        "lock_cta": "Go Premium", "lock_free": "With a free account: 1 full analysis a day, on the match of your choice.",
        "free_title": "Your free analysis of the day",
        "free_text": "With your free account you get 1 full analysis a day, on the match of your choice. Use it on this match?",
        "free_signin_text": "Create your free account (with Google, in a few seconds) to unlock 1 full analysis a day, on the match of your choice.",
        "free_signin_btn": "Sign in for free",
        "free_use": "See this match's analysis",
        "free_used_title": "Today's free analysis already used",
        "free_used_text": "You used it on",
        "free_next": "Next free analysis tomorrow. With Premium, every match is unlocked.",
        "free_this": "Free analysis of the day: this match. The next one will be available tomorrow.",
        # Rewards, referrals, notifications
        "tab_account_short": "My account", "tab_rewards": "Rewards",
        "rw_title": "Rewards",
        "rw_lead": "Your gifts and free analyses. Invite your friends to earn more.",
        "rw_signin": "Sign in to see your rewards and your invitation link.",
        "rw_signin_btn": "Sign in",
        "rw_balance": "Free analyses",
        "rw_balance_help": "Each one opens the full analysis of a match you choose: on the match page, tap “Use a free analysis”.",
        "rw_waiting": "To activate", "rw_history": "History",
        "rw_empty": "No rewards yet. Invite a friend: you earn analyses as soon as they sign up.",
        "inv_title": "Invite your friends",
        "inv_lead": "Share your link. You earn free analyses at every step your friend takes:",
        "inv_signup": "They create their account", "inv_active": "They use Probalis on {d} different days",
        "inv_buy": "They get a Premium pass", "inv_buy_detail": "depending on the pass length",
        "inv_welcome": "And your friend gets {n} free analyses as a welcome gift.",
        "inv_cap": "Sign-ups and activity: up to {n} friends rewarded per month. Purchases: no limit.",
        "inv_link": "Your invitation link", "inv_copy": "Copy", "inv_share_wa": "WhatsApp", "inv_share": "Share",
        "push_title": "Notifications",
        "push_device": "Notifications on this phone",
        "push_device_help": "Your rewards, your gifts and your Premium activation.",
        "push_daily": "Today's analyses are ready", "push_daily_help": "One notification a day, in the morning.",
        "push_ios": "On iPhone: first add Probalis to your Home Screen (Share button, then “Add to Home Screen”), open it from there, then come back here.",
        "push_unsupported": "This browser doesn't support notifications. Try Chrome.",
        "push_blocked": "Notifications are blocked for Probalis. Allow them in your browser settings, then try again.",
        "admin_link": "Open Probalis Office",
        "bonus_use": "Use a free analysis",
        "free_extra": "Free analysis used on this match: it stays open for you.",
        "invp_kicker": "Invitation",
        "invp_title": "Your friend invites you to Probalis",
        "invp_lead": "The real probability of every football match, worked out from market odds. No “sure bets”, just honest numbers.",
        "invp_gift": "{n} free analyses when you sign up",
        "invp_gift_help": "On top of your free analysis every day. Use them on the matches you choose.",
        "invp_perks": ["1 free full analysis a day", "Today's bets ranked by risk level",
                       "Your slip analysed: its real chance of winning", "Our full track record, unfiltered"],
        "invp_cta": "Create my free account",
        "invp_have": "Already have an account? The invitation gift is for new accounts, but you can invite your friends in turn.",
        "invp_have_btn": "See my rewards",
        "invp_bad": "This invitation link is incomplete. You can still create your free account.",
        "list_lock": "Numbers locked: with a free account you unlock 1 full analysis a day. Open the match of your choice.",
        "meta_match": "1X2, goals, both teams to score, correct score probabilities and fair odds.",
        "lk_label": "Locked bet", "lk_times": "Chance and market locked", "lk_coupon_meta": "{n} matches",
        "picks_lock": "The week's most likely bets are for Premium members (except those from your free analysis of the day).",
        "account_title": "My account",
        "signin_title": "Create your free account",
        "signin_text": "Unlock 1 free analysis a day, keep your favourite competitions and go Premium whenever you like.",
        "signin_perks": ["1 free full analysis every day, on the match of your choice",
                         "Your favourite competitions, on all your devices",
                         "An email the day before the biggest matches (if you want it)",
                         "Premium: every analysis, no ads"],
        "adult_confirm": "I'm 18 or older.",
        "google_btn": "Continue with Google",
        "signin_legal_a": "By continuing, you accept our", "signin_legal_b": "and our",
        "terms_link": "terms of use", "privacy_link": "privacy policy",
        "demo_banner": "Demo mode: Google sign-in, Premium and payments are simulated on this device. Nothing is sent.",
        "plan_title": "Your plan", "plan_free": "Free", "plan_premium": "Premium",
        "free_plan_text": "1 full analysis a day, on the match of your choice, with a few ads.",
        "go_premium": "Go Premium", "extend": "Extend",
        "emails_title": "Emails",
        "email_news": "Big matches: an alert the day before",
        "email_news_help": "At most one email a day, only for the biggest matches.",
        "email_reminders": "Reminder before Premium ends",
        "email_reminders_help": "A single email, two days before your pass ends.",
        "email_note": "Welcome messages and receipts are always sent. Every email has an unsubscribe link.",
        "prefs_title": "Preferences", "language": "Language",
        "fav_title": "Favourite competitions",
        "fav_help": "Big-match alerts will only cover these competitions. None selected: all of them.",
        "signout": "Sign out", "delete_account": "Delete my account",
        "responsible_title": "Responsible gambling",
        "responsible_text": "Betting should stay fun. Set yourself a budget, never chase your losses and take a break if it becomes stressful.",
        "responsible_link": "Advice and helplines",
        "demo_premium": "Simulate Premium (demo)",
        "premium_kicker": "More analysis, zero ads",
        "premium_lead": "Premium doesn't make any bet a sure thing: it gives you all our probabilities, so you decide with full knowledge.",
        "cmp_free": "Free", "cmp_premium": "Premium",
        "cmp_rows": [["Full match analysis: 90+ markets, fair odds, check your odds (free: with an account)", "1 a day", "Every match"],
                     ["Probabilities in the match list", 0, 1],
                     ["Email the day before big matches", 1, 1],
                     ["No ads", 0, 1],
                     ["The 5 safest bets of the day (3 levels), daily accumulators, full accumulator builder", "#1 of each list", "Everything"],
                     ["Personal alerts (coming soon)", 0, 1]],
        "plans_title": "Pick your pass",
        "plan_week": "7-day pass", "plan_month": "30-day pass", "plan_quarter": "3-month pass", "plan_half": "6-month pass",
        "plan_year": "1-year pass", "best_value": "Best value",
        "save_note": "Discounts are worked out per day, compared with the 30-day pass.",
        "no_renewal": "One-off payment, no subscription: nothing is charged automatically when your pass ends.",
        "country": "Your country", "other_country": "Other country",
        "methods_stripe": "Card, Apple Pay, Google Pay",
        "methods_flutterwave": "Mobile money (Orange Money, MTN, Wave, M-Pesa…) or card",
        "secure_stripe": "Secure payment by Stripe", "secure_flutterwave": "Secure payment by Flutterwave",
        "wa_methods": "Mobile money or another way: we explain how to pay on WhatsApp.",
        "wa_btn": "Contact {n}",
        "wa_secure": "Your pass is switched on for your account as soon as the payment arrives.",
        "faq_pay_wa": ["How do I pay for Premium?",
                       "For now, payment is done with us on WhatsApp, at {n}. Tap “Contact”: your message is already written with the pass you chose. "
                       "We explain how to pay (mobile money or another way) and your pass is switched on for your account as soon as it arrives. Online payment is coming soon."],
        "faq_title": "FAQ",
        "faq": [["What does the free plan include?",
                 "With a free account (Google sign-in), one full analysis a day, on the match of your choice: every probability, fair odds and \"Check your odds\". The chosen match stays the same all day, even on another device. The counter resets every day at midnight (your phone's time)."],
                ["Can I pay with mobile money?",
                 "Yes, in about twenty African countries (Orange Money, MTN, Wave, M-Pesa…), through Flutterwave. Pick your country above: the app shows the price in your currency."],
                ["Is it a subscription?",
                 "No. You buy a 7-day, 30-day, 3-month, 6-month or 1-year pass. The longer it is, the less each day costs. When it ends, you're back on the free plan unless you buy another pass. A new pass is added after the current one."],
                ["Does Premium help me win?",
                 "Nobody can guarantee a win. Premium gives you more information; the decision is yours. Only stake what you can afford to lose."]],
        "adult_only": "18+ only.",
        "privacy_title": "Privacy policy", "terms_title": "Terms of use",
        "responsible_page_title": "Responsible gambling",
        "legal_updated": "Last updated: 19 November 2026",
        "to_complete": "to be completed",
    },
}

_JS_EXTRA = {
    "fr": {
        "net_slow": "Connexion lente : on charge l'essentiel d'abord.",
        "net_offline": "Pas de connexion Internet.",
        "off_title": "Pas de connexion Internet",
        "off_text": "Probalis a besoin d'Internet pour afficher les analyses du jour. Vérifie ta connexion (données mobiles ou Wi-Fi), puis réessaie.",
        "off_retry": "Réessayer",
        "off_wait": "La page se rechargera toute seule dès que le réseau revient.",
        "net_online": "De nouveau en ligne", "net_close": "Fermer",
        "nav_error": "Impossible de charger la page. Réessaie.", "loaded": "Page chargée : {t}",
        "plan_free": "Gratuit", "plan_premium": "Premium", "premium_until": "Premium jusqu'au {d}",
        "welcome": "Bienvenue, {n} !", "signed_out": "Tu es déconnecté.", "saved": "Enregistré",
        "adult_required": "Coche la case 18+ pour continuer.",
        "need_signin": "Connecte-toi d'abord : ton Premium sera lié à ton compte.",
        "already_premium": "Tu es Premium jusqu'au {d}. Un nouveau pass s'ajoute à la suite.",
        "pay_btn": "Payer {p}", "per_day": "soit {p} par jour", "from_price": "Dès {p}", "save": "−{n} %",
        "pay_redirect": "Redirection vers le paiement sécurisé…",
        "wa_btn": "Contacter {n}", "wa_open": "Ouverture de WhatsApp…",
        "wa_msg": "Bonjour Probalis ! Je veux le {plan} ({price}).\nMon compte : {who}\nComment puis-je payer ?",
        "wa_need_signin": "Connecte-toi d'abord : on activera le pass sur ton compte.",
        "pay_pending": "Paiement reçu, activation de ton Premium…",
        "pay_ok": "Premium activé jusqu'au {d}. Merci !",
        "pay_cancel": "Paiement annulé : rien n'a été prélevé.",
        "pay_slow": "Ton paiement est en cours de confirmation. Le Premium s'activera dans quelques minutes.",
        "demo_paid": "Paiement simulé (démo) : Premium activé jusqu'au {d}. Un reçu aurait été envoyé par e-mail.",
        "demo_welcome": "Connexion simulée (démo). Un e-mail de bienvenue aurait été envoyé.",
        "error": "Une erreur est survenue. Réessaie dans un instant.",
        "delete_confirm": "Supprimer ton compte ? Ton profil et tes préférences seront effacés, et un Premium en cours sera perdu. C'est définitif.",
        "deleted": "Ton compte a été supprimé.", "demo_name": "Joueur démo", "other_country": "Autre pays",
        "unsub_news": "C'est fait : tu ne recevras plus les alertes des grands chocs. Tu peux les réactiver ici quand tu veux.",
        "unsub_reminders": "C'est fait : tu ne recevras plus le rappel avant la fin du Premium.",
        "unsub_bad": "Ce lien de désinscription n'est plus valide. Connecte-toi pour régler tes e-mails ici.",
        "free_unlocked": "Analyse débloquée. Bonne lecture !", "free_other": "un autre match",
        "rw_src": {"gift": "Cadeau de Probalis", "referral_signup": "Un ami s'est inscrit", "referral_active": "Un ami utilise Probalis",
                   "referral_purchase": "Un ami a pris un pass", "welcome_bonus": "Bienvenue (invitation)"},
        "rw_dur": {"week": "7 jours", "month": "30 jours", "quarter": "3 mois", "half": "6 mois", "year": "1 an"},
        "rw_premium": "Pass Premium {d}", "rw_an1": "1 analyse de match", "rw_anN": "{n} analyses de match",
        "rw_act_premium": "Activer mon Premium", "rw_act_analyses": "Ajouter à mes analyses",
        "rw_used": "Utilisée le {d}", "rw_expired": "Expirée", "rw_cancelled": "Annulée", "rw_until": "Lien valable jusqu'au {d}",
        "rw_done_premium": "Premium activé jusqu'au {d} !", "rw_done_analyses": "+{n} analyses offertes ajoutées.",
        "rw_claim_wait": "Validation de ton cadeau…",
        "rw_claim_ok": "C'est validé : ta récompense est activée ! Elle t'attend juste en dessous.",
        "rw_claim_other": "Ce cadeau est pour un autre compte. Connecte-toi avec le compte Google qui a reçu l'e-mail.",
        "rw_claim_bad": "Ce lien n'est plus valide. Demande un nouveau lien à Probalis.",
        "rw_claim_expired": "Ce cadeau a expiré. Écris-nous sur WhatsApp si tu penses que c'est une erreur.",
        "rw_claim_signin": "Connecte-toi pour activer ton cadeau.",
        "inv_copied": "Lien copié",
        "inv_msg": "Je t'invite sur Probalis : les vraies probabilités de chaque match de foot. Inscris-toi avec mon lien, tu reçois {n} analyses offertes : {u}",
        "inv_friends1": "1 ami inscrit grâce à toi", "inv_friendsN": "{n} amis inscrits grâce à toi",
        "bonus_left1": "1 analyse offerte disponible", "bonus_leftN": "{n} analyses offertes disponibles",
        "bonus_done": "Analyse offerte utilisée : ce match est ouvert.", "bonus_none": "Plus d'analyse offerte disponible.",
        "push_on": "Notifications activées sur ce téléphone.", "push_off": "Notifications coupées sur ce téléphone.",
        "push_blocked": "Les notifications sont bloquées pour Probalis. Autorise-les dans les réglages du navigateur.",
        "ref_ok": "Invitation prise en compte : tes analyses de bienvenue t'attendent dans Récompenses.",
    },
    "en": {
        "net_slow": "Slow connection: loading the essentials first.",
        "net_offline": "No internet connection.",
        "off_title": "No internet connection",
        "off_text": "Probalis needs the internet to show today's analyses. Check your connection (mobile data or Wi-Fi), then try again.",
        "off_retry": "Try again",
        "off_wait": "The page will reload by itself as soon as you're back online.",
        "net_online": "Back online", "net_close": "Close",
        "nav_error": "Couldn't load the page. Try again.", "loaded": "Page loaded: {t}",
        "plan_free": "Free", "plan_premium": "Premium", "premium_until": "Premium until {d}",
        "welcome": "Welcome, {n}!", "signed_out": "You're signed out.", "saved": "Saved",
        "adult_required": "Tick the 18+ box to continue.",
        "need_signin": "Sign in first: your Premium will be linked to your account.",
        "already_premium": "You're Premium until {d}. A new pass is added after the current one.",
        "pay_btn": "Pay {p}", "per_day": "{p} per day", "from_price": "From {p}", "save": "−{n}%",
        "pay_redirect": "Taking you to the secure payment page…",
        "wa_btn": "Contact {n}", "wa_open": "Opening WhatsApp…",
        "wa_msg": "Hello Probalis! I'd like the {plan} ({price}).\nMy account: {who}\nHow can I pay?",
        "wa_need_signin": "Sign in first: we'll switch the pass on for your account.",
        "pay_pending": "Payment received, activating your Premium…",
        "pay_ok": "Premium active until {d}. Thank you!",
        "pay_cancel": "Payment cancelled: you haven't been charged.",
        "pay_slow": "Your payment is being confirmed. Premium will be active within a few minutes.",
        "demo_paid": "Simulated payment (demo): Premium active until {d}. A receipt would have been emailed.",
        "demo_welcome": "Simulated sign-in (demo). A welcome email would have been sent.",
        "error": "Something went wrong. Try again in a moment.",
        "delete_confirm": "Delete your account? Your profile and preferences will be erased, and any running Premium will be lost. This can't be undone.",
        "deleted": "Your account has been deleted.", "demo_name": "Demo player", "other_country": "Other country",
        "unsub_news": "Done: you won't get big-match alerts any more. You can turn them back on here at any time.",
        "unsub_reminders": "Done: you won't get the reminder before your Premium ends any more.",
        "unsub_bad": "This unsubscribe link is no longer valid. Sign in to manage your emails here.",
        "free_unlocked": "Analysis unlocked. Enjoy!", "free_other": "another match",
        "rw_src": {"gift": "Gift from Probalis", "referral_signup": "A friend signed up", "referral_active": "A friend uses Probalis",
                   "referral_purchase": "A friend got a pass", "welcome_bonus": "Welcome (invitation)"},
        "rw_dur": {"week": "7-day", "month": "30-day", "quarter": "3-month", "half": "6-month", "year": "1-year"},
        "rw_premium": "{d} Premium pass", "rw_an1": "1 match analysis", "rw_anN": "{n} match analyses",
        "rw_act_premium": "Activate my Premium", "rw_act_analyses": "Add to my analyses",
        "rw_used": "Used on {d}", "rw_expired": "Expired", "rw_cancelled": "Cancelled", "rw_until": "Link valid until {d}",
        "rw_done_premium": "Premium on until {d}!", "rw_done_analyses": "+{n} free analyses added.",
        "rw_claim_wait": "Validating your gift…",
        "rw_claim_ok": "Done: your reward is activated! It's waiting for you just below.",
        "rw_claim_other": "This gift is for another account. Sign in with the Google account that received the email.",
        "rw_claim_bad": "This link is no longer valid. Ask Probalis for a new one.",
        "rw_claim_expired": "This gift has expired. Message us on WhatsApp if you think it's a mistake.",
        "rw_claim_signin": "Sign in to activate your gift.",
        "inv_copied": "Link copied",
        "inv_msg": "Join me on Probalis: the real probability of every football match. Sign up with my link and you get {n} free analyses: {u}",
        "inv_friends1": "1 friend signed up thanks to you", "inv_friendsN": "{n} friends signed up thanks to you",
        "bonus_left1": "1 free analysis available", "bonus_leftN": "{n} free analyses available",
        "bonus_done": "Free analysis used: this match is open.", "bonus_none": "No free analysis left.",
        "push_on": "Notifications on for this phone.", "push_off": "Notifications off for this phone.",
        "push_blocked": "Notifications are blocked for Probalis. Allow them in your browser settings.",
        "ref_ok": "Invitation received: your welcome analyses are waiting in Rewards.",
    },
}

# --- Paris du jour, ticket, historique (ajoutés le 19/11/2026) ---------------------------------------------
_BETS = {
    "fr": {
        "bets_kicker": "Paris du jour", "bets_h1": "Les plus sûrs du jour",
        "bets_lead": "Pour chaque niveau de risque, nos 5 paris les plus probables du jour, sur des marchés classiques que tous les bookmakers proposent. Ils sont enregistrés avant les matchs : les résultats arrivent dans l'Historique.",
        "tiers_label": "Niveau de risque",
        "tier_safe": "Prudent", "tier_balanced": "Équilibré", "tier_bold": "Audacieux",
        "tier_safe_help": "Environ 7 à 8 chances sur 10 · cotes justes de 1,25 à 1,45",
        "tier_balanced_help": "Environ 6 chances sur 10 · cotes justes de 1,45 à 1,80",
        "tier_bold_help": "Environ 4 à 5 chances sur 10 · cotes justes de 2 à 2,80",
        "times_ten": "≈ {n} fois sur 10",
        "pct_explain": "80 % veut dire : sur 10 paris comme celui-ci, environ 8 passent et 2 perdent. Jamais 10 sur 10.",
        "book_est": "≈ {o} chez un bookmaker", "add_coupon": "Ajouter au ticket", "started": "Commencé",
        "res_won": "Gagné", "res_lost": "Perdu", "res_void": "Remboursé", "res_wait": "En attente",
        "res_live": "en cours", "vd_live_won": "Déjà validé", "vd_live_lost": "Déjà perdu",
        "no_picks_day": "Pas de pari retenu ce jour-là : trop peu de matchs fiables (le football féminin et les matchs avec peu de données sont mis de côté).",
        "no_picks": "Pas encore de paris du jour : reviens quand les prochains matchs seront annoncés.",
        "coupons_title": "Coupons du jour",
        "coupons_lead": "Des combinés tout prêts pour une cote d'environ 2, 3 ou 5, avec le moins de matchs possible : chaque match en plus te fait payer une marge de plus au bookmaker.",
        "coupon_target": "Cote ≈ {n}", "coupon_meta": "{n} matchs · chance {p}",
        "coupon_book": "Cote estimée chez un bookmaker", "coupon_fair": "cote juste {o}",
        "coupon_load": "Mettre dans mon ticket", "no_coupons": "Pas de coupon ce jour-là.",
        "lock_anon": "Connecte-toi gratuitement pour voir le n°1 de chaque liste.",
        "lock_signed": "Gratuit : le n°1 de chaque liste. Premium : les 5 paris de chaque niveau et les coupons du jour.",
        "signin_cta": "Se connecter", "coupons_lock": "Coupons du jour réservés à Premium.",
        "est_note": "Cote bookmaker estimée = cote juste moins une marge d'environ 5 %. Vérifie toujours la vraie cote chez ton bookmaker.",
        "see_history": "Voir l'historique",
        "tk_swap_btn": "Remplacer", "tk_today": "Aujourd'hui",
        "team_scores2": "{team} marque 2 buts ou plus",
        "btts_yes_long": "Les deux équipes marquent", "btts_no_long": "Au moins une équipe ne marque pas",
        # Ticket
        "ticket_kicker": "Constructeur de coupons", "ticket_h1": "Mon ticket",
        "ticket_lead": "Construis ton coupon : Probalis calcule la vraie chance qu'il passe, repère le match le plus risqué et te dit si la cote de ton bookmaker vaut le coup.",
        "mode_label": "Mode", "mode_mine": "Mon coupon", "mode_target": "Cote cible", "mode_count": "Nb de matchs",
        "mode_mine_help": "Ajoute tes paris (bouton + dans l'onglet Paris, sur la page d'un match, ou ci-dessous).",
        "mode_target_help": "Donne la cote que tu veux : l'appli construit le coupon le plus solide pour l'atteindre.",
        "mode_count_help": "Choisis le nombre de matchs et le niveau : l'appli prend les paris les plus sûrs du jour.",
        "mine_empty": "Ton ticket est vide. Ajoute des paris avec le bouton + de l'onglet Paris, depuis la page d'un match, ou ici.",
        "add_match": "Ajouter un pari", "pick_day": "Jour", "pick_match": "Match", "pick_bet": "Pari",
        "add_btn": "Ajouter au ticket", "clear_all": "Tout effacer",
        "an_your_odds": "Cote totale chez ton bookmaker (facultatif)",
        "target_label": "Cote voulue", "count_label": "Nombre de matchs", "level_label": "Niveau", "build_btn": "Construire",
        "same_odds_title": "Même cote, plus ou moins de matchs",
        "same_odds_text": "À cote égale, moins de matchs = plus de chance : le bookmaker prend sa marge sur chaque sélection.",
        "use_this": "Mettre dans mon ticket", "share_ticket": "Partager",
        "ticket_note": "Les chances viennent de notre modèle : ce sont des estimations, pas des certitudes. Un combiné perd dès qu'une seule sélection perd.",
        "auto_lock": "Les modes « Cote cible » et « Nombre de matchs » sont réservés à Premium.",
        "mine_lock_anon": "Connecte-toi gratuitement pour analyser ton ticket (jusqu'à 3 matchs). Premium : jusqu'à 10 matchs.",
        "mine_lock_free": "Gratuit : analyse jusqu'à 3 matchs. Premium : jusqu'à 10 matchs.",
        # Historique
        "hist_kicker": "Nos résultats, sans maquillage", "hist_h1": "Historique",
        "hist_lead": "Chaque jour, les paris du jour et les coupons sont enregistrés avant les matchs, puis réglés automatiquement : pendant le match dès qu'un pari est déjà gagné ou perdu, sinon avec le score final. Rien n'est effacé.",
        "hist_since": "Depuis le {d}", "hist_empty": "Le suivi commence aujourd'hui : les premiers résultats arriveront après les matchs.",
        "hist_rate": "réussite", "hist_announced": "annoncé {p} en moyenne", "hist_n": "{won} gagnés sur {n}",
        "hist_calib": "Annoncé {a} → réel {r}", "hist_too_few": "Pas encore assez de paris réglés pour juger : il en faut au moins 30 par niveau.",
        "hist_days": "Jour par jour", "hist_coupons": "Coupons du jour", "hist_pending": "en attente",
        "sim_title": "Simulation sur la saison 2025/26",
        "sim_lead": "Les mêmes règles appliquées après coup à toute la saison 2025/26 ({n} matchs, {leagues} championnats), sans connaître les résultats à l'avance. C'est une simulation, pas un historique réel.",
        "sim_rate": "{r} de réussite pour {a} annoncés ({n} paris)",
        "sim_coupon": "Coupon cote ≈ {t} : {r} de réussite pour {a} annoncés ({n} coupons)",
        "sim_roi": "Gain ou perte à la cote estimée du bookmaker : {r}",
        "sim_note": "Les chances viennent du modèle calé sur les cotes moyennes d'avant-match. Le gain ou la perte est calculé comme si chaque pari avait été joué à la cote estimée du bookmaker (cote juste moins 5 %) : même quand la réussite colle à la chance annoncée, cette marge fait perdre un peu d'argent à long terme.",
    },
    "en": {
        "bets_kicker": "Today's bets", "bets_h1": "Today's safest bets",
        "bets_lead": "For each risk level, our 5 most likely bets of the day, on standard markets every bookmaker offers. They're recorded before kick-off: results show up in History.",
        "tiers_label": "Risk level",
        "tier_safe": "Safe", "tier_balanced": "Balanced", "tier_bold": "Bold",
        "tier_safe_help": "About 7 to 8 chances in 10 · fair odds 1.25 to 1.45",
        "tier_balanced_help": "About 6 chances in 10 · fair odds 1.45 to 1.80",
        "tier_bold_help": "About 4 to 5 chances in 10 · fair odds 2.00 to 2.80",
        "times_ten": "≈ {n} in 10",
        "pct_explain": "80% means: out of 10 bets like this one, about 8 win and 2 lose. Never 10 out of 10.",
        "book_est": "≈ {o} at a bookmaker", "add_coupon": "Add to slip", "started": "Started",
        "res_won": "Won", "res_lost": "Lost", "res_void": "Void", "res_wait": "Pending",
        "res_live": "in play", "vd_live_won": "Already won", "vd_live_lost": "Already lost",
        "no_picks_day": "No pick that day: too few reliable matches (women's football and matches with little data are left out).",
        "no_picks": "No bets of the day yet: come back when the next matches are announced.",
        "coupons_title": "Accumulators of the day",
        "coupons_lead": "Ready-made accas at odds of about 2, 3 or 5, with as few matches as possible: every extra match makes you pay the bookmaker's margin once more.",
        "coupon_target": "Odds ≈ {n}", "coupon_meta": "{n} matches · {p} chance",
        "coupon_book": "Estimated bookmaker odds", "coupon_fair": "fair odds {o}",
        "coupon_load": "Load into my slip", "no_coupons": "No accumulator that day.",
        "lock_anon": "Sign in for free to see the #1 of each list.",
        "lock_signed": "Free: the #1 of each list. Premium: all 5 bets of each level and the daily accumulators.",
        "signin_cta": "Sign in", "coupons_lock": "Daily accumulators are for Premium members.",
        "est_note": "Estimated bookmaker odds = fair odds minus a margin of about 5%. Always check the real price at your bookmaker.",
        "see_history": "See history",
        "tk_swap_btn": "Swap it", "tk_today": "Today",
        "team_scores2": "{team} to score 2+",
        "btts_yes_long": "Both teams to score", "btts_no_long": "At least one team fails to score",
        "ticket_kicker": "Accumulator builder", "ticket_h1": "My slip",
        "ticket_lead": "Build your accumulator: Probalis works out the real chance it wins, spots the riskiest match and tells you whether your bookmaker's price is worth it.",
        "mode_label": "Mode", "mode_mine": "My slip", "mode_target": "Target odds", "mode_count": "No. of matches",
        "mode_mine_help": "Add your bets (+ button in the Bets tab, on a match page, or below).",
        "mode_target_help": "Enter the odds you want: the app builds the most solid accumulator to reach them.",
        "mode_count_help": "Pick the number of matches and the level: the app takes the day's safest bets.",
        "mine_empty": "Your slip is empty. Add bets with the + button in the Bets tab, from a match page, or here.",
        "add_match": "Add a bet", "pick_day": "Day", "pick_match": "Match", "pick_bet": "Bet",
        "add_btn": "Add to slip", "clear_all": "Clear all",
        "an_your_odds": "Total odds at your bookmaker (optional)",
        "target_label": "Target odds", "count_label": "Number of matches", "level_label": "Level", "build_btn": "Build",
        "same_odds_title": "Same odds, more or fewer matches",
        "same_odds_text": "At equal odds, fewer matches = more chance: the bookmaker takes its margin on every selection.",
        "use_this": "Load into my slip", "share_ticket": "Share",
        "ticket_note": "Chances come from our model: they're estimates, not certainties. An accumulator loses as soon as one selection loses.",
        "auto_lock": "“Target odds” and “Number of matches” are for Premium members.",
        "mine_lock_anon": "Sign in for free to analyse your slip (up to 3 matches). Premium: up to 10 matches.",
        "mine_lock_free": "Free: analysis of up to 3 matches. Premium: up to 10 matches.",
        "hist_kicker": "Our results, no make-up", "hist_h1": "History",
        "hist_lead": "Every day, the bets of the day and the accumulators are recorded before kick-off, then settled automatically: during the match as soon as a bet is already won or lost, otherwise with the final score. Nothing is deleted.",
        "hist_since": "Since {d}", "hist_empty": "Tracking starts today: the first results will come in after the matches.",
        "hist_rate": "won", "hist_announced": "{p} announced on average", "hist_n": "{won} won out of {n}",
        "hist_calib": "Announced {a} → actual {r}", "hist_too_few": "Not enough settled bets to judge yet: we need at least 30 per level.",
        "hist_days": "Day by day", "hist_coupons": "Accumulators of the day", "hist_pending": "pending",
        "sim_title": "Simulation on the 2025/26 season",
        "sim_lead": "The same rules applied afterwards to the whole 2025/26 season ({n} matches, {leagues} leagues), without knowing the results in advance. It's a simulation, not a real track record.",
        "sim_rate": "{r} won for {a} announced ({n} bets)",
        "sim_coupon": "Accumulator at odds ≈ {t}: {r} won for {a} announced ({n} accas)",
        "sim_roi": "Profit or loss at the estimated bookmaker odds: {r}",
        "sim_note": "The chances come from the model calibrated on the average pre-match odds. Profit or loss is computed as if each bet had been placed at the estimated bookmaker odds (fair odds minus 5%): even when the hit rate matches the announced chance, that margin loses a little money in the long run.",
    },
}

_BETS_JS = {
    "fr": {
        "tk_added": "Ajouté au ticket ({n})", "tk_replaced": "Pari remplacé pour ce match ({n})",
        "tk_full": "Ticket plein : 10 matchs au maximum.", "tk_started": "Ce match a déjà commencé.",
        "tk_loaded": "Coupon mis dans ton ticket", "tk_removed": "Retiré du ticket",
        "tk_chance": "Chance que le ticket passe", "tk_times": "≈ {n} fois sur 10", "tk_times100": "≈ {n} fois sur 100",
        "tk_fair": "Cote juste", "tk_book": "Cote estimée chez un bookmaker",
        "tk_weak": "Maillon faible : {l} ({p}).",
        "tk_swap": "Remplace-le par « {l} » ({p}) : ta chance passe à {c}, pour une cote d'environ {o}.",
        "tk_drop": "Sans ce match : chance {c}, cote d'environ {o}.",
        "tk_n": "{n} matchs", "tk_1": "1 match", "tk_k": "{k} matchs", "tk_kc": "chance {p}",
        "tk_share_head": "Mon ticket Probalis", "tk_share_chance": "Chance estimée : {p} · cote juste {f}",
        "tk_none": "Pas assez de matchs ce jour-là pour ce coupon. Essaie un autre jour ou une autre cote.",
        "tk_low": "peu de données", "tk_lock_more": "Gratuit : analyse jusqu'à 3 matchs. Passe Premium pour aller jusqu'à 10.",
        "tk_choose": "Choisir…", "tk_today": "Aujourd'hui", "tk_tomorrow": "Demain",
        "tk_verdict_none": "Entre la cote totale de ton bookmaker pour savoir si elle vaut le coup.",
        "tk_loading": "Chargement des matchs…", "tk_load_err": "Impossible de charger les matchs. Réessaie.",
        "tk_lim_anon": "Connecte-toi gratuitement : tu pourras ajouter ici les paris de ton analyse gratuite du jour. Premium : tous les matchs.",
        "tk_lim_none": "Choisis d'abord ton analyse gratuite du jour sur la page d'un match : ses paris s'ajouteront ici. Premium : tous les matchs.",
        "tk_lim_free": "Gratuit : les paris du match de ton analyse gratuite du jour. Premium : tous les matchs.",
        "tk_cleared": "Ticket vidé", "tk_started_short": "commencé", "tk_remove": "Retirer",
        "tk_use": "Mettre dans mon ticket", "tk_same_title": "Même cote, plus ou moins de matchs",
        "tk_same_text": "À cote égale, moins de matchs = plus de chance : le bookmaker prend sa marge sur chaque sélection.",
        "tk_bad_target": "Entre une cote entre 1,5 et 100, par exemple 3.",
        "tk_explain10": "Sur 10 tickets comme celui-ci, environ {w} {wv} et {l} {lv}. Jamais 10 sur 10.",
        "tk_explain100": "Sur 100 tickets comme celui-ci, environ {w} {wv} : c'est un coup de chance, pas un calcul sûr.",
        "tk_win1": "passe", "tk_winN": "passent", "tk_lose1": "perd", "tk_loseN": "perdent",
    },
    "en": {
        "tk_added": "Added to slip ({n})", "tk_replaced": "Bet replaced for this match ({n})",
        "tk_full": "Slip full: 10 matches at most.", "tk_started": "This match has already started.",
        "tk_loaded": "Accumulator loaded into your slip", "tk_removed": "Removed from slip",
        "tk_chance": "Chance the slip wins", "tk_times": "≈ {n} in 10", "tk_times100": "≈ {n} in 100",
        "tk_fair": "Fair odds", "tk_book": "Estimated bookmaker odds",
        "tk_weak": "Weakest link: {l} ({p}).",
        "tk_swap": "Swap it for “{l}” ({p}): your chance goes up to {c}, at odds of about {o}.",
        "tk_drop": "Without this match: {c} chance, odds of about {o}.",
        "tk_n": "{n} matches", "tk_1": "1 match", "tk_k": "{k} matches", "tk_kc": "{p} chance",
        "tk_share_head": "My Probalis slip", "tk_share_chance": "Estimated chance: {p} · fair odds {f}",
        "tk_none": "Not enough matches that day for this accumulator. Try another day or other odds.",
        "tk_low": "little data", "tk_lock_more": "Free: analysis of up to 3 matches. Go Premium for up to 10.",
        "tk_choose": "Choose…", "tk_today": "Today", "tk_tomorrow": "Tomorrow",
        "tk_verdict_none": "Enter your bookmaker's total odds to see whether they're worth it.",
        "tk_loading": "Loading matches…", "tk_load_err": "Couldn't load the matches. Try again.",
        "tk_lim_anon": "Sign in for free to add the bets of your free daily analysis here. Premium: every match.",
        "tk_lim_none": "First pick your free daily analysis on a match page: its bets can then be added here. Premium: every match.",
        "tk_lim_free": "Free: the bets of your free daily analysis match. Premium: every match.",
        "tk_cleared": "Slip cleared", "tk_started_short": "started", "tk_remove": "Remove",
        "tk_use": "Load into my slip", "tk_same_title": "Same odds, more or fewer matches",
        "tk_same_text": "At equal odds, fewer matches = more chance: the bookmaker takes its margin on every selection.",
        "tk_bad_target": "Enter odds between 1.5 and 100, for example 3.",
        "tk_explain10": "Out of 10 slips like this one, about {w} {wv} and {l} {lv}. Never 10 out of 10.",
        "tk_explain100": "Out of 100 slips like this one, about {w} {wv}: that's luck, not a safe bet.",
        "tk_win1": "wins", "tk_winN": "win", "tk_lose1": "loses", "tk_loseN": "lose",
    },
}

# --- Verdicts, « pourquoi », corners et cartons, historique des analyses (ajoutés le 21/11/2026) ----------
_V2 = {
    "fr": {
        "corners_word": "corners", "cards_word": "cartons", "more_corners": "Plus de corners",
        "more_cards": "Plus de cartons", "equal_word": "{what} : égalité",
        "vd_title": "Verdicts", "vd_lead": "Oui ou non, et la chance que la réponse soit la bonne.",
        "vd_best": "Le plus sûr", "vd_yes": "OUI", "vd_no": "NON", "vd_open": "SERRÉ",
        "vd_open_help": "Trop serré pour trancher : ni oui ni non à plus de 55 %.",
        "vd_proof": "Ce type de verdict s'est vérifié {won} fois sur {n} ({rate}) sur la saison {season}, testée sans que le moteur l'ait vue.",
        "vd_proof_none": "Aucun verdict n'est une certitude : sur 10 verdicts à {pct}, environ {miss} ne passent pas.",
        "vd_note": "Le pourcentage est la chance que la réponse (OUI ou NON) soit la bonne. Jamais une certitude.",
        "vd_q_win": "{team} gagne ?", "vd_q_dc": "{sel} ?", "vd_q_ou": "Plus de {line} buts ?",
        "vd_q_btts": "Les deux équipes marquent ?", "vd_q_tt": "{team} marque ?",
        "vd_q_co": "Plus de {line} corners ?", "vd_q_ca": "Plus de {line} cartons ?",
        "vd_partial": "Corners et cartons estimés à partir du championnat de chaque club (un des deux sans données : estimation moins sûre).",
        "why_title": "Pourquoi", "why_lead": "Les raisons de cette analyse, en buts attendus.",
        "counts_none": "Pas de chiffres de corners ni de cartons gratuits pour cette compétition.",
        "counts_none_cup": "Pas de corners ni de cartons pour ce match : aucun des deux clubs n'a de chiffres gratuits dans son championnat.",
        "counts_title": "Corners et cartons attendus",
        "counts_line": "{h} – {a} corners · {ch} – {ca} cartons",
        # Historique des analyses
        "ha_title": "Analyses des derniers jours", "ha_lead": "Chaque match analysé, son score final et ses verdicts : justes ou faux.",
        "ha_yesterday": "Hier", "ha_before": "Avant-hier", "ha_week": "7 jours",
        "ha_none": "Pas encore d'analyse terminée pour ce jour.",
        "ha_day": "{won} verdicts justes sur {n} ({rate}) pour {ann} annoncés",
        "ha_best": "Verdict « le plus sûr » : {won} sur {n} ({rate})",
        "ha_pending": "En attente du résultat", "ha_void": "Match reporté ou annulé",
        "ha_unverif": "Non vérifiable (pas de chiffres gratuits)",
        "ha_engine_v1": "Ancien moteur", "ha_open_match": "Voir les verdicts",
        "ha_past_match": "Ce match est terminé. Voici ce que disait notre analyse.",
        "rel_title": "Fiabilité vérifiée",
        "pk_why": "Pourquoi",
        "rel_tested": "matchs testés sur la saison {season}, que le moteur n'avait jamais vue",
        "rel_best": "de verdicts « le plus sûr » justes sur ce test ({a} annoncés)",
        "tk_same_match": "Deux choix viennent du même match : ils sont liés, la vraie chance du ticket peut être différente.",
        "yesterday_title": "Hier",
        "yesterday_line": "{won} paris gagnés sur {n} ({rate})",
        "vd_res_won": "Juste", "vd_res_lost": "Faux", "vd_res_void": "Match reporté ou annulé",
        "vd_res_nv": "Non vérifiable (pas de chiffres gratuits)",
        "vd_res_open": "Serré : ne compte pas dans le bilan",
        # Forme et face-à-face (fiche match, gratuit)
        "form_title": "Forme et face-à-face",
        "form_lead": "Les 5 derniers matchs de chaque équipe, dans les compétitions que nous suivons.",
        "form_order": "Du plus ancien au plus récent",
        "form_r_W": "V", "form_r_D": "N", "form_r_L": "D",
        "form_rl_W": "Victoire", "form_rl_D": "Nul", "form_rl_L": "Défaite",
        "form_goals": "{gf} buts marqués, {ga} encaissés",
        "form_home": "domicile", "form_away": "extérieur",
        "form_see": "Voir les {n} matchs",
        "form_none": "Pas de match récent dans nos données.",
        "form_comp_other": "Championnat",
        "h2h_title": "Face-à-face",
        "h2h_last": "Sur leurs {n} dernières rencontres",
        "h2h_last1": "Sur leur dernière rencontre",
        "h2h_draws": "nul",
        "h2h_none": "Pas de rencontre entre ces deux équipes ces dernières saisons.",
        "form_note": "Simple rappel des résultats : ils sont déjà pris en compte dans le calcul.",
        "ha_void_short": "Reporté", "ha_ok": "justes", "ha_pending_short": "En attente", "ha_live": "déjà joués · en cours",
        "ha_old_day": "Ce jour-là, seules les listes de paris étaient enregistrées (ancien moteur) : pas encore de verdicts par match.",
        "ha_note": "Chaque verdict est enregistré avant le coup d'envoi, puis jugé avec le score final (ou pendant le match, dès qu'il est déjà joué). Les verdicts « serré » ne comptent pas. Corners et cartons : jugés quand les chiffres sont publiés (2 à 4 jours), non vérifiables pour les coupes.",
        "ha_past_title": "ce que disait l'analyse", "ha_final": "Match terminé",
        "ha_said": "Ce que donnait l'analyse", "ha_top_score": "Score le plus probable : {s}",
        "ha_see_today": "Voir les matchs à venir",
        "hist_old_engine": "Ancien moteur", "hist_bets_title": "Paris du jour : le bilan",
        "nf_title": "Page introuvable", "nf_text": "Cette page n'existe pas ou plus. Les matchs terminés sont dans l'historique des analyses.",
        "nf_back": "Accueil de l'appli",
    },
    "en": {
        "corners_word": "corners", "cards_word": "cards", "more_corners": "More corners",
        "more_cards": "More cards", "equal_word": "{what}: level",
        "vd_title": "Verdicts", "vd_lead": "Yes or no, and the chance that the answer is right.",
        "vd_best": "Most reliable", "vd_yes": "YES", "vd_no": "NO", "vd_open": "CLOSE",
        "vd_open_help": "Too close to call: neither yes nor no above 55%.",
        "vd_proof": "This kind of verdict came true {won} times out of {n} ({rate}) in the {season} season, tested without the engine having seen it.",
        "vd_proof_none": "No verdict is a certainty: out of 10 verdicts at {pct}, about {miss} fail.",
        "vd_note": "The percentage is the chance that the answer (YES or NO) is right. Never a certainty.",
        "vd_q_win": "{team} to win?", "vd_q_dc": "{sel}?", "vd_q_ou": "Over {line} goals?",
        "vd_q_btts": "Both teams to score?", "vd_q_tt": "{team} to score?",
        "vd_q_co": "Over {line} corners?", "vd_q_ca": "Over {line} cards?",
        "vd_partial": "Corners and cards estimated from each club's league (one of them has no data: less reliable estimate).",
        "why_title": "Why", "why_lead": "The reasons behind this analysis, in expected goals.",
        "counts_none": "No free corner or card figures for this competition.",
        "counts_none_cup": "No corners or cards for this match: neither club has free figures in its league.",
        "counts_title": "Expected corners and cards",
        "counts_line": "{h} – {a} corners · {ch} – {ca} cards",
        "ha_title": "Recent analyses", "ha_lead": "Every match we analysed, its final score and its verdicts: right or wrong.",
        "ha_yesterday": "Yesterday", "ha_before": "Day before", "ha_week": "Last 7 days",
        "ha_none": "No finished analysis for this day yet.",
        "ha_day": "{won} correct verdicts out of {n} ({rate}) for {ann} announced",
        "ha_best": "“Most reliable” verdict: {won} out of {n} ({rate})",
        "ha_pending": "Waiting for the result", "ha_void": "Match postponed or cancelled",
        "ha_unverif": "Not verifiable (no free figures)",
        "ha_engine_v1": "Previous engine", "ha_open_match": "See the verdicts",
        "ha_past_match": "This match is over. Here is what our analysis said.",
        "rel_title": "Verified reliability",
        "pk_why": "Why",
        "rel_tested": "matches tested on the {season} season, which the engine had never seen",
        "rel_best": "of “most reliable” verdicts right in that test ({a} announced)",
        "tk_same_match": "Two picks come from the same match: they are linked, so the slip's real chance may differ.",
        "yesterday_title": "Yesterday",
        "yesterday_line": "{won} bets won out of {n} ({rate})",
        "vd_res_won": "Right", "vd_res_lost": "Wrong", "vd_res_void": "Match postponed or cancelled",
        "vd_res_nv": "Not verifiable (no free figures)",
        "vd_res_open": "Too close: not counted in the record",
        # Form and head-to-head (match page, free)
        "form_title": "Form and head-to-head",
        "form_lead": "Each team's last 5 matches, in the competitions we follow.",
        "form_order": "Oldest to most recent",
        "form_r_W": "W", "form_r_D": "D", "form_r_L": "L",
        "form_rl_W": "Win", "form_rl_D": "Draw", "form_rl_L": "Loss",
        "form_goals": "{gf} scored, {ga} conceded",
        "form_home": "home", "form_away": "away",
        "form_see": "See the {n} matches",
        "form_none": "No recent match in our data.",
        "form_comp_other": "League",
        "h2h_title": "Head-to-head",
        "h2h_last": "Over their last {n} meetings",
        "h2h_last1": "In their last meeting",
        "h2h_draws": "draw",
        "h2h_none": "These two teams have not met in recent seasons.",
        "form_note": "Just a reminder of past results: they are already part of the calculation.",
        "ha_void_short": "Postponed", "ha_ok": "right", "ha_pending_short": "Pending", "ha_live": "settled · in play",
        "ha_old_day": "On that day only the bet lists were recorded (previous engine): no per-match verdicts yet.",
        "ha_note": "Every verdict is recorded before kick-off, then judged with the final score (or during the match, as soon as it's decided). “Close” verdicts don't count. Corners and cards: judged when the figures are published (2 to 4 days), not verifiable for cups.",
        "ha_past_title": "what the analysis said", "ha_final": "Full time",
        "ha_said": "What the analysis gave", "ha_top_score": "Most likely score: {s}",
        "ha_see_today": "See upcoming matches",
        "hist_old_engine": "Previous engine", "hist_bets_title": "Daily bets: the record",
        "nf_title": "Page not found", "nf_text": "This page doesn't exist (any more). Finished matches are in the analysis history.",
        "nf_back": "App home",
    },
}

for _lang in LANGS:
    UI[_lang].update(_EXTRA[_lang])
    UI[_lang].update(_BETS[_lang])
    UI[_lang].update(_V2[_lang])
    _JS[_lang].update(_JS_EXTRA[_lang])
    _JS[_lang].update(_BETS_JS[_lang])


def pick_label(key: str, sel: str, line: float | None, lang: str, home: str, away: str) -> str:
    """Libellé clair d'un pari classique : « Victoire Arsenal », « Plus de 1,5 buts », « Chelsea marque »…"""
    t = UI[lang]
    if key == "1x2":
        return t["draw_long"] if sel == "X" else t["home_win"].format(team=home if sel == "1" else away)
    if key in ("tt1", "tt2") and sel == "over" and line in (0.5, 1.5):
        return t["team_scores" if line == 0.5 else "team_scores2"].format(team=home if key == "tt1" else away)
    if key == "ou":
        return f"{selection_label(key, sel, line, lang, home, away)} {t['goals_word']}"
    if key == "btts":
        return t["btts_yes_long"] if sel == "yes" else t["btts_no_long"]
    if key == "dnb":
        return f"{selection_label(key, sel, line, lang, home, away)} ({t['dnb_short']})"
    if key in ("co", "ca", "cot1", "cot2", "cat1", "cat2"):
        word = t["corners_word" if key.startswith("co") else "cards_word"]
        txt = f"{selection_label(key, sel, line, lang, home, away)} {word}"
        if key[-1] in "12":
            return f"{home if key[-1] == '1' else away}{JS_COLON[lang]}{txt[:1].lower() + txt[1:]}"
        return txt
    if key in ("co1x2", "ca1x2"):
        word = t["more_corners" if key == "co1x2" else "more_cards"]
        return t["equal_word"].format(what=word) if sel == "X" else f"{word}{JS_COLON[lang]}{home if sel == '1' else away}"
    return selection_label(key, sel, line, lang, home, away)

