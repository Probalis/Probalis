"""Copie complète chiffrée de l'historique et garde-fous : on ne republie jamais un historique amputé."""
from datetime import datetime, timezone

import pytest

from probalis import __main__ as cli
from probalis.site import history


def _full():
    """Un jour figé avec un pari réglé et un pari en attente (Premium), plus l'analyse d'un match à venir."""
    return {"version": 1, "days": {"2026-11-21": {
        "frozen": True, "built": "2026-11-20T23:00:00+00:00",
        "tiers": {"safe": [{"id": "1|dc||1X", "mid": "1", "key": "dc", "sel": "1X", "p": 0.8, "res": "won"},
                           {"id": "2|dc||X2", "mid": "2", "key": "dc", "sel": "X2", "p": 0.78}]},
        "coupons": [],
        "matches": {"1": {"kickoff": "2026-11-21T13:00:00+00:00", "score": [2, 0]},
                    "2": {"kickoff": "2026-11-21T20:00:00+00:00"}},
        "an": {"2": {"v": "x"}}}}}


NOW = datetime(2026, 11, 21, 15, 0, tzinfo=timezone.utc)


def test_seal_roundtrip_and_wrong_key():
    key = history.new_key()
    blob = history.seal(_full(), key)
    assert b'"sel":"X2"' not in blob and b"frozen" not in blob  # illisible sans la clé
    assert history.unseal(blob, key) == _full()
    with pytest.raises(history.HistoryKeyError):
        history.unseal(blob, history.new_key())


def test_full_copy_beats_public_copy():
    pub = history.public_copy(_full(), NOW)
    assert pub["days"]["2026-11-21"]["sealed"]  # la version publique cache le pari en attente
    merged = history.merge(pub, None, _full())
    assert len(merged["days"]["2026-11-21"]["tiers"]["safe"]) == 2


def test_more_analyses_wins_on_tie():
    a, b = _full(), _full()
    b["days"]["2026-11-21"]["an"]["3"] = {"v": "y"}
    assert history.merge(a, b)["days"]["2026-11-21"] is b["days"]["2026-11-21"]


def _setup(monkeypatch, tmp_path, remote, full, key="k", local=None):
    monkeypatch.setattr(history, "LOCAL", tmp_path / "history.json")
    if local is not None:
        history.LOCAL.write_text(__import__("json").dumps(local), encoding="utf-8")
    monkeypatch.setattr(history, "_remote", lambda url: remote)
    monkeypatch.setattr(history, "_remote_full", lambda url, k: full)
    if key:
        monkeypatch.setenv(history.KEY_ENV, key)
    else:
        monkeypatch.delenv(history.KEY_ENV, raising=False)


def test_load_stops_with_public_copy_only(monkeypatch, tmp_path):
    """GitHub Actions sans copie locale ni copie complète : arrêt, au lieu d'effacer le pari en attente."""
    _setup(monkeypatch, tmp_path, history.public_copy(_full(), NOW), None, key=None)
    with pytest.raises(RuntimeError, match="Historique complet introuvable"):
        history.load("https://exemple.test")


def test_load_uses_full_copy_without_local(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path, history.public_copy(_full(), NOW), _full())
    days = history.load("https://exemple.test")["days"]
    assert len(days["2026-11-21"]["tiers"]["safe"]) == 2


def test_load_wrong_key_stops(monkeypatch, tmp_path):
    def bad(url, k):
        raise history.HistoryKeyError("clé fausse")
    _setup(monkeypatch, tmp_path, history.public_copy(_full(), NOW), None, local=_full())
    monkeypatch.setattr(history, "_remote_full", bad)
    with pytest.raises(history.HistoryKeyError):
        history.load("https://exemple.test")


def test_load_fresh_site_allowed(monkeypatch, tmp_path):
    """Tout premier lancement (rien en ligne, rien en local) : on part d'un historique vide."""
    _setup(monkeypatch, tmp_path, None, None, key=None)
    assert history.load("https://exemple.test")["days"] == {}


def test_save_publishes_sealed_copy_only_with_key(monkeypatch, tmp_path):
    monkeypatch.setattr(history, "LOCAL", tmp_path / "cache" / "history.json")
    key = history.new_key()
    monkeypatch.setenv(history.KEY_ENV, key)
    history.save(_full(), tmp_path / "pub", NOW)
    blob = (tmp_path / "pub" / history.FULL_NAME).read_bytes()
    assert len(history.unseal(blob, key)["days"]["2026-11-21"]["tiers"]["safe"]) == 2
    monkeypatch.delenv(history.KEY_ENV)
    history.save(_full(), tmp_path / "pub2", NOW)
    assert not (tmp_path / "pub2" / history.FULL_NAME).exists()


def test_env_files_never_override(monkeypatch, tmp_path):
    (tmp_path / "site-public.env").write_text("PROBALIS_TEST_A=fichier\nPROBALIS_TEST_B=fichier\n# note\n",
                                              encoding="utf-8")
    monkeypatch.setenv("PROBALIS_TEST_A", "deja")
    monkeypatch.delenv("PROBALIS_TEST_B", raising=False)
    assert cli.load_env_files(tmp_path) == ["site-public.env"]
    import os
    assert os.environ["PROBALIS_TEST_A"] == "deja" and os.environ["PROBALIS_TEST_B"] == "fichier"
    monkeypatch.delenv("PROBALIS_TEST_B")
