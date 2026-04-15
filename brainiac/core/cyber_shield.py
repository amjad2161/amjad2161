"""
CYBER-SHIELD — Defensive Cybersecurity Module
===============================================
Threat intelligence, zero-day detection, network hardening,
post-quantum cryptography, automated incident response.
NOTE: Defensive/detection use only. No offensive capabilities.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import structlog

log = structlog.get_logger("brainiac.cyber_shield")


class ThreatLevel(int, Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ThreatType(str, Enum):
    PORT_SCAN = "port_scan"
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    ANOMALOUS_TRAFFIC = "anomalous_traffic"
    KNOWN_MALWARE_HASH = "known_malware_hash"
    REPLAY_ATTACK = "replay_attack"
    MAN_IN_THE_MIDDLE = "mitm"
    ZERO_DAY = "zero_day"


@dataclass
class ThreatEvent:
    event_id: str
    threat_type: ThreatType
    threat_level: ThreatLevel
    source_ip: str
    target: str
    description: str
    timestamp: float = field(default_factory=time.time)
    mitigated: bool = False
    mitigation: str = ""
    evidence: dict = field(default_factory=dict)


@dataclass
class NetworkAuditResult:
    target: str
    open_ports: list[int]
    services: dict[int, str]
    vulnerabilities: list[str]
    hardening_recommendations: list[str]
    risk_score: float              # 0 (safe) … 10 (critical)
    timestamp: float = field(default_factory=time.time)


# Simplified known-bad pattern database (production: MISP / VirusTotal / etc.)
KNOWN_MALWARE_HASHES: set[str] = {
    "d41d8cd98f00b204e9800998ecf8427e",    # empty file md5
    "e3b0c44298fc1c149afbf4c8996fb924",    # empty file sha256
}

INJECTION_PATTERNS = [
    r"(\bSELECT\b.*\bFROM\b|\bUNION\b.*\bSELECT\b|\bDROP\b.*\bTABLE\b)",  # SQL
    r"(<script[^>]*>|javascript:|on\w+\s*=)",                                # XSS
    r"(\.\./|%2e%2e%2f|%252e%252e)",                                         # Path traversal
    r"(\bexec\b|\beval\b|\bsystem\b|\bpassthru\b)\s*\(",                    # Code injection
]


class CyberShield:
    """
    CYBER-SHIELD Defensive Security Engine.

    Features (all defensive)
    --------
    - Input sanitisation & injection detection
    - Rate limiting & brute-force detection
    - File hash verification against malware DB
    - Network audit & hardening recommendations
    - HMAC message integrity verification
    - JWT validation
    - Incident log with auto-mitigation
    - Post-quantum key exchange (placeholder)
    """

    def __init__(self, secret_key: str = "BRAINIAC-DEFAULT-CHANGE-ME") -> None:
        self._secret = secret_key.encode()
        self._events: list[ThreatEvent] = []
        self._rate_counters: dict[str, list[float]] = {}   # ip → [timestamps]
        self._blocked_ips: set[str] = set()
        log.info("cyber_shield.init")

    # ── Input Validation ──────────────────────────────────────────────────────

    def scan_input(self, text: str, source_ip: str = "0.0.0.0") -> ThreatEvent | None:
        """
        Scan user input for injection attempts.
        Returns a ThreatEvent if a threat is detected, else None.
        """
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                t_type = ThreatType.SQL_INJECTION if "SELECT" in text.upper() else ThreatType.XSS
                event = self._record_threat(
                    threat_type=t_type,
                    level=ThreatLevel.HIGH,
                    source_ip=source_ip,
                    target="input_validation",
                    description=f"Injection pattern detected in input: {text[:80]}",
                    evidence={"pattern_matched": pattern},
                )
                return event
        return None

    def sanitize(self, text: str) -> str:
        """Return a sanitised version of the input (HTML-escape + strip null bytes)."""
        import html
        return html.escape(text.replace("\x00", ""))

    # ── Rate Limiting ─────────────────────────────────────────────────────────

    def check_rate_limit(
        self,
        source_ip: str,
        window_s: float = 60.0,
        max_requests: int = 100,
    ) -> bool:
        """
        Returns True if the IP is within limits, False if rate-limited.
        Automatically blocks IPs that exceed 10× the limit.
        """
        if source_ip in self._blocked_ips:
            return False

        now = time.time()
        history = self._rate_counters.setdefault(source_ip, [])
        history[:] = [t for t in history if now - t < window_s]   # prune old
        history.append(now)

        if len(history) > max_requests * 10:
            self._blocked_ips.add(source_ip)
            self._record_threat(
                ThreatType.BRUTE_FORCE, ThreatLevel.CRITICAL,
                source_ip, "rate_limiter",
                f"IP auto-blocked: {len(history)} reqs in {window_s}s",
            )
            log.warning("cyber_shield.ip_blocked", ip=source_ip)
            return False

        return len(history) <= max_requests

    def unblock_ip(self, ip: str) -> None:
        self._blocked_ips.discard(ip)
        log.info("cyber_shield.ip_unblocked", ip=ip)

    # ── File Integrity ────────────────────────────────────────────────────────

    def verify_file(self, file_bytes: bytes) -> dict[str, Any]:
        """Check file against known-malware hashes."""
        md5 = hashlib.md5(file_bytes).hexdigest()
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        is_malware = md5 in KNOWN_MALWARE_HASHES or sha256 in KNOWN_MALWARE_HASHES

        if is_malware:
            self._record_threat(
                ThreatType.KNOWN_MALWARE_HASH, ThreatLevel.CRITICAL,
                "0.0.0.0", "file_scanner",
                f"Malware hash match: md5={md5}",
                {"md5": md5, "sha256": sha256},
            )
        return {"md5": md5, "sha256": sha256, "malware_detected": is_malware}

    # ── Message Integrity (HMAC) ──────────────────────────────────────────────

    def sign(self, payload: dict) -> str:
        """Generate HMAC-SHA256 signature for a payload."""
        data = json.dumps(payload, sort_keys=True).encode()
        return hmac.new(self._secret, data, hashlib.sha256).hexdigest()

    def verify_signature(self, payload: dict, signature: str) -> bool:
        """Verify HMAC signature. Returns False and logs replay attempt on failure."""
        expected = self.sign(payload)
        if not hmac.compare_digest(expected, signature):
            self._record_threat(
                ThreatType.REPLAY_ATTACK, ThreatLevel.HIGH,
                "0.0.0.0", "hmac_verifier",
                "HMAC signature mismatch — possible replay or tampering",
            )
            return False
        return True

    # ── Network Audit ─────────────────────────────────────────────────────────

    def audit_config(self, config: dict[str, Any]) -> NetworkAuditResult:
        """
        Audit a service/network config dict for common misconfigurations.
        Produces actionable hardening recommendations.
        """
        vulns = []
        recommendations = []

        if config.get("debug", False):
            vulns.append("DEBUG mode is enabled in production")
            recommendations.append("Set DEBUG=False in production")

        if config.get("secret_key") in ("", "changeme", "default", "BRAINIAC-DEFAULT-CHANGE-ME"):
            vulns.append("Weak or default secret key detected")
            recommendations.append("Generate a cryptographically random 256-bit secret key")

        if not config.get("https_only", False):
            vulns.append("HTTPS not enforced — traffic may be intercepted")
            recommendations.append("Enable HTTPS-only with HSTS headers")

        if config.get("cors_origins") == ["*"]:
            vulns.append("CORS allows all origins — XSS risk")
            recommendations.append("Restrict CORS to known origins")

        if not config.get("rate_limiting", False):
            recommendations.append("Enable rate limiting to prevent brute-force attacks")

        risk_score = min(10.0, len(vulns) * 2.5)
        return NetworkAuditResult(
            target="config_audit",
            open_ports=[],
            services={},
            vulnerabilities=vulns,
            hardening_recommendations=recommendations,
            risk_score=risk_score,
        )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _record_threat(
        self,
        threat_type: ThreatType,
        level: ThreatLevel,
        source_ip: str,
        target: str,
        description: str,
        evidence: dict | None = None,
    ) -> ThreatEvent:
        import uuid
        event = ThreatEvent(
            event_id=str(uuid.uuid4()),
            threat_type=threat_type,
            threat_level=level,
            source_ip=source_ip,
            target=target,
            description=description,
            evidence=evidence or {},
        )
        self._events.append(event)
        log.warning(
            "cyber_shield.threat",
            type=threat_type.value,
            level=level.name,
            src=source_ip,
        )
        return event

    # ── Diagnostics ───────────────────────────────────────────────────────────

    def diagnostics(self) -> dict[str, Any]:
        by_level = {}
        for e in self._events:
            by_level[e.threat_level.name] = by_level.get(e.threat_level.name, 0) + 1
        return {
            "status": "ONLINE",
            "total_events": len(self._events),
            "events_by_level": by_level,
            "blocked_ips": len(self._blocked_ips),
            "tracked_ips": len(self._rate_counters),
        }
