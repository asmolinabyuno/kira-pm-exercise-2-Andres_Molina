# Decision Log — API Integration & Error Hunt

Registro de todas las decisiones tomadas durante el ejercicio, su contexto, opciones consideradas y cambios aplicados.

| Field | Description |
|---|---|
| **DEC-XXX** | Sequential decision ID |
| **Triggered by** | CMT-XXX or direct request that originated it |
| **Type** | DECISION (options weighed) / CORRECTION (straightforward fix) / ADDITION (new content) |

---

<!-- New decisions go below this line -->

## DEC-001 — Three-phase evaluation methodology adopted

- **Date:** 2026-05-27
- **Comment:** Primero me gustaria hacer primero validaciones de la documentacion y claridad de la documentacion. Esto es un GAP importante es la primera imagen. Antes de poderse integrar la documentacion es lo unico que se tiene para entender el producto y para inciar la integracion esto es lo unico que se tiene.
- **Type:** ADDITION
- **Interpretation:** Documentation evaluation must precede integration. Phase 1 of the project is dedicated to assessing documentation quality and clarity. Docs quality is a first-class finding category in its own right — not background — because docs are the integrator's only window into the product before any code is written.
- **What was added:** Phase 1 — Documentation Quality Evaluation. Comes BEFORE any empirical integration.
- **Applied to:**
  - [x] CLAUDE.md: added "Project Methodology — Three Phases" section
  - [x] Status mapping: Phase 1 substantially complete (`flow-design.md`, `docs-coverage-matrix.md`, `product-catalog.md`, `api-reference-coverage.md`). **Pending:** consolidated `evidence/analysis/03-phase-1-findings.md`.
- **Future impact:** Every finding maps back to the phase that surfaced it. Docs-quality findings stand alone — not just "context" for later technical findings. They can land in the README top-5 on their own merits.

## DEC-002 — Phase 2: per-endpoint integration with iteration-count + doc-sufficiency telemetry

- **Date:** 2026-05-27
- **Comment:** Me gustaria hacer integraciones con cada uno de los endpoints y validar la dificultad de cada integracion. Validarlo en cuantas iteraciones logramos hacer una integracion exitosa y si la documentacion fue suficiente para hacerla, algunas veces en las integraciones no se comportantan como lo dicen la documentacion. estoy hay que falgearlo como gap.
- **Type:** ADDITION
- **Interpretation:** Phase 2 is empirical integration with per-endpoint difficulty measurement. For each endpoint, the Data Engineer captures: (a) iteration count to first 2xx, (b) doc-sufficiency boolean (was the doc alone enough, or did we have to guess / escalate?), (c) every doc-vs-runtime drift, tagged `@docs-runtime-drift`.
- **What was added:** Phase 2 — Empirical Integration with Difficulty Telemetry. Each endpoint gets a difficulty score anchored in measurable data.
- **Applied to:**
  - [x] CLAUDE.md: documented in methodology section
  - [x] data-engineer.md: existing probe playbook already aligned. Will instrument iteration counts via new artifact `evidence/analysis/04-integration-log.md`.
- **Future impact:** "Iteration count to first success" and "doc-sufficiency rate" become measured KPIs per endpoint — not narrative. Any doc-vs-runtime drift is a tagged finding category.

## DEC-003 — Phase 3: stress / security / abuse testing via Python harnesses

- **Date:** 2026-05-27
- **Comment:** Una vez tengamos las integraciones hechas hagamos test de estres, seguridad y de abuso. Para esto tambien diseños los procesos en python para hacer las pruebas.
- **Type:** ADDITION
- **Interpretation:** Phase 3 — adversarial testing. Stress (load/latency), security (OWASP API Top 10), and abuse (business-logic exploits) testing. All driven by Python harnesses (pytest+httpx for security/abuse, k6/Locust for stress). Runs only after Phase 2 produces stable end-to-end integration.
- **What was added:** Phase 3 — Adversarial Testing. Python-based test harnesses for stress, security, and abuse.
- **Applied to:**
  - [x] CLAUDE.md: documented in methodology section
  - [x] Agents already aligned: `qa-engineer` (stress, k6/Locust), `api-security-auditor` (OWASP API Top 10), `api-functional-tester` (business-logic exploits), `data-engineer` (HTTP plumbing for harnesses).
