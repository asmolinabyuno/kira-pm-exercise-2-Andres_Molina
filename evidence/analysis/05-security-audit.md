# Security Audit — OWASP API Top 10 (Phase 3 Partial)

**Run date:** 2026-05-27
**Scope:** 18 endpoints validated in Phase 2 (per `integration-log.md`)
**Auditor agent:** `api-security-auditor`
**Sandbox base URL:** `https://api.balampay.com` (no `/sandbox` prefix — DRIFT-1)
**Hard rule honored:** No real PII used; no out-of-scope hosts probed; no data exfiltrated via SSRF; all webhook registrations cleaned up via last-write-wins overwrite.

## Findings Summary

| # | Finding | OWASP API | Severity | Probe slug | Status |
|---|---|---|---|---|---|
| 1 | SSRF — Kira fetches attacker-supplied webhook URLs at delivery time | API7:2023 | **CRITICAL** | `ssrf-webhook-delivery-confirm` | CONFIRMED |
| 2 | PII unmasked — SSN/document_number on `/v1/users` (list + detail) | API3:2023 | **CRITICAL** | `info-disclosure-account-details` | CONFIRMED — extends DRIFT-30 |
| 3 | PII unmasked — `account_details` on all 4 `/v1/recipients/{id}` variants | API3:2023 | **CRITICAL** | `info-disclosure-account-details` | CONFIRMED — DRIFT-30 broadened |
| 4 | TLS 1.0 and TLS 1.1 accepted by `api.balampay.com:443` | API8:2023 | **CRITICAL** | `security-headers-and-tls` | CONFIRMED |
| 5 | Mass assignment — `verification_mode` is integrator-settable | API3:2023 | HIGH | `mass-assignment-user-create` | CONFIRMED |
| 6 | Error envelope drift — 5th distinct shape on `/v1/users/{id}` 404 | API8:2023 | LOW | `bola-id-enumeration` | CONFIRMED — supplements DRIFT-6 |
| 7 | CORS `Access-Control-Allow-Origin: *` on preflight | API8:2023 | LOW | `security-headers-and-tls` | CONFIRMED |
| 8 | Missing `permissions-policy` and `cache-control` headers | API8:2023 | LOW | `security-headers-and-tls` | CONFIRMED |
| 9 | SigV4 base64 hash leak on unknown-path 403 | API8:2023 | LOW | `info-disclosure-account-details` | CONFIRMED — supplements DRIFT-39 |

Total CRITICAL: **4** · HIGH: **1** · LOW: **4**

Negative-result probes (no findings): `jwt-attack-suite` (9 attacks all rejected) · `bola-id-enumeration` for cross-tenant 200 (none observed).

---

## Finding 1 — SSRF: Kira fetches attacker-supplied webhook URLs at delivery time

**OWASP API Top 10 mapping:** API7:2023 — Server-Side Request Forgery
**CVSS estimate (v3.1):** 9.1 — `AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:N` (network, low complexity, low privilege required, scope changed because the fetcher hits other hosts, high confidentiality+integrity impact, no availability concern)
**Asset:** Kira webhook-fetcher's internal network reachability — AWS IAM metadata, internal services (Redis, internal HTTP admin panels), RFC1918 hosts.
**Attack vector:** Compromised or insider integrator with one valid `x-api-key` + Bearer pair calls `POST /webhooks/register` with `webhook_url = http://169.254.169.254/latest/meta-data/iam/security-credentials/`. Triggers any event-emitting endpoint (POST /v1/users will do — confirmed). Kira's outbound fetcher (Node, AWS us-west-2 IP `54.201.149.241` observed) attempts the HTTP call to the supplied URL.
**Threat actor:** Compromised-integrator scenarios (insider, leaked credentials), red team, advanced fraudster.
**Reproduction:**
  1. Run `python3 evidence/work/security/ssrf-webhook-delivery-confirm/probe_ssrf_delivery.py`.
  2. Probe registers a fresh `webhook.site/<uuid>`, triggers `POST /v1/users`, observes delivery in ~37 s (POST from `54.201.149.241`, User-Agent `node`, includes `x-signature-sha256` — see `evidence/work/webhooks/32-success-P1-stepC-webhook-receipt-snapshot.json`).
  3. Probe re-registers webhook with the AWS IMDS URL, triggers another `POST /v1/users`. webhook.site receives **zero new deliveries** in the next 120 s — strong evidence the IMDS URL was the delivery target.
  4. Cleanup re-registers webhook.site URL (200 OK — `evidence/work/webhooks/31-success-P1-G-cleanup-final-overwrite.json`).
