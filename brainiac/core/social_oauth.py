"""OAuth helpers for one-click social account connection."""

from __future__ import annotations

import json
import os
import secrets
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import structlog

from brainiac.core.social_accounts import SocialAccountStore, get_social_store

log = structlog.get_logger("brainiac.social_oauth")

STATE_TTL_S = 600
_PUBLIC_BASE = os.getenv("BRAINIAC_REEL_PUBLIC_BASE_URL", "").rstrip("/")
_REDIRECT_BASE = os.getenv(
    "BRAINIAC_OAUTH_REDIRECT_BASE", _PUBLIC_BASE or "http://127.0.0.1:8000"
).rstrip("/")

META_APP_ID = os.getenv("META_APP_ID", os.getenv("FACEBOOK_APP_ID", "")).strip()
META_APP_SECRET = os.getenv("META_APP_SECRET", os.getenv("FACEBOOK_APP_SECRET", "")).strip()
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()


@dataclass(frozen=True)
class OAuthProviderSpec:
    key: str
    label: str
    platforms: tuple[str, ...]
    app_id_env: str
    app_secret_env: str

    def configured(self) -> bool:
        if self.key == "meta":
            return bool(META_APP_ID and META_APP_SECRET)
        if self.key == "youtube":
            return bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
        if self.key == "tiktok":
            return bool(TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET)
        return False


OAUTH_PROVIDERS: dict[str, OAuthProviderSpec] = {
    "meta": OAuthProviderSpec(
        key="meta",
        label="Meta (Instagram + Facebook)",
        platforms=("instagram", "facebook"),
        app_id_env="META_APP_ID",
        app_secret_env="META_APP_SECRET",
    ),
    "youtube": OAuthProviderSpec(
        key="youtube",
        label="YouTube",
        platforms=("youtube",),
        app_id_env="GOOGLE_CLIENT_ID",
        app_secret_env="GOOGLE_CLIENT_SECRET",
    ),
    "tiktok": OAuthProviderSpec(
        key="tiktok",
        label="TikTok",
        platforms=("tiktok",),
        app_id_env="TIKTOK_CLIENT_KEY",
        app_secret_env="TIKTOK_CLIENT_SECRET",
    ),
}


class OAuthStateStore:
    def __init__(self, base_dir: Path) -> None:
        self._path = base_dir / "social" / "oauth_states.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            data = json.loads(self._path.read_text())
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, data: dict[str, Any]) -> None:
        self._path.write_text(json.dumps(data, separators=(",", ":")))

    def create(
        self,
        *,
        provider: str,
        label: str,
        group_id: str | None,
        return_to: str | None,
    ) -> str:
        state = secrets.token_urlsafe(24)
        data = self._read()
        now = time.time()
        data = {k: v for k, v in data.items() if float(v.get("expires_at", 0)) > now}
        data[state] = {
            "provider": provider,
            "label": label,
            "group_id": group_id,
            "return_to": return_to or "/reel",
            "expires_at": now + STATE_TTL_S,
        }
        self._write(data)
        return state

    def pop(self, state: str) -> dict[str, Any] | None:
        data = self._read()
        entry = data.pop(state, None)
        self._write(data)
        if not entry:
            return None
        if float(entry.get("expires_at", 0)) < time.time():
            return None
        return entry


def redirect_uri(provider: str) -> str:
    return f"{_REDIRECT_BASE}/api/v1/reel/social/oauth/callback/{provider}"


def oauth_providers_status() -> dict[str, Any]:
    return {
        key: {
            "label": spec.label,
            "platforms": list(spec.platforms),
            "configured": spec.configured(),
            "start_path": f"/api/v1/reel/social/oauth/start/{key}",
        }
        for key, spec in OAUTH_PROVIDERS.items()
    }


