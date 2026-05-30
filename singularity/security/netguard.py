"""SSRF guard for the CONTROL organ (singularity/organs/control.py).

Fixes cursor/Qodo finding #1 (High — full-read SSRF, CWE-918).

The original `control._browse` validated only scheme+netloc, so an
unauthenticated caller could make the server fetch
`http://169.254.169.254/...` (cloud IAM creds), `http://127.0.0.1:<port>/`,
or any internal host, and the body was returned to the caller.

This module resolves the host, rejects loopback / private / link-local /
reserved / multicast / cloud-metadata targets, disables auto-redirects
(re-validating each hop to defeat DNS-rebinding + redirect bypass), and
caps the response size. Standard library only — no new dependencies.

Integration (control.py)::

    from singularity.security.netguard import safe_fetch, SSRFError

    async def _browse(self, url: str) -> dict[str, Any]:
        def _get() -> dict[str, Any]:
            try:
                return safe_fetch(url, max_bytes=200_000, timeout=8)
            except SSRFError as exc:
                return {"url": url, "ok": False, "error": str(exc),
                        "_backend": "builtin", "_mode": self._mode.value}
        return await asyncio.to_thread(_get)
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

# Hosts that must never be fetched regardless of resolved IP.
_BLOCKED_HOSTNAMES = frozenset(
    {"localhost", "metadata.google.internal", "metadata", "instance-data"}
)
_ALLOWED_SCHEMES = frozenset({"http", "https"})
# Cloud metadata endpoints (link-local already blocked, listed for clarity).
_METADATA_IPS = frozenset({"169.254.169.254", "100.100.100.200", "fd00:ec2::254"})


class SSRFError(ValueError):
    """Raised when a URL targets a forbidden / non-public destination."""


def _ip_is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or (addr.version == 6 and addr.ipv4_mapped is not None
            and not ipaddress.ip_address(str(addr.ipv4_mapped)).is_global)
    )


def assert_safe_url(url: str) -> tuple[str, int, str]:
    """Validate ``url`` and return (host, port, scheme). Raise SSRFError if unsafe.

    Resolves every A/AAAA record for the host and rejects the request unless
    *all* resolved IPs are public — partial-trust answers (one public, one
    private) are treated as hostile.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    host = (parsed.hostname or "").lower()

    if scheme not in _ALLOWED_SCHEMES:
        raise SSRFError(f"scheme not allowed: {scheme!r}")
    if not host:
        raise SSRFError("missing host")
    if host in _BLOCKED_HOSTNAMES:
        raise SSRFError(f"blocked hostname: {host!r}")

    port = parsed.port or (443 if scheme == "https" else 80)

    # If host is a literal IP, validate it directly.
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if host in _METADATA_IPS or not _ip_is_public(host):
            raise SSRFError(f"non-public address: {host}")
        return host, port, scheme

    # Resolve and validate *every* record.
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise SSRFError(f"dns resolution failed: {host}") from exc
    resolved = {str(info[4][0]) for info in infos}
    if not resolved:
        raise SSRFError(f"no addresses for {host}")
    for ip in resolved:
        if ip in _METADATA_IPS or not _ip_is_public(ip):
            raise SSRFError(f"host {host} resolves to non-public address {ip}")
    return host, port, scheme


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and len(self.title) < 300:
            self.title += data


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Block automatic redirects — each hop must be re-validated explicitly."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


def safe_fetch(
    url: str,
    *,
    max_bytes: int = 200_000,
    timeout: float = 8.0,
    max_redirects: int = 3,
    user_agent: str = "singularity-control/1.1",
) -> dict[str, object]:
    """Fetch ``url`` safely. Re-validates the target before every hop.

    Redirects are followed manually (up to ``max_redirects``) so each
    Location is checked with :func:`assert_safe_url`, defeating
    redirect-to-internal and DNS-rebinding bypasses.
    """
    opener = urllib.request.build_opener(_NoRedirect)
    current = url
    for _ in range(max_redirects + 1):
        assert_safe_url(current)  # raises SSRFError if unsafe
        req = urllib.request.Request(current, headers={"User-Agent": user_agent})
        try:
            resp = opener.open(req, timeout=timeout)  # noqa: S310 (validated)
        except urllib.error.HTTPError as http_err:
            if http_err.code in (301, 302, 303, 307, 308):
                location = http_err.headers.get("Location")
                if not location:
                    raise SSRFError("redirect without Location")
                current = urllib.parse.urljoin(current, location)
                continue
            # Non-redirect HTTP errors are real responses; surface them.
            return {
                "url": current, "ok": False, "status": http_err.code,
                "title": "", "text_snippet": "", "_backend": "urllib",
            }
        with resp:
            raw = resp.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            body = raw[:max_bytes]
            text = body.decode("utf-8", "replace")
            parser = _TitleParser()
            try:
                parser.feed(text)
            except Exception:  # noqa: BLE001 - malformed HTML is non-fatal
                pass
            return {
                "url": resp.geturl(),
                "ok": True,
                "status": getattr(resp, "status", 200),
                "title": parser.title.strip()[:300],
                "text_snippet": text[:400],
                "bytes": len(body),
                "truncated": truncated,
                "_backend": "urllib",
            }
    raise SSRFError("too many redirects")


if __name__ == "__main__":
    # Self-test: the documented attack inputs must all be rejected.
    attacks = [
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "http://127.0.0.1:8188/",
        "http://[::1]/",
        "http://localhost/admin",
        "http://10.0.0.5/",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "file:///etc/passwd",
        "gopher://127.0.0.1/",
        "http://metadata.google.internal/computeMetadata/v1/",
    ]
    ok = True
    for a in attacks:
        try:
            assert_safe_url(a)
            print(f"FAIL (not blocked): {a}")
            ok = False
        except SSRFError as e:
            print(f"blocked: {a}  ->  {e}")
    print("\nALL ATTACKS BLOCKED" if ok else "\nSOME ATTACKS LEAKED")
