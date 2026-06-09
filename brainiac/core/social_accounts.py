"""Encrypted on-disk store for connected social publishing accounts."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

_STORE_FILENAME = "accounts.json.enc"
_ENV_TOKEN_KEYS = (
    "INSTAGRAM_ACCESS_TOKEN",
    "TIKTOK_ACCESS_TOKEN",
    "YOUTUBE_ACCESS_TOKEN",
    "FACEBOOK_ACCESS_TOKEN",
)
_PLATFORM_ENV: dict[str, dict[str, str]] = {
    "instagram": {"token": "INSTAGRAM_ACCESS_TOKEN", "extra": "INSTAGRAM_USER_ID"},
    "tiktok": {"token": "TIKTOK_ACCESS_TOKEN"},
    "youtube": {"token": "YOUTUBE_ACCESS_TOKEN"},
    "facebook": {"token": "FACEBOOK_ACCESS_TOKEN", "extra": "FACEBOOK_PAGE_ID"},
}
_DEFAULT_SECRET = "CHANGE-IN-PRODUCTION"


@dataclass
class SocialAccount:
    id: str
    platform: str
    label: str
    access_token: str
    refresh_token: str | None = None
    expires_at: float | None = None
    extra: dict[str, str] = field(default_factory=dict)
    group_id: str | None = None
    connected_at: float = field(default_factory=time.time)

    def to_public(self, *, is_default: bool = False) -> dict[str, Any]:
        public_extra = {
            k: v
            for k, v in self.extra.items()
            if k
            in (
                "user_id",
                "page_id",
                "page_name",
                "username",
                "open_id",
                "channel_id",
                "channel_title",
            )
        }
        return {
            "id": self.id,
            "platform": self.platform,
            "label": self.label,
            "group_id": self.group_id,
            "connected_at": self.connected_at,
            "expires_at": self.expires_at,
            "extra": public_extra,
            "is_default": is_default,
            "token_expired": bool(self.expires_at and self.expires_at <= time.time()),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SocialAccount:
        return cls(
            id=str(data["id"]),
            platform=str(data["platform"]),
            label=str(data.get("label") or data["platform"]),
            access_token=str(data["access_token"]),
            refresh_token=data.get("refresh_token"),
            expires_at=data.get("expires_at"),
            extra={str(k): str(v) for k, v in (data.get("extra") or {}).items()},
            group_id=data.get("group_id"),
            connected_at=float(data.get("connected_at") or time.time()),
        )


def _fernet(secret: str) -> Fernet:
    digest = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _store_secret() -> str:
    return os.getenv("BRAINIAC_SECRET", _DEFAULT_SECRET)


class SocialAccountStore:
    """Persists OAuth-connected accounts under the reel output directory."""

    def __init__(self, base_dir: Path, *, secret: str | None = None) -> None:
        self._dir = base_dir / "social"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._path = self._dir / _STORE_FILENAME
        self._secret = secret or _store_secret()
        self._fernet = _fernet(self._secret)
        self._data = self._load()

    def _load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"accounts": [], "defaults": {}}
        try:
            raw = self._fernet.decrypt(self._path.read_bytes())
            payload = json.loads(raw.decode())
            if not isinstance(payload, dict):
                return {"accounts": [], "defaults": {}}
            payload.setdefault("accounts", [])
            payload.setdefault("defaults", {})
            return payload
        except (InvalidToken, json.JSONDecodeError, OSError):
            return {"accounts": [], "defaults": {}}

    def _save(self) -> None:
        body = json.dumps(self._data, separators=(",", ":"), default=str).encode()
        self._path.write_bytes(self._fernet.encrypt(body))

    def list_accounts(self, *, platform: str | None = None) -> list[SocialAccount]:
        accounts = [SocialAccount.from_dict(a) for a in self._data.get("accounts", [])]
        if platform:
            accounts = [a for a in accounts if a.platform == platform]
        return sorted(accounts, key=lambda a: a.connected_at, reverse=True)

    def get_account(self, account_id: str) -> SocialAccount | None:
        for raw in self._data.get("accounts", []):
            if raw.get("id") == account_id:
                return SocialAccount.from_dict(raw)
        return None

    def get_default(self, platform: str) -> SocialAccount | None:
        default_id = (self._data.get("defaults") or {}).get(platform)
        if default_id:
            return self.get_account(str(default_id))
        accounts = self.list_accounts(platform=platform)
        return accounts[0] if accounts else None

    def set_default(self, account_id: str) -> SocialAccount:
        account = self.get_account(account_id)
        if not account:
            raise ValueError(f"Account not found: {account_id}")
        defaults = self._data.setdefault("defaults", {})
        defaults[account.platform] = account_id
        self._save()
        return account

    def upsert_account(self, account: SocialAccount) -> SocialAccount:
        accounts: list[dict[str, Any]] = self._data.setdefault("accounts", [])
        replaced = False
        for idx, raw in enumerate(accounts):
            if raw.get("id") == account.id:
                accounts[idx] = asdict(account)
                replaced = True
                break
        if not replaced:
            accounts.append(asdict(account))
        defaults = self._data.setdefault("defaults", {})
        if account.platform not in defaults:
            defaults[account.platform] = account.id
        self._save()
        return account

    def add_account(
        self,
        *,
        platform: str,
        label: str,
        access_token: str,
        refresh_token: str | None = None,
        expires_at: float | None = None,
        extra: dict[str, str] | None = None,
        group_id: str | None = None,
        account_id: str | None = None,
    ) -> SocialAccount:
        account = SocialAccount(
            id=account_id or str(uuid.uuid4()),
            platform=platform,
            label=label,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            extra=extra or {},
            group_id=group_id,
        )
        return self.upsert_account(account)

    def remove_account(self, account_id: str) -> bool:
        accounts: list[dict[str, Any]] = self._data.get("accounts", [])
        new_accounts = [a for a in accounts if a.get("id") != account_id]
        if len(new_accounts) == len(accounts):
            return False
        self._data["accounts"] = new_accounts
        defaults: dict[str, str] = self._data.get("defaults", {})
        for platform, default_id in list(defaults.items()):
            if default_id == account_id:
                remaining = [a for a in new_accounts if a.get("platform") == platform]
                if remaining:
                    defaults[platform] = str(remaining[0]["id"])
                else:
                    del defaults[platform]
        self._save()
        return True

    def list_public(self) -> list[dict[str, Any]]:
        defaults = self._data.get("defaults") or {}
        return [
            acc.to_public(is_default=defaults.get(acc.platform) == acc.id)
            for acc in self.list_accounts()
        ]

    def credentials_for_platform(
        self,
        platform: str,
        *,
        account_id: str | None = None,
    ) -> dict[str, str] | None:
        plat = str(platform)
        account: SocialAccount | None
        if account_id:
            account = self.get_account(account_id)
            if account is None or account.platform != plat:
                return None
        else:
            account = self.get_default(plat)
        if account is None:
            return None
        if account.expires_at and account.expires_at <= time.time():
            return None
        creds: dict[str, str] = {"access_token": account.access_token}
        for key, value in account.extra.items():
            creds.setdefault(key, value)
        return creds

    def any_platform_configured(self) -> bool:
        if self.list_accounts():
            return True
        return any(os.getenv(k) for k in _ENV_TOKEN_KEYS)

    def platform_configured(self, platform: str) -> bool:
        plat = str(platform)
        if self.list_accounts(platform=plat):
            return True
        env = _PLATFORM_ENV.get(plat, {})
        token_set = bool(os.getenv(env.get("token", "")))
        extra_key = env.get("extra")
        extra_set = bool(os.getenv(extra_key)) if extra_key else True
        return token_set and extra_set


def get_social_store(output_dir: Path) -> SocialAccountStore:
    return SocialAccountStore(output_dir)
