# Docs Coverage Matrix — Kira Guides Sidebar vs flow-design.md

> **Purpose:** Section-by-section coverage assessment of the 13 Guides sidebar pages at https://kira-financial-ai.readme.io/v2026-04-14/docs/ against `evidence/analysis/08-flow-design.md`. For PARTIAL / MISSING sections, the docs were fetched fresh; for COVERED sections, this matrix summarizes from flow-design.md without re-fetching.
> **Methodology:** Each section is classified (COVERED | PARTIAL | MISSING), anchored to flow-design.md, and then mined for net-new probes/tests/findings per agent. Empty agent rows are intentionally skipped — the value of this matrix is what we MISSED, not what we already caught.
> **Sweep date:** 2026-05-27.
> **Sweep author:** docs-coverage coordinator agent (channels 8 evaluator personas).

---

## Section 1 — Kira API Overview (`kira-api-overview`)
**Coverage status:** COVERED
**Anchored in flow-design.md:** §1 Overview, §1.1 Base URLs, §1.3 What Kira is *not*, Appendix A (`docs/kira-api-overview.md` crawled)
**Source URL:** https://kira-financial-ai.readme.io/docs/kira-api-overview

**Section summary (from flow-design §1):** Introduces Kira ("Balam" hostname) as a unified fintech infra API spanning five product lines (users/verification, virtual USD accounts, on-ramps via PayIns, off-ramps via Payouts, liquidation addresses). Establishes sandbox vs production base URL (URL prefix only, no `X-Environment` header), the `v2026-04-14` version-in-docs-URL convention, and the architectural truth that Kira does no fiat-to-fiat (USD→MXN routes through stablecoins).

### New tests / probes / findings to add — per agent

**`product-manager`**
- Probe whether the marketing claim "FDIC-insured via 4 US partner banks" is auditable in the API response: does `GET /v1/virtual-accounts/{id}` expose which partner bank holds the funds (Portage / Austin Capital Trust / Slovak Savings Bank) and whether it's FDIC-insured? Three partner banks are named, but the marketing claims four. Finding-candidate: bank inventory discrepancy.
- Probe whether the "stablecoin under the hood" architectural truth (§1.3) is exposed anywhere in the API response — `kira_rate` may quietly drop the stablecoin leg from `/v1/quotations`. Integrator MUST know the route for reconciliation/audit.

**`devil-advocate`**
- Flag that the overview's "5 product lines" headline collides with `use-case-product-comparison`'s 5 different product names (Wallets, Payment Link, Virtual Account, cashPay, Payout API) — these are not the same five. Cross-page taxonomy drift on the home page itself. Sniff-test severity.

---

## Section 2 — Use Case Product Comparison (`use-case-product-comparison`)
**Coverage status:** PARTIAL
**Anchored in flow-design.md:** Appendix A lists `docs/use-case-product-comparison.md` as crawled, but §3 Resource Catalog organizes by *endpoint family*, not by *product line*. The product-comparison taxonomy was not extracted.
**Source URL:** https://kira-financial-ai.readme.io/docs/use-case-product-comparison

**Section summary:** Compares 5 products: **Wallets**, **Payment Link**, **Virtual Account**, **cashPay**, **Payout API**. Dimensions: Goal, Operation type, Payment methods supported, Countries, Who can use it (individual vs business), Personas, Integration effort (low/medium), UI customization (limited/customizable), Embeddable (Y/N), KYC/B required, Evidence-of-transaction required, Common applications. **No explicit latency/SLA/cost tables. No cross-links to other docs pages.**

### New tests / probes / findings to add — per agent

**`product-manager`**
- **NEW FINDING-CANDIDATE: "Wallets" product is on the comparison table but absent from flow-design's §3 Resource Catalog.** No `/v1/wallets` family is mapped — the only mention is `POST /v1/users/{userId}/wallets` (an idempotency-required endpoint cited in §2.4 without a reference page). If Wallets is a marketed product, the integrator can't find its endpoints. Open question for @Nicolle/@Diego: what is the Wallets product surface?
- **NEW FINDING-CANDIDATE: "cashPay" treated as a separate product from Payment Link in this comparison, but flow-design §3.9 treats cashPay as a delivery channel inside Payment Link (`barcode_generated` event).** Taxonomic drift between product-marketing and API surface.
- Cross-check the "Embeddable in website (Y/N)" column against the Full-stack agent's iframe probe results — if the docs say "Embeddable: Yes" but CSP headers refuse iframe embedding, that's a documented-vs-runtime drift finding.
- Probe whether "KYC/B required" claims line up with what the API actually enforces (GAP-24 — verification requirement for PayIn users undocumented).

**`data-architect`**
- The product-comparison page identifies **5 distinct integration personas** with different effort levels — flow-design.md does not yet have an integration-effort axis in `test-topology.md`. Add a column to test-topology: product-line × test-category × effort-tier.
- "Global" coverage for Wallets vs "United States" for Virtual Account vs "13 LATAM nations" for Payouts is a coverage-matrix that's missing from flow-design §3. Add §3.x: per-product geographic-eligibility matrix anchored to `GET /v1/countries`.

**`fullstack-integrations-specialist`**
- "Embeddable in website" column claims a Yes/No per product — probe each one: iframe-embed Payment Link, Virtual Account onboarding, cashPay barcode page on three origins (localhost, *.vercel.app, prod TLD) and capture `X-Frame-Options` / `Content-Security-Policy: frame-ancestors` per page.
- "UI customization: limited vs fully customizable" — for Payment Link probe the actual customization knobs (logo, brand colors, locale, return-URL, copy strings) via `POST /v1/payment-link` body fields not yet enumerated in §3.9. Document the actual customization surface area.

**`qa-engineer`**
- Build a Schemathesis-style consistency test: every product the comparison table claims has KYC/B = required should fail with a documented error code if called pre-verification. Today only Payouts is verified to enforce this (Recipe B step 1 dependency note).

---

