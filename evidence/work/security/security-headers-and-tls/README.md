# Probe 5 — Security Headers and TLS Protocol Audit

**OWASP API Top 10 mapping:** API8:2023 — Security Misconfiguration
**Severity:** **CRITICAL** (TLS 1.0/1.1 accepted) + LOW (minor header gaps + CORS wildcard on preflight)
**Status:** TLS finding is a real exposure; header posture is otherwise solid.

## Findings — ranked

### Finding 5.1 — TLS 1.0 AND TLS 1.1 accepted on `api.balampay.com` — CRITICAL

Confirmed via two independent tools:

**Python `ssl` module (`SSLContext` pinned to each version):**
```
tls1.0-only: connected=True negotiated=TLSv1 cipher=ECDHE-RSA-AES128-SHA
tls1.1-only: connected=True negotiated=TLSv1.1 cipher=ECDHE-RSA-AES128-SHA
tls1.2-only: connected=True negotiated=TLSv1.2 cipher=ECDHE-ECDSA-CHACHA20-POLY1305
tls1.3-only: error (LibreSSL build on macOS doesn't expose TLSv1.3 enum — inconclusive but irrelevant)
```

**openssl `s_client -tls1` / `-tls1_1`:** both return exit 0, handshake completes, no rejection.

**Impact:**
- TLS 1.0 was deprecated by the IETF in 2021 (RFC 8996). PCI-DSS 3.2 forbid it. Major browsers stopped supporting it in 2020.
- TLS 1.1 has known vulnerabilities (BEAST, weak MAC). Same regulatory bans.
- Any client that downgrades (intentionally or via a downgrade attack on a weak intermediary) can negotiate a weaker cipher.
- For a regulated fintech moving real money for partner banks under FedNow/RTP/ACH/Wire, this is a regulatory finding (PCI-DSS, GLBA, multi-state money-transmitter laws) on top of the technical one.

**Remediation:** Set the CloudFront/ALB security policy to `TLSv1.2_2021` (or newer). Verify with `nmap --script ssl-enum-ciphers -p 443 api.balampay.com` after fix.

### Finding 5.2 — CORS `Access-Control-Allow-Origin: *` on preflight — LOW (informational)

`OPTIONS /v1/users` with `Origin: https://evil.example.com` returns:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: DELETE,GET,HEAD,OPTIONS,PATCH,POST,PUT`
- `Access-Control-Allow-Headers: Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token`
- `Access-Control-Allow-Credentials` is NOT echoed on preflight (good — that would be the critical version)

**Why LOW:** The API is server-to-server; legitimate clients aren't browsers anyway. But `*` on preflight is more permissive than it needs to be. The GET response separately includes `Access-Control-Allow-Credentials: true` (per the headers in our authenticated GET — no `Access-Control-Allow-Origin` echoed on the GET response), which means a browser-based attacker can't trivially exfiltrate authenticated responses. Still: best practice is to either (a) drop CORS entirely on a server-to-server API, or (b) echo only specific allowed origins.

### Finding 5.3 — Permissions-Policy and Cache-Control headers missing — LOW

Audit found 7 of 9 expected security headers present; missing: `permissions-policy`, `cache-control`.

For a JSON API, `cache-control: no-store` is recommended to prevent intermediate caches from holding sensitive responses (especially given DRIFT-30 / Probe-6 unmasked PII).

### Finding 5.4 — `Server: cloudflare` + `x-amzn-errortype` framework disclosure — LOW

Headers reveal Cloudflare CDN + AWS API Gateway (via `x-amzn-errortype`, `x-amz-apigw-id`, `x-amzn-remapped-*`). These let an attacker fingerprint the stack and target known CVEs. Not a finding on its own; calibrate to LOW.

## Reproduction

```bash
python3 evidence/work/security/security-headers-and-tls/probe_headers_tls.py
```

Outputs:
- `01-headers-authenticated-get.json` — full header audit on GET /v1/users
- `02-cors-preflight.json` — CORS preflight against evil.example.com
- `03-tls-protocol-audit.json` — TLS 1.0 / 1.1 / 1.2 / 1.3 handshake probes (Python + openssl)
- `04-unauth-error.json` — unauth gateway error envelope

## Security headers — full audit

**Present (good):**
- `strict-transport-security: max-age=15552000; includeSubDomains` (180 days, no preload)
- `x-content-type-options: nosniff`
- `x-frame-options: SAMEORIGIN`
- `referrer-policy: no-referrer`
- `content-security-policy: default-src 'self';base-uri 'self'; …` (verbose, strict)
- `cross-origin-opener-policy: same-origin`
- `cross-origin-resource-policy: same-origin`
- `x-permitted-cross-domain-policies: none`
- `x-xss-protection: 0` (good — modern guidance is to disable)
- `x-download-options: noopen`

**Missing:**
- `permissions-policy`
- `cache-control` (no-store)

**Bonus (positive):**
- `x-api-version: 2026-04-14` — confirms the version path. Minor info leak (attacker learns the API version) but explicit versioning is otherwise good.

## Files

- `probe_headers_tls.py`
- `01-headers-authenticated-get.json`
- `02-cors-preflight.json`
- `03-tls-protocol-audit.json`
- `04-unauth-error.json`
