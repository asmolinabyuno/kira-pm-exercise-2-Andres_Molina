# Test Inventory Matrix — Architect Proposal

**Persona:** `data-architect` | **Lens:** cross-cutting visibility, state-machine integrity, endpoint-family grouping, traceability to `flow-design.md` GAP-NN and `integration-log.md` DRIFT-NN.

---

## 1. Architectural Framing — why this matrix matters

A test inventory is a **system observability artifact**, not a status report. From the architect chair I need to answer four questions at a glance:

1. Which **resource family** (Auth · Users · Verification · VAs · Recipients · Quotations · PayIns · Payouts · PayLinks · LiqAddr · Webhooks · RefData) is under- vs over-tested?
2. Are **cross-cutting contracts** (envelope, auth, idempotency, versioning, pagination, country-code drift, webhook semantics) being exercised against *every* family, or only one?
3. Which tests **anchor a documented GAP-NN / DRIFT-NN** vs which are exploratory? (Traceability defends the README ranking.)
4. Which async **state machines** (User, VA, Payout, PayIn, Verification) are being traversed legally vs adversarially?

The user's 7-column proposal answers none of (1)–(4) directly.

## 2. Critique of the proposed format

| Column | Verdict | Comment |
|---|---|---|
| Endpoint tested | Keep | But add `family` — endpoints alone don't group. |
| Request type (POST/GET) | **CUT** | Redundant with endpoint path; HTTP method is already in the path column for any reader. Zero analytical value. |
| Test type | Keep, formalize | Must use a fixed taxonomy (docs / connection / congruence / functional / edge / concurrency / performance / security / abuse — same 9 categories as `test-topology.md`). |
| Test description | Keep, shorten | One line; the detail belongs in the linked evidence file. |
| Results summary | Keep, structure | Pass/fail/drift outcomes, not prose. |
| Priority | Keep | Tie to GAP severity, not free-form. |
| Status | Keep, expand taxonomy | Two values ("designed/done") collapses 4 distinct blockers into one bucket. |

**Critical omissions:** no GAP/DRIFT traceability, no resource family, no sync-vs-async semantic, no state-machine relevance flag, no prerequisite chain, no cross-cutting tag, no owner agent.

## 3. Recommended column list (13 columns, sortable flat table)

| # | Column | Why it matters |
|---|---|---|
| 1 | **Test ID** (`T-NNN`) | Stable handle for cross-references, README citations, and `.feature` filenames. |
| 2 | **Resource family** | Roll-up to 12 families (per `flow-design.md` § 3). Drives the heat-map view. |
| 3 | **Endpoint + method** | `POST /v1/payouts`. Method inline, not separate. |
| 4 | **Sync/async** | `sync` \| `async-poll` \| `async-webhook`. Determines whether a state-machine test is even meaningful. |
| 5 | **Test category** | 9-value enum (docs / connection / congruence / functional / edge / concurrency / performance / security / abuse). |
| 6 | **Cross-cutting tag** | One of: `envelope`, `auth`, `idempotency`, `versioning`, `pagination`, `iso3166`, `webhook-semantics`, `state-casing`, `none`. **Non-obvious; this is the column that exposes systemic gaps.** |
| 7 | **State-machine relevance** | `n/a` \| `legal-transition` \| `illegal-transition` \| `terminal-state` \| `re-entry`. |
| 8 | **Prerequisite chain** | Comma-list of upstream Test IDs (e.g., `T-002,T-007`). Encodes dependency arrows. |
| 9 | **Linked GAP-NN(s)** | E.g., `GAP-04, GAP-37`. Empty = exploratory. |
| 10 | **Linked DRIFT-NN(s)** | E.g., `DRIFT-1, DRIFT-19`. Closes the loop with `integration-log.md`. |
| 11 | **Owner agent** | `data-engineer` / `qa-engineer` / `api-functional-tester` / `api-security-auditor` / `fullstack-integrations`. |
| 12 | **Status** (see § 5) | Discrete taxonomy with blockers explicit. |
| 13 | **Result + evidence path** | Pass/Fail/Drift + relative path to `evidence/work/...` JSON or `.feature`. |

Priority is **derived**, not a column — it's `MAX(severity of linked GAP-NNs)`. Recording it manually risks drift against `flow-design.md`.

## 4. Grouping recommendation — flat table, sub-tabled by family

Keep **one flat sortable table** (sort/filter by any column) as the source-of-truth, then publish **12 read-only views grouped by `Resource family`** as collapsible sub-tables. Rationale:

