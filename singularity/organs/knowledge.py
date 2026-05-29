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

from ..kernel.contracts import Capability, Domain
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

    async def _attach_real(self) -> None:
        root = self.repos_root()
        if root is None:
            raise RuntimeError("no repos root for asset scan")
        index = _scan_assets(root)
        if not index:
            raise RuntimeError("no assets found on disk")
        self._index = index
        self._detail["indexed"] = len(index)
        self._detail["root"] = str(root)

    async def _on_boot(self) -> None:
        if not self._index:  # mock fallback
            self._index = [
                {"kind": "skill", **s} for s in _MOCK_SKILLS
            ]
            self._detail.setdefault("indexed", len(self._index))

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "knowledge.skills":
            limit = int(payload.get("limit", 25))
            skills = [a for a in self._index if a.get("kind") == "skill"][:limit]
            return {"skills": skills, "count": len(skills), "total_indexed": len(self._index)}
        if intent == "knowledge.search":
            return self._search(str(payload.get("query", "")), int(payload.get("limit", 10)))
        if intent == "knowledge.stats":
            kinds: dict[str, int] = {}
            sources: dict[str, int] = {}
            for asset in self._index:
                kinds[asset.get("kind", "?")] = kinds.get(asset.get("kind", "?"), 0) + 1
                sources[asset.get("source", "?")] = sources.get(asset.get("source", "?"), 0) + 1
            return {"total": len(self._index), "by_kind": kinds, "by_source": sources}
        raise AssertionError("unreachable")  # pragma: no cover

    def _search(self, query: str, limit: int) -> dict[str, Any]:
        terms = [t for t in query.lower().split() if t]
        scored: list[tuple[int, dict[str, str]]] = []
        for asset in self._index:
            haystack = f"{asset.get('name', '')} {asset.get('description', '')}".lower()
            score = sum(haystack.count(term) for term in terms)
            if score:
                scored.append((score, asset))
        scored.sort(key=lambda item: item[0], reverse=True)
        hits = [asset for _, asset in scored[:limit]]
        return {"query": query, "hits": hits, "count": len(hits)}


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
