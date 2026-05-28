# Kira PM Exercise 2 — API Integration & Error Hunt

Public exercise repo. Findings from an end-to-end empirical evaluation of the Kira sandbox API against its public docs (`kira-financial-ai.readme.io`) and partner-distributed guides (`kira-sandbox-integration-guide.docx`, `kira-prod-certification-matrix.docx`).

**Methodology:** three sequential phases —
1. **Documentation Quality Evaluation** — score the docs as the integrator's only Day-0 surface.
2. **Empirical Integration with iteration telemetry** — probe every endpoint, capture iteration count to 2xx, doc-sufficiency, and every doc-vs-runtime drift.
3. **Adversarial Testing** — OWASP API Top 10 security, business-logic abuse, and load.

**Coverage:** 18/30 endpoints empirically validated · 53 drift events captured · 78 underlying findings synthesized · 108-row test matrix with executable Given/When/Then · 4 critical security findings.

---

## Top 5 Findings

Severity ordering: CRITICAL → CRITICAL → CRITICAL → CRITICAL → CRITICAL. The 5th is downgraded internally (compound docs + congruence) but kept at CRITICAL because every integrator hits it on call #1.

### Finding #1 — Public docs are materially incomplete; the real Kira contract is partner-distributed (Word docs)
**Severity:** CRITICAL
**Category / Pillar:** Documentation Quality + Ease of Connection
**Why this matters to a client:** A real integrator opening only `kira-financial-ai.readme.io` (the public docs portal) hits a Day-1 wall: (1) the documented `/sandbox` base URL returns 403 on call #1, (2) the `POST /v1/versioning/upgrade` pin endpoint required to lock to v2026-04-14 is nowhere in the public docs, (3) the sandbox manually rejects every user after ~90s without telling you the workaround is "ping your Kira contact in Slack," (4) the Postman collection that contains the canonical request/response shapes is referenced 7× in the partner guide but distributed nowhere public, (5) the Quotations Reference and Guides describe two disjoint schemas — the Guides body is silently dropped at runtime. **22 of our 53 drifts are acknowledged by the partner guide; 0 of 53 are acknowledged by the public docs.** Cost estimate: 4–8 engineering days lost vs. <1 day for a partner-doc-equipped integrator. For a Banco Industrial / N1co procurement evaluation this is the difference between "ship a prototype" and "fail the eval."
**Evidence:** `evidence/analysis/13-docs-vs-partner-guide-delta.md` § 3 · `evidence/analysis/03-phase-1-findings.md` (Findings #1, #2, #7, #8) · `evidence/analysis/12-api-reference-coverage.md` · `evidence/analysis/11-docs-coverage-matrix.md`
**Spec:** `features/01-public-docs-materially-incomplete.feature`
**Reproduction:** open `kira-financial-ai.readme.io/v2026-04-14`, attempt `POST /sandbox/auth` per the documented base URL, observe 403; then attempt `POST /v1/versioning/upgrade` (cited only in the partner Word doc) at the no-prefix base and observe 200; conclude the docs and runtime disagree on every base-URL claim.
**Disclosure status:** documented in this deliverable; recommended next step is coordination with @Diego before broader publication.

---

### Finding #2 — Webhook subsystem is a triple-vector exploit (SSRF + cross-tenant `client_uuid` + optional secret + cleartext URL + opaque response)
**Severity:** CRITICAL (CVSS 9.1)
**Category / Pillar:** Integration Hardening (security) + Webhook contract
**Why this matters to a client:** `POST /webhooks/register` accepts arbitrary `webhook_url` values — `http://localhost`, `http://169.254.169.254/latest/meta-data/`, `http://10.0.0.1`, `http://[::1]` — with HTTP 200 and persists them, and Kira's egress fetcher (`54.201.149.241`) does reach the URL at delivery time (IMDS reachability empirically confirmed). The endpoint also accepts arbitrary foreign `client_uuid` values: 3/3 random UUIDs registered (foreign-tenant webhooks). The `secret` field is effectively optional (`null` and omission both accepted, no HMAC material persisted), cleartext `http://` URLs are accepted, and the response is opaque (no id, no list, no delete) — so once a hostile registration lands you cannot revoke it through the API. **Neither the public docs nor the partner guide acknowledges any of this**, so even a partner-equipped integrator does not know to defend against it. Combined chain: one leaked API key + Bearer token registers a cross-tenant webhook pointing at attacker infrastructure, unsigned, over HTTP, with Kira's fetcher reaching AWS IMDS on delivery.
**Evidence:** `evidence/analysis/05-security-audit.md` § Finding 1 · `evidence/analysis/06-abuse-scenarios.md` Scenario 5 · `evidence/work/security/webhook-ssrf/` · `evidence/work/abuse/webhook-spoof/` · DRIFT-47, DRIFT-48, DRIFT-51, DRIFT-53, ABUSE-4
**Spec:** `features/02-webhook-triple-vector.feature`
**Reproduction:** `POST https://api.balampay.com/webhooks/register` with `{webhook_url: "http://169.254.169.254/latest/meta-data/", secret: null, client_uuid: "<random-uuid>"}` and Bearer+x-api-key → 200. Then trigger any delivery event; observe outbound request from Kira IP 54.201.149.241 to the URL.
**Disclosure status:** included in this deliverable. Recommended next step: coordinate with @Diego on remediation timeline before any broader publication or third-party sharing of reproduction details.

---

### Finding #3 — PII unmasked across `/v1/users` LIST and `/v1/recipients` GET — SSN, document_number, CLABE, routing, IBAN, wallet plaintext
**Severity:** CRITICAL
**Category / Pillar:** Integration Hardening (security) + Regulatory (PCI / GLBA-adjacent)
**Why this matters to a client:** The public docs show `account_details` masked as `****7890`. The runtime returns full plaintext across every read path: `GET /v1/users` (list and detail) returns full SSN and `document_number`; `GET /v1/recipients/{id}` returns full CLABE (SPEI), routing+account (ACH USD), IBAN+SWIFT (SWIFT EUR), and wallet address (USDT TRON) on all 4 recipient variants. One leaked credential bulk-scrapes the entire customer book in plaintext. Plaintext routing+account enables fraudulent ACH/SPEI debits without any further compromise. **Neither public docs nor the partner guide mentions masking**, so an integrator has no way to know they are storing/forwarding plaintext PII. For a regulated buyer (BIA, N1co) this is a state money-transmitter / GLBA-adjacent finding that blocks production access independent of any other technical work.
**Evidence:** `evidence/analysis/05-security-audit.md` § Findings 2-3 · DRIFT-30 (broadened across all variants in Phase 3) · `evidence/work/security/pii-unmasked-users/` · `evidence/work/security/pii-unmasked-recipients/`
**Spec:** `features/03-pii-unmasked.feature`
**Reproduction:** `GET https://api.balampay.com/v1/users` with valid auth → inspect `body.data[].document_number` (full digits, not last-4). `GET https://api.balampay.com/v1/recipients/{id}` for any SPEI/ACH/SWIFT/USDT recipient → inspect `body.account_details` (full plaintext).
**Disclosure status:** included in this deliverable. Recommended next step: coordinate with @Diego on remediation timeline.

---

### Finding #4 — TLS 1.0 and TLS 1.1 accepted by `api.balampay.com:443`
**Severity:** CRITICAL
**Category / Pillar:** Integration Hardening (transport security) + Regulatory
**Why this matters to a client:** `openssl s_client -tls1` and `-tls1_1` both complete a successful handshake against the production-fronting host, and legacy ciphers negotiate. PCI-DSS Req 4.1, FFIEC, and US state money-transmitter rules require TLS 1.2 minimum; some require TLS 1.3. For a Banco Industrial or N1co InfoSec review this is "no, you cannot ship until this is fixed" — independent of technical exploit potential, the procurement gate doesn't open. Neither the public docs nor the partner guide acknowledges or commits to fixing this.
**Evidence:** `evidence/analysis/05-security-audit.md` § Finding 4 · `evidence/work/security/security-headers-and-tls/03-tls-protocol-audit.json`
**Spec:** `features/04-tls-1-0-1-1-accepted.feature`
**Reproduction:** `openssl s_client -connect api.balampay.com:443 -tls1` → handshake completes (expected: alert). `openssl s_client -connect api.balampay.com:443 -tls1_1` → handshake completes.
**Disclosure status:** included in this deliverable. Recommended next step: coordinate with @Diego on remediation timeline.

---

### Finding #5 — `/sandbox` base URL is wrong everywhere — and even the partner guide directs to a broken URL (DRIFT-1 + DRIFT-1b + DRIFT-1c compound)
**Severity:** CRITICAL
**Category / Pillar:** Docs↔Runtime Congruence + Documentation Quality
**Why this matters to a client:** The public docs say sandbox base = `https://api.balampay.com/sandbox`. `POST /sandbox/auth` returns 403; the working base is `https://api.balampay.com` (no prefix) (DRIFT-1). The partner-distributed `kira-sandbox-integration-guide.docx` insists the `/sandbox` prefix IS required and describes a one-time `POST /sandbox/v1/versioning/upgrade` "pin" call that supposedly unlocks the stage. Empirical revalidation on 2026-05-28 (6-probe re-run, `evidence/work/versioning/`) confirms the pin endpoint works **only** at the no-prefix base, and after a successful pin the `/sandbox/*` tree continues to return the same 403/401 envelopes (DRIFT-1b, DRIFT-1c). **The partner guide is wrong about the prefix on every URL it lists.** Two parallel auth/base-URL models exist (one in public docs, one in the partner guide); neither matches runtime; the Postman collection (per the guide, tested 2026-05-26) is the only artifact that uses the working URL, but it is not publicly distributed. Every integrator — public-doc reader OR partner-doc holder — hits a gateway error on call #1.
**Evidence:** `evidence/analysis/04-integration-log.md` § DRIFT-1, DRIFT-2 (with 2026-05-28 revalidation block) · `evidence/work/auth/01-fail-403.json` · `evidence/work/auth/02-success.json` · `evidence/work/versioning/01-pin-no-prefix-success.json` · `evidence/work/versioning/03-sandbox-auth-after-pin-fail-403.json` · `evidence/work/versioning/04-sandbox-users-after-pin-fail-401.json`
**Spec:** `features/05-sandbox-base-url-wrong.feature`
**Reproduction:** `POST https://api.balampay.com/sandbox/auth` with valid `client_id`+`password` → 403 ForbiddenException. `POST https://api.balampay.com/auth` (no prefix) → 200 with JWT. Then `POST https://api.balampay.com/v1/versioning/upgrade` body `{"target_version":"2026-04-14"}` → 200. Re-attempt `POST https://api.balampay.com/sandbox/auth` → still 403 (pin does not unlock the prefix).
**Disclosure status:** documented in this deliverable; recommended next step is coordination with @Diego before broader publication.

---

### Honorable mentions

- **`/v1/banks` Colombia-only at runtime, despite multi-country pretense** (DRIFT-8 / GAP-32) — every LATAM payout recipe is blocked unless the integrator knows to add `country_code=CO`; not in either doc.
- **6 distinct error envelope shapes across the API** (DRIFT-6 + ABUSE-5 + Phase-1 Finding #3) — partner guide concedes the inventory and commits to a v2026-XX-XX unification; downgraded internally but still a Day-1 build-blocker.
- **Idempotency-Key silently ignored on `/webhooks/register`** (DRIFT-50) — partner guide acknowledges + ships a fix.
- **Webhook lifecycle is opaque** (DRIFT-51) — no id, no list, no delete; coming in v2026-XX-XX per the partner guide.

---

## Repo Layout

```
.
├── README.md                              ← this file (top-5 findings)
├── CLAUDE.md                              ← project context (private)
├── Exercise 2 — Brief.md                  ← the original brief
├── features/                              ← one .feature per finding
├── evidence/
│   ├── ai/prompt-log.md                   ← every prompt logged ES + EN
│   ├── analysis/                          ← 13 high-value analysis docs
│   │   ├── 01-test-matrix.md              ← 108-row source of truth
│   │   ├── 02-test-coverage-heatmap.md
│   │   ├── 03-phase-1-findings.md         ← docs-quality findings
│   │   ├── 04-integration-log.md          ← Phase 2 drift ledger (53 drifts)
│   │   ├── 05-security-audit.md           ← Phase 3 OWASP API Top 10
│   │   ├── 06-abuse-scenarios.md          ← Phase 3 business-logic abuse
│   │   ├── 07-load-summary.md             ← Phase 3 stress/latency
│   │   ├── 08-flow-design.md              ← endpoint catalog + GAP-NN
│   │   ├── 09-integration-plan.md         ← Phase 2 master playbook
│   │   ├── 10-product-catalog.md          ← Guides as product brochure
│   │   ├── 11-docs-coverage-matrix.md     ← Guides sweep × 8 agents
│   │   ├── 12-api-reference-coverage.md   ← Reference layer findings
│   │   ├── 13-docs-vs-partner-guide-delta.md  ← partner-doc reclassification
│   │   ├── README.md                      ← analysis index + reading order
│   │   └── decision-log.md                ← DEC-001..DEC-008
│   └── work/                              ← raw HTTP captures, scripts, batch logs
└── .claude/                               ← agents + slash commands used to build this
```

## Reading order

See `evidence/analysis/README.md`. Short version: start with **01-test-matrix.md** (108 tests), then **13-docs-vs-partner-guide-delta.md** (the partner-doc reclassification that drove this README's ranking), then the phase reports (03/04/05/06/07).

## Outreach to Kira

Questions surfaced from the evaluation, framed for @Diego (Eng) and @Nicolle (PD). Full list in `evidence/analysis/13-docs-vs-partner-guide-delta.md` § 6.

- **@Diego (Eng)** — base URL contradiction across public docs, partner guide, and runtime. The partner-distributed guide claims `/sandbox` prefix + pin endpoint unlocks the stage; revalidation on 2026-05-28 confirms the pin works only at no-prefix base and does not unlock the prefix. Is the prefix ever required, or is the entire guide and public-docs claim a documentation error?
- **@Diego (Eng)** — security disclosures (Findings #2, #3, #4) raised privately; awaiting acknowledgement before publishing reproduction details beyond what is necessary in this README.
- **@Diego (Eng)** — AiPrise vs SumSub server-side routing (partner guide L43-46). What's the routing rule? Region? Account tier?
- **@Nicolle (PD)** — the partner-distributed Postman collection (referenced 7× in the sandbox integration guide) is the canonical worked example; it is not on any public docs surface. How does a public-docs-only integrator (procurement-stage prospect) obtain it?
- **@Nicolle (PD)** — the 15-item Production Readiness Checklist (`kira-prod-certification-matrix.docx`) is the de facto test plan for partners. Can it be published publicly so prospects know the rubric before engaging Sales?
- **@Nicolle / @Diego** — Production Readiness Checklist item #14 (event de-dup): with no retry policy today (per partner guide L83), how does an integrator force a retry to demonstrate the de-dup property? Is there a sandbox endpoint to replay a webhook delivery on demand?

## Methodology details

- **Phase 1 — Documentation Quality.** Evaluated the public docs portal (`kira-financial-ai.readme.io`) across four pillars (Documentation Quality, Ease of Connection, Docs↔Runtime Congruence, Integration Hardening). Closed with 11 ranked findings in `03-phase-1-findings.md` + canonical GAP-NN inventory in `08-flow-design.md` § 6.
- **Phase 2 — Empirical Integration.** Probed 18 of 30 documented endpoints; captured per-endpoint iteration count to first 2xx, doc-sufficiency boolean, and every doc-vs-runtime drift in `04-integration-log.md`. Batches D and F (Virtual Accounts deposit simulation, Payouts) are blocked by DRIFT-23 (sandbox does not auto-approve verification).
- **Phase 3 — Adversarial Testing.** Three Python harnesses — load (`07-load-summary.md`), security (`05-security-audit.md`, OWASP API Top 10), abuse (`06-abuse-scenarios.md`, business-logic exploits). All findings are reproducible via the captures in `evidence/work/{security,abuse,automation}/`.
- **Partner-doc delta reclassification (2026-05-28).** After two partner-distributed Word docs (`kira-sandbox-integration-guide.docx`, `kira-prod-certification-matrix.docx`) became available, every prior finding was reclassified against them — yielding the META-finding (Top 5 #1) and 9 internal severity downgrades for findings the partner guide acknowledges with a documented workaround + scheduled fix. The 4 security findings (Top 5 #2-#4) remain unaddressed by either doc; the base-URL finding (Top 5 #5) is the only finding that both docs get wrong. Full reclassification in `13-docs-vs-partner-guide-delta.md`.
