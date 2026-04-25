"""
QUANTUM-MIND — Quantum-Inspired Probabilistic Reasoning Engine
==============================================================
Superpositions of decision paths, multi-universe scenario simulation,
weighted multi-criteria decision analysis, and predictive timeline forecasting.

All computation is classical; the "quantum" framing models uncertainty and
parallel-path exploration as probability amplitudes, mirroring quantum
superposition/interference before wave-function collapse.
"""

from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger("brainiac.quantum_mind")


class CollapseStrategy(str, Enum):
    MAX_PROBABILITY = "max_probability"  # pick highest-probability path
    WEIGHTED_RANDOM = "weighted_random"  # probability-weighted sample
    MIN_RISK = "min_risk"  # minimise worst-case outcome
    MAX_EXPECTED_VALUE = "max_expected_value"  # maximise expected utility


class TimelineStatus(str, Enum):
    SUPERPOSED = "superposed"  # not yet collapsed
    COLLAPSED = "collapsed"  # single path chosen
    DIVERGED = "diverged"  # multiple irreconcilable futures


@dataclass
class Scenario:
    """One possible future branch in a superposition."""

    scenario_id: str
    description: str
    probability: float  # 0..1 — amplitude² of this branch
    utility: float  # subjective utility / reward signal
    risk: float  # 0..1 — worst-case impact if this branch occurs
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def expected_value(self) -> float:
        return self.probability * self.utility

    @property
    def risk_adjusted_value(self) -> float:
        return self.expected_value * (1.0 - self.risk)


@dataclass
class Superposition:
    """A set of scenarios held in quantum superposition awaiting collapse."""

    superposition_id: str
    query: str
    scenarios: list[Scenario]
    created_at: float = field(default_factory=time.time)
    collapsed: bool = False
    chosen: Scenario | None = None
    collapse_strategy: CollapseStrategy = CollapseStrategy.MAX_EXPECTED_VALUE

    @property
    def total_probability(self) -> float:
        return sum(s.probability for s in self.scenarios)

    def normalise(self) -> None:
        """Normalise probabilities so they sum to 1."""
        total = self.total_probability
        if total > 0:
            for s in self.scenarios:
                s.probability /= total


@dataclass
class DecisionMatrix:
    """Weighted multi-criteria decision analysis (MCDM) result."""

    matrix_id: str
    options: list[str]
    criteria: list[str]
    weights: list[float]
    scores: dict[str, dict[str, float]]  # option → criterion → score
    ranked: list[tuple[str, float]]  # (option, composite_score) sorted desc
    created_at: float = field(default_factory=time.time)


@dataclass
class Prediction:
    """A time-series forecast with confidence bounds."""

    prediction_id: str
    variable: str
    horizon_steps: int
    values: list[float]
    lower_bound: list[float]
    upper_bound: list[float]
    confidence: float  # 0..1
    method: str
    created_at: float = field(default_factory=time.time)


