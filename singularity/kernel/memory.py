"""Memory — long-term, session-scoped working memory.

A cross-cutting kernel service (like the bus, governor and blackboard) rather
than a federated organ: sessions accumulate turns across many organ calls, and
``recall`` does keyword-scored retrieval over them. Modelled on agency's
``MemoryStore`` and BRAINIAC's session persistence; serialises through any
``Checkpointer`` for durability.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .persistence import Checkpointer


@dataclass(slots=True)
class Turn:
    role: str
    content: str
    intent: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def as_dict(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content, "intent": self.intent,
                "meta": self.meta, "ts": self.ts}


@dataclass
class Session:
    id: str
    created: float = field(default_factory=time.time)
    turns: list[Turn] = field(default_factory=list)


class SessionStore:
    """Multi-session conversational / task memory with keyword recall."""

    def __init__(self, checkpointer: "Checkpointer | None" = None) -> None:
        self._sessions: dict[str, Session] = {}
        self._checkpointer = checkpointer

    def session(self, sid: str = "default") -> Session:
        return self._sessions.setdefault(sid, Session(id=sid))

    def remember(
        self,
        content: str,
        *,
        role: str = "user",
        sid: str = "default",
        intent: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Turn:
        turn = Turn(role=role, content=content, intent=intent, meta=meta or {})
        self.session(sid).turns.append(turn)
        return turn

    def recall(self, query: str, *, sid: str | None = None, limit: int = 5) -> list[Turn]:
        """TF-IDF cosine retrieval over remembered turns (keyword-safe)."""

        q_terms = _tokenize(query)
        if not q_terms:
            return []
        pool: list[Turn] = []
        sessions = (
            [self._sessions[sid]] if sid and sid in self._sessions else list(self._sessions.values())
        )
        for session in sessions:
            pool.extend(session.turns)
        if not pool:
            return []

        docs = [_tokenize(t.content) for t in pool]
        df: dict[str, int] = {}
        for doc in docs:
            for term in set(doc):
                df[term] = df.get(term, 0) + 1
        n = len(docs)
        idf = {term: math.log((n + 1) / (count + 1)) + 1 for term, count in df.items()}

        q_vec = _tfidf(q_terms, idf)
        scored: list[tuple[float, float, Turn]] = []
        for turn, doc in zip(pool, docs):
            score = _cosine(q_vec, _tfidf(doc, idf))
            if score > 0:
                scored.append((score, turn.ts, turn))
        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [turn for _, _, turn in scored[:limit]]

    def sessions(self) -> list[str]:
        return sorted(self._sessions)

    def summary(self, sid: str = "default") -> dict[str, Any]:
        session = self._sessions.get(sid)
        if not session:
            return {"id": sid, "turns": 0}
        return {
            "id": sid,
            "created": session.created,
            "turns": len(session.turns),
            "last": session.turns[-1].as_dict() if session.turns else None,
        }

    # -- durability -------------------------------------------------------
    def save(self, name: str = "memory") -> bool:
        if self._checkpointer is None:
            return False
        state = {
            sid: {"created": s.created, "turns": [t.as_dict() for t in s.turns]}
            for sid, s in self._sessions.items()
        }
        self._checkpointer.save(name, {"sessions": state})
        return True

    def load(self, name: str = "memory") -> bool:
        if self._checkpointer is None:
            return False
        state = self._checkpointer.load(name)
        if not state:
            return False
        for sid, data in (state.get("sessions") or {}).items():
            session = Session(id=sid, created=data.get("created", time.time()))
            session.turns = [
                Turn(role=t["role"], content=t["content"], intent=t.get("intent"),
                     meta=t.get("meta", {}), ts=t.get("ts", time.time()))
                for t in data.get("turns", [])
            ]
            self._sessions[sid] = session
        return True

    def __len__(self) -> int:
        return len(self._sessions)


# --------------------------------------------------------------------------
# TF-IDF cosine helpers (dependency-free)
# --------------------------------------------------------------------------
def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]{2,}", text.lower())


def _tfidf(terms: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf: dict[str, float] = {}
    for term in terms:
        tf[term] = tf.get(term, 0.0) + 1.0
    return {term: count * idf.get(term, 1.0) for term, count in tf.items()}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[t] * b[t] for t in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0
