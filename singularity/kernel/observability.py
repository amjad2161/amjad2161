"""Observability — a tiny, dependency-free metrics registry.

Inspired by the Prometheus client model (and BRAINIAC's ``prometheus_metrics()``):
counters, gauges and histograms with labels, rendered in the Prometheus text
exposition format. No third-party dependency — the kernel must observe itself
even in the most stripped-down deployment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Mapping

# Default latency buckets (milliseconds) for route timing histograms.
_DEFAULT_BUCKETS = (1.0, 5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0)

_Labels = tuple[tuple[str, str], ...]


def _key(labels: Mapping[str, str] | None) -> _Labels:
    if not labels:
        return ()
    return tuple(sorted((str(k), str(v)) for k, v in labels.items()))


@dataclass
class _Histogram:
    buckets: tuple[float, ...]
    counts: list[int]
    total: float = 0.0
    n: int = 0

    def observe(self, value: float) -> None:
        self.total += value
        self.n += 1
        for i, edge in enumerate(self.buckets):
            if value <= edge:
                self.counts[i] += 1


@dataclass
class Metrics:
    """Thread-safe counter / gauge / histogram registry."""

    _counters: dict[tuple[str, _Labels], float] = field(default_factory=dict)
    _gauges: dict[tuple[str, _Labels], float] = field(default_factory=dict)
    _histos: dict[tuple[str, _Labels], _Histogram] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def inc(self, name: str, labels: Mapping[str, str] | None = None, amount: float = 1.0) -> None:
        key = (name, _key(labels))
        with self._lock:
            self._counters[key] = self._counters.get(key, 0.0) + amount

    def set_gauge(self, name: str, value: float, labels: Mapping[str, str] | None = None) -> None:
        with self._lock:
            self._gauges[(name, _key(labels))] = value

    def observe(
        self,
        name: str,
        value: float,
        labels: Mapping[str, str] | None = None,
        buckets: tuple[float, ...] = _DEFAULT_BUCKETS,
    ) -> None:
        key = (name, _key(labels))
        with self._lock:
            histo = self._histos.get(key)
            if histo is None:
                histo = _Histogram(buckets=buckets, counts=[0] * len(buckets))
                self._histos[key] = histo
            histo.observe(value)

    # -- read views -------------------------------------------------------
    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counters = {self._fmt(n, lab): v for (n, lab), v in self._counters.items()}
            gauges = {self._fmt(n, lab): v for (n, lab), v in self._gauges.items()}
            histos = {
                self._fmt(n, lab): {"count": h.n, "sum": round(h.total, 3),
                                    "avg": round(h.total / h.n, 3) if h.n else 0.0}
                for (n, lab), h in self._histos.items()
            }
        return {"counters": counters, "gauges": gauges, "histograms": histos}

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            for (name, labels), value in sorted(self._counters.items()):
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{self._fmt(name, labels)} {value}")
            for (name, labels), value in sorted(self._gauges.items()):
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{self._fmt(name, labels)} {value}")
            for (name, labels), histo in sorted(self._histos.items()):
                lines.append(f"# TYPE {name} histogram")
                cumulative = 0
                for edge, count in zip(histo.buckets, histo.counts):
                    cumulative += count
                    le_labels = labels + (("le", _num(edge)),)
                    lines.append(f"{self._fmt(name + '_bucket', le_labels)} {cumulative}")
                inf_labels = labels + (("le", "+Inf"),)
                lines.append(f"{self._fmt(name + '_bucket', inf_labels)} {histo.n}")
                lines.append(f"{self._fmt(name + '_sum', labels)} {round(histo.total, 3)}")
                lines.append(f"{self._fmt(name + '_count', labels)} {histo.n}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _fmt(name: str, labels: _Labels) -> str:
        if not labels:
            return name
        inner = ",".join(f'{k}="{v}"' for k, v in labels)
        return f"{name}{{{inner}}}"


def _num(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)
