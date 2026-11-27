"""Générateur de coupons sur plusieurs jours et équipes suivies (mise à niveau 4)."""
import re
from datetime import datetime, timezone
from pathlib import Path

from probalis.site import build, i18n

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "probalis" / "site"


def _match(mid, ko):
    sel = lambda **ps: {k: {"p": v, "fair": round(1 / v, 3)} for k, v in ps.items()}  # noqa: E731
    return {"id": mid, "slug": f"s-{mid}", "league": "E0", "kickoff": ko, "confidence": "high",
            "home": {"name": f"H{mid}"}, "away": {"name": f"A{mid}"},
            "markets": [{"key": "1x2", "sel": sel(**{"1": 0.5, "X": 0.3, "2": 0.2})},
                        {"key": "ou", "line": 1.5, "sel": sel(over=0.75, under=0.25)}]}


def test_ticket_data_has_league_code_and_every_upcoming_day():
    """Le générateur filtre par compétition (code « lc ») et sur plusieurs jours (« d » de chaque match)."""
    now = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)
    ms = [_match("a", "2026-11-27T19:00:00+00:00"), _match("b", "2026-11-29T15:00:00+00:00"),
          _match("old", "2026-11-27T10:00:00+00:00")]
    data = build._ticket_data(ms, "fr", now)
    got = {m["id"]: m for m in data["matches"]}
    assert set(got) == {"a", "b"}  # les matchs déjà commencés ne sont pas proposés
    assert got["a"]["lc"] == "E0" and got["a"]["lg"]
    assert (got["a"]["d"], got["b"]["d"]) == ("2026-11-27", "2026-11-29")
    assert got["a"]["h"] == "Ha"  # même nom que celui enregistré dans les équipes suivies


def test_migration_adds_followed_teams_member_can_edit():
    sql = (ROOT / "supabase/migrations/20261127120000_equipes_suivies.sql").read_text(encoding="utf-8")
    assert "add column if not exists favorite_teams text[] not null default '{}'" in sql
    assert "cardinality(favorite_teams) <= 50" in sql
    assert "grant update (favorite_teams) on public.profiles to authenticated" in sql
    assert "premium_until" not in sql  # rien d'autre n'est ouvert à l'écriture


def test_texts_exist_in_both_languages():
    ui = ("mode_gen", "mode_gen_help", "tk_today", "tk_tomorrow", "gen_period", "gen_3d", "gen_7d", "gen_custom", "gen_from", "gen_to", "gen_goal",
          "gen_odds", "gen_more", "gen_leagues", "gen_types", "gen_min", "gen_favs", "gen_btn", "fam_corners", "fam_cards",
          "follow", "fav_chip", "fav_lg", "my_teams", "my_teams_none", "teams_title", "teams_help", "teams_none")
    js = ("follow", "followed", "follow_team", "unfollow_team", "fav_signin", "fav_full", "fav_team_on", "fav_off",
          "gen_range", "gen_zero", "gen_few", "gen_few0", "gen_none_odds", "gen_no_match", "gen_favs_help", "gen_favs_empty",
          "gen_calc", "tk_today", "tk_tomorrow", "tk_bad_target")
    for lang in i18n.LANGS:
        assert all(i18n.UI[lang].get(k) for k in ui), lang
        assert all(i18n._JS[lang].get(k) for k in js), lang
    assert "Cote cible" not in i18n.UI["fr"]["auto_lock"]  # l'ancien mode n'existe plus


def test_pages_have_generator_and_follow_controls():
    tk = (SITE / "templates/ticket.html").read_text(encoding="utf-8")
    assert 'data-mode="gen"' in tk and 'data-mode="target"' not in tk and 'data-mode="count"' not in tk
    for per in ("today", "tomorrow", "3", "7", "custom"):
        assert f'data-per="{per}"' in tk
    assert 'id="gen-out"' in tk and 'id="gm-favs"' in tk
    match = (SITE / "templates/match.html").read_text(encoding="utf-8")
    assert match.count("data-follow=") == 2
    home = (SITE / "templates/matches.html").read_text(encoding="utf-8")
    assert "favs-chip" in home and 'id="myteams"' in home and "data-fav-league" in home
    js = (SITE / "static/app.js").read_text(encoding="utf-8")
    assert "favorite_teams: []" in js
    assert re.search(r"mode === 'target' \|\| mode === 'count'\) mode = 'gen'", js)  # ancien choix gardé en mémoire
