# SAMAKSH — `ui/`

**You own the demo surface.** Every number the other four compute is invisible until you render
it. Read `00_TEAM_README.md` first.

**You are completely unblocked from minute zero.** `fixtures/` contains a golden JSON file for
every object in the system. Build the entire dashboard against them, then flip one flag to point
at the live API. **Do not wait for a backend. Ever.**

---

## Clean your branch

```bash
git fetch origin && git checkout main && git reset --hard origin/main
git branch -D <your-old-branch>
git push origin --delete <your-old-branch>
git checkout -b feat/ui
```

---

## Stack: use what you're fast in

Flutter Web is fine — you know it and speed matters more than purity here. One honest note: this
is a **desktop analyst tool** (dense tables, side-by-side evidence panels, wide layouts), not a
phone app. Design for **1440px wide first**. If Flutter Web fights you on dense data tables in
the first two hours, switch to React + Tailwind + shadcn and don't look back. **The deadline is
the boss.**

---

## What everyone else is building

- **Vaibhav** (`core/`) — entity resolution + risk scoring. Gives you `RiskAssessment`
  (tier, score, **gates_fired**, **suppressions**) and `Candidate` (with `rejection_reason`).
- **Mohita** (`watchlist/`) — the three real regulatory lists + the **temporal replay engine**.
  You get a "Replay" control that streams 2024→2026 at speed and makes the dashboard light up live.
- **Aditya** (`signals/`) — live news. Headlines, excerpts, source URLs.
- **Sneha** (`casefile/`) — Case, timeline, SAR (with `[EV-nnn]` citations and
  `unverified_claims`), reviewer actions, audit trail.

---

## The API you consume (all defined in `contracts/models.py`)

```
GET  /api/alerts?tier=&status=          -> alert queue
GET  /api/entity/{client_id}            -> Customer + current RiskAssessment
GET  /api/entity/{client_id}/timeline   -> TimelineEvent[]   (tier can go DOWN)
GET  /api/case/{case_id}                -> Case (evidence, SAR, reviewer actions)
POST /api/case/{case_id}/review         -> {action, note}
GET  /api/case/{case_id}/sar            -> SAR
POST /api/case/{case_id}/sar/approve
GET  /api/audit?object_id=              -> AuditEvent[]
GET  /api/suppressions                  -> the false positives we KILLED  <-- see Screen 5
GET  /api/metrics                       -> precision/recall, before vs after
POST /api/replay?from=&to=&speed=       -> temporal replay control
```

---

## The six screens

### 1. Alert queue (landing)
Sortable by tier × exposure. `CRITICAL / HIGH / EDD / EDD_LITE / MONITOR`.
**Colour-code by tier, but never let CRITICAL and HIGH look similar** — CRITICAL is UAPA and it
behaves differently (always human, no auto-decisions).
Show `exposure_inr` prominently. Risk = likelihood × exposure; a HIGH on ₹50cr outranks a
CRITICAL on ₹2L in practice.

### 2. Entity 360
Customer record ← → matched watchlist entry, **side by side**, fields aligned so a mismatch is
visually obvious. This is where an analyst sees *why*:

```
CUSTOMER                          WATCHLIST (NSE/SEBI debarred)
name  Anand Sharma                name  Anand Sharma          ✓ match
PAN   BGJPS5517E                  PAN   ATFPS5670Q            ✗ MISMATCH -> different person
type  Individual                  type  Individual            ✓
```

Show `Candidate.match_method` and `Candidate.confidence` as a badge. When rejected, show
`rejection_reason` **in plain language**.

### 3. Risk timeline — **the PS demands this explicitly**
*"Compile a timeline of key events showing how and why the risk profile changed."*

Horizontal, dated. Each event: what happened, evidence chips, `tier_before → tier_after`.

> **The tier can go DOWN.** A SEBI order gets revoked → risk decreases. Render that with a
> distinct visual (green, downward). Almost nobody builds de-escalation. **Make it obvious.**

### 4. Evidence panel — **three columns, never merged**
The PS explicitly requires separating confirmed evidence, correlated signals, and missing evidence.

| ✅ CONFIRMED | 🟡 CORRELATED | ⬜ MISSING |
|---|---|---|
| PAN exact match to NSE order | Same name + same city, no identifier | Registry record not retrievable |

Every card: `claim`, `source_name`, clickable `source_url` (real NSE circular PDFs), `excerpt`,
`confidence`. The `[EV-nnn]` id is visible, because the SAR cites it.

### 5. Suppression log — **the screen that wins the hackathon**

Nobody else will build this. It's the whole thesis on one screen.

> **"Alerts we did NOT raise, and why."**

| Customer | Matched | Method | Why we suppressed it |
|---|---|---|---|
| Anand Sharma | NSE debarred | `PAN_MISMATCH_REJECT` | PAN BGJPS5517E ≠ ATFPS5670Q → different person |
| Amir Khan | MHA UAPA | `ALIAS_BARE_REJECT` | Matched only the bare alias "Amir Khan" — requires corroboration |
| Ajay Kumar | PEP + debarred | `CROSS_LIST_NO_LINK` | The two sources share zero identifiers → never auto-link |

Header, in big type: **"394 → N false positives suppressed."**
Every other team shows what their system *found*. We show what it **refused to say.**

### 6. SAR review + audit
Render Sneha's SAR with `[EV-nnn]` citations as **clickable inline chips** that scroll to the
evidence card. Show `citation_coverage` as a percentage badge.

Show `unverified_claims` in a distinct panel:
> ⚠️ **Excluded from this report — could not be verified:** …

Then: `CONFIRM` / `DISMISS` / `ESCALATE` / `REQUEST_INFO`, and the append-only audit log below.

---

## Two demo controls that make the pitch land

1. **Replay button.** `POST /api/replay?from=2024-01-01&to=2026-07-01&speed=1000`.
   The dashboard lights up live: alerts appear, timelines populate, one order gets revoked and a
   tier goes **down**. This is how we demonstrate "near real-time monitoring" without waiting for
   the news to break during our slot.

2. **Before / after toggle.** One switch: **naive screening** vs **our system**.
   ```
   BASELINE   474 alerts   precision 0.169   ← 83% of an analyst's day is noise
   OURS         N alerts   precision   ?
   ```
   Flip it live in front of the judges. That single toggle *is* the pitch.

---

## Definition of done

- [ ] All six screens render from `fixtures/` with **zero backend**. (Do this first.)
- [ ] Flip one flag → same screens render from the live API.
- [ ] Evidence panel keeps CONFIRMED / CORRELATED / MISSING in **three separate columns**.
- [ ] Suppression log built, with `rejection_reason` in plain language.
- [ ] Timeline renders a **de-escalation** (tier going down) distinctly.
- [ ] SAR citations are clickable chips → scroll to evidence.
- [ ] `unverified_claims` panel is visible and unmissable.
- [ ] Replay control works.
- [ ] Before/after toggle works.
- [ ] Designed for 1440px. Nothing important below the fold on the alert queue.

## Datasets you receive

**None.** Only `fixtures/`. That is deliberate — it means you can start before anyone else has
written a line of backend.

## Do not touch

`core/` `watchlist/` `signals/` `casefile/` `contracts/`.
