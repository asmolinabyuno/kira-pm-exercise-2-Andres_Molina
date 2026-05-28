"""Probe 5 — Security headers and TLS audit (OWASP API8:2023).

Captures response headers from Kira's authenticated GET /v1/users endpoint and
checks for the standard security header set. Also runs a TLS protocol probe
to verify TLS 1.0/1.1 are rejected.

Reads token via run_flow.auth(). Writes evidence to:
  evidence/work/security/security-headers-and-tls/

Run: python3 evidence/work/security/security-headers-and-tls/probe_headers_tls.py
"""
from __future__ import annotations

import json
import socket
import ssl
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]  # evidence/work
if str(WORK) not in sys.path:
    sys.path.insert(0, str(WORK))

from _redact import redact_headers  # noqa: E402
from run_flow import API_KEY, BASE_URL, auth  # noqa: E402


def write(name: str, data: Dict[str, Any]) -> Path:
    out = HERE / name
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return out


# --- 1) Header audit: authenticated GET /v1/users ---------------------------

EXPECTED_HEADERS = [
    "strict-transport-security",
    "x-content-type-options",
    "x-frame-options",
    "referrer-policy",
    "permissions-policy",
    "content-security-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
    "cache-control",
]

DISCLOSURE_HEADERS = [
    "server",
    "x-powered-by",
    "via",
    "x-aspnet-version",
]


def probe_headers(token: str) -> Path:
    url = f"{BASE_URL}/v1/users?limit=1"
    headers = {
        "x-api-key": API_KEY,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    t0 = time.perf_counter_ns()
    resp = httpx.get(url, headers=headers, timeout=15.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    response_headers = {k.lower(): v for k, v in resp.headers.items()}

    audit = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "url": url,
        "method": "GET",
        "request_headers": redact_headers(headers),
        "status": resp.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "response_headers_raw": response_headers,
        "audit": {
            "missing_security_headers": [h for h in EXPECTED_HEADERS if h not in response_headers],
            "present_security_headers": {h: response_headers[h] for h in EXPECTED_HEADERS if h in response_headers},
            "info_disclosure_headers": {h: response_headers[h] for h in DISCLOSURE_HEADERS if h in response_headers},
            "cors": {h: v for h, v in response_headers.items() if h.startswith("access-control-")},
            "cdn_or_waf_clues": {h: v for h, v in response_headers.items() if h.startswith("x-amzn") or h.startswith("cf-") or h == "x-cache" or h == "via"},
        },
    }
    return write("01-headers-authenticated-get.json", audit)


# --- 2) CORS preflight probe -------------------------------------------------

def probe_cors_preflight() -> Path:
    url = f"{BASE_URL}/v1/users"
    headers = {
        "Origin": "https://evil.example.com",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,x-api-key,content-type",
    }
    t0 = time.perf_counter_ns()
    try:
        resp = httpx.request("OPTIONS", url, headers=headers, timeout=15.0)
        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
        response_headers = {k.lower(): v for k, v in resp.headers.items()}
        body = None
        try:
            body = resp.text[:500]
        except Exception:
            pass
        result = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "method": "OPTIONS",
            "request_headers": headers,
            "status": resp.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
            "response_headers": response_headers,
            "body_excerpt": body,
            "audit": {
                "allow_origin": response_headers.get("access-control-allow-origin"),
                "allow_credentials": response_headers.get("access-control-allow-credentials"),
                "allow_methods": response_headers.get("access-control-allow-methods"),
                "allow_headers": response_headers.get("access-control-allow-headers"),
                "wildcard_with_credentials_dangerous": (
                    response_headers.get("access-control-allow-origin") == "*"
                    and response_headers.get("access-control-allow-credentials") == "true"
                ),
            },
        }
    except Exception as e:
        result = {"captured_at": datetime.now(timezone.utc).isoformat(), "error": str(e)}
    return write("02-cors-preflight.json", result)


# --- 3) TLS protocol probe: TLS 1.0 / 1.1 should be REJECTED -----------------