- Two-dimensional grouping (family × phase, or family × category) duplicates rows and breaks Test ID uniqueness.
- The heat-map view (§ 7) handles `family × category` aggregation visually without row duplication.
- Cross-cutting tests (e.g., "ISO 3166 swap across all families") get one row per (test, family) pair so they roll up correctly into the heat map. Their Test IDs share a prefix (`T-XC-…` for cross-cutting) so they're filterable as a band.

## 5. Status taxonomy (with blockers explicit)

| Status | Meaning |
|---|---|
| `DESIGNED` | Row exists, parameters fixed, no harness yet. |
| `DEVELOPED` | Harness or `.feature` file written, not yet executed. |
| `EXECUTED-ONCE` | Single run captured; result recorded. |
| `REPRODUCED-N` | N ≥ 2 runs converge on the same outcome (drift-free or drift-confirmed). |
| `BLOCKED-DEP` | Waiting on an upstream Test ID (e.g., need VA → blocked on KYB approval). |
| `BLOCKED-GAP` | Waiting on a documentation answer (cite the GAP-NN). |
| `BLOCKED-ENV` | Sandbox can't model it (e.g., GAP-22 sandbox deposit). |
| `RETIRED` | Superseded by a better test (cite replacement Test ID). |

Three blocker variants matter — collapsing them hides whether we need engineering, docs, or env work.

## 6. Sample row (cross-cutting — DRIFT-1 base URL)

| # | Field | Value |
|---|---|---|
| 1 | Test ID | `T-XC-001` |
| 2 | Family | `cross-cutting (all)` |
| 3 | Endpoint + method | `POST https://api.balampay.com/sandbox/auth` (probe variant) |
| 4 | Sync/async | `sync` |
| 5 | Category | `congruence` (docs↔runtime) |
| 6 | Cross-cutting tag | `versioning` *(URL prefix is the version anchor; failure reveals GAP-32-shape issue)* |
| 7 | State-machine relevance | `n/a` |
| 8 | Prerequisite chain | — (zero-deps, foundational) |
| 9 | Linked GAP-NN | `GAP-32` (unversioned base path pattern) |
| 10 | Linked DRIFT-NN | `DRIFT-1` |
| 11 | Owner | `data-engineer` |
| 12 | Status | `REPRODUCED-3` (confirmed `/sandbox` 403/401 vs root 2xx) |
| 13 | Result + evidence | **FAIL — docs wrong** · `evidence/work/auth/01-sandbox-prefix-403.json` |

## 7. Complementary coverage view — family × category heat map

A second view is **worth the cost** — the flat table answers "what's the state of test T-117?", the heat map answers "is the system tested?". They serve different audiences (engineer vs reviewer vs PM).

```
                  docs  conn  congr  func  edge  conc  perf  sec   abuse
Auth               ✓✓    ✓✓    ✓✓    ✓     ·     ·     ✓     ◐     ·
Users              ✓     ✓     ✓✓    ✓✓    ✓     ◐     ✓     ◐     ·
Verification       ✓     ✓     ✓     ◐     ·     ·     ·     ·     ·
VAs                ✓     ✓     ◐     ◐     ·     ·     ·     ·     ·
Recipients         ✓     ✓     ✓     ✓     ·     ·     ✓     ·     ·
Quotations         ◐     ·     ✗     ·     ·     ·     ·     ·     ·   ← GAP-31 block
PayIns             ✓     ·     ◐     ·     ·     ·     ·     ·     ·
Payouts            ✓     ·     ✓     ·     ·     ·     ·     ✗     ·   ← GAP-23 block
PayLinks           ·     ·     ·     ·     ·     ·     ·     ◐     ·
LiqAddr            ✓     ·     ·     ·     ·     ·     ·     ·     ·
Webhooks           ✓     ·     ·     ·     ·     ·     ·     ✗     ◐   ← Finding #4
RefData            ✓✓    ✓✓    ✓     ·     ·     ·     ✓     ·     ·
```
Legend: `✓✓` reproduced ≥2× · `✓` executed-once · `◐` designed-or-developed · `·` no test · `✗` blocked.

Empty columns scream — at a glance: concurrency, abuse, and edge are systemically under-tested. That's a Phase-3 plan, not a status report.

---

**End of architect proposal.** Hand off to PM for severity-derivation rules; to QA for harness-mapping the `DEVELOPED → EXECUTED-ONCE` transition; to functional-tester and security-auditor for filling the `abuse` and `sec` columns of the heat map.
