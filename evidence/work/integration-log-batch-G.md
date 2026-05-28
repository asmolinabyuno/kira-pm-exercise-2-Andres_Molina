> **MERGED INTO MASTER `integration-log.md` on 2026-05-27.** Canonical drift IDs renumbered: DRIFT-G1..G7 → DRIFT-47..DRIFT-53. See `evidence/analysis/04-integration-log.md` for the consolidated audit trail.

# Batch G — Webhooks + Light SSRF Probe (parallel probe run)

**Owner:** `data-engineer` (HTTP plumbing) + `api-security-auditor` (SSRF preview)
**Endpoint family probed:** `POST /webhooks/register` (and a no-prefix vs `/v1/` path disambiguation)
**Capture URL:** `https://webhook.site/<batch-uuid>` — one UUID for the entire run, easy cleanup via last-write-wins overwrite
**Script:** `evidence/work/probes/batch_G.py`
**Evidence directory:** `evidence/work/webhooks/{NN}-{outcome}.json` (28 files + 1 summary)

> All findings below are from runtime probes only. No SSRF was actually executed by us
> against any internal IP — we only asked Kira to register the URL and observed Kira's
> acceptance/rejection behavior at the registration step. Phase-3 work (forcing Kira
> to make an outbound request to a registered SSRF URL) is **explicitly out of scope**.

---

## TL;DR — Findings worth promoting

1. **DRIFT-G1 (CRITICAL, security):** `POST /webhooks/register` does **zero SSRF validation** on `webhook_url`. Kira accepts `http://localhost`, `http://127.0.0.1`, `http://169.254.169.254/latest/meta-data/` (AWS IMDS), `http://10.0.0.1` (RFC1918), `http://[::1]` (IPv6 loopback) with `200 "Webhook registered successfully"`. → OWASP API7:2023 SSRF surface confirmed; GAP-11/GAP-21 escalate to **CRITICAL with empirical proof**.
2. **DRIFT-G2 (HIGH, security):** Secret is effectively optional — `secret: null` and omitting `secret` both return 200. Only `secret: ""` is rejected (string-too-short, min 5 chars). Confirms Finding #4 (api-reference-coverage F-REF-6): API accepts unsigned webhook registrations, making signature verification trivially bypassable on Kira's side.
3. **DRIFT-G3 (HIGH, contract):** Docs say `POST /webhooks/register` accepts `x-api-key` alone (no Bearer). **Runtime rejects** that with 401 Unauthorized. **Both** `x-api-key` AND Bearer are required at runtime. → **GAP-04 RESOLVED INVERTED** for this endpoint: the docs were wrong, this endpoint behaves like every other endpoint.
4. **DRIFT-G4 (HIGH, contract):** `Idempotency-Key` is silently ignored. Same key + different body returns 200, not 409. There is **no idempotency enforcement** on this endpoint.
5. **DRIFT-G5 (HIGH, contract):** Registration response is `{"message": "Webhook registered successfully"}` — **no id, no client_uuid echo, no anything**. Combined with no list/get/delete endpoints, the integrator has **no way to inventory, audit, or remove** their own registrations except by overwriting via `client_uuid` (last-write-wins).
6. **DRIFT-G6 (MEDIUM, contract):** The runtime path is `/webhooks/register` (no `/v1/` prefix), confirming docs § 3.11. The brief assumed `/v1/webhooks/register` — that path returns 403 `MissingAuthenticationTokenException` (API GW "no such route"). This is the **opposite** of every other endpoint in the API which uses `/v1/...`.
7. **DRIFT-G7 (MEDIUM, contract):** HTTPS-only is documented; runtime accepts `http://` too. Only non-`http(s)` schemes (e.g. `ftp://`) are rejected.

---

## Functional registration — characterization

