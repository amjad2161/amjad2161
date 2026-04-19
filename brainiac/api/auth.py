"""API authentication and authorization helpers."""

from __future__ import annotations

import os

from fastapi import HTTPException, Request

API_KEY_HEADER = "X-API-Key"


def parse_keys(env: str | None) -> set[str]:
    if not env:
        return set()
    return {item.strip() for item in env.split(",") if item.strip()}


def _configured_keys() -> tuple[set[str], set[str]]:
    api_keys = parse_keys(os.getenv("BRAINIAC_API_KEYS"))
    admin_keys = parse_keys(os.getenv("BRAINIAC_ADMIN_API_KEYS"))
    return api_keys, admin_keys


def require_api_key(request: Request, *, admin: bool = False) -> None:
    api_keys, admin_keys = _configured_keys()
    if not api_keys and not admin_keys:
        return

    provided_key = request.headers.get(API_KEY_HEADER)
    if not provided_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    all_keys = api_keys | admin_keys
    if provided_key not in all_keys:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if admin and provided_key not in admin_keys:
        raise HTTPException(status_code=403, detail="Admin API key required")


def is_admin(request: Request) -> bool:
    _, admin_keys = _configured_keys()
    provided_key = request.headers.get(API_KEY_HEADER)
    return bool(provided_key and provided_key in admin_keys)
