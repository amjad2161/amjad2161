"""VISION — perception & creative media.

Federates: ComfyUI (node-graph media engine on :8188) plus BRAINIAC's
OmniVision/CreativeEngine. In ``REAL`` mode it submits workflows to the ComfyUI
HTTP API; in ``MOCK`` mode it emits a valid ComfyUI-style workflow graph, image
metadata and a deterministic SVG badge so creative steps always produce an
inspectable artifact.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..kernel.contracts import Capability, Domain
from .base import BaseOrgan


class VisionOrgan(BaseOrgan):
    id = "vision"
    domain = Domain.PERCEPTION
    title = "OmniVision — perception & creation"
    vision = "Generate and understand media through a unified graph-based perception engine."
    capabilities = (
        Capability("vision.generate", "Build a ComfyUI workflow for a text-to-image job.",
                   {"prompt": "str", "width": "int?", "height": "int?", "steps": "int?"}),
        Capability("vision.analyze", "Summarise metadata for an image (size/colors).",
                   {"width": "int?", "height": "int?", "format": "str?"}),
        Capability("vision.creative", "Produce a deterministic SVG badge for a label.",
                   {"text": "str", "color": "str?"}),
    )

    async def _attach_real(self) -> None:
        import os
        import urllib.request

        base = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
        with urllib.request.urlopen(f"{base}/system_stats", timeout=1.5):  # noqa: S310
            pass
        self._backend = base
        self._detail["comfyui"] = base

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "vision.generate":
            return self._generate(payload)
        if intent == "vision.analyze":
            w = int(payload.get("width", 1024))
            h = int(payload.get("height", 1024))
            return {
                "width": w,
                "height": h,
                "format": str(payload.get("format", "png")),
                "megapixels": round(w * h / 1_000_000, 2),
                "aspect_ratio": round(w / h, 3) if h else 0.0,
                "dominant_colors": ["#2b2d42", "#8d99ae", "#edf2f4"],
            }
        if intent == "vision.creative":
            return self._svg_badge(str(payload.get("text", "SINGULARITY")), payload.get("color"))
        raise AssertionError("unreachable")  # pragma: no cover

    def _generate(self, payload: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get("prompt", "a luminous neural galaxy"))
        width = int(payload.get("width", 1024))
        height = int(payload.get("height", 1024))
        steps = int(payload.get("steps", 20))
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        workflow = {
            "3": {"class_type": "KSampler",
                  "inputs": {"seed": seed, "steps": steps, "cfg": 7.0,
                             "sampler_name": "euler", "scheduler": "normal",
                             "model": ["4", 0], "positive": ["6", 0],
                             "negative": ["7", 0], "latent_image": ["5", 0]}},
            "4": {"class_type": "CheckpointLoaderSimple",
                  "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
            "5": {"class_type": "EmptyLatentImage",
                  "inputs": {"width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode",
                  "inputs": {"text": "blurry, low quality", "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage",
                  "inputs": {"filename_prefix": "singularity", "images": ["8", 0]}},
        }
        return {
            "prompt": prompt,
            "seed": seed,
            "workflow": workflow,
            "endpoint": "POST /prompt",
            "_usd": 0.0,
        }

    def _svg_badge(self, text: str, color: str | None) -> dict[str, Any]:
        fill = color or "#" + hashlib.sha256(text.encode()).hexdigest()[:6]
        width = 12 * max(len(text), 4) + 24
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="36">'
            f'<rect rx="6" width="{width}" height="36" fill="{fill}"/>'
            f'<text x="12" y="24" font-family="monospace" font-size="16" fill="#fff">'
            f"{text}</text></svg>"
        )
        return {"text": text, "color": fill, "svg": svg, "width": width, "height": 36}
