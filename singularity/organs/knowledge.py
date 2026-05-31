"""KNOWLEDGE — skills, agents and prompt corpus.

Federates: anthropics/skills, everything-claude-code, claude-code (+ -abc) and
the system-prompts corpus. Uniquely, this organ runs in ``REAL`` mode purely
from the filesystem: when the sibling repos are checked out it discovers and
indexes their ``SKILL.md`` / ``agents/*.md`` / vendor prompt files with a
dependency-free frontmatter parser. With no checkout it serves a built-in
catalog so search/listing always work.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..kernel.contracts import Capability, Domain, Mode
from .base import BaseOrgan

_MAX_INDEX = 4000  # safety bound on filesystem scans

_MOCK_SKILLS: tuple[dict[str, str], ...] = (
    {"name": "tdd-workflow", "source": "everything-claude-code",
     "description": "Test-driven development loop: red, green, refactor."},
    {"name": "code-review", "source": "everything-claude-code",
     "description": "Quality and maintainability review of a change."},
    {"name": "docx", "source": "skills", "description": "Create and edit Word documents."},
    {"name": "pdf", "source": "skills", "description": "Generate and manipulate PDF files."},
    {"name": "frontend-design", "source": "claude-code",
     "description": "Build polished web interfaces with strong UX."},
    {"name": "mcp-builder", "source": "skills",
     "description": "Author production MCP servers and tools."},
)


class KnowledgeOrgan(BaseOrgan):
    id = "knowledge"
    domain = Domain.KNOWLEDGE
    title = "Codex — skills, agents & prompts"
    vision = "One searchable memory of every skill, subagent and system prompt in the ecosystem."
    capabilities = (
        Capability("knowledge.skills", "List indexed skills.", {"limit": "int?"}),
        Capability("knowledge.search", "Search skills/agents/prompts by keyword.",
                   {"query": "str", "limit": "int?"}),
        Capability("knowledge.stats", "Report what is indexed and from where.", {}),
    )

    def __init__(self, *, force_mock: bool = False) -> None:
        super().__init__(force_mock=force_mock)
        self._index: list[dict[str, str]] = []
        self._tfidf: dict[str, Any] | None = None  # lazily-built TF-IDF index

    async def _attach_real(self) -> None:
        index: list[dict[str, str]] = []
        root = self.repos_root()
        if root is not None:
            index = _scan_assets(root)
        # Also index any configured knowledge roots (real .md agent/skill corpora
        # that live outside a single checkout — e.g. an agency-agents repo).
        for kroot in _extra_knowledge_roots():
            if len(index) >= _MAX_INDEX:
                break
            _scan_md_tree(Path(kroot), Path(kroot).name, index)
        if not index:
            raise RuntimeError("no assets found on disk")
        self._index = index[:_MAX_INDEX]
        self._detail["indexed"] = len(self._index)
        self._detail["root"] = str(root) if root else "extra-knowledge-roots"

    async def _on_boot(self) -> None:
        if not self._index:  # mock fallback
            self._index = [
                {"kind": "skill", **s} for s in _MOCK_SKILLS
            ]
            self._detail.setdefault("indexed", len(self._index))

    @property
    def _provenance(self) -> str:
        return "filesystem-scan" if self._mode is Mode.REAL else "builtin-catalog"

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "knowledge.skills":
            limit = int(payload.get("limit", 25))
            skills = [a for a in self._index if a.get("kind") == "skill"][:limit]
            return {"skills": skills, "count": len(skills), "total_indexed": len(self._index),
                    "_backend": self._provenance}
        if intent == "knowledge.search":
            result = self._search(str(payload.get("query", "")), int(payload.get("limit", 10)))
            result["_backend"] = self._provenance
            return result
        if intent == "knowledge.stats":
            kinds: dict[str, int] = {}
            sources: dict[str, int] = {}
            for asset in self._index:
                kinds[asset.get("kind", "?")] = kinds.get(asset.get("kind", "?"), 0) + 1
                sources[asset.get("source", "?")] = sources.get(asset.get("source", "?"), 0) + 1
            return {"total": len(self._index), "by_kind": kinds, "by_source": sources,
                    "_backend": self._provenance}
        raise AssertionError("unreachable")  # pragma: no cover

    def _build_tfidf(self) -> None:
        """Build a TF-IDF index over the corpus once (cached) — real semantic
        ranking instead of raw keyword counts (khoj / RAG style)."""
        import math
        import re
        from collections import Counter

        docs = []
        for a in self._index:
            text = f"{a.get('name', '')} {a.get('description', '')}".lower()
            docs.append(Counter(re.findall(r"[a-z0-9]+", text)))
        n_docs = max(1, len(docs))
        df: Counter[str] = Counter()
        for c in docs:
            df.update(c.keys())
        idf = {t: math.log(n_docs / (1 + n)) + 1.0 for t, n in df.items()}
        vecs: list[tuple[dict[str, float], float]] = []
        for c in docs:
            v = {t: cnt * idf.get(t, 0.0) for t, cnt in c.items()}
            norm = math.sqrt(sum(x * x for x in v.values())) or 1e-9
            vecs.append((v, norm))
        self._tfidf = {"idf": idf, "vecs": vecs}

    def _search(self, query: str, limit: int) -> dict[str, Any]:
        import math
        import re
        from collections import Counter

        if self._tfidf is None:
            self._build_tfidf()
        idf: dict[str, float] = self._tfidf["idf"]  # type: ignore[index]
        vecs: list[tuple[dict[str, float], float]] = self._tfidf["vecs"]  # type: ignore[index]
        qc = Counter(re.findall(r"[a-z0-9]+", query.lower()))
        qv = {t: cnt * idf.get(t, 0.0) for t, cnt in qc.items()}
        qnorm = math.sqrt(sum(x * x for x in qv.values())) or 1e-9
        scored: list[tuple[float, int]] = []
        for i, (v, norm) in enumerate(vecs):
            dot = sum(qv[t] * v.get(t, 0.0) for t in qv)
            if dot > 0:
                scored.append((dot / (qnorm * norm), i))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits = [{**self._index[i], "score": round(s, 4)} for s, i in scored[:limit]]
        return {"query": query, "hits": hits, "count": len(hits), "method": "tfidf-cosine"}


# --------------------------------------------------------------------------
# Filesystem scanning (dependency-free)
# --------------------------------------------------------------------------
def _scan_assets(root: Path) -> list[dict[str, str]]:
    index: list[dict[str, str]] = []
    _scan_skills(root / "skills", "skills", index)
    _scan_skills(root / "everything-claude-code", "everything-claude-code", index)
    _scan_agents(root / "everything-claude-code" / "agents", "everything-claude-code", index)
    _scan_skills(root / "claude-code", "claude-code", index)
    _scan_prompts(root / "system-prompts-and-models-of-ai-tools", index)
    return index[:_MAX_INDEX]


_SKIP_MD = {"readme.md", "changelog.md", "contributing.md", "license.md",
            "code_of_conduct.md", "security.md"}


def _extra_knowledge_roots() -> list[str]:
    """Absolute corpus roots from ``SINGULARITY_KNOWLEDGE_PATHS`` env (os.pathsep
    separated) and ``~/.singularity/knowledge.txt`` (one path per line)."""
    import os

    roots: list[str] = []
    env = os.environ.get("SINGULARITY_KNOWLEDGE_PATHS", "")
    if env:
        roots += [p for p in env.split(os.pathsep) if p.strip()]
    cfg = Path.home() / ".singularity" / "knowledge.txt"
    if cfg.is_file():
        try:
            roots += [ln.strip() for ln in cfg.read_text(encoding="utf-8").splitlines()
                      if ln.strip() and not ln.strip().startswith("#")]
        except Exception:  # noqa: BLE001 - unreadable config is non-fatal
            pass
    return roots


def _scan_md_tree(base: Path, source: str, index: list[dict[str, str]]) -> None:
    """Recursively index real agent/skill ``.md`` files (those with frontmatter)
    under ``base`` — skips docs/readmes and vendored trees."""
    if not base.is_dir():
        return
    for path in base.rglob("*.md"):
        if len(index) >= _MAX_INDEX:
            return
        parts = {p.lower() for p in path.parts}
        if ".git" in parts or "node_modules" in parts:
            continue
        if path.name.lower() in _SKIP_MD:
            continue
        meta = _frontmatter(path)
        if not meta.get("name") and not meta.get("description"):
            continue  # only genuine agent/skill definitions carry frontmatter
        index.append(
            {
                "kind": "agent",
                "name": meta.get("name") or path.stem,
                "description": meta.get("description", "")[:280],
                "source": source,
                "path": str(path),
            }
        )


def _scan_skills(base: Path, source: str, index: list[dict[str, str]]) -> None:
    if not base.is_dir():
        return
    for path in base.rglob("SKILL.md"):
        if len(index) >= _MAX_INDEX:
            return
        meta = _frontmatter(path)
        index.append(
            {
                "kind": "skill",
                "name": meta.get("name") or path.parent.name,
                "description": meta.get("description", "")[:280],
                "source": source,
                "path": str(path),
            }
        )


def _scan_agents(base: Path, source: str, index: list[dict[str, str]]) -> None:
    if not base.is_dir():
        return
    for path in sorted(base.glob("*.md")):
        if len(index) >= _MAX_INDEX:
            return
        meta = _frontmatter(path)
        index.append(
            {
                "kind": "agent",
                "name": meta.get("name") or path.stem,
                "description": meta.get("description", "")[:280],
                "source": source,
                "path": str(path),
            }
        )


def _scan_prompts(base: Path, index: list[dict[str, str]]) -> None:
    if not base.is_dir():
        return
    for path in base.rglob("*.txt"):
        if len(index) >= _MAX_INDEX:
            return
        if ".git" in path.parts:
            continue
        index.append(
            {
                "kind": "prompt",
                "name": f"{path.parent.name}/{path.stem}",
                "description": f"System prompt: {path.parent.name}",
                "source": "system-prompts",
                "path": str(path),
            }
        )


def _frontmatter(path: Path) -> dict[str, str]:
    """Parse a leading ``---`` YAML-ish frontmatter block without PyYAML."""

    meta: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return meta
    if not text.startswith("---"):
        return meta
    end = text.find("\n---", 3)
    if end == -1:
        return meta
    block = text[3:end]
    for line in block.splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and value:
            meta[key] = value
    return meta
