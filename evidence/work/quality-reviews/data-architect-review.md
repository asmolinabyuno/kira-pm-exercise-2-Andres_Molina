# Data Architect Quality Review

**Reviewer persona:** data-architect (integration strategy + flow contracts + test topology owner)
**Scope:** `08-flow-design.md` · `09-integration-plan.md` · `02-test-coverage-heatmap.md` · cross-cutting consistency
**Date:** 2026-05-28

---

## What's strong

- **GAP-NN canonical numbering is intact and well-disciplined.** Flow-design §6 defines exactly 37 sequential canonical GAPs (GAP-01 → GAP-37), plus the GAP-22a/22b split documented inline. The DEC-005 renumber map in §6 ("Renumbering reconciliation") explicitly resolves all three collision sources (api-reference-coverage, docs-coverage-matrix, product-catalog) with a clear rationale and a "data-architect is the only assigner from now on" rule that is being honored downstream (no rogue numbers appear in 01/02/03/04/06/07/09/13).
- **State machines are coherent and architecturally honest.** §5.2 (User Verification), §5.3 (VA), §5.4 (Payout) each name the transitions, mark the integrator-visible illegal ones, cite the source GAP for missing endpoints (GAP-27 close-VA, GAP-28 cancel-payout), and call out the empirical drift in payout casing (GAP-19 — `returned`/`pending` lowercase missing from detail schema).
- **Cross-cutting contracts §2 are dense and accurate.** Three error envelopes (Shape A flat / B nested / C Pydantic) with example payloads; idempotency endpoint discrepancy (7 documented vs 9 empirically required) cited with the changelog as source; pagination shape inconsistency between offset (users/VAs) and page-based (payouts) explicitly catalogued.
- **GAP-22 revalidation is properly journaled.** The 2026-05-28 entry inside the GAP-22 bullet narrates the partner-distributed doc disclosure, both probe outcomes (no-prefix 403 SigV4 leak vs `/sandbox` prefix 401 UnauthorizedException), the renaming recommendation (22a public-docs gap / 22b sandbox routing inconsistency), and the cross-link to DRIFT-1/DRIFT-2. T-P2-DRIFT-56 in `01-test-matrix.md` carries this through faithfully.
- **Integration plan's webhook decision is well-argued.** §5.1–5.4 catalog every documented webhook event with poll alternative, cost in sandbox (0.2 rps peak vs 10 rps budget), and the binary verdict ("NO" for Phase 2 + Phase-3 escalation plan). The reasoning treats GAP-11 as an adversarial-test target, not a Phase-2 plumbing assumption — that's architecturally sound.
- **Heatmap family taxonomy is consistent with flow-design §3.** All 11 §3 sub-sections appear as rows, plus §2.7 Webhooks and a Cross-cutting row, explicitly explained at the top of the doc. Cell counts (117) match (13 × 9). Blocked cells consistently cite DRIFT-23 (sandbox no auto-approve) or DRIFT-45 (sandbox fee profiles ≥100%) as the named blocker.

---

## What needs fixing — BLOCKING

### B1. `08-flow-design.md` § 2.7 / § 2.2 / § 3.11 / GAP-04 — webhook auth model contradicts confirmed runtime (DRIFT-49)

- **File:** `evidence/analysis/08-flow-design.md` lines 61, 120, 124, 222, 561, 789, and Recipe F line 649
- **What:** Flow-design states `POST /webhooks/register` requires `x-api-key` only and **no Bearer token** — this is the original docs claim and is repeated as architectural fact in five places. **DRIFT-49 (REPRODUCED, REFERENCED in 04-integration-log.md line 425, and in heatmap row "Webhooks × Connection ✓ 1 (H, DRIFT-49)") inverts this:** both headers are required at runtime; `x-api-key` alone returns 401. The heatmap, integration-log, and test-matrix all reflect DRIFT-49; flow-design does not.
- **Fix:** Annotate § 2.2 row, § 2.7 paragraph, § 3.11 row, GAP-04 commentary, and Recipe F step 1 with "**Revalidated 2026-05-28 — DRIFT-49 INVERTS this: both `x-api-key` AND `Authorization: Bearer` required at runtime; `x-api-key` alone returns 401.**" GAP-04 itself should be re-pointed: webhooks is no longer the "API-key-only" exemplar, it's an additional contradiction.

