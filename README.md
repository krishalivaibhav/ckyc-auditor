# TechMKYC — Continuous KYC Autonomous Auditor

Built for **Code by Tech Mahindra — Challenge 3: Continuous KYC Autonomous Auditor.**

A network of five cooperating agents that continuously watches a bank's customer book
against sanctions lists and adverse media, **resolves name collisions on hard
identifiers instead of raising them as alerts**, investigates the matches that survive,
drafts a fully-cited SAR for human sign-off, emails the compliance team the moment a
high-risk entity is hit, and records every step in an append-only audit trail. A
Flutter dashboard is the human reviewer's cockpit.

## 🎥 Demo video

> **▶️ Watch the demo: https://drive.google.com/file/d/1R3mS-lTVGo3MzPkBVAFhHl0yYf4Veg0i/view?usp=drivesdk**

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
5. **Alerts a human immediately** (email) on any HIGH/CRITICAL hit,
6. Keeps the **human as the final reviewer** — approve / deny / blacklist / dismiss /
   escalate, all recorded in an append-only audit trail that physically cannot be
   rewritten.

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
        │  read-API adapter — api/server.py (:8787, stdlib-only)  │
        │  projects Case blobs → the dashboard's JSON;            │
        │  reviewer writes (approve/deny/blacklist/dismiss/       │
        │  escalate); SAR → inline HTML preview + filled PDF;     │
        │  Gmail risk-alert emails; LIVE/TEST mode switch         │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                                    ▼
                     Flutter dashboard (lib/, chrome)
             alert queue · entity 360 · risk timeline ·
             evidence board · SAR review · reports · audit · settings
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
| 5 | Samaksh | **Backend + dashboard + integration** | `wkyc/` root (`api/`, `lib/`, `run_backend.sh`) | The SQLite sink schema, the read-API adapter, reviewer write-back, SAR preview + PDF, Gmail risk alerts, LIVE/TEST demo mode, the Flutter dashboard, and the wiring that connects all five agents into one pipeline. |

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

7. **A high-risk hit emails the reviewer.** When the resulting tier is **HIGH or
   CRITICAL** and an alert recipient is configured (Settings screen), the read-API
   sends a Gmail alert immediately — entity, tier, case id, exposure — so the team
   doesn't have to be watching the dashboard.

8. **The human closes the loop.** The dashboard renders the persisted Case. The
   reviewer can **Blacklist / Dismiss / Escalate** the entity and **Approve / Deny**
   the SAR; each action atomically updates the case status and appends one
   `human:{name}` audit row. A dismissed false positive leaves the queue; a
   blacklisted entity stays, escalated for filing; **Escalate** routes a case to
   senior compliance without closing it. The filled SAR previews inline and downloads
   as a **PDF**.

9. **Timelines accumulate.** Re-ingests for the same customer **merge** into the
   existing case (deduped timeline, earliest open date, reviewer actions preserved) —
   a case is a living history, not a snapshot. Tiers can go **down** too (a revoked
   order de-escalates), and the timeline shows it, with the exact date and time of
   each event.

---

## 5. The dashboard (what each screen proves)

| Screen | Route | What the judge should notice |
|---|---|---|
| **Alert queue** | `/entities` | Sorted by tier × exposure. Filter by tier/status, search, and **Export → Excel / PDF / Copy CSV**. Only *raised* alerts — dismissed and suppressed items are absent by design. |
| **Case detail** | `/entities/:id` | **Entity 360**: our customer vs the matched watchlist entry side-by-side with the ER verdict (confirmed match / suppressed-with-reason). **Risk timeline**: dated tier transitions incl. de-escalations, each stamped with the exact date and time of the event, with `[EV-nnn]` chips. **Evidence board**: three columns — confirmed / correlated / missing. **Reviewer decision** panel — Blacklist / Escalate / Dismiss. |
| **SAR draft** | `/entities/:id/report` | Section-structured report; inline `[EV-nnn]` chips are **tappable** → the backing evidence + source link. Citation-coverage bar. "Excluded — could not be verified" box. **Preview** (opens the filled official SAR form inline) and **Download PDF** (same form, server-rendered). Approve / Deny. |
| **Reports** | `/reports` | Every entity that has a drafted SAR, with tier, SAR status and citation coverage — each **previewable and downloadable** without drilling into the case. |
| **Audit log** | `/audit` | Every actor (`agent:signals`, `agent:er`, `agent:orchestrator`, `human:reviewer`) and every action, newest first, append-only. |
| **Settings** | `/settings` | Configure the **risk-alert email** recipient, send a test alert, and see whether the sender (Gmail app password) is wired up. |