## Section 3 — Getting Started with Kira API (`getting-started`)
**Coverage status:** PARTIAL
**Anchored in flow-design.md:** Appendix A lists `docs/getting-started.md` and `docs/authentication.md` as crawled. §1.1 / §2.1 cover base URLs and auth body. **But:** the subsection map (Authentication / Manage Users / Create Virtual Accounts / Set up Webhooks) and the quickstart curl sample are not extracted.
**Source URL:** https://kira-financial-ai.readme.io/docs/getting-started

**Section summary:** Three-step authentication setup (obtain credentials → POST /auth → use Bearer). Environment URLs reaffirmed. Required headers listed. Curl quickstart for `/auth` provided. **Subsection links:** `./authentication`, `./users-and-verification`, `./virtual-accounts`, `./webhooks` — confirmed as the canonical "Day 1 happy path." Subsection `authentication` carries the **expired-token body** `{"message": "The incoming token has expired"}` — note: **no `code` field, no nested `error` wrapper** → this is a **fourth error envelope shape** not catalogued in flow-design §2.3.

### New tests / probes / findings to add — per agent

**`product-manager`**
- **NEW FINDING-CANDIDATE — fourth error envelope shape.** flow-design §2.3 catalogues 3 error shapes (flat, nested, Pydantic). The auth guide documents a 401 expired-token body that has **only `message`, no `code`** — neither Shape A nor B. This breaks the assumption that "code is always present in business-logic errors." Update §2.3 → Shape D ("bare message"). Severity: MEDIUM (generic error handler returns null on `.code` lookup).
- Time-to-first-call probe: the Getting Started quickstart has only the `/auth` curl. There is no copy-paste end-to-end sample (auth → create user → create VA). Compare with Stripe / Plaid quickstarts — this is a measurable docs-quality gap for Pillar 2 (Ease of Connection).

**`data-architect`**
- The Getting Started subsection map promises 4 sub-pages (`authentication`, `users-and-verification`, `virtual-accounts`, `webhooks`). All 4 exist in Appendix A. But there is **no quickstart subsection on "Idempotency setup", "Error handling", or "Webhooks signature verification"** — the sidebar-level Guides for those exist, but the Getting Started funnel does not lead to them. Pillar 1 findability gap.
- The Authentication sub-page says **"Change password regularly" and "Request new API keys periodically"** — implies manual key rotation only, no API endpoint. Add to GAP-21 family: no `POST /api-keys/rotate` documented. Open question for @Diego.

**`data-engineer`**
- Probe: send a request with an *expired* JWT (manipulate `exp` claim or wait 1 hour) and capture the exact 401 body — confirm `{"message": "The incoming token has expired"}` and **assert that `body.code` is `undefined`**, not just empty. This is the shape-D probe.
- Probe: send a request with a *malformed* JWT (random string), an *unsigned* JWT (`alg=none`), and a *valid-but-wrong-tenant* JWT. Capture the body of each — does Kira return distinct error codes / messages? If all three return the same bare `{"message": ...}`, integrators cannot triage auth failures programmatically.
- The Getting Started curl uses production base URL (`https://api.balampay.com/auth`), not sandbox. Probe whether the sandbox base URL works with the same credentials and whether the docs sample is silently routable to production by a copy-paste integrator. Pillar 3 sandbox-prod drift candidate.

**`api-security-auditor`**
- **API2:2023 — Broken Authentication probe family seeded by the auth guide:** no MFA documented, no IP allowlisting documented, no key rotation API, "change password regularly" written as a habit not enforced — credential-stuffing risk. Probe `POST /auth` for rate-limit (the auth guide is silent on whether `/auth` is rate-limited; the global 10rps cap may or may not apply).
- Probe whether the `/auth` response sets `Cache-Control: no-store` — JWT in a cached intermediary is a CWE-525 finding.
- The auth guide says "include **both** the token and API key in all subsequent API requests" while OpenAPI for GET endpoints declares `oneOf(BearerAuth, ApiKeyAuth)`. Probe each GET endpoint with: Bearer-only, API-key-only, both, neither — capture the 4-way table. This sharpens GAP-04.

**`qa-engineer`**
- Author `.feature` file `auth-error-envelope-shape-d.feature`: send expired JWT, assert response body has key `message` but NOT key `code`, NOT key `error`. Tag `@error-envelope` + `@auth`.
- Author `.feature` file `getting-started-quickstart-runnable.feature`: copy-paste each curl from the Getting Started page, execute against sandbox, assert documented HTTP status returned. (Pillar 1 docs-quality property test.)

---

## Section 4 — Users and verification (`users`)
**Coverage status:** COVERED
**Anchored in flow-design.md:** §3.2 (Users endpoints), §3.3 (Verification state machine), §3.2.1 (user body minimal payloads), §3.2.2 (two VA-products onboarding shapes), §5.2 (verification state diagram), GAP-14 (dual enum)
**Source URL:** https://kira-financial-ai.readme.io/docs/users-and-verification

**Section summary (from flow-design):** Users are the verified counterparties every other resource attaches to. `type: individual | business` selects the schema. KYC/KYB auto-triggers when all required fields are supplied. Two parallel status enums (modern UPPERCASE, legacy lowercase). Two VA-products with different required-field tables (Portage vs ACT). Hosted-link KYC mode via `verification_mode: verification_link`. `verification_url` returned for legacy `POST /v1/users/{id}/verifications`.

### New tests / probes / findings to add — per agent

**`fullstack-integrations-specialist`**
- Iframe-embed the returned `verification_url` (or `verification_link` from verification-link mode) on a third-party origin; capture `X-Frame-Options` / `Content-Security-Policy: frame-ancestors`. Today flow-design §3.2 captures the URL field but no iframe-fit probe is on the test plan.
- Probe the `redirect_uri` contract: send `redirect_uri` values with `http://` (non-TLS), with query params, with URL fragments (`#`), with localhost, with non-ASCII path segments. Capture which values are accepted, which return validation errors, and what params come back appended to the redirect.
- Probe mobile WebView behavior: complete a verification on iOS Safari, Android Chrome, Slack in-app browser, X/Twitter in-app browser. Document which fail.