def start_all_connections(*, label: str = "default", group_id: str | None = None) -> dict[str, Any]:
    gid = group_id or str(uuid.uuid4())
    connections = []
    for key, spec in OAUTH_PROVIDERS.items():
        query = urlencode({"label": label, "group_id": gid})
        connections.append(
            {
                "provider": key,
                "label": spec.label,
                "platforms": list(spec.platforms),
                "configured": spec.configured(),
                "start_url": f"/api/v1/reel/social/oauth/start/{key}?{query}",
            }
        )
    return {"group_id": gid, "label": label, "connections": connections}


def build_authorization_url(
    provider: str,
    *,
    output_dir: Path,
    label: str = "default",
    group_id: str | None = None,
    return_to: str | None = None,
) -> str:
    spec = OAUTH_PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(f"Unknown OAuth provider: {provider}")
    if not spec.configured():
        raise ValueError(
            f"OAuth app not configured for {provider}. Set {spec.app_id_env} and {spec.app_secret_env}."
        )
    state = OAuthStateStore(output_dir).create(
        provider=provider,
        label=label,
        group_id=group_id,
        return_to=return_to,
    )
    cb = redirect_uri(provider)
    if provider == "meta":
        params = {
            "client_id": META_APP_ID,
            "redirect_uri": cb,
            "state": state,
            "scope": ",".join(
                [
                    "instagram_basic",
                    "instagram_content_publish",
                    "pages_show_list",
                    "pages_manage_posts",
                    "pages_read_engagement",
                    "business_management",
                ]
            ),
            "response_type": "code",
        }
        return f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"
    if provider == "youtube":
        params = {
            "client_id": GOOGLE_CLIENT_ID,
            "redirect_uri": cb,
            "state": state,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "scope": "https://www.googleapis.com/auth/youtube.upload",
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    if provider == "tiktok":
        params = {
            "client_key": TIKTOK_CLIENT_KEY,
            "redirect_uri": cb,
            "state": state,
            "response_type": "code",
            "scope": "user.info.basic,video.publish,video.upload",
        }
        return f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"
    raise ValueError(f"Unsupported provider: {provider}")


async def handle_oauth_callback(
    provider: str,
    *,
    code: str,
    state: str,
    output_dir: Path,
) -> dict[str, Any]:
    spec = OAUTH_PROVIDERS.get(provider)
    if spec is None:
        raise ValueError(f"Unknown OAuth provider: {provider}")
    state_entry = OAuthStateStore(output_dir).pop(state)
    if state_entry is None:
        raise ValueError("Invalid or expired OAuth state")
    if state_entry.get("provider") != provider:
        raise ValueError("OAuth state provider mismatch")

    store = get_social_store(output_dir)
    label = str(state_entry.get("label") or "default")
    group_id = state_entry.get("group_id")
    created: list[dict[str, Any]] = []

    if provider == "meta":
        created = await _exchange_meta(code, store, label=label, group_id=group_id)
    elif provider == "youtube":
        created = await _exchange_youtube(code, store, label=label, group_id=group_id)
    elif provider == "tiktok":
        created = await _exchange_tiktok(code, store, label=label, group_id=group_id)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    return {
        "provider": provider,
        "label": label,
        "group_id": group_id,
        "accounts": created,
        "return_to": state_entry.get("return_to") or "/reel",
    }


async def _exchange_meta(
    code: str,
    store: SocialAccountStore,
    *,
    label: str,
    group_id: str | None,
) -> list[dict[str, Any]]:
    import httpx

    cb = redirect_uri("meta")
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={
                "client_id": META_APP_ID,
                "client_secret": META_APP_SECRET,
                "redirect_uri": cb,
                "code": code,
            },
        )
        token_body = token_resp.json() if token_resp.content else {}
        if not token_resp.is_success:
            raise ValueError(f"Meta token exchange failed: {token_body}")
        user_token = str(token_body.get("access_token", ""))
        if not user_token:
            raise ValueError("Meta token exchange returned no access_token")

        pages_resp = await client.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={
                "access_token": user_token,
                "fields": "id,name,access_token,instagram_business_account",
            },
        )
        pages_body = pages_resp.json() if pages_resp.content else {}
        if not pages_resp.is_success:
            raise ValueError(f"Meta pages lookup failed: {pages_body}")

    created_accounts: list[dict[str, Any]] = []
    pages = pages_body.get("data") or []
    if not pages:
        raise ValueError(
            "No Facebook Pages found for this Meta account. Connect a Page with an Instagram Business account."
        )

    for page in pages:
        page_id = str(page.get("id", ""))
        page_token = str(page.get("access_token") or user_token)
        page_name = str(page.get("name") or page_id)
        ig = page.get("instagram_business_account") or {}
        ig_id = str(ig.get("id") or "")

        fb_account = store.add_account(
            platform="facebook",
            label=f"{label} · {page_name}",
            access_token=page_token,
            extra={"page_id": page_id, "page_name": page_name},
            group_id=group_id,
        )
        created_accounts.append(fb_account.to_public(is_default=True))

        if ig_id:
            ig_account = store.add_account(
                platform="instagram",
                label=f"{label} · {page_name} (IG)",
                access_token=page_token,
                extra={"user_id": ig_id, "page_id": page_id, "page_name": page_name},
                group_id=group_id,
            )
            created_accounts.append(ig_account.to_public(is_default=True))

    return created_accounts


