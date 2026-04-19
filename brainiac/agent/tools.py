"""Tool registry for agent use."""
from __future__ import annotations

from typing import Any, Callable

from brainiac.core.medical_protocols import MedicalProtocols


def build_default_tools(medical_protocols: MedicalProtocols | None = None) -> dict[str, Callable[..., Any]]:
    med = medical_protocols or MedicalProtocols()
    return {
        "medical.list_drugs": med.list_drugs,
        "medical.get_drug_info": med.get_drug_info,
        "medical.calculate_dose": med.calculate_dose,
    }


__all__ = ["build_default_tools"]