**`api-functional-tester`**
- **Mass assignment probe on `POST /v1/users`:** include `status: "VERIFIED"`, `verification_status: "verified"`, `eligible_products: ["usa-virtual-accounts"]`, `client_id: <other tenant uuid>`, `created_at: "1970-01-01"` in the body and observe if any are honored. flow-design §3.2 hints at the response *exposing* `missing_fields` but doesn't probe whether the request can *set* status fields directly.
- **State-machine bypass:** call `PUT /v1/users/{id}` on a `VERIFIED` user with no sensitive fields and observe whether `requires_reverification` flips back to `false`. Then with a sensitive field — verify the transition `VERIFIED → VERIFYING` actually happens vs the docs claim.
- **Dual-enum exploit:** if the legacy `verification_status` enum still drives any downstream check (payout eligibility, VA creation), can a user be modern-`VERIFIED` but legacy-`unverified` and trigger contradictory behavior? Probe with sequential PUTs to find the seam.

**`qa-engineer`**
- Author `.feature` file `user-dual-enum-mapping.feature` (GAP-14): create a user, observe both `status` and `verification_status` in `GET /v1/users/{id}`, assert the mapping table. Today flow-design says the mapping is undocumented — this `.feature` makes it observable.

**`api-security-auditor`**
- **API3:2023 — Broken Object Property Level Authorization:** `GET /v1/users/{id}` returns `eligible_products[]` and `missing_fields{}` — does it also return internal audit fields (OFAC score, sanctions flag, internal notes, vendor IDs)? Probe the full response and look for fields not in the docs schema.
- **API1:2023 — BOLA setup on `GET /v1/users/{id}`:** create a user in tenant A, attempt to fetch by ID from tenant B's credentials. flow-design §3.2 doesn't yet have a cross-tenant assertion.

---

## Section 5 — Recipients (`recipients`)
**Coverage status:** PARTIAL
**Anchored in flow-design.md:** §3.5 (recipients catalog with 22+ account types), GAP-15 (no pagination), GAP-16 (`bank_address` type drift), GAP-17 (Spanish enums). Appendix A lists `recipient-management-1.md` and `account-types-reference.md` but **NOT** the parent `recipients` slug, which today is a stub/landing-page only.
**Source URL:** https://kira-financial-ai.readme.io/docs/recipients

**Section summary:** Parent page is a stub/landing page that points to subsections (`account-types-reference`, `recipient-management-1`). No standalone content beyond navigation. The actual contract lives in the subsections (already in flow-design §3.5).

### New tests / probes / findings to add — per agent

**`product-manager`**
- **NEW FINDING-CANDIDATE — sidebar parent page is a stub.** The `recipients` slug exists on the sidebar but has no own content; an integrator clicks "Recipients" and finds only a Jump-to-Content link. This is a Pillar 1 (Findability) finding: a top-level sidebar entry must lead somewhere. Severity: LOW–MEDIUM.

**`data-engineer`**
- Probe the parent page in browser vs `.md` flavor — confirm both return empty/stub. If the `.md` returns the full subsection content but the HTML page doesn't, that's a docs-rendering bug worth flagging.

**`devil-advocate`**
- Push back on whether "sidebar stub" deserves a finding slot vs being filed as "noise." Sniff-test: would Banco Industrial care? Probably no. But it's a Pillar 1 indicator if there's also a stub parent for `virtual-accounts`, `webhooks`, etc. — bundle into one finding if pattern repeats.

---

## Section 6 — Virtual Accounts (`virtual-accounts`)
**Coverage status:** COVERED
**Anchored in flow-design.md:** §3.4 (VA endpoints + worked example), §3.2.2 (two VA-products onboarding shapes), §5.3 (state machine), Recipe A in §4.1, GAP-22 (sandbox deposit simulation), GAP-27 (no close-VA endpoint)
**Source URL:** https://kira-financial-ai.readme.io/docs/virtual-accounts

**Section summary (from flow-design):** Virtual Accounts are USD bank accounts at partner banks (Portage / Austin Capital Trust / Slovak Savings Bank). Fiat mode (USD balance) or crypto mode (auto-convert + send to wallet) selected by `destination` field; mode is immutable. `source_deposit_instructions` is null until the `virtual_account.activated` webhook fires.

### New tests / probes / findings to add — per agent

**`data-engineer`**
- Probe how long `pending → active` takes in sandbox (the "activating" webhook latency). Today no SLA captured. Run 10 VA creates, measure time-to-activation, capture p50/p95/p99 to `evidence/work/latency/va-activation.json`.
- Probe what happens if the integrator polls `GET /v1/virtual-accounts/{id}` before the webhook arrives: does `source_deposit_instructions` flip from `null` to populated atomically, or could a partial state leak (some fields populated, others null)?
- Probe `markup{fx_bps, fee_bps}` boundary values: 0, negative, > 10000 (>100%), missing. Today flow-design §3.4 catalogs these fields but doesn't probe bounds.

**`api-functional-tester`**
- **Mode-immutability bypass:** create a fiat-mode VA, then PUT/PATCH with `destination` set. Is the immutability enforced? If yes, what status code? If no, that's a state-machine corruption finding.
- **Crypto-mode VA without verified destination:** create a crypto-mode VA pointing to an attacker-controlled wallet, then have someone deposit to its US bank routing details. Funds auto-sweep to the attacker wallet — is there a verification step on the destination address? If not, that's a HIGH-severity abuse vector.

