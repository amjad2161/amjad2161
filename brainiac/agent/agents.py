from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from brainiac.core.medical_protocols import MedicalProtocols


@dataclass
class AgentManager:
    medical_protocols: MedicalProtocols | None = None

    def _build_medical_tools(self, protocols: MedicalProtocols | None = None) -> dict[str, Any]:
        med = protocols or self.medical_protocols or MedicalProtocols()
        return {"triage": med.triage, "calculate_dose": med.calculate_dose}