class QuantumMind:
    """
    QUANTUM-MIND — probabilistic multi-path reasoning for BRAINIAC.

    Features
    --------
    - Scenario superposition: hold N futures in parallel, collapse to optimal
    - Weighted multi-criteria decision matrix (MCDM / TOPSIS-inspired)
    - Exponential-smoothing trend prediction with confidence intervals
    - Probability amplitude interference (constructive / destructive)
    - Timeline divergence detection
    """

    def __init__(self) -> None:
        self._superpositions: dict[str, Superposition] = {}
        self._matrices: dict[str, DecisionMatrix] = {}
        self._predictions: dict[str, Prediction] = {}
        self._collapses = 0
        log.info("quantum_mind.init")

    # ── Superposition & Collapse ───────────────────────────────────────────────

    def superpose(
        self,
        query: str,
        scenarios: list[dict[str, Any]],
        strategy: CollapseStrategy = CollapseStrategy.MAX_EXPECTED_VALUE,
    ) -> Superposition:
        """
        Create a superposition of scenario branches for a query.

        Each item in ``scenarios`` must contain:
            - ``description`` (str)
            - ``probability`` (float, 0..1)
            - ``utility`` (float)
            - ``risk`` (float, 0..1)
        Optional keys: ``tags`` (list[str]), ``metadata`` (dict).
        """
        built = [
            Scenario(
                scenario_id=uuid.uuid4().hex[:8],
                description=s["description"],
                probability=float(s.get("probability", 1.0 / max(len(scenarios), 1))),
                utility=float(s.get("utility", 0.5)),
                risk=float(s.get("risk", 0.0)),
                tags=s.get("tags", []),
                metadata=s.get("metadata", {}),
            )
            for s in scenarios
        ]
        sup = Superposition(
            superposition_id=uuid.uuid4().hex[:12],
            query=query,
            scenarios=built,
            collapse_strategy=strategy,
        )
        sup.normalise()
        self._superpositions[sup.superposition_id] = sup
        log.info(
            "quantum_mind.superposed",
            id=sup.superposition_id,
            branches=len(built),
        )
        return sup

    def collapse(self, superposition_id: str) -> Scenario:
        """
        Collapse a superposition to a single chosen scenario.
        Uses the strategy defined at superposition creation.
        """
        sup = self._superpositions.get(superposition_id)
        if sup is None:
            raise KeyError(f"Superposition {superposition_id!r} not found")
        if sup.collapsed and sup.chosen is not None:
            return sup.chosen

        sup.collapsed = True
        chosen = self._collapse_by_strategy(sup)
        sup.chosen = chosen
        self._collapses += 1
        log.info(
            "quantum_mind.collapsed",
            id=superposition_id,
            strategy=sup.collapse_strategy.value,
            chosen=chosen.scenario_id,
        )
        return chosen

    def interfere(
        self,
        superposition_id: str,
        amplify_tags: list[str] | None = None,
        dampen_tags: list[str] | None = None,
        factor: float = 0.5,
    ) -> Superposition:
        """
        Apply constructive / destructive interference to amplitudes.

        Scenarios whose tags overlap with ``amplify_tags`` have their
        probability boosted by ``factor``; those in ``dampen_tags`` are reduced.
        Probabilities are re-normalised after interference.
        """
        sup = self._superpositions.get(superposition_id)
        if sup is None:
            raise KeyError(f"Superposition {superposition_id!r} not found")
        if sup.collapsed:
            raise ValueError("Cannot interfere with already-collapsed superposition")

        amplify = set(amplify_tags or [])
        dampen = set(dampen_tags or [])

        for s in sup.scenarios:
            tag_set = set(s.tags)
            if tag_set & amplify:
                s.probability = min(1.0, s.probability * (1.0 + factor))
            if tag_set & dampen:
                s.probability = max(0.0, s.probability * (1.0 - factor))

        sup.normalise()
        return sup

    # ── Decision Matrix ────────────────────────────────────────────────────────

    def decision_matrix(
        self,
        options: list[str],
        criteria: list[str],
        scores: dict[str, dict[str, float]],
        weights: list[float] | None = None,
    ) -> DecisionMatrix:
        """
        Weighted multi-criteria decision analysis.

        Parameters
        ----------
        options   : list of option names
        criteria  : list of criterion names
        scores    : {option: {criterion: score (0..1)}}
        weights   : importance weight per criterion (will be normalised)
        """
        if weights is None:
            weights = [1.0 / len(criteria)] * len(criteria)

        # Normalise weights
        total_w = sum(weights) or 1.0
        w_norm = [w / total_w for w in weights]

        # Composite score = weighted sum of normalised criterion scores
        ranked_list: list[tuple[str, float]] = []
        for opt in options:
            opt_scores = scores.get(opt, {})
            composite = sum(
                opt_scores.get(crit, 0.0) * w_norm[i] for i, crit in enumerate(criteria)
            )
            ranked_list.append((opt, round(composite, 6)))

        ranked_list.sort(key=lambda x: x[1], reverse=True)

        dm = DecisionMatrix(
            matrix_id=uuid.uuid4().hex[:12],
            options=options,
            criteria=criteria,
            weights=w_norm,
            scores=scores,
            ranked=ranked_list,
        )
        self._matrices[dm.matrix_id] = dm
        log.info("quantum_mind.decision_matrix", id=dm.matrix_id, winner=ranked_list[0][0])
        return dm

    # ── Prediction ────────────────────────────────────────────────────────────

    def predict(
        self,
        variable: str,
        history: list[float],
        horizon: int = 10,
        alpha: float = 0.3,
        confidence: float = 0.95,
    ) -> Prediction:
        """
        Exponential-smoothing forecast with symmetric confidence intervals.

        Parameters
        ----------
        variable  : name of the variable being predicted
        history   : historical values (at least 2 points)
        horizon   : how many future steps to forecast
        alpha     : smoothing factor (0 < alpha < 1)
        confidence: confidence level for intervals (e.g. 0.95)
        """
        if len(history) < 2:
            raise ValueError("Need at least 2 historical points to predict")
        alpha = max(0.01, min(0.99, alpha))

        # Single exponential smoothing
        smoothed = history[0]
        residuals: list[float] = []
        for obs in history[1:]:
            smoothed = alpha * obs + (1.0 - alpha) * smoothed
            residuals.append(abs(obs - smoothed))

        # Forecast
        forecast: list[float] = []
        level = smoothed
        for _ in range(horizon):
            forecast.append(round(level, 6))

        # Confidence interval via MAE
        mae = sum(residuals) / len(residuals) if residuals else 0.0
        z = self._z_for_confidence(confidence)
        margin = z * mae

        pred = Prediction(
            prediction_id=uuid.uuid4().hex[:12],
            variable=variable,
            horizon_steps=horizon,
            values=forecast,
            lower_bound=[round(v - margin, 6) for v in forecast],
            upper_bound=[round(v + margin, 6) for v in forecast],
            confidence=confidence,
            method="exponential_smoothing",
        )
        self._predictions[pred.prediction_id] = pred
        log.info(
            "quantum_mind.prediction",
            id=pred.prediction_id,
            variable=variable,
            horizon=horizon,
        )
        return pred

    # ── Timeline Divergence ───────────────────────────────────────────────────

    def detect_divergence(self, superposition_id: str, threshold: float = 0.3) -> TimelineStatus:
        """
        Detect whether a superposition contains irreconcilably divergent futures.

        Two scenarios are considered divergent when they have similar probabilities
        (within ``threshold``) but opposite utility signs.
        """
        sup = self._superpositions.get(superposition_id)
        if sup is None:
            raise KeyError(f"Superposition {superposition_id!r} not found")
        if sup.collapsed:
            return TimelineStatus.COLLAPSED

        pos = [s for s in sup.scenarios if s.utility > 0]
        neg = [s for s in sup.scenarios if s.utility < 0]

        if not pos or not neg:
            return TimelineStatus.SUPERPOSED

        top_pos_p = max(s.probability for s in pos)
        top_neg_p = max(s.probability for s in neg)

        if abs(top_pos_p - top_neg_p) <= threshold:
            log.warning(
                "quantum_mind.divergence",
                id=superposition_id,
                pos_p=top_pos_p,
                neg_p=top_neg_p,
            )
            return TimelineStatus.DIVERGED

        return TimelineStatus.SUPERPOSED

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "superpositions": len(self._superpositions),
            "collapses": self._collapses,
            "decision_matrices": len(self._matrices),
            "predictions": len(self._predictions),
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _collapse_by_strategy(sup: Superposition) -> Scenario:
        if sup.collapse_strategy == CollapseStrategy.MAX_PROBABILITY:
            return max(sup.scenarios, key=lambda s: s.probability)
        if sup.collapse_strategy == CollapseStrategy.MIN_RISK:
            return min(sup.scenarios, key=lambda s: s.risk)
        if sup.collapse_strategy == CollapseStrategy.MAX_EXPECTED_VALUE:
            return max(sup.scenarios, key=lambda s: s.risk_adjusted_value)
        # WEIGHTED_RANDOM — pseudo-random weighted by probability
        import random

        roll = random.random()
        cumulative = 0.0
        for s in sup.scenarios:
            cumulative += s.probability
            if roll <= cumulative:
                return s
        return sup.scenarios[-1]

    @staticmethod
    def _z_for_confidence(confidence: float) -> float:
        """Approximate z-score for common confidence levels."""
        table = {0.80: 1.282, 0.85: 1.440, 0.90: 1.645, 0.95: 1.960, 0.99: 2.576}
        # Find nearest key
        nearest = min(table.keys(), key=lambda k: abs(k - confidence))
        return table[nearest]

    def get_superposition(self, superposition_id: str) -> Superposition | None:
        return self._superpositions.get(superposition_id)

    def get_prediction(self, prediction_id: str) -> Prediction | None:
        return self._predictions.get(prediction_id)

    def entropy(self, superposition_id: str) -> float:
        """
        Shannon entropy of the superposition's probability distribution.
        High entropy = high uncertainty; 0 = certainty.
        """
        sup = self._superpositions.get(superposition_id)
        if sup is None:
            return 0.0
        h = 0.0
        for s in sup.scenarios:
            if s.probability > 0:
                h -= s.probability * math.log2(s.probability)
        return round(h, 6)
