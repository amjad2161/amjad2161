"""The ecosystem manifest — the single source of truth for the federation.

Every repository in ``amjad2161``'s constellation is declared here exactly
once, mapped to the organ that federates it and annotated with how the kernel
talks to it. This is what makes the platform *singular and continuous*: one
canonical description of the whole organism, machine-readable and
human-auditable, generated into ``INTEGRATION_MAP.md``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import Domain


class Integration(str):
    """How the kernel reaches a backing repo."""

    IN_PROCESS = "in-process"  # python import in the same interpreter
    HTTP = "http"  # REST / websocket service
    SUBPROCESS = "subprocess"  # spawn a CLI / node process
    ASSET = "asset"  # filesystem assets (skills, prompts) parsed in-process


@dataclass(frozen=True, slots=True)
class RepoSpec:
    """Declaration of one repository's place in the singularity."""

    repo: str
    organ: str
    domain: Domain
    language: str
    integration: str
    entrypoint: str
    mock_ready: bool
    role: str

    def as_dict(self) -> dict[str, object]:
        return {
            "repo": self.repo,
            "organ": self.organ,
            "domain": self.domain.value,
            "language": self.language,
            "integration": self.integration,
            "entrypoint": self.entrypoint,
            "mock_ready": self.mock_ready,
            "role": self.role,
        }


