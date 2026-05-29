# Data Engineer Quality Review

Reviewer persona: `data-engineer` (HTTP consumer + raw evidence capture).
Scope: Integration Depth (20%) of the deliverable — reproducibility, evidence integrity, master ledger, latency baselines, probe scripts.
Method: read-only — no deliverable files modified. AST-parsed every probe, import-tested `run_flow.py` + `_redact.py`, ran `_redact.py` self-tests, swept all 427 evidence JSON files programmatically for redaction violations and PII smells.

---

## What's strong

- **`run_flow.py` is well-engineered as a base library for probes.** Clean separation: `auth()`, `capture()`, `fake_*_payload()` helpers; in-memory token; deep-copy redaction; `sys.path` shimmed so probes can import it regardless of cwd; obvious hard rules documented in module docstring ("never write raw secrets", "no hardcoded creds"). All 12 probe scripts import from it cleanly (verified via AST parse).
- **`_redact.py` is the right primitive.** Case-insensitive header matching, recursive body walk with deep-copy, last-resort regex (`_JWT_RE`, `_BEARER_RE`, `_LONG_TOKEN_RE`). Self-test runs end-to-end (`python3 _redact.py` → `_redact.py self-tests passed`). Mask format encodes length (`REDACTED(<n>)`) — engineers can sanity-check shape without leaking content.
- **Spot-check across 427 JSON evidence files: zero unredacted `Authorization` headers and zero unredacted `x-api-key` headers** (programmatic sweep). Zero JWT-shaped tokens anywhere in the tree (single regex match was inside `_redact.py` itself). No real-looking SSN/EIN patterns — fake values used throughout (`000-00-0000`, `00-0000000`, `TFAK900101AAA`).
- **Timestamps consistent.** All `captured_at` values are ISO-8601 with explicit `+00:00` offset. Status codes present on every per-call file; `elapsed_ms` present with 2-decimal rounding.
- **Master ledger is thorough.** `evidence/analysis/04-integration-log.md` carries all 53 canonical DRIFT entries with evidence paths, severity, doc-claim vs runtime-fact framing, and a per-endpoint narrative covering all 8 endpoint families. Drift renumber map (Original → Canonical → Origin batch) is present at lines 515–574 — full audit trail from `DRIFT-A1..G7` to `DRIFT-1..53`.
- **Batch logs preserved with merge banner.** Every `integration-log-batch-{A,B,C,E,G}.md` opens with a "MERGED INTO MASTER" callout that names the canonical IDs and links back to `evidence/analysis/04-integration-log.md` — cross-refs in both directions are intact.
- **Latency files admit their `n`.** `get_v1_banks.json` declares `n=4` with a note "p50/p95/p99 require N>=10" — honest. `post_auth_cold_warm.json` has `n=30` with `min/median/p95/p99/max`, cold-vs-warm ratio, sleep cadence, and the full sample array. Pagination latency file carries the offset/limit sweep matrices.
- **Probe scripts are self-contained and shareable.** Every probe loads `.env` via `dotenv` or via `run_flow`; no hardcoded credentials anywhere; all evidence written through redacting `capture()` helpers (with the exception called out below).
- **`requirements.txt` declares the only two non-stdlib deps (`httpx>=0.27`, `python-dotenv>=1.0`).** Fresh integrator can `pip install -r requirements.txt` and go.

## What needs fixing — BLOCKING

None. No unmasked Kira credentials (api key, JWT, refresh token, client_secret) found in any evidence file. Reproducibility prerequisites are in place. Master ledger is internally consistent. **The deliverable can ship from a data-engineering standpoint.**

## What should improve — SHOULD-FIX

1. **`evidence/work/security/**` and a few `evidence/work/abuse/**` files bypass the shared `capture()` helper and write raw response headers, leaking the Cloudflare `set-cookie: __cf_bm=...` value.** Counted 24 leaks across:
   - `evidence/work/security/security-headers-and-tls/01-headers-authenticated-get.json`
   - `evidence/work/security/security-headers-and-tls/02-cors-preflight.json`
   - `evidence/work/security/security-headers-and-tls/04-unauth-error.json`
   - `evidence/work/security/info-disclosure-account-details/01-disclosure-sweep.json` (12 nested attempts)
   - `evidence/work/security/jwt-attack-suite/02-attack-results.json` (10 nested attempts under `attempts[].response_headers.set-cookie`)
   `__cf_bm` is a Cloudflare bot-management cookie scoped to `balampay.com` — it is server-set and not a Kira credential, but `set-cookie` IS in `SECRET_HEADER_NAMES` in `_redact.py` and the deliverable's own redaction policy says it should be masked. Fix: route those scripts through `_redact.redact_headers(...)` before persisting (or call `capture()` from `run_flow.py`). One-line fix per file at write time. Not blocking publication but inconsistent with stated policy.
