"""Medical triage and dosing protocols."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DoseResult:
    medication: str
    recommended_mg: float
    actual_dose_mg: float
    clamped: bool


class MedicalProtocols:
    def triage(self, *, heart_rate: float, systolic_bp: float, spo2: float) -> str:
        if heart_rate <= 0 or systolic_bp <= 0 or spo2 <= 0:
            return "BLACK"
        if spo2 < 85 or systolic_bp < 80 or heart_rate > 180:
            return "RED"
        if spo2 < 92 or systolic_bp < 95 or heart_rate > 130:
            return "YELLOW"
        return "GREEN"

    def calculate_dose(
        self,
        *,
        medication: str,
        weight_kg: float,
        mg_per_kg: float,
        min_mg: float = 0.0,
        max_mg: float | None = None,
    ) -> dict[str, Any]:
        if weight_kg <= 0:
            raise ValueError("weight_kg must be positive")
        if mg_per_kg <= 0:
            raise ValueError("mg_per_kg must be positive")
        recommended = weight_kg * mg_per_kg
        actual = max(min_mg, recommended)
        if max_mg is not None:
            actual = min(actual, max_mg)
        return DoseResult(
            medication=medication,
            recommended_mg=round(recommended, 3),
            actual_dose_mg=round(actual, 3),
            clamped=abs(actual - recommended) > 1e-9,
        ).__dict__

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "navigation_role": "medical_support",
            "capabilities": ["triage", "dose_calculation"],
            "metrics": {},
            "version": "2.1.0",
        }
