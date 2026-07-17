# TechMKYC — Complete Technical Deep-Dive

> **Purpose.** This document explains *every* moving part of the system: what each
> teammate built, how their component works internally, how the pieces connect, and
> exactly what happens end-to-end when a signal fires. It is written from the source,
> not the pitch — file names, function names, and data shapes are real.
>
> Read `README.md` first for the "why". This is the "how, in full".

---

## Table of contents

1. [System at a glance](#1-system-at-a-glance)
2. [The data contract (the shared language)](#2-the-data-contract-the-shared-language)
3. [Person 3 — Aditya · News / adverse-media agent](#3-person-3--aditya--news--adverse-media-agent)
4. [Person 1 — Mohita · Sanctions / watchlist agent](#4-person-1--mohita--sanctions--watchlist-agent)
5. [Person 2 — Vaibhav · Ambiguity agent (ER ladder) + orchestrator](#5-person-2--vaibhav--ambiguity-agent-er-ladder--orchestrator)
6. [Person 4 — Sneha · Investigation agent + SAR](#6-person-4--sneha--investigation-agent--sar)
7. [Person 5 — Samaksh · Sink, read-API, dashboard, alerts, demo](#7-person-5--samaksh--sink-read-api-dashboard-alerts-demo)
8. [The connection points (exact HTTP contracts)](#8-the-connection-points-exact-http-contracts)
9. [Two end-to-end walkthroughs](#9-two-end-to-end-walkthroughs)
10. [Processes, ports & startup order](#10-processes-ports--startup-order)
11. [Data stores](#11-data-stores)
12. [Guarantees & failure modes](#12-guarantees--failure-modes)
13. [Where the LLMs are (and their fallbacks)](#13-where-the-llms-are-and-their-fallbacks)

---

## 1. System at a glance

Five components, three processes, one shared data contract, one SQLite sink.

```
 PRODUCERS (own clocks, HTTP)          PIPELINE (one process, in-memory)         CONSUMER
 ┌────────────────────────┐            ┌───────────────────────────────────┐    ┌──────────────┐
 │ News agent      :8002  │─/signals/  │ investigation_agent          :8001│    │ Flutter app  │
 │  scan→ER→triage→emit   │  ingest ──▶│  ingest → resolve(ER ladder) →    │    │  (Chrome)    │
 └────────────────────────┘            │  assess → investigate → draft SAR │    └──────▲───────┘
 ┌────────────────────────┐  /api/     │  → persist Case+SAR+Audit         │           │ JSON
 │ Sanctions agent        │─ingest ───▶│                    │              │           │
 │  screen→hit            │            └────────────────────┼──────────────┘           │
 └────────────────────────┘                                 ▼                          │
                                              ckyc.db (SQLite sink)  ──▶  read-API :8787
                                              append-only audit trail      api/server.py
```

- **Producers** (News, Sanctions) run on their own schedules and *push* events over HTTP.
- The **pipeline** is a single FastAPI process. Inside it, stages hand off typed
  Pydantic objects via **direct function calls** — no DB or bus between stages.
- The **sink** (`ckyc.db`) is written **once, at the end** of each run.
- The **read-API** (`api/server.py`, Python stdlib only) projects the stored `Case`
  blobs into the JSON the Flutter app parses, handles reviewer writes, renders the
  SAR to HTML/PDF, and sends Gmail alerts.
- The **dashboard** is the human reviewer's cockpit.

---

## 2. The data contract (the shared language)

**File:** `investigation_agent/contracts/models.py` — **owned by Vaibhav, edited by no one else.**
Every component produces and consumes *these* Pydantic objects and nothing else. This
is what let five people build in parallel without breaking each other.

| Model | Meaning | Produced by |
|---|---|---|
| `Customer` | A row in the bank's book — `client_id`, `client_name`, `client_type`, `pan?`, `sector`, `branch`, `exposure_inr`, dates. Deliberately messy (typos, missing PAN). | The book (fixtures) |
| `WatchlistEntry` | The canonical reference side — `watchlist_id`, `list`, `name`, `aliases`, `alias_quality`, `pan?`, `status`, `order_id?`, `source_url`. 100% clean. | Mohita |
| `Signal` | The atomic event that **starts the pipeline** — `signal_type` (`ADVERSE_MEDIA`/`WATCHLIST_DELTA`), `headline`, `source`, `severity`, `content_hash`, `mentioned_names` (extracted, **not** resolved). | Aditya + Mohita |
| `Candidate` | One (customer × entry) resolution attempt — `match_method`, `confidence`, `decision` (`CONFIRMED`/`AMBIGUOUS`/`REJECTED`), and **`rejection_reason` (mandatory on REJECTED)**. | Vaibhav |
| `Evidence` | A single factual claim — `status` (`CONFIRMED`/`CORRELATED`/`MISSING`), `claim`, `source_*`, cited inline as `[EV-nnn]`. | Sneha |
| `RiskAssessment` | The scoring output — `prior_tier`, `tier`, `score`, `gates_fired`, `suppressions`, `evidence`, `explanation`. | Vaibhav (scoring) |
| `SAR` | The report — `sections{}`, `evidence[]`, `unverified_claims[]`, `citation_coverage`, `status`. | Sneha |
| `Case` | The object the UI renders — `tier`, `status`, `timeline[]`, `sar?`, `reviewer_actions[]`. | Orchestrator |
| `AuditEvent` | **Append-only** trail row — `actor`, `action`, `object_*`, `rationale`. Both the risk timeline and the audit log derive from these. | Everyone |

**Key enums:**
- `Tier = NONE · MONITOR · EDD_LITE · EDD · HIGH · CRITICAL` (in the UI, `EDD` →
  "Enhanced Review", `EDD_LITE` → "Standard Review"; wire values unchanged).
- `MatchMethod` includes the deterministic verdicts: `PAN_EXACT`,
  `TYPE_MISMATCH_REJECT`, `PAN_MISMATCH_REJECT`, `ALIAS_BARE_REJECT`,
  `CROSS_LIST_NO_LINK`, plus `NAME_EXACT`, `PHONETIC`, `FUZZY`, `LLM_ADJUDICATED`.
- `EvidenceStatus = CONFIRMED · CORRELATED · MISSING` — **never collapsed** (the
  problem statement requires the three be kept separate).

> **Design rule:** intermediate `Signal`/`Candidate`/`RiskAssessment` objects are
> **never persisted as their own rows**. They flow in memory and, where the UI needs
> them, ride *embedded inside the `Case` JSON` blob.

---

## 3. Person 3 — Aditya · News / adverse-media agent

**Folder:** `news_agent/` · **Service:** FastAPI on **:8002** · **DB:** `news_agent/signals/signals.db`

### Responsibility
Continuously scan news for the watched entities, decide (a) *is this article about our
entity?* and (b) *is it genuinely adverse?*, and emit only true adverse signals
downstream. Everything benign or about a same-named stranger is dropped here.

### Files
| File | Role |
|---|---|
| `signals/main.py` | Mounts the FastAPI router |
| `signals/router.py` | Endpoints + the **APScheduler** background scan loop |
| `signals/kyc_list.py` | The watchlist of entities to scan (seeded from the shared customer book) |
| `signals/news_fetcher.py` | Fetches articles (NewsAPI live, or bundled mock corpus) |
| `signals/triage_agent.py` | **The AI** — 2-stage ER + adverse triage (Groq, with keyless fallback) |
| `signals/scanner.py` | Deterministic orchestration of one scan cycle |
| `signals/emitter.py` | Sends the confirmed `Signal` downstream + local JSONL audit |
| `signals/database.py` | SQLite: articles, resolutions, signals, audit |
| `signals/security.py` | `X-API-Key` auth, per-IP rate-limit, input sanitisation |

### Internal flow (one scan cycle — `scanner.run_scan`)
1. **List entities** to scan (`kyc_list.get_all()`). On startup the watchlist is seeded
   from the *shared dataset* (the same customer book the ambiguity agent resolves against).
2. **Fetch** news per entity: `news_fetcher.fetch(name, aliases)`.
3. **Deduplicate**: `save_article()` returns `False` for an already-seen hash → skip.
4. **Analyse** each new article: `triage_agent.analyse(article, entity)` →
   - **Stage 1 · Entity Resolution** (`run_entity_resolution`): "is this article about
     *our* entity, or a same-named stranger?" Groq `llama-3.3-70b` (temperature 0.1) →
     verdict `confirmed` / `false_positive` / `needs_review` + confidence + one-line
     evidence. `false_positive` → **suppressed**; `needs_review` → dropped to a human queue.
   - **Stage 2 · Adverse triage** (`run_triage`, only if Stage 1 = confirmed): "is this
     genuinely adverse?" → `is_adverse`, `severity` (low/medium/high/critical),
     confidence, reasoning. A `Signal` is emitted **only if `is_adverse` and
     `confidence ≥ 0.70`**. Benign (a board appointment, a product launch, the company
     *reporting* fraud as a victim) → `None`, dropped.
5. **Save + emit** (`emitter.emit`): appends to `signals_log.jsonl` (local audit) **and**
   `POST`s the signal JSON to `CORE_API_URL` → the pipeline's `/signals/ingest`.

### Keyless fallback (demo insurance)
`triage_agent` checks `GROQ_API_KEY`. With **no key**, both stages degrade to
deterministic heuristics: ER matches the watched name **verbatim** in the text
(`_heuristic_er`); triage scans an ordered **adverse-keyword → severity** ladder
(`_heuristic_triage`, e.g. `terror`→critical, `launder`→high, `bribe`→medium). A dead
API key never silently emits nothing — the demo runs offline.

### What leaves the agent
A name-only, news-lineage JSON payload (its *own* `Signal` model — `entity_name`,
`severity` word, `triage_reasoning`, no PAN). The pipeline's ingest adapter translates
it into the shared contract (see §8).

---

## 4. Person 1 — Mohita · Sanctions / watchlist agent

**Folder:** `Sanctions_agent/` · **Runs as:** a monitor process (one pass in the demo)

### Responsibility
Own the canonical watchlist reference data (SEBI/NSE debarred, UAPA, Sabha PEP), and
stream "a sanction was imposed" events, screening each against the customer book. Each
hit is handed to the ambiguity agent for adjudication.

### Files
| File | Role |
|---|---|
| `watchlist/build.py` | Builds the watchlist artifact from source data |
| `watchlist/load.py` | Loads `WatchlistEntry` objects |
| `watchlist/index.py` | `ScreeningIndex` — deterministic candidate lookup |
| `watchlist/monitor.py` | The near-real-time monitor: find hits, POST them |
| `watchlist/replay.py` | Streams real NSE-circular deltas (when the artifact is built) |

### `ScreeningIndex` (`watchlist/index.py`)
Inverted indices over the watchlist: **by PAN**, **by normalised name**, **by phonetic
(soundex)**, and **by surname block**. Critically, **bare-token aliases are excluded
from candidate expansion** (`alias_quality == "bare_token"`) — a single token like
"Salim" must never expand a search on its own. `candidates(name, pan)` prioritises PAN
(exact → single entry), then name, then phonetic, then surname block, and caps the pool
at 49.

> Soundex here is a *blocking* key only — it never decides a match; the resolver does.

### The monitor (`watchlist/monitor.py`)
1. Load `WatchlistEntry` + `Customer` lists.
2. `find_hits()`: order active sanctions chronologically by `_effective_dt` (last_change
   → order_date → first_seen). For each active entry, for each customer, if
   `ScreeningIndex.candidates(customer)` surfaces that entry → yield a **`SanctionHit`**.
3. For each hit, `post_hit()` → `POST /api/ingest` on the pipeline (:8001), with payload
   `{customer, candidates:[entry], trigger}`. `--verify-only` hits `/api/verify` instead
   (verdict only, nothing persisted). `--dry-run` just prints.
4. Every transport failure **degrades** (returns `None`) — one unreachable call never
   kills the monitor.

---

## 5. Person 2 — Vaibhav · Ambiguity agent (ER ladder) + orchestrator

**Folder:** `investigation_agent/core/` + `contracts/` · **Runs inside** the pipeline (:8001)

This is the heart: turn "a name collided" into a **decision on identity**, deterministically.

### 5.1 Blocking — `core/blocking.py` (Rung 0)
`Blocker` builds inverted indices over ~18k watchlist entries (`by_pan`, `by_surname`,
`by_fi_surname`, `by_phon_surname`, `by_phon_full`, using `jellyfish.metaphone`).
`candidates(name, pan)` returns a small blocked set (**target < 50/customer**) so the
resolver never compares a customer against the whole list. Blocking only *widens recall*
of the candidate set — it never decides anything.

### 5.2 The resolver — `core/resolver.py` (Rungs 1–3)
`resolve(customer, candidates)` returns one `Candidate` per meaningful pair, each with a
`decision` and (for rejects) a plain-language `rejection_reason`:

| Rung | Condition | Result | `match_method` |
|---|---|---|---|
| **1** | Customer PAN == entry PAN | **CONFIRMED**, confidence 1.0 | `PAN_EXACT` |
| **2** | Name matches, both PANs present, PAN 4th-char type differs (e.g. entry PAN is a Company `C`, customer is Individual) | **REJECTED** | `TYPE_MISMATCH_REJECT` |
| **3** | Name matches, both PANs present, PANs differ | **REJECTED** — "distinct entities despite identical name" | `PAN_MISMATCH_REJECT` |
| **(+)** | Name matches but PAN can't adjudicate (one side has no PAN — PEP/UAPA lists carry none) | **CONFIRMED (provisional)**, confidence 0.7 | `NAME_EXACT` |

The **PAN 4th character encodes holder type** (`P`=Individual, `C`=Company, `H`=HUF …),
giving a second deterministic gate. **Rung 1 is bidirectional**: a shared PAN confirms a
match *even when the recorded name is noised* — this is how typo-broken true positives
are recovered (and why recall goes **up** while alerts go **down**).

> **REJECTED candidates are the product.** Their `rejection_reason` populates the
> suppression log — the headline metric.

### 5.3 Verify — `core/verify.py`
`verify_hit(customer, candidates)` runs `resolve` and summarises a single verdict:
`CONFIRMED` (any confirm) → `AMBIGUOUS` → `SUPPRESSED` (only rejects) → `NO_MATCH`, plus
the list of `suppressions`. This is what the sanctions agent's `/api/ingest` and
`/api/verify` return.

### 5.4 Scoring / assessment
Gates are **deterministic** (e.g. `DEBARRED_PAN_EXACT_ACTIVE`, `UAPA_CONFIRMED` →
CRITICAL regardless of score); the soft `score` blends severity × credibility × recency ×
ER-confidence; the **`tier` is the output**. In the current build the orchestrator's
`_assess` delegates to `core.scoring.assess` if present, else uses a fixture/golden-backed
stub (`_stub_assessment`) that still records ER suppressions so the audit trail is complete.

### 5.5 The orchestrator — `core/orchestrator.py` (the in-memory pipeline)
`run_pipeline(customer, external_signals=…, extra_watchlist=…)` is the spine. Every stage
is wrapped in `safe()` (log + degrade to a default on any exception — one dead stage never
crashes the run):

```
load_watchlist()            (+ extra_watchlist from a sanctions hit)
fetch_and_triage(customer)  (+ external_signals from news/sanctions)
_resolve_stage()            = Blocker.candidates → resolve()      → list[Candidate]
_assess()                   = gates + soft score                 → RiskAssessment
   └─ if tier != NONE:
        needs_investigation = tier in {CRITICAL, EDD} or any AMBIGUOUS candidate
        investigate()       (only if needs_investigation)         → list[Evidence]
        draft_sar()                                               → SAR
build_case()                → Case (status from tier; timeline seeded)
+ AuditEvents (RESOLVED, ASSESSED, CASE_OPENED, one SIGNAL_INGESTED per trigger)
_merge_with_prior()         (union timeline, keep earliest opened_at, keep reviewer actions)
persist()                   → ckyc.db  (the ONLY DB write)
```

**Investigation is gated** — it's only spent where it can change the answer
(contextual/ambiguous tiers). A deterministic HIGH (PAN-exact, confidence 1.0) is already
settled and skips it. **`_merge_with_prior`** is why a case is a *living history*: repeat
ingests for the same customer union into the existing case (deduped timeline) instead of
clobbering it — tiers can even move *down* (a revoked order de-escalates).

---

## 6. Person 4 — Sneha · Investigation agent + SAR

**File:** `investigation_agent/core/investigate.py` · **Runs inside** the pipeline

### Why it's an agent, not a gate
The resolver decides on *identifiers*. But the lists where a miss is catastrophic carry
the *fewest* identifiers (adverse media has no PAN; UAPA has none at all). When the ladder
can only say AMBIGUOUS, the only path to confidence is **corroboration** — a
plan/execute/adjudicate loop.

### `investigate(assessment)` — four steps
1. **Gather (`_gather`)** — resolve the assessment's contributing signals, candidates, and
   watchlist entries (from this run's live data unioned with fixtures).
2. **Probe (`_probe`)** — deterministic corroboration checks; **each always yields a
   finding** (a hit is CORRELATED/CONFIRMED; a look-and-not-found is **MISSING** — "we
   looked"):
   - **Authority named?** Does adverse media name the designating authority (SEBI/NSE for
     debarred, NIA/MHA/UN for UAPA)? Whole-word match → CORRELATED, else MISSING.
   - **Identifier-level proof?** Does the watchlist entry carry a PAN? → CONFIRMED, else MISSING.
   - **Co-accused?** Another entity in the same regulatory `order_id`? → CORRELATED, else MISSING.
3. **Adjudicate** — weigh the findings and emit a verdict:
   - **With `ANTHROPIC_API_KEY`:** `_llm_adjudicate` calls **`claude-opus-4-8`** with
     **forced tool use** (`tool_choice` = `record_investigation`), so the output is a
     **schema-validated** `{verdict, findings}`. An off-schema response raises → fall back.
   - **Keyless / on any failure:** `_offline_adjudicate` picks the verdict from the
     strongest finding, deterministically.
   - The verdict space is `CONFIRMED / CORRELATED / INSUFFICIENT_EVIDENCE`.
     **`INSUFFICIENT_EVIDENCE` is a first-class answer** — when nothing corroborates, the
     agent emits *only* MISSING/low-confidence evidence and refuses to invent a finding.
     "An agent that always finds something is the failure mode we are avoiding."
4. **Emit (`_to_evidence`)** — each finding becomes an `Evidence` (`EV-INV-nnn`) carrying
   its `status`. The three statuses are **never merged**.

> The LLM only ever *classifies gathered facts* — it cannot introduce new ones. Identity
> itself is never decided by an LLM. And the orchestrator gates this call so no LLM is
> spent on a settled deterministic match.

### The SAR
`SAR` (contract) is a **structured artifact**: fixed `sections{}` (subject_identification,
basis_for_suspicion, chronology_of_events, evidence_summary, risk_assessment,
recommended_action), an `evidence[]` list, `unverified_claims[]` (**the refusal** — things
we could not source, disclosed rather than invented), and a measured `citation_coverage`.
Every claim carries an inline `[EV-nnn]` citation; in the demo the sections are authored
deterministically with real citations, and the generic pipeline reuses golden-fixture SARs
or synthesizes a minimal one.

---

## 7. Person 5 — Samaksh · Sink, read-API, dashboard, alerts, demo

**Folders:** `investigation_agent/db/`, `api/`, `lib/`, `run_backend.sh`

### 7.1 The sink — `investigation_agent/db/{schema.sql, store.py}`
Three tables only: `cases`, `sars`, `audit_events`. A `Case` is stored as **one row** with
a JSON `data` blob = the full contract object *plus* the embedded `assessments`, `customer`,
and `candidates` the UI needs (`store.persist`). Writes are **atomic** (`with conn:` — the
Case, its SAR, and all audit rows commit together or roll back together).

**Append-only audit is enforced, not conventional:**
```sql
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(FAIL, 'audit_events is append-only'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(FAIL, 'audit_events is append-only'); END;
```
Any UPDATE/DELETE **fails loudly**. `init_db()` rebuilds the schema each boot (DROP TABLE
doesn't trip the DELETE trigger). `INSERT OR REPLACE` on `cases` keys one case per case_id
— which is exactly why the orchestrator's `_merge_with_prior` exists.

### 7.2 The read-API — `api/server.py` (:8787, **Python standard library only**)
A thin adapter: it reads the pipeline's SQLite sink and **projects** each stored `Case`
blob into the six-screen JSON the Dart models parse. Projection helpers: `_cust`,
`_assessment`, `_candidate`, `_alert`, `_timeline`, `_evidence`, `_sar`, `_case` — each
tolerant of both blob shapes (the final UI shape and the raw pipeline shape).

Responsibilities beyond reads:
- **Reviewer writes** (the *only* mutations): `review_case` (BLACKLIST / DISMISS /
  **ESCALATE**) and `review_sar` (APPROVE / DENY) — each atomically updates the Case blob +
  the `sars` row and **appends one `human:{name}` audit row**.
- **SAR rendering**: fills `casefile_sar_exact_template.html` and serves it inline
  (`/sar/html`, preview) or prints it to **PDF via headless Chrome** (`/sar/pdf`).
- **Gmail alerts**: on a HIGH/CRITICAL time-skip, `send_alert_email` over SMTP-SSL.
- **LIVE/TEST mode**: `POST /api/mode` and `/api/demo/timeskip` forward to the pipeline's
  `/demo/*` and re-point every read at `ckyc_demo.db` (`current_db()`).

### 7.3 The dashboard — `lib/` (Flutter, runs in Chrome)
| Layer | File(s) | Role |
|---|---|---|
| Config/plumbing | `core/api.dart`, `core/router.dart`, `core/theme.dart`, `core/download*.dart` | Base URL, go_router routes, theme, web download/print bridge (`package:web`) |
| Models | `models/models.dart` | Dart mirrors of the contract (Alert, Entity360, Case, Sar, TimelineEvent, RiskTier, SarReport…) |
| Data | `data/repository.dart` | `ApiRepository` (live) + `DemoRepository` (offline) behind one interface, all Riverpod providers, `AlertConfig`/`DemoStatus` |
| Screens | `features/entities/*`, `features/report/*`, `features/audit/*`, `features/settings/*`, `features/auth/*` | Alert queue, case detail, SAR draft, reports, audit, settings, login |

State is **Riverpod**; every provider watches a `changesProvider` revision stream so a
write anywhere refreshes every screen. `DemoRepository` gives a fully offline path
(bundled fixtures) selectable with `--dart-define=USE_DEMO_DATA=true`.

### 7.4 Email alerts
- **Recipient** set in Settings → persisted to `api/.alert_config.json` (gitignored).
- **Sender** creds from `.env` (`ALERT_SMTP_USER` / `ALERT_SMTP_PASS`), loaded by a
  stdlib `.env` parser; never hardcoded.
- On a HIGH/CRITICAL time-skip, `_maybe_alert_on_timeskip` enriches the case (name, tier,
  exposure) and sends via `smtplib.SMTP_SSL('smtp.gmail.com', 465)`. **Best-effort**: an
  unreachable mail server never fails the pipeline; the outcome rides back to the UI.

### 7.5 Demo mode — `investigation_agent/api/demo.py`
The scripted **Vijay Mallya** scenario, pinned to the **real 2015–2017 chronology**
(`DEMO_T0 = 2015-11-13`). `start()` = phase 1 (Kingfisher default → EDD, SAR v1);
`timeskip()` = phase 2 (+~15 months: two more articles + the SEBI debarment → **CRITICAL**,
SAR v2). It runs the **real** agent functions (`resolve`, `verify_hit`, `investigate`,
`build_case`) against a **separate** sink (`ckyc_demo.db`) and narrates each hand-off to
the backend terminal — the live data is never touched.

---

## 8. The connection points (exact HTTP contracts)

### A. News agent → pipeline · `POST :8001/signals/ingest`
The news agent emits its **own** name-only JSON. Adapter: `api/ingest.py`.
```
{ "entity_name": "...", "headline": "...", "url": "...", "source_name": "...",
  "published_at": "...", "severity": "high", "confidence": 0.9, "triage_reasoning": "..." }
```
- `find_customers(entity_name)` — normalised exact match against the book. **Returns ALL
  matches** (two "Dipak Dwiwedi"s are two clients, each adjudicated separately — that
  ambiguity *is* the product). No match → `200 {matched:false}` (the emitter must never
  retry-loop on names outside the book).
- `news_signal_to_contract()` maps severity word → 0..1, keyword → `RiskTypology`, and
  builds a `content_hash`, producing a contract `Signal(ADVERSE_MEDIA)`.
- Each matched customer → `run_pipeline(customer, external_signals=[sig])`.

### B. Sanctions agent → pipeline · `POST :8001/api/ingest`
The monitor already screened the book, so the hit arrives as **contract objects**:
```
{ "customer": {…Customer…}, "candidates": [ {…WatchlistEntry…} ], "trigger": {…} }
```
- `verify_hit(customer, entries)` → verdict + suppressions.
- `sanctions_trigger_to_contract(trigger)` → `Signal(WATCHLIST_DELTA)`.
- `run_pipeline(customer, external_signals=[sig], extra_watchlist=entries)` → returns
  `{verdict, suppressions, case:{…summary…}}`.
- `POST /api/verify` is the same ER ladder but **verdict-only, nothing persisted**.

### C. Dashboard → read-API · `:8787/api/*`
`/api/alerts`, `/api/entity/{id}`, `/api/entity/{id}/timeline`, `/api/entity/{id}/case`,
`/api/entity/{id}/sar/html|pdf`, `/api/case/{id}`, `/api/suppressions`, `/api/reports`,
`/api/audit`, `/api/metrics`; writes `POST /api/case/{id}/review`,
`/api/case/{id}/sar/review`; `GET/POST /api/alert-config` (+ `/test`); `GET/POST /api/mode`,
`POST /api/demo/timeskip`. (Full list in `README.md` §10.)

### D. Read-API → pipeline (demo only) · `POST :8001/demo/start` / `/demo/timeskip`
Triggered when the dashboard toggles LIVE→TEST or presses the time-skip button.

---

## 9. Two end-to-end walkthroughs

### 9.1 An adverse-media signal (news path)
1. Scheduler fires `run_scan` → `news_fetcher.fetch("Vijay Mallya", aliases)`.
2. New article survives dedup → `triage_agent.analyse`:
   ER (Groq/heuristic) = **confirmed** → triage = **adverse, high, 0.9**.
3. `emitter.emit` → `POST :8001/signals/ingest` (name-only JSON) + `signals_log.jsonl`.
4. `find_customers("Vijay Mallya")` → `[C9001]`; `news_signal_to_contract` → `Signal`.
5. `run_pipeline(C9001, external_signals=[sig])`: blocking → `resolve` (no watchlist PAN
   yet → provisional / no confirm) → `_assess` → **EDD** (adverse-media gate) →
   `needs_investigation` (EDD) → `investigate` (authority named? PAN? →
   CORRELATED/MISSING) → `draft_sar` → `build_case` → audit rows → `persist` → `ckyc.db`.
6. Dashboard `/api/alerts` now shows **Vijay Mallya · Enhanced Review**; the case page
   shows the news event dated **13 Nov 2015**, the assessment, and SAR v1.

### 9.2 A sanctions hit (watchlist path) — the "two Dipak Dwiwedi" suppression
1. Monitor streams active sanctions; `ScreeningIndex.candidates` surfaces the SEBI entry
   for **both** same-named customers → two `SanctionHit`s.
2. `POST :8001/api/ingest` for each. `verify_hit`:
   - Customer A: PAN == entry PAN → `PAN_EXACT` **CONFIRMED** → verdict **CONFIRMED**.
   - Customer B: name matches, PANs differ → `PAN_MISMATCH_REJECT` **REJECTED** → verdict
     **SUPPRESSED**, with reason *"PAN … != … → distinct entities despite identical name."*
3. `run_pipeline` for A → gates fire → **HIGH/CRITICAL** → (CRITICAL) investigate → SAR →
   persist. B's suppression is recorded (the rejected candidate rides in the audit trail /
   suppression log) and **never raised as an alert**.
4. Dashboard: A appears in the queue; B appears only in **`/api/suppressions`** with its reason.

---

## 10. Processes, ports & startup order

`./run_backend.sh` (from repo root) starts everything in order:

| Step | What | Port | Command (essence) |
|---|---|---|---|
| 1 | Pipeline service (ambiguity + investigation) | **8001** | `uvicorn api.main:app` — `lifespan` seeds the sink from fixtures |
| 2 | News agent | **8002** | `uvicorn signals.main:app` — APScheduler starts |
| 3 | Sanctions monitor (one pass) | — | `python -m watchlist.monitor --base-url :8001` → `/api/ingest` |
| 4 | News scan trigger | — | `curl /signals/scan/trigger` → emit → `/signals/ingest` |
| 5 | Read-API adapter | **8787** | `CKYC_DB=investigation_agent/ckyc.db python3 api/server.py` |

Then, separately: `flutter run -d chrome` (the dashboard).

- The pipeline's `X-API-Key` for the news agent defaults to
  `signals-dev-key-change-in-production` (`SIGNALS_API_KEY`).
- The news emitter targets `CORE_API_URL` — point it at the pipeline's
  `:8001/signals/ingest`.

---

## 11. Data stores

| Store | Owner | Contents |
|---|---|---|
| `investigation_agent/ckyc.db` | Pipeline | LIVE sink: `cases`, `sars`, `audit_events` (append-only) |
| `investigation_agent/ckyc_demo.db` | Demo | TEST-mode sink (scripted scenario) — live data untouched |
| `news_agent/signals/signals.db` | News agent | articles, resolutions, signals, agent audit |
| `api/.alert_config.json` | Read-API | alert recipient (gitignored) |
| `.env` | Read-API | Gmail SMTP sender creds (gitignored) |
| `fixtures/customers.json`, `fixtures/watchlist.json` | Shared | the customer book + watchlist all agents read |

`run_backend.sh` wipes `news_agent/signals/signals.db` and `signals_log.jsonl` on boot so
signals re-emit for a fresh demo; the pipeline rebuilds its sink on startup.

---

## 12. Guarantees & failure modes

| Guarantee | Mechanism |
|---|---|
| One dead stage never kills a run | `safe(fn, default=…)` around every orchestrator stage |
| A dead API key never stops the demo | Deterministic fallbacks in `triage_agent` (news) and `investigate` (adjudication) |
| History cannot be rewritten | `RAISE(FAIL)` triggers on UPDATE/DELETE of `audit_events` |
| Case write is all-or-nothing | `with conn:` atomic transaction in `store.persist` |
| Repeat ingests don't clobber history | `_merge_with_prior` (union timeline, earliest open, keep reviewer actions) |
| No LLM on a settled match | Orchestrator gates `investigate` to CRITICAL/EDD/AMBIGUOUS only |
| LLM can't hallucinate structure | Forced tool-use (`record_investigation`); off-schema → reject → fallback |
| Email never blocks the pipeline | `_maybe_alert_on_timeskip` is best-effort; failure is reported, not raised |
| Same-name people stay separate | PAN ladder (Rungs 1–3) + bare-alias exclusion in both indices |

---

## 13. Where the LLMs are (and their fallbacks)

Exactly **two** LLM seams, both guarded; **identity is never decided by an LLM**.

| Seam | Model | Guard | Fallback |
|---|---|---|---|
| News ER + adverse triage | Groq `llama-3.3-70b` (temp 0.1) | Worst case emits a benign article; the ambiguity agent still gates it on identity | Deterministic keyword/verbatim heuristics (`_heuristic_er`, `_heuristic_triage`) |
| Investigation adjudication | Anthropic `claude-opus-4-8` | Forced tool-use → schema-validated; classifies *gathered facts* only; `INSUFFICIENT_EVIDENCE` is valid | Deterministic `_offline_adjudicate` over the same probes |

Everything else — the ER ladder, gates, blocking, persistence, audit, projections, PDF,
alerts, the dashboard — is deterministic code.

---

*Companion docs: `README.md` (overview + demo script), `docs/AGENT_CONNECTION.md`
(connection-point deep-dive), `investigation_agent/contracts/models.py` (the contract).*
