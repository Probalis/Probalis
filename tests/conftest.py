"""Réglages communs des tests : jamais d'appel réseau vers ESPN, cache ESPN dans un dossier temporaire."""
import pytest

from probalis.football import espn


@pytest.fixture(autouse=True)
def _espn_offline(monkeypatch, tmp_path):
    monkeypatch.setattr(espn, "_fetch", lambda url: None)
    monkeypatch.setattr(espn, "DIR", tmp_path / "espn")
    monkeypatch.setattr(espn, "_down", set())
    monkeypatch.setattr(espn, "_state", {"last": 0.0, "fails": 0})
    monkeypatch.setattr(espn, "errors", {})
