"""Tests for the GANE Medical Protocols Engine."""
import pytest

from brainiac.core.medical_protocols import (
    MedicalProtocols, ProtocolCategory, Urgency, DrugRoute,
    DRUG_DATABASE, PROTOCOL_LIBRARY,
)


@pytest.fixture
def med():
    return MedicalProtocols()


# ── Protocol Lookup ──────────────────────────────────────────────────────────

def test_list_all_protocols(med):
    names = med.list_protocols()
    assert len(names) >= 4
    assert "acls_cardiac_arrest" in names
    assert "bls_adult" in names


def test_list_protocols_by_category(med):
    acls = med.list_protocols(ProtocolCategory.ACLS)
    assert "acls_cardiac_arrest" in acls
    for name in acls:
        assert PROTOCOL_LIBRARY[name].category == ProtocolCategory.ACLS


def test_get_known_protocol(med):
    proto = med.get_protocol("acls_cardiac_arrest")
    assert proto is not None
    assert proto.name == "ACLS Cardiac Arrest Algorithm"
    assert proto.urgency == Urgency.IMMEDIATE
    assert len(proto.steps) >= 10
    assert any(s.critical for s in proto.steps)


def test_get_unknown_protocol(med):
    assert med.get_protocol("nonexistent") is None


def test_protocol_has_drugs(med):
    proto = med.get_protocol("acls_cardiac_arrest")
    assert len(proto.drugs) >= 2
    drug_names = [d.drug for d in proto.drugs]
    assert "Epinephrine" in drug_names


def test_stroke_protocol_has_contraindications(med):
    proto = med.get_protocol("stroke_code")
    assert len(proto.contraindications) >= 3


def test_stemi_protocol(med):
    proto = med.get_protocol("stemi_protocol")
    assert proto.category == ProtocolCategory.STEMI
    assert any("Aspirin" in d.drug for d in proto.drugs)


# ── Drug Dose Calculation ────────────────────────────────────────────────────

def test_calculate_epinephrine_dose(med):
    result = med.calculate_dose("epinephrine", weight_kg=80.0)
    assert result["drug"] == "Epinephrine"
    assert result["calculated_mg"] == pytest.approx(0.8)
    assert result["actual_dose_mg"] == pytest.approx(0.8)
    assert result["clamped"] is False
    assert "VERIFY" in result["disclaimer"]


def test_dose_clamped_at_max(med):
    result = med.calculate_dose("epinephrine", weight_kg=200.0)
    assert result["clamped"] is True
    assert result["actual_dose_mg"] == 1.0


def test_dose_unknown_drug(med):
    result = med.calculate_dose("unobtanium", weight_kg=70.0)
    assert "error" in result


def test_dose_invalid_weight(med):
    result = med.calculate_dose("epinephrine", weight_kg=0)
    assert "error" in result
    result2 = med.calculate_dose("epinephrine", weight_kg=600)
    assert "error" in result2


def test_dose_with_specific_route(med):
    result = med.calculate_dose("epinephrine", weight_kg=70.0, route=DrugRoute.IO)
    assert result["route"] == "IO"


def test_amiodarone_dose(med):
    result = med.calculate_dose("amiodarone", weight_kg=80.0)
    assert result["actual_dose_mg"] == 300.0
    assert result["clamped"] is True


def test_adenosine_dose(med):
    result = med.calculate_dose("adenosine", weight_kg=70.0)
    assert result["actual_dose_mg"] <= 12.0


# ── Triage Scoring ───────────────────────────────────────────────────────────

def test_triage_normal_vitals(med):
    result = med.triage(
        heart_rate=72, respiratory_rate=16,
        systolic_bp=120, gcs=15, spo2=98,
    )
    assert result.category == Urgency.EXPECTANT
    assert result.score == 0
    assert result.recommended_protocol == ""


def test_triage_cardiac_arrest(med):
    result = med.triage(
        heart_rate=0, respiratory_rate=0,
        systolic_bp=0, gcs=3, spo2=0,
    )
    assert result.category == Urgency.IMMEDIATE
    assert result.score >= 8
    assert result.recommended_protocol == "acls_cardiac_arrest"


def test_triage_moderate_concern(med):
    result = med.triage(
        heart_rate=130, respiratory_rate=24,
        systolic_bp=95, gcs=14, spo2=94,
    )
    assert result.category in (Urgency.URGENT, Urgency.DELAYED)
    assert result.score >= 2


def test_triage_severe_hypotension(med):
    result = med.triage(
        heart_rate=110, respiratory_rate=22,
        systolic_bp=60, gcs=10, spo2=88,
    )
    assert result.category == Urgency.IMMEDIATE
    assert "hypotension" in result.rationale.lower() or "SBP" in result.rationale


def test_triage_hypothermia(med):
    result = med.triage(
        heart_rate=50, respiratory_rate=10,
        systolic_bp=110, gcs=14, spo2=96,
        temperature_c=33.0,
    )
    assert result.score >= 2
    assert "Temperature" in result.rationale or "temp" in result.rationale.lower()


# ── Drug Reference ───────────────────────────────────────────────────────────

def test_list_drugs(med):
    drugs = med.list_drugs()
    assert "epinephrine" in drugs
    assert "amiodarone" in drugs
    assert "naloxone" in drugs
    assert len(drugs) >= 8


def test_get_drug_info(med):
    info = med.get_drug_info("naloxone")
    assert info is not None
    assert info["drug"] == "Naloxone"
    assert "IN" in info["routes"]


def test_get_unknown_drug_info(med):
    assert med.get_drug_info("fakemed") is None


# ── Diagnostics ──────────────────────────────────────────────────────────────

def test_diagnostics(med):
    d = med.diagnostics()
    assert d["status"] == "ONLINE"
    assert d["protocols"] >= 4
    assert d["drugs"] >= 8


def test_access_log_populated(med):
    med.get_protocol("acls_cardiac_arrest")
    med.get_protocol("bls_adult")
    d = med.diagnostics()
    assert d["access_log_size"] == 2
