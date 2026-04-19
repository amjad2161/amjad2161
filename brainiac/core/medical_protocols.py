"""
GANE MEDICAL PROTOCOLS — Ministry of Health SOP Engine
=======================================================
Encodes clinical decision support, drug reference data, emergency protocols,
and Ministry of Health standard operating procedures for field-deployable
medical AI.

This is NOT clinical decision-making software — it's an educational and
reference engine that helps trained medical professionals access protocols
rapidly in time-critical situations.

DISCLAIMER: All outputs must be verified by a licensed medical professional.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProtocolCategory(str, Enum):
    ACLS = "acls"
    BLS = "bls"
    PALS = "pals"
    TRAUMA = "trauma"
    STROKE = "stroke"
    STEMI = "stemi"
    TOXICOLOGY = "toxicology"
    AIRWAY = "airway"
    OBSTETRIC = "obstetric"


class Urgency(str, Enum):
    IMMEDIATE = "immediate"
    URGENT = "urgent"
    DELAYED = "delayed"
    EXPECTANT = "expectant"


class DrugRoute(str, Enum):
    IV = "IV"
    IO = "IO"
    IM = "IM"
    PO = "PO"
    SL = "SL"      # sublingual
    ETT = "ETT"    # endotracheal
    IN = "IN"      # intranasal
    SC = "SC"      # subcutaneous
    RECTAL = "PR"
    TOPICAL = "TOPICAL"


@dataclass
class DrugDose:
    drug: str
    dose_mg_per_kg: float
    max_dose_mg: float
    routes: list[DrugRoute]
    frequency: str = ""
    notes: str = ""
    aha_reference: str = "AHA 2020 Guidelines"


@dataclass
class ProtocolStep:
    step_number: int
    action: str
    duration_s: int | None = None
    critical: bool = False
    notes: str = ""


@dataclass
class ClinicalProtocol:
    name: str
    category: ProtocolCategory
    urgency: Urgency
    steps: list[ProtocolStep]
    drugs: list[DrugDose] = field(default_factory=list)
    contraindications: list[str] = field(default_factory=list)
    reference: str = ""
    last_updated: str = "2024-01"


@dataclass
class TriageResult:
    category: Urgency
    score: int
    rationale: str
    recommended_protocol: str
    timestamp: float = field(default_factory=time.time)


# ── Drug Reference Database ─────────────────────────────────────────────────

DRUG_DATABASE: dict[str, DrugDose] = {
    "epinephrine": DrugDose(
        drug="Epinephrine",
        dose_mg_per_kg=0.01,
        max_dose_mg=1.0,
        routes=[DrugRoute.IV, DrugRoute.IO],
        frequency="Every 3-5 minutes",
        notes="Cardiac arrest: 1mg IV/IO. Anaphylaxis: 0.3-0.5mg IM.",
        aha_reference="AHA 2020 ACLS",
    ),
    "amiodarone": DrugDose(
        drug="Amiodarone",
        dose_mg_per_kg=5.0,
        max_dose_mg=300.0,
        routes=[DrugRoute.IV],
        frequency="First dose 300mg, second dose 150mg",
        notes="For refractory VF/pVT after 3rd shock.",
        aha_reference="AHA 2020 ACLS",
    ),
    "atropine": DrugDose(
        drug="Atropine",
        dose_mg_per_kg=0.02,
        max_dose_mg=3.0,
        routes=[DrugRoute.IV, DrugRoute.IO],
        frequency="Every 3-5 minutes",
        notes="Symptomatic bradycardia only. 0.5mg per dose.",
        aha_reference="AHA 2020 ACLS",
    ),
    "adenosine": DrugDose(
        drug="Adenosine",
        dose_mg_per_kg=0.1,
        max_dose_mg=12.0,
        routes=[DrugRoute.IV],
        frequency="First dose 6mg, then 12mg",
        notes="Rapid IV push with immediate flush. SVT only.",
        aha_reference="AHA 2020 ACLS",
    ),
    "lidocaine": DrugDose(
        drug="Lidocaine",
        dose_mg_per_kg=1.0,
        max_dose_mg=100.0,
        routes=[DrugRoute.IV, DrugRoute.IO],
        frequency="May repeat 0.5-0.75 mg/kg every 5-10 min",
        notes="Alternative to amiodarone for VF/pVT.",
        aha_reference="AHA 2020 ACLS",
    ),
    "naloxone": DrugDose(
        drug="Naloxone",
        dose_mg_per_kg=0.1,
        max_dose_mg=2.0,
        routes=[DrugRoute.IV, DrugRoute.IM, DrugRoute.IN],
        frequency="May repeat every 2-3 minutes",
        notes="Opioid reversal. Start with 0.4mg, titrate to effect.",
        aha_reference="AHA 2020",
    ),
    "aspirin": DrugDose(
        drug="Aspirin",
        dose_mg_per_kg=5.0,
        max_dose_mg=325.0,
        routes=[DrugRoute.PO],
        frequency="Single dose, chewed",
        notes="Acute coronary syndrome. 162-325mg chewed.",
        aha_reference="AHA 2020 ACS",
    ),
    "nitroglycerin": DrugDose(
        drug="Nitroglycerin",
        dose_mg_per_kg=0.0,
        max_dose_mg=0.4,
        routes=[DrugRoute.SL],
        frequency="Every 5 minutes, max 3 doses",
        notes="Chest pain / ACS. Contraindicated if systolic BP < 90mmHg or recent PDE5 inhibitor.",
        aha_reference="AHA 2020 ACS",
    ),
}


# ── Clinical Protocol Library ────────────────────────────────────────────────

PROTOCOL_LIBRARY: dict[str, ClinicalProtocol] = {
    "acls_cardiac_arrest": ClinicalProtocol(
        name="ACLS Cardiac Arrest Algorithm",
        category=ProtocolCategory.ACLS,
        urgency=Urgency.IMMEDIATE,
        reference="AHA 2020 ACLS Guidelines, Section 4",
        steps=[
            ProtocolStep(1, "Start high-quality CPR (30:2 or continuous if advanced airway)", critical=True),
            ProtocolStep(2, "Attach defibrillator / monitor", duration_s=30),
            ProtocolStep(3, "Check rhythm — shockable (VF/pVT)?", critical=True),
            ProtocolStep(4, "If shockable: Defibrillate 120-200J biphasic", critical=True),
            ProtocolStep(5, "Resume CPR immediately for 2 minutes", duration_s=120, critical=True),
            ProtocolStep(6, "Establish IV/IO access"),
            ProtocolStep(7, "Epinephrine 1mg IV/IO every 3-5 minutes", critical=True),
            ProtocolStep(8, "If refractory VF/pVT: Amiodarone 300mg IV (then 150mg)"),
            ProtocolStep(9, "Consider advanced airway (ETT or SGA)"),
            ProtocolStep(10, "Identify and treat reversible causes (5H's and 5T's)", critical=True,
                         notes="Hypovolemia, Hypoxia, Hydrogen ion, Hypo/Hyperkalemia, Hypothermia, "
                               "Tension pneumothorax, Tamponade, Toxins, Thrombosis (PE), Thrombosis (MI)"),
        ],
        drugs=[DRUG_DATABASE["epinephrine"], DRUG_DATABASE["amiodarone"]],
    ),
    "bls_adult": ClinicalProtocol(
        name="BLS Adult Algorithm",
        category=ProtocolCategory.BLS,
        urgency=Urgency.IMMEDIATE,
        reference="AHA 2020 BLS Guidelines",
        steps=[
            ProtocolStep(1, "Verify scene safety"),
            ProtocolStep(2, "Check responsiveness — tap shoulders, shout", duration_s=10),
            ProtocolStep(3, "Activate emergency response / call for AED"),
            ProtocolStep(4, "Check breathing and pulse simultaneously (no more than 10 seconds)", duration_s=10, critical=True),
            ProtocolStep(5, "Begin CPR: 30 compressions, 2 breaths. Rate 100-120/min, depth 5-6cm", critical=True),
            ProtocolStep(6, "AED arrives: Apply pads, analyze rhythm"),
            ProtocolStep(7, "Shock advised: Clear and deliver shock, resume CPR immediately", critical=True),
            ProtocolStep(8, "No shock: Resume CPR for 2 minutes, then re-analyze", duration_s=120),
        ],
    ),
    "stroke_code": ClinicalProtocol(
        name="Acute Stroke Protocol",
        category=ProtocolCategory.STROKE,
        urgency=Urgency.IMMEDIATE,
        reference="AHA/ASA 2019 Acute Ischemic Stroke Guidelines",
        steps=[
            ProtocolStep(1, "Activate stroke team — time is brain", critical=True),
            ProtocolStep(2, "Obtain NIHSS score"),
            ProtocolStep(3, "Non-contrast CT head — within 20 minutes of arrival", duration_s=1200, critical=True),
            ProtocolStep(4, "If no hemorrhage: assess tPA eligibility (within 4.5 hours of symptom onset)", critical=True),
            ProtocolStep(5, "Labs: glucose, coagulation, CBC, troponin, type & screen"),
            ProtocolStep(6, "If eligible: Alteplase 0.9 mg/kg IV (max 90mg). 10% bolus, 90% over 60 min.", critical=True),
            ProtocolStep(7, "Monitor BP: maintain < 185/110 pre-tPA, < 180/105 post-tPA"),
            ProtocolStep(8, "Consider thrombectomy if large vessel occlusion (within 24h window)"),
        ],
        contraindications=[
            "Active internal bleeding",
            "Intracranial hemorrhage on CT",
            "Platelet count < 100,000",
            "INR > 1.7 or PT > 15 seconds",
            "Recent major surgery (< 14 days)",
        ],
    ),
    "stemi_protocol": ClinicalProtocol(
        name="STEMI Protocol",
        category=ProtocolCategory.STEMI,
        urgency=Urgency.IMMEDIATE,
        reference="AHA 2020 ACS Guidelines",
        steps=[
            ProtocolStep(1, "12-lead ECG — within 10 minutes", duration_s=600, critical=True),
            ProtocolStep(2, "Aspirin 162-325mg chewed", critical=True),
            ProtocolStep(3, "Nitroglycerin 0.4mg SL every 5 min (if SBP > 90)", notes="Max 3 doses"),
            ProtocolStep(4, "Activate cardiac cath lab — door-to-balloon < 90 min", critical=True),
            ProtocolStep(5, "Heparin per protocol"),
            ProtocolStep(6, "Morphine 2-4mg IV only if refractory pain"),
            ProtocolStep(7, "Monitor for arrhythmias — defibrillator at bedside"),
        ],
        drugs=[DRUG_DATABASE["aspirin"], DRUG_DATABASE["nitroglycerin"]],
        contraindications=["Nitroglycerin: SBP < 90, RV infarct, recent PDE5 inhibitor"],
    ),
}


class MedicalProtocols:
    """
    Field-deployable medical protocol engine.

    Provides protocol lookup, drug dose calculations, triage scoring,
    and structured emergency reference data.
    """

    def __init__(self) -> None:
        self._access_log: list[dict] = []

    def get_protocol(self, name: str) -> ClinicalProtocol | None:
        proto = PROTOCOL_LIBRARY.get(name)
        if proto:
            self._access_log.append({"protocol": name, "ts": time.time()})
        return proto

    def list_protocols(self, category: ProtocolCategory | None = None) -> list[str]:
        if category is None:
            return list(PROTOCOL_LIBRARY.keys())
        return [k for k, v in PROTOCOL_LIBRARY.items() if v.category == category]

    def calculate_dose(
        self,
        drug_name: str,
        weight_kg: float,
        route: DrugRoute | None = None,
    ) -> dict[str, Any]:
        """
        Calculate weight-based dosing for a drug.

        Returns calculated dose clamped to max, with safety disclaimer.
        """
        drug = DRUG_DATABASE.get(drug_name.lower())
        if not drug:
            return {"error": f"Drug '{drug_name}' not found in database"}

        if weight_kg <= 0 or weight_kg > 500:
            return {"error": f"Invalid weight: {weight_kg} kg"}

        calculated = drug.dose_mg_per_kg * weight_kg
        actual = min(calculated, drug.max_dose_mg) if drug.max_dose_mg > 0 else calculated
        selected_route = route or drug.routes[0]

        return {
            "drug": drug.drug,
            "weight_kg": weight_kg,
            "calculated_mg": round(calculated, 2),
            "actual_dose_mg": round(actual, 2),
            "max_dose_mg": drug.max_dose_mg,
            "clamped": calculated > drug.max_dose_mg and drug.max_dose_mg > 0,
            "route": selected_route.value,
            "available_routes": [r.value for r in drug.routes],
            "frequency": drug.frequency,
            "notes": drug.notes,
            "reference": drug.aha_reference,
            "disclaimer": "EDUCATIONAL REFERENCE ONLY — VERIFY WITH LICENSED PHARMACIST/PHYSICIAN",
        }

    def triage(
        self,
        heart_rate: int,
        respiratory_rate: int,
        systolic_bp: int,
        gcs: int,
        spo2: int = 98,
        temperature_c: float = 37.0,
    ) -> TriageResult:
        """
        Simple field triage scoring based on vital signs.

        Uses a weighted score to classify urgency and recommend a protocol.
        Higher score = more critical.
        """
        score = 0
        reasons = []

        # Heart rate
        if heart_rate > 150 or heart_rate < 40:
            score += 4
            reasons.append(f"Critical HR: {heart_rate}")
        elif heart_rate > 120 or heart_rate < 50:
            score += 2
            reasons.append(f"Abnormal HR: {heart_rate}")

        # Respiratory rate
        if respiratory_rate > 30 or respiratory_rate < 8:
            score += 4
            reasons.append(f"Critical RR: {respiratory_rate}")
        elif respiratory_rate > 22 or respiratory_rate < 10:
            score += 2
            reasons.append(f"Abnormal RR: {respiratory_rate}")

        # Systolic BP
        if systolic_bp < 70:
            score += 4
            reasons.append(f"Severe hypotension: SBP {systolic_bp}")
        elif systolic_bp < 90:
            score += 3
            reasons.append(f"Hypotension: SBP {systolic_bp}")
        elif systolic_bp > 200:
            score += 3
            reasons.append(f"Hypertensive crisis: SBP {systolic_bp}")

        # GCS
        if gcs <= 8:
            score += 4
            reasons.append(f"Severe neuro: GCS {gcs}")
        elif gcs <= 12:
            score += 2
            reasons.append(f"Moderate neuro: GCS {gcs}")

        # SpO2
        if spo2 < 85:
            score += 4
            reasons.append(f"Severe hypoxia: SpO2 {spo2}%")
        elif spo2 < 92:
            score += 2
            reasons.append(f"Hypoxia: SpO2 {spo2}%")

        # Temperature
        if temperature_c > 40.0 or temperature_c < 34.0:
            score += 2
            reasons.append(f"Temperature: {temperature_c}°C")

        # Classify
        if score >= 8:
            category = Urgency.IMMEDIATE
            protocol = "acls_cardiac_arrest"
        elif score >= 4:
            category = Urgency.URGENT
            protocol = "bls_adult"
        elif score >= 2:
            category = Urgency.DELAYED
            protocol = "bls_adult"
        else:
            category = Urgency.EXPECTANT
            protocol = ""

        return TriageResult(
            category=category,
            score=score,
            rationale="; ".join(reasons) if reasons else "Vitals within normal limits",
            recommended_protocol=protocol,
        )

    def get_drug_info(self, drug_name: str) -> dict[str, Any] | None:
        drug = DRUG_DATABASE.get(drug_name.lower())
        if not drug:
            return None
        return {
            "drug": drug.drug,
            "dose_mg_per_kg": drug.dose_mg_per_kg,
            "max_dose_mg": drug.max_dose_mg,
            "routes": [r.value for r in drug.routes],
            "frequency": drug.frequency,
            "notes": drug.notes,
            "reference": drug.aha_reference,
        }

    def list_drugs(self) -> list[str]:
        return list(DRUG_DATABASE.keys())

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "navigation_role": "emergency_evacuation_intelligence",
            "capabilities": ["triage_scoring", "dose_calculation", "protocol_lookup", "enroute_medical"],
            "protocols": len(PROTOCOL_LIBRARY),
            "drugs": len(DRUG_DATABASE),
            "categories": [c.value for c in ProtocolCategory],
            "access_log_size": len(self._access_log),
        }
