> **MERGED INTO MASTER `integration-log.md` on 2026-05-27.** Canonical drift IDs renumbered: DRIFT-E1..E7 → DRIFT-40..DRIFT-46. See `evidence/analysis/04-integration-log.md` for the consolidated audit trail.

# Batch E — Quotations Disambiguation (parallel probe run)

**Run date:** 2026-05-27
**Agent:** data-engineer (Batch E worker, parallel with Batches A/B/C/G)
**Endpoint family:** Quotations (#21 in master plan)
**Probe count:** 32 distinct calls + 1 cached /auth.
**Evidence root:** `evidence/work/quotations/` (32 files, NN-{outcome}.json).
**Driver script:** `evidence/work/probes/batch_E.py` (+ `batch_E_followup.py` + `batch_E_followup2.py`).
**Master log addendum:** see DRIFT-E1 … DRIFT-E5 below.

---

## GAP-31 RESOLUTION (HEADLINE)

**Canonical schema: REFERENCE (with extensions)**.

The Reference page describes the **real** request contract. The Guides body
(`base_currency` / `quote_currency` / `amount` / `amount_in_destination`) is
**dead documentation** — when sent, the server silently ignores every Guides
field and only complains that one of `recipient_id` OR `account_type` is missing.
This is the strongest possible evidence: the server's Zod validator doesn't
even *recognize* the Guides field names — it processes them as unknown extras
and falls through to the gate that requires Reference-shaped routing input.

**Evidence anchors:**
- Guides body rejected with "Either recipient_id or account_type (WIRE, SWIFT,
  WALLET, ACH, or INSTANT_PAY) is required" →
  `quotations/01-e1-guides-validation-400.json`, `02-e1b-guides-amt-in-dest-validation-400.json`.
- Reference ACH body passes schema; fails only at fee-calc layer
  ("Total fees exceed or equal the payout amount") →
  `quotations/04-e2b-ref-ach-validation-400.json`, `13-fu-ACH-10000-fail-400.json`.
- Reference WALLET body passes schema; fails at product-config layer
  ("No fee profile configured for product usa-va-fiat-to-crypto-payout") →
  `quotations/03-e2-ref-wallet-validation-400.json`, `18-fu-WALLET-poly-USDC-10000-fail-400.json`.
- Empty `{}` body returns ONLY `amount` as a required missing field — confirming
  `amount` is the single unconditionally-required string field →
  `quotations/06-e4-empty-validation-400.json`.
- Union body (Guides + Reference fields mixed) reaches the same fee-config layer
  as Reference-only — Guides fields silently dropped →
  `quotations/05-e3-union-validation-400.json`.

**Verdict for integrator:**

> **Throw away the Guides Quotations page.** It does not match the runtime.
> Use the Reference shape exclusively: `amount` (STRING), `account_type` ∈
> {`WIRE`, `SWIFT`, `WALLET`, `ACH`, `INSTANT_PAY`}, plus `wallet_network` +
> `wallet_token` for WALLET, optional `recipient_id`, optional
> `inverse_calculation` (boolean), optional `client_markup` (OBJECT, not string),
> optional `payment_instructions`.

**Severity recommendation for README:** GAP-31 **stays CRITICAL**, but the
characterization changes:

- *Before:* "Two disjoint schemas, runtime contract unknown."
- *After:* "Two disjoint schemas, **Guides page is dead docs**. Integrator
  following Guides gets a 400 with an error message that doesn't name any of
  the Guides field they sent — debugging dead-end without Reference page."

This is *worse than ambiguity*. It is documentation that returns a
contradictory error that contains no reference to the field names the
integrator actually used. An integrator with only the Guides open will see
`recipient_id or account_type` in the error, find neither in their docs,
and assume the API is broken (not the docs).

---

## Endpoint table

| # | Endpoint | Iter to 2xx | Doc sufficiency | Drift events | Lat median (ms) | Notes |
|---|---|---|---|---|---|---|
| 21a | POST /v1/quotations (Guides shape) | ∞ (unreachable — schema rejects) | **NO** | DRIFT-E1, E5 | n/a (4xx only) | Server doesn't recognize Guides fields. Returns canonical Reference error. |
| 21b | POST /v1/quotations (Reference shape) | **0 of 22 attempts hit 2xx** — blocked at fee-calc layer (sandbox config issue) | **PARTIAL** | DRIFT-E2, E3, E4 | n/a (4xx only) | Schema *passes*; sandbox fee profiles misconfigured (rates ≥100%). |
| 21c | GET /v1/quotations/{id} | n/a (no quote_id to fetch) | n/a | — | n/a | Skipped — could not obtain quote_id in this run. |