### B2. `08-flow-design.md` — orphan `GAP-14a` proposed in 12-api-reference-coverage.md never reconciled

- **File:** `evidence/analysis/08-flow-design.md` §6 (Async state machines block) — missing entry
- **What:** `12-api-reference-coverage.md` line 84 proposes "**GAP-14a** sub-gap: list-endpoint filter exposes a *different* enum than the resource model. An integrator filtering by `verification_status=verified` … hits a 400." DEC-005 says only the data-architect assigns canonical numbers, but GAP-14a never made it into flow-design §6 or the renumber map. It is an orphan citation.
- **Fix:** Either (a) elevate to a canonical GAP-38 (or GAP-14a as a documented sub-gap) and add a §6 entry; or (b) explicitly fold the finding into GAP-14's body and update `12-api-reference-coverage.md` line 84 to cite GAP-14 (no `a` suffix). Decision must be journaled in the §6 reconciliation table so it does not regress.

### B3. `09-integration-plan.md` — GAP-22 references stale; never refreshed to GAP-22a/22b post-revalidation

- **File:** `evidence/analysis/09-integration-plan.md` lines 79, 115, 360, 400, 423, 425, 612, 624, 688, 709
- **What:** Integration plan was written 2026-05-27 with "GAP-22 (sandbox deposit simulation undocumented — Batch D might fail at deposit step)". The 2026-05-28 partner-guide revalidation produced the GAP-22a / GAP-22b split (flow-design §6 GAP-22 bullet documents this; T-P2-DRIFT-56 carries it). Integration-plan still says "GAP-22 (sandbox deposit simulation undocumented)" — that framing is now empirically wrong. The endpoint exists, only the auth model fails.
- **Fix:** Update every GAP-22 mention in integration-plan to "GAP-22a/22b" with a single-sentence rewrite: "Endpoint exists per partner guide but is not reachable on either base URL with our auth model — see DRIFT-1c / T-P2-DRIFT-56." Batch D's "🚫 blocked" status should explicitly cite DRIFT-23 (sandbox no auto-approve) **and** GAP-22b (simulate-deposit route 401/403), not just GAP-22.

### B4. `09-integration-plan.md` § 8 — open architectural questions list is now partly resolved but not marked

- **File:** `evidence/analysis/09-integration-plan.md` lines 707–714
- **What:** Question #2 ("GAP-22 — is there an undocumented `POST /sandbox/simulate-deposit`?") has been answered by the partner-guide revalidation (yes, at the `/sandbox` prefix, but 401). Question #3 ("GAP-31 canonical schema") is resolved per 04-integration-log.md line 491 ("GAP-31 RESOLVED. Canonical schema: REFERENCE (with extensions)."). Question #5 (OTP endpoint `/verification/send`) is resolved per DRIFT-21. Reader of the plan would think these are still open. Cross-doc reality drift.
- **Fix:** Re-stamp § 8 with `[RESOLVED 2026-05-28 — see DRIFT-X / GAP-22b / DEC-008]` annotations against questions 2, 3, 5. Or add a "Resolution status" column to the list.

---

## What should improve — SHOULD-FIX

### S1. `08-flow-design.md` Last-verified stamp lagging behind empirical reality

Line 5 says "Last verified: 2026-05-27." Every empirical revalidation since (DRIFT-1 partner-guide pin probe, GAP-22a/22b split, DRIFT-23/45 documented in integration-log) makes flow-design's bare-text claims drift further. Either bump the timestamp to 2026-05-28 with a "revalidated against partner guide" note, OR add a "Empirical revalidation log" sub-section at the top with a 5–6 line summary of what changed since 2026-05-27 and pointers to the relevant DRIFT-IDs.