- **Future impact:** Don't jump phases. Security tests against an unvalidated endpoint generate noise findings. Each Phase 3 harness must be reproducible via `python -m pytest` or `k6 run` from `evidence/work/{automation|security|abuse}/{slug}/`.

## DEC-004 — Phase 1 closeout: consolidated phase-1-findings.md

- **Date:** 2026-05-27
- **Comment:** Cerremos Phase 1 con el phase-1-findings.md con /proc_comment
- **Interpretation:** Consolidate the four Phase 1 source artifacts (`flow-design.md`, `docs-coverage-matrix.md`, `product-catalog.md`, `api-reference-coverage.md`) into one ranked deliverable: `evidence/analysis/03-phase-1-findings.md`. This is the closeout for Phase 1 and the docs-quality input to the README top-5.
- **Type:** ADDITION
- **Phase:** 1
- **Priority:** HIGH (unblocks README top-5 assembly and Phase 2 kickoff)
- **What was added:** `evidence/analysis/03-phase-1-findings.md` — top docs-quality findings ranked by integrator impact, each with severity / pillar / category / "why this matters to a client" / evidence anchors / README-top-5-candidate flag.
- **Owner agent(s):** `product-manager` (draft) → `devil-advocate` (review), channelled inside one general-purpose subagent.
- **Acceptance:** Document exists; contains 8-12 ranked findings; every finding cites its source artifact + section; pillar-tagged; severity-justified; devil-advocate review attached; README top-5 candidates explicitly flagged.
- **Applied to:**
  - [x] `evidence/analysis/03-phase-1-findings.md` (created)
  - [x] `CLAUDE.md` § Project Methodology — Phase 1 marked COMPLETE
  - [x] `evidence/work/comments.md` (cleared)
  - [x] `evidence/ai/prompt-log.md` (Prompt 5 added)
- **Future impact:** Phase 2 (empirical integration) can begin. Phase 2 findings will join Phase 1 findings in the final README top-5. Re-running `/proc_comment` on a comment that *adds* a Phase 1 finding requires updating both `phase-1-findings.md` and the README top-5 candidates.

## DEC-005 — GAP-NN numbering collision across Phase 1 artifacts (follow-up from DEC-004 cross-validation)

- **Date:** 2026-05-27
- **Triggered by:** DEC-004 closeout — agent flagged numbering collisions during consolidation
- **Type:** CORRECTION
- **Phase:** 1 (cleanup before Phase 2 starts)
- **Priority:** HIGH (cross-artifact citations break without reconciliation)
- **Issue:** GAP numbers collide across the three artifacts produced after `flow-design.md`:
  - `docs-coverage-matrix.md` proposes **GAP-29** for "api-upgrades 404"
  - `api-reference-coverage.md` independently uses **GAP-29** for "Quotations Reference hidden from llms.txt" and continues with GAP-30/31/32/33/34
  - `product-catalog.md` proposes **GAP-31** for "Wallets without reference page", colliding with `api-reference-coverage.md`'s GAP-31 (Quotations)
- **Change:** Data-architect must reconcile into `flow-design.md` § 6 as the canonical authority. Each later artifact's "proposed GAP-NN" must be renamed to its assigned canonical number (or stay if non-colliding) and back-references in `phase-1-findings.md` updated accordingly.
- **Applied to (pending):**
  - [ ] `flow-design.md` § 6 — canonical numbering with all post-Phase-1-sweep gaps assigned
  - [ ] `docs-coverage-matrix.md` — rename collisions
  - [ ] `product-catalog.md` — rename collisions
  - [ ] `api-reference-coverage.md` — rename collisions
  - [ ] `phase-1-findings.md` — update back-references after canonical assignment
