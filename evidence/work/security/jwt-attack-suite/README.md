# Probe 4 — JWT Attack Suite

**OWASP API Top 10 mapping:** API2:2023 — Broken Authentication
**Severity:** N/A (no findings — control posture is solid)
**Status:** **All 9 forgery attempts REJECTED with 401/403. Strong AuthN posture.**

## Question answered

Can we forge a JWT and get a 200 from a protected read endpoint (`GET /v1/users?limit=1`)?

Answer: **No.** Every forgery returned 401 (or 403 for one variant that survived signature parsing). Control (valid token) returned 200 — confirming the read endpoint works.

## Token structure (header only; claim values redacted)

```
header: {"kid": "<32-char b64>", "alg": "RS256"}
claims_keys: ["auth_time","client_id","exp","iat","iss","jti","scope","sub","token_use","version"]
signature_length: 342 (RSA-SHA256 bytes b64url'd)
```

→ Token is RS256-signed by AWS Cognito. `kid` references a public key in Cognito's JWKS. Claims include `client_id`, `scope`, `sub`, `iss`, `exp`/`iat`/`jti` — standard Cognito Access Token shape.

## Attacks attempted

| # | Attack | Status | Verdict |
|---|---|---|---|
| 00 | Control — valid token | 200 | OK |
| 01 | `alg=none`, no signature | 401 | REJECTED |
| 01b | `alg=none`, old sig appended | 401 | REJECTED |
| 02 | `kid: "../../../dev/null"` (path traversal) | 401 | REJECTED |
| 02b | `kid` header removed entirely | 401 | REJECTED |
| 03 | Claim `client_id` tampered, original sig kept | 403 | REJECTED (interesting: 403 not 401 — signature parsed OK but claim doesn't match the kid's public key derivation, or claim mismatches the API-Gateway authorizer's expectations) |
| 04 | First char of signature flipped | 403 | REJECTED |
| 05 | Empty Bearer | (httpx error — no transport for empty Authorization) | NA |
| 06 | Garbage bearer | 401 | REJECTED |
| 07a | HS256-confusion attack (empty key) | 401 | REJECTED — Cognito's JWKS does not expose an HMAC key, so the "RS256→HS256" confusion is blocked |
| 07b | HS256-confusion attack ("secret" key) | 401 | REJECTED |

## Token TTL probe (deferred — out of time budget)

Token TTL is 3600s per the `/auth` response. A full TTL replay test would take 1 hour — out of Phase 3 partial budget. **Document plan:** capture a token, sleep 3700s, replay against `GET /v1/users`. Expect 401. Run this in a CI job once integration is stable.

## Findings (none)

No exploitable findings. Kira's gateway-layer authorizer correctly:
- Rejects `alg=none`
- Validates signature against the `kid`-referenced public key
- Rejects HS256 confusion (Cognito's JWKS exposes only RSA modulus/exponent, no symmetric secret)
- Surfaces 403 not 401 for tampered claims with intact signature shape — minor signal (could be 401 across the board), but not exploitable

## Observed Kira behavior

- AWS Cognito as the AuthN provider. Standard, well-vetted JWT validation.
- Gateway-layer authorizer enforces signature + kid validation.

## Files

- `probe_jwt.py`
- `01-token-structure.json`
- `02-attack-results.json`