# --------------------------------------------------------------------------
# The 17 repositories, federated into 8 organs.
# --------------------------------------------------------------------------
ECOSYSTEM: tuple[RepoSpec, ...] = (
    # ---- REASONING -------------------------------------------------------
    RepoSpec(
        repo="amjad2161 (brainiac)",
        organ="neuro",
        domain=Domain.REASONING,
        language="python",
        integration=Integration.IN_PROCESS,
        entrypoint="brainiac.core.neuro_core:NeuroCore",
        mock_ready=True,
        role="Anthropic-backed reasoning core: think / stream / parallel-think with a cost breaker.",
    ),
    RepoSpec(
        repo="Mythos",
        organ="neuro",
        domain=Domain.REASONING,
        language="python",
        integration=Integration.IN_PROCESS,
        entrypoint="mythos:MythosAgent.run",
        mock_ready=True,
        role="Minimal self-directed Reason→Act→Observe autonomous loop with self-monitoring.",
    ),
    RepoSpec(
        repo="SuperAGI",
        organ="neuro",
        domain=Domain.REASONING,
        language="python",
        integration=Integration.HTTP,
        entrypoint="POST /v1/agent/{id}/run",
        mock_ready=False,
        role="Production agent framework (Celery + Postgres) for concurrent autonomous workflows.",
    ),
    RepoSpec(
        repo="anthropic-sdk-typescript",
        organ="neuro",
        domain=Domain.REASONING,
        language="typescript",
        integration=Integration.SUBPROCESS,
        entrypoint="@anthropic-ai/sdk:Anthropic",
        mock_ready=True,
        role="Canonical typed Claude client used by every TypeScript organ.",
    ),
    RepoSpec(
        repo="anthropic-quickstarts",
        organ="neuro",
        domain=Domain.REASONING,
        language="python/typescript",
        integration=Integration.HTTP,
        entrypoint="computer_use_demo.loop:sampling_loop",
        mock_ready=True,
        role="Reference Claude apps: computer-use loop, support RAG, financial analyst.",
    ),
    # ---- AGENCY ----------------------------------------------------------
    RepoSpec(
        repo="agency-agents",
        organ="agents",
        domain=Domain.AGENCY,
        language="python",
        integration=Integration.IN_PROCESS,
        entrypoint="agency.jarvis_brain:SupremeJarvisBrain",
        mock_ready=True,
        role="JARVIS brain + 340 persona skills, deterministic routing, planner→executor loop.",
    ),
    RepoSpec(
        repo="everything-claude-code",
        organ="agents",
        domain=Domain.AGENCY,
        language="markdown/node",
        integration=Integration.ASSET,
        entrypoint="agents/*.md",
        mock_ready=True,
        role="47 production subagents with model/tool routing frontmatter.",
    ),
    # ---- KNOWLEDGE -------------------------------------------------------
    RepoSpec(
        repo="skills",
        organ="knowledge",
        domain=Domain.KNOWLEDGE,
        language="markdown",
        integration=Integration.ASSET,
        entrypoint="skills/**/SKILL.md",
        mock_ready=True,
        role="Anthropic Agent Skills reference packages (docx/pdf/pptx/design/mcp).",
    ),
    RepoSpec(
        repo="claude-code",
        organ="knowledge",
        domain=Domain.KNOWLEDGE,
        language="markdown/typescript",
        integration=Integration.ASSET,
        entrypoint="plugins/*/.claude-plugin/plugin.json",
        mock_ready=True,
        role="Reference Claude Code plugins: agents, skills, commands, hooks.",
    ),
    RepoSpec(
        repo="claude-code-abc",
        organ="knowledge",
        domain=Domain.KNOWLEDGE,
        language="typescript",
        integration=Integration.ASSET,
        entrypoint="src/",
        mock_ready=True,
        role="Annotated Claude Code internals: tool loop, buddy/dream subsystems, prompts.",
    ),
    RepoSpec(
        repo="system-prompts-and-models-of-ai-tools",
        organ="knowledge",
        domain=Domain.KNOWLEDGE,
        language="text/json",
        integration=Integration.ASSET,
        entrypoint="<Vendor>/*.{txt,json}",
        mock_ready=True,
        role="Corpus of ~31 vendors' system prompts and tool schemas for grounding.",
    ),
    # ---- EMBODIMENT ------------------------------------------------------
    RepoSpec(
        repo="Dji-owner (SkyCore)",
        organ="sky",
        domain=Domain.EMBODIMENT,
        language="python",
        integration=Integration.IN_PROCESS,
        entrypoint="skycore:SimulatorDrone / WaypointMission.execute",
        mock_ready=True,
        role="Unified async drone API over simulator/Tello/MAVLink/DJI with safety + missions.",
    ),
    # ---- ECONOMICS -------------------------------------------------------
    RepoSpec(
        repo="autonomous-trading-engine",
        organ="trade",
        domain=Domain.ECONOMICS,
        language="typescript/deno",
        integration=Integration.HTTP,
        entrypoint="supabase/functions/autonomous-orchestrator",
        mock_ready=True,
        role="Gate.io multi-strategy autonomous trading control center (24 edge functions).",
    ),
    RepoSpec(
        repo="tradingboy",
        organ="trade",
        domain=Domain.ECONOMICS,
        language="python",
        integration=Integration.SUBPROCESS,
        entrypoint="bot",
        mock_ready=True,
        role="Lightweight trading bot companion to the trading engine.",
    ),
    # ---- PERCEPTION ------------------------------------------------------
    RepoSpec(
        repo="ComfyUI",
        organ="vision",
        domain=Domain.PERCEPTION,
        language="python",
        integration=Integration.HTTP,
        entrypoint="http://127.0.0.1:8188/prompt (+ /ws)",
        mock_ready=True,
        role="Node-graph generative media engine (image/video/3D) with stable HTTP/WS API.",
    ),
    # ---- DATAPLANE -------------------------------------------------------
    RepoSpec(
        repo="auto-save-sync (GMIN Nexus)",
        organ="nexus",
        domain=Domain.DATAPLANE,
        language="typescript/deno",
        integration=Integration.HTTP,
        entrypoint="supabase/functions/calc-entry",
        mock_ready=True,
        role="Offline-first mobility/timesheet data plane with anonymous auth + sync queue.",
    ),
    # ---- NETWORK ---------------------------------------------------------
    RepoSpec(
        repo="cors-anywhere",
        organ="net",
        domain=Domain.NETWORK,
        language="node",
        integration=Integration.SUBPROCESS,
        entrypoint="node server.js (:8080)",
        mock_ready=True,
        role="CORS bypass / egress proxy shim for browser-bound organs.",
    ),
)


def repos_for_organ(organ_id: str) -> list[RepoSpec]:
    return [spec for spec in ECOSYSTEM if spec.organ == organ_id]


def repo_names_for_organ(organ_id: str) -> list[str]:
    return [spec.repo for spec in repos_for_organ(organ_id)]


def organ_ids() -> list[str]:
    seen: list[str] = []
    for spec in ECOSYSTEM:
        if spec.organ not in seen:
            seen.append(spec.organ)
    return seen
