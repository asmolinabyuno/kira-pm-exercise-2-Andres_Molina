# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working in this repository.

## Project Overview

PM exercise for Kira: **API Integration & Error Hunt**. Integrate the Kira sandbox end-to-end (customer → KYB → virtual account → inbound deposit → payout), capture every request/response, find the top 5 errors ranked by *integrator impact*, and write a Gherkin `.feature` file for each.

Grading rubric: Prioritization 40%, Specificity 30%, Integration depth 20%, Communication 10%.

## Project Methodology — Three Phases (per DEC-001, DEC-002, DEC-003)

Work proceeds in **three sequential phases**. Findings are categorized by which phase surfaced them. **Don't jump phases** — premature security testing on un-validated endpoints generates noise.

### Phase 1 — Documentation Quality Evaluation
Before any integration, evaluate documentation quality and clarity as the *primary* integrator experience. The docs are the only thing an integrator has on day zero. **Docs-quality gaps are first-class findings**, not background context.

Status: **COMPLETE** (closed 2026-05-27 via DEC-004). Artifacts:
- `evidence/analysis/08-flow-design.md` — endpoint catalog extracted from docs (929 lines, 30 endpoints, 28+ gaps)
- `evidence/analysis/11-docs-coverage-matrix.md` — Guides sweep × 8 agents (sections × per-agent net-new probes)
- `evidence/analysis/10-product-catalog.md` — Guides as product brochure + API contrast (9 products, 3 dead sidebar entries, "Wallets has no reference page" finding)
- `evidence/analysis/12-api-reference-coverage.md` — API Reference layer sweep (62 net-new probes; GAP-30/31/32 added)
- **`evidence/analysis/03-phase-1-findings.md`** — consolidated, ranked deliverable (11 findings: 4 CRITICAL + 7 HIGH; 4 confirmed README top-5 candidates, slot 5 contested pending Phase 2). Includes devil-advocate review notes and Phase 1 → Phase 2 handoff probes.

**Open follow-up (DEC-005):** GAP-NN numbering collisions across `docs-coverage-matrix.md`, `product-catalog.md`, and `api-reference-coverage.md` — the data-architect must reconcile into `flow-design.md` § 6 before Phase 2 starts.

### Phase 2 — Empirical Integration with Difficulty Telemetry
Integrate against every endpoint. For each, capture:
- Iteration count to first 2xx
- Doc-sufficiency boolean (was the doc alone enough?)
- Doc-vs-runtime drift events (every contradiction → tagged `@docs-runtime-drift`)
- Latency baseline (p50/p95/p99)

Status: **IN PROGRESS — 18 / 30 endpoints** probed (auth + /v1/users + Batches A/B/C/E/G done 2026-05-27; **53 drift events** captured; Batches D and F blocked pending DRIFT-B10 resolution — sandbox not auto-approving users).

**Lead:** `data-engineer`. Outputs: `evidence/analysis/04-integration-log.md` (the difficulty ledger) + per-call evidence under `evidence/work/{step}/*.json` + `evidence/work/latency/*.json`.

### Phase 3 — Adversarial Testing via Python Harnesses
Runs *after* Phase 2 produces a stable end-to-end integration. Three Python harnesses:
- **Stress / load** (`qa-engineer`, k6/Locust): latency under load, `429` behavior, sustained throughput, recovery curves
- **Security** (`api-security-auditor`): OWASP API Top 10 — BOLA, mass assignment, JWT, SSRF (esp. webhook-register), injection, TLS, info leakage
- **Abuse** (`api-functional-tester`): business-logic exploits — state-machine bypass, races, refund-after-transfer, KYB skip, currency rounding, webhook spoof

Status: **not started**. Test categories already designed in agent personas; Python harnesses pending.

**Outputs:** `evidence/work/automation/{slug}/` (stress), `evidence/work/security/{slug}/` (security), `evidence/work/abuse/{slug}/` (abuse). Each reproducible via `python -m pytest` or `k6 run`.

## About Kira

Kira (kirafin.ai) — fintech infrastructure platform. Unified API for embedded financial products powered by stablecoins and AI agents. Founded by Edrizio De La Cruz (ex-Arcus/Mastercard), Beto Díaz (ex-Clip/Stori), Camilo Jiménez (ex-Littio). $6.7M seed (Blockchange, Vamos, Stellar), $3M first-year revenue. Built on Stellar blockchain, backed by 4 FDIC-insured US partner banks. Real clients: Banco Industrial, Banco N1co, Factil, Shield, Borderless, Suku, Vank, AU.