def tls_probe_via_openssl(version_flag: str) -> Dict[str, Any]:
    """Run `openssl s_client` with an explicit protocol flag.

    Returns connect outcome and a short excerpt.
    """
    host = BASE_URL.replace("https://", "").replace("http://", "").split("/")[0]
    cmd = ["openssl", "s_client", "-connect", f"{host}:443", "-servername", host, version_flag]
    try:
        proc = subprocess.run(
            cmd,
            input=b"",
            capture_output=True,
            timeout=10,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace")[:2000]
        stderr = proc.stderr.decode("utf-8", errors="replace")[:2000]
        # Did the handshake succeed?
        success_marker = "BEGIN CERTIFICATE" in stdout or "Protocol  :" in stdout
        rejected_markers = [
            "alert protocol version",
            "no protocols available",
            "ssl handshake failure",
            "wrong version number",
            "unsupported protocol",
            "tlsv1 alert",
        ]
        rejected = any(m in (stdout + stderr).lower() for m in rejected_markers)
        return {
            "version_flag": version_flag,
            "exit_code": proc.returncode,
            "handshake_completed": success_marker and not rejected,
            "rejected": rejected,
            "stdout_excerpt": stdout,
            "stderr_excerpt": stderr,
        }
    except FileNotFoundError:
        return {"version_flag": version_flag, "error": "openssl not found"}
    except subprocess.TimeoutExpired:
        return {"version_flag": version_flag, "error": "timeout"}


def tls_probe_via_python(min_version, max_version, label: str) -> Dict[str, Any]:
    host = BASE_URL.replace("https://", "").replace("http://", "").split("/")[0]
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.minimum_version = min_version
        ctx.maximum_version = max_version
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                return {
                    "label": label,
                    "connected": True,
                    "negotiated_protocol": ssock.version(),
                    "cipher": ssock.cipher(),
                }
    except Exception as e:
        return {"label": label, "connected": False, "error": f"{type(e).__name__}: {e}"}


def probe_tls() -> Path:
    """Probe TLS 1.0/1.1 — both should be REJECTED. Probe TLS 1.2/1.3 — both expected ACCEPTED."""
    results = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "host": BASE_URL.replace("https://", "").split("/")[0],
        "python_probes": [],
        "openssl_probes": [],
    }

    # Python ssl module — most reliable
    results["python_probes"].append(tls_probe_via_python(ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1, "tls1.0-only"))
    results["python_probes"].append(tls_probe_via_python(ssl.TLSVersion.TLSv1_1, ssl.TLSVersion.TLSv1_1, "tls1.1-only"))
    results["python_probes"].append(tls_probe_via_python(ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_2, "tls1.2-only"))
    results["python_probes"].append(tls_probe_via_python(ssl.TLSVersion.TLSv1_3, ssl.TLSVersion.TLSv1_3, "tls1.3-only"))

    # openssl fallback
    for flag in ["-tls1", "-tls1_1", "-tls1_2", "-tls1_3"]:
        results["openssl_probes"].append(tls_probe_via_openssl(flag))

    return write("03-tls-protocol-audit.json", results)


# --- 4) Unauthenticated probe: do error responses leak ------------------------

def probe_error_disclosure() -> Path:
    """No auth headers → what does the gateway say?"""
    url = f"{BASE_URL}/v1/users"
    t0 = time.perf_counter_ns()
    resp = httpx.get(url, timeout=10.0)
    elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
    return write(
        "04-unauth-error.json",
        {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "status": resp.status_code,
            "elapsed_ms": round(elapsed_ms, 2),
            "response_headers": {k.lower(): v for k, v in resp.headers.items()},
            "body_excerpt": resp.text[:1000],
        },
    )


def main() -> None:
    token = auth()
    if not token:
        print("AUTH FAILED — aborting probe 5")
        sys.exit(1)
    p1 = probe_headers(token)
    p2 = probe_cors_preflight()
    p3 = probe_tls()
    p4 = probe_error_disclosure()
    print("Probe 5 outputs:")
    for p in (p1, p2, p3, p4):
        print(" -", p)


if __name__ == "__main__":
    main()