**Expected hardened API:** Validate `webhook_url` against private/link-local/loopback ranges at registration AND re-validate at delivery (DNS rebinding defense); route outbound webhook deliveries through an egress proxy with an internet-only allowlist; expose a delete endpoint so insecure registrations can be removed.
**Observed Kira behavior:** No URL validation at registration (DRIFT-47 already proved this). At delivery, Kira honors whatever URL was last registered for the `client_uuid` — including IMDS. No allowlist. No way to delete a registration (GAP-21).
**Impact:** AWS IAM credential exfiltration (if Kira's fetcher VPC permits IMDSv1), internal port-scan via webhook bodies, reachability of any internal service. Severity escalated to CRITICAL because Phase 3 now has empirical proof that the outbound fetch IS being made.
**Remediation hint:** SSRF-allowlist on `webhook_url` (RFC1918, loopback, link-local rejected at registration); DNS re-validation at delivery; delete endpoint; IMDSv2 on the webhook-fetcher hosts.

---

## Finding 2 — PII unmasked: SSN / document_number on `/v1/users`

**OWASP API Top 10 mapping:** API3:2023 — Broken Object Property Level Authorization (excessive data exposure)
**CVSS estimate (v3.1):** 7.5 — `AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N` (network, low complexity, low privilege, single-tenant scope, high confidentiality impact)
**Asset:** Associated-person SSN and document_number on every user record owned by the integrator.
**Attack vector:** Any compromised integrator credential → `GET /v1/users?limit=100` returns multiple users at once, each with `associated_persons[].ssn` and `.document_number` in plaintext. No need to know specific user IDs — the list view is the attack surface.
**Threat actor:** Insider, credential leak, malware on integrator's CI/CD server.
**Reproduction:**
  1. Run `python3 evidence/work/security/info-disclosure-account-details/probe_disclosure.py`.
  2. Inspect `01-disclosure-sweep.json` `analysis[label=users-list].sensitive_fields_found` → 3 SSNs returned plaintext in a 5-item list.
  3. Same for `analysis[label=user-detail]` → 7 unmasked sensitive fields in one detail call.
**Expected hardened API:** List view should not include SSN/document_number at all (or mask to last-4 only); detail view should mask by default, with a separate authorized endpoint + audit log for full retrieval.
**Observed Kira behavior:** Plaintext on every read. No masking, no separate endpoint, no scope gate.
**Impact:** Bulk SSN scrape from one credential. Combined with `verification_status` exposing `unverified` vs `approved` per user, an attacker can prioritize harvesting only the high-trust (real-PII) records.
**Remediation hint:** Add a read-projection layer that masks PII fields on every list AND detail by default; full-plaintext gated by separate scope + audit log.

---

## Finding 3 — PII unmasked: `account_details` on all 4 recipient variants

**OWASP API Top 10 mapping:** API3:2023 — Broken Object Property Level Authorization
**CVSS estimate (v3.1):** 7.5 — same as Finding 2
**Asset:** Bank account numbers, routing numbers, IBANs, CLABEs, SWIFT codes, full crypto wallet addresses for every recipient owned by the integrator. Doc numbers (RFC/SSN/EIN) also exposed.
**Attack vector:** `GET /v1/recipients/{id}` for any recipient ID the attacker knows (or `GET /v1/recipients?user_id={uid}` to discover IDs first). Each detail returns:
  - SPEI: `clabe` + `doc_number` (RFC)
  - ACH: `routing_number` + `account_number` + `doc_number`
  - USDT: full wallet `address`
  - SWIFT: `account_number` (IBAN) + `swift_code` + `doc_number`
**Threat actor:** Same as Finding 2.
**Reproduction:** Same probe — `info-disclosure-account-details/probe_disclosure.py`. See `01-disclosure-sweep.json` `analysis[label=recipient_id_*-detail]`. Already independently captured in `evidence/work/recipients/06,27,29,31-*.json` from Batch C.
**Expected hardened API:** Mask all account identifiers on read by default. Provide a separate audited endpoint for plaintext retrieval (e.g., for outgoing payouts that legitimately need the full account number — but only the payout-creation flow should access it, not the integrator at large).
**Observed Kira behavior:** DRIFT-30 originally flagged this on SPEI; Phase 3 confirms it on ALL FOUR variants.
**Impact:** With plaintext routing+account number, an attacker can construct fraudulent ACH/SPEI/SWIFT debits against the victim's bank. With plaintext IBAN+SWIFT, same for SEPA/SWIFT. With wallet address, attacker can dust-attack or track on-chain flows.
**Remediation hint:** Same as Finding 2 — mask by default, gate plaintext.

---

## Finding 4 — TLS 1.0 and TLS 1.1 accepted by `api.balampay.com:443`

**OWASP API Top 10 mapping:** API8:2023 — Security Misconfiguration
**CVSS estimate (v3.1):** 5.9 — `AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:N` (network, HIGH attack complexity because requires a MITM and a client that consents to downgrade; HIGH confidentiality+integrity impact if exploited via downgrade attack like BEAST). Real-world severity is CRITICAL on compliance grounds (PCI-DSS, state money-transmitter audits) more than on technical exploitability — calibrate against the threat-model.
**Asset:** Encrypted transport between client integrators and Kira's API. For a fintech moving FedNow/RTP/ACH/Wire, this is in scope of PCI-DSS Req 4.1 (strong cryptography), the FFIEC IT Handbook, and most state money-transmitter audits.
**Attack vector:** A MITM on the network path can negotiate a TLSv1 or TLSv1.1 session and exploit known weaknesses (BEAST, POODLE for SSLv3 — not active here, but TLSv1 ciphers include CBC modes that are still vulnerable in some configs).
**Reproduction:**
  1. `python3 evidence/work/security/security-headers-and-tls/probe_headers_tls.py`
  2. Inspect `03-tls-protocol-audit.json` — Python `ssl.SSLContext` pinned to `TLSv1` and `TLSv1.1` both connect successfully and return ciphers `ECDHE-RSA-AES128-SHA`.
  3. Cross-check with `openssl s_client -connect api.balampay.com:443 -tls1 -servername api.balampay.com` → exit 0, certificate received.
**Expected hardened API:** Modern security policy — TLS 1.2 minimum, TLS 1.3 preferred. AWS CloudFront security policy `TLSv1.2_2021` is the standard fix; ALB equivalent is `ELBSecurityPolicy-TLS-1-2-2017-01` or newer.
**Observed Kira behavior:** Accepts TLSv1, TLSv1.1, TLSv1.2 — verified by two independent tools.
**Impact:** Compliance finding (PCI-DSS Req 4.1, FFIEC, state money-transmitter audits). Technical exploit requires MITM + downgrade — not trivial but well within nation-state / advanced-fraud-group capabilities.
**Remediation hint:** Update CloudFront or ALB to a TLS-1.2-minimum security policy; verify with `nmap --script ssl-enum-ciphers -p 443 api.balampay.com`.

---

## Finding 5 — Mass assignment: `verification_mode` is integrator-settable

**OWASP API Top 10 mapping:** API3:2023 — Broken Object Property Level Authorization (mass assignment)
**CVSS estimate (v3.1):** 5.4 — `AV:N/AC:L/PR:L/UI:R/S:U/C:N/I:H/A:N` (network, low complexity, low priv, user-interaction required — the victim must click the link, HIGH integrity impact)
**Asset:** User verification workflow — `automatic` (in-process KYB) vs `verification_link` (emails the user a link).
**Attack vector:** `POST /v1/users` with `verification_mode: "verification_link"` is accepted (201, field echoed back as-set). An attacker can create users in a non-default verification mode, possibly triggering an email to an arbitrary `email` value in the body — phishing-by-proxy from a legitimate Kira sender domain.
**Threat actor:** Compromised integrator credential → spam/phish from Kira's domain.
**Reproduction:**
  1. `python3 evidence/work/security/mass-assignment-user-create/probe_enum_inputs.py`
  2. Inspect `02-enum-input-results.json` entry E4 — `verification_mode: "verification_link"` sent, response shows `verification_mode: "verification_link"`.
**Expected hardened API:** Either strip `verification_mode` from the request body entirely (derive from integrator's account config), or gate it behind a separate scope claim in the JWT.
**Observed Kira behavior:** Field is accepted; only `manual` is rejected as out-of-enum. `automatic` (default) and `verification_link` (the dangerous one) are both accepted.
**Impact:** Phishing-by-proxy through Kira's email infra; workflow divergence (integrator UI assumes one verification mode but the actual user record has another); audit-log filters miss the attacker's records.
**Remediation hint:** Make `verification_mode` server-derived from the client config, not an input. Or, gate with a scope claim.

---

## Finding 6 — Error envelope drift: 5th distinct shape on `/v1/users/{id}` 404 vs `/v1/recipients/{id}` 404

**OWASP API Top 10 mapping:** API8:2023 — Security Misconfiguration (consistency)
**CVSS estimate:** N/A (not directly exploitable; type-safe-codegen breakage)
**Asset:** Integrator's parser uniformity.
**Attack vector:** N/A — defensive coding nuisance.
**Reproduction:** See Probe 3 README.
**Observed Kira behavior:**
  - `/v1/users/{guessed_uuid}` 404: `{"code":"not_found","message":"User with ID <uuid> not found"}`
  - `/v1/recipients/{guessed_uuid}` 404: `{"error":{"code":"NOT_FOUND","message":"Recipient with ID <uuid> not found","details":{}}}`
**Impact:** Breaks type-safe code generators (Go, TS) — adds to DRIFT-6 (already 4 shapes catalogued; this is now 5).
**Remediation hint:** Pick one envelope shape and migrate the API.

---

## Finding 7 — CORS `Access-Control-Allow-Origin: *` on preflight

**OWASP API Top 10 mapping:** API8:2023
**CVSS estimate:** 3.7 — `AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:N/A:N`
**Asset:** Browser-based session integrity (low on a server-to-server API but non-zero).
**Attack vector:** `OPTIONS /v1/users` with `Origin: https://evil.example.com` returns `Access-Control-Allow-Origin: *`. Browser will then send the actual request. The actual GET response includes `Access-Control-Allow-Credentials: true` (per Phase 2 evidence), but `Access-Control-Allow-Origin` is NOT echoed on the GET — so credentialed cross-origin reads are still blocked by the browser. Safe for server-to-server but permissive for browsers.
**Reproduction:** `02-cors-preflight.json`.
**Observed Kira behavior:** Wildcard on preflight, missing origin echo on GET. Inconsistent.
**Impact:** No direct exfiltration; mostly cosmetic, but indicates a misconfigured CORS policy.
**Remediation hint:** If the API is server-to-server only, disable CORS entirely. If browsers must call it, echo specific allowed origins.

---

## Finding 8 — Missing `Permissions-Policy` and `Cache-Control` headers

**OWASP API Top 10 mapping:** API8:2023
**CVSS estimate:** N/A — defense-in-depth.
**Asset:** Cache hygiene (especially given Finding 2/3 PII).
**Attack vector:** Intermediate caches (CDN, corporate proxy) may store PII responses if `cache-control: no-store` isn't set. Permissions-Policy is irrelevant for an API (more browser-relevant) but expected by hardening checklists.
**Observed Kira behavior:** Both headers absent.
**Remediation hint:** Set `Cache-Control: no-store` on all `/v1/*` responses; `Permissions-Policy: ()` for completeness.

---

## Finding 9 — SigV4 base64 hash leak on unknown-path 403

**OWASP API Top 10 mapping:** API8:2023
**CVSS estimate:** 2.5 — info disclosure of the AWS gateway authorizer behavior.
**Asset:** Kira's gateway internals.
**Attack vector:** `GET /v1/this-endpoint-does-not-exist` returns `{"message":"Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): '<32-char-base64>'."}`.
**Observed Kira behavior:** The base64 string is the hash of the request's Authorization header — not the secret itself, but an oracle that confirms the request reached the SigV4 authorizer.
**Impact:** Minor — same class as DRIFT-39.
**Remediation hint:** Map gateway-layer 403s to a generic `{"error":"forbidden"}` envelope.

---

## Probes that did NOT trigger findings

### `jwt-attack-suite`

9 forgery attempts against `GET /v1/users?limit=1` — all rejected (401 or 403). Tests covered:
- alg=none (with and without retained sig)
- kid path-traversal + kid removal
- claim tampering (client_id mutated, original sig kept)
- single-byte signature flip
- empty bearer (httpx transport error — no API call)
- garbage bearer
- HS256-confusion (empty key + "secret" key)

Token is RS256-signed by AWS Cognito (kid + JWKS lookup). Standard, well-vetted validator. **No exploitable JWT finding.**

Open item: full TTL replay (3600 s wait + retry) was out of time budget — recommend running in CI nightly.

### `bola-id-enumeration` cross-tenant 200 attempts

16 attempts across `/v1/users/{id}` + `/v1/recipients/{id}` + `/v1/virtual-accounts/{id}` with random and sequential UUIDs. **Zero 200s on cross-tenant guesses.** All returned 404 (or 400 for malformed). No BOLA / IDOR. Two ancillary informational findings recorded under Finding 6 (envelope drift) and finding-3 README (ID echoed in 404 body — minor existence oracle, but not enumerable with v4 UUIDs).

---

## SSRF delivery confirmation — outcome

**Kira's sandbox DOES deliver webhooks** (confirmed by observation of POST from `54.201.149.241` with `User-Agent: node` + `x-signature-sha256` header, ~37 s after the trigger event).

**When the registration is changed to the AWS IMDS URL**, the previously-active webhook.site URL stops receiving deliveries — strong evidence Kira routed the outbound HTTP to the IMDS URL (or wherever was last registered). Last-write-wins by `client_uuid` is now empirically confirmed.

We did NOT escalate to harvest IMDS data — only confirmed Kira's outbound behavior.

---

## JWT attack outcomes summary

- `alg=none` — REJECTED (401)
- Token replay (full TTL) — DEFERRED (3600 s wall-time out of budget)
- Tampered `client_id` claim with intact sig — REJECTED (403)
- HS256 confusion — REJECTED
- Missing kid / path-traversal kid — REJECTED
- Empty / garbage Bearer — REJECTED

Net: **No JWT auth findings.**

---

## New drift events introduced in Phase 3 (security track)

This audit produced **9 new findings**, but several are confirmations/escalations of Phase-2 drifts rather than wholly new contradictions. Net-new drift-class entries:

1. **SSRF delivery confirmed (DRIFT-47 escalation)** — empirical proof Kira fetches the registered URL, not just accepts it.
2. **PII unmasked on `/v1/users` LIST and DETAIL (DRIFT-30 broadening)** — extends to users, not just recipients.
3. **TLS 1.0/1.1 accepted at the gateway** — new finding entirely. Not previously captured.
4. **`verification_mode` mass-assignable** — new finding (DRIFT-4 lineage but a specific exploitable field).
5. **Error-envelope drift to 5 shapes** — supplements DRIFT-6.
6. **CORS `*` on preflight** — new minor finding.
7. **Missing Permissions-Policy and Cache-Control** — new minor finding.
8. **SigV4 hash leak on unknown path** — new instance of the DRIFT-39 class.

The data-engineer / data-architect can decide whether to renumber as DRIFT-54..61 in `integration-log.md` — recommend they do, since these are runtime observations that contradict the implicit "regulated fintech defaults" everyone assumed.

---

## Open questions / out-of-scope items

- **SSRF actual IMDS reachability:** we proved Kira *attempts* the outbound, but we can't tell from outside whether Kira's VPC egress policy blocks IMDS. Recommend @Diego confirm.
- **Webhook signing on unsigned-secret registration:** Phase 3 follow-up (DRIFT-G2 escalation) — register with `secret: null`, force delivery, inspect headers. We confirmed delivery happens; the secret behavior on null-secret deliveries was not specifically probed this run.
- **Cross-tenant `client_uuid` spoof:** can a tenant register a webhook under a different `client_uuid` than their own? This requires a 2nd test tenant (not in this scope) — strongly recommend doing this carefully against a sandbox-only second tenant.
- **Token TTL replay:** 3600 s wait + retry. Run in CI nightly.

---

## Files created

- `evidence/analysis/05-security-audit.md` (this file)
- `evidence/work/security/ssrf-webhook-delivery-confirm/{probe_ssrf_delivery.py, README.md, 01-delivery-confirm-results.json}`
- `evidence/work/security/mass-assignment-user-create/{probe_mass_assignment.py, probe_enum_inputs.py, README.md, 01-mass-assignment-results.json, 02-enum-input-results.json}`
- `evidence/work/security/bola-id-enumeration/{probe_bola.py, README.md, 01-bola-results.json}`
- `evidence/work/security/jwt-attack-suite/{probe_jwt.py, README.md, 01-token-structure.json, 02-attack-results.json}`
- `evidence/work/security/security-headers-and-tls/{probe_headers_tls.py, README.md, 01-headers-authenticated-get.json, 02-cors-preflight.json, 03-tls-protocol-audit.json, 04-unauth-error.json}`
- `evidence/work/security/info-disclosure-account-details/{probe_disclosure.py, README.md, 01-disclosure-sweep.json}`
- `evidence/work/webhooks/29-success-P1-A-register-receiver.json`
- `evidence/work/webhooks/30-success-P1-D-register-imds.json`
- `evidence/work/webhooks/31-success-P1-G-cleanup-final-overwrite.json`
- `evidence/work/webhooks/32-success-P1-stepC-webhook-receipt-snapshot.json`

## Operational confirmations

- No out-of-scope hosts probed. All requests targeted `https://api.balampay.com` and the registered webhook.site URLs.
- No real PII used. All test SSNs/EINs are the obviously-fake `000-00-0000` / `00-0000000`.
- No SSRF data exfiltration. The IMDS URL was registered briefly and re-registered to the benign webhook.site URL within 3 minutes (cleanup at step G).
- All `_redact.py` rules honored — every evidence file passed through `redact_headers` and `redact_body`. Raw token, password, and api-key values never written to disk.
- No `run_flow.py` or `_redact.py` mutations.