### S2. `09-integration-plan.md` § 7 handoff table — endpoint reality drifted

- POST /v1/quotations is listed "BLOCKED on GAP-31 disambiguation" but GAP-31 was empirically resolved (Reference schema is canonical). The actual blocker is now DRIFT-45 (fee profiles ≥100%). The plan still labels this BLOCKED for the wrong reason.
- POST /webhooks/register is "yes (spoof priority)" for abuse, "TOP PRIORITY (Finding #4)" for security — but the plan was drafted before ABUSE-4 and Finding-#2 (README) confirmed that priority was right and SSRF is reachable end-to-end. Should reference DRIFT-47..53 + SEC-Finding-1 + ABUSE-4 explicitly.

### S3. `02-test-coverage-heatmap.md` — `SEC-F<N>` naming doesn't match `05-security-audit.md`'s `Finding <N>`

Heatmap line 65: "SEC-F1 (P3-Security)", "SEC-F4/F7/F8" (line 68), "SEC-F2, SEC-F3" (line 69). The security audit doc uses bare "Finding 1", "Finding 2", … (lines 29, 48, 66, 85, 102, 119, 134, 147, 158). Findings resolve by ordinal so a careful reader can map, but the prefix differs. Either re-prefix the audit doc's headings to `SEC-F<N>` (preferred, mirrors the ABUSE-N convention in `06-abuse-scenarios.md`) or rewrite the heatmap mentions to "Finding 1 (security audit)".

### S4. `08-flow-design.md` § 1.1 Base URLs row is contradicted by repo's `.env` + DRIFT-1

Section 1.1 says sandbox base = `https://api.balampay.com/sandbox`. CLAUDE.md explicitly states "the working base for every endpoint is `https://api.balampay.com` (no `/sandbox` prefix)" and the README ranks this as the #5 finding (CRITICAL). The architect's prose in § 1.1 should be updated to "Documented base: `…/sandbox` — runtime base: `https://api.balampay.com` (no prefix), see DRIFT-1 / DRIFT-1b / DRIFT-1c." Right now the doc reads as if the sandbox prefix is correct.

### S5. Renumber map in §6 is missing the GAP-22a/22b split

DEC-005 renumber table (lines 862–874) maps the three colliding artifacts to canonical numbers. The subsequent GAP-22a/22b split (2026-05-28) is documented inside the GAP-22 bullet but is **not** added as a row in the renumber table. For traceability, add: "GAP-22 → split into GAP-22a (public docs gap) + GAP-22b (sandbox routing inconsistency) — 2026-05-28 revalidation." This makes the §6 table the single source of truth for "what does this number mean today."

### S6. `02-test-coverage-heatmap.md` Concurrency-column comment is partly wrong

Line 53 says "only Recipients (✓ clean via ABUSE-8) tested." Recipients row in the table shows `Concurrency: ✓ clean` (correct). But Webhooks row shows `Concurrency: ✗` — which is true that no race-test was run, yet DRIFT-50 (idempotency silently ignored on webhooks/register) and ABUSE-4 (cross-tenant client_uuid) effectively constitute concurrency-adjacent abuse. Worth re-classifying one cell, or adding a note that "no race test was needed — uniqueness/locking is absent by construction."

---

## Cross-cutting contradictions found

### X1. Webhook auth model: flow-design vs runtime

- **08-flow-design.md says:** `POST /webhooks/register` — `x-api-key` only, no Bearer (lines 61, 120, 124, 222, 561, 789, 649). Listed as the canonical exemplar of GAP-04's "Bearer OR API key" mode.
- **04-integration-log.md DRIFT-49 (CONFIRMED REPRODUCED) says:** both `x-api-key` AND `Authorization: Bearer` required; `x-api-key` alone returns 401 on `/webhooks/register`.
- **02-test-coverage-heatmap.md row 23 says:** `Connection: ✓ 1 (H, DRIFT-49)` — empirical reality.
- **README.md & 01-test-matrix.md T-P2-DRIFT-49** corroborate the inversion.
- **Resolution:** Runtime is canonical (DRIFT-49). Flow-design must be updated. This is B1.