**`api-security-auditor`**
- **API1:2023 — BOLA on `GET /v1/virtual-accounts/{id}`:** create VA in tenant A, fetch by ID from tenant B. Especially probe `source_deposit_instructions` — leaking US bank routing + account number cross-tenant is a CRITICAL finding.
- **API1:2023 — BOLA on `/v1/virtual-accounts/{id}/balance`:** balance disclosure cross-tenant.
- **API3:2023 — Excessive data exposure on `GET /v1/virtual-accounts/{id}`:** does the response leak internal bank-vendor IDs, FDIC certificate numbers, account type internal flags?

**`devil-advocate`**
- Cross-check: flow-design §1 names 3 partner banks (Portage / ACT / Slovak Savings) but the marketing claims 4 FDIC-insured banks. Where's bank #4? Possibly Diameter? Probe `provider` enum exhaustively on `POST /v1/virtual-accounts`.

---

## Section 7 — Payment Link (`payment-link`)
**Coverage status:** COVERED
**Anchored in flow-design.md:** §3.9 (Payment Links endpoint + redirect contract), webhook events `card_payment` / `barcode_generated` in §2.7, GAP-12 (legacy events)
**Source URL:** https://kira-financial-ai.readme.io/docs/payment-link

**Section summary (from flow-design):** `POST /v1/payment-link` creates a hosted payment link. Senders pay via debit card or cash (cashPay at 50–90k retail locations, excluded NY/AK for card, NY/LA for cash). Link URL `https://your-domain.kirafin.ai/v3/{txn_uuid}` accepts `redirect_url` query string; success appends `?status=success`, cancel appends `?status=cancelled`. Two webhook events emitted.

### New tests / probes / findings to add — per agent

**`fullstack-integrations-specialist`**
- **Redirect-contract probe:** create a payment link with `redirect_url` set to: `http://localhost:3000`, `https://attacker.com/steal`, a URL with `#fragment`, a URL with existing `?status=success` (collision), an `intent://` Android deep link, and an `app://` custom-scheme URL. Capture which are accepted, which are sanitized, which validate against an allowlist.
- **Open-redirect probe (security adjacent):** if `redirect_url` is not validated against a tenant allowlist, the payment link becomes an open redirector with Kira's domain in the path. Phishing surface.
- **iframe-embed probe:** does the payment link page (`/v3/{txn_uuid}`) allow iframe embedding? CSP `frame-ancestors`? If "Embeddable" claim from §2 holds, this must pass.
- **Link expiry probe:** flow-design §3.9 doesn't specify link TTL. Create a link, wait 1/24/72 hours, attempt to load. Document expiry behavior.
- **Mobile browser matrix:** open the link in iOS Safari, Android Chrome, Slack mobile, Instagram in-app, Telegram in-app. Document which fail to redirect after payment.

**`api-functional-tester`**
- **`barcode_generated` without payment:** generate a cashPay barcode, never pay it. Does the link expire? Is the barcode reusable? Can the same `txn_uuid` be requoted at a different amount?
- **`link_type: "top-up"` vs default remittance:** probe whether top-up flow has different KYC/refund/limit semantics. Today §3.9 only mentions the field, not the contract divergence.
- **`acct_info` per-country variance:** the body field "varies by country" — enumerate all valid `acct_info` shapes by probing each country. Currently undocumented per-country.

**`api-security-auditor`**
- The `redirect_url` appends `?status=success|cancelled` — if the URL parser is naive, attacker can supply `?status=cancelled&status=success` and use status-overriding to mislead the integrator's success-handler. Probe parser behavior.
- **CSP on the hosted page:** capture `Content-Security-Policy`, `X-Content-Type-Options`, `Referrer-Policy`, `Strict-Transport-Security` headers on `/v3/{txn_uuid}`. JSON-API CSP rules don't apply but a hosted payment page needs strict CSP.

**`qa-engineer`**
- Author `.feature` file `payment-link-redirect-contract.feature` listing each redirect param value and the expected outcome. Tag `@redirect` + `@security`.

---

## Section 8 — Webhooks (`webhooks`)
**Coverage status:** COVERED
**Anchored in flow-design.md:** §2.7 (extensive — registration, signing, events, gaps), §4.6 (Recipe F: subscribe-verify-recover), GAP-11 (delivery semantics absent), GAP-12 (legacy events), GAP-21 (no update/delete), GAP-04 (`x-api-key` only auth)
**Source URL:** https://kira-financial-ai.readme.io/docs/webhooks-guide

**Section summary (from flow-design):** `POST /webhooks/register` with `webhook_url`, `secret`, `client_uuid`. Only `x-api-key`; no Bearer. Signing via `x-signature-sha256` HMAC-SHA256 of raw body. Push-only, fire-and-forget. No retry/DLQ/replay-window/timestamp/signature-encoding spec. 23+ event types catalogued including legacy ones.

### New tests / probes / findings to add — per agent

**`fullstack-integrations-specialist`**
- **Webhook receiver on Vercel serverless probe:** deploy a Vercel function as the webhook receiver, force 100 deliveries, capture cold-start vs warm latency. Vercel cold-starts can blow Kira's "acknowledge immediately" expectation if Kira's timeout is short (undocumented per GAP-11).
- **Cloudflare Workers body-size probe:** CF Workers cap request body at 100MB but free tier at 1MB. Probe whether any Kira webhook body exceeds 1MB (large user verifications with embedded base64 docs).

**`api-functional-tester`**
- **Out-of-order delivery probe:** wedge the receiver to simulate slow processing, then send the same event_id at different states (`PROCESSING` then `PENDING`). Does the integrator's idempotent handler handle non-monotonic state? Doc requires it but Kira's spec doesn't help — GAP-11 amplified.
- **Replay-attack window probe:** capture a real `x-signature-sha256` from a legit delivery; replay it to a different webhook URL registered under the same client. Does Kira accept the replay? Is there a timestamp header at all? Probe for `x-timestamp`, `x-delivery-id`, `x-event-id` in response headers.

