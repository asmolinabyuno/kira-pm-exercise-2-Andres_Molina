# Probe 6 — Information Disclosure: PII / Account Details Sweep

**OWASP API Top 10 mapping:** API3:2023 — Broken Object Property Level Authorization (excessive data exposure side) + API8:2023 — Security Misconfiguration
**Severity:** **CRITICAL** (PII unmasked across users + recipients, list AND detail views)
**Status:** **DRIFT-30 escalated and broadened — affects `/v1/users` LIST AND DETAIL, plus all 4 recipient variants**

## Question answered

DRIFT-30 (Batch C) flagged `account_details` returned unmasked on recipient detail. Phase-3 question: **how wide is the disclosure?**

Answer: **WIDER than DRIFT-30 — extends to `/v1/users` (list AND detail) and to every recipient variant (SPEI / ACH / USDT / SWIFT).**

## Findings

### Finding 6.1 — `GET /v1/users` (LIST view) leaks `associated_persons[].ssn` unmasked — CRITICAL

The list view (`?limit=5`) returned 3 of the listed users with `associated_persons[0].ssn` in plaintext (in our case, the test SSN `"000-00-0000"` — but the schema would expose real SSNs in production). **List view is worse than detail view** because one paginated call returns N SSNs at once.

Evidence:
```
$.data[2].associated_persons[0].ssn = 000-00-0000
$.data[3].associated_persons[0].ssn = 000-00-0000
$.data[4].associated_persons[0].ssn = 000-00-0000
```

### Finding 6.2 — `GET /v1/users/{id}` leaks `associated_persons[].ssn` + `document_number` unmasked — CRITICAL

The user-detail returns SSN and `document_number` for every associated person, plaintext. Sample:
```
$.associated_persons[0].ssn = 000-00-0000
$.associated_persons[0].document_number = FAKE-DOC-00000001
```

This is DRIFT-30 extended from recipients to users. Confirmed 7 unmasked sensitive fields on a single GET.

### Finding 6.3 — `GET /v1/recipients/{id}` leaks bank/wallet identifiers unmasked — CRITICAL

Confirmed on all 4 variants:

| Variant | Unmasked fields |
|---|---|
| SPEI (MX) | `clabe`, `doc_number` (RFC) |
| ACH (USD) | `routing_number`, `account_number`, `doc_number` |
| USDT (TRON) | `address` (full wallet address) |
| SWIFT (EUR) | `account_number` (IBAN), `swift_code`, `doc_number` |

This confirms DRIFT-30 isn't a SPEI-only quirk — every recipient flavor returns full account identifiers in plaintext on detail.

### Finding 6.4 — `GET /v1/recipients?user_id=...` LIST does NOT leak (good) — CONTROL

The list view of recipients does not contain `account_details` (we verified — 0 unmasked sensitive fields). So the disclosure is on detail-only for recipients. List for `/v1/users` is the one that leaks (Finding 6.1).

### Finding 6.5 — `GET /v1/banks?country_code=ZZZ` reveals the country allowlist — LOW

```
{"error": "Invalid request data", "details": [{"path":"country_code","message":"Invalid literal value, expected \"CO\"","code":"invalid_literal"}]}
```

Confirms the country allowlist is hardcoded to literal `"CO"` only (already known via DRIFT-7 / GAP-32). Reveals the implementation choice (Zod `z.literal('CO')`) to anyone probing.

### Finding 6.6 — `GET /v1/this-endpoint-does-not-exist` returns a SigV4 base64 hash — LOW (DRIFT-39 confirmed at endpoint level)

```
{"message":"Invalid key=value pair (missing equal-sign) in Authorization header (hashed with SHA-256 and encoded with Base64): '/vTWWppr+9Ffd3RLXh9wej0ya8LpUse0iLAGaMR5ArI='."}
```

This is the AWS API Gateway SigV4 fallback path. The base64 string is a *hash* of the Authorization header, not the secret itself — so it's not a credential leak. But it confirms:
- The unknown-path handler routes through the SigV4 authorizer.
- The response includes a verbatim path of the auth-failure with an internal-format error.
- Same disclosure class as DRIFT-39 (DELETE /v1/recipients/{id}).

### Finding 6.7 — Error envelope drift on 404 — LOW

(See Probe 3 — already documented.) `/v1/users/{id}` 404 uses `{code, message}` while `/v1/recipients/{id}` 404 uses `{error: {code, message, details}}` — a 5th envelope shape on top of DRIFT-6's 4.

## Reproduction

```bash
python3 evidence/work/security/info-disclosure-account-details/probe_disclosure.py
```

Output: `01-disclosure-sweep.json` — sweeps users-list, user-detail, recipients-list, all 4 recipient-detail variants, and 5 error-trigger probes. All read-only — no resources created.

## Expected hardened API

For account / identity numbers (SSN, EIN, IBAN, CLABE, account_number, wallet_address):
- LIST views: omit entirely, or return masked-only (last-4-chars).
- DETAIL views: mask everything except the last 4 chars; provide a separate authenticated `GET /v1/recipients/{id}/account-details` (or similar) that requires an additional permission scope and is rate-limited + audit-logged.
- Even authenticated, audit every retrieval — for fintech this is a compliance ask (SOX/GLBA "need-to-know" + Reg P).

## Observed Kira behavior

- Plaintext PII / account identifiers in both list AND detail.
- No mask-only mode, no segregated detail endpoint.
- Likely the same field is used to write AND read — Kira hasn't split the read model.

## Impact

- Insider browsing: any operator (or compromised integrator) can scrape the entire SSN database via paginated `/v1/users`.
- Data-at-rest concerns: if responses are cached anywhere upstream (without `Cache-Control: no-store` — Finding 5.3), the PII propagates.
- Compliance: PCI-DSS Reqs 3.x (mask PAN), GLBA Safeguards Rule, state money-transmitter audits — all expect masking by default.
- The CRITICAL severity is calibrated on the fact that **list view exposes SSN in bulk** — that's the single worst class.

## Remediation hint

Add a read-projection layer that masks SSN/EIN/account_number/CLABE/IBAN/wallet_address on every list AND detail endpoint by default. Gate full plaintext behind a separate scope + audit log.

## Files

- `probe_disclosure.py`
- `01-disclosure-sweep.json`