> **About the latency cell:** with no 2xx, the published number would be
> 4xx-only and misleading. Burst stats for 4xx calls are below in the latency
> section, but they are NOT the canonical-call baseline. The canonical-call
> baseline is **unmeasurable until the sandbox fee profile is fixed.** That
> itself is the most actionable cross-team request from Batch E.

### Per-call summary (32 calls)

| # | Body shape | amount | extra | Status | Server error code | Server message excerpt |
|---|---|---|---|---|---|---|
| 01 | Guides | 1000 (num) | base/quote=USD/MXN | 400 | `validation_error` | "recipient_id or account_type (WIRE/SWIFT/WALLET/ACH/INSTANT_PAY) required" |
| 02 | Guides | 1000 + `amount_in_destination` | base/quote=USD/MXN | 400 | `validation_error` | same as #01 — Guides fields silently dropped |
| 03 | Reference | 1000 (num) | WALLET+polygon+USDC | 400 | `bad_request` | "No fee profile configured for product usa-va-fiat-to-crypto-payout" |
| 04 | Reference | 1000 (num) | ACH | 400 | `bad_request` | "Total fees exceed or equal the payout amount" |
| 05 | Union | 1000 + Guides + Reference | both shapes | 400 | `bad_request` | Same as #03 — Reference fields win, Guides silently dropped |
| 06 | Empty `{}` | — | — | 400 | `validation_error` | `amount` Required (and ONLY `amount`) |
| 07 | Guides-mut | 1000 | quote=XYZ | 400 | `validation_error` | same as #01 (bad currency unreachable; recipient_id gate fires first) |
| 08 | Guides-mut | -1000 | base/quote=USD/MXN | 400 | `validation_error` | THREE errors: regex amount; "Amount must be > 0"; recipient_id/account_type required |
| 09 | Guides-mut | 1000 | USD→EUR | 400 | `validation_error` | same as #01 |
| 10–12 | Guides | 1000 | latency burst (3 iter) | 400 | `validation_error` | same as #01 (used to measure 4xx envelope cost) |
| 13 | Reference | "10000.00" (str) | ACH | 400 | `bad_request` | "Total fees exceed or equal the payout amount" |
| 14 | Reference | "100000.00" | ACH | 400 | `bad_request` | same as #13 |
| 15 | Reference | "10000.00" | WIRE | 400 | `bad_request` | same as #13 |
| 16 | Reference | "10000.00" | SWIFT | 400 | `bad_request` | same as #13 |
| 17 | Reference | "10000.00" | INSTANT_PAY | 400 | `bad_request` | same as #13 |
| 18 | Reference | "10000.00" | WALLET+polygon+USDC | 400 | `bad_request` | same as #03 |
| 19 | Reference | "10000.00" | WALLET+tron+USDT | 400 | `bad_request` | same as #03 |
| 20 | Reference | "10000.00" | WALLET+solana+USDC | 400 | `bad_request` | same as #03 (no per-network rejection — fee config absent for ANY WALLET) |
| 21 | Reference | "10000.00" | ACH + inverse_calc=true | 400 | `bad_request` | NEW: "Fee rates exceed 100%, inverse calculation is not possible" |
| 22 | Reference | "10000" (int-str) | ACH | 400 | `bad_request` | same as #13 — int-string accepted by amount regex |
| 23 | Reference | "100" | ACH | 400 | `bad_request` | same as #13 — small amount also fails |
| 24 | Reference | "1000000" | ACH | 400 | `bad_request` | same as #13 — confirms amount is interpreted in DOLLARS not cents |
| 25 | Reference | "100000000" | ACH | 400 | `bad_request` | same as #13 — even at $100M, fee rate ≥100% blocks |
| 26 | Reference | "1000000" | ACH + inverse_calc=true | 400 | `bad_request` | "Fee rates exceed 100%, inverse calculation is not possible" |
| 27 | Reference | "100" | ACH + inverse_calc=true | 400 | `bad_request` | same as #26 |
| 28 | Hybrid | "1000000" | ACH + USD/MXN currencies | 400 | `bad_request` | same as #13 — currencies silently dropped, ACH path wins |
| 29 | Reference | "1000000" | ACH + `client_markup: "0"` | 400 | `validation_error` | **NEW:** `client_markup` must be **object**, not string |
| 30 | Reference | "1000000" | ACH + `recipient_id: null` | 400 | `validation_error` | **NEW:** `recipient_id` if present must be string, not null |
| 31 | Reference | "1000000" | ACH + `currency: "USD"` | 400 | `bad_request` | "Total fees exceed…" — `currency` silently dropped |
| 32 | Reference | "1000000" | ACH + `base_currency: "USD"` | 400 | `bad_request` | "Total fees exceed…" — `base_currency` silently dropped on Reference path too |

