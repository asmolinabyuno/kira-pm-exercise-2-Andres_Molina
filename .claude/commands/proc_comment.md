# /proc_comment — Process Comments (Test Design / Develop / Execute)

You are a change-propagation engine for an **API evaluation project** organized around three sequential phases (see `CLAUDE.md` § Project Methodology):

1. **Phase 1 — Documentation Quality Evaluation**
2. **Phase 2 — Empirical Integration with Difficulty Telemetry**
3. **Phase 3 — Adversarial Testing via Python Harnesses**

The deliverable is a *test program*: designing tests, developing them (Python harnesses + `.feature` files + automation scripts), executing them against Kira's sandbox, and turning the findings into a ranked top-5 README with backing evidence. Most comments will request one of these things.

The user leaves comments in `evidence/work/comments.md`. Your job: process each one, classify by **type + phase**, record decisions, update all affected artifacts using specialized agents, and clear the inbox.

## Input

1. Read `evidence/work/comments.md`
2. If the file is empty (no comments after the `---` separator), check $ARGUMENTS for inline comments
3. If both are empty, ask the user what they want to change

Each comment is a separate change request. Process them in order.

## Procedure

### Step 1: Parse, Classify & Phase-Tag

For each comment:

- **Interpret** (user writes Spanish; interpret to English)
- **Classify type** — pick the best fit:
  | Type | Use when the comment asks for... |
  |---|---|
  | `DESIGN` | A new test/probe/scenario/harness to be **designed** (not yet coded) |
  | `DEVELOP` | A test to be **implemented** (Python harness, `.feature` file, automation script, k6 plan) |
  | `EXECUTE` | A test to be **run** and evidence captured (request/response logs, latency stats, abuse outcomes) |
  | `REFINE` | An existing finding's **severity / category / ranking / wording** to change |
  | `ADDITION` | New content / methodology / rule / artifact |
  | `CORRECTION` | A straightforward fix |
  | `DECISION` | Options to weigh before committing |
- **Phase-tag:** `Phase 1` | `Phase 2` | `Phase 3` | `Cross-phase`
- **Priority:** CRITICAL | HIGH | MEDIUM | LOW
- **Scope:** which artifacts AND which future work is affected

### Step 2: Phase-Jump Check

Before processing, ask: **does this comment require work from a phase we haven't started?** Check `CLAUDE.md` § Project Methodology for current phase statuses.

- If the comment is methodological (ADDITION / DECISION / REFINE), proceed regardless of phase.
- If the comment is test work (DESIGN / DEVELOP / EXECUTE) on a phase we're not in yet:
  - **DESIGN** can run ahead of the phase — designing is cheap. Process.
  - **DEVELOP / EXECUTE** on a phase we're not in → process, but flag in DEC entry and surface in summary: *"WARNING — Phase {N} work requested on endpoints not yet validated in Phase {M}."*
- **Hard rule:** Phase 3 (security/abuse) DEVELOP/EXECUTE against endpoints we haven't successfully integrated in Phase 2 produces noise. Ask the user to confirm before processing.

### Step 3: Impact Analysis

