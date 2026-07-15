# TechMKYC — Continuous KYC Autonomous Auditor

Built for **Code by Tech Mahindra — Challenge 3: Continuous KYC Autonomous Auditor.**

A network of five cooperating agents that continuously watches a bank's customer book
against sanctions lists and adverse media, **resolves name collisions on hard
identifiers instead of raising them as alerts**, investigates the matches that survive,
drafts a fully-cited SAR for human sign-off, and records every step in an
append-only audit trail. A Flutter dashboard is the human reviewer's cockpit.

---

## 1. The problem (and our thesis)

Banks re-check customers against watchlists **periodically** — quarterly or yearly.
Between refreshes, a customer can be sanctioned, debarred, or named in a fraud case
and nobody notices. The naive fix — screen everyone against everything continuously —
drowns compliance teams in **false positives**: most watchlist hits are *a different
person with the same name*.

**Our thesis: the product is not the alerts we raise — it's the alerts we refuse to
raise, each with a plain-language reason.** Screening India-scale names ("Amir Khan",
"Dipak Dwiwedi") without identifier-level disambiguation is noise generation. So the
system:

1. Watches **continuously** (news agent + sanctions agent, near-real-time),
2. **Disambiguates on hard identifiers** (PAN) before anything reaches a human,
3. **Investigates** what survives — corroborates, never invents,
4. Drafts a **SAR where every claim carries a citation** and unverifiable claims are
   *excluded and disclosed*, not asserted,
5. Keeps the **human as the final reviewer** — approve / deny / blacklist / dismiss,
   all recorded in an append-only audit trail that physically cannot be rewritten.

Measured on our evaluation cohort: **474 → 293 alerts** (38% fewer),
precision **0.169 → 0.352** (2.1×), recall **0.656 → 0.844** (we suppress noise AND
catch more true hits, because identifier matching recovers typo-broken names).

---

## 2. Architecture

```
  news_agent (:8002)                        Sanctions_agent
  ┌───────────────────────┐                 ┌────────────────────────┐
  │ scan news (mock/API)  │                 │ watchlist delta stream │
  │ ER: is article about  │                 │ (SEBI/NSE debarments,  │
  │  a watched entity?    │                 │  UAPA additions …)     │
  │ triage: adverse/benign│                 └───────────┬────────────┘
  └──────────┬────────────┘                             │
             │ POST /signals/ingest                     │ POST /api/ingest
             ▼                                          ▼
        ┌─────────────────────────────────────────────────────────┐
        │   pipeline service — investigation_agent (:8001)        │
        │                                                         │
        │   1. AMBIGUITY AGENT  — ER ladder (Rungs 0–3):          │
        │      PAN_EXACT → CONFIRMED (conf 1.0)                   │
        │      PAN mismatch / type gate → SUPPRESSED + reason     │
        │      name-only → provisional / AMBIGUOUS                │
        │   2. assess → risk tier (NONE…MONITOR…EDD…HIGH…CRITICAL)│
        │   3. INVESTIGATION AGENT — plan/execute/adjudicate:     │
        │      corroboration probes → evidence chain              │
        │      CONFIRMED / CORRELATED / MISSING (never collapsed) │
        │   4. draft SAR — cited sections, excluded claims listed │
        │   5. persist Case + SAR + AuditEvents → ckyc.db (SQLite)│
        └───────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
        ┌─────────────────────────────────────────────────────────┐
        │  read-API adapter — api/server.py (:8787)               │
        │  projects Case blobs → the dashboard's JSON;            │
        │  reviewer writes (approve/deny/blacklist/dismiss);      │
        │  SAR → filled PDF; LIVE/TEST mode switch                │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
                     Flutter dashboard (lib/, chrome)
             alert queue · entity 360 · risk timeline ·
             evidence board · SAR review · suppression log · audit
```

**Key design decision:** ambiguity → investigation is **in-process** (direct typed
function calls, one service), not microservices. Stages hand off frozen
`contracts/models.py` Pydantic objects; the DB is a **sink at the end**, never a bus
between stages. The two producers (news, sanctions) talk to the pipeline over HTTP
because they genuinely run on their own clocks.

---

## 3. The five agents (who owns what)

