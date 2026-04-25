"""Tests for QUANTUM-MIND module."""

from __future__ import annotations

import pytest

from brainiac.core.quantum_mind import (
    CollapseStrategy,
    QuantumMind,
    TimelineStatus,
)


@pytest.fixture
def qm() -> QuantumMind:
    return QuantumMind()


_SCENARIOS = [
    {
        "description": "Launch product A",
        "probability": 0.6,
        "utility": 0.9,
        "risk": 0.1,
        "tags": ["fast"],
    },
    {
        "description": "Launch product B",
        "probability": 0.3,
        "utility": 0.7,
        "risk": 0.3,
        "tags": ["safe"],
    },
    {
        "description": "Delay all launches",
        "probability": 0.1,
        "utility": 0.2,
        "risk": 0.05,
        "tags": ["safe"],
    },
]


# ── Superposition ──────────────────────────────────────────────────────────────


def test_superpose_creates_superposition(qm: QuantumMind) -> None:
    sup = qm.superpose("What should we do?", _SCENARIOS)
    assert sup.superposition_id
    assert len(sup.scenarios) == 3
    assert not sup.collapsed


def test_superpose_normalises_probabilities(qm: QuantumMind) -> None:
    sup = qm.superpose("test", _SCENARIOS)
    assert abs(sup.total_probability - 1.0) < 1e-9


def test_entropy_between_zero_and_log2_n(qm: QuantumMind) -> None:
    sup = qm.superpose("entropy test", _SCENARIOS)
    h = qm.entropy(sup.superposition_id)
    import math

    assert 0.0 <= h <= math.log2(len(_SCENARIOS)) + 1e-6


# ── Collapse ───────────────────────────────────────────────────────────────────


def test_collapse_max_expected_value(qm: QuantumMind) -> None:
    sup = qm.superpose("collapse test", _SCENARIOS, CollapseStrategy.MAX_EXPECTED_VALUE)
    chosen = qm.collapse(sup.superposition_id)
    # All scenarios have positive utility and positive probability — chosen must be valid
    assert chosen.description in {s["description"] for s in _SCENARIOS}


def test_collapse_max_probability(qm: QuantumMind) -> None:
    sup = qm.superpose("prob test", _SCENARIOS, CollapseStrategy.MAX_PROBABILITY)
    chosen = qm.collapse(sup.superposition_id)
    # Highest raw prob after normalisation should be the first scenario
    assert chosen.description == "Launch product A"


def test_collapse_min_risk(qm: QuantumMind) -> None:
    sup = qm.superpose("risk test", _SCENARIOS, CollapseStrategy.MIN_RISK)
    chosen = qm.collapse(sup.superposition_id)
    risks = [0.1, 0.3, 0.05]  # same order as _SCENARIOS
    assert chosen.risk == min(risks)


def test_collapse_marks_superposition_as_collapsed(qm: QuantumMind) -> None:
    sup = qm.superpose("q", _SCENARIOS)
    qm.collapse(sup.superposition_id)
    assert sup.collapsed is True
    assert sup.chosen is not None


def test_collapse_idempotent(qm: QuantumMind) -> None:
    sup = qm.superpose("q", _SCENARIOS)
    c1 = qm.collapse(sup.superposition_id)
    c2 = qm.collapse(sup.superposition_id)
    assert c1.scenario_id == c2.scenario_id


def test_collapse_unknown_id_raises(qm: QuantumMind) -> None:
    with pytest.raises(KeyError):
        qm.collapse("nonexistent-id")


# ── Interference ──────────────────────────────────────────────────────────────


def test_interference_amplify(qm: QuantumMind) -> None:
    sup = qm.superpose("interfere", _SCENARIOS)
    fast_before = next(s.probability for s in sup.scenarios if "fast" in s.tags)
    qm.interfere(sup.superposition_id, amplify_tags=["fast"])
    fast_after = next(s.probability for s in sup.scenarios if "fast" in s.tags)
    assert fast_after > fast_before


def test_interference_on_collapsed_raises(qm: QuantumMind) -> None:
    sup = qm.superpose("q", _SCENARIOS)
    qm.collapse(sup.superposition_id)
    with pytest.raises(ValueError):
        qm.interfere(sup.superposition_id, amplify_tags=["fast"])


# ── Decision Matrix ────────────────────────────────────────────────────────────


def test_decision_matrix_ranks_options(qm: QuantumMind) -> None:
    dm = qm.decision_matrix(
        options=["Option A", "Option B", "Option C"],
        criteria=["cost", "speed", "quality"],
        scores={
            "Option A": {"cost": 0.9, "speed": 0.5, "quality": 0.7},
            "Option B": {"cost": 0.4, "speed": 0.9, "quality": 0.6},
            "Option C": {"cost": 0.6, "speed": 0.6, "quality": 0.9},
        },
        weights=[0.3, 0.3, 0.4],
    )
    assert len(dm.ranked) == 3
    # Scores must be in descending order
    scores = [sc for _, sc in dm.ranked]
    assert scores == sorted(scores, reverse=True)


def test_decision_matrix_equal_weights(qm: QuantumMind) -> None:
    dm = qm.decision_matrix(
        options=["X", "Y"],
        criteria=["a", "b"],
        scores={"X": {"a": 1.0, "b": 1.0}, "Y": {"a": 0.0, "b": 0.0}},
    )
    assert dm.ranked[0][0] == "X"


# ── Prediction ────────────────────────────────────────────────────────────────


def test_predict_returns_correct_horizon(qm: QuantumMind) -> None:
    pred = qm.predict("temperature", [20.0, 21.0, 20.5, 22.0], horizon=5)
    assert len(pred.values) == 5
    assert len(pred.lower_bound) == 5
    assert len(pred.upper_bound) == 5


def test_predict_bounds_contain_forecast(qm: QuantumMind) -> None:
    pred = qm.predict("metric", [10.0, 10.5, 11.0, 10.8, 11.2], horizon=3)
    for i in range(3):
        assert pred.lower_bound[i] <= pred.values[i] <= pred.upper_bound[i]


def test_predict_insufficient_data_raises(qm: QuantumMind) -> None:
    with pytest.raises(ValueError):
        qm.predict("v", [42.0], horizon=5)


# ── Divergence ────────────────────────────────────────────────────────────────


def test_detect_divergence_superposed(qm: QuantumMind) -> None:
    sup = qm.superpose("div test", _SCENARIOS)
    # All utilities positive → no divergence
    status = qm.detect_divergence(sup.superposition_id)
    assert status == TimelineStatus.SUPERPOSED


def test_detect_divergence_collapsed(qm: QuantumMind) -> None:
    sup = qm.superpose("q", _SCENARIOS)
    qm.collapse(sup.superposition_id)
    assert qm.detect_divergence(sup.superposition_id) == TimelineStatus.COLLAPSED


def test_detect_divergence_detects_conflict(qm: QuantumMind) -> None:
    conflicting = [
        {"description": "Good outcome", "probability": 0.5, "utility": 1.0, "risk": 0.1},
        {"description": "Bad outcome", "probability": 0.5, "utility": -1.0, "risk": 0.9},
    ]
    sup = qm.superpose("conflict", conflicting)
    status = qm.detect_divergence(sup.superposition_id, threshold=0.3)
    assert status == TimelineStatus.DIVERGED


# ── Diagnostics ───────────────────────────────────────────────────────────────


def test_diagnostics(qm: QuantumMind) -> None:
    d = qm.diagnostics()
    assert d["status"] == "ONLINE"
    assert "superpositions" in d
    assert "predictions" in d
    assert "decision_matrices" in d