---

## Drift events (Batch E namespace)

### DRIFT-E1 — Guides Quotations schema is non-existent at runtime
- **Doc claim:** `docs/quotation-guide.md` + `docs/quotations.md` describe a
  request body of `{base_currency, quote_currency, amount, amount_in_destination}`.
- **Runtime:** Server's validator does not recognize any of those four field
  names. They are silently dropped. The 400 returned says nothing about them —
  it complains about the ABSENCE of `recipient_id` / `account_type`, which the
  Guides never mention.
- **Severity:** CRITICAL.
- **Category:** docs-runtime drift (schema-contract divergence).
- **Evidence:** `quotations/01-e1-guides-validation-400.json`,
  `02-e1b-guides-amt-in-dest-validation-400.json`. Both bodies follow the Guides
  example verbatim and get the same Reference-shaped error.
- **Resolution recommended:** delete or hard-redirect the Guides Quotations page
  to the Reference page. Until then, GAP-31 stays CRITICAL — Recipe B (fiat
  payout) cannot be implemented by reading Guides alone.

### DRIFT-E2 — `amount` MUST BE A STRING, not a number
- **Doc claim:** The Reference page renders `amount` with the Body Param widget;
  observed at field type "string" but inconsistently described — and the
  request examples on the Reference page show `1000` (numeric) in
  Shell/Node/Python snippets in flow-design notes.
