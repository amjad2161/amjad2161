"""The organ registry: instantiates and indexes every organ.

Indexes organs by id, by domain and — crucially — by *intent*, so the kernel
can route ``"neuro.think"`` to whichever organ advertises that capability
without hard-coding any wiring.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from .contracts import Capability, Domain, Organ, OrganError, OrganInfo


class OrganRegistry:
    """Holds the living organs and the intent → organ routing table."""

    def __init__(self, organs: Iterable[Organ] = ()) -> None:
        self._by_id: dict[str, Organ] = {}
        self._intent_index: dict[str, str] = {}
        for organ in organs:
            self.register(organ)

    def register(self, organ: Organ) -> None:
        if organ.id in self._by_id:
            raise OrganError(f"duplicate organ id: {organ.id!r}")
        self._by_id[organ.id] = organ
        for capability in organ.describe().capabilities:
            if capability.intent in self._intent_index:
                owner = self._intent_index[capability.intent]
                raise OrganError(
                    f"intent {capability.intent!r} already owned by organ {owner!r}"
                )
            self._intent_index[capability.intent] = organ.id

    # -- lookup -----------------------------------------------------------
    def get(self, organ_id: str) -> Organ:
        try:
            return self._by_id[organ_id]
        except KeyError as exc:
            raise OrganError(f"unknown organ: {organ_id!r}") from exc

    def organ_for_intent(self, intent: str) -> Organ:
        try:
            return self._by_id[self._intent_index[intent]]
        except KeyError as exc:
            raise OrganError(f"no organ handles intent {intent!r}") from exc

    def by_domain(self, domain: Domain) -> list[Organ]:
        return [o for o in self._by_id.values() if o.domain is domain]

    def intents(self) -> dict[str, str]:
        return dict(self._intent_index)

    def capabilities(self) -> list[Capability]:
        caps: list[Capability] = []
        for organ in self._by_id.values():
            caps.extend(organ.describe().capabilities)
        return caps

    def describe_all(self) -> list[OrganInfo]:
        return [o.describe() for o in self._by_id.values()]

    # -- container protocol ----------------------------------------------
    def __iter__(self) -> Iterator[Organ]:
        return iter(self._by_id.values())

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, organ_id: object) -> bool:
        return organ_id in self._by_id


def build_default_registry(
    *, force_mock: bool = False, include_plugins: bool = False
) -> OrganRegistry:
    """Construct the canonical 8-organ federation (+ discovered plugins).

    Imported lazily so the kernel package has no hard dependency cycle and so
    importing :mod:`singularity.kernel` stays cheap.
    """

    from ..organs.agents import AgentsOrgan
    from ..organs.control import ControlOrgan
    from ..organs.knowledge import KnowledgeOrgan
    from ..organs.net import NetOrgan
    from ..organs.neuro import NeuroOrgan
    from ..organs.nexus import NexusOrgan
    from ..organs.sky import SkyOrgan
    from ..organs.trade import TradeOrgan
    from ..organs.vision import VisionOrgan

    organ_types = (
        NeuroOrgan,
        AgentsOrgan,
        KnowledgeOrgan,
        SkyOrgan,
        TradeOrgan,
        VisionOrgan,
        NexusOrgan,
        NetOrgan,
        ControlOrgan,
    )
    registry = OrganRegistry(cls(force_mock=force_mock) for cls in organ_types)
    if include_plugins:
        from .plugins import discover_plugin_organs

        for organ in discover_plugin_organs():
            try:
                registry.register(organ)
            except OrganError:
                continue  # skip duplicate ids / intent collisions defensively
    return registry