**Three product lines you'll integrate against:**
1. **Virtual USD Accounts** — FDIC-insured. Inbound rails: FedNow, RTP, ACH (same-day/standard), Wire (domestic/international).
2. **On-Ramps** — USD → USDT/USDC. Volume-tiered pricing.
3. **Off-Ramps** — USDT/USDC → USD (including SWIFT). Volume-tiered pricing.

Kira does NOT do fiat-to-fiat (e.g., USD → MXN). Anything implying that is a data issue.

## Integration Target

- **Docs portal:** https://kira-financial-ai.readme.io/v2026-04-14/docs/kira-api-overview
- **API reference:** https://kira-financial-ai.readme.io/v2026-04-14/reference
- **Sandbox base URL:** Docs claim `https://api.balampay.com/sandbox` but **runtime proves the docs are wrong across the entire API** (confirmed on `/auth` AND `/v1/users` — see DRIFT-1 in `evidence/analysis/04-integration-log.md`). The working base for every endpoint is `https://api.balampay.com` (no `/sandbox` prefix). `/sandbox/auth` returns 403 ForbiddenException; `/sandbox/v1/users` returns 401 UnauthorizedException (gateway-layer error type inconsistency is its own minor finding). `.env` `KIRA_API_BASE_URL` reflects the working value. **Revalidated 2026-05-28** against the partner-distributed `kira-sandbox-integration-guide.docx` (which insists the prefix is required and claims a one-time `POST /v1/versioning/upgrade` "pin" call unlocks it): the pin endpoint works **at the no-prefix base only**, and after a successful pin the `/sandbox/*` tree still returns the same 403/401 envelopes (`evidence/work/versioning/`). DRIFT-1 stands — see DRIFT-1 "Revalidation 2026-05-28" note.
- **Auth endpoint:** `POST /auth` — body `{ "client_id", "password" }` → returns JWT Bearer in `{ message, data: { access_token, expires_in: 3600, token_type: "Bearer" } }` envelope
- **Credentials:** loaded from `.env` (gitignored)
  - `KIRA_CLIENT_ID` → request body `client_id`
  - `KIRA_COGNITO_SECRET` → request body `password`
  - `KIRA_API_KEY` → header `x-api-key`

## Required Headers (from docs)

- `x-api-key` — required on ALL endpoints
- `Authorization: Bearer <token>` — required on all endpoints except `/auth`
- `x-validation-header` — required on some sensitive operations (e.g., fiat payouts with OTP)
- `Idempotency-Key` — required on specific create operations (recipient creation, verification initiation)
- **No documented version header** at the API level. Version lives in the docs URL path (`v2026-04-14`) but not in request headers — this is a candidate finding.

## Minimum Integration Flow (to drive findings)

```
1. POST /auth                           → JWT
2. POST /customers                      → customer_id
3. POST /customers/{id}/kyb             → kyb_submission_id, status=PENDING
   (poll or webhook)                    → APPROVED|REJECTED
4. POST /virtual-accounts               → va_id
5. simulate inbound deposit (sandbox)   → balance update
6. POST /payouts                        → payout_id, status=PENDING
```

Exact endpoint paths above are placeholders — verify against the docs and capture the real shape.

## Key Rules

- **Never commit secrets.** `.env` is gitignored. Redact bearer tokens and API keys in any committed request/response evidence.
- **One call per evidence file.** Path: `evidence/work/{step}/{NN}-{outcome}.json`. Easier to reference from `.feature` files.
- **Every finding needs evidence.** A README finding with no raw HTTP capture is not a finding.
- **Specificity bar for Gherkin** — every `Then` must assert something observable from the response (status code, header value, JSON path). No "should be correct" steps.
- **Severity ↔ ranking** — README order must reflect severity (CRITICAL → HIGH → MEDIUM → LOW). If a severity changes, re-check the rank.
- **Outreach is graded.** Flag what to ask @Nicolle (PD) or @Diego (Eng) explicitly. Silent guessing loses points.
- **Bias toward integrator-invisible gaps** — undocumented fields, missing version headers, vague error bodies, enum mismatches, no idempotency guidance, sandbox-prod drift. Cosmetic doc typos are not findings.

## Decision-Making

- Decision log: `evidence/analysis/decision-log.md` — every meaningful decision gets a DEC-XXX entry
- Comment inbox: `evidence/work/comments.md` — processed via `/proc_comment` slash command
- Prompt log: `evidence/ai/prompt-log.md` — every prompt logged in Spanish + English (grading requirement)

