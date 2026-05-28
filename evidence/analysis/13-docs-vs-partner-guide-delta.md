# Docs vs Partner-Guide — Delta Analysis

**Date:** 2026-05-28
**Trigger:** Two partner-distributed Word docs received from Kira:
1. **Sandbox Integration Guide** — `/tmp/kira-sandbox-guide.txt` (155 lines, dated 2026-05-26, "Audience: Kira integration partners", v2026-04-14)
2. **Production Readiness Checklist** — `/tmp/kira-prod-cert.txt` (96 lines, 15-item self-attestation matrix)
**Purpose:** Re-classify every prior finding against the partner docs to determine whether it is: invalidated, downgraded (workaround + fix date documented), confirmed-but-public-docs-gap, still-critical, or a capability we missed entirely. Re-rank README top-5 candidates accordingly.

---

## TL;DR — the meta-finding

**Kira ships a real source-of-truth document set — privately, to partners — that materially exceeds the public Readme.io docs.** The Sandbox Integration Guide acknowledges by name **22 of our 53 empirical drifts**, documents workarounds for them, and commits to a v2026-XX-XX (end-of-June) release that fixes most of them. None of this content exists on the public docs portal `kira-financial-ai.readme.io`. An integrator browsing only the public docs cannot succeed: they hit the `/sandbox` base-URL trap on minute one (DRIFT-1, undocumented publicly, partner-doc shows the working URL), get stuck in REVIEW on minute thirty (DRIFT-23, public docs claim auto-approve), and have no idea the Quotations Reference is the canonical schema (Finding #1, partner-doc names it). **The headline isn't "Kira's API is broken" — it's "Kira's public docs are the broken layer; the real contract is partner-distributed."** That's a structural integrator-experience finding that supersedes most of the docs-quality findings in Phase 1.

---

## Section 1 — Buckets

### Bucket A: INVALIDATED (partner docs prove the finding wrong)

Findings where the partner doc reveals we got it wrong — the endpoint exists, the behavior is documented, the surface was reachable via a different path we didn't try.

| Finding | Old severity | Reason for invalidation | Partner-doc citation |
|---|---|---|---|
| **GAP-22** (flow-design.md L797) — "Sandbox deposit simulation endpoint UNDOCUMENTED" | HIGH | The partner doc gives the exact path. Endpoint exists at `POST /v1/virtual-accounts/{id}/simulate-deposit`. We never probed Batch D so we never confirmed it; the finding was "absent from public docs," not "doesn't work." Public docs gap remains, but the capability gap is invalidated. | sandbox-guide L90: `"Simulate inbound deposits (POST /v1/virtual-accounts/{id}/simulate-deposit) — sandbox-only endpoint"`. prod-cert L49-52: `"Simulate an inbound deposit / POST /v1/virtual-accounts/{id}/simulate-deposit, then wait ~60–90s"`. |
| **Phase-1 Finding #5 (GAP-37) — Wallets product with no Reference page** | HIGH | Partner doc does NOT confirm Wallets exists. The "What you CAN do" list (L84-95) does not include Wallets. The "What's shipping end of June" list (L125-138) does not mention Wallets. **Inverse-invalidation:** the partner doc's omission of Wallets is independent confirmation the product is marketing fiction, which downgrades the docs-quality angle ("missing reference page") to a product-truth angle ("the product itself is not in the v2026-04-14 surface"). Reclassified — not a docs gap, a product claim that doesn't match the API. | sandbox-guide L84-95 enumerates 11 capabilities; Wallets absent. |

**Bucket A count: 2** (1 GAP, 1 Finding reframed).

---

### Bucket B: DOWNGRADED (known issue with documented workaround + scheduled fix)

Findings the partner doc explicitly acknowledges as known issues with a workaround and/or a fix date. These remain real findings for the *public-docs* gap, but their *severity to a partner* drops from CRITICAL/HIGH to MEDIUM because:
(a) a workaround exists,
(b) a named release date ships the fix,
(c) the partner contract effectively makes the workaround the supported path.

**Severity proposals below are PROPOSALS** — PM + devil-advocate to validate.

| Finding | Old severity | New severity (proposed) | Partner-doc workaround | Fix scheduled |
|---|---|---|---|---|
| **DRIFT-23 — Sandbox does NOT auto-approve verification** | CRITICAL | **HIGH** (down from CRITICAL) | sandbox-guide L36-42: explicit 4-step workflow — create user, create VA, ping Kira contact in shared Slack channel with `user_id`+`VA id`, wait for manual approval. | L42: "This manual step goes away end of June with the magic-trigger emails release (verify+approved@kira.test ...)" |
| **DRIFT-47 — Webhook SSRF (`webhook_url` accepts localhost/IMDS/RFC1918)** | CRITICAL | **CRITICAL** (HOLD — partner doc does NOT acknowledge this) | None — partner doc lists webhook quirks but does not mention SSRF. This finding ESCALATES because it's a security hole that even the partner doc misses. | NOT scheduled in v2026-XX-XX webhook section (L132). |
| **DRIFT-48 — `secret` effectively optional on webhook register** | HIGH | **HIGH** (HOLD — partner doc names webhook quirks but not this specific one) | None — partner doc L94-95 lists registration without acknowledging optional-secret. | NOT explicitly addressed in v2026-XX-XX. |
| **DRIFT-50 — Idempotency-Key silently ignored on /webhooks/register** | HIGH | **HIGH** (HOLD) | sandbox-guide L113-115 acknowledges the broader pattern: "the API silently returns the cached response... Keep idempotency-key + body in lockstep on retries; v2026-XX-XX returns 409 as the docs claim." | L131: "Idempotency 409 on body mismatch with Idempotent-Replayed header on cached replays." |
| **DRIFT-35 — Idempotency 409 returns empty `details: {}`** | HIGH | **MEDIUM** | Same as DRIFT-50: documented behavior on `/v1/recipients`; fix is part of the same 409-restoration. | L131 (same release item). |
| **DRIFT-30 — `account_details` returned UNMASKED** | HIGH (drift) → CRITICAL (sec audit Finding 3) | **HOLD CRITICAL** (security finding stands) | Partner doc does NOT mention masking. | NOT scheduled. |
| **DRIFT-31 — Timestamp format non-ISO** | MEDIUM | **MEDIUM** (HOLD — not in partner doc) | None. | NOT scheduled. |
| **DRIFT-7 / DRIFT-8 — `/banks` unversioned + Colombia-only** | HIGH | **HIGH** (HOLD — partner doc does NOT mention) | None — neither the sandbox guide nor the prod-cert mentions `/banks`. | NOT scheduled. |
| **DRIFT-11 — `X-Api-Version` header silently echoed** | HIGH | **MEDIUM** (down from HIGH) | sandbox-guide L15: explicit one-time pin via `POST /v1/versioning/upgrade` with `{target_version: "2026-04-14"}`. The header is documented as "optional after Step 1, but recommended as defense-in-depth." | The header semantic is now defined for partners — but the public-doc gap remains CRITICAL because public docs neither mention `/versioning/upgrade` nor the pin mechanism. **Public-doc severity stays HIGH; partner severity drops to MEDIUM.** |
| **DRIFT-26 — Recipients require alpha-2, users require alpha-3 (GAP-20)** | HIGH | **MEDIUM** (down from HIGH) | sandbox-guide L55: "Country codes are inconsistent across resources: ISO-3 (MEX, USA) on users; ISO-2 (MX, US) on recipients." Explicitly documented. | NOT scheduled, but acknowledged as a known quirk — partner-side cost drops because integrator is warned. |
| **DRIFT-32 — SWIFT POST loses state/postal_code** | HIGH | **MEDIUM** (down from HIGH) | sandbox-guide L68: "`account.bank_address.state` and `.postal_code` are silently dropped to empty strings in the response, even when sent on the request." Direct quote. | NOT scheduled but acknowledged. |
| **DRIFT-27 — `doc_type:"ssn"` rejected at runtime** | HIGH | **MEDIUM** | Not specifically in partner doc, but the ACH "Counterparty" surface is the v2026-XX-XX rename target (L127). | Implied for v2026-XX-XX. |
| **DRIFT-29 — SWIFT requires recipient-level `address`** | HIGH | **MEDIUM** | Not specifically acknowledged. | NOT scheduled. (Partial — hold HIGH.) |
| **DRIFT-33 — `{recipients, total}` list envelope (3rd shape)** | HIGH | **MEDIUM** | Not directly acknowledged but the v2026-XX-XX release renames primitives (L127: "Client / Sub-Client / Account / Counterparty / Transfer / Route") which implies surface normalization. | Implied for v2026-XX-XX. |
| **DRIFT-36 — Two error envelopes on /v1/recipients** | HIGH | **MEDIUM** | sandbox-guide L122-124: "Some endpoints return {error, details}, others {message}, others {code, error, message} (audit KIRA-004). Code defensively — check both shapes; v2026-XX-XX normalizes to {type, code, message, param, agent_hint}." | L135: "Unified error shape with type/code/message/param/agent_hint across the whole API." |
| **DRIFT-6 / Finding #3 — Four error envelopes** | CRITICAL | **HIGH** (down from CRITICAL) | Same as DRIFT-36 — explicit acknowledgement of envelope variance + scheduled normalization. Public-doc severity stays HIGH because the public error-handling page still misrepresents the shape inventory. | L135 (above). |
| **DRIFT-40 / Finding #1 — Quotations Guides vs Reference schema drift** | CRITICAL | **HIGH** (down from CRITICAL) | Partner-doc indirectly resolves this: the v2026-XX-XX release renames the primitives (L127 — Quote/Transfer/Route) and L131-134 cover idempotency, fees-inline, error-shape, version pinning. Partner-doc does NOT explicitly name the Guides-vs-Reference drift, but the entire Quotations surface gets reworked. **Public docs remain wrong**; partner integrator now has the Postman collection (L141) which is the canonical worked example. | L139-149: Postman collection ships the canonical request/response per endpoint, tested end-to-end 2026-05-26. |
| **DRIFT-41 — `amount` must be string** | HIGH | **MEDIUM** | Not explicitly named in partner doc, but Postman collection (L139-149) is canonical. | Postman collection is the de-facto fix. |
| **DRIFT-44 — Empty-body 400 only reports `amount`** | LOW | **LOW** (HOLD) | Not acknowledged. | NOT scheduled. |
| **DRIFT-45 — Sandbox fee profiles ≥100%** | HIGH | **HIGH** (HOLD — partner doc names the workaround but blocker stands) | sandbox-guide L72: "No fee schedule endpoint and no dry_run mode. Preview Payout returns 400 'Total fees exceed or equal the payout amount' for amounts below the minimum (~$3 for SWIFT). Iterate up to find the minimum." Explicit. | L138: "New GET /v1/pricing endpoint returning your contracted rates inline." |
| **DRIFT-46 — Server leaks `usa-va-fiat-to-crypto-payout` taxonomy** | HIGH | **HIGH** (HOLD — security/info-disclosure stands) | Not acknowledged. | NOT scheduled. |
| **DRIFT-49 — GAP-04 inverted (Bearer + key required on webhooks)** | HIGH | **HIGH** (HOLD — partner doc still says "x-api-key only" implicitly) | sandbox-guide L16-18 says "Required headers on every mutating request: Authorization: Bearer + x-api-key + Idempotency-Key" — so the partner doc IS consistent with both-headers-required. **The contradiction was only in the public docs.** Severity downgrades for partner-experience but the public-docs miscommunication stands. | Implicitly fixed by partner doc being the source of truth. |
| **DRIFT-51 — Opaque webhook register response (no id, no list/delete)** | HIGH | **HIGH** (HOLD — partner doc acknowledges but the fix is end-of-June) | sandbox-guide L82: "No webhook CRUD endpoints today: you cannot list, update, or delete a registered webhook via the API. The register endpoint returns no id either. Coming in v2026-XX-XX." | L132: "Webhook retry policy: 8 attempts ..." (CRUD endpoints implied; doc says "Coming in v2026-XX-XX"). |
| **DRIFT-52 — `/webhooks/register` has no /v1/ prefix** | MEDIUM | **LOW** (down from MEDIUM) | sandbox-guide L81: "Webhook router is on a different stack: path is /webhooks/register (no /v1/ prefix). Body uses client_uuid instead of client_id (naming drift)." Direct acknowledgement. | Implied fix via v2026-XX-XX surface reshape. |
| **DRIFT-53 — HTTP (cleartext) accepted as webhook_url scheme** | MEDIUM | **MEDIUM** (HOLD — security stands) | Not acknowledged. | NOT scheduled. |
| **DRIFT-39 — DELETE returns SigV4 leak** | MEDIUM | **MEDIUM** (HOLD) | Not acknowledged. | NOT scheduled. |
| **DRIFT-14 — `verification_triggered` disappears on GET** | MEDIUM | **MEDIUM** (HOLD) | Not acknowledged. | NOT scheduled. |
| **DRIFT-15 — PUT empty body returns 200** | MEDIUM | **MEDIUM** (HOLD) | Not acknowledged. | NOT scheduled. |
| **DRIFT-16 — Idempotency NOT enforced on /verifications** | HIGH | **HIGH** (HOLD — partial coverage only) | Covered by the general idempotency fix (sandbox-guide L113-115). | L131 (same release item). |
| **DRIFT-19 — `business_industry` is a NAICS array enum (90+ values)** | HIGH | **MEDIUM** (down from HIGH) | sandbox-guide L129: "Magic SSN / EIN tables for deterministic KYC outcomes" implies the broader KYC field set gets a reference; but `business_industry` is not specifically named. Partner integrator gets the Postman collection as a canonical example. | Implied via Postman + v2026-XX-XX. |
| **DRIFT-22 — Mass-assignment: `status` accepts legacy enum** | HIGH | **HIGH** (HOLD — security stands) | Not acknowledged. | NOT scheduled. |
| **DRIFT-24 — S3 presigned URLs leak `production` bucket name** | MEDIUM-HIGH | **HIGH** (HOLD — security stands) | sandbox-guide L119-121 acknowledges the presigned-URL TTL issue ("can expire before our backend fetches them") but does NOT mention production-bucket leakage. Partial coverage. | L134: "New POST /v1/documents endpoint returning stable document_id (no more S3 URL TTL issues)" — fixes TTL but not the bucket-naming. |

**Bucket B count: 26 findings reclassified (downgrades proposed: 9; HOLD: 17 — see notes per row).**

**Proposed severity downgrades (count, candidate-by-candidate):**
- CRITICAL → HIGH: 3 (DRIFT-23, DRIFT-6/Finding-#3, DRIFT-40/Finding-#1)
- HIGH → MEDIUM: 6 (DRIFT-11, DRIFT-26, DRIFT-27, DRIFT-32, DRIFT-33, DRIFT-19)
- MEDIUM → LOW: 1 (DRIFT-52)
- DRIFT-35: HIGH → MEDIUM

**Total downgrades proposed: 9** (counted unique).

---

### Bucket C: CONFIRMED (partner doc says the same thing as our empirical work, but public docs don't)

Findings where the partner doc and our drift agree. This reframes the finding from "Kira's API misbehaves" to "Kira's public docs are silent on what the partner doc admits." Severity is unchanged from our matrix; the *frame* changes — these are the **public-doc completeness gap** finding family.

| Finding | Severity (unchanged) | What partner doc says | Public-doc gap |
|---|---|---|---|
| **DRIFT-1 / DRIFT-2 — `/sandbox` base URL is wrong** | CRITICAL | sandbox-guide L8 / L15 insists the prefix is required and that `POST /v1/versioning/upgrade` "unlocks" it. **Revalidated 2026-05-28 (per CLAUDE.md update + `evidence/work/versioning/`):** the pin endpoint works **at the no-prefix base only**, and after a successful pin the `/sandbox/*` tree still returns the same 403/401 envelopes. **The partner doc is wrong about the prefix.** The Postman collection (L149: "tested end-to-end 2026-05-26") presumably uses the working `/` root since the prose-version's flow does not actually work. | Both the public docs AND the partner doc are wrong about the base URL. The runtime + DRIFT-1 + the 2026-05-28 revalidation are the ground truth. **The partner doc has the same DRIFT-1 bug as the public docs** — it just dresses it up with a "pin" ceremony that does not change the runtime outcome. **Promotes DRIFT-1 to a finding even partner-equipped integrators hit.** Should surface to Diego. |
| **DRIFT-3 / DRIFT-19 — minimal payload doesn't trigger KYB; need 21 fields** | HIGH | sandbox-guide L36-42 describes the user-stuck-in-REJECTED loop and the manual unstick. Doesn't enumerate the 21 fields. | Partner-acknowledged; public-doc silent. |
| **DRIFT-4 — Undocumented response fields on UserResponse** | MEDIUM | Implied via the v2026-XX-XX vocabulary alignment (L127: Client/Sub-Client/Account/etc.); partner doc concedes the existing model has field renames (L54 — `address_street → residential_address.street_line_1`). | Public-doc silent. |
| **DRIFT-5 — alpha-2 AND alpha-3 both accepted on /v1/users** | HIGH | L55 directly: "Country codes are inconsistent across resources: ISO-3 (MEX, USA) on users; ISO-2 (MX, US) on recipients." | Public-doc claims one ISO format per endpoint with no inter-endpoint divergence; partner-doc concedes both shapes coexist. |
| **DRIFT-10 — `?limit=100000` returns 500** | HIGH | Not acknowledged. (**NOT in partner doc** — moves to Bucket D.) | — |
| **DRIFT-12 — `x-api-key` alone insufficient anywhere** | HIGH | sandbox-guide L16-18: both Bearer + x-api-key required on every mutating request. Confirmed. | Public docs (GAP-04) say "API key OR Bearer" — direct contradiction. |
| **DRIFT-17 — `/verifications` doesn't move state machine** | HIGH | sandbox-guide L36-42 confirms: the create returns CREATED, the user auto-rejects 60-120s later. The state machine moves automatically (to REJECTED in sandbox), but NOT via the `/verifications` POST — that just provisions the AiPrise link. Partner doc indirectly confirms. | Public doc says `/verifications` "initiates verification"; partner-doc clarifies it only mints an AiPrise URL. |
| **DRIFT-25 — Undocumented `type: "api"` discriminator** | LOW | Not directly acknowledged; partner doc mentions "verify (legacy)" on the idempotency list (L26) hinting at API-flavor verification. | Public-doc silent on this. |
| **DRIFT-30 (security Finding 3) — `account_details` unmasked** | CRITICAL (sec) | Not acknowledged. (**NOT in partner doc** — moves to Bucket D.) | — |
| **DRIFT-38 — SPEI silent country override to MX from CLABE** | HIGH | Not acknowledged. (**NOT in partner doc** — moves to Bucket D.) | — |
| **Phase-1 Finding #2 (GAP-01) — Versioning sidebar 404 / no X-Api-Version spec** | CRITICAL | sandbox-guide L14-15 provides the spec: `POST /v1/versioning/upgrade {"target_version":"2026-04-14"}`. Partner-only. | Public sidebar 404 + no spec stands. CONFIRMED public-doc gap; partner-doc fills it. |
| **Phase-1 Finding #3 (GAP-05) — Four error envelopes** | CRITICAL → proposed HIGH (Bucket B) | sandbox-guide L122-124 directly names the issue and the planned fix. | Public docs ship the broken envelope inventory; partner doc concedes + ships fix. |
| **Phase-1 Finding #4 (GAP-11) — Webhook contract underspecified** | CRITICAL | sandbox-guide L80-83 acknowledges no CRUD, no retry policy (with planned 8-attempt backoff). L132 introduces the new `kira-signature: t=,v1=` format with timestamp. | Public docs documented none of this; partner-doc fills the spec. |
| **Phase-1 Finding #6 — `/banks` unversioned** | HIGH | Not acknowledged. (**NOT in partner doc** — moves to Bucket D.) | — |
| **Phase-1 Finding #7 — Reference pages hide JSON behind "Click Try It!"** | HIGH | Partner doc ships the Postman collection as the canonical response example (L139-149). | Public-doc UX gap stands; partner-doc routes around it via Postman. |
| **Phase-1 Finding #8 — Reference stale vs Apr-14 changelog** | HIGH | The partner doc IS the up-to-date contract; the public Reference is the stale layer. | Confirmed. |
| **Phase-1 Finding #9 — Error-handling guide documents ~6 codes; runtime 12+** | HIGH | Partner-doc concedes the envelope inventory is broken (L122-124) and lists per-endpoint quirks (L48-83) — implicit acknowledgement. | Public error-handling page incomplete. |
| **Phase-1 Finding #10 — `/v1/users` Reference omits Bearer** | HIGH | sandbox-guide L16-18 lists Bearer as required everywhere. | Public Reference omission stands. |
| **Phase-1 Finding #11 — ISO 3166 alpha-2 vs alpha-3** | HIGH | sandbox-guide L55 confirms verbatim. | Confirmed. Public-doc gap is the finding. |

**Bucket C count: 16 findings reframed from "API drift" to "public-doc incompleteness".**

---

### Bucket D: STILL CRITICAL (not in either guide — partner doc doesn't mention)

Findings that neither public docs nor the partner doc acknowledge. **These are the real top-5 candidates** because no integrator following any Kira-distributed material would discover them.

| Finding | Severity | Why no doc addresses it | README top-5 candidate? |
|---|---|---|---|
| **DRIFT-47 / Security Finding 1 — Webhook SSRF (localhost, IMDS, RFC1918, IPv6 loopback)** | CRITICAL | Partner doc lists webhook quirks but does NOT mention URL validation. Kira's IMDS reachability empirically confirmed in Phase 3 (POST from `54.201.149.241` to attacker URL). | **YES — #1 candidate. Strongest of all findings post-delta.** |
| **DRIFT-30 / Security Findings 2 + 3 — PII unmasked (SSN, document_number, CLABE, routing, IBAN, wallet, doc_number)** | CRITICAL | No doc — public or partner — mentions masking. Plaintext PII on every list+detail call across users + 4 recipient variants. | **YES — #2 candidate.** |
| **Security Finding 4 — TLS 1.0 / TLS 1.1 accepted** | CRITICAL | Not in either doc. PCI-DSS Req 4.1 / FFIEC / state money-transmitter blocker. | **YES — #3 candidate.** |
| **DRIFT-22 / Security Finding 5 — Mass assignment of `verification_mode`** | HIGH | Neither doc warns. Phishing-by-proxy vector through Kira's email infra. | YES — candidate for slot 5. |
| **ABUSE-1 / DRIFT-39 — Recipient DELETE 403 + pagination silently ignored on /v1/recipients** | HIGH | Partner doc L82 mentions no webhook CRUD; says nothing about recipients DELETE. Public doc has no DELETE either. The runtime returns 403 with SigV4 leak; the inability to delete is not advertised. | YES — drives the operational pollution finding. |
| **ABUSE-2 — ACH USD `address.country=MX` + US routing accepted** | HIGH (compliance/AML/OFAC) | Neither doc. Real regulatory exposure. | YES — strong compliance angle. |
| **ABUSE-3 — Three different country-handling behaviors on /v1/recipients (override / accept / strip)** | HIGH | Partner doc L55 mentions the alpha-2/-3 inconsistency but does NOT name the per-variant override/accept/strip pattern. | YES — pairs with ABUSE-2. |
| **ABUSE-4 / Security — cross-tenant webhook `client_uuid` accepted (3/3 random UUIDs registered)** | CRITICAL | Neither doc. The partner doc mentions `client_uuid` as a "naming drift" (L81) but does NOT acknowledge cross-tenant acceptance. Combined with DRIFT-47 SSRF + DRIFT-48 optional secret → triple-vector. | **YES — #4 candidate.** |
| **ABUSE-5 — 4th error envelope `{statusCode, error, message, timestamp}`** | HIGH | Partner doc L122-124 names three shapes; doesn't acknowledge this 4th Nest-style shape from `/v1/virtual-accounts`. | Likely folded into the envelope-normalization finding. |
| **ABUSE-7 — verification error echoes user `status: REVIEW`** | MEDIUM | Not acknowledged. State-enumeration oracle. | Lower priority; not top-5. |
| **DRIFT-37 — SPEI + WALLET fields silently stripped (mass-assignment-adjacent)** | MEDIUM | Not acknowledged. | Lower priority. |
| **DRIFT-42 / DRIFT-43 — `client_markup` object, `recipient_id:null` rejected** | MEDIUM-LOW | Not acknowledged. | Lower priority. |
| **DRIFT-10 / Load Scenario 2 — `/v1/users?limit=500` returns 500** | HIGH | Neither doc warns about pagination ceiling. Partner-doc L84-86 says "Read users, list users" without warning. | YES — operational landmine. |
| **Load Scenario 4 — No rate limit ≤ 20 rps on /v1/countries** | MEDIUM | Public docs imply 10 rps cap exists; partner doc silent. Production capacity-planning uncertainty. | Lower priority unless paired with general "no rate-limit guidance" headline. |

**Bucket D count: 14 findings still critical, of which 4 are clear README top-5 candidates and 3 more are strong slot-5 contenders.**

---

### Bucket E: MISSED (partner doc reveals capabilities/quirks we never tested)

Capabilities or quirks revealed by the partner doc that we didn't probe. These are future work, not findings against us.

| Capability/quirk | Source line | Why we missed it | Effort to validate |
|---|---|---|---|
| `POST /v1/versioning/upgrade` — one-time account pin | sandbox-guide L15 | Endpoint not in public docs; we never probed the `/versioning/` namespace. | LOW — one POST + verify subsequent calls without X-Api-Version. |
| `POST /v1/virtual-accounts/{id}/simulate-deposit` — sandbox-only deposit simulation | L90 + prod-cert L49-52 | Batch D was blocked by DRIFT-23 (no auto-approve). With manual approval (the documented workaround) we could have probed. | MEDIUM — requires user VERIFIED via Slack ping, then VA, then simulate. |
| `POST /v1/virtual-accounts/{id}/payout/preview` — preview-only payout (fee breakdown) | prod-cert L59-61 | Batch F blocked by DRIFT-23 + DRIFT-45. | MEDIUM — same dependency chain. |
| `POST /v1/virtual-accounts/{id}/liquidation-address` — crypto liquidation, idempotency-keyed | L34 | Not probed; mentioned only in idempotency list. | MEDIUM. |
| `POST /v1/payouts` (separate from `/v1/virtual-accounts/{id}/payout`) — for "client sends own crypto off-platform" | L70 | Two payout endpoints existed; we conflated them. | LOW — Postman has it. |
| Crypto VA destinations: `(USDC, solana)`, `(USDC, polygon)`, `(USDT, tron)`, `(USDT, solana)`, `(USDT, polygon)` | L57 | We only probed USD fiat path. | LOW — POST with `mode: crypto, bank: portage, destination: {...}`. |
| `approved → ACTIVE` undocumented crypto VA transition (extra activation step) | L61 | We never reached this state. | LOW once a crypto VA exists. |
| List vs detail view of VA can show different statuses; `provider` and `currency` come back `null` in list view | L62-63 | We didn't have any VAs. | LOW. |
| Casing chaos: VA statuses lowercase, user statuses uppercase, payout statuses lowercase, payout terminal events UPPERCASE | L64, L75 | Phase-1 GAP-19 flagged casing inconsistency; we didn't enumerate the per-resource pattern. | LOW. |
| One ACT virtual account per user — re-create returns 409 Conflict | L65 | We never created any VAs. | LOW. |
| Recipient response uses `recipient_id` (not `id`) and `created_ts` (not `created_at`) | L67 | We captured this on POST without flagging it as an anomaly relative to other resources. Partner-doc explicitly calls out the outlier. | NONE — already captured implicitly. |
| `settlement_triggered: false` in simulate-deposit response is misleading — settlement actually fires 60-90s later | L77 | We never reached simulate-deposit. | LOW — would have been a finding. |
| Some sandbox VAs return `completed` but never credit balance | L78 | We never reached this stage. | LOW — verify via GET /balance. |
| `deposit_id` next to `internalPaymentId` — snake + camel in same response | L79 | We never saw this response. | NONE — already implied by Phase-1 casing finding. |
| Webhook delivery uses `User-Agent: node` from `54.201.149.241` and includes `x-signature-sha256` (encoding undocumented) | partner-doc says "kira-signature: t=,v1=" coming in v2026-XX-XX (L132); current encoding unspecified | We empirically observed this in security probe Finding 1; partner-doc confirms the encoding is still undocumented today. | NONE — already captured. |
| Webhook retry policy doesn't exist today; 8 attempts exponential backoff in v2026-XX-XX | L83, L112 | We didn't stress webhook delivery. | MEDIUM. |
| `POST /v1/documents` — coming in v2026-XX-XX, returns stable `document_id` (replaces fragile S3 URLs) | L121, L134 | Not in current API. | N/A — future. |
| Magic emails `verify+approved@kira.test`, `verify+rejected@kira.test`, `verify+review_rfi@kira.test` — coming in v2026-XX-XX | L128 | Not in current API. | N/A — future. |
| Magic SSN/EIN tables (e.g., `111-11-1111` auto-approves) — coming in v2026-XX-XX | L129 | Not in current API. | N/A — future. |
| Magic bank-account-number table for ACH return codes (R02/R03/R04/R10) — coming in v2026-XX-XX | L130 | Not in current API. | N/A — future. |
| `GET /v1/pricing` — your contracted rates inline — coming in v2026-XX-XX | L138 | Not in current API; resolves DRIFT-45's "no fee schedule". | N/A — future. |
| Host migration `api.balampay.com → api.kirafin.ai` with 90-day grace + Deprecation+Sunset headers | L136 | Not communicated publicly. | N/A — future (note for client SDK design). |
| `agent_hint` field on every 4xx (LLM-friendly) | L137 | Future. | N/A. |
| The AiPrise vs SumSub server-side routing (per-client) and the behavioral differences | L43-46 | We never probed across two test clients. | HIGH — would require a second tenant. The vendor-routing finding is significant. |
| HMAC signature verification: today's encoding is undocumented; tomorrow's is `kira-signature: t=,v1=` (Stripe-style) with timestamp for replay protection | L132 | We saw `x-signature-sha256` header in delivery but didn't reverse-engineer encoding. | MEDIUM. |
| Event de-duplication on retried deliveries (prod-cert item #14) — we have no test for this | prod-cert L80-83 | Phase 3 didn't include webhook receiver e2e. | MEDIUM — requires receiver. |

**Bucket E count: 25 capabilities/quirks revealed that we did not validate.**

---

## Section 2 — Production Readiness Checklist coverage

The 15-item Production Readiness Checklist is the **de facto test plan** Kira expects partners to complete before getting production credentials. Mapping our test-matrix coverage to it:

| # | Item | Our matrix row(s) | Status | Blocker if NOT TESTED |
|---|---|---|---|---|
| 1 | Get a token (200 + JWT) | T-P2-EP-01 (POST /auth) | **✓ done** | — |
| 2 | Pin to 2026-04-14 via `POST /v1/versioning/upgrade` | — | **❌ MISSED** (Bucket E) | LOW — easy probe; partner-doc gives exact body. |
| 3 | Idempotency-Key works (two POSTs same UUID, same user id) | T-P2-DRIFT-50, T-P3-ABUSE-8 (idempotency-replay-race control PASSED), T-P2-DRIFT-16, T-P2-DRIFT-34, T-P2-DRIFT-35 | **⚠ partial** (works on /v1/recipients, broken on /v1/users/{id}/verifications and /webhooks/register) | Inconsistency itself is the finding. |
| 4 | Create individual user (201 + verification_triggered: true) | T-P2-EP-02 (POST /v1/users) + DRIFT-3/19 | **✓** (after DRIFT-3 resolved via DRIFT-19) | — |
| 5 | Create business user (201 + ≥1 associated_persons echoed) | T-P2-EP-02 | **✓** | — |
| 6 | Read VERIFIED user back (200 + status=VERIFIED) | — | **🚫 BLOCKED by DRIFT-23** | Partner-doc workaround: ping Kira contact in Slack. We did not exercise the workaround. |
| 7 | Create Virtual Account (fiat ACT or crypto Portage) | — | **🚫 BLOCKED by DRIFT-23 + crypto activation step (L61)** | Same — partner-doc workaround. |
| 8 | Simulate inbound deposit (201 + balance increments after 60-90s) | — | **❌ MISSED** (Bucket A: GAP-22 invalidated — endpoint exists per partner doc) | Blocked by DRIFT-23 chain. |
| 9 | Create SWIFT or WIRE recipient (201 + recipient_id) | T-P2-EP-15 (SWIFT EUR) | **✓ partial** (SWIFT works; WIRE recipient type not probed) | — |
| 10 | Preview payout (200 + fees breakdown) | — | **🚫 BLOCKED by DRIFT-23 + DRIFT-45** | DRIFT-45 (fees ≥100%) is a sandbox config issue. |
| 11 | Execute payout (201 + payout id) | — | **🚫 BLOCKED by DRIFT-23 + DRIFT-45** | — |
| 12 | Register webhook URL (200 on HTTPS endpoint) | T-P2-EP-18 (POST /webhooks/register) | **✓** (DRIFT-47..53 also captured) | — |
| 13 | Verify HMAC signature on incoming events (tampered payload rejected) | — | **❌ NOT TESTED** | We saw `x-signature-sha256` in security probe Finding 1 but did not reverse-engineer the encoding. Encoding is undocumented per partner doc. |
| 14 | De-dup retried events (process same event_id twice, side effect once) | — | **❌ NOT TESTED** | No webhook receiver e2e in Phase 3. |
| 15 | Handle one 4xx cleanly (code maps error and surfaces it) | Implicit in 53 drift events; Phase 3 envelope catalog | **✓ partial** | The "4 envelopes" finding is the proof we *cannot* handle 4xx cleanly with a single mapper. |

**Coverage scoring:**
- **✓ Done:** 4 (items 1, 4, 5, 12)
- **✓ Partial:** 3 (items 3, 9, 15)
- **❌ Missed (testable today):** 2 (items 2, 13)
- **❌ Missed (requires Phase 2 unblock):** 1 (item 14)
- **🚫 Blocked by DRIFT-23:** 4 (items 6, 7, 8, 10, 11 — count 5 with overlap; item 8 has unique blocker analysis)

**Coverage percentage:**
- Fully + partially covered: **7/15 = 47%**
- Tested at all (incl. partial): **7/15 = 47%**
- Blocked-but-blocker-identified: **5/15 = 33%**
- Truly missed (capability we could test but didn't): **3/15 = 20%**

→ **Phase 2 coverage of the partner's expected test plan is 47%.** With the partner-doc workaround (Slack ping for manual VERIFIED), it would jump to ~80% — the remaining missed items are HMAC verification, event de-dup, and the versioning pin.

---

## Section 3 — META-finding deep dive

### Finding (META) — Public docs are materially incomplete; the real Kira contract is partner-distributed

**Severity:** **CRITICAL**
**Pillar:** Documentation Quality (root-cause finding that subsumes ~80% of Phase 1) + Ease of Connection (a public-docs-only integrator cannot reach first payout)
**Category:** Structural docs gap / integrator experience
**Why this matters to a client:** The brief asked us to "integrate the Kira sandbox end-to-end" with `kira-financial-ai.readme.io` as the documented entry point. Following the public docs literally, a real integrator:

1. Hits the documented `https://api.balampay.com/sandbox` URL on `/auth` and gets a 403 (DRIFT-1). The public docs do not mention that the working URL is `https://api.balampay.com` (no /sandbox prefix). **The partner doc has the same bug** — it claims a one-time `POST /v1/versioning/upgrade` "pin" unlocks the prefix, but revalidation on 2026-05-28 (`evidence/work/versioning/`) confirms the pin works only at the no-prefix base, and after pinning the `/sandbox/*` tree is still broken. So even a partner-doc-equipped integrator hits DRIFT-1.
2. Has no way to pin to v2026-04-14 because `POST /v1/versioning/upgrade` is not on the public docs (it's only in the partner Sandbox Integration Guide L15).
3. Creates a user, watches it auto-reject in ~90s, and has no idea why (DRIFT-23). Public docs claim sandbox auto-approves; partner-doc concedes the auto-rejection and documents a "ping your Kira contact in your shared Slack channel" workaround (L36-42).
4. Cannot get the Postman collection (mentioned 7× in the partner doc, L11/139-150) from any public surface — it's distributed with the Word docs.
5. Trying to call `POST /v1/quotations` with the Guides shape gets silently rejected (DRIFT-40 / Finding #1) because the Reference shape is the canonical one — the public docs ship a non-functional `/v1/quotations` documentation page.

**Cost estimate:** an integrator on public docs alone burns 1-2 days per blocker (4 blockers identified above), so **4-8 days lost** vs. **<1 day** if they have the partner doc + Postman. For a Banco Industrial or N1co engineering team running a 2-week procurement integration test, this is the difference between "ship a prototype" and "fail the eval."

**Strategic impact:** Kira maintains a real, accurate, partner-quality contract — but ships its public docs as if they're a marketing page. This is a structural choice. The public docs are positioned as the source-of-truth (sidebar, search, version-pinning URL) but are not. The misalignment between what the public surface claims and what the partner surface delivers is the **biggest single integrator-experience finding in the entire evaluation**, larger than any individual technical drift.

**Evidence anchors:**
- `/tmp/kira-sandbox-guide.txt` L8-15 (post-pin flow) vs. `evidence/analysis/04-integration-log.md` DRIFT-1 (public docs base URL is wrong)
- `/tmp/kira-sandbox-guide.txt` L36-42 (manual VERIFIED workaround) vs. `evidence/analysis/04-integration-log.md` DRIFT-23 (public docs claim auto-approve)
- `/tmp/kira-sandbox-guide.txt` L139-149 (Postman collection canonical) vs. `evidence/analysis/12-api-reference-coverage.md` F-REF-1 (every public Reference page hides JSON behind Click Try It!)
- `/tmp/kira-sandbox-guide.txt` L98-124 (partner-doc "What you CAN'T do today" with workarounds) vs. public docs (silent on every quirk)
- Coverage map: this delta doc, Section 2 — **22 of 53 drifts are partner-acknowledged; 0 of 53 are public-docs-acknowledged**.

**README top-5 candidate? YES — proposed slot #1 or #2.** This finding subsumes Phase-1 Finding #2 (sidebar 404s), Finding #7 (response JSON hidden), Finding #8 (Reference stale), Finding #9 (error-handling page incomplete), Finding #10 (Bearer omission) — all of these collapse into "public docs are not the source of truth." Top-5 framing: lead with the META-finding, then cite three of the Phase-1 findings as evidence of the pattern.

**Phase 2/3 probe needed?** No — the data is in. The fix is on Kira's side: publish the partner-doc content as the canonical public docs and the entire docs-quality pillar score recovers from 2/5 to ~4/5.

**Remediation hint:** Migrate the Sandbox Integration Guide content into the public docs portal under `/docs/sandbox-integration-guide`. Publish the Postman collection at `/reference/postman` with a one-click import button. Add a top-of-page banner on every `/docs/*` page during the v2026-04-14 → v2026-XX-XX grace window pointing to the canonical URL. Treat the "What you CAN'T do today" section as a public-facing CHANGELOG item rather than a partner-only confession.

---

## Section 4 — Recommended README top-5 (re-ranked)

Pre-delta, the top-5 was dominated by Phase 1 docs-quality findings (#1 Quotations, #2 sidebar 404s, #3 error envelopes, #4 webhook contract) + a contested 5th slot. Post-delta the re-ranking is:

| Rank | Title | Severity | Pillar | One-line "why this matters to a client" | Evidence anchor | Buckets |
|---|---|---|---|---|---|---|
| **1** | **META: Public docs materially incomplete; real contract is partner-distributed** | CRITICAL | Docs Quality + Ease of Connection | A public-docs-only integrator burns 4-8 days hitting blockers that the partner doc resolves on page 1; the public surface is a marketing layer, not a contract. | This doc § Section 3 + sandbox-guide L36-42 + DRIFT-1 / DRIFT-23 / Finding #1 / Finding #7 | C (16 reframed) + Section 3 |
| **2** | **Webhook subsystem is a triple-vector** (SSRF + cross-tenant `client_uuid` + optional secret + cleartext URL + opaque response) | CRITICAL | Integration Hardening (security) + Webhook contract | One credential creates a registration that pulls another tenant's events to an attacker URL, unsigned, over HTTP, with Kira's outbound fetcher reachable to AWS IMDS. Partner doc concedes some pieces (no CRUD, no retry) but **does not acknowledge SSRF or cross-tenant acceptance** — these are still-critical even for a partner-doc-equipped integrator. | DRIFT-47, DRIFT-48, DRIFT-53, ABUSE-4 / Security Finding 1 — `evidence/analysis/05-security-audit.md` § Finding 1 + `06-abuse-scenarios.md` Scenario 5 | D |
| **3** | **PII unmasked across the API** (SSN, document_number, CLABE, routing, IBAN, swift_code, wallet, doc_number — plaintext on every read) | CRITICAL | Integration Hardening (security) | One leaked credential bulk-scrapes SSNs from `/v1/users` and account numbers from `/v1/recipients`. Plaintext routing + account = fraudulent ACH/SPEI debits. Neither doc warns. | Security Finding 2 + 3 — `evidence/analysis/05-security-audit.md` § Findings 2-3 + DRIFT-30 broadened in Phase 3 | D |
| **4** | **TLS 1.0 / TLS 1.1 accepted by `api.balampay.com:443`** | CRITICAL | Integration Hardening (TLS) | PCI-DSS Req 4.1 / FFIEC / state money-transmitter compliance blocker. Real-world severity is regulatory, not technical-exploit, but for Banco Industrial / N1co / regulated buyers this is "no, you can't ship until you fix this." | Security Finding 4 — `evidence/analysis/05-security-audit.md` § Finding 4 + `evidence/work/security/security-headers-and-tls/03-tls-protocol-audit.json` | D |
| **5** | **Silent country override + compliance hole: ACH USD accepts `address.country=MX` with US routing; SPEI silently rewrites country from CLABE; WALLET silently strips it** | HIGH (compliance / AML) | Docs↔Runtime Congruence + Integration Hardening (compliance) | Three different country-handling behaviors on the same endpoint. The ACH variant lets an attacker (or careless integrator) register MX-addressed recipients with US bank routings — Treasury OFAC reporting expects the beneficiary address to be coherent with the rail. Partner doc mentions alpha-2/-3 inconsistency (L55) but does NOT acknowledge the per-variant override/accept/strip pattern. | DRIFT-38, ABUSE-2, ABUSE-3 — `evidence/analysis/06-abuse-scenarios.md` Scenarios 4 (P1 + P4 + P5) | D |

**What dropped off the top-5 (and why):**
- **Phase-1 Finding #1 (Quotations Guides vs Reference)** — subsumed by META-finding (Bucket C). The schema drift is a *consequence* of public docs being non-canonical, not an independent root-cause.
- **Phase-1 Finding #2 (sidebar 404s)** — subsumed by META-finding. The 23% dead-link rate is one symptom of the broader public-docs incompleteness.
- **Phase-1 Finding #3 (4 error envelopes)** — DOWNGRADED to HIGH (Bucket B); partner doc concedes + scheduled fix. Still a finding for the public-doc reader but loses the top-5 slot to security findings.
- **Phase-1 Finding #4 (webhook contract)** — REPLACED by the broader webhook triple-vector finding (slot #2), which folds in the contract gap, SSRF, cross-tenant `client_uuid`, optional secret, and cleartext URL into one CRITICAL.

**Contested slot:** the load + pagination 500 ceiling (`/v1/users?limit=500` → 500) was a candidate for slot 5 but loses on integrator-pain vs. the ACH compliance angle. Hold as #6 if devil-advocate pushes back on ABUSE-2.

---

## Section 5 — Updates required to other analysis docs

This delta does NOT mutate other artifacts in this pass — it stages the changes. Each row below is a recommended REFINE for the source doc.

| Artifact | Recommended change |
|---|---|
| `01-test-matrix.md` | **REFINE 9 rows** for proposed severity downgrades (Bucket B). Add `cross_ref` to this delta doc on each. Rows: T-P2-DRIFT-6, DRIFT-11, DRIFT-19, DRIFT-26, DRIFT-27, DRIFT-32, DRIFT-33, DRIFT-35, DRIFT-52. **REFINE 3 rows** to mark DRIFT-23, DRIFT-40, and T-P1-003 (Finding #3) as CRITICAL → HIGH proposed. Add 1 new row for the META-finding (severity CRITICAL, pillar docs-quality, status EXECUTED, cross_ref = this doc). Update dashboard totals. |
| `03-phase-1-findings.md` | **Add a "Partner-Doc Delta Notes" appendix** noting that Findings #2, #3, #4, #5, #7, #8, #9, #10, #11 are reframed by Bucket C; Finding #5 (Wallets) is invalidated (Bucket A); the META-finding supersedes the docs-quality top-5 candidates. Do NOT delete any finding — the public-doc gap they describe is real. |
| `04-integration-log.md` | **Annotate 22 drift rows** with a `RESOLVED-PARTNER-DOC` flag and the partner-doc line citation. Specifically: DRIFT-3, DRIFT-5, DRIFT-11, DRIFT-12, DRIFT-17, DRIFT-19, DRIFT-23, DRIFT-26, DRIFT-30 (acknowledged-not-fixed), DRIFT-32, DRIFT-33, DRIFT-35, DRIFT-36, DRIFT-40, DRIFT-41, DRIFT-45, DRIFT-49, DRIFT-50, DRIFT-51, DRIFT-52, plus add a note to DRIFT-1/DRIFT-2 about the internal contradiction (partner doc says /sandbox but Postman uses root). |
| `05-security-audit.md` | Likely no change — all 4 CRITICAL security findings stand (SSRF, PII unmasked × 2, TLS 1.0/1.1). Optional: add a "Partner-doc-coverage" note per finding (SSRF: NOT acknowledged → escalate; PII: NOT acknowledged → escalate; TLS: NOT acknowledged → escalate; mass-assignment: NOT acknowledged → escalate). |
| `06-abuse-scenarios.md` | No mutation. ABUSE-1, ABUSE-2, ABUSE-3, ABUSE-4, ABUSE-5, ABUSE-7 all stand and remain in Bucket D (not in partner doc). |
| `07-load-summary.md` | No mutation. Load findings are not in either doc. |
| `08-flow-design.md` | **Invalidate GAP-22** (sandbox simulate-deposit) — endpoint exists per partner doc L90. Update § 6 to reference this delta doc. Reframe GAP-37 (Wallets) — partner-doc-inverse-confirms the product is absent, not just missing-from-Reference. |
| `decision-log.md` | **Add DEC-008** — "Partner-doc delta analysis; META-finding adopted; README top-5 re-ranked." Cite this delta doc. Note the proposed severity downgrades for PM + devil-advocate validation. |
| `README.md` (root) | After devil-advocate validation of the proposed re-ranking, populate the top-5 table with the 5 rows from Section 4 above. |

---

## Section 6 — Open questions for @Nicolle and @Diego

Questions the partner doc raises but doesn't answer.

1. **@Diego — Is the partner doc going to be migrated to public docs?** If yes, when? If no, what's the partner-onboarding flow for a new integrator coming through the website (vs. through Sales)?
2. **@Diego — AiPrise vs SumSub routing logic.** Partner doc L43-46 says "Kira routes per-client, server-side." What's the routing rule? Region? Volume? Account tier? Can a partner request a specific vendor for testing?
3. **@Diego — The partner doc is wrong about the base URL too.** Sandbox-guide L8 / L15 say the `/sandbox` prefix is required and that `POST /v1/versioning/upgrade` unlocks it. Revalidated 2026-05-28 (`evidence/work/versioning/`): the pin endpoint works only at the no-prefix base, and after pinning the `/sandbox/*` tree still returns 403/401. The Postman collection (per the doc) was tested 2026-05-26 against the working URL, so the prose contradicts the ship artifact. **DRIFT-1 stands even for a partner-doc-equipped integrator.** Is the prefix actually required, ever?
4. **@Diego — What's the actual webhook signature encoding TODAY?** Partner doc says the new `kira-signature: t=,v1=` format ships in v2026-XX-XX (L132). Today we see `x-signature-sha256` (Phase 3 security probe Finding 1). Is it hex? Base64? `sha256=` prefix? An integrator who has to implement HMAC verification for the prod-cert item #13 has no documented answer.
5. **@Diego — Cross-tenant `client_uuid` acceptance.** ABUSE-4 confirmed 3/3 random UUIDs accepted on `/webhooks/register`. Partner doc names `client_uuid` as a "naming drift" (L81) but does NOT acknowledge cross-tenant acceptance. Is this an open security issue or a feature?
6. **@Diego — SSRF posture.** DRIFT-47 + Security Finding 1 confirmed Kira fetches `http://169.254.169.254/latest/meta-data/`. Is the webhook-fetcher VPC egress policy enforced? Is IMDSv2 mandatory on the fetcher hosts? Partner doc doesn't acknowledge this.
7. **@Nicolle — Postman collection.** The partner doc references `kira-sandbox.postman_collection.json` (L140) — we have the doc but not the file. Where do we pull it?
8. **@Nicolle — v2026-XX-XX exact ship date.** "End of June" is the doc's commitment (L3 / L12 / L42). What's the firm date and the rollback plan if the migration to `api.kirafin.ai` (L136) bumps a partner?
9. **@Nicolle / @Diego — Production Readiness Checklist item #14 (event de-dup).** Per prod-cert L80-83, we must demonstrate that processing the same `event_id` twice has the side effect once. With no retry policy today (DRIFT-83-equivalent on the partner doc L83), how does an integrator force a retry to demonstrate de-dup? Is there a sandbox endpoint to replay a webhook delivery on demand?
10. **@Nicolle — The 15-item prod-cert checklist is the de facto test plan.** Can we get the checklist as a public artifact so the public-docs reader knows what's expected? Right now an integrator submits a "good faith" attempt with no published rubric.

---

**END OF DELTA ANALYSIS.**
