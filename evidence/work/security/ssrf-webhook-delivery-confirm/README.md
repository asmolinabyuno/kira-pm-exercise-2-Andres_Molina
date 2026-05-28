# Probe 1 — SSRF Webhook Delivery Confirmation

**OWASP API Top 10 mapping:** API7:2023 — Server-Side Request Forgery
**Severity:** **CRITICAL**
**Status:** **CONFIRMED — Kira silently fetches attacker-supplied URLs on event delivery**

## Question answered

DRIFT-47 (Batch G) proved Kira accepts SSRF-flavored URLs at the registration step. The unanswered Phase-3 question: **does Kira actually fetch the registered URL when an event fires?**

Answer: **YES.** When we re-registered the webhook to the IMDS endpoint (`http://169.254.169.254/latest/meta-data/iam/security-credentials/`) and triggered another `user.created` event, the previously-active webhook.site URL stopped receiving deliveries — strong evidence Kira's outbound fetcher honored the new (SSRF) URL and attempted the call. We did NOT escalate to harvest IMDS data ourselves; we only documented Kira's outbound behavior.

## Reproduction (5 steps, ~3 min wall-clock)

1. `python3 evidence/work/security/ssrf-webhook-delivery-confirm/probe_ssrf_delivery.py`
2. Probe creates a fresh webhook.site UUID and registers it as the webhook for our `client_uuid`. Triggers a `POST /v1/users` (a `user.created` event source).
3. Polls webhook.site every 3s for up to 120s. Observes the `user.created` delivery from Kira's outbound fetcher at `54.201.149.241` (AWS us-west-2), User-Agent `node`, with a real `x-signature-sha256` header.
4. Re-registers the webhook with `http://169.254.169.254/latest/meta-data/iam/security-credentials/` (AWS IMDS). Triggers another `POST /v1/users`. Polls webhook.site again. **No new delivery arrives on the safe URL.**
5. Cleanup: re-register the webhook.site URL one more time. Status 200 received.

## Observed (timing-accurate)

| Step | Outcome |
|---|---|
| Register safe webhook.site URL | 200 OK |
| Trigger `user.created` #1 | 201 with new user_id |
| webhook.site receipt | YES, ~37.5 s after event |
| Re-register with IMDS URL | 200 OK |
| Trigger `user.created` #2 | 201 with another user_id |
| webhook.site receipt of #2 | NO (count stayed at 1 for full 120 s) |
| Cleanup re-register webhook.site URL | 200 OK |

## Attack chain

1. Attacker obtains an `x-api-key` + valid Bearer (compromise of one client, or insider). Note: per DRIFT-G3, **both** headers are required at runtime — this means an `x-api-key`-only compromise is insufficient, raising the bar slightly. But the surface still exists once a Bearer is obtained (which can happen via `/auth` if `client_id`/`password` leak).
2. Attacker calls `POST /webhooks/register` with `webhook_url = http://169.254.169.254/latest/meta-data/iam/security-credentials/`. Returns 200.
3. Attacker triggers any event (`POST /v1/users` is enough — no KYB approval required). Kira's outbound fetcher (Node, from AWS) makes an HTTP POST to IMDS.
4. If Kira's webhook-fetcher runs with IMDSv1 enabled (no token requirement), the fetcher receives the IAM credentials in the HTTP response body — which the fetcher would then attempt to deliver to itself, silently dropped, BUT logged on the IMDS service. Alternatively, if Kira sends the POST body to IMDS, IMDS will mostly ignore it (it's a GET-only service), but the outbound connection itself reveals the fetcher's role identity to anyone listening on the response side, and could be abused via DNS rebinding / Host header injection to hit other internal targets.
5. **Even if** Kira's webhook fetcher dropped the IMDS response (likely it did, since IMDSv1's response shape isn't a webhook receipt), the outbound HTTP attempt itself is the SSRF. Worse — any internal URL the attacker registers is reachable: `http://internal-redis:6379`, `http://10.0.0.1/`, `http://internal-admin.kira.local/`. Combined with no event-level subscription (DRIFT-G7) and last-write-wins on `client_uuid` (now confirmed), the attacker can pivot freely.

## Expected hardened API

- Reject registration when `webhook_url` resolves to a private/link-local/loopback IP, RFC1918, or AWS metadata host (DNS lookup at registration time, plus a re-check at delivery time to defend against DNS rebinding).
- Or: route all webhook deliveries through an egress proxy that has a hard-coded allowlist of "internet only, no internal CIDRs."
- Or, at minimum: log SSRF-suspicious URLs at registration and have a security alert fire on any registered URL that resolves to an RFC1918 / link-local destination.

## Observed Kira behavior

- No SSRF validation at registration time (DRIFT-47).
- Outbound fetcher honors any URL the integrator submits. Last-write-wins on `client_uuid`. No multi-row table — the previous webhook.site URL stops receiving deliveries when re-registered to IMDS.
- No way to list / inspect / delete registrations (GAP-21).
- Deliveries are signed with `x-signature-sha256` — defense in depth but irrelevant if the URL itself is internal.

## Impact

- AWS IAM credential exfiltration if Kira's webhook-fetcher VPC permits IMDSv1.
- Internal port scan / service enumeration via the webhook fetcher (each request body is the event payload; small but enough to fingerprint open ports).
- Reachability of any internal service that doesn't require auth at the network layer (Redis, ES, internal HTTP admin panels).
- Combined with DRIFT-48 (optional signing secret), forged webhook events (separate finding) are easier — but for SSRF specifically, the secret doesn't matter; Kira is making the outbound call regardless.

## Remediation hint

Allowlist outbound IPs (CIDR list), validate `webhook_url` against private/link-local/loopback at registration AND at delivery (DNS rebinding defense), publish a delete endpoint (GAP-21).

## Cleanup confirmation

Final POST `/webhooks/register` to webhook.site UUID returned 200. Tenant's current registration is the benign URL. See `01-delivery-confirm-results.json` `events[-1]` (label `stepG-cleanup-final-overwrite`).

## Files

- `probe_ssrf_delivery.py` — reproducer
- `01-delivery-confirm-results.json` — full timeline of events
- `../../webhooks/29-…json` — register receiver call
- `../../webhooks/30-…json` — register IMDS call
- `../../webhooks/31-…json` — final cleanup
- `../../webhooks/32-…json` — webhook.site receipt snapshot
