"""Tests for API auth helper utilities."""

from __future__ import annotations

from fastapi import Request

from brainiac.api.auth import is_admin, parse_keys


def _request_with_api_key(value: str | None) -> Request:
    headers = []
    if value is not None:
        headers.append((b"x-api-key", value.encode("utf-8")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "http_version": "1.1",
    }
    return Request(scope)


def test_parse_keys() -> None:
    assert parse_keys(None) == set()
    assert parse_keys(" key1, key2 ,,key3 ") == {"key1", "key2", "key3"}


def test_is_admin_true_for_admin_key(monkeypatch) -> None:
    monkeypatch.setenv("BRAINIAC_ADMIN_API_KEYS", "admin-a,admin-b")
    request = _request_with_api_key("admin-b")
    assert is_admin(request) is True


def test_is_admin_false_for_non_admin_key(monkeypatch) -> None:
    monkeypatch.setenv("BRAINIAC_ADMIN_API_KEYS", "admin-a")
    request = _request_with_api_key("user-a")
    assert is_admin(request) is False
