# Architecture — Direct In-Memory Pipeline

**This replaces the old Supabase/Postgres, `entity_id`-keyed, OFAC/UN build.** That
design is retired. The current build keys on **PAN** over real Indian data
(`contracts/models.py`) and hands off objects **in memory via direct function calls** —
no database between stages, no message bus. The database is a **sink** at the end.

```
Customer
   │
   ▼   load_watchlist()            -> list[WatchlistEntry]   (Mohita)
       fetch_and_triage(customer)  -> list[Signal]           (Aditya, network → safe)
   ▼   resolve(customer, watchlist)-> list[Candidate]        (core, Rungs 0-3)
       assess(candidates, signals) -> RiskAssessment         (core scoring, later session)
   ▼   (only if tier != NONE)
       investigate(assessment)     -> list[Evidence]         (Sneha)
       draft_sar(assessment, ev)   -> SAR                    (Sneha)
   ▼   PERSIST: Case + SAR + AuditEvent  ->  SQLite   (the ONLY DB writes)
   ▼   UI reads the persisted Case                           (Samaksh)
```

Entry point: `core/orchestrator.py :: run_pipeline(customer) -> Case`.

## The three rules

1. **Every hand-off is a `contracts/models.py` object** — never a dict, never an ad-hoc
   shape. With the DB gone from between stages, the typed contract is the ONLY thing
   keeping five people's code aligned. That makes it more important, not less.

2. **Only three things persist, and only as a final sink:** `Case`, `SAR`, `AuditEvent`
   (`db/schema.sql`, `db/store.py`). Intermediate `Signal` / `Candidate` /
   `RiskAssessment` objects stay in memory; where the UI needs them, they ride embedded
   inside the persisted `Case` JSON. The old `signals` / `candidates` / `risk_assessments`
   tables are gone.

3. **Each stage degrades, it does not crash.** `safe(fn, ..., default=...)` wraps every
   stage; a failure logs and returns the default (`[]` for the network stage). One dead
   component cannot kill the run — this matters most for `fetch_and_triage` (GDELT) on
   demo day.

## Runs on fixtures TODAY

Stages whose owner hasn't shipped are backed by `fixtures/` inside the orchestrator, so
the whole pipeline runs end-to-end before any real component lands. `resolve` (Rungs 0-3)
is real; `assess` is stubbed from `fixtures/assessments.json` until `core/scoring.py`
lands (a later session — **the refactor introduced no scoring**). Each stub is a seam:
ship the real function to the documented signature and swap the import.

`GET`/`POST` surface: see `docs/05_SAMAKSH_ui.md`. The API rebuilds the SQLite sink and
seeds it via `run_pipeline()` over the fixture customers on startup.

## Salvaged from the retired build — exactly two things

**Salvage 1 — append-only audit via a RAISING trigger** (`db/schema.sql`). Not a silent
`DO INSTEAD NOTHING`: any UPDATE/DELETE on `audit_events` **fails loudly**
(`RAISE(FAIL, 'audit_events is append-only')`). You cannot rewrite history, and an attempt
errors. Verified: UPDATE and DELETE both raise; rows stay intact.

**Salvage 2 — atomic review action** (belongs to `casefile/`; documented in
`docs/04_SNEHA_casefile.md`, not implemented here). A reviewer action must flip the `Case`
status **and** append the `AuditEvent` in one transaction — both or neither. `db/store.py`
already writes inside a single `with conn:` transaction; `casefile/` extends that pattern.

Everything else from the old build is discarded.

## Hard constraints honored

- `contracts/models.py` untouched (frozen).
- No Supabase / Postgres / Docker / `entity_id`.
- No intermediate objects persisted as standalone rows.
- `eval/` untouched — the ER ladder result is independent of this refactor and still runs.