**`api-security-auditor`**
- **SSRF on `POST /webhooks/register`:** register `http://169.254.169.254/latest/meta-data/` (AWS IMDS), `http://localhost:6379/` (Redis), `http://internal.kira.local/`, `file:///etc/passwd`. Document which are accepted at registration time. If accepted, force a delivery and observe what Kira's outbound fetcher does.
- **DNS rebinding probe:** register `attacker.com` (resolves to attacker IP at registration, rebinds to internal IP at delivery time).
- **Webhook signature secret leak:** does any response (GET-after-register, or list-webhooks if it exists) return the registered `secret` in cleartext? `secret` was sent on registration but should never echo.
- **Signature forgery probe:** if the signature is HMAC-SHA256(secret, raw_body), confirm constant-time comparison server-side by timing attacks on the registration probe. Practically impossible to probe client-side, but document the question.
- **Webhook auth gap (GAP-04 expansion):** with only `x-api-key` required, a leaked API key registers a webhook to attacker's URL — and now every event for that tenant flows there. Probe whether there's any out-of-band confirmation (email, click-to-confirm) before activation.

**`qa-engineer`**
- Author `.feature` file `webhook-signature-encoding.feature`: capture 5 deliveries, decode `x-signature-sha256` as hex AND base64, assert which one verifies. Today GAP-11 leaves encoding unspecified.
- Author `.feature` file `webhook-retry-curve.feature`: stand up a receiver that returns 5xx on first 3 attempts, then 200. Capture inter-attempt delays. Assert backoff curve. Compares with industry norms (Stripe: 1min/1hr/3hr/etc, Plaid: 5sec/30sec/2min/...).

**`product-manager`**
- The webhook guide says "Acknowledge receipt immediately, process asynchronously" but **does not specify Kira's acknowledgment-timeout SLO**. Open question for @Diego: is the timeout 5s, 30s, 60s? Vercel/Lambda cold starts can exceed 5s. This is an integrator-pain finding even without any vulnerability.

---

## Section 9 — Error Handling (`error-handling`)
**Coverage status:** PARTIAL
**Anchored in flow-design.md:** §2.3 (three coexisting error envelopes), GAP-05 (envelope inconsistency), GAP-06 (no request-id). Appendix A lists `docs/error-handling.md` as crawled but specific page sections (Common Errors, Best Practices, Debugging Tips, Getting Help) weren't extracted.
**Source URL:** https://kira-financial-ai.readme.io/docs/error-handling

**Section summary:** Page sections: Overview / HTTP Status Codes / Error Response Format / Common Errors / Error Handling Best Practices / Error Response Reference / Debugging Tips / Getting Help. Catalogues 200/201/400/401/404/409/500 status codes. Lists error codes `validation_error`, `unauthorized`, `not_found`, `idempotency_key_reused`, `internal_error`, `invalid_type`. Two error-response-format shapes documented (Business Logic flat, Schema Validation nested with `details[].path`). Retry guidance: exponential backoff for 500, re-auth for 401, idempotent retry on same-key-same-data. Support email: `support@kira.com`. **Notable absences: no request_id documentation, no rate-limit error documented, no network-error retry guidance, no idempotent-vs-non-idempotent distinction, no FAQ.**

### New tests / probes / findings to add — per agent

**`product-manager`**
- **NEW FINDING-CANDIDATE — error-handling page is incomplete relative to actual error inventory.** Page lists 7 status codes; flow-design §2.3 catalogues 12+ error codes including `forbidden`, `resource_conflict`, `rate_limit_exceeded`, `invalid_operation`, `invalid_user_id`, `idempotency_conflict`, plus the entire Shape-B family (`USER_NOT_FOUND`, `PAYOUT_ACCESS_DENIED`, `INVALID_BANK_CODE`, `FEES_EXCEED_AMOUNT`, `QUOTE_INVALID_STATE`, `CURRENCY_PAIR_NOT_ENABLED`, `IDEMPOTENCY_CONFLICT`, etc.) plus the new Shape-D bare `{message}` from the auth guide. The dedicated guide misses ~80% of the inventory. Severity: HIGH for Pillar 1 (Completeness).
- **Inconsistency between page sections:** Common Errors mentions `idempotency_key_reused` returning **409 for user creation but 400 for virtual accounts**. That contradiction is documented on the page itself, and `flow-design §2.4` flags it as "behavior worth re-verifying" without yet probing. This is a specific runtime probe to schedule.
- **NEW FINDING-CANDIDATE — request_id is referenced in the support contact ("Request ID (if available)") but is nowhere documented to be returned by the API.** GAP-06 amplified: integrators are told to attach a request_id they have no way to obtain.
- **NEW FINDING-CANDIDATE — no 422 documented** despite `/auth` returning 422 with Pydantic validation list (flow-design §2.1). Status-code inventory drift.
- **NEW FINDING-CANDIDATE — no 429 documented in error-handling**, despite §2.6 documenting rate-limit headers + 429 with `Retry-After`. Rate-limit error UX is absent from the dedicated error guide.

**`data-engineer`**
- Probe each error envelope shape A/B/C/D systematically: trigger 401 (expired token → D?), 400 validation_error on `POST /v1/users` (A), 422 on `/auth` malformed UUID (C), 409 on `POST /v1/recipients` IDEMPOTENCY_CONFLICT (B), 404 on `GET /v1/users/<random-uuid>` (A?), 403 on `PUT /v1/users` after verification (A?), 429 (if reachable). Build the empirical matrix `evidence/work/error-envelopes/matrix.md`. This makes GAP-05 concrete and rankable.
- Probe whether responses carry **any** correlation header: `x-request-id`, `x-correlation-id`, `cf-ray`, `x-amzn-requestid`, `x-amz-cf-id`, `request-id`. flow-design §2.3 says "never in any error body or success header sample" but that needs empirical confirmation against headers.

**`qa-engineer`**
- Author `.feature` file `error-handling-page-completeness.feature`: assert that every error code observed in runtime probes appears in the docs Error Response Reference. Likely fails for 80% of codes — that's the finding.
- Author `.feature` file `idempotency-conflict-status-divergence.feature`: trigger idempotency conflict on `POST /v1/users` (expect 409) and on `POST /v1/virtual-accounts` (page says 400, changelog says 409). Assert observed status. This makes the cross-page contradiction concrete.