| # | Owner | Agent | Folder | What it does |
|---|-------|-------|--------|--------------|
| 1 | Mohita | **Sanctions agent** | `Sanctions_agent/` | Screens the customer book against watchlist deltas (SEBI/NSE debarred, UAPA, PEP) in near-real-time; on a hit, POSTs `{customer, candidates, trigger}` to the pipeline's `/api/ingest`. |
| 2 | Vaibhav | **Ambiguity agent** (entity disambiguation & scoring) | `investigation_agent/core/` (`resolver.py`, `blocking.py`, `verify.py`) | The ER ladder. Rung 0 blocking (phonetic index), Rung 1 `PAN_EXACT` confirm, Rung 2 PAN type gate, Rung 3 PAN mismatch reject. **Every rejection carries a human-readable reason** — the suppression log is built from them. Owns the frozen data contract (`contracts/models.py`). |
| 3 | Aditya | **News / media agent** | `news_agent/` | Scans news (NewsAPI live or bundled mock corpus), runs its own article-level ER ("is this article about a watched entity?") and triage ("is it adverse?") via Groq `llama-3.3-70b` (deterministic keyword fallback when keyless), emits adverse signals to the pipeline's `/signals/ingest`. APScheduler polling; `X-API-Key` auth. |
| 4 | Sneha | **Investigation agent + cited draft generation** | `investigation_agent/core/investigate.py` | Plan/execute/adjudicate loop. Runs corroboration probes (does the media name the designating authority? is there identifier-level proof? co-accused in the same order?), then adjudicates each finding **CONFIRMED / CORRELATED / MISSING** — via Anthropic `claude-opus-4-8` forced-tool-use when a key is set, or a deterministic adjudicator otherwise. `INSUFFICIENT_EVIDENCE` is a valid verdict: the agent refuses to invent findings. Drafts the SAR with inline `[EV-nnn]` citations. |
| 5 | Samaksh | **Backend + dashboard + integration** | `wkyc/` root (`api/`, `lib/`, `run_backend.sh`) | The SQLite sink schema, the read-API adapter, reviewer write-back, SAR-to-PDF, LIVE/TEST demo mode, the Flutter dashboard, and the wiring that connects all five agents into one pipeline. |

> Historical note: the repo began as five microservices around Postgres/Supabase
> (`docs/schema.md` §1–6). It was consolidated to the current in-process pipeline +
> SQLite sink for reliability and demo speed; each agent folder is a git worktree of
> the same team repo.

---

## 4. The data flow, end to end (what actually happens)

1. **A signal fires.** The news agent's scanner finds "SEBI debars Dipak Dwiwedi" and
   triages it adverse (benign stories — film releases, board appointments — are
   dropped at triage and never leave the agent). Or the sanctions agent sees a
   watchlist delta. Both emit JSON to the pipeline service.