## Agents

Specialized agents live in `.claude/agents/`. Launch them via the Task tool. The team is an **API evaluation crew** — every agent's job is to assess Kira's API across the four pillars: documentation quality, ease of connection, docs↔runtime congruence, and integration hardening (functional + performance + abuse + security).

| Agent | Expertise | Use for |
|---|---|---|
| `product-manager` | API quality evaluation, four-pillar scoring, integrator-experience PM | Top-5 ranking, README, pillar scoring, BDD direction, outreach decisions |
| `data-architect` | Integration strategy + test topology + flow contracts | Owns `flow-design.md`; produces `test-topology.md`; maps endpoint × category × owner |
| `data-engineer` | API integration consumer + raw HTTP capture + measurement | HTTP plumbing, auth wiring, webhook receiver, latency baselines, evidence files |
| `fullstack-integrations-specialist` | Full-stack integration patterns (hosted pages, payment links, SDKs, iframe/CSP, serverless webhook receivers, multi-tenant SaaS patterns) | Frontend & full-stack findings the Data Engineer would miss with raw HTTP |
| `qa-engineer` | API test automation: BDD/Gherkin + contract (Schemathesis/Pact) + load (k6/Locust) + property-based | One `.feature` per finding + runnable automation backing it |
| `api-functional-tester` | **Fraud, abuse, business-logic exploits** — state-machine bypass, races, refund-after-transfer, KYB skip, rounding exploits | `evidence/analysis/06-abuse-scenarios.md` and `evidence/work/abuse/{slug}/` |
| `api-security-auditor` | **OWASP API Top 10 + pentest** — BOLA, mass assignment, JWT attacks, SSRF, injection, TLS, info leakage | `evidence/analysis/05-security-audit.md` and `evidence/work/security/{slug}/` |
| `devil-advocate` | Critical reviewer across all categories | Final pass — prioritization defensible, specificity bar met, severities calibrated |

**Role overlap rules:**
- `api-functional-tester` finds *intent bypass* (logic the API legitimately allows). `api-security-auditor` finds *security bypass* (controls that should block but don't). Where they overlap (e.g., BOLA), they pair: functional writes the abuse scenario, security writes the OWASP-mapped finding.
- `data-engineer` measures raw HTTP. `fullstack-integrations-specialist` measures hosted pages, SDKs, redirect flows, embedded widgets. They split on whether the probe is HTTP-level or UI/full-stack-level.
- `qa-engineer` Gherkinizes & automates findings from all other agents — they don't design abuse or security scenarios themselves, they turn them into runnable tests.

## Repo Structure

```
.
├── README.md                    ← top 5 findings, ranked
├── CLAUDE.md                    ← this file
├── Exercise 2 — Brief.md        ← the brief
├── .env                         ← credentials (gitignored)
├── .gitignore
├── features/                    ← one .feature file per finding
├── evidence/
│   ├── ai/
│   │   └── prompt-log.md        ← all prompts ES+EN
│   └── work/                    ← raw HTTP captures, scripts, analysis
│       ├── comments.md          ← /proc_comment inbox
│       ├── decision-log.md      ← DEC-XXX entries
│       ├── flow-design.md       ← data-architect's integration reference (30 endpoints, 28 gaps)
│       ├── test-topology.md     ← endpoint × test-category × owner matrix
│       ├── pillar-scores.md     ← PM's four-pillar evaluation scores
│       ├── observations.md      ← engineer's running notes
│       ├── fullstack-evaluation.md ← hosted pages, payment links, SDK evaluation
│       ├── abuse-scenarios.md   ← functional-tester's exploit catalogue
│       ├── abuse/{slug}/        ← reproducible abuse scenarios
│       ├── security-audit.md    ← security-auditor's OWASP mapping
│       ├── security/{slug}/     ← reproducible security findings
│       ├── automation/{slug}/   ← QA's runnable automation backing each .feature
│       ├── latency/             ← per-endpoint p50/p95/p99 baselines
│       ├── webhooks/            ← captured Kira sandbox deliveries
│       └── {step}/*.json        ← raw request/response captures per call
└── .claude/
    ├── agents/                  ← specialized agent definitions
    └── commands/
        └── proc_comment.md      ← /proc_comment slash command
```

## Deliverable

Public GitHub repo `kira-pm-exercise-2-<name>` containing all of the above. Drop the link in Slack by EOD Thursday.
