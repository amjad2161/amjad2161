from __future__ import annotations

import pytest

from singularity.kernel.contracts import Domain, OrganError
from singularity.kernel.ecosystem import ECOSYSTEM, organ_ids
from singularity.kernel.registry import build_default_registry


def test_default_registry_has_eight_organs():
    registry = build_default_registry(force_mock=True)
    assert len(registry) == 8
    assert set(organ_ids()) == {o.id for o in registry}


def test_every_intent_is_unique_and_routable():
    registry = build_default_registry(force_mock=True)
    intents = registry.intents()
    # No collisions: index size equals total capability count.
    assert len(intents) == len(registry.capabilities())
    for intent, organ_id in intents.items():
        assert registry.organ_for_intent(intent).id == organ_id


def test_by_domain_covers_all_domains():
    registry = build_default_registry(force_mock=True)
    for domain in Domain:
        assert registry.by_domain(domain), f"no organ for {domain}"


def test_unknown_lookups_raise():
    registry = build_default_registry(force_mock=True)
    with pytest.raises(OrganError):
        registry.get("nope")
    with pytest.raises(OrganError):
        registry.organ_for_intent("nope.nope")


def test_every_repo_maps_to_a_real_organ():
    registry = build_default_registry(force_mock=True)
    organ_set = {o.id for o in registry}
    for spec in ECOSYSTEM:
        assert spec.organ in organ_set, f"{spec.repo} → unknown organ {spec.organ}"
    assert len(ECOSYSTEM) == 17
