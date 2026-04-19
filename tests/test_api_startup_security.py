"""Startup security warning tests for API application."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_startup_warns_when_default_secret(monkeypatch, capsys):
    monkeypatch.setenv("BRAINIAC_SECRET", "CHANGE-IN-PRODUCTION")
    monkeypatch.setenv("BRAINIAC_API_KEYS", "test-key")
    monkeypatch.setenv("BRAINIAC_ADMIN_API_KEYS", "test-admin-key")

    with patch("brainiac.core.neuro_core.anthropic.AsyncAnthropic"):
        from brainiac.api.main import app

        with TestClient(app, raise_server_exceptions=False):
            pass

    captured = capsys.readouterr()
    assert "brainiac.security.default_secret" in captured.out


def test_startup_warns_when_api_keys_missing(monkeypatch, capsys):
    monkeypatch.setenv("BRAINIAC_SECRET", "test-secret")
    monkeypatch.delenv("BRAINIAC_API_KEYS", raising=False)
    monkeypatch.delenv("BRAINIAC_ADMIN_API_KEYS", raising=False)

    with patch("brainiac.core.neuro_core.anthropic.AsyncAnthropic"):
        from brainiac.api.main import app

        with TestClient(app, raise_server_exceptions=False):
            pass

    captured = capsys.readouterr()
    assert "brainiac.security.api_keys_missing" in captured.out