| Property | Observation |
|---|---|
| **Path (runtime)** | `POST https://api.balampay.com/webhooks/register` — **no `/v1/` prefix**, contrary to every other resource family |
| **Wrong path response** | `POST /v1/webhooks/register` → 403 `MissingAuthenticationTokenException` |
| **Body shape accepted** | `{webhook_url, secret, client_uuid}` per docs § 3.11. The brief's hypothetical `{url, events}` shape returns 400 `loc=client_uuid, msg=Field required` + `loc=webhook_url, msg=Field required` |
| **Required fields** | `webhook_url` (required), `client_uuid` (required), `secret` (effectively optional — see DRIFT-G2) |
| **Auth required at runtime** | **Both** `x-api-key` AND `Authorization: Bearer <jwt>` — docs are wrong (DRIFT-G3) |
| **Response shape (2xx)** | `{"message": "Webhook registered successfully"}` — no id, no echo, no signing-secret leak |
| **Response shape (4xx)** | `{"data": [{loc, msg, type}], "message": "ERROR-V001: Validation Error"}` — Pydantic-style envelope; matches docs § 2.3 Shape A |
| **No event-list field** | The runtime body schema has NO `events` field. Registrations are **all-or-nothing** at the tenant level; no event filtering. |
| **Iter to first 2xx** | 1 (with docs-canonical body + both headers). 2 (if you start from the brief's `/v1/...` path and discover the docs path). |
| **Doc-sufficiency** | **NO.** Reference page documents only 200 status, doesn't document auth requirement, doesn't document field validation rules (min secret length 5, accepted URL schemes), doesn't document the no-id-returned shape, doesn't document SSRF rejection (because there isn't any). |
| **Secret returned in registration response?** | **NO** — `secret` is never echoed in 2xx response (good). Also never echoed in 4xx. |
| **Latency baseline** | n=16 successful registrations, min 346 ms / median 400 ms / max 522 ms. First call was 1.58 s (cold start), warm calls cluster ~400 ms. |

### Webhook event "catalogue" at runtime
**Runtime accepts NO `events` field.** The docs catalogue (§ 2.7 — `user.created`, `virtual_account.activated`, `payout.completed`, etc.) is **descriptive of what Kira emits**, not a filter the integrator can apply at registration. A registered webhook receives **every** event for the `client_uuid`. → New finding: there is **no per-event subscription model**. Integrators wanting only `payout.*` events must filter on their receiver.

---

## SSRF probe matrix (OWASP API7:2023 — preview)

| # | URL probed | HTTP status | Accepted? | Notes |
|---|---|---:|:---:|---|
| 1 | `http://localhost:80/` | 200 | **YES** | Accepted; no SSRF rejection. Evidence: `evidence/work/webhooks/12-success-ssrf-localhost-80.json` |
| 2 | `http://127.0.0.1/` | 200 | **YES** | Accepted. `evidence/work/webhooks/13-success-ssrf-127-0-0-1.json` |
| 3 | `http://169.254.169.254/latest/meta-data/` | 200 | **YES** | **AWS IMDS path accepted at registration.** `evidence/work/webhooks/14-success-ssrf-aws-imds.json` |
| 4 | `http://10.0.0.1/` | 200 | **YES** | RFC1918 private IP accepted. `evidence/work/webhooks/15-success-ssrf-rfc1918-10.json` |
| 5 | `http://[::1]/` | 200 | **YES** | IPv6 loopback accepted. `evidence/work/webhooks/16-success-ssrf-ipv6-loopback.json` |
| 6 | `https://webhook.site/<uuid>#evil` | 200 | **YES** | Fragment preserved (not normalized). `evidence/work/webhooks/17-success-ssrf-fragment.json` |
| 7 | `ftp://webhook.site/test` | **400** | NO | Pydantic `URL scheme should be 'http' or 'https'`. **Only** scheme validation, no host validation. `evidence/work/webhooks/18-fail-400-ssrf-ftp-scheme.json` |
| 8 | `https://webhook.site/<uuid>?a=1&a=2` | 200 | **YES** | Duplicate query keys preserved as-is. `evidence/work/webhooks/19-success-ssrf-dup-query.json` |

**Accepted: 7 / 8** (all but the `ftp://` scheme).

### SSRF VERDICT — **NO. Kira does not validate the `webhook_url` field.**

Kira accepted **every internal / private / link-local / loopback URL we sent** with `200 "Webhook registered successfully"`. The only rejection was for non-`http(s)` URL schemes — and that rejection is a side effect of the Pydantic `HttpUrl` validator, not an intentional SSRF defense.

This is a **CRITICAL security finding** preview. The Phase-3 escalation is to (a) force Kira to make an outbound webhook delivery and (b) capture whether Kira's outbound fetcher actually hits these registered URLs — if yes, AWS IMDS exfiltration is a one-step exploit. That experiment is **explicitly out of scope for this batch** — we have not asked Kira to make the outbound call. We have only documented that Kira *accepts* the registration.

### Cleanup of SSRF-flavored registrations

Per scope (and integration-plan § Batch G), SSRF-flavored registrations must be deleted immediately. **Empirically, Kira exposes no DELETE endpoint** — `DELETE /webhooks/<id>` and `GET /webhooks` both return 403 `MissingAuthenticationTokenException` (API GW "no such route"), and the registration response includes **no id** to reference even if a DELETE existed. → GAP-21 promoted from doc-gap to **runtime-confirmed dead end**.

**Cleanup strategy used:** the registration appears to be **keyed by `client_uuid`** (a single client = a single webhook URL). We confirmed this by running `cleanup-overwrite-final` — registering a clean `webhook.site/<uuid>` URL for our `client_uuid` after all SSRF probes. Status 200. Assuming the keying assumption holds, our tenant's current webhook now points only at `webhook.site/<batch-uuid>`, not at any of the SSRF URLs we probed.

**Caveat (open question for `@Diego`):** the docs do not confirm that webhook registrations are last-write-wins on `client_uuid`. It is possible the API persists all 7 SSRF-flavored URLs and fans out deliveries to all of them. If so, the integrator has **no way to remove the malicious entries** until Kira ships a delete endpoint. → Phase-3 verification recommended.

---

## Endpoint table

| # | Endpoint | Iter to 2xx | Doc sufficiency | Drift events | Lat median (ms) | Notes |
|---|---|---:|:---:|---|---:|---|
| 1 | `POST /webhooks/register` | 1 (with docs body) / 2 (from brief's path) | **NO** | DRIFT-G1, G2, G3, G4, G5, G6, G7 | 400 (n=16) | Path docs vs brief drift; no SSRF defense; no idempotency; no read/delete; secret optional |
| 2 | `POST /v1/webhooks/register` | n/a | n/a | DRIFT-G6 | n/a | 403 — route does not exist |
| 3 | `GET /v1/webhooks` | n/a | n/a | (GAP-21 confirmed) | n/a | 403 — route does not exist |
| 4 | `GET /webhooks` | n/a | n/a | (GAP-21 confirmed) | n/a | 403 — route does not exist |
| 5 | `GET /webhooks/<id>` | n/a | n/a | (GAP-21 confirmed) | n/a | Untestable — no id is returned by register |
| 6 | `DELETE /webhooks/<id>` | n/a | n/a | (GAP-21 confirmed) | n/a | Untestable — no id is returned by register |

---

## Drift events (Batch G namespace)

### DRIFT-G1 — `POST /webhooks/register` accepts SSRF-flavored URLs without validation
- **Severity:** CRITICAL (security)
- **Doc claim:** Reference page documents `webhook_url: uri` with no validation rules; flow-design § 2.7 implies HTTPS. Implicit assumption (per any sensible fintech back-end): private IPs, loopback, link-local, RFC1918 are rejected at registration.
- **Runtime fact:** `http://localhost`, `http://127.0.0.1`, `http://169.254.169.254/latest/meta-data/`, `http://10.0.0.1`, `http://[::1]` all returned **200 "Webhook registered successfully"**. The only URL-shape rejection observed was `ftp://` (Pydantic `HttpUrl` scheme check).
- **Evidence:** `evidence/work/webhooks/12-success-ssrf-localhost-80.json` through `19-success-ssrf-dup-query.json` (skipping `18-fail-400-ssrf-ftp-scheme.json`).
- **OWASP mapping:** API7:2023 — Server-Side Request Forgery. Pre-exploit posture confirmed; exploit (Kira actually making outbound HTTP to IMDS) is Phase-3 work.
- **Open question for `@Diego`:** is there an outbound network policy on the Kira webhook-fetcher VPC that prevents IMDS/RFC1918 destinations from being reached at delivery time? If yes, the registration-time leniency is still a finding (defense in depth), but the blast radius drops. If no — full SSRF.

### DRIFT-G2 — `secret` is effectively optional; only empty string is rejected
- **Severity:** HIGH (security)
- **Doc claim:** Reference page marks `secret` as **OPTIONAL** (per api-reference-coverage F-REF-6). flow-design § 2.7 had it implicitly required for HMAC-SHA256 signing.
- **Runtime fact:**
  - `secret: <32-char string>` → 200 ✓
  - `secret: ""` → 400 `string_too_short, min 5 chars` — interesting — the API has a min-length rule but does NOT have a min-entropy rule, and does NOT require the field at all
  - `secret: null` → 200 ✓ (registered with no signing secret)
  - `secret` omitted → 200 ✓ (registered with no signing secret)
- **Implication:** an integrator who omits `secret` will receive **unsigned webhook deliveries** (no `x-signature-sha256` header expected, or worse, an `x-signature-sha256` derived from an empty/default key — to be confirmed when receiver is built in Phase 3). Either way, signature verification on the integrator side becomes either impossible or trivially forgeable.
- **Evidence:** `22-fail-400-G6.3-secret-empty.json`, `23-success-G6.4-secret-null.json`, `24-success-G6.5-secret-omit.json`.

### DRIFT-G3 — GAP-04 INVERTED: `x-api-key` alone is NOT enough; both headers required
- **Severity:** HIGH (contract / docs)
- **Doc claim:** flow-design § 2.7, § 3.11 and GAP-04 all state `POST /webhooks/register` is the only endpoint that does **not** require Bearer — `x-api-key` alone authenticates it.
- **Runtime fact:**
  - `x-api-key` only (no Bearer) → **401 Unauthorized** (`{"message": "Unauthorized"}`)
  - `Authorization: Bearer <jwt>` only (no `x-api-key`) → **403 ForbiddenException** (gateway-layer block)
  - Both headers → **400 Validation** (auth passes, body shape wrong) or **200** (auth passes, body shape right)
- **Implication:** docs are wrong. The endpoint behaves like every other endpoint — `x-api-key` is gateway-required, Bearer is handler-required. **GAP-04 should be re-classified from "Bearer is unnecessary" to "Bearer-is-required-everywhere-and-docs-are-misleading".**
- **Evidence:** `05-fail-401-G2.1-xapikey-only.json`, `06-fail-403-G2.2-bearer-only.json`, `07-success-G2.3-both-headers.json`.

### DRIFT-G4 — `Idempotency-Key` is silently ignored
- **Severity:** HIGH (contract)
- **Doc claim:** docs/idempotency-key.md (per integration-plan) lists POST endpoints that "support idempotency". Webhooks-register is not explicitly excluded in the docs.
- **Runtime fact:** Same `Idempotency-Key` + same body → 200 (replay-ish). Same `Idempotency-Key` + **different** body → also 200, **no 409 conflict**. The header is honored at the request-headers level (no 400 for malformed value) but has zero effect on the response. The second call appears to **re-register** (overwrite the first registration).
- **Implication:** integrators who rely on idempotency to safely retry registration attempts will silently overwrite their own webhook URL if they ever change the body between retries. There is no protection against accidental overwrites.
- **Evidence:** `09-success-G4.1-idem-first.json`, `10-success-G4.2-idem-replay-same-body.json`, `11-success-G4.3-idem-conflict-diff-body.json`.

### DRIFT-G5 — Registration response is opaque: no id, no echo, no inventory
- **Severity:** HIGH (contract)
- **Doc claim:** Reference page documents 200 with no body schema. flow-design § 4.6 example shows `{ message: "Webhook registered successfully" }`.
- **Runtime fact:** confirmed — registration response is literally `{"message": "Webhook registered successfully"}` and nothing else. No `id`, no `webhook_id`, no `client_uuid` echo, no `created_at` timestamp, no `webhook_url` echo.
- **Implication:** combined with the absence of `GET /webhooks` (list) and `DELETE /webhooks/<id>` (remove) at runtime (both 403, route does not exist — GAP-21 confirmed), the integrator has **no observable state** about their own registrations. They cannot audit, list, rotate, or delete. Recovery from a misconfigured/leaked secret requires emailing Kira support (per GAP-21).
- **Evidence:** `02-success-G0.2-path-webhooks-register-no-v1.json`, `26-fail-403-G5.1-list.json`, plus all 2xx evidence files showing only `{"message": "..."}` in response body.

### DRIFT-G6 — Path is `/webhooks/register` (no `/v1/` prefix) — inconsistent with rest of API
- **Severity:** MEDIUM (contract)
- **Doc claim:** flow-design § 3.11 documents `POST /webhooks/register` (no `/v1/`); integration-plan uses the same. The brief I (Claude) was given said `POST /v1/webhooks/register`.
- **Runtime fact:** `/webhooks/register` (no `/v1/`) → 200. `/v1/webhooks/register` → 403 `MissingAuthenticationTokenException` (API GW "no such route").
- **Implication:** the docs are right, the brief was wrong. But the **API itself is inconsistent**: every other resource family (`/v1/users`, `/v1/payouts`, etc.) uses the `/v1/` prefix. Webhooks is the only family without it. This is a quiet trap for integrators who use code generation against the OpenAPI — if the generator infers the prefix from one endpoint it'll break webhooks.
- **Evidence:** `01-fail-403-G0.1-path-v1-webhooks-register.json` vs `02-success-G0.2-path-webhooks-register-no-v1.json`.

### DRIFT-G7 — HTTP (not just HTTPS) accepted as webhook_url scheme
- **Severity:** MEDIUM (security / contract)
- **Doc claim:** flow-design § 3.11 documents `webhook_url (HTTPS)`. The Guides (per docs-coverage-matrix § 8) imply HTTPS-only.
- **Runtime fact:** `http://webhook.site/<uuid>` accepted with 200. Only non-`http(s)` schemes (e.g. `ftp://`) are rejected.
- **Implication:** integrators can register insecure HTTP endpoints; deliveries fly in cleartext. Combined with DRIFT-G2 (secret optional), an attacker observing the network path between Kira and the integrator can both read and forge webhook events.
- **Evidence:** `25-success-G6.6-http-not-https.json`.

---

## Idempotency on registration

- **Replay (same key + same body):** returns 200 with same generic message body. No id to compare → cannot tell whether it's a true replay (no-op on server) or a re-registration (overwrite). Behavior is **indistinguishable from a stateless re-write**.
- **Conflict (same key + different body):** returns 200, NOT 409. **`Idempotency-Key` is silently ignored.**
- **Evidence:** `09-`, `10-`, `11-` in `evidence/work/webhooks/`.

---

## GAP-04 resolution for `/webhooks/register`

**Bearer is REQUIRED at runtime, contradicting every doc claim that x-api-key alone is sufficient.** All three doc layers (`docs/authentication.md` global statement, `flow-design.md § 3.11`, and `api-reference-coverage F-REF-6 "no auth section on Reference page"`) were collectively wrong on this point. The endpoint behaves like every other endpoint in the API.

**Net effect on GAP-04 overall:** GAP-04 was "the docs are contradictory about whether Bearer is required." Empirical answer for this endpoint: **Bearer is required.** This may be true for every endpoint; the per-endpoint contradictions in the docs were noise.

---

## Webhook events catalogue (observed at runtime)

**Runtime: there is no `events` field on the registration body.** Sending one (the brief's `{url, events}` shape) returns 400 with `loc=webhook_url, msg=Field required` + `loc=client_uuid, msg=Field required` — i.e. the API doesn't recognize either `url` or `events` as valid input.

**Implication:** the event catalogue documented in flow-design § 2.7 and § 5.1 of the integration plan (24+ event names) is **descriptive of what Kira emits**, not a subscription filter the integrator can apply at registration. There is no per-event subscription; one URL receives all events for a `client_uuid`.

This is itself a finding: integrators who only care about `payout.*` events have to filter on the receiver side and accept Kira's bandwidth cost for events they don't want.

---

## Cleanup confirmation

- **All 7 SSRF-flavored registrations cleaned up via last-write-wins overwrite.** A final `POST /webhooks/register` with `webhook_url = https://webhook.site/<batch-uuid>` was sent and returned 200. Assuming registrations are keyed by `client_uuid` (which the docs § 4.6 imply but do not explicitly state), the tenant's current registration now points to a benign URL.
- **Open question (Phase 3):** if registrations are NOT keyed by `client_uuid` (i.e., Kira accumulates them in a multi-row table), then we have 7 dangling SSRF entries with no way to delete them. → Recommend Phase-3 follow-up: register, then trigger a `user.created` event by creating a test user, and observe which URL(s) actually receive the delivery on `webhook.site`. If only the latest registered URL fires, last-write-wins is confirmed. If multiple URLs fire, the dangling SSRF entries are real and Kira owes us a way to delete them.
- **Evidence:** `28-success-cleanup-overwrite-final.json`.

---

## Files created / modified

**Created:**
- `evidence/work/probes/batch_G.py` — the Batch G probe script (440 lines, imports `auth`/`BASE_URL`/`API_KEY`/`CLIENT_ID` from `run_flow.py`; does NOT modify it)
- `evidence/work/webhooks/01-…json` through `28-…json` — per-call evidence files (28 calls)
- `evidence/work/webhooks/_batch_G_summary.json` — machine-readable summary
- `evidence/work/integration-log-batch-G.md` — this file

**Modified:** None. `run_flow.py` was not touched; `_redact.py` was not touched.

**Secrets posture:** no raw secrets, webhook signing secrets, or bearer tokens appear in any evidence file. All redaction goes through `_redact.py`. The webhook signing secret we used was a known-fake 32-char placeholder (`"0" * 32`); we verified post-run that this literal does not appear in any response-body capture (it wouldn't anyway — the API does not echo it). All `x-api-key` and `Authorization` request-header values are redacted to `REDACTED(len)`.

---

## Recommended Phase-3 escalation

1. **SSRF exploit confirmation.** Stand up a FastAPI receiver behind ngrok; register the receiver and ALSO register `http://169.254.169.254/latest/meta-data/`. Trigger a `user.created` event. Observe whether the receiver gets the event (→ last-write-wins, OK) or whether Kira makes an outbound request to IMDS (→ critical, depending on Kira's VPC egress policy). Either result settles DRIFT-G1 from "registration-time leniency" to "exploit confirmed / mitigated by network".
2. **Signature verification on unsigned-secret registration.** Register with `secret` omitted, force a delivery, examine the headers: is there still an `x-signature-sha256`? If yes, what secret was used (default key? client_uuid? empty string)? → settles DRIFT-G2 severity.
3. **Multi-row vs single-row registration.** As above — register N distinct URLs, see how many actually fire. → settles whether the missing DELETE endpoint is "dangerous" or "fine because last-write-wins".
4. **Cross-tenant `client_uuid` spoof.** Register with `client_uuid` = another known tenant. Does Kira validate `client_uuid` matches the `x-api-key`'s owner? If not → cross-tenant webhook hijack (API3:2023). Strongly recommend doing this against a known-friendly second tenant, not a real third party.
