import pytest

from brainiac.core.medical_protocols import MedicalProtocols


def test_triage_boundary_cases():
    med = MedicalProtocols()
    assert med.triage(heart_rate=70, systolic_bp=120, spo2=98) == "GREEN"
    assert med.triage(heart_rate=140, systolic_bp=100, spo2=90) == "YELLOW"
    assert med.triage(heart_rate=190, systolic_bp=70, spo2=80) == "RED"
    assert med.triage(heart_rate=0, systolic_bp=0, spo2=0) == "BLACK"


def test_calculate_dose_clamp_and_errors():
    med = MedicalProtocols()
    result = med.calculate_dose(medication="x", weight_kg=10, mg_per_kg=5, min_mg=60, max_mg=80)
    assert result["actual_dose_mg"] == 60
    assert result["clamped"] is True
    with pytest.raises(ValueError):
        med.calculate_dose(medication="x", weight_kg=0, mg_per_kg=1)