### X2. GAP-22 framing: integration-plan vs flow-design vs test-matrix

- **08-flow-design.md GAP-22 bullet (lines 797–801)** carries the 2026-05-28 revalidation and the GAP-22a/22b split rationale.
- **01-test-matrix.md T-P2-DRIFT-56** uses GAP-22a, GAP-22b verbatim.
- **09-integration-plan.md** still uses bare "GAP-22 (sandbox deposit simulation undocumented)" — the framing is now wrong (the endpoint exists, just isn't reachable for our auth model).
- **Resolution:** Flow-design + test-matrix are canonical. Integration-plan must be refreshed. This is B3.

### X3. GAP-31 resolution: integration-plan vs integration-log

- **04-integration-log.md line 491:** "GAP-31 RESOLVED. Canonical schema: REFERENCE (with extensions). Guides body shape is non-functional (DRIFT-40)."
- **09-integration-plan.md § 7 line 692:** "POST /v1/quotations BLOCKED on GAP-31 disambiguation."
- **02-test-coverage-heatmap.md row 17:** Quotations `Functional: 🚫 blocked (DRIFT-45)` — blocker is DRIFT-45 (fee profile ≥100%), not GAP-31.
- **Resolution:** Heatmap + integration-log are correct. Integration-plan § 7 row is stale. This is S2.

### X4. SEC-F<N> vs Finding <N>

- **02-test-coverage-heatmap.md** cites `SEC-F1, SEC-F2, SEC-F3, SEC-F4, SEC-F7, SEC-F8`.
- **05-security-audit.md** uses unprefixed `Finding 1, Finding 2, …`.
- Resolution: not a contradiction in fact, but a naming inconsistency. See S3.

### X5. GAP-14a orphan citation

- **12-api-reference-coverage.md line 84** proposes GAP-14a.
- **08-flow-design.md §6** has no GAP-14a entry (and no canonical "no, fold into GAP-14" rejection).
- Per DEC-005 only the data-architect assigns canonical numbers, so this is an orphan. See B2.

---

## Architectural verdict

**Coherent enough to ship?** **YES — with the four BLOCKING fixes (B1–B4) applied in a 30-minute focused pass.**

Reasoning:
- The architectural skeleton (resource families, state machines, cross-cutting contracts §2, renumber map in §6) is sound, defensible, and demonstrably the source-of-truth for downstream artifacts (the heatmap, test-matrix, phase-1-findings.md, README all consistently cite back to it).
- The integration plan's webhook-receiver decision (NO for Phase 2, defer to Phase 3) is empirically validated by Phase 3 work: Finding-#2 (CRITICAL SSRF + cross-tenant + opaque registration) was surfaced via passive `webhook.site` capture and adversarial FastAPI receiver in Phase 3 — exactly the staging the plan recommended. **The decision is not just still defensible, it produced the project's top-ranked security finding.**
- The 37 canonical GAPs are anchored to evidence; the renumber map cleanly resolves DEC-005 collisions; no two analysis docs propose conflicting canonical numbers for the same finding.
- The blockers are all "doc-drifted-from-runtime" issues, not "architecture-was-wrong" issues. B1 (webhook auth), B3 (GAP-22 framing), and B4 (open questions partly resolved) are easy mechanical updates. B2 (GAP-14a orphan) needs one decision (elevate or fold). None of these invalidate any downstream deliverable; they only make flow-design lag the empirical reality it should be leading.
- Family taxonomy in heatmap is consistent with flow-design §3. Cell counts add up. Blocker citations are accurate. Cross-references between Finding-#N, DRIFT-NN, GAP-NN, ABUSE-N resolve.

If B1–B4 are not applied, the project ships with a flow-design that contradicts its own runtime evidence on the webhook auth model — embarrassing but not fatal, since the README and test-matrix carry the canonical truth. Apply the fixes; flow-design becomes the integration reference it claims to be.

