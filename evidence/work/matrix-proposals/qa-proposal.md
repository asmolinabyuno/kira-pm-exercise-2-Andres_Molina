# QA Test-Inventory Matrix — Proposal (qa-engineer lens)

## Tooling reference

Mimicking the **Allure TestOps** test-case schema (id, suite, severity, owner, steps, attachments) crossed with the **JUnit 5 `@Tag` / pytest marker** model and the **Bruno collection** file-per-test layout. Allure gives us the lifecycle-vs-outcome split; JUnit/pytest gives the discrete outcome enum; Bruno gives the on-disk reproducibility (one test = one file). Bonus: **Schemathesis stateful test IDs** for fuzz/contract rows.

Each matrix row corresponds 1:1 to a real artifact already on disk under `evidence/work/{abuse|security|automation|latency}/{slug}/` — the matrix is an **index over the harnesses**, not a parallel document.

## Critique of the user's 7-column format

| Column | Verdict | Issue |
|---|---|---|
| Endpoint tested | KEEP | But add **path + method** as separate fields so we can filter by family. |
| Request type | **CUT — merge into Endpoint** | "POST /v1/users" is one atom; splitting `method` from `path` is sufficient. A standalone "Request type" column is redundant. |
| Test type | KEEP, but enumerate | Today implicit ("abuse", "load", "contract"). Must be a closed enum tied to `@tags`. |
| Test description | KEEP | But mandate Given/When/Then template — free-text descriptions = unrunnable. |
| Results summary | KEEP, **split into 3** | One column smushes `expected`, `actual`, `verdict`. Allure separates them; we should too. |
| Priority | KEEP, **rename → Severity** | Match `.feature` header field; align with PM ranking (CRITICAL/HIGH/MEDIUM/LOW). |
| Status | KEEP, **make 2D** | Single-axis status confuses *lifecycle* (designed/coded) with *outcome* (passed/failed). See § 2D taxonomy. |

**The hard miss:** **no reproducibility hook.** A QA engineer reading row 47 cannot answer "where do I rerun this?" or "what assertion failed?". That kills the deliverable's value the moment someone tries to regress-test it.

## Recommended column list (14 columns)

| # | Column | Why (tooling parallel) |
|---|---|---|
| 1 | `test_id` | Stable PK, format `KIRA-{CAT}-{NNN}` (e.g., `KIRA-ABU-007`). Allure `testCaseId`. |
| 2 | `suite` | Allure suite / pytest module — grouping (see § Grouping). |
| 3 | `feature_file` | Path to `features/{slug}.feature` — Cucumber traceability. |
| 4 | `scenario_name` | Exact Gherkin `Scenario:` line. JUnit `@DisplayName`. |
| 5 | `method` | GET/POST/PUT/DELETE — filterable. |
| 6 | `path` | `/v1/recipients/{id}` — templated, not concrete. |
| 7 | `tags` | Closed enum, multi-valued: `@auth @idempotency @abuse @docs-runtime-drift @latency @security @contract @fuzz @concurrency` (matches qa-engineer.md § Tags). |
| 8 | `severity` | CRITICAL / HIGH / MEDIUM / LOW. Aligns with `.feature` header. |
| 9 | `given_when_then` | One-line collapsed Gherkin. If we can't write it, the test is undefined. |
| 10 | `expected` | Concrete observable (status code, JSON path, header). |
| 11 | `actual` | Captured from latest run. Empty if `lifecycle < EXECUTED`. |
| 12 | `lifecycle_state` | See § 2D taxonomy axis 1. |
| 13 | `outcome` | See § 2D taxonomy axis 2. |
| 14 | `evidence_anchor` | `{harness_path}#{capture_file}#{summary_jsonpath}` — see § Evidence-anchor. |

