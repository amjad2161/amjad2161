"""EVOLUTION — the self-learning / self-improving / self-updating layer.

Three honest mechanisms (no self-rewriting of source code — that is unsafe):

  1. **Experience** — every JARVIS command is recorded to a real sqlite store
     (goal, plan, organs engaged, conclusion, reward), so the organism has a
     durable memory of what it has done and how well it worked.

  2. **Learned routing** — a ``(term -> organ -> score)`` table that the
     commander consults and reinforces after every run, so routing genuinely
     *improves with use* rather than staying a fixed keyword map.

  3. **Evolve loop (24/7)** — pursues standing objectives on an interval,
     records outcomes, periodically **self-reflects** with the brain (the LLM
     reviews recent runs and extracts a lesson into long-term memory), and
     **re-discovers** capabilities (new Ollama models, freshly indexed skills,
     organ health) so it keeps up to date with its changing environment.

    from singularity import build_default_kernel, Jarvis
    from singularity.evolution import Evolver

    async with build_default_kernel() as k:
        ev = Evolver()
        jarvis = Jarvis(k, evolver=ev)
        await jarvis.command("check the market")     # recorded + reinforces routing
        await ev.evolve_forever(k, jarvis,
                                objectives=["scan the market", "audit my skills"],
                                interval_s=600)       # 24/7 self-improvement
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any


class ExperienceStore:
    """Durable sqlite-backed experience + learned-routing memory."""

    def __init__(self, path: str | None = None) -> None:
        path = path or os.environ.get(
            "SINGULARITY_EVOLUTION_DB", str(Path.home() / ".singularity" / "evolution.db"))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript(
            "CREATE TABLE IF NOT EXISTS experience(ts REAL, goal TEXT, plan TEXT,"
            " organs TEXT, conclusion TEXT, reward REAL);"
            "CREATE TABLE IF NOT EXISTS routing(term TEXT, organ TEXT, score REAL,"
            " n INTEGER, PRIMARY KEY(term,organ));"
            "CREATE TABLE IF NOT EXISTS lessons(ts REAL, lesson TEXT);"
        )
        self.db.commit()
        self.path = path

    # -- experience ----------------------------------------------------------
    def record(self, goal: str, plan: list[str], organs: list[str],
               conclusion: str, reward: float) -> None:
        self.db.execute(
            "INSERT INTO experience VALUES (?,?,?,?,?,?)",
            (time.time(), goal, " | ".join(plan), ",".join(organs), conclusion[:1000], reward))
        self.db.commit()

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT ts,goal,organs,conclusion,reward FROM experience"
            " ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [{"ts": r[0], "goal": r[1], "organs": r[2], "conclusion": r[3], "reward": r[4]}
                for r in rows]

    def stats(self) -> dict[str, Any]:
        n, avg = self.db.execute(
            "SELECT COUNT(*), COALESCE(AVG(reward),0) FROM experience").fetchone()
        terms = self.db.execute("SELECT COUNT(DISTINCT term) FROM routing").fetchone()[0]
        return {"runs": n, "avg_reward": round(avg, 3), "learned_terms": terms,
                "lessons": self.db.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]}

    # -- learned routing -----------------------------------------------------
    def reinforce(self, term: str, organ: str, reward: float) -> None:
        row = self.db.execute(
            "SELECT score,n FROM routing WHERE term=? AND organ=?", (term, organ)).fetchone()
        if row:
            score, n = row
            score = (score * n + reward) / (n + 1)
            self.db.execute("UPDATE routing SET score=?,n=? WHERE term=? AND organ=?",
                            (score, n + 1, term, organ))
        else:
            self.db.execute("INSERT INTO routing VALUES (?,?,?,?)", (term, organ, reward, 1))
        self.db.commit()

    def best_organ(self, term: str, *, min_n: int = 2, min_score: float = 0.5) -> str | None:
        row = self.db.execute(
            "SELECT organ,score,n FROM routing WHERE term=? ORDER BY score DESC LIMIT 1",
            (term,)).fetchone()
        if row and row[2] >= min_n and row[1] >= min_score:
            return str(row[0])
        return None

    def add_lesson(self, lesson: str) -> None:
        self.db.execute("INSERT INTO lessons VALUES (?,?)", (time.time(), lesson[:2000]))
        self.db.commit()

    def close(self) -> None:
        try:
            self.db.close()
        except Exception:
            pass


class Evolver:
    """Self-learning controller wrapped around an ExperienceStore."""

    def __init__(self, store: ExperienceStore | None = None) -> None:
        self.store = store or ExperienceStore()

    # learned-routing hooks used by Jarvis ----------------------------------
    def learned_organ(self, term: str) -> str | None:
        return self.store.best_organ(term)

    def observe(self, goal: str, plan: list[str], routed: list[tuple[str, str]],
                results: list[Any], conclusion: str) -> float:
        """Record one command and reinforce routing. Returns the reward."""
        rewards = []
        for (term, organ), res in zip(routed, results):
            ok = isinstance(res, dict) and res.get("ok") is not False and "error" not in res
            r = 1.0 if ok else 0.0
            rewards.append(r)
            if term:
                self.store.reinforce(term, organ, r)
        reward = round(sum(rewards) / len(rewards), 3) if rewards else 0.0
        self.store.record(goal, plan, [o for _, o in routed], conclusion, reward)
        return reward

    # 24/7 self-improvement --------------------------------------------------
    async def reflect(self, kernel: Any) -> str:
        """Have the brain review recent runs and store a lesson in memory."""
        recent = self.store.recent(8)
        if not recent:
            return ""
        digest = "; ".join(f"goal='{r['goal']}' organs={r['organs']} reward={r['reward']}"
                           for r in recent)
        out = await kernel.route("neuro.think", {
            "prompt": "You are JARVIS reflecting on your own recent actions. Given these "
                      f"runs: {digest}. In one sentence, state the single most useful lesson "
                      "to route and act better next time."})
        lesson = str(out.get("thought", "")).strip()
        if lesson:
            self.store.add_lesson(lesson)
            try:  # also persist into the kernel's long-term memory if available
                kernel.memory.remember(lesson, role="evolver", sid="evolution", intent="lesson")
            except Exception:
                pass
        return lesson

    async def rediscover(self, kernel: Any) -> dict[str, Any]:
        """Re-probe the environment so the organism stays up to date."""
        changed: dict[str, Any] = {}
        try:
            from .organs.neuro import NeuroOrgan

            changed["ollama_model"] = NeuroOrgan._probe_ollama()
        except Exception:
            changed["ollama_model"] = None
        try:
            status = kernel.status()
            changed["real_mode"] = status.get("real_mode")
            changed["alive"] = status.get("alive")
        except Exception:
            pass
        return changed

    async def evolve_forever(self, kernel: Any, jarvis: Any, *, objectives: list[str],
                             interval_s: float = 600.0, max_cycles: int | None = None) -> None:
        """The 24/7 loop: pursue standing objectives, reflect, re-discover."""
        import asyncio

        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            cycle += 1
            for goal in objectives:
                try:
                    await jarvis.command(goal)
                except Exception as exc:  # noqa: BLE001 - a bad cycle must not kill the loop
                    print(f"(evolve cycle {cycle}: '{goal}' failed: {type(exc).__name__})")
            lesson = await self.reflect(kernel)
            disc = await self.rediscover(kernel)
            st = self.store.stats()
            print(f"[evolve cycle {cycle}] runs={st['runs']} avg_reward={st['avg_reward']} "
                  f"learned_terms={st['learned_terms']} model={disc.get('ollama_model')} "
                  f"real={disc.get('real_mode')}/9")
            if lesson:
                print(f"  lesson: {lesson[:140]}")
            if max_cycles is not None and cycle >= max_cycles:
                break
            await asyncio.sleep(interval_s)