async def _exchange_youtube(
    code: str,
    store: SocialAccountStore,
    *,
    label: str,
    group_id: str | None,
) -> list[dict[str, Any]]:
    import httpx

    cb = redirect_uri("youtube")
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": cb,
                "grant_type": "authorization_code",
            },
        )
        token_body = token_resp.json() if token_resp.content else {}
        if not token_resp.is_success:
            raise ValueError(f"YouTube token exchange failed: {token_body}")
        access_token = str(token_body.get("access_token", ""))
        refresh_token = token_body.get("refresh_token")
        expires_in = token_body.get("expires_in")
        expires_at = time.time() + float(expires_in) if expires_in else None
        if not access_token:
            raise ValueError("YouTube token exchange returned no access_token")

        channel_resp = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        channel_body = channel_resp.json() if channel_resp.content else {}
        channel_title = "YouTube"
        channel_id = ""
        items = channel_body.get("items") or []
        if items:
            channel_id = str(items[0].get("id") or "")
            snippet = items[0].get("snippet") or {}
            channel_title = str(snippet.get("title") or channel_title)

    account = store.add_account(
        platform="youtube",
        label=f"{label} · {channel_title}",
        access_token=access_token,
        refresh_token=str(refresh_token) if refresh_token else None,
        expires_at=expires_at,
        extra={"channel_id": channel_id, "channel_title": channel_title},
        group_id=group_id,
    )
    return [account.to_public(is_default=True)]


async def _exchange_tiktok(
    code: str,
    store: SocialAccountStore,
    *,
    label: str,
    group_id: str | None,
) -> list[dict[str, Any]]:
    import httpx

    cb = redirect_uri("tiktok")
    async with httpx.AsyncClient(timeout=30.0) as client:
        token_resp = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": TIKTOK_CLIENT_KEY,
                "client_secret": TIKTOK_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": cb,
            },
        )
        token_body = token_resp.json() if token_resp.content else {}
        if not token_resp.is_success:
            raise ValueError(f"TikTok token exchange failed: {token_body}")
        data = token_body.get("data") or token_body
        access_token = str(data.get("access_token") or "")
        refresh_token = data.get("refresh_token")
        open_id = str(data.get("open_id") or "")
        expires_in = data.get("expires_in") or data.get("expires_in_sec")
        expires_at = time.time() + float(expires_in) if expires_in else None
        if not access_token:
            raise ValueError("TikTok token exchange returned no access_token")

    account = store.add_account(
        platform="tiktok",
        label=f"{label} · TikTok",
        access_token=access_token,
        refresh_token=str(refresh_token) if refresh_token else None,
        expires_at=expires_at,
        extra={"open_id": open_id},
        group_id=group_id,
    )
    return [account.to_public(is_default=True)]