**`api-security-auditor`**
- **API8:2023 — Information disclosure on 500 errors:** the page says 500 returns `internal_error` — probe whether the actual sandbox 500 leaks stack traces, framework name (FastAPI? AWS Lambda?), file paths, or vendor names. flow-design §2.1 already shows `/auth` 500 returns `"Service unavailable"` semantically (should be 503) — extend to all 500-emitting endpoints.

**`devil-advocate`**
- Push back on whether "error-handling page is 80% incomplete" deserves CRITICAL/HIGH or is just MEDIUM. Calibration: Stripe's `/docs/error-codes` lists hundreds; Plaid's is even longer. A page that lists ~6 codes for a payments API with ~50 documented codes is *materially* misleading. Vote HIGH.

---

## Section 10 — Idempotency (`idempotency`)
**Coverage status:** COVERED
**Anchored in flow-design.md:** §2.4 (full coverage — header name, format, TTL, 7-endpoint guide list vs 9-endpoint reality), GAP-07 (POST /v1/payouts in guide but not in reference), GAP-08 (endpoint list inconsistent)
**Source URL:** https://kira-financial-ai.readme.io/docs/idempotency

**Section summary (from flow-design):** Header `idempotency-key` (lowercase). UUID v4 recommended. 24h TTL. Required on 7 endpoints per the dedicated guide, but the true count is 9 after the April-14 changelog (PayIn + Liquidation added). Reuse semantics: same key+same body → cached replay; same key+different body → 409. Sandbox behavior around docs drift worth re-verifying.

### New tests / probes / findings to add — per agent

**`data-engineer`**
- **Idempotency-key TTL probe:** generate a key, use it on `POST /v1/users`, wait 24h+1min, reuse same key with different body. Does the new request succeed (TTL expired, new operation allowed) or 409 (TTL not yet expired)? Confirm exact TTL boundary.
- **Header casing probe:** flow-design §2.4 notes the header is `idempotency-key` (lowercase) in all examples — but HTTP headers are case-insensitive. Probe whether `Idempotency-Key` (Title-Case, the industry-standard Stripe convention) is also accepted, or rejected as missing. If rejected, that's a Pillar 1 finding (industry-standard header name not accepted).
- **Concurrent same-key probe:** fire 10 parallel `POST /v1/users` with identical key+body. Assert: 1 returns 201, 9 return cached 201; OR all 10 return identical bodies; OR (worst) two 201s with two distinct user_ids = duplicate-create race.
- **`POST /v1/payouts` route probe (GAP-07):** send a POST to `/v1/payouts` (the path the guide names) — does the server route it (perhaps to `/v1/virtual-accounts/{id}/payout`)? Or does it 404? Or 405? Empirical answer required.

**`api-functional-tester`**
- **Idempotency conflict semantics probe:** send same key + slightly different body (e.g., changed `email` by case). Does the server fuzzy-match the body (hashing the canonical form) or strict-match? If strict, integrators can bypass conflict checks by reordering JSON keys.

**`qa-engineer`**
- Author `.feature` file `idempotency-required-endpoints.feature` enumerating all 9 endpoints from the changelog reality, asserting each rejects requests without the key. This empirically verifies the 9-not-7 finding (GAP-08).

---

## Section 11 — Metadata (`metadata`)
**Coverage status:** MISSING
**Anchored in flow-design.md:** **Not addressed anywhere.** Not in Appendix A. No GAP cites it. No endpoint in §3 references a metadata field.
**Source URL:** https://kira-financial-ai.readme.io/docs/metadata → **404 Not Found** (both `.md` and non-`.md`)

**Section summary:** Page does not exist. Sidebar entry leads to 404. **This is a smoking-gun docs gap — the sidebar promises a metadata guide that has never been published.**

### New tests / probes / findings to add — per agent

**`product-manager`**
- **NEW CRITICAL FINDING-CANDIDATE — sidebar entry "Metadata" 404s.** This is the same shape as GAP-01 (Versioning 404) but for a different topic. Two sidebar entries that 404 = pattern, not a one-off. Severity: HIGH (Pillar 1 Completeness + Findability), possibly CRITICAL if pattern persists across more entries.
- Probe whether ANY Kira endpoint accepts a `metadata` body field today. If yes, the contract for that field is undocumented (max size, key/value types, PII restrictions, webhook return, query/filter behavior — all unknowable). If no, the sidebar entry is aspirational.
- **Open question for @Nicolle/@Diego:** is `metadata` a planned-but-unbuilt feature, a built-but-undocumented feature, or stale sidebar leakage? Each scenario has different integrator implications.

**`data-engineer`**
- Probe every POST endpoint with a body containing `metadata: {"test_key": "test_value", "trace_id": "abc-123"}`. Capture: (a) is it accepted (201 vs 400)? (b) is it echoed in the GET response? (c) is it queryable via list-endpoint filter `?metadata.test_key=...`? (d) does it appear in webhooks?
- Probe `metadata` size boundaries: 1 key, 50 keys, 500 keys; values of 100 chars, 10KB, 1MB. Find the limit. Find whether long values are silently truncated.
- Probe metadata with PII (emails, SSNs, credit-card-shaped strings): is the field rejected, masked, or stored raw? Compliance-sensitive.

**`api-security-auditor`**
- **API3:2023 — Mass assignment via metadata:** if metadata is silently accepted on any endpoint, can an attacker store payload-shaped values that other endpoints then trust (e.g., `metadata.admin_override: true`)? Probe whether the value is round-tripped to any downstream check.
- **API8:2023 — Information leakage via metadata in webhooks:** if metadata is echoed in webhook payloads but the webhook receiver is the wrong tenant (BOLA cross-talk), PII leaks.

