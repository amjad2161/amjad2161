"""Localization abstraction combining GNSS + INS."""
from __future__ import annotations

from typing import Any

from .ins import INS
from .orbital_nav import Coordinate, OrbitalNav


class Localization:
    def __init__(self, nav: OrbitalNav | None = None, ins: INS | None = None) -> None:
        self.nav = nav or OrbitalNav()
        self.ins = ins or INS()

    async def position(self) -> Coordinate:
        return await self.nav.get_position()

    def diagnostics(self) -> dict[str, Any]:
        return {"status": "ONLINE", "nav": self.nav.diagnostics(), "ins": self.ins.diagnostics()}


__all__ = ["Localization"]
