"""Tests for encrypted social account store and OAuth helpers."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from brainiac.core.reel_maker import Platform, ReelMaker
from brainiac.core.social_accounts import SocialAccountStore, get_social_store
from brainiac.core.social_oauth import (
    OAuthStateStore,
    oauth_providers_status,
    start_all_connections,
)


@pytest.fixture
def reel_maker(tmp_path: Path) -> ReelMaker:
    return ReelMaker(output_dir=tmp_path)


def test_social_store_encrypts_at_rest(tmp_path: Path) -> None:
    store = SocialAccountStore(tmp_path, secret="test-secret")
    account = store.add_account(
        platform="tiktok",
        label="test · TikTok",
        access_token="secret-token",
        extra={"open_id": "oid-1"},
        group_id="grp-1",
    )
    raw_path = tmp_path / "social" / "accounts.json.enc"
    assert raw_path.is_file()
    assert b"secret-token" not in raw_path.read_bytes()

    reloaded = SocialAccountStore(tmp_path, secret="test-secret")
    loaded = reloaded.get_account(account.id)
    assert loaded is not None
    assert loaded.access_token == "secret-token"
    assert loaded.extra["open_id"] == "oid-1"


def test_social_store_default_and_remove(tmp_path: Path) -> None:
    store = SocialAccountStore(tmp_path, secret="test-secret")
    a1 = store.add_account(platform="youtube", label="A", access_token="t1")
    a2 = store.add_account(platform="youtube", label="B", access_token="t2")
    default = store.get_default("youtube")
    assert default is not None
    assert default.id == a1.id

    store.set_default(a2.id)
    default = store.get_default("youtube")
    assert default is not None
    assert default.id == a2.id

    assert store.remove_account(a2.id) is True
    default = store.get_default("youtube")
    assert default is not None
    assert default.id == a1.id
    assert store.remove_account(a1.id) is True
    assert store.get_default("youtube") is None


def test_credentials_for_platform_expired(tmp_path: Path) -> None:
    store = SocialAccountStore(tmp_path, secret="test-secret")
    account = store.add_account(
        platform="instagram",
        label="IG",
        access_token="tok",
        extra={"user_id": "123"},
        expires_at=time.time() - 10,
    )
    creds = store.credentials_for_platform("instagram", account_id=account.id)
    assert creds is None


def test_oauth_state_store_roundtrip(tmp_path: Path) -> None:
    states = OAuthStateStore(tmp_path)
    state = states.create(provider="meta", label="bundle", group_id="g1", return_to="/reel")
    entry = states.pop(state)
    assert entry is not None
    assert entry["provider"] == "meta"
    assert entry["group_id"] == "g1"
    assert states.pop(state) is None


def test_start_all_connections_group_id() -> None:
    bundle = start_all_connections(label="my-bundle")
    assert bundle["label"] == "my-bundle"
    assert bundle["group_id"]
    assert len(bundle["connections"]) == 3
    for conn in bundle["connections"]:
        assert "start_url" in conn
        assert "group_id=my-bundle" not in conn["start_url"]


def test_oauth_providers_status_shape() -> None:
    providers = oauth_providers_status()
    assert set(providers) == {"meta", "youtube", "tiktok"}
    for spec in providers.values():
        assert "configured" in spec
        assert "start_path" in spec


def test_get_social_store_singleton_path(tmp_path: Path) -> None:
    store = get_social_store(tmp_path)
    store.add_account(platform="facebook", label="FB", access_token="x", extra={"page_id": "1"})
    assert store.any_platform_configured() is True


@pytest.mark.asyncio
async def test_publish_uses_stored_credentials(
    reel_maker: ReelMaker, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = get_social_store(reel_maker._output_dir)
    store.add_account(
        platform="tiktok",
        label="stored",
        access_token="stored-tiktok-token",
        extra={"open_id": "oid"},
    )
    job = await reel_maker.compose("cred topic", platforms=[Platform.TIKTOK], voiceover=False)
    captured: dict[str, str] = {}

    async def fake_tiktok(payload: dict, *, dry_run: bool) -> dict:
        captured["token"] = (payload.get("credentials") or {}).get("access_token", "")
        return {"dry_run": dry_run, "platform": "tiktok"}

    monkeypatch.setattr(reel_maker, "_publish_tiktok", fake_tiktok)
    result = await reel_maker.publish(job.job_id, dry_run=False)
    assert result["dry_run"] is False
    assert captured["token"] == "stored-tiktok-token"
