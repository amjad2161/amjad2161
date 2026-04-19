"""Medical protocol helpers and dosage calculation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DrugRoute(str, Enum):
    ORAL = "oral"
    IV = "iv"
    IM = "im"
    TOPICAL = "topical"


@dataclass(frozen=True)
class DrugInfo:
    name: str
    mg_per_kg: float
    max_single_dose_mg: float
    route: DrugRoute


class MedicalProtocols:
    _DRUGS: dict[str, DrugInfo] = {
        "epinephrine": DrugInfo("epinephrine", mg_per_kg=0.01, max_single_dose_mg=1.0, route=DrugRoute.IV),
        "acetaminophen": DrugInfo("acetaminophen", mg_per_kg=15.0, max_single_dose_mg=1000.0, route=DrugRoute.ORAL),
        "ibuprofen": DrugInfo("ibuprofen", mg_per_kg=10.0, max_single_dose_mg=800.0, route=DrugRoute.ORAL),
    }

    def list_drugs(self) -> list[str]:
        return sorted(self._DRUGS.keys())

    def get_drug_info(self, drug_name: str) -> dict[str, Any]:
        key = drug_name.lower().strip()
        info = self._DRUGS.get(key)
        if not info:
            raise KeyError(f"Unknown drug: {drug_name}")
        return {
            "name": info.name,
            "mg_per_kg": info.mg_per_kg,
            "max_single_dose_mg": info.max_single_dose_mg,
            "route": info.route.value,
        }

    def calculate_dose(self, drug_name: str, weight_kg: float) -> dict[str, Any]:
        if weight_kg <= 0:
            raise ValueError("weight_kg must be > 0")
        key = drug_name.lower().strip()
        info = self._DRUGS.get(key)
        if not info:
            raise KeyError(f"Unknown drug: {drug_name}")
        dose = min(info.mg_per_kg * weight_kg, info.max_single_dose_mg)
        return {"drug": info.name, "weight_kg": weight_kg, "dose_mg": round(dose, 2), "route": info.route.value}


__all__ = ["MedicalProtocols", "DrugRoute", "DrugInfo"]