2. **Ambiguity adjudicates identity.** The customer book has **two** "Dipak Dwiwedi"s
   with different PANs. The ER ladder confirms the one whose PAN matches the SEBI
   order (`PAN_EXACT`, confidence 1.0) and **suppresses** the other
   (`PAN_MISMATCH_REJECT` — "PAN ATDPD… ≠ AFOPG… → distinct entities despite
   identical name"). The suppression is recorded, not discarded — it *is* the metric.

3. **Assessment → tier.** Deterministic gates (e.g. `DEBARRED_PAN_EXACT_ACTIVE`,
   `UAPA_CONFIRMED`) plus a soft score produce a tier:
   `NONE → MONITOR → EDD_LITE → EDD → HIGH → CRITICAL`. CRITICAL (UAPA) is
   **always-human** — never auto-decided. Risk = likelihood × exposure: the queue
   ranks a HIGH on ₹48 Cr above a CRITICAL on ₹2 L.

4. **Investigation corroborates.** For ambiguous/critical cases the investigation
   agent probes for corroboration and emits an evidence chain where every finding is
   `CONFIRMED`, `CORRELATED`, or `MISSING` — the three are never merged. "We looked
   and it isn't there" is recorded as MISSING evidence.

5. **SAR drafted.** Structured sections (subject identification, basis for suspicion,
   chronology, evidence summary, risk assessment, recommended action), every claim
   cited `[EV-nnn]`, citation coverage measured, and **unverifiable claims listed as
   excluded** instead of silently asserted.

6. **Persisted once, at the end.** Case (+embedded customer, candidates, assessments),
   SAR, and audit rows land in `ckyc.db` in one transaction. `audit_events` is
   append-only, **enforced by a database trigger that raises on UPDATE/DELETE** — you
   cannot rewrite history, and an attempt errors loudly.

7. **The human closes the loop.** The dashboard renders the persisted Case. The
   reviewer can **Blacklist / Dismiss** the entity and **Approve / Deny** the SAR;
   each action atomically flips the case status and appends one `human:{name}` audit
   row. A dismissed false positive leaves the queue; a blacklisted entity stays,
   escalated for filing. The filled SAR form downloads as a **PDF**.

8. **Timelines accumulate.** Re-ingests for the same customer **merge** into the
   existing case (deduped timeline, earliest open date, reviewer actions preserved) —
   a case is a living history, not a snapshot. Tiers can go **down** too (a revoked
   order de-escalates), and the timeline shows it.

---

## 5. The dashboard (what each screen proves)

| Screen | Route | What the judge should notice |
|---|---|---|
| **Alert queue** | `/entities` | Sorted by tier × exposure. Filter by tier/status, search, CSV export. Only *raised* alerts — dismissed and suppressed items are absent by design. |
| **Case detail** | `/entities/:id` | **Entity 360**: our customer vs the matched watchlist entry side-by-side with the ER verdict (confirmed match / suppressed-with-reason). **Risk timeline**: dated tier transitions incl. de-escalations, `[EV-nnn]` chips. **Evidence board**: three columns — confirmed / correlated / missing. **Reviewer decision** panel. |
| **SAR draft** | `/entities/:id/report` | Section-structured report; inline `[EV-nnn]` chips are **tappable** → the backing evidence + source link. Citation-coverage bar. "Excluded — could not be verified" box. Approve / Deny. **Download PDF** fills the official SAR form template server-side. |
| **Audit log** | `/audit` | Every actor (`agent:signals`, `agent:er`, `agent:orchestrator`, `human:reviewer`) and every action, newest first, append-only. |

The UI renders **only what the pipeline persisted** — there is no fabricated display
data on the live path.

---

## 6. LIVE / TEST mode — the judge demo

The dashboard defaults to **LIVE** (whatever the real pipeline produced). The
**LIVE/TEST toggle** on the alert queue runs a scripted, deterministic scenario —
**Vijay Mallya** — through the *real* agent functions, against a separate demo
database (the live data is never touched), while the backend terminal narrates every
hand-off with color-coded agent tags.

### Demo script (follow this in front of the judges)

1. `./run_backend.sh` in one terminal (leave it visible — it's half the demo),
   `flutter run -d chrome` in another. Log in with your reviewer name.
2. Show **LIVE** briefly: 4 real pipeline-produced alerts, the suppression story
   (two Dipak Dwiwedis, one confirmed, one suppressed on PAN).
3. **Toggle → TEST.** Point at the terminal:
   `[NEWS AGENT]` catches *"Kingfisher Airlines defaults on ₹9,000-crore loans"* →
   `[AMBIGUITY AGENT]` matches the name to customer C9001 (PAN, Bengaluru, ₹920 Cr
   exposure) → `[INVESTIGATION]` honestly reports *no corroborating identifier yet* →
   `[SINK]` persists an **EDD** case. The dashboard refreshes to **one entity**.
4. Click **Vijay Mallya** → the case page shows the single news event, the
   assessment, and SAR v1 (75% coverage).
5. Press **"Time skip +15 months"** (the real-world gap between the first default
   reporting and the regulatory action). Terminal: two more articles (Supreme Court,
   ED/PMLA case) land, then `[SANCTIONS AGENT]` fires on the **SEBI debarment** —
   `[AMBIGUITY AGENT]` confirms **PAN_EXACT (confidence 1.00)** → `[INVESTIGATION]`
   corroborates (authority named across three outlets) → **CRITICAL**, escalated.
6. The timeline now carries **3 news articles + the sanction** with the tier
   stepping NONE → EDD → CRITICAL. Evidence board shows
   CONFIRMED (PAN) / CORRELATED (authority mentions) / MISSING (co-accused link) —
   and the SAR v2 (92% coverage, **one claim excluded as unverifiable**).
7. **Download PDF** — the filled SAR form. Optionally **Approve** it: the audit log
   gains a `human:{you}` row.
8. **Toggle → LIVE** — the real data is back instantly, untouched.

Everything the judges see in test mode ran through the same resolver, verifier,
investigation and case-assembly code as live mode — only the input events are
scripted.

---

## 7. Running it

### One-time setup

```bash
# pipeline service venv
python3 -m venv investigation_agent/.venv
investigation_agent/.venv/bin/pip install fastapi 'uvicorn[standard]' \
    pydantic jellyfish python-dotenv httpx anthropic pytest

# news agent venv
python3 -m venv news_agent/.venv
news_agent/.venv/bin/pip install -r news_agent/signals/requirements.txt
```

Chrome/Chromium must be installed (it renders the SAR PDF and runs the Flutter web
app — no extra Python PDF dependency).

### Every demo

```bash
./run_backend.sh          # pipeline :8001 + news agent :8002 + sanctions pass
                          # + read-API :8787 — leave this terminal VISIBLE
flutter run -d chrome     # the dashboard (in another terminal)
```

### Optional keys (`news_agent/signals/.env`) — keyless works end-to-end

| Env var | Effect when set |
|---|---|
| `GROQ_API_KEY` | News ER + triage go LLM (`llama-3.3-70b`) instead of deterministic heuristics |
| `ANTHROPIC_API_KEY` | Investigation adjudication goes LLM (`claude-opus-4-8` forced tool-use) instead of the deterministic adjudicator |
| `NEWS_API_KEY` + `USE_MOCK_NEWS=false` | Live NewsAPI instead of the bundled mock corpus |

Every LLM call has a deterministic fallback — **a dead API key can not kill the demo.**

### Tests

```bash
cd investigation_agent && .venv/bin/python -m pytest    # pipeline suite (22 tests)
flutter test                                            # dashboard suite
```

---

## 8. Repo layout

```
wkyc/                          ← Person 5: dashboard + integration (branch samaksh_ui)
├── run_backend.sh             ← ONE command: full backend stack
├── api/server.py              ← read-API adapter :8787 (stdlib-only) + writes + PDF + mode
├── lib/                       ← Flutter app (models, repository, screens, widgets)
├── casefile_sar_exact_template.html   ← the official SAR form the PDF fills
├── docs/AGENT_CONNECTION.md   ← deep-dive: how every connection point works
├── investigation_agent/       ← worktree: pipeline service (ambiguity + investigation)
│   ├── contracts/models.py    ←   THE frozen data contract (Pydantic)
│   ├── core/{blocking,resolver,verify}.py      ← ER ladder
│   ├── core/{investigate,orchestrator}.py      ← investigation + pipeline
│   ├── api/main.py            ←   FastAPI :8001 (ingest + demo endpoints)
│   ├── api/demo.py            ←   the scripted Vijay Mallya scenario
│   ├── db/{schema.sql,store.py}               ← sink + append-only triggers
│   └── fixtures/customers.json ←  THE shared customer book (all agents read it)
├── news_agent/                ← worktree: news/media agent :8002
└── Sanctions_agent/           ← worktree: sanctions monitor
```

Each agent folder is a **git worktree** of the same team repository (one repo, five
parallel working copies — the two-day merge-conflict strategy).

---

## 9. API quick reference (read-API :8787 — what the dashboard speaks)

```
GET  /api/alerts?tier=&status=       alert queue
GET  /api/entity/{id}                Entity 360 (customer + assessment + candidate)
GET  /api/entity/{id}/timeline       risk timeline
GET  /api/entity/{id}/case           full case (evidence + SAR + reviewer actions)
GET  /api/entity/{id}/sar/pdf        SAR filled into the form template → PDF download
GET  /api/suppressions               the alerts we REFUSED to raise, with reasons
GET  /api/audit?object_id=           append-only trail
GET  /api/metrics                    baseline vs ours (precision/recall/alerts)
POST /api/case/{id}/review           {action: BLACKLIST|DISMISS, note?, reviewer}
POST /api/case/{id}/sar/review       {action: APPROVE|DENY, note?, reviewer}
GET/POST /api/mode                   live ↔ test;  POST /api/demo/timeskip
```

Pipeline service (:8001): `/api/ingest` (sanctions), `/signals/ingest` (news),
`/api/verify` (ER verdict only), `/demo/*` (scenario), `/docs` (OpenAPI).

---

## 10. Anticipated judge questions (and our answers)

**Q: Where do you use LLMs, and what happens when they hallucinate?**
LLMs sit at exactly two seams, both with structural guards: (1) news ER/triage
(Groq) — worst case a benign article is emitted, and the ambiguity agent still gates
it on identity; (2) investigation adjudication (Claude, **forced tool-use** so the
output is schema-validated). The adjudicator classifies *gathered facts* — it cannot
introduce new ones, an off-schema response is rejected, and `INSUFFICIENT_EVIDENCE`
is a first-class verdict. Identity itself is decided by the **deterministic** ER
ladder, never by an LLM. And the SAR *measures* citation coverage and lists excluded
claims rather than asserting them.

**Q: How is this different from a rules engine?**
The rules (gates, PAN ladder) handle what *should* be deterministic — identity and
escalation policy. The agents handle what can't be: reading news, deciding whether
an article is about our customer, planning corroboration, drafting prose. Each agent
degrades independently (`safe()` wrappers) — one dead stage never kills the run.

**Q: Why PAN and not name-matching ML?**
India-scale name collision makes name-only screening structurally noisy (our
baseline: precision 0.169). PAN's 4th character even encodes entity *type*, giving us
a second deterministic gate. Phonetic/fuzzy matching still exists — at the blocking
rung, where it only *nominates* candidates; it never confirms identity alone.
Bare-token aliases ("Amir Khan" on the UAPA list) are explicitly barred from matching
alone.

**Q: What's real vs. mocked?**
Real: all five agents' logic, the ER ladder, the investigation probes and
adjudication, SAR drafting, the sink with enforced append-only audit, reviewer
write-back, PDF generation, both dashboards' data paths. Mocked for the demo: the
news corpus (a bundled dataset, switchable to live NewsAPI with a key) and the
customer book (synthetic — no public dataset is a real bank's book; watchlist data
follows real SEBI/UAPA list structures). The test-mode scenario scripts the *inputs*
but runs the *real* pipeline code.

**Q: Can the audit trail actually not be tampered with?**
The SQLite triggers `RAISE(FAIL)` on any UPDATE or DELETE to `audit_events` — writes
are INSERT-only at the database level, not by convention. We demonstrated a direct
UPDATE attempt failing with `audit_events is append-only`.

**Q: How does the human stay in control?**
CRITICAL (UAPA) is always-human — no auto-decision. Every reviewer action requires a
confirm dialog + optional note, lands as a `human:{name}` audit row, and is the only
mutation path the dashboard has. Dismissals are recorded (feeding future suppression
rules), not deleted.

**Q: How would this scale beyond the demo?**
The seams are already shaped for it: producers are HTTP-decoupled; the sink is one
`DATABASE_URL` away from Postgres; the blocking index bounds ER cost (candidates per
customer, not book × list); signals carry `content_hash`/`story_cluster_id` for
dedup at volume; and the read-API adapter isolates the UI from storage shape.

**Q: What did you measure?**
On our labelled evaluation cohort (`eval/evaluate.py`): naive name screening =
474 alerts, precision 0.169, recall 0.656. Ours = 293 alerts, precision 0.352,
recall 0.844. Fewer alerts *and* more true hits — the suppression log and the
PAN-recovery of noise-broken names are both visible in the dashboard.

**Q: Why is recall higher if you suppress more?**
Because Rung 1 works both ways: a typo-mangled customer name that name-matching
misses is still recovered by an exact PAN hit. Suppression removes *identifier-
contradicted* matches, which are (by construction) false positives.

---

## 11. Team

| Person | Name | Ownership |
|---|---|---|
| 1 | Mohita | Sanctions/watchlist agent + reference data |
| 2 | Vaibhav | Entity disambiguation (ER ladder), scoring, data contract |
| 3 | Aditya | News/media agent (scan, ER, triage, emit) |
| 4 | Sneha | Investigation agent + cited SAR generation |
| 5 | Samaksh | Backend, sink, read-API, Flutter dashboard, integration, demo mode |

Deep-dive documentation: **`docs/AGENT_CONNECTION.md`** (every connection point,
verification results, and design notes).