- **Owner agent:** `data-architect` (owns `flow-design.md`)
- **Future impact:** From Phase 2 onward, **only `data-architect` assigns new GAP-NN numbers**, via updates to `flow-design.md` § 6. Other artifacts cite assigned numbers; they don't propose new ones unilaterally.

## DEC-006 — Phase 2 master integration plan + webhook architecture decision

- **Date:** 2026-05-27
- **Comment:** Hagamos el plan de integracion con todos los endpoints y validemos si tenemos que construir webhook para recibir la respuestas de algunos endpoints.
- **Interpretation:** Produce ONE master document covering: (a) execution plan for all 30 endpoints with prerequisites, dependency chains, sync/async classification, and per-endpoint probe set; (b) webhook architecture decision — which Kira events do we need to receive, can polling fallback cover us, do we stand up the FastAPI receiver in Phase 2 or defer to Phase 3.
- **Type:** DESIGN
- **Phase:** 2
- **Priority:** HIGH (master playbook for the remaining 28 endpoints + Phase 2→3 handoff)
- **Owner agent(s):** `data-architect` (primary). Channel `data-engineer` mindset for feasibility notes on webhook reception, but architect drives.
- **Test category:** functional + state-machine coverage + probe-mutation planning
- **Design target artifact:** `evidence/analysis/09-integration-plan.md` (NEW)
- **Depends on:** `flow-design.md` (endpoint catalogue + state machines), `integration-log.md` (current empirical evidence: 2/30 endpoints), `phase-1-findings.md` (gap-prioritization inputs)
- **Acceptance:**
  - All 30 endpoints listed with prerequisites and execution order (batched)
  - Sync vs async classified per endpoint
  - Webhook events catalogued with trigger-endpoint mapping
  - Binary decision: webhook receiver YES / NO + rationale + cost of skipping
  - Per-endpoint probe checklist embedded (functional, header-mutation, idempotency-replay, ISO 3166, concurrency, error UX, security-precondition)
  - Phase 2 → Phase 3 handoff section: which endpoints are pre-cleared for adversarial testing
- **Applied to (pending):**
  - [ ] `evidence/analysis/09-integration-plan.md` (NEW)
  - [ ] `CLAUDE.md` § Repo Structure (add the new file to the tree)
  - [ ] `evidence/work/comments.md` (clear)
  - [ ] `evidence/ai/prompt-log.md` (Prompt 6)
- **Future impact:** Becomes the playbook for remaining Phase 2 work. Each subsequent endpoint probe (e.g., POST /v1/recipients, POST /v1/payouts) follows the plan's execution batch. The webhook decision unblocks Phase 3 adversarial testing of webhook delivery semantics (GAP-11). Subsequent `/proc_comment` invocations of the form "next Phase 2 batch" can dispatch agents directly from the plan without re-planning.

## DEC-007 — Folder reorg: promote 12 analysis docs to `evidence/analysis/`