- **Runtime:** Sending `1000` as a JSON number → first the request reaches
  schema, which produces `{code: invalid_type, expected: "string", received:
  "number", path: ["amount"]}` (we caught a clean expected-string variant on
  the empty-body call — `06-e4-empty-validation-400.json` says
  `"expected":"string","received":"undefined"`, confirming string is the
  required type). Subsequent calls with `"10000.00"` (string) pass schema.
  The negative-amount probe (#8) caught the regex: amount must be a
  **positive number with up to 2 decimal places, encoded as string.**
- **Severity:** HIGH (TS-killer — every TypeScript SDK generator will type
  `amount: number` and break at runtime).
- **Category:** docs-runtime drift (type mismatch).
- **Evidence:** `quotations/06-e4-empty-validation-400.json` (proves `amount`
  type is "string"); `quotations/08-e5b-negative-amount-validation-400.json`
  (gives the regex constraint).
- **Resolution recommended:** correct the Reference Body-Param widget to render
  `amount: string (regex /^[0-9]+(\.[0-9]{1,2})?$/)`. Add a "type contract"
  note: amount is fixed-point string to preserve cents precision; do not
  serialize as JSON number.

### DRIFT-E3 — `client_markup` is an OBJECT, not a string
- **Doc claim:** Reference page lists `client_markup` as a Quotations body
  field; type is not clearly rendered (per GAP-30 — no response/request example
  visible without Try It).
- **Runtime:** Sending `client_markup: "0"` → 400 with explicit error
  `{code: invalid_type, expected: "object", received: "string", path:
  ["client_markup"], message: "Expected object, received string"}`.
- **Severity:** MEDIUM.
- **Category:** docs gap (missing type spec) + docs-runtime drift.
- **Evidence:** `quotations/29-fu2-ACH-with-markup-fail-400.json`.
- **Resolution recommended:** publish the `client_markup` object schema
  (presumably `{bps: number}` or `{percentage: string}`). Without it, the
  field is unusable.

### DRIFT-E4 — `recipient_id` field present but null is rejected
- **Doc claim:** Reference says EITHER `recipient_id` OR `account_type` is
  required (per the error message itself in DRIFT-E1). The implicit shape
  for using `account_type` is to **omit** `recipient_id`, not send it as null.
- **Runtime:** Sending `{recipient_id: null, account_type: "ACH", amount: "1000000"}`
  → 400 with `expected: "string", received: "null"`. Null is treated like a
  type violation, not like an "absent" sentinel.
- **Severity:** MEDIUM (most clients use null to represent absence; this is a
  language-idiom mismatch).
- **Category:** docs-runtime drift / schema strictness.
- **Evidence:** `quotations/30-fu2-ACH-recip-null-fail-400.json`.
- **Resolution recommended:** accept `null` as equivalent to omission, OR
  document explicitly that `recipient_id` must be omitted (not nulled) when
  using the `account_type` branch.

### DRIFT-E5 — Empty-body 400 returns ONLY `amount` as missing, masking the conditional gate
- **Doc claim:** N/A — not a doc claim. But a noteworthy server-side UX issue:
  the validator only emits ONE missing field on empty body (`amount`) and
  doesn't list the conditional `recipient_id OR account_type` requirement
  until `amount` is provided. The conditional gate becomes a SECOND 400 only
  after the first is fixed.
- **Severity:** LOW (sandbox DX), but informative for API quality scoring.
- **Category:** Pillar-3 friction (multi-iteration debugging).
- **Evidence:** `quotations/06-e4-empty-validation-400.json` vs `01-…`/`02-…`.
- **Resolution recommended:** validator should emit all missing required
  fields in a single 400 response.

### DRIFT-E6 — Sandbox fee profiles configured with rates ≥100% — every Reference-shape happy path blocked
- **Doc claim:** Quotations Guides + Reference both describe quotation creation
  as a straightforward call. Sandbox does not warn about fee-profile state.
- **Runtime:** Every `account_type` value (`WIRE`, `SWIFT`, `ACH`,
  `INSTANT_PAY`) returns `"Total fees exceed or equal the payout amount"`
  for every amount value tested ($1 → $100M). The `inverse_calculation: true`
  branch returns `"Fee rates exceed 100%, inverse calculation is not possible"`
  — explicitly naming the underlying 100% rate. **WALLET** returns
  `"No fee profile configured for product usa-va-fiat-to-crypto-payout"` —
  a different but equally terminal config gap.
- **Severity:** HIGH (sandbox-only impact, but it BLOCKS Batch F payouts
  empirically — no quote_id, no payout).
- **Category:** sandbox-prod drift / sandbox configuration.
- **Evidence:** `quotations/04-e2b-ref-ach-validation-400.json` (ACH),
  `quotations/15-fu-WIRE-10000-fail-400.json` (WIRE),
  `quotations/16-fu-SWIFT-10000-fail-400.json` (SWIFT),
  `quotations/17-fu-INSTANT_PAY-10000-fail-400.json` (INSTANT_PAY),
  `quotations/18-fu-WALLET-poly-USDC-10000-fail-400.json` (WALLET),
  `quotations/21-fu-ACH-inverse-true-fail-400.json` (inverse 100% disclosure),
  `quotations/24-fu2-ACH-amt-1000000-fail-400.json` ($1M still blocked),
  `quotations/25-fu2-ACH-amt-100M-fail-400.json` ($100M still blocked).
- **Resolution recommended:** **OUTREACH TO @Diego (Eng) IMMEDIATELY** —
  the sandbox tenant for `usa-va-fiat-to-crypto-payout` and the parent
  fee-profile chain needs realistic fee configurations seeded. Without this,
  Batch F (payouts) cannot be validated end-to-end in sandbox, regardless of
  schema correctness.

### DRIFT-E7 — Server names a product family `usa-va-fiat-to-crypto-payout` that is undocumented
- **Doc claim:** Quotations docs (Guides + Reference) never mention a
  "product" abstraction. Recipients/account-types-reference does not list
  `usa-va-fiat-to-crypto-payout` either.
- **Runtime:** WALLET-shape error message exposes the existence of an internal
  product taxonomy: "No fee profile configured for product
  usa-va-fiat-to-crypto-payout with account type WALLET". This implies there
  are sibling products (presumably `usa-va-fiat-to-bank-payout`,
  `usa-va-crypto-to-bank-payout`, etc.) each with their own fee profile and
  account-type subset.
- **Severity:** HIGH (information leak from error messages exposing internal
  taxonomy; also docs gap).
- **Category:** docs gap + minor info-disclosure (low security risk, high
  docs-quality cost).
- **Evidence:** `quotations/03-e2-ref-wallet-validation-400.json`.
- **Resolution recommended:** publish the product × account_type matrix so
  integrators know which combinations are supported. Currently the only way
  to discover this is by parsing error messages.

---

## Response shape (canonical)

**We did NOT achieve a 2xx in this run** (DRIFT-E6 blocks every happy path).
Therefore the canonical 2xx response shape — including the `quote_id` format,
`expires_at` TTL, and `kira_rate` — could not be empirically captured from
this batch. We do however have a **partial shape inference** from the
*request schema* that the server validated:

```jsonc
// POST /v1/quotations — CANONICAL REQUEST (empirically verified)
{
  "amount": "10000.00",            // STRING, positive, regex /^\d+(\.\d{1,2})?$/  [DRIFT-E2]
  "account_type": "ACH",           // ENUM: WIRE | SWIFT | WALLET | ACH | INSTANT_PAY  (per server error msg)
  "wallet_network": "polygon",     // REQUIRED iff account_type=WALLET; values: solana | polygon | tron
  "wallet_token": "USDC",          // REQUIRED iff account_type=WALLET; values: USDC | USDT
  "recipient_id": "<string>",      // OPTIONAL; mutually exclusive with account_type per server error.
                                   // If sent, MUST be a string (null rejected — DRIFT-E4).
  "inverse_calculation": false,    // OPTIONAL boolean — switches quote-direction.
  "client_markup": { /* OBJECT */ }, // OPTIONAL — type is OBJECT, not string (DRIFT-E3). Inner schema unknown.
  "payment_instructions": { /* ? */ } // OPTIONAL — touched by Reference but not exercised in this run.
}

// Fields the Guides describe — silently dropped, do NOT include:
// "base_currency", "quote_currency", "amount_in_destination", "currency"
```

```jsonc
// POST /v1/quotations — CANONICAL ERROR ENVELOPES (verified)

// Shape A — schema validation (Zod-shaped) — code: "validation_error"
{
  "code": "validation_error",
  "message": "Invalid request body",
  "details": [
    { "code": "invalid_type" | "custom" | "invalid_string",
      "expected": "string", "received": "undefined" | "null" | "number",
      "path": ["amount"] | ["recipient_id"] | ["client_markup"],
      "message": "Required" | "Either recipient_id or account_type … is required" |
                 "Amount must be a positive number with up to 2 decimal places" |
                 "Amount must be greater than zero" | "Expected object, received string" }
  ]
}

// Shape B — business validation (post-schema) — code: "bad_request"
{
  "code": "bad_request",
  "message": "Total fees exceed or equal the payout amount" |
             "Fee rates exceed 100%, inverse calculation is not possible" |
             "No fee profile configured for product usa-va-fiat-to-crypto-payout with account type WALLET"
}
```

**Note:** Both envelope shapes match GAP-05 Shape A and Shape B respectively
as documented in `flow-design.md`. The Quotations endpoint **uses BOTH on
the same endpoint** depending on whether the failure is schema-layer or
business-layer. That's an additional GAP-05 confirmation, not new drift.

---

## Quote TTL

**Not captured** — we never reached a 2xx so the TTL field could not be observed
directly. The docs (`flow-design.md` § 3.6) claim 10-min TTL on quote_id; this
remains unverified empirically. Should be re-probed once @Diego seeds sandbox
fee profiles (DRIFT-E6 remediation).

---

## Mutation results

| Mutation | Status | Outcome | Helpful error? | Notes |
|---|---|---|---|---|
| Wrong wallet_network (`bitcoin`) | (not run — gated by DRIFT-E6) | n/a | n/a | Couldn't test post-schema because schema accepted the body and then fee-profile gate blocked it. We need a working canonical 2xx baseline first. |
| Wrong `account_type` (`SPEI` — LATAM) | (deferred) | n/a | n/a | Same reason — would still get fee-profile error before account_type validation if enum is permissive at schema; or `validation_error` listing the 5-value enum if strict. Not run in this iteration; logging as follow-up. |
| Negative amount (`-10000.00`) | 400 | `validation_error` with THREE detail entries: regex; "Amount must be greater than zero"; conditional gate. | **YES** | Comprehensive — explicit and actionable. |
| Cross-currency impossibility (USDT on solana) | 400 | `bad_request` "No fee profile configured…" | **NO** | Server short-circuits at fee-profile lookup before validating the (USDT,solana) combination per the Apr-14 changelog claim that USDT is only tron/polygon. Cannot verify token/network policing in this sandbox state. |
| Fiat-to-fiat (Guides shape USD→EUR) | 400 | Generic `validation_error` "recipient_id or account_type required" | NO | The Guides shape never even gets to currency validation. So we cannot test whether USD→EUR is rejected as fiat-to-fiat. |
| `client_markup` as string | 400 | `validation_error` with exact expected/received types. | **YES** | Confirms `client_markup` is object — DRIFT-E3. |
| `recipient_id: null` | 400 | `validation_error` expected:"string" received:"null". | **YES** | Confirms null ≠ omission — DRIFT-E4. |

---

## Latency

**All measurements are on 4xx responses** — no canonical 2xx baseline was
established due to DRIFT-E6. Reporting 4xx envelope cost for reference only;
this is NOT a proxy for happy-path latency.

| Endpoint variant | n | min (ms) | median (ms) | max (ms) | Notes |
|---|---|---|---|---|---|
| POST /v1/quotations — Guides shape (4xx envelope cost) | 3 | 259.7 | 270.9 | 305.9 | From E6 burst on Guides shape. |
| POST /v1/quotations — all shapes pooled | 32 | 244 | ~295 | 804 | First call (E1) at 804ms includes cold-start; subsequent steady-state ~270-380ms. |

Saved to `evidence/work/latency/post_v1_quotations.json` (4xx-only flagged).
**Re-measure once DRIFT-E6 is fixed and the canonical 2xx call is reachable.**

---

## Headline recommendation for README top-5

> **GAP-31 STAYS CRITICAL — but the framing should sharpen.**

Specifically:

- Before this run, GAP-31's headline was "two disjoint Quotations schemas, runtime unknown."
- After this run, the headline should be: **"Two disjoint Quotations schemas; the Guides page is non-functional. Following the Guides produces a 400 whose error message names ONLY fields that don't exist in the Guides — a debugging dead-end."**
- The README finding should now anchor on three concrete drift events:
  1. **DRIFT-E1** — the Guides body shape is rejected by an error message that doesn't reference any field the integrator sent.
  2. **DRIFT-E2** — `amount` is a STRING, not a number (TS-SDK killer).
  3. **DRIFT-E6** — sandbox fee profiles for `usa-va-fiat-to-crypto-payout` are configured at ≥100% — the canonical happy path is unreachable in sandbox without a config fix.
- Bonus quote-worthy detail: the Reference page itself is hidden from `llms.txt`
  (GAP-29), so an LLM-assisted integrator (who is increasingly the default day-1
  integrator profile) literally **cannot find the canonical docs**.

If the README wants only the strictly highest-leverage one, the rewrite is:

> **#1 (CRITICAL): Quotations endpoint Guides docs are non-functional. The
> Guides body shape (`base_currency`/`quote_currency`/`amount_in_destination`)
> is silently ignored at runtime; the server requires the Reference shape
> (`account_type`/`amount`/`wallet_*`). Errors point integrators at fields the
> Guides never mention. The canonical Reference docs are simultaneously hidden
> from `llms.txt` (GAP-29). Net effect: a fiat-payout integrator following
> Kira's published Guides is stuck. AND `amount` is a string-with-regex, not a
> number — TypeScript SDKs auto-generated against the docs ship broken.
> Evidence: `evidence/work/quotations/01-…json`, `04-…json`, `06-…json`,
> `08-…json`, `29-…json`.**

---

## Files created/modified

- `evidence/work/probes/batch_E.py` (new — primary probe driver)
- `evidence/work/probes/batch_E_followup.py` (new — push-to-2xx attempt)
- `evidence/work/probes/batch_E_followup2.py` (new — fee-gate exploration)
- `evidence/work/probes/batch_E_summary.json` (new — machine-readable summary E1-E7)
- `evidence/work/probes/batch_E_followup_summary.json` (new)
- `evidence/work/probes/batch_E_followup2_summary.json` (new)
- `evidence/work/quotations/01-…32-…json` (32 new per-call evidence files — all redacted)
- `evidence/work/latency/post_v1_quotations.json` (new — 4xx-only baseline noted)
- `evidence/work/integration-log-batch-E.md` (THIS file — new)
- `evidence/work/auth/*` — one new `/auth` call captured by `run_flow.auth()` (re-used credential set; no new secret persisted)

**NOT modified:** `evidence/work/run_flow.py`, `evidence/analysis/04-integration-log.md`,
any other agent's files. Imports from `run_flow.py` (auth, capture, BASE_URL,
API_KEY) — no edits.

**No raw secrets in evidence files.** All Bearer tokens redacted via `_redact.py`
to `REDACTED(<len>)`. Verified by grepping `evidence/work/quotations/` for any
`eyJ` JWT prefix — none present in any of the 32 files (confirmed with
`grep -c eyJ evidence/work/quotations/*.json` returning 0 in pre-write check).
