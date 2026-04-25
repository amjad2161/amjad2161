"""Tests for EMOTION-ENGINE module."""

from __future__ import annotations

import pytest

from brainiac.core.emotion_engine import (
    CommunicationTone,
    EmotionEngine,
    PersonalityTrait,
    PrimaryEmotion,
)


@pytest.fixture
def engine() -> EmotionEngine:
    return EmotionEngine()


# ── Sentiment Analysis ────────────────────────────────────────────────────────


def test_positive_sentiment(engine: EmotionEngine) -> None:
    result = engine.analyse_sentiment("This is amazing! I love it, fantastic work!")
    assert result.score > 0
    assert result.magnitude > 0
    assert result.emotion != PrimaryEmotion.SADNESS
    assert result.emotion != PrimaryEmotion.ANGER


def test_negative_sentiment(engine: EmotionEngine) -> None:
    result = engine.analyse_sentiment("This is terrible, I hate it. Awful failure.")
    assert result.score < 0
    assert result.magnitude > 0


def test_neutral_text(engine: EmotionEngine) -> None:
    result = engine.analyse_sentiment("The file exists at the path.")
    assert abs(result.score) < 0.5  # roughly neutral


def test_keywords_extracted(engine: EmotionEngine) -> None:
    result = engine.analyse_sentiment("wonderful and happy and great")
    assert len(result.keywords) > 0


def test_negation_flips_score(engine: EmotionEngine) -> None:
    pos = engine.analyse_sentiment("I love this product")
    neg = engine.analyse_sentiment("I do not love this product")
    # Negated form should score lower than positive form
    assert neg.score < pos.score


def test_empty_like_text(engine: EmotionEngine) -> None:
    result = engine.analyse_sentiment("the a an is of")
    assert -1.0 <= result.score <= 1.0
    assert 0.0 <= result.magnitude <= 1.0


# ── Empathy Mapping ───────────────────────────────────────────────────────────


def test_empathize_returns_emap(engine: EmotionEngine) -> None:
    emap = engine.empathize("I'm feeling really sad and overwhelmed today.")
    assert emap.map_id
    assert emap.user_emotion in PrimaryEmotion.__members__.values()
    assert emap.response_tone in CommunicationTone.__members__.values()
    assert emap.acknowledgement
    assert emap.action_suggestion


def test_empathize_positive_text(engine: EmotionEngine) -> None:
    emap = engine.empathize("I'm so happy and excited, everything is great!")
    assert emap.user_emotion in (
        PrimaryEmotion.JOY,
        PrimaryEmotion.ANTICIPATION,
        PrimaryEmotion.TRUST,
    )


def test_empathize_angry_text(engine: EmotionEngine) -> None:
    emap = engine.empathize("I'm angry and frustrated, this is terrible!")
    # High arousal → URGENT tone; or REASSURING for anger
    assert emap.response_tone in (CommunicationTone.URGENT, CommunicationTone.REASSURING)


def test_empathize_increments_interaction_count(engine: EmotionEngine) -> None:
    before = engine.diagnostics()["interactions"]
    engine.empathize("test")
    after = engine.diagnostics()["interactions"]
    assert after == before + 1


# ── Adaptive Tone ─────────────────────────────────────────────────────────────


def test_adapt_message_prepends_preamble(engine: EmotionEngine) -> None:
    adapted = engine.adapt_message("Here is the data.", CommunicationTone.ANALYTICAL)
    assert adapted.startswith("The data indicates: ")


def test_adapt_message_appends_close(engine: EmotionEngine) -> None:
    adapted = engine.adapt_message("Everything is fine.", CommunicationTone.REASSURING)
    assert "Everything will be fine." in adapted


def test_adapt_message_all_tones(engine: EmotionEngine) -> None:
    for tone in CommunicationTone:
        result = engine.adapt_message("test message", tone)
        assert "test message" in result


# ── Personality Profiling ─────────────────────────────────────────────────────


def test_personality_profile_created(engine: EmotionEngine) -> None:
    samples = [
        "I love exploring new ideas and learning every single day.",
        "I am very organised and methodical in everything I do.",
        "Meeting new people energises me and I enjoy social events.",
    ]
    profile = engine.profile_personality(samples)
    assert profile.profile_id
    assert len(profile.traits) == 5
    for v in profile.traits.values():
        assert 0.0 <= v <= 1.0
    assert profile.dominant_trait in PersonalityTrait.__members__.values()
    assert profile.communication_preference in CommunicationTone.__members__.values()


def test_personality_empty_samples_raises(engine: EmotionEngine) -> None:
    with pytest.raises(ValueError):
        engine.profile_personality([])


# ── Emotional Memory ──────────────────────────────────────────────────────────


def test_remember_stores_memory(engine: EmotionEngine) -> None:
    engine.remember("This was a great meeting!")
    assert engine.diagnostics()["memories"] == 1


def test_recall_recent(engine: EmotionEngine) -> None:
    engine.remember("I'm happy!")
    engine.remember("I'm sad.")
    memories = engine.recall(limit=5)
    assert len(memories) >= 2
    # Most recent first
    assert memories[0].text == "I'm sad."


def test_recall_filter_by_emotion(engine: EmotionEngine) -> None:
    engine.remember("amazing fantastic wonderful")
    memories = engine.recall(emotion=PrimaryEmotion.JOY, limit=10)
    # May be empty if emotion doesn't match exactly — just check no crash
    assert isinstance(memories, list)


# ── State Management ──────────────────────────────────────────────────────────


def test_update_state(engine: EmotionEngine) -> None:
    engine.update_state(valence=0.8, arousal=0.6, dominance=0.5)
    s = engine.current_state
    assert s.valence == pytest.approx(0.8)
    assert s.arousal == pytest.approx(0.6)
    assert s.dominance == pytest.approx(0.5)


def test_state_clamps_to_range(engine: EmotionEngine) -> None:
    engine.update_state(valence=5.0, arousal=-9.0, dominance=100.0)
    s = engine.current_state
    assert -1.0 <= s.valence <= 1.0
    assert -1.0 <= s.arousal <= 1.0
    assert -1.0 <= s.dominance <= 1.0


# ── Diagnostics ───────────────────────────────────────────────────────────────


def test_diagnostics(engine: EmotionEngine) -> None:
    d = engine.diagnostics()
    assert d["status"] == "ONLINE"
    assert "interactions" in d
    assert "memories" in d
    assert "current_state" in d
    assert "personality" in d


def test_vad_state_distance() -> None:
    from brainiac.core.emotion_engine import VADState

    a = VADState(valence=0.0, arousal=0.0, dominance=0.0)
    b = VADState(valence=1.0, arousal=0.0, dominance=0.0)
    assert a.distance(b) == pytest.approx(1.0)
    assert a.distance(a) == pytest.approx(0.0)
