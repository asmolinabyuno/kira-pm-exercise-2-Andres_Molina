# Test Inventory Matrix — PM Proposal

**Lens:** Product Manager — integrator-impact framing, README top-5 feeder.
**Date:** 2026-05-28

---

## Audience & Purpose

**Primary audience:** Kira engineering team (Diego/Eng + Nicolle/PD) reading our deliverable to decide *what to fix this sprint*. **Secondary audience:** Edrizio + enterprise-deal AEs who need to see "we tested X, found Y, here's the integrator pain." **Tertiary:** future probes/regression — can a new agent re-run a row in 2026-Q3?

The matrix MUST answer four PM questions in a single row scan:
1. Did this hurt a real integrator? (severity + integrator-pain one-liner)
2. Is it a README top-5 candidate? (binary, defended)
3. What's the GAP / DRIFT / OWASP it ties to? (cross-ref to existing artifacts)
4. What's the fix-effort vs blast-radius? (so Kira engineering can sprint-plan)

---

## Critique of User's Proposed Format

The 7 columns are a solid **QA test log** but a weak **integrator-impact deliverable**. What a Kira engineer reading it would NOT be able to do:

- **Prioritize.** No severity, no integrator-pain estimate, no blast-radius. "Priority" alone is ungrounded — priority *for whom*?
- **Triangulate.** No link back to GAP-NN (37 catalogued), DRIFT-NN (53 captured), OWASP API#, or README finding #. Each row is an island.
- **Estimate fix cost.** No `fix_effort` axis → no sprint-plan.
- **Trace evidence.** No evidence-path column → "results summary" alone is uncited.
- **Tell apart docs vs runtime vs security vs abuse.** "Test type" is one column carrying three orthogonal axes (pillar, OWASP/abuse category, phase).
- **Distinguish silent breakage from loud failure** — Kira's #1 risk class (the silent-200 with wrong body). This needs its own flag.

"Endpoint tested" + "Request type" are useful but redundant once we have a `method+path` column. "Test description" should split into `intent` (what hypothesis) and `inputs` (what we sent).

---

## Recommended Column List