The UI renders **only what the pipeline persisted** — there is no fabricated display
data on the live path.

> **Risk-tier labels are plain-language in the UI:** the pipeline's `EDD` /
> `EDD_LITE` tiers render as **"Enhanced Review"** / **"Standard Review"** so a
> non-specialist can read the queue. The wire/DB values are unchanged.

---

## 6. Risk-alert email (Gmail SMTP)

The moment a **HIGH or CRITICAL** entity is hit, the read-API emails the configured
recipient — so a reviewer learns about a sanctioned customer without watching a screen.

- **Recipient** is set in the dashboard **Settings** screen (persisted to
  `api/.alert_config.json`, gitignored). A **Send test email** button verifies the
  wiring end-to-end.
- **Sender** credentials (a Gmail account + app password) come from the backend's
  `.env` — `ALERT_SMTP_USER` / `ALERT_SMTP_PASS` — never hardcoded in source. `.env`
  is gitignored.
- Delivery is **best-effort and non-blocking**: an unreachable mail server never fails
  the pipeline or the demo time skip; the outcome ("emailed to …" / "not sent —
  reason") is surfaced back in the UI.
- **In the demo**, the alert fires when the **"Time skip +15 months"** button
  escalates the Vijay Mallya case to CRITICAL.

Standard-library `smtplib` over SSL (`smtp.gmail.com:465`) — no extra Python
dependency. Offline demo mode (no backend) disables sending with a clear message.

---

## 7. LIVE / TEST mode — the judge demo

The dashboard defaults to **LIVE** (whatever the real pipeline produced). The
**LIVE/TEST toggle** on the alert queue runs a scripted, deterministic scenario —
**Vijay Mallya**, pinned to the *real* 2015–2017 chronology — through the *real* agent
functions, against a separate demo database (the live data is never touched), while
the backend terminal narrates every hand-off with color-coded agent tags.

### Demo script (follow this in front of the judges)

1. `./run_backend.sh` in one terminal (leave it visible — it's half the demo),
   `flutter run -d chrome` in another. Log in with your reviewer name.
2. *(Optional, one-time)* In **Settings**, set your alert email and hit **Send test
   email** to prove the wiring.
3. Show **LIVE** briefly: real pipeline-produced alerts, the suppression story
   (two Dipak Dwiwedis, one confirmed, one suppressed on PAN).
4. **Toggle → TEST.** Point at the terminal:
   `[NEWS AGENT]` catches *"Kingfisher Airlines defaults on ₹9,000-crore loans"*
   (**13 Nov 2015**) → `[AMBIGUITY AGENT]` matches the name to customer C9001 (PAN,
   Bengaluru, ₹920 Cr exposure) → `[INVESTIGATION]` honestly reports *no corroborating
   identifier yet* → `[SINK]` persists an **Enhanced Review (EDD)** case. The dashboard
   refreshes to **one entity**.
5. Click **Vijay Mallya** → the case page shows the single news event dated Nov 2015,
   the assessment, and SAR v1 (75% coverage).
6. Press **"Time skip +15 months"** (the real-world gap to the regulatory action).
   Terminal: two more articles land (**Mar 2016** — Supreme Court, ED/PMLA case), then
   `[SANCTIONS AGENT]` fires on the **SEBI debarment** (**25 Jan 2017**) —
   `[AMBIGUITY AGENT]` confirms **PAN_EXACT (confidence 1.00)** → `[INVESTIGATION]`
   corroborates (authority named across three outlets) → **CRITICAL**, escalated. If an
   alert email is configured, it's **sent now**, and the confirmation says so.
7. The timeline now carries **3 news articles + the sanction** with real 2015→2017
   dates and times, the tier stepping NONE → EDD → CRITICAL. Evidence board shows
   CONFIRMED (PAN) / CORRELATED (authority mentions) / MISSING (co-accused link) —
   and the SAR v2 (92% coverage, **one claim excluded as unverifiable**).
8. **Preview / Download PDF** — the filled official SAR form. Optionally **Approve**
   it: the audit log gains a `human:{you}` row.
9. **Toggle → LIVE** — the real data is back instantly, untouched.

Everything the judges see in test mode ran through the same resolver, verifier,
investigation and case-assembly code as live mode — only the input events are
scripted.

> The pipeline service loads the scenario at startup, so **restart `./run_backend.sh`**
> if you change demo data before toggling test mode again.

---

## 8. Running it

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

### Risk-alert email (optional — for the Gmail alerts)

Create a gitignored `.env` at the repo root with a Gmail account and an
[app password](https://support.google.com/accounts/answer/185833):

```bash
# .env  (gitignored)
ALERT_SMTP_USER=your.account@gmail.com
ALERT_SMTP_PASS=your gmail app password
```

Then set the **recipient** in the dashboard's Settings screen. Without this, everything
else still works — high-risk hits simply won't be emailed.

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
cd investigation_agent && .venv/bin/python -m pytest    # pipeline suite
flutter test                                            # dashboard suite
flutter analyze lib                                     # static analysis
```

---

## 9. Repo layout

```
wkyc/                          ← Person 5: dashboard + integration (branch samaksh_ui)
├── run_backend.sh             ← ONE command: full backend stack
├── .env                       ← Gmail SMTP sender creds for alerts (gitignored)
├── api/
│   ├── server.py              ←   read-API adapter :8787 (stdlib-only): reads, reviewer
│   │                              writes, SAR preview/PDF, Gmail alerts, LIVE/TEST mode
│   └── .alert_config.json     ←   alert recipient, set from Settings (gitignored)
├── lib/                       ← Flutter app
│   ├── core/                  ←   api config, router, theme, web download bridge
│   ├── data/repository.dart   ←   API + offline-demo repositories + Riverpod providers
│   ├── models/models.dart     ←   Dart mirrors of the six-screen contract
│   └── features/              ←   entities, report (+ reports_screen), audit, settings, auth
├── casefile_sar_exact_template.html   ← the official SAR form the preview/PDF fills
├── docs/AGENT_CONNECTION.md   ← deep-dive: how every connection point works
├── investigation_agent/       ← worktree: pipeline service (ambiguity + investigation)
│   ├── contracts/models.py    ←   THE frozen data contract (Pydantic)
│   ├── core/{blocking,resolver,verify}.py      ← ER ladder
│   ├── core/{investigate,orchestrator}.py      ← investigation + pipeline
│   ├── api/main.py            ←   FastAPI :8001 (ingest + demo endpoints)
│   ├── api/demo.py            ←   the scripted Vijay Mallya scenario (2015–2017)
│   ├── db/{schema.sql,store.py}               ← sink + append-only triggers
│   └── fixtures/customers.json ←  THE shared customer book (all agents read it)
├── news_agent/                ← worktree: news/media agent :8002
└── Sanctions_agent/           ← worktree: sanctions monitor
```

Each agent folder is a **git worktree** of the same team repository (one repo, five
parallel working copies — the two-day merge-conflict strategy).

---

## 10. API quick reference (read-API :8787 — what the dashboard speaks)

```
GET  /api/alerts?tier=&status=       alert queue
GET  /api/entity/{id}                Entity 360 (customer + assessment + candidate)
GET  /api/entity/{id}/timeline       risk timeline (dated, incl. de-escalations)
GET  /api/entity/{id}/case           full case (evidence + SAR + reviewer actions)
GET  /api/entity/{id}/sar/html       SAR filled into the form template → inline preview
GET  /api/entity/{id}/sar/pdf        same form → PDF download
GET  /api/suppressions               the alerts we REFUSED to raise, with reasons
GET  /api/reports                    cases that carry a drafted SAR (the Reports tab)
GET  /api/audit?object_id=           append-only trail
GET  /api/metrics                    baseline vs ours (precision/recall/alerts)
POST /api/case/{id}/review           {action: BLACKLIST|DISMISS|ESCALATE, note?, reviewer}
POST /api/case/{id}/sar/review       {action: APPROVE|DENY, note?, reviewer}
GET/POST /api/alert-config           risk-alert recipient;  POST /api/alert-config/test
GET/POST /api/mode                   live ↔ test;  POST /api/demo/timeskip
```

Pipeline service (:8001): `/api/ingest` (sanctions), `/signals/ingest` (news),
`/api/verify` (ER verdict only), `/demo/*` (scenario), `/docs` (OpenAPI).

---

## 12. Team

| Person | Name | Ownership |
|---|---|---|
| 1 | Mohita | Sanctions/watchlist agent + reference data |
| 2 | Vaibhav | Entity disambiguation (ER ladder), scoring, data contract |
| 3 | Aditya | News/media agent (scan, ER, triage, emit) |
| 4 | Sneha | Investigation agent + cited SAR generation |
| 5 | Samaksh | Backend, sink, read-API, Flutter dashboard, alerts, integration, demo mode |

Deep-dive documentation: **`docs/AGENT_CONNECTION.md`** (every connection point,
verification results, and design notes).