**`devil-advocate`**
- Sniff-test: does an integrator actually need metadata on Day 1? Stripe, Plaid, every modern payments API has `metadata` for reconciliation. Absence is HIGH-severity for any platform claiming enterprise-readiness. Vote HIGH at least.

---

## Section 12 — Versioning (`versioning`)
**Coverage status:** MISSING (confirmed 404 — already captured as GAP-01)
**Anchored in flow-design.md:** §1.2 (versioning model + the smoking gun), GAP-01, Appendix A "Pages that 404'd"
**Source URL:** https://kira-financial-ai.readme.io/docs/versioning → **404 Not Found** (re-verified 2026-05-27); also `/docs/api-versioning.md` → **404**

**Section summary:** Page does not exist. Per the April-14 changelog, a Versioning guide *was promised* and an `X-Api-Version` header was announced with two values (`2025-01-01` default, `2026-04-14` latest). Neither the guide page nor any example request setting the header exists. Already GAP-01.

### New tests / probes / findings to add — per agent

**`data-engineer`**
- Probe **omitted header** vs **header set to `2025-01-01`** vs **header set to `2026-04-14`** vs **header set to garbage**: capture response bodies on `POST /v1/users` and `GET /v1/recipients` (an endpoint that arguably changed in the April-14 sweep). Diff the schemas. This is the GAP-01 probe-of-truth — its absence today means the team has been writing about GAP-01 without empirically pinning it.
- Probe **case sensitivity** of the version header: `X-Api-Version` vs `x-api-version` vs `X-API-VERSION`. HTTP headers are case-insensitive but middlewares often disagree.
- Probe whether the **URL path version** `/v1/...` vs hypothetical `/v2/...` exists at all (is `v1` the only path-version, with header being the semantic-version selector?). Send `GET /v2/users` and observe.

**`api-security-auditor`**
- **API9:2023 — Improper Inventory Management:** with `X-Api-Version` announced but undefined, are old versions still reachable? Specifically: if header `2025-01-01` returns the old schema, does it also bypass any *new* validation rules (e.g., the April-14 changelog tightened SWIFT recipient fields). Probe whether old-version requests can submit fields that new-version rejects → security-relevant inventory finding.

**`product-manager`**
- Already GAP-01 / Top-5 seed. **No new probe — but flag that until §1.2's empirical-omission probe runs, GAP-01 is theoretical.** Without the data-engineer's diff, the team is repeating the docs back to itself.

---

## Section 13 — API upgrades (`api-upgrades`)
**Coverage status:** MISSING (confirmed 404)
**Anchored in flow-design.md:** **Not addressed.** Not in Appendix A. No GAP cites it.
**Source URL:** https://kira-financial-ai.readme.io/docs/api-upgrades → **404 Not Found** (both `.md` and non-`.md`)

**Section summary:** Page does not exist. Third sidebar entry that 404s after `versioning` and `metadata`. This is the upgrade-path companion to the versioning page; without it, there is **no documented migration / deprecation / EOL policy**.

### New tests / probes / findings to add — per agent

**`product-manager`**
- **NEW CRITICAL FINDING-CANDIDATE — "API upgrades" sidebar entry 404s.** Combined with versioning (404) and metadata (404), this is **3 of 13 sidebar entries returning 404 = 23%**. That's not a typo, that's a pattern. Severity for the *pattern*: CRITICAL (Pillar 1 Findability + Completeness). Even if each individual page is MEDIUM, the *concentration* of dead links elevates this.
- **Open question for @Nicolle/@Diego:** is there a documented breaking-change policy (semver-like) and a deprecation timeline? Real clients (Banco Industrial, N1co) cannot sign multi-year contracts against an API that has no published upgrade contract. This is a sales-blocker, not a docs nit.

**`data-architect`**
- Add a new GAP entry to flow-design §6: **GAP-35 — No API upgrade / deprecation policy documented.** Companion to GAP-01.
- Architectural question: does Kira commit to N-1 version support? N-2? Forever? Without an upgrades page, the contract is "we can break you next Tuesday."

**`api-security-auditor`**
- **API9:2023 — Improper Inventory Management** amplified: without a published deprecation schedule, old version endpoints stay reachable indefinitely. Probe whether `2025-01-01` (per GAP-01 default) is *still* the default for clients onboarded today — if yes, every new integrator is silently on an old version with an unknown EOL.

**`devil-advocate`**
- This is a top-5 candidate. Push for it. Real clients budget *years*, not weeks, for migrations. An undocumented upgrade policy is one of the few things that can block a deal *after* technical evaluation.

---

# Aggregates

## Aggregate — Top 10 New Probes/Findings to Add

Ranked by likely integrator impact.

