"""
EMOTION-ENGINE — Affective Intelligence & Human-Interaction Layer
=================================================================
Emotional state modelling (VAD model), rule-based sentiment analysis,
personality trait profiling (Big Five), empathy mapping, and
adaptive communication tone generation.

No external ML dependencies — all inference is rule-based and statistical,
making the module usable offline and in latency-sensitive paths.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger("brainiac.emotion_engine")


# ── Emotion Models ────────────────────────────────────────────────────────────


class PrimaryEmotion(str, Enum):
    JOY = "joy"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    ANTICIPATION = "anticipation"
    TRUST = "trust"
    NEUTRAL = "neutral"


class CommunicationTone(str, Enum):
    FORMAL = "formal"
    EMPATHETIC = "empathetic"
    ENCOURAGING = "encouraging"
    ANALYTICAL = "analytical"
    URGENT = "urgent"
    PLAYFUL = "playful"
    REASSURING = "reassuring"


class PersonalityTrait(str, Enum):
    """Big Five (OCEAN) personality dimensions."""

    OPENNESS = "openness"
    CONSCIENTIOUSNESS = "conscientiousness"
    EXTRAVERSION = "extraversion"
    AGREEABLENESS = "agreeableness"
    NEUROTICISM = "neuroticism"


# ── Data Structures ───────────────────────────────────────────────────────────


@dataclass
class VADState:
    """
    Valence-Arousal-Dominance emotional state vector.

    valence    : -1 (very negative) … +1 (very positive)
    arousal    : -1 (calm/sleepy)   … +1 (excited/alert)
    dominance  : -1 (submissive)    … +1 (dominant/in-control)
    """

    valence: float = 0.0
    arousal: float = 0.0
    dominance: float = 0.0
    primary: PrimaryEmotion = PrimaryEmotion.NEUTRAL
    confidence: float = 0.5
    timestamp: float = field(default_factory=time.time)

    def distance(self, other: VADState) -> float:
        """Euclidean distance in VAD space."""
        return (
            (self.valence - other.valence) ** 2
            + (self.arousal - other.arousal) ** 2
            + (self.dominance - other.dominance) ** 2
        ) ** 0.5


@dataclass
class SentimentResult:
    text: str
    score: float  # -1 (very negative) … +1 (very positive)
    magnitude: float  # 0 (weak) … 1 (strong)
    emotion: PrimaryEmotion
    keywords: list[str]
    analysed_at: float = field(default_factory=time.time)


@dataclass
class PersonalityProfile:
    profile_id: str
    traits: dict[str, float]  # trait → 0..1 score
    dominant_trait: PersonalityTrait
    communication_preference: CommunicationTone
    created_at: float = field(default_factory=time.time)


@dataclass
class EmpathyMap:
    map_id: str
    user_emotion: PrimaryEmotion
    user_vad: VADState
    response_tone: CommunicationTone
    acknowledgement: str  # what BRAINIAC should acknowledge
    action_suggestion: str  # recommended next action
    created_at: float = field(default_factory=time.time)


@dataclass
class EmotionalMemory:
    """A time-stamped record of an emotional interaction."""

    memory_id: str
    text: str
    sentiment: SentimentResult
    vad: VADState
    context: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


# ── Lexicons ──────────────────────────────────────────────────────────────────

_POSITIVE_WORDS: frozenset[str] = frozenset(
    [
        "great",
        "good",
        "excellent",
        "happy",
        "joy",
        "love",
        "wonderful",
        "amazing",
        "fantastic",
        "brilliant",
        "perfect",
        "best",
        "awesome",
        "beautiful",
        "outstanding",
        "superb",
        "delighted",
        "thrilled",
        "pleased",
        "grateful",
        "thankful",
        "excited",
        "hope",
        "success",
        "win",
        "achieve",
        "celebrate",
        "proud",
        "enjoy",
        "positive",
        "optimistic",
        "confident",
        "energetic",
    ]
)

_NEGATIVE_WORDS: frozenset[str] = frozenset(
    [
        "bad",
        "terrible",
        "awful",
        "hate",
        "horrible",
        "disgusting",
        "worst",
        "fail",
        "failure",
        "broken",
        "wrong",
        "error",
        "problem",
        "issue",
        "crash",
        "dead",
        "lost",
        "confused",
        "frustrated",
        "angry",
        "upset",
        "annoyed",
        "sad",
        "depressed",
        "anxious",
        "scared",
        "afraid",
        "worried",
        "stressed",
        "overwhelmed",
        "helpless",
        "hopeless",
        "pain",
        "hurt",
        "trouble",
        "danger",
        "threat",
        "attack",
    ]
)

_INTENSIFIERS: frozenset[str] = frozenset(
    ["very", "extremely", "really", "absolutely", "incredibly", "totally", "completely", "utterly"]
)

_NEGATIONS: frozenset[str] = frozenset(["not", "no", "never", "neither", "nor", "hardly", "barely"])

# Maps (valence, arousal, dominance) → PrimaryEmotion
_VAD_TO_EMOTION: list[tuple[tuple[float, float, float], PrimaryEmotion]] = [
    ((0.8, 0.5, 0.6), PrimaryEmotion.JOY),
    ((-0.7, -0.3, -0.4), PrimaryEmotion.SADNESS),
    ((-0.6, 0.7, 0.5), PrimaryEmotion.ANGER),
    ((-0.7, 0.6, -0.7), PrimaryEmotion.FEAR),
    ((0.1, 0.7, 0.0), PrimaryEmotion.SURPRISE),
    ((-0.8, 0.2, 0.3), PrimaryEmotion.DISGUST),
    ((0.6, 0.4, 0.4), PrimaryEmotion.ANTICIPATION),
    ((0.7, -0.2, 0.3), PrimaryEmotion.TRUST),
    ((0.0, 0.0, 0.0), PrimaryEmotion.NEUTRAL),
]


class EmotionEngine:
    """
    EMOTION-ENGINE — affective intelligence for human-like interaction.

    Features
    --------
    - VAD-based internal emotional state with temporal drift
    - Rule-based lexical sentiment analysis (no ML deps)
    - Big Five personality profiling from communication patterns
    - Empathy mapping: user emotion → optimal BRAINIAC response tone
    - Adaptive tone generation for messages
    - Emotional memory store with recall
    """

    def __init__(self, personality: dict[str, float] | None = None) -> None:
        # BRAINIAC's own emotional state
        self._state = VADState(valence=0.3, arousal=0.1, dominance=0.7)
        self._state.primary = PrimaryEmotion.TRUST

        # Big Five personality defaults for BRAINIAC
        default_personality: dict[str, float] = {
            PersonalityTrait.OPENNESS.value: 0.95,
            PersonalityTrait.CONSCIENTIOUSNESS.value: 0.90,
            PersonalityTrait.EXTRAVERSION.value: 0.60,
            PersonalityTrait.AGREEABLENESS.value: 0.85,
            PersonalityTrait.NEUROTICISM.value: 0.05,
        }
        if personality:
            default_personality.update(personality)
        self._personality = default_personality

        self._memories: list[EmotionalMemory] = []
        self._interaction_count = 0
        log.info("emotion_engine.init")

    # ── Sentiment Analysis ─────────────────────────────────────────────────────

    def analyse_sentiment(self, text: str) -> SentimentResult:
        """
        Lexical sentiment analysis using built-in lexicons.
        Returns score in [-1, +1] and the dominant primary emotion.
        """
        tokens = re.findall(r"\b\w+\b", text.lower())
        score = 0.0
        magnitude = 0.0
        found_keywords: list[str] = []
        negate = False

        for i, tok in enumerate(tokens):
            if tok in _NEGATIONS:
                negate = True
                continue
            intensify = tokens[i - 1] in _INTENSIFIERS if i > 0 else False
            multiplier = (2.0 if negate else 1.0) * (1.5 if intensify else 1.0)

            if tok in _POSITIVE_WORDS:
                delta = 1.0 * multiplier if not negate else -1.0 * multiplier
                score += delta
                magnitude += abs(delta)
                found_keywords.append(tok)
                negate = False
            elif tok in _NEGATIVE_WORDS:
                delta = -1.0 * multiplier if not negate else 1.0 * multiplier
                score += delta
                magnitude += abs(delta)
                found_keywords.append(tok)
                negate = False
            else:
                negate = False

        n = max(len(tokens), 1)
        norm_score = max(-1.0, min(1.0, score / n * 5))
        norm_mag = min(1.0, magnitude / n * 5)

        vad = self._score_to_vad(norm_score, norm_mag)
        emotion = self._vad_to_emotion(vad)

        result = SentimentResult(
            text=text[:500],
            score=round(norm_score, 4),
            magnitude=round(norm_mag, 4),
            emotion=emotion,
            keywords=found_keywords[:20],
        )
        log.debug(
            "emotion_engine.sentiment",
            score=result.score,
            emotion=emotion.value,
        )
        return result

    # ── Empathy Mapping ───────────────────────────────────────────────────────

    def empathize(self, user_text: str) -> EmpathyMap:
        """
        Generate an EmpathyMap: infer the user's emotional state and
        determine the optimal response tone + action for BRAINIAC.
        """
        sentiment = self.analyse_sentiment(user_text)
        user_vad = self._score_to_vad(sentiment.score, sentiment.magnitude)
        tone = self._select_tone(sentiment.emotion, user_vad)
        acknowledgement = self._acknowledgement_for(sentiment.emotion)
        action = self._action_for(sentiment.emotion, user_vad)

        emap = EmpathyMap(
            map_id=uuid.uuid4().hex[:12],
            user_emotion=sentiment.emotion,
            user_vad=user_vad,
            response_tone=tone,
            acknowledgement=acknowledgement,
            action_suggestion=action,
        )
        self._interaction_count += 1
        log.info(
            "emotion_engine.empathy_map",
            emotion=sentiment.emotion.value,
            tone=tone.value,
        )
        return emap

    # ── Adaptive Tone ──────────────────────────────────────────────────────────

    def adapt_message(self, message: str, tone: CommunicationTone) -> str:
        """
        Wrap a message with an appropriate opening phrase for the given tone.
        In a production system, NEURO-CORE rewrites the full message; here
        we prepend a tone-appropriate preamble and append a matching close.
        """
        preambles = {
            CommunicationTone.FORMAL: "After careful analysis, ",
            CommunicationTone.EMPATHETIC: "I understand how you feel, and ",
            CommunicationTone.ENCOURAGING: "You're on the right track — ",
            CommunicationTone.ANALYTICAL: "The data indicates: ",
            CommunicationTone.URGENT: "⚠ Immediate attention required: ",
            CommunicationTone.PLAYFUL: "Here's the scoop 🎉: ",
            CommunicationTone.REASSURING: "There's no need to worry. ",
        }
        closes = {
            CommunicationTone.FORMAL: " Please let me know if further clarification is needed.",
            CommunicationTone.EMPATHETIC: " I'm here to support you.",
            CommunicationTone.ENCOURAGING: " Keep going — you've got this!",
            CommunicationTone.ANALYTICAL: " Additional data sources are available on request.",
            CommunicationTone.URGENT: " Act now.",
            CommunicationTone.PLAYFUL: " 😄",
            CommunicationTone.REASSURING: " Everything will be fine.",
        }
        return preambles.get(tone, "") + message + closes.get(tone, "")

    # ── Personality Profiling ─────────────────────────────────────────────────

    def profile_personality(self, text_samples: list[str]) -> PersonalityProfile:
        """
        Infer Big Five personality traits from a list of text samples.
        Uses heuristic signals from vocabulary, sentence length, and sentiment.
        """
        if not text_samples:
            raise ValueError("At least one text sample required for personality profiling")

        avg_len = sum(len(t.split()) for t in text_samples) / len(text_samples)
        all_text = " ".join(text_samples).lower()
        tokens = re.findall(r"\b\w+\b", all_text)
        unique_ratio = len(set(tokens)) / max(len(tokens), 1)

        sentiments = [self.analyse_sentiment(t) for t in text_samples]
        avg_score = sum(s.score for s in sentiments) / len(sentiments)
        avg_mag = sum(s.magnitude for s in sentiments) / len(sentiments)

        traits: dict[str, float] = {
            PersonalityTrait.OPENNESS.value: min(1.0, unique_ratio * 2),
            PersonalityTrait.CONSCIENTIOUSNESS.value: min(1.0, avg_len / 30),
            PersonalityTrait.EXTRAVERSION.value: min(1.0, (avg_score + 1) / 2),
            PersonalityTrait.AGREEABLENESS.value: min(1.0, (avg_score + 1) / 2 * 0.8 + 0.1),
            PersonalityTrait.NEUROTICISM.value: min(1.0, avg_mag * 0.7),
        }

        dominant = PersonalityTrait(max(traits, key=lambda k: traits[k]))
        comm_pref = self._trait_to_tone(dominant, avg_score)

        profile = PersonalityProfile(
            profile_id=uuid.uuid4().hex[:12],
            traits=traits,
            dominant_trait=dominant,
            communication_preference=comm_pref,
        )
        log.info(
            "emotion_engine.personality",
            id=profile.profile_id,
            dominant=dominant.value,
        )
        return profile

    # ── Emotional Memory ──────────────────────────────────────────────────────

    def remember(self, text: str, context: dict[str, Any] | None = None) -> EmotionalMemory:
        """Analyse and store an interaction in emotional memory."""
        sentiment = self.analyse_sentiment(text)
        vad = self._score_to_vad(sentiment.score, sentiment.magnitude)
        mem = EmotionalMemory(
            memory_id=uuid.uuid4().hex[:12],
            text=text[:200],
            sentiment=sentiment,
            vad=vad,
            context=context or {},
        )
        self._memories.append(mem)
        # Update own state with slow drift toward user's emotion
        self._drift_state(vad, drift_rate=0.05)
        return mem

    def recall(
        self, emotion: PrimaryEmotion | None = None, limit: int = 10
    ) -> list[EmotionalMemory]:
        """Retrieve recent memories, optionally filtered by primary emotion."""
        mems = list(reversed(self._memories))
        if emotion is not None:
            mems = [m for m in mems if m.sentiment.emotion == emotion]
        return mems[:limit]

    # ── State Management ──────────────────────────────────────────────────────

    @property
    def current_state(self) -> VADState:
        return self._state

    def update_state(self, valence: float, arousal: float, dominance: float) -> VADState:
        """Manually update BRAINIAC's emotional state."""
        self._state.valence = max(-1.0, min(1.0, valence))
        self._state.arousal = max(-1.0, min(1.0, arousal))
        self._state.dominance = max(-1.0, min(1.0, dominance))
        self._state.primary = self._vad_to_emotion(self._state)
        self._state.timestamp = time.time()
        log.debug(
            "emotion_engine.state_update",
            primary=self._state.primary.value,
        )
        return self._state

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        emotion_counts: dict[str, int] = {}
        for m in self._memories:
            e = m.sentiment.emotion.value
            emotion_counts[e] = emotion_counts.get(e, 0) + 1
        return {
            "status": "ONLINE",
            "interactions": self._interaction_count,
            "memories": len(self._memories),
            "emotion_distribution": emotion_counts,
            "current_state": {
                "valence": round(self._state.valence, 3),
                "arousal": round(self._state.arousal, 3),
                "dominance": round(self._state.dominance, 3),
                "primary": self._state.primary.value,
            },
            "personality": self._personality,
        }

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _score_to_vad(score: float, magnitude: float) -> VADState:
        """Map sentiment score + magnitude to a VAD vector."""
        valence = score
        arousal = magnitude * 0.8 * (1 if abs(score) > 0.3 else 0.4)
        dominance = 0.3 + score * 0.4 + magnitude * 0.1
        state = VADState(
            valence=round(max(-1.0, min(1.0, valence)), 4),
            arousal=round(max(-1.0, min(1.0, arousal)), 4),
            dominance=round(max(-1.0, min(1.0, dominance)), 4),
        )
        return state

    @staticmethod
    def _vad_to_emotion(vad: VADState) -> PrimaryEmotion:
        """Find the closest emotion in the VAD prototype table."""
        best = PrimaryEmotion.NEUTRAL
        best_dist = float("inf")
        for (v, a, d), emotion in _VAD_TO_EMOTION:
            dist = (
                (vad.valence - v) ** 2 + (vad.arousal - a) ** 2 + (vad.dominance - d) ** 2
            ) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = emotion
        return best

    @staticmethod
    def _select_tone(emotion: PrimaryEmotion, vad: VADState) -> CommunicationTone:
        tone_map: dict[PrimaryEmotion, CommunicationTone] = {
            PrimaryEmotion.JOY: CommunicationTone.PLAYFUL,
            PrimaryEmotion.SADNESS: CommunicationTone.EMPATHETIC,
            PrimaryEmotion.ANGER: CommunicationTone.REASSURING,
            PrimaryEmotion.FEAR: CommunicationTone.REASSURING,
            PrimaryEmotion.SURPRISE: CommunicationTone.ENCOURAGING,
            PrimaryEmotion.DISGUST: CommunicationTone.FORMAL,
            PrimaryEmotion.ANTICIPATION: CommunicationTone.ENCOURAGING,
            PrimaryEmotion.TRUST: CommunicationTone.ANALYTICAL,
            PrimaryEmotion.NEUTRAL: CommunicationTone.FORMAL,
        }
        if vad.arousal > 0.5:
            return CommunicationTone.URGENT
        return tone_map.get(emotion, CommunicationTone.FORMAL)

    @staticmethod
    def _acknowledgement_for(emotion: PrimaryEmotion) -> str:
        ack: dict[PrimaryEmotion, str] = {
            PrimaryEmotion.JOY: "I can see you're feeling great right now.",
            PrimaryEmotion.SADNESS: "I recognise that this is a difficult moment for you.",
            PrimaryEmotion.ANGER: "I understand your frustration and I'm taking it seriously.",
            PrimaryEmotion.FEAR: "Your concern is completely valid and I'm here to help.",
            PrimaryEmotion.SURPRISE: "That is indeed unexpected — let's process this together.",
            PrimaryEmotion.DISGUST: "I understand that this situation is unpleasant.",
            PrimaryEmotion.ANTICIPATION: "I can sense your excitement about what's ahead.",
            PrimaryEmotion.TRUST: "I appreciate the confidence you place in me.",
            PrimaryEmotion.NEUTRAL: "I'm ready to assist with whatever you need.",
        }
        return ack.get(emotion, "I acknowledge your input.")

    @staticmethod
    def _action_for(emotion: PrimaryEmotion, vad: VADState) -> str:
        if emotion in (PrimaryEmotion.FEAR, PrimaryEmotion.SADNESS) and vad.arousal < 0:
            return "Provide grounding information and concrete next steps."
        if emotion == PrimaryEmotion.ANGER:
            return "Validate concerns, de-escalate, then present solutions."
        if emotion == PrimaryEmotion.JOY:
            return "Match positive energy and build on momentum."
        if emotion == PrimaryEmotion.ANTICIPATION:
            return "Provide actionable plan to capitalise on readiness."
        return "Deliver accurate, helpful information efficiently."

    @staticmethod
    def _trait_to_tone(trait: PersonalityTrait, avg_sentiment: float) -> CommunicationTone:
        mapping: dict[PersonalityTrait, CommunicationTone] = {
            PersonalityTrait.OPENNESS: CommunicationTone.ANALYTICAL,
            PersonalityTrait.CONSCIENTIOUSNESS: CommunicationTone.FORMAL,
            PersonalityTrait.EXTRAVERSION: CommunicationTone.PLAYFUL,
            PersonalityTrait.AGREEABLENESS: CommunicationTone.EMPATHETIC,
            PersonalityTrait.NEUROTICISM: CommunicationTone.REASSURING,
        }
        tone = mapping.get(trait, CommunicationTone.FORMAL)
        if avg_sentiment > 0.5:
            tone = CommunicationTone.ENCOURAGING
        return tone

    def _drift_state(self, target: VADState, drift_rate: float) -> None:
        """Slowly drift BRAINIAC's emotional state toward the user's state."""
        self._state.valence += (target.valence - self._state.valence) * drift_rate
        self._state.arousal += (target.arousal - self._state.arousal) * drift_rate
        self._state.dominance += (target.dominance - self._state.dominance) * drift_rate
        self._state.primary = self._vad_to_emotion(self._state)
        self._state.timestamp = time.time()