(I keep 4 of the user's 7 in some form, drop 1, replace 2, add 9 — for a total of 13 columns.)

| # | Column | Rationale |
|---|---|---|
| 1 | `test_id` | Stable handle (`T-001..T-NNN`) so README and `.feature` files reference rows by ID. |
| 2 | `phase` | P1-Docs / P2-Integration / P3-Security / P3-Abuse / P3-Load. Phase = grading axis (CLAUDE.md), so it gates the row. |
| 3 | `pillar` | Documentation / Ease-of-Connection / Docs↔Runtime / Integration-Hardening. Drives pillar-scores.md. |
| 4 | `endpoint` | `METHOD path` collapsed (e.g. `POST /v1/users`). Replaces user's #1+#2. |
| 5 | `test_intent` | One-line hypothesis (e.g. "verify webhook URL validation rejects RFC1918"). Replaces user's "test description" — sharper. |
| 6 | `inputs` | Concrete payload/header diff vs happy-path. Specificity bar from CLAUDE.md. |
| 7 | `expected` | Doc-derived expected behavior (status + envelope shape). |
| 8 | `observed` | Runtime fact (status + envelope shape + key field). |
| 9 | `drift_flag` | Boolean — does observed contradict expected? Drives docs↔runtime congruence count. |
| 10 | `severity` | CRITICAL / HIGH / MEDIUM / LOW. PM heuristic from product-manager.md (>1 day lost? silent breakage? blocks go-live? abuse exposure?). |
| 11 | `integrator_impact` | One sentence: who is hurt and how. The README-feeder column — this IS the "why this matters to a client" line. |
| 12 | `cross_ref` | `GAP-NN, DRIFT-NN, OWASP-API#, FINDING-#, FEATURE-slug` — multi-link back to all existing artifacts. |
| 13 | `status` | See taxonomy below. Replaces user's #7 with discrete states. |
| 14 | `evidence_path` | `evidence/work/{slug}/...` — every row cites a raw HTTP capture (CLAUDE.md hard rule: "every finding needs evidence"). |
| 15 | `readme_top5_candidate` | YES / NO / CONTESTED. Bias the deliverable: the matrix's *purpose* is to feed README ranking. |

(Counts as **13 columns net-new beyond the user's 2 I kept = endpoint + status.** Or 15 total if you count rolling endpoint+method into one cell.)

---

## Recommended Grouping (Rows)

**Primary sort: by `phase`. Secondary: by `severity` desc. Tertiary: by `endpoint`.**

Why phase-first, not endpoint-first:
- Our deliverable IS phase-structured (CLAUDE.md three-phase methodology — P1 closed, P2 in progress, P3 partial). Phase-first preserves the project's narrative.
- A grader reading top-down sees: docs findings → integration findings → security/abuse findings, mirroring the README's likely structure.
- Endpoint-grouping forces duplication (one row per phase × endpoint), exploding the count.
- Severity-second means CRITICALs surface within each phase block — directly README-actionable.

Reject "by OWASP category" — too narrow (only Phase 3 maps to OWASP). Reject "by endpoint" — fights our phased narrative. Reject "by README finding" — chicken-and-egg, the matrix should *feed* README ranking, not assume it.

---

## Status Taxonomy

Seven discrete states (no overlaps, all transitions logged):

- **DESIGNED** — row exists, intent + expected populated, not yet executed.
- **EXECUTING** — actively being probed. Time-boxed; should not stay here >24h.
- **EXECUTED-CLEAN** — ran, observed matches expected, no drift, closed.
- **EXECUTED-DRIFT** — ran, drift_flag=true, drift event written, awaiting finding write-up.
- **REPRODUCED** — drift verified N≥2 times, eligible for README candidate.
- **BLOCKED** — cannot execute (e.g., Batches D/F blocked by DRIFT-B10 user-not-auto-approved). Must name blocker.
- **CLOSED-FINDING** — promoted to a numbered finding (Finding #N in `phase-1-findings.md` or OWASP # in `security-audit.md`).
- **CLOSED-DEFERRED** — out-of-scope for this exercise; logged for handoff to Diego.

(User's "designed / done" collapses 5 of these into 1 — too coarse for a deliverable graded on Specificity 30%.)

---

## Sample Row (real data — DRIFT-47, SSRF-webhook)

| col | value |
|---|---|
| test_id | T-091 |
| phase | P3-Security |
| pillar | Integration-Hardening |
| endpoint | `POST /webhooks/register` |
| test_intent | Verify Kira rejects attacker-supplied internal-network URLs (RFC1918, AWS IMDS) at webhook registration. |
| inputs | `webhook_url=http://169.254.169.254/latest/meta-data/iam/security-credentials/`, `secret=""`, valid client_uuid. |
| expected | 400 with envelope-B `{error:{code:"INVALID_WEBHOOK_URL"}}` per defensive-validation norms. |
| observed | **200** registration accepted; subsequent `POST /v1/users` triggered outbound fetch from `54.201.149.241` to the IMDS URL (zero deliveries to webhook.site control). |
| drift_flag | TRUE |
| severity | CRITICAL |
| integrator_impact | A compromised integrator API key becomes a launchpad to exfiltrate Kira's AWS IAM creds. Every Kira tenant shares one fetcher pool → blast radius is platform-wide, not single-tenant. Enterprise security review at Banco Industrial/N1co will block sign-off until fixed. |
| cross_ref | DRIFT-47, GAP-11, GAP-21, OWASP-API7:2023, security-audit Finding #1, abuse Scenario #5 |
| status | REPRODUCED |
| evidence_path | `evidence/work/security/ssrf-webhook-delivery-confirm/probe_ssrf_delivery.py` + `evidence/work/webhooks/32-success-P1-stepC-webhook-receipt-snapshot.json` |
| readme_top5_candidate | YES |

---

## Trade-offs (What This Format Sacrifices)

- **Density.** 15 columns is wide. Mitigation: render as wrapped markdown table or sectioned-per-row block in the deliverable; CSV under the hood for filter-ability.
- **Speed of authoring.** Filling `integrator_impact` per row is real PM work — but that IS the deliverable (Communication 10% + Prioritization 40%).
- **QA test-management ergonomics.** A test engineer wanting "all POST /v1/users tests" must filter, not sort — endpoint is column 4, not the primary sort. Acceptable trade because the audience is Kira eng, not our internal QA.
- **Phase-bias risk.** Grouping by phase hides cross-phase patterns (e.g., "envelope drift" hits P1 + P2 + P3). Mitigation: `cross_ref` column carries the linkage; a separate cross-phase summary lives in `phase-1-findings.md` Executive Summary.
- **No automation column.** Did the test ship a runnable harness (k6/pytest/probe.py)? Implicit in evidence_path but not a first-class column — if QA-engineer's lens wants this, add a 16th.