For each comment, determine:
1. What specifically changes (a probe, a harness script, a `.feature` step, a finding's severity, a `phase-1-findings.md` entry)
2. Downstream implications — if severity changes, does README ranking change? If a harness moves to a new endpoint, does `test-topology.md` need updating?
3. Conflicts with previous decisions in `decision-log.md`?
4. Impact on future work — new rules/patterns/constraints

### Step 4: Decision Log Entry

Read `decision-log.md`. For each comment, append one entry using the matching template:

**DESIGN — design a test/probe/scenario/harness:**
```
## DEC-{N} — {decision_title}
- **Date:** {YYYY-MM-DD}
- **Comment:** {ES original}
- **Interpretation:** {EN}
- **Type:** DESIGN
- **Phase:** 1 | 2 | 3 | Cross-phase
- **Owner agent(s):** {who designs}
- **Test category:** docs-quality | functional | contract | concurrency | performance | abuse | security | full-stack
- **Design target artifact:** {file that gets the design — test-topology.md, abuse-scenarios.md, security-audit.md, phase-1-findings.md, etc.}
- **Acceptance:** {what counts as "designed" — e.g., scenario has setup/attempt/expected/observed, mapped to endpoint, tagged with category}
- **Future impact:** {if relevant}
```

**DEVELOP — implement a test:**
```
## DEC-{N} — {decision_title}
- **Date:** {YYYY-MM-DD}
- **Comment:** {ES original}
- **Interpretation:** {EN}
- **Type:** DEVELOP
- **Phase:** 1 | 2 | 3 | Cross-phase
- **Owner agent(s):** {who codes}
- **Depends on:** {DESIGN DEC-XXX if any}
- **Implementation target:** {exact path — e.g., evidence/work/abuse/refund-race/run.py, features/version-header-default.feature, evidence/work/automation/idempotency/test_idem_conflict.py}
- **Test framework:** pytest+httpx | k6 | Locust | Schemathesis | Pact | Cucumber-Karate | Postman/Newman | Bruno
- **Acceptance:** {test runs locally; fails without bug-fix; passes with; captures evidence to designated path; never commits secrets}
- **Future impact:** {if relevant}
```

**EXECUTE — run a test:**
```
## DEC-{N} — {decision_title}
- **Date:** {YYYY-MM-DD}
- **Comment:** {ES original}
- **Interpretation:** {EN}
- **Type:** EXECUTE
- **Phase:** 1 | 2 | 3 | Cross-phase
- **Owner agent(s):** {who runs}
- **Depends on:** {DEVELOP DEC-XXX if any}
- **Test target:** {script path}
- **Evidence target:** {path where results land — evidence/work/.../{outcome}.json or .md}
- **Outcome to record:** {pass/fail/finding-promoted-to-top-5}
- **Iteration count + doc-sufficiency capture (Phase 2 only):** required → `evidence/analysis/04-integration-log.md`
- **Latency capture (any phase):** if endpoint, save p50/p95/p99 to `evidence/work/latency/{endpoint}.json`
- **Future impact:** {if a finding is promoted, list README/feature-file/decision-log updates needed}
```

**REFINE — change a finding's severity / category / ranking / wording:**
```
## DEC-{N} — {decision_title}
- **Date:** {YYYY-MM-DD}
- **Comment:** {ES original}
- **Interpretation:** {EN}
- **Type:** REFINE
- **Phase:** 1 | 2 | 3 | Cross-phase
- **Finding affected:** {Finding #N or GAP-NN}
- **Change:** {old → new for severity / category / ranking / pillar / "why this matters" copy}
- **Rationale:** {why the change is warranted — anchor to evidence if possible}
- **Applied to:** {README.md, features/{slug}.feature header comment, phase-1-findings.md, flow-design.md §6, etc.}
- **Validated by:** {agent — usually `devil-advocate` for severity changes}
```

**ADDITION — new content / methodology / rule:**
```
## DEC-{N} — {decision_title}
- **Date:** {YYYY-MM-DD}
- **Comment:** {ES original}
- **Type:** ADDITION
- **Phase:** 1 | 2 | 3 | Cross-phase
- **What was added:** {description}
- **Applied to:** {artifacts updated}
- **Future impact:** {new constraint or pattern}
```

**CORRECTION — straightforward fix:**
```
## DEC-{N} — {decision_title}
- **Date:** {YYYY-MM-DD}
- **Comment:** {ES original}
- **Type:** CORRECTION
- **Phase:** 1 | 2 | 3 | Cross-phase
- **Change:** {what changed}
- **Applied to:** {artifacts}
- **Future impact:** {if any}
```

**DECISION — options to weigh:**
```
## DEC-{N} — {decision_title}
- **Date:** {YYYY-MM-DD}
- **Comment:** {ES original}
- **Interpretation:** {EN}
- **Type:** DECISION
- **Phase:** 1 | 2 | 3 | Cross-phase
- **Context:** {why this decision was needed}
- **Options considered:**
  1. {A} — {pros/cons}
  2. {B} — {pros/cons}
- **Decision:** {what was decided and why}
- **Changes applied:**
  - [ ] {artifact 1}: {specific change}
  - [ ] {artifact 2}: {specific change}
- **Future impact:** {constraints applied to future work}
- **Validated by:** {agent}
```

### Step 5: Launch Agents to Apply & Validate Changes

Use the Task tool to launch agents in parallel. Choose based on **phase + type + content area**:

| Content area | Agent | Phases | Validates |
|---|---|---|---|
| Phase 1 docs evaluation, four-pillar scoring, finding ranking, README copy, integrator-impact framing, outreach decisions | `product-manager` | 1, 2, 3 | Top-5 defensible, severities calibrated, pillar scores anchored to evidence |
| Integration flow, contract table, state machines, test topology, structural gaps, flow-design.md updates | `data-architect` | 1, 2 | flow-design.md current; test-topology.md maps endpoint × category × owner |
| HTTP plumbing, auth wiring, webhook receiver, redaction, **integration-log instrumentation** (iteration count + doc-sufficiency), latency baselines, list-endpoint reporting probes | `data-engineer` | 2 (primary), 1 & 3 (support) | Evidence reproducible, secrets redacted, integration-log captures iteration counts + doc-sufficiency booleans + drift events |
| Hosted-page evaluation, payment-link tests, SDK eval/absence, iframe/CSP/redirect probes, serverless webhook-receiver patterns, mobile-browser matrix | `fullstack-integrations-specialist` | 1, 2 | Full-stack findings include UI/redirect/iframe context |
| `.feature` files, Gherkin steps, automation scripts (pytest+httpx, Newman, Karate), contract tests (Schemathesis/Pact), load tests (k6/Locust) | `qa-engineer` | 1, 2, 3 | Every finding has a runnable `.feature` + automation under `evidence/work/automation/{slug}/`; load harness under same path; contract tests under `evidence/work/automation/contract/` |
| Business-logic abuse scenarios (state-machine bypass, refund-after-transfer race, double-spend, KYB skip, currency exploits, webhook spoof) + Python reproduction harnesses | `api-functional-tester` | 3 | Scenarios reproducible (`evidence/work/abuse/{slug}/run.py`), dollar/trust impact stated, severity calibrated against money at risk |
| OWASP API Top 10 audit (BOLA, broken auth, mass assignment, SSRF, injection, TLS, info leakage) + Python pentest harnesses | `api-security-auditor` | 3 | Each finding mapped to API{1-10}:2023, CVSS-shape impact, sanitized reproduction in `evidence/work/security/{slug}/` |
| Any change (final pass) — prioritization, specificity, severity calibration, missing categories | `devil-advocate` | 1, 2, 3 | No contradictions, prioritization defensible, specificity bar met, top-5 properly ranked |

**Routing rules:**
- Default to the agent whose specialty matches the comment's content area.
- For findings overlapping abuse + security (e.g., BOLA): route to `api-functional-tester` (abuse scenario) AND `api-security-auditor` (OWASP mapping); they pair.
- For findings about hosted pages, payment links, redirects, SDKs: route to `fullstack-integrations-specialist`, not `data-engineer`.
- For EVERY finding that needs a runnable test: route to `qa-engineer` after the originating agent has documented the finding.
- For DESIGN-then-DEVELOP-then-EXECUTE chains: process in that order, with each DEC depending on the prior. Don't fire DEVELOP before DESIGN is logged.
- For REFINE on severity / ranking: ALWAYS finish with `devil-advocate` for calibration.
- For final ship review: always end the batch with `devil-advocate`.

Each agent receives:
- The comment text
- The DEC-{N} reference
- The phase + type tags
- The specific artifacts to update (paths)
- Instructions to READ the artifact first, APPLY the change, CONFIRM what was modified, and report whether their work introduced any new findings or new doc-vs-runtime drift events

**Important:** Agents must update `CLAUDE.md` if the comment introduces a new rule / constraint / known issue (e.g., "from now on every Python harness must call `_redact.py` before logging").

### Step 6: Cross-Validation

After agents finish, verify in this order:

1. **Phase coherence** — every DEVELOP/EXECUTE DEC ties back to a DESIGN DEC (or marks itself as ad-hoc with rationale)
2. **Evidence integrity** — every `.feature` file's `# Evidence:` and `# Automation:` lines point to files that exist
3. **Severity ↔ ranking** — README top-5 order matches severity (CRITICAL > HIGH > MEDIUM > LOW)
4. **Pillar consistency** — every finding has a pillar tag (Docs Quality / Ease of Connection / Docs-Runtime Congruence / Integration Hardening)
5. **GAP traceability** — `.feature` files cite GAP-NN where applicable; `phase-1-findings.md` references the source artifacts (docs-coverage-matrix, product-catalog, api-reference-coverage)
6. **Reproducibility** — every Python harness can be run via `python -m pytest` or `python {script}.py` from a fresh checkout + `.env`
7. **Secret hygiene** — grep evidence/work for committed tokens, API keys, or webhook secrets; reject any unredacted
8. **Decision log checkboxes** — all marked `[x]`

If issues found, create a follow-up DEC entry and fix inline (don't recurse infinitely).

### Step 7: Clear the Inbox

After ALL comments are processed and validated, overwrite `evidence/work/comments.md` with the clean template:

```markdown
# Comments — Inbox

Write your comments below. Run `/proc_comment` to process them all and clear this file.

---

```

### Step 8: Summary Output

```
PHASE STATUS:
  Phase 1 (Docs Quality):           {NOT STARTED | IN PROGRESS X% | COMPLETE}
  Phase 2 (Empirical Integration):  {NOT STARTED | IN PROGRESS X% | COMPLETE}
  Phase 3 (Adversarial Testing):    {NOT STARTED | IN PROGRESS X% | COMPLETE}

PROCESSED: {N} comment(s)
DECISIONS: DEC-{first} through DEC-{last}

BY TYPE:        design={n} develop={n} execute={n} refine={n} addition={n} correction={n} decision={n}
BY PHASE:       1={n}  2={n}  3={n}  cross={n}

AGENTS USED: {comma-separated list}

ARTIFACTS UPDATED:
  - {artifact}: {brief description}

NEW FINDINGS PROMOTED TO TOP-5 CANDIDATES: {count, or "none"}
FUTURE RULES ADDED:                       {count, or "none"}
PHASE-JUMP FLAGS:                         {list, or "none"}

CROSS-VALIDATION: PASS | {numbered list of remaining issues}
```

## Artifact Inventory

**This list grows as the project evolves** — always scan `evidence/work/` and `features/` for new files before processing.

### Phase 1 — Documentation Quality
| Artifact | Path | What to check |
|---|---|---|
| Flow design | `evidence/analysis/08-flow-design.md` | Endpoint catalog, state machines, cross-cutting contracts, gap list (GAP-NN) |
| Docs coverage matrix | `evidence/analysis/11-docs-coverage-matrix.md` | Guides sweep × 8 agents, per-section coverage status |
| Product catalog | `evidence/analysis/10-product-catalog.md` | Guides as product brochure, product↔API mismatches |
| API Reference coverage | `evidence/analysis/12-api-reference-coverage.md` | Reference-layer findings (Try It widget, code samples, Recent Requests) |
| Pillar scores | `evidence/work/pillar-scores.md` | Four-pillar evaluation |
| Phase 1 findings | `evidence/analysis/03-phase-1-findings.md` | Consolidated docs-quality findings ranked by integrator impact |

### Phase 2 — Empirical Integration
| Artifact | Path | What to check |
|---|---|---|
| Test topology | `evidence/work/test-topology.md` | Endpoint × test-category × owner matrix |
| Run script | `evidence/work/run_flow.py` | End-to-end orchestrator, idempotent re-run |
| Redaction helper | `evidence/work/_redact.py` | Used by all logging — must mask tokens & API keys |
| Webhook receiver | `evidence/work/webhook_receiver.py` | FastAPI receiver for sandbox deliveries |
| Integration log | `evidence/analysis/04-integration-log.md` | **Per-endpoint:** iteration count to first 2xx, doc-sufficiency boolean, drift event list |
| HTTP evidence | `evidence/work/{step}/{NN}-{outcome}.json` | One file per call, request + response, redacted |
| Latency baselines | `evidence/work/latency/{endpoint}.json` | p50/p95/p99 per endpoint |
| Webhooks captured | `evidence/work/webhooks/delivery-{event_id}.json` | Each Kira delivery with signature, body, timestamps |
| Observations | `evidence/work/observations.md` | Engineer's running notes per finding candidate |
| Full-stack evaluation | `evidence/work/fullstack-evaluation.md` | Hosted pages, payment links, SDK, redirects, iframe/CSP, mobile |

### Phase 3 — Adversarial Testing
| Artifact | Path | What to check |
|---|---|---|
| Abuse scenarios | `evidence/analysis/06-abuse-scenarios.md` | Functional-tester catalogue |
| Abuse harnesses | `evidence/work/abuse/{slug}/run.py` + `evidence/work/abuse/{slug}/README.md` | Reproducible Python harness per scenario, README explains setup |
| Security audit | `evidence/analysis/05-security-audit.md` | OWASP API Top 10 coverage table |
| Security harnesses | `evidence/work/security/{slug}/` | pytest harnesses per OWASP finding (or curl-based for TLS/header probes) |
| Stress / load | `evidence/work/automation/load/{slug}.js` (k6) or `.../locustfile.py` | Per-endpoint load curves, recovery behavior |
| Contract tests | `evidence/work/automation/contract/` | Schemathesis / Pact runs |

### Cross-cutting / Always
| Artifact | Path | What to check |
|---|---|---|
| README | `README.md` | Top-5 ranking, severities, pillars, "why this matters to a client" lines |
| Feature files | `features/*.feature` | Gherkin precision, tags, evidence + automation references, scenario coverage |
| Automation behind features | `evidence/work/automation/{slug}/` | Runnable scripts backing each `.feature` |
| CLAUDE.md | `CLAUDE.md` | Key rules, phase methodology, agent roster, repo structure |
| Decision log | `evidence/analysis/decision-log.md` | The DEC ledger |
| Prompt log | `evidence/ai/prompt-log.md` | Every prompt in ES + EN |
| Any new files | `evidence/work/*`, `features/*` | Scan for new artifacts created since last `/proc_comment` run |

## Rules

### Process
- The comments file is an INBOX — process and clear. The decision-log is the permanent record.
- ALWAYS launch agents — never apply changes yourself without agent validation (exceptions: methodology updates to CLAUDE.md and DEC entries themselves, which the orchestrator handles).
- ALWAYS read before editing — never assume current content.
- If a comment is ambiguous, ask the user to clarify BEFORE processing.
- If a comment contradicts a previous decision, flag the conflict in the DEC entry.
- Update the prompt log in BOTH Spanish and English.

### Phase coherence
- **Don't jump phases** without flagging (see Step 2).
- Phase 2 DEVELOP/EXECUTE work must instrument `integration-log.md` with iteration count + doc-sufficiency + doc-vs-runtime drift events per endpoint.
- Phase 3 DEVELOP/EXECUTE work must reference Phase 2 evidence as a prerequisite (you can't security-test an endpoint you haven't validated).

### Test design / develop / execute
- Every DEVELOP DEC must specify the exact test framework and target file path.
- Every Python harness must: (a) load credentials from `.env` (never hardcoded), (b) use `_redact.py` for logging, (c) write evidence to a deterministic path, (d) be runnable with `python -m pytest {path}` or `python {path}`.
- Every `.feature` file must have a backing automation script — Gherkin without automation is incomplete.
- Each test that successfully reproduces a finding promotes that finding to a top-5 candidate via a REFINE DEC.

### Specificity & evidence
- **BDD specificity rule:** every change touching a `.feature` file must preserve or improve specificity — no step may become more vague.
- **Evidence integrity rule:** if a finding changes, the `.feature` file's `# Evidence:` and `# Automation:` references and the README's evidence link must all be re-validated.
- **Severity ↔ rank rule:** README top-5 ranking must reflect severities (CRITICAL > HIGH > MEDIUM > LOW). If REFINE changes severity, re-check the ranking.
- **GAP traceability:** every `.feature` file must cite the source GAP-NN from `flow-design.md` § 6 (or note `GAP — new`).

### Future-work propagation
- Comments apply to EXISTING artifacts AND to ALL FUTURE development (new findings, new feature files, new harnesses, new evidence).
- If a comment creates a new rule for future work, add it to `CLAUDE.md` under "Key Rules" or "Known API Behaviors" or "Project Methodology."

### Secret hygiene
- **NEVER commit secrets** — if a comment proposes including a real token/key in evidence, push back and propose redaction via `_redact.py`.
- If you discover an unredacted secret in evidence during cross-validation, create a CRITICAL follow-up DEC and redact immediately.
