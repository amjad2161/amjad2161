from __future__ import annotations

import asyncio

from singularity.kernel.plugins import load_spec_organs
from singularity.kernel.registry import build_default_registry


def test_load_spec_organs_imports_real_organ():
    organs = load_spec_organs(["singularity.organs.net:NetOrgan"])
    assert len(organs) == 1
    assert organs[0].id == "net"


def test_load_spec_ignores_bad_specs():
    organs = load_spec_organs(["", "no-colon", "nonexistent.module:Thing",
                               "singularity.organs.sky:DoesNotExist"])
    assert organs == []


def test_env_discovery(monkeypatch):
    monkeypatch.setenv("SINGULARITY_PLUGINS", "singularity.organs.net:NetOrgan")
    from singularity.kernel.plugins import discover_plugin_organs

    organs = discover_plugin_organs()
    assert any(o.id == "net" for o in organs)


def test_plugin_organ_registers_and_routes():
    # A custom organ registered into a registry becomes routable like any other.
    from singularity.organs.base import BaseOrgan
    from singularity.kernel.contracts import Capability, Domain
    from singularity import Singularity

    class EchoOrgan(BaseOrgan):
        id = "echo"
        domain = Domain.KNOWLEDGE
        title = "Echo"
        capabilities = (Capability("echo.say", "Echo a message", {"text": "str"}),)

        async def _invoke(self, intent, payload):
            return {"echo": payload.get("text", "")}

    registry = build_default_registry(force_mock=True)
    registry.register(EchoOrgan(force_mock=True))

    async def run():
        kernel = Singularity(registry)
        await kernel.boot()
        out = await kernel.route("echo.say", {"text": "hi"})
        await kernel.shutdown()
        return out

    assert asyncio.run(run())["echo"] == "hi"
