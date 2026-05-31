"""CONTROL — digital embodiment: browser / GUI / device automation.

Federates the 2026 computer-use frontier the user surfaced: UI-TARS-desktop
(multimodal GUI-agent stack), auto-browser / autobrowse, docker-android, and
localsend (P2P transfer). It gives the organism hands in the digital world.

* ``control.browse`` performs a *real* HTTP GET (stdlib urllib) — genuine page
  fetch with title/status/text — and degrades honestly when egress is blocked.
* ``control.plan_actions`` decomposes a UI goal into a UI-TARS-style action
  trace (navigate/click/type/scroll/extract).
* ``control.transfer`` produces a localsend-style P2P transfer session spec.
"""

from __future__ import annotations

import asyncio
import hashlib
import re
from typing import Any
from urllib.parse import urlparse

from ..kernel.contracts import Capability, Domain
from ..security.netguard import SSRFError, safe_fetch
from .base import BaseOrgan

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")
_ACTION_VERBS = ("navigate", "locate", "click", "type", "scroll", "extract", "verify")


class ControlOrgan(BaseOrgan):
    id = "control"
    domain = Domain.ACTUATION
    title = "Control — browser / GUI / device automation"
    vision = "Give the organism hands: drive browsers, GUIs and devices toward a goal."
    invoke_timeout_s = 220.0  # control.act runs a screenshot -> vision -> LLM loop
    capabilities = (
        Capability("control.browse", "Fetch a URL (real HTTP GET): status, title, text snippet.",
                   {"url": "str"}),
        Capability("control.plan_actions", "Decompose a UI goal into an action trace.",
                   {"goal": "str", "url": "str?", "max_steps": "int?"}),
        Capability("control.transfer", "Build a localsend-style P2P transfer session spec.",
                   {"filename": "str", "size_bytes": "int?", "peer": "str?"}),
        Capability("control.screen_info", "Perceive: real screen size + cursor position.", {}),
        Capability("control.screenshot", "Perceive: capture the screen to a PNG.",
                   {"name": "str?"}),
        Capability("control.speak", "Voice: speak text aloud (Windows SAPI / pyttsx3).",
                   {"text": "str"}),
        Capability("control.act", "Computer-use agent: perceive the screen and decide the next "
                   "UI action toward a goal (UI-TARS/Agent-S); keyboard execution when execute=true.",
                   {"goal": "str", "execute": "bool?"}),
    )

    async def _attach_real(self) -> None:
        # REAL when the organ can actually reach the network (egress available).
        def _probe() -> bool:
            import socket

            try:
                with socket.create_connection(("1.1.1.1", 443), timeout=1.5):
                    return True
            except OSError:
                return False

        if not await asyncio.to_thread(_probe):
            raise RuntimeError("no network egress")
        self._backend = {"egress": True}
        self._detail["egress"] = True

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "control.browse":
            return await self._browse(str(payload.get("url", "")))
        if intent == "control.plan_actions":
            return self._plan_actions(str(payload.get("goal", "")), payload.get("url"),
                                      int(payload.get("max_steps", 6)))
        if intent == "control.transfer":
            return self._transfer(str(payload.get("filename", "file.bin")),
                                  int(payload.get("size_bytes", 1024)), str(payload.get("peer", "")))
        if intent == "control.screen_info":
            return await asyncio.to_thread(self._screen_info)
        if intent == "control.screenshot":
            return await asyncio.to_thread(self._screenshot, str(payload.get("name", "screenshot")))
        if intent == "control.speak":
            return await asyncio.to_thread(self._speak, str(payload.get("text", "")))
        if intent == "control.act":
            return await asyncio.to_thread(
                self._act, str(payload.get("goal", "")), bool(payload.get("execute", False)))
        raise AssertionError("unreachable")  # pragma: no cover

    def _act(self, goal: str, execute: bool) -> dict[str, Any]:
        """Computer-use agent (UI-TARS / Agent-S): PERCEIVE the real screen with a
        multimodal model, DECIDE the next UI action with the reasoning model, and
        (only when execute=true) carry out safe keyboard actions. Clicking is
        proposed but needs pixel coordinates a description model can't give
        reliably — reported honestly rather than guessed."""
        import base64
        import io
        import json
        import os
        import urllib.request

        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

        def _ollama(body: dict[str, Any], timeout: float) -> str | None:
            try:
                req = urllib.request.Request(
                    f"{host}/api/generate", data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return str(json.loads(r.read()).get("response", "")).strip() or None
            except Exception:
                return None

        # 1) PERCEIVE — screenshot + a vision model description.
        try:
            import pyautogui

            from PIL import Image  # noqa: F401  (ensures Pillow is present)
        except Exception:
            return {"ok": False, "error": "pyautogui/Pillow not available", "_backend": "builtin"}
        try:
            from .neuro import NeuroOrgan
            from .vision import VisionOrgan
        except Exception:
            return {"ok": False, "error": "organ imports failed", "_backend": "builtin"}

        text_model = NeuroOrgan._probe_ollama()
        vision_model = VisionOrgan._probe_ollama_vision()
        if not text_model:
            return {"ok": False, "error": "no local LLM (Ollama) for decision", "_backend": "builtin"}

        img = pyautogui.screenshot()
        img.thumbnail((1024, 1024))
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        screen = "(no vision model)"
        if vision_model:
            screen = _ollama({"model": vision_model, "images": [b64], "stream": False,
                              "prompt": "Briefly describe this screen and its main clickable "
                                        "elements (apps, buttons, fields).",
                              "options": {"num_predict": 160}}, 170) or screen

        # 2) DECIDE — the reasoning model proposes the single next action.
        raw = _ollama({"model": text_model, "stream": False, "format": "json",
                       "prompt": f"Goal: {goal}\nScreen: {screen}\nDecide the SINGLE next UI "
                                 'action. Respond ONLY JSON: {"action":"click|type|press|'
                                 'hotkey|scroll|done","target":"...","text":"...","reason":"..."}',
                       "options": {"num_predict": 160}}, 120)
        action: dict[str, Any] = {}
        try:
            action = json.loads(raw) if raw else {}
        except Exception:
            action = {"action": "done", "reason": (raw or "")[:120]}

        # 3) EXECUTE — only safe keyboard actions, only when asked.
        executed = None
        kind = str(action.get("action", "")).lower()
        if execute and kind in ("type", "press", "hotkey", "scroll"):
            try:
                if kind == "type":
                    pyautogui.write(str(action.get("text", "")), interval=0.02)
                elif kind == "press":
                    pyautogui.press(str(action.get("target") or action.get("text", "enter")))
                elif kind == "hotkey":
                    keys = str(action.get("target", "")).replace(" ", "").split("+")
                    pyautogui.hotkey(*[k for k in keys if k])
                elif kind == "scroll":
                    pyautogui.scroll(-300)
                executed = kind
            except Exception as exc:  # noqa: BLE001
                executed = f"failed: {type(exc).__name__}"
        note = None
        if kind == "click" and execute:
            note = "click proposed but not executed — needs pixel coordinates a description model cannot give"
        return {"ok": True, "goal": goal, "screen_summary": screen[:200],
                "proposed_action": action, "executed": executed, "note": note,
                "vision_model": vision_model, "text_model": text_model,
                "_backend": "ui-tars-loop"}

    # -- real perception + voice (merged from the local JARVIS computer-use) ---
    def _screen_info(self) -> dict[str, Any]:
        try:
            import pyautogui
        except Exception:
            return {"ok": False, "error": "pyautogui not available on this host",
                    "_backend": "builtin"}
        w, h = pyautogui.size()
        x, y = pyautogui.position()
        return {"ok": True, "screen": {"width": int(w), "height": int(h)},
                "cursor": {"x": int(x), "y": int(y)}, "_backend": "pyautogui"}

    def _screenshot(self, name: str) -> dict[str, Any]:
        import tempfile
        from pathlib import Path

        try:
            import pyautogui
        except Exception:
            return {"ok": False, "error": "pyautogui not available on this host",
                    "_backend": "builtin"}
        if not name.lower().endswith(".png"):
            name += ".png"
        dest = Path(tempfile.gettempdir()) / "singularity-control" / Path(name).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        img = pyautogui.screenshot()
        img.save(str(dest))
        return {"ok": True, "path": str(dest),
                "size": {"width": img.width, "height": img.height}, "_backend": "pyautogui"}

    def _speak(self, text: str) -> dict[str, Any]:
        if not text:
            return {"ok": False, "error": "no text", "_backend": "builtin"}
        try:  # Windows SAPI — no install needed
            import win32com.client

            win32com.client.Dispatch("SAPI.SpVoice").Speak(text)
            return {"ok": True, "spoke": text[:200], "_backend": "sapi"}
        except Exception:
            pass
        try:  # cross-platform fallback
            import pyttsx3

            engine = pyttsx3.init()
            engine.say(text)
            engine.runAndWait()
            return {"ok": True, "spoke": text[:200], "_backend": "pyttsx3"}
        except Exception:
            return {"ok": False, "error": "no TTS backend (SAPI/pyttsx3) on this host",
                    "_backend": "builtin"}

    async def _browse(self, url: str) -> dict[str, Any]:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return {"url": url, "ok": False, "error": "invalid url", "_backend": "builtin"}

        def _get() -> dict[str, Any]:
            # SSRF-guarded fetch: resolves the host and rejects loopback,
            # private, link-local and cloud-metadata targets, and re-validates
            # after every redirect hop. Never reaches 169.254.169.254 / 127.0.0.1.
            try:
                return {**safe_fetch(url, max_bytes=200_000, timeout=8),
                        "_mode": self._mode.value}
            except SSRFError as exc:
                return {"url": url, "ok": False, "error": f"blocked: {exc}",
                        "_backend": "builtin", "_mode": self._mode.value}

        try:
            return await asyncio.to_thread(_get)
        except Exception as exc:  # noqa: BLE001 - egress blocked → honest fallback
            return {"url": url, "ok": False, "error": f"{type(exc).__name__}",
                    "note": "real fetch failed (no egress?); would GET via the guarded fetcher when reachable",
                    "_backend": "mock"}

    def _plan_actions(self, goal: str, url: str | None, max_steps: int) -> dict[str, Any]:
        max_steps = max(2, min(max_steps, 12))
        targets = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", goal.lower())[:max_steps]
        steps = []
        if url:
            steps.append({"step": 1, "action": "navigate", "target": url})
        for i, tok in enumerate(targets, start=len(steps) + 1):
            verb = _ACTION_VERBS[i % len(_ACTION_VERBS)]
            steps.append({"step": i, "action": verb, "target": tok})
            if len(steps) >= max_steps:
                break
        steps.append({"step": len(steps) + 1, "action": "verify", "target": "goal satisfied"})
        return {"goal": goal, "action_space": list(_ACTION_VERBS), "steps": steps,
                "count": len(steps), "_backend": "builtin"}

    def _transfer(self, filename: str, size_bytes: int, peer: str) -> dict[str, Any]:
        session = hashlib.sha256(f"{filename}:{size_bytes}:{peer}".encode()).hexdigest()[:16]
        pin = int(session[:6], 16) % 1_000_000
        chunk = 64 * 1024
        return {
            "protocol": "localsend-v2",
            "session": session,
            "pin": f"{pin:06d}",
            "filename": filename,
            "size_bytes": size_bytes,
            "chunks": max(1, (size_bytes + chunk - 1) // chunk),
            "chunk_bytes": chunk,
            "peer": peer or "broadcast",
            "_backend": "builtin",
        }