Optional sidecar columns (won't fit in a flat .md table, but live in YAML front-matter per row): `gap_id`, `drift_id`, `related_findings[]`, `last_run_iso`, `last_run_git_sha`, `flake_count`, `owner_agent`.

## Recommended grouping — by suite, then by tag

Three-level hierarchy, mirroring pytest's `module::class::test`:

```
Suite (top of matrix section)
 └── Category tag (table per tag)
      └── Row per scenario
```

Suites:
1. `auth-and-headers` — `/auth`, version header, `x-api-key`, `x-validation-header`
2. `users-and-kyb` — `/v1/users`, verifications, state machine
3. `recipients` — POST/GET/DELETE + 4 rail variants
4. `quotations-and-payouts` — quotation lifecycle, payout creation
5. `webhooks` — register, delivery, signature, SSRF
6. `reference-data` — `/v1/countries`, `/v1/banks`
7. `cross-cutting` — error-envelope drift, idempotency, pagination, latency

Rationale: **suite matches Phase-2 batch** (A/B/C/E/G), so rows trace back to `integration-log-batch-{X}.md` without renaming. Endpoint-grouping alone (the obvious move) splits cross-cutting findings like "error envelope variance" across 8 rows.

## 2D Status taxonomy (lifecycle × outcome)

**Two independent axes.** A row has one value from each.

**Axis 1 — Lifecycle (where in the workflow):**
| State | Meaning |
|---|---|
| `DESIGNED` | Scenario written in `.feature`, no automation yet. |
| `DEVELOPED` | Automation script (`run.py` / `probe_*.py` / `.bru` / k6) exists, not yet executed against runtime. |
| `EXECUTED` | Has at least one captured run against sandbox; evidence files exist. |
| `REGRESSED` | Re-run after a code/doc change; outcome compared to previous. |
| `DEPRECATED` | Endpoint removed or scenario invalidated (e.g., GAP closed). |

**Axis 2 — Outcome (last execution result, pytest-aligned):**
| State | pytest equivalent | Meaning |
|---|---|---|
| `PASSED` | `.` | Assertion held — API behaved as expected. |
| `FAILED` | `F` | Assertion broke — API misbehaved (the **interesting** rows: these are findings). |
| `XFAILED` | `x` | Expected failure (e.g., we know GAP-21 has no list endpoint — assertion is "expect 403"). |
| `ERROR` | `E` | Harness blew up before assertion (network, fixture). Not a finding — a flake. |
| `SKIPPED` | `s` | Prereq missing (e.g., needs second tenant for true BOLA). |
| `BLOCKED` | n/a | Dependency on another test or external escalation (DRIFT-B10 sandbox-approval style). |
| `N/A` | n/a | Used when `lifecycle != EXECUTED`. |

**Interaction matrix (which combos are legal):**
- `DESIGNED` → `outcome` MUST be `N/A`
- `DEVELOPED` → `outcome` MUST be `N/A`
- `EXECUTED` / `REGRESSED` → `outcome` MUST be one of {PASSED, FAILED, XFAILED, ERROR, SKIPPED, BLOCKED}
- `DEPRECATED` → `outcome` is frozen at last-known value

A "completion %" dashboard reads `lifecycle ≥ EXECUTED` AND `outcome IN (PASSED, XFAILED)`. A "findings count" reads `outcome = FAILED`.

## Sample row (real data — Scenario 3 from abuse harness)

```yaml
test_id:           KIRA-ABU-003
suite:             cross-cutting
feature_file:      features/bola-cross-tenant-stub.feature
scenario_name:     "POST /v1/payouts with a recipient_id we do not own returns 4xx not 200"
method:            POST
path:              /v1/payouts
tags:              [@abuse, @security, @bola, @cross-tenant]
severity:          HIGH
given_when_then:   |
  Given a valid bearer for tenant A
  When I POST /v1/payouts with recipient_id = <UUID owned by no one we created>
  Then the response status MUST be 400 or 404 (NOT 200/201/202)
  And response.body.error.code MUST equal "VALIDATION_ERROR" or "NOT_FOUND"
expected:          status ∈ {400,404}; error.code defined
actual:            status=400; body.error.code="VALIDATION_ERROR"
lifecycle_state:   EXECUTED
outcome:           PASSED
evidence_anchor:   evidence/work/abuse/bola-cross-tenant-stub/run.py#L46
                   ::evidence/work/abuse/bola-cross-tenant-stub/05-payout-fake-recipient.json
                   ::_summary.json$.results[?(@.probe=="payout-fake-recipient")]
gap_id:            (cross-cutting; no specific GAP — feeds into security-audit BOLA section)
last_run_iso:      2026-05-27T19:42:00Z
owner_agent:       api-security-auditor (designed) + qa-engineer (Gherkinized)
```

## Evidence-anchor scheme (the reproducibility contract)

Format: `{script_path}#L{line}::{capture_file}::{jsonpath_into_summary}`

Three parts because each answers a different question:
1. **`{script_path}#L{line}`** — "How do I rerun this exact probe?" Open the script, jump to line, copy the function call. Mirrors Allure's "step" link.
2. **`{capture_file}`** — "What did the API return on the run that produced this row?" A pinned `.json` capture under the harness dir, **not** a regenerated one. Mirrors Allure attachment.
3. **`{jsonpath}`** — "Which assertion in the summary keyed off this capture?" JSONPath into `_summary.json` so the row pivots back to the harness's own verdict. Mirrors JUnit `<failure message="">` selectors.

**Reproducibility hash (recommended sidecar):** `sha256(script_path + git_sha_at_run + scenario_name)` truncated to 8 chars → embed in `test_id` as suffix when needed (`KIRA-ABU-003-a7f1c2`). Lets us detect when the script changed but the row didn't get re-run.

**Runnability question — can a future engineer regenerate?** YES if the row has: `feature_file` (the spec), `evidence_anchor.script_path` (the executor), `expected` (the assertion), `tags` (the framework hook), and `severity` (the prioritization). Missing any one of those, the row is documentation, not a test.