- **Date:** 2026-05-28
- **Comment:** Antes de continuar organicemos los folders y dejemos los analisis de mas valor afuera.
- **Interpretation:** Surface the 12 highest-value analysis docs (plus decision-log) by promoting them out of the saturated `evidence/work/` directory into a new sibling `evidence/analysis/` with numbered prefixes for sort order. Keep supporting evidence (per-call JSONs, harness scripts, batch logs, probe scripts) in `evidence/work/`.
- **Type:** ADDITION
- **Phase:** Cross-phase (project hygiene)
- **What was added:** New `evidence/analysis/` directory with 13 numbered docs + an index README.
- **Files moved (13):**
  - `evidence/work/test-matrix.md` → `evidence/analysis/01-test-matrix.md`
  - `evidence/work/test-coverage-heatmap.md` → `evidence/analysis/02-test-coverage-heatmap.md`
  - `evidence/work/phase-1-findings.md` → `evidence/analysis/03-phase-1-findings.md`
  - `evidence/work/integration-log.md` → `evidence/analysis/04-integration-log.md`
  - `evidence/work/security-audit.md` → `evidence/analysis/05-security-audit.md`
  - `evidence/work/abuse-scenarios.md` → `evidence/analysis/06-abuse-scenarios.md`
  - `evidence/work/automation/load/load-summary.md` → `evidence/analysis/07-load-summary.md`
  - `evidence/work/flow-design.md` → `evidence/analysis/08-flow-design.md`
  - `evidence/work/integration-plan.md` → `evidence/analysis/09-integration-plan.md`
  - `evidence/work/product-catalog.md` → `evidence/analysis/10-product-catalog.md`
  - `evidence/work/docs-coverage-matrix.md` → `evidence/analysis/11-docs-coverage-matrix.md`
  - `evidence/work/api-reference-coverage.md` → `evidence/analysis/12-api-reference-coverage.md`
  - `evidence/work/decision-log.md` → `evidence/analysis/decision-log.md`
- **Files updated for references (24):** `CLAUDE.md`, `.claude/commands/proc_comment.md`, 8 agent files in `.claude/agents/` (api-functional-tester, api-security-auditor, data-architect, data-engineer, devil-advocate, fullstack-integrations-specialist, product-manager, qa-engineer), 8 of the 13 moved analysis docs (cross-refs that needed substitution: 01, 03, 05, 06, 10, 11, 12, decision-log), `evidence/ai/prompt-log.md`, and 5 batch logs in `evidence/work/integration-log-batch-{A,B,C,E,G}.md`. README.md was inspected and had no qualifying references.
- **Applied to:**
  - [x] 13 files moved
  - [x] Internal references updated across the repo (24 files, all 13 path substitutions applied where applicable)
  - [x] `evidence/analysis/README.md` index created
  - [x] Prompt 8 logged
- **Future impact:**
  - **New rule:** any future high-value analysis doc goes to `evidence/analysis/` with next numerical prefix
  - Supporting evidence (per-call JSONs, harnesses, scripts) stays in `evidence/work/`
  - Cross-referencing rule: `cross_ref` column's last link in `01-test-matrix.md` must point to the source-of-truth doc
  - When a doc moves, `git mv` + grep-and-update all references in one batch

## DEC-008 — README top-5 finalized; severity adjustments per partner-docs delta

