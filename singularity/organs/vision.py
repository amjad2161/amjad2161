"""VISION — perception & creative media.

Federates: ComfyUI (node-graph media engine on :8188) plus BRAINIAC's
OmniVision/CreativeEngine. In ``REAL`` mode it submits workflows to the ComfyUI
HTTP API; in ``MOCK`` mode it emits a valid ComfyUI-style workflow graph, image
metadata and a deterministic SVG badge so creative steps always produce an
inspectable artifact.
"""

from __future__ import annotations

import base64
import hashlib
import math
import struct
import zlib
from typing import Any

from ..kernel.contracts import Capability, Domain
from ..security.safe_render import safe_color, svg_badge
from .base import BaseOrgan


class VisionOrgan(BaseOrgan):
    id = "vision"
    domain = Domain.PERCEPTION
    title = "OmniVision — perception & creation"
    vision = "Generate and understand media through a unified graph-based perception engine."
    # Real multimodal image understanding (local llava) can take ~30s.
    invoke_timeout_s = 120.0
    capabilities = (
        Capability("vision.generate", "Build a ComfyUI workflow for a text-to-image job.",
                   {"prompt": "str", "width": "int?", "height": "int?", "steps": "int?"}),
        Capability("vision.analyze", "Summarise metadata for an image (size/colors).",
                   {"width": "int?", "height": "int?", "format": "str?"}),
        Capability("vision.creative", "Produce a real PNG image + SVG badge for a label.",
                   {"text": "str", "color": "str?", "size": "int?"}),
        Capability("vision.audio", "Synthesize a real WAV melody from a prompt (ACE-Step style).",
                   {"prompt": "str", "seconds": "float?"}),
        Capability("vision.splat", "Generate a 3D Gaussian-splat scene spec (SuperSplat style).",
                   {"prompt": "str", "count": "int?"}),
        Capability("vision.face_track", "See and locate a face via the webcam (robot-head eyes).",
                   {"camera": "int?"}),
        Capability("vision.watch", "Watch the camera for presence + motion (frigate/DeepCamera style).",
                   {"camera": "int?", "frames": "int?"}),
        Capability("vision.colors", "OmniVision: extract dominant colors from an image (k-means).",
                   {"image_path": "str?", "image_b64": "str?", "k": "int?"}),
    )

    async def _attach_real(self) -> None:
        import os
        import urllib.request

        # 1) ComfyUI (full generative media) if its server is reachable.
        base = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
        try:
            with urllib.request.urlopen(f"{base}/system_stats", timeout=1.5):  # noqa: S310
                pass
            self._backend = {"comfyui": base}
            self._detail["comfyui"] = base
            return
        except Exception:
            pass
        # 2) Local multimodal LLM (real image UNDERSTANDING) via Ollama llava.
        vmodel = self._probe_ollama_vision()
        if vmodel is None:
            raise RuntimeError("no real vision backend (ComfyUI / multimodal LLM) available")
        self._backend = {"ollama_vision": vmodel}
        self._detail["ollama_vision"] = vmodel

    @staticmethod
    def _probe_ollama_vision() -> str | None:
        import json
        import os
        import urllib.request

        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        try:
            with urllib.request.urlopen(f"{host}/api/tags", timeout=2) as r:
                models = json.loads(r.read()).get("models", [])
        except Exception:
            return None
        for m in models:
            name = (m.get("name") or "").lower()
            if any(t in name for t in ("llava", "vision", "bakllava", "moondream")):
                return str(m.get("name"))
        return None

    def _analyze_real(self, image_b64: str, prompt: str) -> str | None:
        import json
        import os
        import urllib.request

        model = (self._backend or {}).get("ollama_vision")
        if not model:
            return None
        # Downscale large images so a local multimodal model responds in budget.
        try:
            import base64 as _b64
            import io

            from PIL import Image  # Pillow ships with pyautogui

            img = Image.open(io.BytesIO(_b64.b64decode(image_b64)))
            img.thumbnail((1024, 1024))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            image_b64 = _b64.b64encode(buf.getvalue()).decode()
        except Exception:
            pass
        host = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        body = {"model": model, "prompt": prompt or "Describe this image in detail.",
                "images": [image_b64], "stream": False, "options": {"num_predict": 200}}
        try:
            req = urllib.request.Request(
                f"{host}/api/generate", data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=110) as r:
                return str(json.loads(r.read()).get("response", "")).strip() or None
        except Exception:
            return None

    async def _invoke(self, intent: str, payload: dict[str, Any]) -> dict[str, Any]:
        if intent == "vision.generate":
            return self._generate(payload)
        if intent == "vision.analyze":
            import asyncio
            import base64

            img_b64 = payload.get("image_b64")
            path = payload.get("image_path")
            if not img_b64 and path:
                try:
                    with open(str(path), "rb") as fh:
                        img_b64 = base64.b64encode(fh.read()).decode()
                except Exception:
                    img_b64 = None
            if img_b64 and (self._backend or {}).get("ollama_vision"):
                # REAL multimodal understanding of an actual image (e.g. a
                # control.screenshot) via the local llava model.
                desc = await asyncio.to_thread(
                    self._analyze_real, str(img_b64),
                    str(payload.get("prompt", "Describe this image in detail.")))
                if desc:
                    model = self._backend["ollama_vision"]
                    return {"description": desc, "model": model,
                            "_backend": f"ollama:{model}", "_mode": "real"}
            w = int(payload.get("width", 1024))
            h = int(payload.get("height", 1024))
            return {
                "width": w,
                "height": h,
                "format": str(payload.get("format", "png")),
                "megapixels": round(w * h / 1_000_000, 2),
                "aspect_ratio": round(w / h, 3) if h else 0.0,
                "dominant_colors": ["#2b2d42", "#8d99ae", "#edf2f4"],
                "_backend": "builtin", "_mode": "mock",
            }
        if intent == "vision.creative":
            return self._creative(str(payload.get("text", "SINGULARITY")), payload.get("color"),
                                  int(payload.get("size", 96)))
        if intent == "vision.audio":
            return self._audio(str(payload.get("prompt", "singularity")),
                               float(payload.get("seconds", 1.5)))
        if intent == "vision.splat":
            return self._splat(str(payload.get("prompt", "nebula")), int(payload.get("count", 24)))
        if intent == "vision.face_track":
            import asyncio

            return await asyncio.to_thread(self._face_track, int(payload.get("camera", 0)))
        if intent == "vision.watch":
            import asyncio

            return await asyncio.to_thread(
                self._watch, int(payload.get("camera", 0)), int(payload.get("frames", 6)))
        if intent == "vision.colors":
            import asyncio

            return await asyncio.to_thread(
                self._colors, payload.get("image_path"), payload.get("image_b64"),
                int(payload.get("k", 5)))
        raise AssertionError("unreachable")  # pragma: no cover

    def _colors(self, image_path: Any, image_b64: Any, k: int) -> dict[str, Any]:
        """OmniVision: REAL dominant-color extraction via k-means (cv2)."""
        import base64

        try:
            import cv2
            import numpy as np
        except Exception:
            return {"ok": False, "error": "opencv (cv2) not available", "_backend": "builtin"}
        try:
            if image_b64:
                buf = np.frombuffer(base64.b64decode(str(image_b64)), dtype=np.uint8)
                img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            elif image_path:
                img = cv2.imread(str(image_path))
            else:
                return {"ok": False, "error": "provide image_path or image_b64", "_backend": "builtin"}
            if img is None:
                return {"ok": False, "error": "could not decode image", "_backend": "builtin"}
            small = cv2.resize(img, (96, 96))
            data = small.reshape(-1, 3).astype(np.float32)
            k = max(2, min(k, 8))
            crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
            kmeans = getattr(cv2, "kmeans")  # noqa: B009 - avoid strict cv2 stub overloads
            _, labels, centers = kmeans(data, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
            counts = np.bincount(labels.flatten(), minlength=k)
            order = np.argsort(-counts)
            colors = []
            for i in order:
                b, g, r = (int(c) for c in centers[i])  # cv2 is BGR
                colors.append({"hex": f"#{r:02x}{g:02x}{b:02x}",
                               "weight": round(float(counts[i]) / len(labels), 3)})
            return {"ok": True, "dominant_colors": colors, "_backend": "omnivision-kmeans"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "_backend": "builtin"}

    def _watch(self, camera: int, frames: int) -> dict[str, Any]:
        """REAL: watch the camera for a short burst and report PRESENCE + MOTION
        — the distilled concept behind frigate / DeepCamera (an AI camera that
        notices movement and people). Motion via frame-differencing (no model);
        presence via the built-in face cascade. Honest fallback without cv2/cam."""
        try:
            import cv2
            import numpy as np
        except Exception:
            return {"ok": False, "error": "opencv (cv2) not available", "_backend": "builtin"}
        cap = None
        try:
            cap = cv2.VideoCapture(camera)
            grays: list[Any] = []
            last = None
            for _ in range(max(2, min(frames, 30))):
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                last = frame
                grays.append(cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (21, 21), 0))
            if len(grays) < 2 or last is None:
                return {"ok": False, "error": f"insufficient frames from camera {camera}",
                        "_backend": "builtin"}
            # motion = mean abs diff across consecutive frames (0..255 -> 0..1)
            diffs = [float(np.mean(cv2.absdiff(grays[i], grays[i - 1]))) for i in range(1, len(grays))]
            level = round(max(diffs) / 255.0, 4)
            moved = level > 0.02
            haar = getattr(cv2, "data").haarcascades  # noqa: B009
            cascade = cv2.CascadeClassifier(haar + "haarcascade_frontalface_default.xml")
            faces = cascade.detectMultiScale(grays[-1], 1.1, 5, minSize=(60, 60))
            present = len(faces) > 0
            return {"ok": True, "present": present, "faces": int(len(faces)),
                    "motion": moved, "motion_level": level, "frames": len(grays),
                    "alert": bool(moved or present),
                    "summary": ("person present" if present else
                                "motion detected" if moved else "all quiet"),
                    "_backend": "cv2-watch"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "_backend": "builtin"}
        finally:
            if cap is not None:
                cap.release()

    def _face_track(self, camera: int) -> dict[str, Any]:
        """REAL: capture one webcam frame and locate the strongest face — the
        software twin of the robot head's eye-tracking (cv2 built-in cascade, no
        model file). Returns the normalized look-vector the 'eyes' should follow."""
        try:
            import cv2
        except Exception:
            return {"ok": False, "error": "opencv (cv2) not available", "_backend": "builtin"}
        cap = None
        try:
            cap = cv2.VideoCapture(camera)
            ok, frame = (cap.read() if cap is not None else (False, None))
            if not ok or frame is None:
                return {"ok": False, "error": f"no frame from camera {camera}", "_backend": "builtin"}
            h, w = frame.shape[:2]
            haar_dir = getattr(cv2, "data").haarcascades  # noqa: B009
            cascade = cv2.CascadeClassifier(haar_dir + "haarcascade_frontalface_default.xml")
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
            if len(faces) == 0:
                return {"ok": True, "found": False, "frame": {"w": int(w), "h": int(h)},
                        "look": {"x": 0.0, "y": 0.0}, "_backend": "cv2-facetrack"}
            fx, fy, fw, fh = max(faces, key=lambda b: int(b[2]) * int(b[3]))  # strongest (largest)
            cx, cy = int(fx + fw / 2), int(fy + fh / 2)
            # normalised look-vector in [-1,1] (where the eyes should point)
            look_x = round((cx - w / 2) / (w / 2), 3)
            look_y = round((cy - h / 2) / (h / 2), 3)
            return {"ok": True, "found": True, "frame": {"w": int(w), "h": int(h)},
                    "face": {"x": cx, "y": cy, "w": int(fw), "h": int(fh)},
                    "look": {"x": look_x, "y": look_y},
                    "size_pct": round(100 * fw * fh / (w * h), 1), "_backend": "cv2-facetrack"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "_backend": "builtin"}
        finally:
            if cap is not None:
                cap.release()

    def _audio(self, prompt: str, seconds: float) -> dict[str, Any]:
        seconds = max(0.25, min(seconds, 8.0))
        rate = 16000
        digest = hashlib.sha256(prompt.encode()).digest()
        # A short procedural melody — a real, playable WAV (no deps).
        scale = [261.63, 293.66, 329.63, 392.0, 440.0, 523.25]  # C major pentatonish
        n = int(rate * seconds)
        frames = bytearray()
        notes = max(1, int(seconds * 4))
        for i in range(n):
            note = scale[digest[(i * notes // n) % len(digest)] % len(scale)]
            t = i / rate
            env = min(1.0, 8 * (1 - (i % (n // notes)) / (n // notes)))  # simple decay
            sample = int(0.3 * env * 32767 * math.sin(2 * math.pi * note * t))
            frames += struct.pack("<h", max(-32768, min(32767, sample)))
        wav = _encode_wav(bytes(frames), rate)
        return {"prompt": prompt, "seconds": round(seconds, 2), "sample_rate": rate,
                "wav_base64": base64.b64encode(wav).decode(), "wav_bytes": len(wav),
                "_backend": "builtin-wav"}

    def _splat(self, prompt: str, count: int) -> dict[str, Any]:
        count = max(1, min(count, 512))
        digest = hashlib.sha256(prompt.encode()).digest()
        splats = []
        for i in range(count):
            d = digest[i % len(digest)]
            ang = 2 * math.pi * i / count
            r = 1.0 + (d / 255)
            splats.append({
                "p": [round(r * math.cos(ang), 3), round((d - 128) / 128, 3),
                      round(r * math.sin(ang), 3)],
                "scale": round(0.02 + (d % 16) / 200, 3),
                "rgba": [d, (d * 3) & 255, (d * 7) & 255, 255],
            })
        return {"prompt": prompt, "format": "gaussian-splat", "count": len(splats),
                "splats": splats, "_backend": "builtin-splat"}

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

    def _creative(self, text: str, color: str | None, size: int) -> dict[str, Any]:
        # XSS / SVG-injection safe: `text` is XML-escaped and `color` is validated
        # against a strict allowlist before entering the SVG. A value like
        # "</text><script>…" can no longer break out of the markup.
        fill = safe_color(color, fallback="#" + hashlib.sha256(text.encode()).hexdigest()[:6])
        svg = svg_badge(text, fill)
        size = max(16, min(size, 256))
        png = _render_png(text, size)
        return {
            "text": text,
            "color": fill,
            "svg": svg,
            "png_base64": base64.b64encode(png).decode(),
            "png_bytes": len(png),
            "width": size,
            "height": size,
            "_backend": "builtin-raster",
        }


def _render_png(seed_text: str, size: int) -> bytes:
    """Generate a genuine, openable PNG of deterministic generative art."""

    digest = hashlib.sha256(seed_text.encode()).digest()
    a, b, c = digest[0] / 255, digest[1] / 255, digest[2] / 255
    fr, fg, fb = digest[3], digest[4], digest[5]
    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            u, v = x / size, y / size
            r = int(127 + 127 * math.sin((u * (2 + a * 6) + b) * math.pi))
            g = int(127 + 127 * math.sin((v * (2 + c * 6) + a) * math.pi))
            bl = int(127 + 127 * math.sin(((u + v) * (1 + b * 4)) * math.pi))
            pixels += bytes(((r ^ fr) & 255, (g ^ fg) & 255, (bl ^ fb) & 255))
    return _encode_png(size, size, bytes(pixels))


def _encode_wav(frames: bytes, rate: int) -> bytes:
    """Minimal 16-bit mono PCM WAV encoder (dependency-free)."""

    data_len = len(frames)
    return (
        b"RIFF" + struct.pack("<I", 36 + data_len) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data" + struct.pack("<I", data_len) + frames
    )


def _encode_png(width: int, height: int, rgb: bytes) -> bytes:
    """Minimal, dependency-free 8-bit RGB PNG encoder."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    stride = width * 3
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type: none
        raw += rgb[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