| Rank | Title | Owning agent | Target section | Why it matters |
|---|---|---|---|---|
| 1 | **Three sidebar entries 404 (versioning, metadata, api-upgrades) — 23% dead-link rate** | `product-manager` | §12 + §11 + §13 | Pattern-level Pillar 1 failure. Versioning was GAP-01; adding metadata + api-upgrades makes it a deal-blocker for enterprise clients. |
| 2 | **No `metadata` field / undocumented if it exists** | `data-engineer` + `product-manager` | §11 | Every modern payments API has metadata for integrator reconciliation. Absence (or undocumented presence) blocks Day-1 ops mapping. |
| 3 | **Fourth error envelope shape D — bare `{message}` on auth 401** | `data-engineer` + `qa-engineer` | §3 | flow-design §2.3 catalogued 3 shapes; auth-guide reveals a 4th. Sharpens GAP-05; generic error handlers crash on `.code is null`. |
| 4 | **Error-handling page lists ~6 codes; runtime has 12+** | `product-manager` + `qa-engineer` | §9 | The dedicated docs page misses ~80% of the actual error inventory. Pillar 1 catastrophic. |
| 5 | **Idempotency-Key case sensitivity (industry standard vs Kira's lowercase)** | `data-engineer` | §10 | Stripe convention is `Idempotency-Key` (Title-Case); Kira docs say `idempotency-key` (lowercase). Probe whether industry-standard casing is accepted. |
| 6 | **Webhook acknowledgment timeout SLO undocumented (interacts with serverless cold-starts)** | `product-manager` + `fullstack-integrations-specialist` | §8 | Vercel/Lambda cold-starts can exceed Kira's (unstated) ack timeout, leading to duplicate deliveries with the wrong receiver design. |
| 7 | **Wallets product on use-case-comparison table but no `/v1/wallets` endpoint family in catalogued reference** | `product-manager` | §2 | Marketed product without discoverable API surface. |
| 8 | **Open-redirect risk on Payment Link `redirect_url`** | `fullstack-integrations-specialist` + `api-security-auditor` | §7 | If `redirect_url` isn't tenant-allowlisted, the Kira-branded URL becomes a phishing weapon. |
| 9 | **Recipients sidebar parent is a stub (Pillar 1 findability — pattern with §5 + §11 + §12 + §13)** | `product-manager` | §5 | One more pixel of the dead-link pattern. |
| 10 | **request_id told-to-attach in support emails but never returned by API** | `product-manager` + `data-engineer` | §9 | Sharpens GAP-06: the docs *contradict themselves* — support says "include Request ID" but the API never emits one. |

## Aggregate — Sections by Coverage Status

| Section | Status | Anchors | Net new probes |
|---|---|---|---|
| 1. kira-api-overview | COVERED | §1, §1.1, §1.3 | 3 (PM × 2, devil × 1) |
| 2. use-case-product-comparison | PARTIAL | Appendix A only | 9 (PM × 4, architect × 2, fullstack × 2, QA × 1) |
| 3. getting-started | PARTIAL | §1.1, §2.1 + sub-pages | 13 (PM × 2, architect × 2, data-eng × 3, security × 3, QA × 2, plus shape-D source) |
| 4. users | COVERED | §3.2, §3.3, §5.2, GAP-14 | 9 (fullstack × 3, func × 3, QA × 1, security × 2) |
| 5. recipients | PARTIAL | §3.5 (subsections only) | 3 (PM × 1, data-eng × 1, devil × 1) |
| 6. virtual-accounts | COVERED | §3.4, §5.3, §4.1, GAP-22/27 | 10 (data-eng × 3, func × 2, security × 3, devil × 1, partner-bank-count × 1) |
| 7. payment-link | COVERED | §3.9, §2.7, GAP-12 | 13 (fullstack × 5, func × 3, security × 2, QA × 1, redirect-contract × 2) |
| 8. webhooks | COVERED | §2.7, §4.6, GAP-11/12/21 | 13 (fullstack × 2, func × 2, security × 5, QA × 2, PM × 2) |
| 9. error-handling | PARTIAL | §2.3, GAP-05/06 | 11 (PM × 5, data-eng × 2, QA × 2, security × 1, devil × 1) |
| 10. idempotency | COVERED | §2.4, GAP-07/08 | 6 (data-eng × 4, func × 1, QA × 1) |
| 11. metadata | MISSING (404) | none — NEW GAP | 7 (PM × 3, data-eng × 3, security × 2, devil × 1) — minus dup |
| 12. versioning | MISSING (404 confirmed) | §1.2, GAP-01 | 4 (data-eng × 3, security × 1) |
| 13. api-upgrades | MISSING (404) | none — NEW GAP | 4 (PM × 2, architect × 1, security × 1, devil × 1) — minus dup |

**Tally:** COVERED = 6 · PARTIAL = 4 · MISSING = 3. Total net-new probes/findings = **~105** (including shape-D, partner-bank-count, redirect-contract sub-probes counted once).

## Aggregate — Docs Sections Not in flow-design.md Appendix A

| Slug | URL | Status | Recommended action |
|---|---|---|---|
| `recipients` | https://kira-financial-ai.readme.io/docs/recipients | Stub/landing page (200 but no content) | Add to Appendix A with the "Pages that are stubs" note next to `llms-full.txt` |
| `metadata` | https://kira-financial-ai.readme.io/docs/metadata | **404 Not Found** | Add to Appendix A "Pages that 404'd" + open GAP-36 (metadata feature undocumented or undeployed) |
| `versioning` | https://kira-financial-ai.readme.io/docs/versioning | **404 (already in Appendix A as smoking-gun for GAP-01)** | No action — already correctly anchored |
| `api-upgrades` | https://kira-financial-ai.readme.io/docs/api-upgrades | **404 Not Found** | Add to Appendix A "Pages that 404'd" + open GAP-35 (no upgrade/deprecation policy) |

## Aggregate — Suggested Updates to flow-design.md

1. **Extend §2.3 with Shape D — bare `{message}` envelope.** The auth-guide 401 expired-token body `{"message": "The incoming token has expired"}` has neither `code` nor nested `error`. Update GAP-05 to "four coexisting shapes."
2. **Open GAP-35 (api-upgrades 404) and GAP-36 (metadata 404).** Both are sidebar entries with no content; both are pattern-level Pillar 1 findings; both go in §6.
3. **Add §3.x Wallets — investigation needed.** The use-case-comparison page treats Wallets as a 5th product line; no `/v1/wallets` reference page is in Appendix A. Either crawl for one or open a GAP entry.
4. **Update §1.1 partner-bank inventory.** Three banks are named in §1 (Portage / Austin Capital Trust / Slovak Savings Bank); marketing claims 4 FDIC-insured banks. Reconcile or open a GAP.
5. **Add §2.9 — Payment Link redirect contract.** The `redirect_url` query-string contract (`?status=success` vs `?status=cancelled` appended) is captured in §3.9 prose but should be promoted to a cross-cutting redirect-contract subsection given the security implications and the §2 "Embeddable: Yes" claim.
6. **Sharpen GAP-06.** Error-handling page tells support to attach "Request ID (if available)" — but the API never emits one. This makes GAP-06 a self-contradicting docs gap, not just an absence. Worth a severity bump.
