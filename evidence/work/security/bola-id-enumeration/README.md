# Probe 3 — BOLA / IDOR Enumeration

**OWASP API Top 10 mapping:** API1:2023 — Broken Object Level Authorization
**Severity:** LOW (no cross-tenant 200; minor info leak via 404 echoes)
**Status:** **No BOLA. Two ancillary findings: error envelope drift + ID echo in 404 body.**

## Question answered

DRIFT-4/30 left open: can the integrator hit `GET /v1/users/{id}`, `GET /v1/recipients/{id}`, `GET /v1/virtual-accounts/{id}` with a guessed UUID and get back a different tenant's data?

Answer: **No.** Every guessed UUID returned 404. No cross-tenant 200 observed across 16 attempts.

## Reproduction

```bash
python3 evidence/work/security/bola-id-enumeration/probe_bola.py
```

Reads our own `user_id` and `recipient_id` from existing evidence (`users/03-success.json`, `recipients/01-success-201-spei.json`) — does NOT create new resources.

## Test matrix

| Family | Attempts | All non-control 200? | Notes |
|---|---|---|---|
| `GET /v1/users/{id}` | 7 (own, 3 random, sequential±1, zeros, malformed) | 0 of 6 leaked | 404 except control (200) and malformed (400) |
| `GET /v1/recipients/{id}` | 6 | 0 of 5 leaked | 404 except control |
| `GET /v1/virtual-accounts/{id}` | 3 | 0 of 3 leaked | 404 (we don't own any VA — every attempt was pure enumeration) |

## Findings (LOW)

### F3.1 — Error envelope drift on 404

- `GET /v1/users/{guessed_uuid}` 404 body: `{"code":"not_found","message":"User with ID <uuid> not found"}`
- `GET /v1/recipients/{guessed_uuid}` 404 body: `{"error":{"code":"NOT_FOUND","message":"Recipient with ID <uuid> not found","details":{}}}`

Two distinct envelope shapes (a 5th total, in addition to DRIFT-6's four). Type-safe codegen against either won't parse the other.

### F3.2 — Error message echoes the probed UUID

Both 404 bodies include the probed UUID in the message text (`"User with ID caa363ce-… not found"`). This is a minor info leak — it confirms to an attacker that *their probe was processed* (rules out gateway-level rejection), and creates an oracle for log-correlation attacks. The hardened response would be `"User not found"` (no UUID) or 403 (which doesn't distinguish "missing" from "not yours").

### F3.3 — 404 lumps "doesn't exist" with "doesn't belong to caller"

Even with our own ID (control), the response is 200. With anyone else's ID, the response is 404. This means an attacker who can guess a real-but-cross-tenant UUID (extremely unlikely with v4 UUIDs) would receive 404 — same as random. So **no enumeration oracle.** This is acceptable for v4 UUIDs but would be a problem if Kira ever switched to sequential IDs.

## Expected hardened API

Return 403 (or 404 with a generic message that does NOT echo the queried ID) for any resource the caller doesn't own. The 200/404 distinction on cross-tenant IDs is a side-channel; combining it with response timing might still leak existence.

## Observed Kira behavior

- BOLA proper: NOT present.
- 404 echoes the UUID (minor info leak).
- Two different error envelope shapes on adjacent resources (consistency bug).

## Impact

- Existence-of-ID oracle: present (404 echoes the ID, confirms processed).
- Cross-tenant data leak: NOT observed.
- Codegen drift: present (two 404 shapes).

## Remediation hint

Standardize 404 envelope across resources; drop the requested ID from the message text; consider 403 (uniform) for unauthorized-OR-missing.

## Files

- `probe_bola.py`
- `01-bola-results.json`