2. **DRIFT-26 has two `### DRIFT-26` headers in `evidence/analysis/04-integration-log.md`** — line 242 (placeholder for the reserved `C1`) and line 247 (the actual `C2 → 26` content). The intent is explained inline ("placeholder slot — see note below" at line 544 of the renumber map), but a markdown TOC generator or anchor link will collide. Either drop the placeholder header and keep only the prose note, or rename it to `### DRIFT-26 (placeholder, see below)` so anchors stay unique.
3. **`evidence/work/latency/get_v1_banks.json` has a 20-second outlier on 3 of 4 samples** (19925, 19947, 20151 vs 261 ms). The file notes only "Preliminary baseline, p95/p99 require N>=10" — it should also flag the outlier as a likely sandbox stall (`429`-without-Retry-After? cold connect?) so a downstream reader doesn't conclude the endpoint is structurally 20s. Add a 1-line note and ideally re-run N=10 against the working `country_code=CO` query so the median isn't dominated by 3 stalls.
4. **`run_flow.py` `__main__` only exercises auth.** It runs `auth()` and prints OK/FAILED. Given the persona spec ("Reproducible. `run_flow.py` re-runs end-to-end given fresh `.env`"), the main path should at least drive `auth → create_user → trigger verification` and link to the probe scripts as the deeper passes. Today a fresh integrator running `python3 evidence/work/run_flow.py` gets one HTTP call back. The probes deliver the rest but it's not obvious from the top-level entry point. Add a `--full` or `--batch=A|B|C|E|G` flag, or document the probe-script invocation order in the module docstring.
5. **Probe scripts each rebuild a near-duplicate of `capture()`** (`batch_A.py`, `batch_C.py`, `batch_G.py`). They each redact correctly but this is the surface that produced the security-folder leak above. Consolidating to `run_flow.capture()` (which Batch B and `revalidate_drift_1.py` already do) would close the divergence.
6. **22 of 427 JSON files have no `captured_at`** — these are aggregate/summary files (`_summary.json`, `_batch_G_summary.json`, `latency/*.json`). Not a correctness issue, but a single uniform schema across both per-call and aggregate files would make downstream tooling simpler.

## Reproducibility verdict

**YES, a fresh integrator with their own `.env` can re-run this work — with two caveats.**

Verified:
- `run_flow.py` + `_redact.py` import cleanly (`python3 -c "import run_flow"` succeeds).
- All 12 probe scripts AST-parse without error.
- `_redact.py` self-tests pass.
- `requirements.txt` is complete (`httpx`, `python-dotenv`).
- All probes resolve their imports via `sys.path` shims (work regardless of cwd).
- No hardcoded credentials anywhere; everything is `os.environ["KIRA_*"]`.
- Evidence write paths are consistent (`evidence/work/{family}/{NN}-{outcome}.json`).

Caveats:
- The fresh integrator needs the partner-distributed `kira-sandbox-integration-guide.docx` to understand why `.env` `KIRA_API_BASE_URL` uses `https://api.balampay.com` (no `/sandbox` prefix). `CLAUDE.md` calls this out, but a `.env.example` file is missing — the integrator must guess the env-var names. SHOULD-FIX: add `.env.example` with the four required keys (`KIRA_API_BASE_URL`, `KIRA_CLIENT_ID`, `KIRA_COGNITO_SECRET`, `KIRA_API_KEY`) and blank values.
- Some downstream batches (D, F, H) are blocked by sandbox state (DRIFT-23, DRIFT-45). These blockers are documented in the master log — reproducer hits the same wall, which is the correct outcome but should be loud at first-run.

## Evidence integrity verdict

**Spot-check (programmatic sweep over 427 files plus manual inspection of 10 across families):**

- Files manually inspected: `auth/01-fail-403.json`, `auth/02-success.json`, `users/06-success.json`, `recipients/01-success-201-spei.json`, `webhooks/01-fail-403-G0.1-...json`, `webhooks/14-success-ssrf-aws-imds.json`, `webhooks/23-success-G6.4-secret-null.json`, `security/jwt-attack-suite/02-attack-results.json`, `versioning/01-pin-no-prefix-success.json`, `abuse/idempotency-replay-race/A-same-key-same-body-w00.json`.
- Programmatic sweep across all 427: 0 unredacted `Authorization`, 0 unredacted `x-api-key`, 0 unredacted body secrets (`client_id`, `password`, `access_token`, `token`, `secret`, `client_secret`), 0 JWT-shaped strings, 0 real-looking SSN/EIN patterns.
- One literal-but-safe `"secret": "REDACTED"` in `webhooks/23-success-G6.4-secret-null.json` (manually redacted, not the standard `REDACTED(<n>)` form — confirmed safe by reading file: `client_uuid` was also hand-redacted to `<client_id-redacted>`).
- **Leak risk:** LOW. The 24 `__cf_bm` Cloudflare-bot-cookie leaks in `security/**` are server-set, scoped to `balampay.com`, useless to an external attacker, but are policy violations against the project's own `SECRET_HEADER_NAMES` list. Worth fixing for hygiene.

## Overall data-eng verdict

**Ship: YES.**

Reasoning:
- All four reproducibility prerequisites pass (`run_flow.py` imports, `_redact.py` self-tests pass, probes AST-parse, `requirements.txt` complete).
- 427 evidence files audited, no Kira credential leaks of any kind.
- Master ledger renumbering is sound (53 DRIFT entries, audit-trail map in place); the DRIFT-26 placeholder is a markdown anchor wart, not a data integrity bug.
- Latency files declare their `n` honestly and the `n<10` cases say so.
- Two SHOULD-FIX items (security-folder `__cf_bm` redaction + DRIFT-26 anchor) are hygiene, not correctness. Neither blocks the grader's ability to read the work.

The single most important data-eng follow-up after publish: **route the security probes through `run_flow.capture()` so the redaction policy is enforced uniformly** — it's a one-import-and-replace per probe and it closes the `set-cookie` policy hole.
