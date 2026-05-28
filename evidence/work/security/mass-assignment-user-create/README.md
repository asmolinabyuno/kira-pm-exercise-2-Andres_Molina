# Probe 2 — Mass Assignment on `POST /v1/users`

**OWASP API Top 10 mapping:** API3:2023 — Broken Object Property Level Authorization (mass assignment side)
**Severity:** HIGH (one HIGH input field), otherwise solid posture
**Status:** **Mostly safe; ONE finding — `verification_mode` is integrator-settable**

## Question answered

DRIFT-4 noted Kira silently accepts undocumented fields. Phase-3 question: **can an integrator escalate trust state via the create body?**

Answer: **Largely NO, with one HIGH exception.**

## Test matrix (results)

| # | Field sent | Server response | Verdict |
|---|---|---|---|
| T1 | `verification_status: "APPROVED"` | server returns `"unverified"` | SAFE — server-controlled |
| T2 | `status: "ACTIVE"` | 400 enum mismatch (`active\|inactive\|suspended`) | SAFE — field validated |
| T3 | `client_id: "<foreign>"` | 201; field not echoed | SAFE — silently stripped |
| T4 | `verification_mode: "manual"` | 400 enum mismatch | SAFE for `manual`… |
| **E4** | **`verification_mode: "verification_link"`** | **201; field echoed back as `verification_link`** | **HIGH — accepted** |
| T5 | `verified_at: "2000-01-01T00:00:00Z"` | 201; field not echoed | SAFE |
| T6 | `eligible_products: [{… eligible:true}]` | 201; server returned its own computed list, all `eligible:false` | SAFE — server-controlled |
| T7 | `missing_fields: {}` + `verification_triggered: true` | 201; server returned its own computed `missing_fields` and `verification_triggered: false` | SAFE |
| T8 | `is_admin: true, role: "admin"` | 201; fields not echoed | SAFE |
| T9 | `fee_override: 0` / `fees: {…}` | 201; fields not echoed | SAFE |
| T10 | `id: <chosen-uuid>` | 201; server assigned its own UUID | SAFE |

## The HIGH finding — `verification_mode`

POST /v1/users **accepts `verification_mode: "verification_link"` and persists it on the user**. (Default value is `"automatic"`.) When set to `verification_link`, the integrator presumably bypasses the immediate KYB calculation and switches to a flow where the end user receives an email/SMS with a verification link.

### Attack vector

An attacker who briefly compromises an `x-api-key` + Bearer pair can:
1. Create users with `verification_mode: "verification_link"` instead of the integrator's default `automatic`. This means Kira sends a "complete your KYB" email/link to whatever email address the attacker put in the body — which might be a victim's email, used for phishing-by-proxy (the recipient sees a legitimate Kira-domain email arriving and may click through).
2. Or simply switch all newly-created users into a state that diverges from the integrator's UI assumptions. If the integrator polls or webhooks for "verification complete" but their analytics filter on `verification_mode == automatic`, the attacker-created users are invisible.

### Why this is HIGH not CRITICAL

- `verification_status` itself (the actual trust state) is NOT settable — the server returns `unverified` regardless of what we send (confirmed).
- The attacker still needs valid credentials to call POST /v1/users; this is not a no-auth exploit.
- The "verification link" delivery may not actually fire in sandbox (we didn't trigger and capture a victim-email send), so the phishing-by-proxy is theoretical until verified.

### Reproduction

```bash
python3 evidence/work/security/mass-assignment-user-create/probe_mass_assignment.py
python3 evidence/work/security/mass-assignment-user-create/probe_enum_inputs.py
```

Read `02-enum-input-results.json` — see entries E4 and E5.

## Expected hardened API

- Reject any request that sets `verification_mode` if the integrator's account-level config is `automatic`; or require an additional capability/scope claim in the JWT to switch modes.
- Strip `verification_mode` from the request body at the schema level, derive only from the integrator's config.

## Observed Kira behavior

- 9 of 10 mass-assignment vectors safely rejected/stripped (good).
- `verification_mode` is the one exposed knob.

## Impact

- Workflow divergence: attacker can route a victim through a different verification path than the integrator's UI expects.
- Possible phishing amplification via the email/SMS verification-link delivery (un-confirmed).
- Subtle audit-log drift: when the integrator's CSV exports filter on `verification_mode = automatic`, attacker-created users are invisible.

## Remediation hint

Make `verification_mode` server-controlled (derived from client config), not a request-body field. If it must be a request field, gate it behind an explicit scope/permission.

## Files

- `probe_mass_assignment.py` + `01-mass-assignment-results.json`
- `probe_enum_inputs.py` + `02-enum-input-results.json`