- **Date:** 2026-05-28
- **Trigger:** Delta analysis (`evidence/analysis/13-docs-vs-partner-guide-delta.md`) + DRIFT-1 revalidation (2026-05-28 partner-guide pin-flow probe in `evidence/work/versioning/`)
- **Type:** REFINE
- **Phase:** Cross-phase (closeout)
- **Priority:** CRITICAL (this is the public deliverable)
- **What changed:**
  - `README.md` final top-5 published:
    1. META-finding — Public docs materially incomplete; real contract is partner-distributed (CRITICAL)
    2. Webhook subsystem triple-vector — SSRF + cross-tenant client_uuid + optional secret + cleartext URL + opaque response (CRITICAL, CVSS 9.1)
    3. PII unmasked across /v1/users and /v1/recipients — SSN, document_number, CLABE, routing, IBAN, wallet plaintext (CRITICAL)
    4. TLS 1.0 and TLS 1.1 accepted on api.balampay.com:443 (CRITICAL)
    5. /sandbox base URL wrong everywhere; partner guide also directs to broken URL — DRIFT-1 + DRIFT-1b + DRIFT-1c compound (CRITICAL)
  - `01-test-matrix.md`:
    - 11 rows REFINED with severity adjustments (Bucket B downgrades + Bucket A reframings): T-P1-003 (CRITICAL→HIGH), T-P1-005 (reframe only, HIGH holds), T-P2-DRIFT-6 (CRITICAL→HIGH), T-P2-DRIFT-11 (HIGH→MEDIUM), T-P2-DRIFT-19 (HIGH→MEDIUM), T-P2-DRIFT-23 (CRITICAL→HIGH), T-P2-DRIFT-26 (HIGH→MEDIUM), T-P2-DRIFT-27 (HIGH→MEDIUM), T-P2-DRIFT-32 (HIGH→MEDIUM), T-P2-DRIFT-33 (HIGH→MEDIUM), T-P2-DRIFT-35 (HIGH→MEDIUM), T-P2-DRIFT-40 (CRITICAL→HIGH), T-P2-DRIFT-52 (MEDIUM→LOW)
    - T-P2-DRIFT-1 row updated with the 2026-05-28 revalidation annotation and reference to DRIFT-1b/-1c sub-findings
    - 4 new rows added: T-P2-DRIFT-54 (DRIFT-1b, CRITICAL), T-P2-DRIFT-55 (DRIFT-1c, CRITICAL), T-P2-DRIFT-56 (GAP-22b, HIGH, BLOCKED-ENV), T-P1-META-01 (META-finding, CRITICAL)
    - Dashboard counts updated: total 108 → 112 rows; CRITICAL=14, HIGH=40, MEDIUM=23, LOW=12, N/A=23
  - `03-phase-1-findings.md`:
    - Added "Postscript — Partner-Doc Delta Analysis Impact" section reframing Findings #1-#11 against the partner-doc reclassification
    - Documents the META-finding subsuming most Phase 1 top-5 candidates
    - Notes Finding #5 (Wallets) reframe per Bucket A (inverse-invalidation: partner doc also omits Wallets, confirming product-truth gap)
- **Rationale:** Two partner-distributed Word docs (`kira-sandbox-integration-guide.docx`, `kira-prod-certification-matrix.docx`) materially alter the framing of ~22 of our 53 drifts as "known issues with documented workarounds + scheduled fix dates" rather than CRITICAL API bugs. The 4 security findings (F1+ABUSE-4 SSRF/cross-tenant, F2+F3 PII unmasked, F4 TLS) remain unaddressed by either doc and become the natural top-5 anchors after the META-finding. DRIFT-1 was revalidated 2026-05-28 against the partner-guide pin flow and CONFIRMED — the partner guide is wrong about the `/sandbox` prefix on every URL it lists, so DRIFT-1 stands even for a partner-doc-equipped integrator. This drove the new DRIFT-1b/-1c sub-findings and the compound DRIFT-1 top-5 entry.
- **Validated by:** delta-doc analysis (`13-docs-vs-partner-guide-delta.md` § 3-4) + DRIFT-1 revalidation empirical confirmation (`evidence/work/versioning/01..06-*.json`) + dashboard recount (CRITICAL=14, HIGH=40, MEDIUM=23, LOW=12, N/A=23, total=112).
- **Future impact:** README top-5 ranked and publishable. `.feature` files per finding pending as the next-step deliverable. Test-matrix downgrades represent partner-side severity; public-doc severity stays at the pre-REFINE value for findings where Public-doc reader still hits the gap (META-finding caries that load). When v2026-XX-XX ships (end-of-June per partner guide), the downgraded rows should be re-evaluated against the actual release notes and re-synced.
- **Open follow-up items flagged for future passes:**
  - 10 outreach questions to @Diego / @Nicolle (`13-docs-vs-partner-guide-delta.md` § 6) — not yet sent
  - 25 Bucket E capabilities/quirks the partner doc reveals that we did not probe (`13-docs-vs-partner-guide-delta.md` § 1 Bucket E) — candidates for a Phase 2.5 extension
  - Postman collection referenced 7× in partner guide is not in our possession — request to @Nicolle
  - `.feature` files for top-5 + honorable mentions are pending (called out in README as TBD)
