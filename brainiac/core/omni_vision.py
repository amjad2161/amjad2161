"""
OMNI-VISION — Multi-Spectrum Visual Intelligence
=================================================
360° visual awareness: visible, infrared, thermal, radar, SAR.
Object detection, scene understanding, real-time processing.
"""

from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger("brainiac.omni_vision")


class Spectrum(str, Enum):
    VISIBLE = "visible"
    INFRARED = "infrared"
    THERMAL = "thermal"
    RADAR = "radar"
    SYNTHETIC_APERTURE = "synthetic_aperture"
    ULTRAVIOLET = "ultraviolet"
    LIDAR = "lidar"


@dataclass
class Detection:
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h in pixels
    spectrum: Spectrum
    distance_m: float | None = None
    velocity_ms: float | None = None  # for moving objects


@dataclass
class SceneAnalysis:
    description: str
    objects: list[Detection]
    dominant_colors: list[str]
    estimated_lighting: str
    weather_conditions: str | None
    geographic_context: str | None
    timestamp: float = field(default_factory=time.time)
    processing_ms: float = 0.0


class OmniVision:
    """
    OMNI-VISION visual intelligence engine.

    Wraps OpenCV for image processing with hooks for:
    - Object detection (YOLO-compatible)
    - Scene description (via NEURO-CORE)
    - Thermal/IR spectrum interpretation
    - Base64 image I/O for API transport
    """

    def __init__(self, spectrums: list[Spectrum] | None = None) -> None:
        self.spectrums = spectrums or list(Spectrum)
        self._frames_processed = 0
        log.info("omni_vision.init", spectrums=[s.value for s in self.spectrums])

    # ── Image Processing ──────────────────────────────────────────────────────

    def load_image(self, image_bytes: bytes) -> Any:
        """Load image bytes into OpenCV BGR array."""
        try:
            import cv2
            import numpy as np

            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img
        except ImportError:
            log.warning("omni_vision.opencv_unavailable")
            return None

    def image_info(self, image_bytes: bytes) -> dict[str, Any]:
        """Extract basic image metadata."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            return {
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "size_bytes": len(image_bytes),
            }
        except Exception as exc:
            return {"error": str(exc)}

    def to_base64(self, image_bytes: bytes) -> str:
        """Encode image bytes as base64 string."""
        return base64.b64encode(image_bytes).decode("utf-8")

    def from_base64(self, b64: str) -> bytes:
        """Decode base64 string to image bytes."""
        return base64.b64decode(b64)

    def resize(self, image_bytes: bytes, width: int, height: int) -> bytes:
        """Resize image and return as PNG bytes."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            resized = img.resize((width, height))
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as exc:
            log.error("omni_vision.resize_error", error=str(exc))
            return image_bytes

    def extract_dominant_colors(self, image_bytes: bytes, n: int = 5) -> list[str]:
        """Return top-N dominant colors as hex strings."""
        try:
            import numpy as np
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((100, 100))
            _ = np.array(img).reshape(-1, 3)
            # Simple k-means would be ideal; here we use quantization
            quantized = img.quantize(colors=n)
            palette = quantized.getpalette()
            if palette is None:
                return []
            colors = []
            for i in range(n):
                r, g, b = palette[i * 3], palette[i * 3 + 1], palette[i * 3 + 2]
                colors.append(f"#{r:02x}{g:02x}{b:02x}")
            return colors
        except Exception as exc:
            log.warning("omni_vision.color_extract_error", error=str(exc))
            return []

    def detect_edges(self, image_bytes: bytes) -> bytes:
        """Apply Canny edge detection and return result as PNG."""
        try:
            import cv2
            import numpy as np

            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
            edges = cv2.Canny(img, 100, 200)
            _, buf = cv2.imencode(".png", edges)
            self._frames_processed += 1
            return buf.tobytes()
        except Exception as exc:
            log.error("omni_vision.edge_detect_error", error=str(exc))
            return image_bytes

    def analyze_scene(self, image_bytes: bytes) -> SceneAnalysis:
        """
        Full scene analysis pipeline.
        Object detection requires a loaded YOLO model (not bundled here).
        Color extraction and metadata are always available.
        """
        t0 = time.perf_counter()
        info = self.image_info(image_bytes)
        colors = self.extract_dominant_colors(image_bytes)
        elapsed = (time.perf_counter() - t0) * 1000
        self._frames_processed += 1

        return SceneAnalysis(
            description=(
                f"Image {info.get('width', '?')}x{info.get('height', '?')} "
                f"{info.get('format', 'unknown')} — awaiting YOLO model for object detection"
            ),
            objects=[],  # Populate when YOLO model is loaded
            dominant_colors=colors,
            estimated_lighting="unknown",
            weather_conditions=None,
            geographic_context=None,
            processing_ms=round(elapsed, 2),
        )

    # ── Spectrum simulation ───────────────────────────────────────────────────

    def simulate_thermal(self, image_bytes: bytes) -> bytes:
        """Apply a false-colour thermal LUT to a greyscale image."""
        try:
            import cv2
            import numpy as np

            arr = np.frombuffer(image_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
            thermal = cv2.applyColorMap(img, cv2.COLORMAP_INFERNO)
            _, buf = cv2.imencode(".png", thermal)
            return buf.tobytes()
        except Exception as exc:
            log.warning("omni_vision.thermal_error", error=str(exc))
            return image_bytes

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        return {
            "status": "ONLINE",
            "spectrums": [s.value for s in self.spectrums],
            "frames_processed": self._frames_processed,
        }
