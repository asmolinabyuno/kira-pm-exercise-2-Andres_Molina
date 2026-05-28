# PM Exercise 2 of 3 — API Integration & Error Hunt

**Time-box:** 2 days. **Window:** Wed 9am CST → Thu 11:59pm CST. **Format:** GitHub repo link.

## Why this exercise
Every Kira client lives or dies on how fast our API gets them to production. Your job as PM is to *feel* that path — not read about it. You will integrate the sandbox yourself, find the things that break or confuse, and write the acceptance criteria an engineer would need to fix them. The output is the same thing we ask of our best engineers: a small repo with BDD specs that name the gap precisely.

## Required: build with AI (especially Claude Code)
**This is mandatory, not a nice-to-have.** Use [Claude Code](https://claude.com/claude-code) (CLI), Claude.ai, or both — but AI must do real work in your loop: exploring the docs, drafting requests, writing BDD scenarios, pressure-testing your prioritization. PMs at Kira ship with AI every day; this exercise is also us watching how you think *with* a model. Save your key prompts and Claude Code session transcripts to `evidence/ai/` in the repo. We grade *how* you use AI, not whether — copy-paste is obvious; iterating with the model is the signal.

## What you get
1. **Sandbox API keys** — credentials in your 1Password vault under `kira-sandbox-pm-exercise`.
2. **Documentation** — [docs.kira.finance](https://docs.kira.finance) + Postman collection link in the vault note.
3. **Freedom to mock everything** — make up the business, the UBOs, the documents. Use fake names, fake IDs, fake addresses. Sandbox accepts it. Don't waste time hunting for "realistic" data — spend it on the integration.

## What to do
1. **Integrate.** Pick any stack (curl, Postman, Python, n8n, no-code — your call). Run at minimum: create customer → submit KYB → create virtual account → simulate inbound deposit → initiate payout. Capture every request/response.
2. **Hunt the top 5 errors.** Rank by *integrator impact*: which gaps would cost a real client the most time, cause silent breakage, or block go-live? Bias toward issues that are invisible from inside Kira (undocumented fields, missing version headers, vague error bodies, enum mismatches, no idempotency guidance, etc.). Quantity is not the point — sharpness of prioritization is.
3. **Write BDD specs.** One `.feature` file per finding, in Gherkin (`Given / When / Then`). Each scenario must be concrete enough that an engineer could turn it into a failing test without asking you a question.

## Deliverable
A public GitHub repo named `kira-pm-exercise-2-<yourname>` containing:
- `README.md` — your top 5 findings ranked, with a one-line "why this matters to a client" for each.
- `features/` — one `.feature` file per finding.
- `evidence/` — raw request/response logs, screenshots, or Postman exports backing each finding.
- `evidence/ai/` — prompts, Claude Code transcripts, or screenshots of the exchanges that shaped your thinking. Required.

Drop the repo link in your Slack channel by EOD Thursday.

## How we'll grade it
- **Prioritization** (40%) — did you find the issues that actually hurt integrators, or just the cosmetic ones?
- **Specificity** (30%) — would an engineer know exactly what to build from your BDD?
- **Integration depth** (20%) — did you actually exercise the API, or skim the docs?
- **Communication** (10%) — did you reach out to @Nicolle (PD) and @Diego (Eng) in your channel to clarify what was ambiguous? PMs who silently guess get worse answers than PMs who ask. We will check the channel and DMs for evidence. Zero outreach is a flag, not a feature.

## Success metric this exercise ladders into
> **Time-to-first-successful-API-call < `[xx]` days; % of signed integrations that reach production and grow daily call volume month-over-month with zero rollbacks.**

If your findings would move either number, you're on the right track.

## BDD in 15 minutes (if it's new to you)
- [Cucumber: BDD 101](https://cucumber.io/docs/bdd/) — the canonical primer.
- [Martin Fowler — GivenWhenThen](https://martinfowler.com/bliki/GivenWhenThen.html) — short, opinionated.
- [Example: a good `.feature` file](https://github.com/cucumber/cucumber/wiki/Feature-Introduction) — what "good" looks like.

You do not need to make the tests *run*. You need to write scenarios precise enough that they *could* run.

## What's next
Exercise 3 (Friday 9am → Friday 11:59pm CST) closes the week — the open prompt. Different muscle entirely. Bring conviction, not artifacts.
