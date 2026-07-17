# TechMKYC — Limitations, Alternatives & Road to Production

> **Purpose & tone.** This is a deliberately candid engineering review of the system as
> built for the hackathon. It lists real flaws (from the source, not hypotheticals),
> explains design choices we'd defend against the obvious alternatives, and lays out
> what production-grade would actually require. Nothing here is a surprise to the team —
> writing it down is the point.
>
> Companion: `docs/TECHNICAL_DEEP_DIVE.md` (how everything works).

---

## Table of contents

1. [Known limitations & flaws](#1-known-limitations--flaws)
2. [Alternatives we considered — and why the current choice is better](#2-alternatives-we-considered--and-why-the-current-choice-is-better)
3. [The road to production-grade](#3-the-road-to-production-grade)

---

## 1. Known limitations & flaws

### 1.1 Correctness & completeness (the honest gaps)

- **Scoring is a stub.** The tier is *the* output of the system, but
  `core.scoring.assess` is not implemented — `orchestrator._assess` falls back to
  `_stub_assessment`, which returns a **golden-fixture** assessment for known clients or a
  `NONE`-tier record otherwise. So in the generic pipeline, tiering is fixture-driven, not
  a live gate + calibrated soft-score engine. The *demo* scenario hard-codes its tiers
  (EDD → CRITICAL) authentically, but the general path does not compute them.
- **SAR prose is not generated live.** `orchestrator.draft_sar` reuses a golden-fixture
  SAR when the subject matches, else synthesizes a minimal one. The rich, cited SAR
  sections a judge sees come from the **hand-authored demo** (`api/demo.py`) or fixtures.
  The **evidence chain** (`investigate()` → CONFIRMED/CORRELATED/MISSING) *is* genuinely
  generated; the narrative sections around it are not.
- **The ER ladder is Rungs 0–3 only.** Rungs 4–7 (alias-quality gate beyond bare-token,
  cross-list no-link, phonetic/fuzzy confirm, LLM adjudicator as a rung) are marked "later
  sessions" in `resolver.py`. Consequence: on the **no-PAN lists** (PEP/UAPA), a plain
  `NAME_EXACT` is surfaced as a **provisional CONFIRMED (confidence 0.7)** — a common name
  with no identifier can still raise. Precision on those lists rests on later rungs that
  don't exist yet.
- **News-path customer matching is exact-only.** `api/ingest.find_customers` resolves a
  news `entity_name` against the book by **normalised exact equality**. A typo'd or
  transliterated news name that doesn't exactly equal a customer name is silently missed —
  the very noise the PAN ladder handles on the sanctions path is *not* handled on the news
  path (news has no PAN to recover with).
- **Merge dedup is string-brittle.** `_merge_with_prior` dedups timeline events on
  `(timestamp-to-the-second, kind, summary)`. A re-run that phrases a summary slightly
  differently produces a duplicate timeline entry.
- **Audit grows unbounded on re-runs.** Re-running the pipeline for a customer appends a
  *fresh* audit trail every time (unique `audit_id` per emission). Correct for
  append-only integrity, but with no rotation/partitioning the table only grows.
- **Metrics are reported inconsistently.** `README.md` cites 474→293 alerts; the pipeline's
  `/api/metrics` returns a different cut (realistic fp 394→190). Both come from a
  **synthetic** eval cohort — directionally real, but not a measured production number.

### 1.2 Data realism

- **The customer book and watchlist are synthetic fixtures**, and news defaults to a
  **bundled mock corpus** (`USE_MOCK_NEWS`). No public dataset is a real bank's book;
  watchlist data follows real SEBI/UAPA *structure* but isn't a live feed. Everything is
  demonstrable and switchable to live APIs, but the numbers are lab numbers.
- **Three separate entity-resolution implementations** exist: the news agent's LLM ER
  (`triage_agent`), the sanctions agent's `ScreeningIndex` (soundex blocking), and the
  ambiguity agent's `Blocker` + `resolver` (metaphone blocking, PAN ladder). They share a
  goal but not code, and can drift.
- **Blocking uses single Metaphone, not Double Metaphone** (`jellyfish` limitation, noted
  in `blocking.py`). Fine because blocking only widens recall — but it's a stand-in.

### 1.3 Security & secrets

- **No authentication on the read-API.** `api/server.py` is `CORS: *` with no API key or
  token; any local caller can read cases and post reviewer decisions. The dashboard
  "login" is just a reviewer *name* (audit attribution), not real auth.
- **SMTP credentials live in a plaintext `.env`.** Gitignored and env-overridable (better
  than hardcoding), but it's a plaintext app password on disk, not a secrets manager, and
  the recipient is a single global address.
- **No encryption at rest, no PII minimisation, no retention policy.** The sink is a plain
  SQLite file with names/PANs in cleartext JSON blobs.

### 1.4 Scalability & operations

- **SQLite is a single-file, single-writer sink.** Concurrent reviewer writes serialise;
  `INSERT OR REPLACE` on `cases` means the merge logic is the *only* thing preventing a
  re-ingest from clobbering history — and merge runs only on the persist path.
- **The read-API is a stdlib `ThreadingHTTPServer`.** Great for zero-dependency portability
  and a demo; not a hardened ASGI deployment. **No pagination** — `/api/alerts` and
  `/api/audit` return whole tables.
- **PDF rendering shells out to a headless Chrome binary.** If Chrome isn't installed, the
  SAR PDF route fails (there's a clear error, but no fallback renderer).
- **Producers are fire-and-forget over HTTP with no retry/queue.** The news emitter and
  sanctions monitor degrade gracefully on a failed POST, but a dropped signal is simply
  lost until the next scan — there's no durable queue or dead-letter path.
- **Alerts fire on the demo time-skip, not on live-mode hits.** There's no hook inside
  `run_pipeline` to email when a *live* case crosses HIGH/CRITICAL; today it's wired to the
  demo/test trigger and the Settings test button.

### 1.5 UX & product

- No case assignment, comments, or collaboration; one global reviewer identity.
- No responsive/mobile layout tuning; built for a desktop Chrome demo.
- Suppression log is sourced two ways (pipeline reads `fixtures/candidates.json`; read-API
  rebuilds from audit/blobs) — they can disagree.

---

## 2. Alternatives we considered — and why the current choice is better

Each of these is a road we *could* have taken. For a compliance tool that must be
**explainable, reliable, and demoable**, the current choice wins — but the trade-off is
real and stated.

### 2.1 In-process pipeline + SQLite  ·  vs  ·  microservices + Postgres/Supabase
- **Alternative:** the repo actually *started* as five microservices around Supabase
  (`docs/schema.md` §1–6).
- **Why current is better here:** direct typed function calls between stages remove a whole
  class of failure modes (network partitions, serialization drift, partial writes, service
  discovery) and make the **Pydantic contract more load-bearing, not less**. One process
  boots in seconds and can't half-fail on stage 3. The DB is a *sink*, not a bus.
- **The trade-off we accept:** no independent horizontal scaling of stages, and the sink is
  a single writer. Acceptable at demo scale; the seams (`DATABASE_URL`, HTTP producers) are
  shaped so this can be undone later without rewriting logic.

### 2.2 Deterministic PAN ladder  ·  vs  ·  LLM-decided identity
- **Alternative:** let an LLM decide "is this the same person?" end-to-end.
- **Why current is better:** identity in KYC must be **auditable, reproducible, and
  cheap**. An exact-PAN match is confidence 1.0 with a one-line reason a regulator can read;
  an LLM verdict is non-deterministic, costs a call per pair, and can't be defended in an
  audit. We use the LLM only to **classify already-gathered corroboration**, never to decide
  identity.
- **Trade-off:** the ladder needs identifiers; where there are none (UAPA), we fall back to
  name + corroboration, which is exactly where precision is hardest (see §1.1).

### 2.3 Identifier-first matching  ·  vs  ·  fuzzy/ML name matching as the primary matcher
- **Alternative:** train/΅buy a name-matching model and rank everything by similarity.
- **Why current is better:** at India-scale name collision, name-only similarity is
  **structurally noisy** (baseline precision 0.169). PAN's 4th char even re-derives entity
  *type* for a second gate. Fuzzy/phonetic still exists — but at the **blocking** rung, where
  it only *nominates* candidates and never confirms alone.
- **Trade-off:** we depend on identifier coverage; ~18% of the book has no PAN, so those
  customers lean on the weaker rungs.

### 2.4 Direct function calls  ·  vs  ·  a message bus (Kafka) between stages
- **Alternative:** Kafka/PubSub between ER → assess → investigate.
- **Why current is better at this scale:** a bus adds brokers, consumer groups,
  at-least-once semantics, and ops burden for *zero* benefit when the stages run in one
  process on one box. It would make the demo *less* reliable.
- **Trade-off:** a bus is genuinely needed at production volume for backpressure and
  replay — which is exactly what the roadmap adds (§3.2).

### 2.5 Embed intermediates in the Case blob  ·  vs  ·  normalized tables per object
- **Alternative:** persist `signals`, `candidates`, `assessments` as their own rows.
- **Why current is better:** the UI reads **one row** and has everything it renders
  (timeline, evidence, SAR, suppressions). No joins, no schema churn as the contract evolves.
- **Trade-off:** you can't run analytical SQL over intermediates directly — they're inside
  JSON. Fine now; a warehouse ETL solves it later.

### 2.6 Headless-Chrome server-side PDF  ·  vs  ·  a client-side PDF library
- **Alternative:** generate the SAR PDF in Flutter with a `pdf`/`printing` package.
- **Why current is better:** Chrome renders the **exact** official HTML SAR template
  faithfully, and it's a dependency the demo already requires (`flutter run -d chrome`).
  Re-implementing the form layout in a PDF DSL is effort with a fidelity risk.
- **Trade-off:** a Chrome binary must be present on the server.

### 2.7 Gmail SMTP for alerts  ·  vs  ·  a transactional email provider
- **Alternative:** SES/SendGrid/Postmark from day one.
- **Why current is better for now:** `smtplib` is standard-library, works offline-of-a-SaaS,
  and needs one app password to demo. No new dependency, no account provisioning.
- **Trade-off:** no deliverability guarantees, no templating/analytics, single sender —
  strictly a demo channel (roadmap swaps it, §3.3).

### 2.8 Flutter (web)  ·  vs  ·  a React/TS SPA
- **Why current is fine:** one typed codebase that mirrors the Pydantic contract closely,
  targets web today and mobile later, with Riverpod giving clean reactive refresh.
- **Trade-off:** smaller hiring pool than React and a heavier web bundle; not a compliance
  concern.

---

## 3. The road to production-grade

Phased so each stage delivers standalone value. P0 is "make it real"; P3 is "make it smart".

### 3.1 P0 — Close the correctness gaps
- **Implement the real scoring engine**: deterministic gates + a *calibrated* soft score,
  replacing `_stub_assessment`. Unit-test each gate; add a scoring regression suite.
- **Implement a live `draft_sar` generator**: LLM-drafted sections with **enforced inline
  citations**, measured `citation_coverage`, and `unverified_claims` populated from MISSING
  evidence — replacing the fixture stub. Add golden-file tests.
- **Finish the ER ladder (Rungs 4–7)**: alias-quality gates, cross-list no-link, phonetic/
  fuzzy confirm, and an **LLM adjudicator as a rung** — so no-PAN name matches are reasoned
  about, not naively confirmed.
- **Harden the news→customer join**: fuzzy/phonetic customer resolution (with a human-review
  bucket) instead of exact-name-only.
- **Consolidate the three ER implementations** behind one shared normalization + blocking
  library so news, sanctions, and ambiguity can't drift.

### 3.2 P1 — Scale & reliability
- **Postgres sink** via the already-abstracted `DATABASE_URL`; connection pooling; Alembic
  migrations; move the JSON blob to `JSONB` with GIN indexes (or split hot fields into columns).
- **Durable streaming ingest** (Kafka/PubSub) with `content_hash`/`story_cluster_id` dedup,
  **idempotency keys**, retries with backoff, and a **dead-letter queue** — no dropped signals.
- **Real ASGI serving** for the read-API (uvicorn/gunicorn workers), **pagination**, caching,
  and rate-limiting; keep the stdlib server only as the offline demo mode.
- **Audit lifecycle**: partition/rotate `audit_events`, make re-run audit **idempotent**, and
  archive cold cases to a warehouse.

### 3.3 P2 — Security, compliance & alerting
- **AuthN/AuthZ**: OIDC/SSO login, **RBAC** (reviewer / senior / admin), maker–checker on
  terminal decisions, and multi-tenant isolation.
- **Secrets & data protection**: Vault/KMS for credentials, encryption at rest + in transit,
  PII minimisation, field-level access controls, and a data-retention policy.
- **Production alerting**: move to SES/SendGrid; add a live-mode hook in `run_pipeline` that
  fires when a case crosses HIGH/CRITICAL, with **fan-out** (email/Slack/Teams/webhook),
  dedup/throttling, and **escalation SLAs**.
- **Regulatory integration**: automated filing to **FIU-IND / goAML**, e-signature on
  approved SARs, and immutable retention (WORM storage) for filed reports.

### 3.4 P3 — Intelligence & operations
- **Human-feedback loop**: turn reviewer **dismissals/escalations** into training signal —
  auto-suggested suppression rules and negative examples (active learning), closing the
  "continuously improve" loop the contract already anticipates (`ReviewerAction`).
- **Model quality & governance**: an **LLM eval harness** with regression tests on the
  adjudicator, drift monitoring, **precision/recall dashboards over time**, **bias/fairness**
  checks on suppression, and published **model cards**.
- **Observability**: structured logging, Prometheus metrics, OpenTelemetry tracing across the
  producer→pipeline→sink path, and alerting on pipeline health.
- **Real data connectors**: core-banking customer feeds, and live watchlist refresh pipelines
  for **OFAC / UN / EU / Interpol / MCA** with provenance and freshness SLAs; more identifiers
  (passport, DIN/CIN, LEI, hashed Aadhaar) for multi-jurisdiction matching.
- **Delivery**: full CI (unit + integration + **contract tests on the Pydantic schema** +
  load tests + E2E), and blue-green/canary deploys.

---

### One-line summary

> The system is a **correct, explainable skeleton with a real spine** (deterministic ER +
> gated LLM corroboration + enforced append-only audit) and **stubbed muscles** (scoring and
> SAR-prose generation) plus **demo-grade edges** (synthetic data, no auth, SQLite, SMTP).
> The architecture choices are the *right* ones to keep at scale; the roadmap is mostly about
> replacing stubs, hardening the edges, and adding the governance a regulator would demand.
