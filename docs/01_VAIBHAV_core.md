# VAIBHAV — `core/` + `contracts/` + `api/` + `fixtures/` + `eval/`

**You own the graded centrepiece and the integration.** Read `00_TEAM_README.md` first.

You have two jobs and they are not equal:
1. **Unblock everyone (Checkpoint 0).** Until `main` has contracts + fixtures + docker-compose,
   four people are idle. Do this first. It should take hours, not days.
2. **Entity Resolution + Risk Scoring.** This is what the problem statement grades hardest and
   it is the thing that produces our headline numbers.

---

## PHASE 0 — the scaffold (do this before anything else)

Reset `main`. Everyone else is waiting on you.

```bash
git checkout main
# main is being rebuilt from scratch. the old build is dead.
git rm -r --cached . && rm -rf <old dirs>
# scaffold:
mkdir -p contracts core watchlist signals casefile ui api fixtures eval data tests
```

Ship in `main` at CP0:

- `contracts/models.py` — **provided to you, already written and validated. Commit it as-is.**
- `docker-compose.yml` — Postgres 16 + the FastAPI app. One command: `docker-compose up`.
- `db/schema.sql` — tables mirroring the contracts. `audit_events` is **append-only**
  (no UPDATE, no DELETE — enforce with a trigger, it's five lines and it's a great answer in Q&A).
- `fixtures/` — **this is the most important thing you ship at CP0.** One golden JSON file per
  contract object, realistic, hand-checked:
  ```
  fixtures/customers.json          10 customers, incl. one of each ground-truth bucket
  fixtures/watchlist.json          30 entries: debarred w/ PAN, PEP, RCA, UAPA w/ aliases
  fixtures/signals.json            8 signals: 3 adverse media, 2 watchlist deltas, 1 rehash
  fixtures/candidates.json         one per match_method, incl. every REJECT type
  fixtures/assessments.json        one per tier, incl. a DOWNGRADE
  fixtures/cases.json              2 cases: one CRITICAL w/ SAR, one DISMISSED
  fixtures/sar.json                a full SAR with [EV-nnn] citations
  fixtures/audit.json              20 audit events
  ```
  **Samaksh builds the entire dashboard from these. Sneha drafts SARs from these. If your
  fixtures are thin or unrealistic, two people build the wrong thing.** Spend real time here.
- `Makefile` with `make demo-core`, `make demo-watchlist`, … (each package runs standalone)
- `api/main.py` — FastAPI, mounts a router per package. Routers can return fixtures at CP0.

Then post in the group: **"main is ready, branch now."**

---

## PHASE 1 — Entity Resolution (`core/resolver.py`)

This is a **ladder**, not a model. Cheap deterministic checks first; the LLM only sees the
ambiguous band. Every rung is defensible in Q&A.

```
INPUT:  Customer (messy: typos, translit, "SURNAME, First", 18% missing PAN)
        + WatchlistEntry candidates from the blocking index
OUTPUT: Candidate (CONFIRMED | AMBIGUOUS | REJECTED, + rejection_reason)
```

### Rung 0 — Blocking / candidate generation
Never compare a customer against 18,222 entries. Block on:
`normalised surname` ∪ `first-initial + surname` ∪ `double-metaphone of full name` ∪ `PAN`.
Target: < 50 candidates per customer. Report your reduction ratio — it's a real number.

### Rung 1 — PAN exact  →  `CONFIRMED`, confidence 1.0
Covers ~81% of the debarred list. No LLM, no ambiguity, no argument.

### Rung 2 — PAN 4th-char type gate  →  `TYPE_MISMATCH_REJECT`
```python
PAN_TYPE = {"P": "Individual", "C": "Corporate", "H": "HUF", "F": "Firm", "T": "Trust"}
# customer is Individual, watchlist PAN[3] == "C"  ->  REJECT. cannot be the same entity.
```
Kills an entire false-positive class for free. **The OpenSanctions schema flattens everything
to `LegalEntity` — no person/company distinction at all. PAN gives it back to you. Say this.**

### Rung 3 — PAN mismatch  →  `PAN_MISMATCH_REJECT`
Both sides have a PAN and they **differ** → different person. Full stop.
This is the gate that kills bucket `B_FP_PAN_MISMATCH` (60 traps).
`rejection_reason = "PAN AKHPG5185D != AFOPG8341M -> distinct entities"`

### Rung 4 — Alias-quality gate  →  `ALIAS_BARE_REJECT`
A match that rests **only** on a `bare_token` alias is not a match.
97 of 227 UAPA aliases are bare tokens: `Salim`, `Hamza`, `Zakir`, `Ismail`, `Sultan`,
`Doctor`, `Chief`, **`Amir Khan`**, **`Gulshan Kumar`**.
Bare tokens may only *corroborate* a match already established by a full name or by context.
This kills bucket `F_FP_UAPA_ALIAS` (35 traps).
`rejection_reason = "matched only bare alias 'Amir Khan'; requires corroboration"`

### Rung 5 — Cross-list no-link rule  →  `CROSS_LIST_NO_LINK`
**The PEP register and the debarred list share ZERO strong identifiers** (debarred has PAN and
no DOB; Sabha has DOB and no PAN). 54 names appear on both. **Never auto-link them.**
A link requires external corroboration — a news article placing them together, or a shared
co-accused order. This kills bucket `C_FP_PEP_COLLISION` (30 traps).

> This single rule is the most sophisticated-sounding thing in the whole system and it is
> completely defensible. Put it on a slide.

### Rung 6 — Phonetic / fuzzy (this is where fuzzy matching *earns* its place)
Only reached when there is no PAN on one side. Two distinct jobs:
- **Transliteration** (UAPA): `Hafiz Muhammad Saeed` has 8 spellings — `Hafez Mohammad Saeed`,
  `Hafiz Mohaddad Sayid`, `Hafiz Mohammad Sayeed`… Use **Double Metaphone** + Jaro-Winkler.
  This is the *only* place in the system where phonetic matching is justified. Say so.
- **Record noise** (our messy book): typos, `SURNAME, First`, initials, dropped middle names.
  Normalise hard (strip Shri/Shrimati/Smt/Dr, handle comma-inversion) then token-set ratio.

Score → `CONFIRMED` (high) / `AMBIGUOUS` (mid) / `REJECTED` (low). **The mid band goes to Rung 7.**

### Rung 7 — LLM adjudicator (ambiguous band ONLY)
Give the LLM: customer record, candidate entry, the triggering signal's text, and the features
from lower rungs. Ask for `{decision, confidence, reasoning, needed_evidence[]}`.
**It may answer `INSUFFICIENT_EVIDENCE`.** That is a valid, correct, valuable answer — that
is the "AI Delivered Right" behaviour and it routes straight to human review.

Never send more than the ambiguous band to the LLM. Cost and latency are both a story.

---

## PHASE 2 — Risk scoring (`core/scoring.py`)

**Do not multiply a sanctions score by a news score.** A confirmed sanctions match is not a
smooth signal — it is a **hard gate**.

```python
# 1) GATES — deterministic, no scoring
if uapa_confirmed:                     return CRITICAL   # SAR mandatory, always human
if debarred_pan_exact and active:      return HIGH
if debarred_pan_exact and revoked:     return downgrade(prior_tier)   # risk goes DOWN
if pep_current or rca:                 return EDD        # NOT adverse media
if all_candidates_rejected:            return SUPPRESS   # log reason, never surface

# 2) SOFT SCORE — only for whatever no gate caught
score = (severity
         * source_credibility
         * recency_decay(occurred_at)      # exp decay, half-life ~90d
         * er_confidence)
score += w_pep * pep_status + w_net * network_exposure
# network_exposure: co-accused in the same SEBI order. 1,515 orders / 11,698 rows.
#   one Pyramid Saimira order names 254 entities. that's a real graph, free.
```

**The threshold.** Sweep it on `eval/`. Plot precision/recall. Pick where precision hits 0.90
(at the triage stage, compliance cares far more about FP than FN — the human review layer
catches the rest). Then in the deck: *"0.62, because that's where precision reaches 0.90 on
our benchmark."* Never say "we chose 0.7."

---

## PHASE 3 — Orchestrator (`core/orchestrator.py`)

Dead simple. One process. No Kafka, no Celery.

```
Signal arrives (from signals/ or watchlist/)
  -> block + resolve against watchlist        [core/resolver]
  -> score + gate                             [core/scoring]
  -> if tier > NONE: open/update Case         [casefile/]
  -> if tier == CRITICAL: trigger investigation agent + SAR draft   [casefile/]
  -> append AuditEvent at every step
```

**Multiple independent triggers.** Not just news. A watchlist delta with zero press coverage
must still fire — that is exactly the scenario KYC exists for.

---

## PHASE 4 — `eval/` (this is the pitch)

You already have `build_portfolio.py` and `evaluate.py`. Wire your resolver into `evaluate.py`
(same signature as `baseline_screener`) and report at **both base rates**:

```
                   prevalence   precision   recall   false pos
  BASELINE stress       6.10%       0.452    0.656          97
  BASELINE realistic    0.20%       0.169    0.656         394
  OURS     stress       6.10%         ?        ?            ?
  OURS     realistic    0.20%         ?        ?            ?
```

**Note it must improve BOTH.** The baseline misses 42 true positives (noise broke exact
matching) *and* raises 394 false ones. Anyone can cut FPs by refusing to alert. We have to
raise recall *and* precision simultaneously. That is a much harder and much more credible claim.

Also emit a **per-bucket table** — it shows *which gate* fixed *which trap*:

| Bucket | Baseline | Ours | Fixed by |
|---|---|---|---|
| B_FP_PAN_MISMATCH | 46/60 wrongly fired | ? | PAN mismatch gate |
| C_FP_PEP_COLLISION | 27/30 wrongly fired | ? | cross-list no-link |
| F_FP_UAPA_ALIAS | 16/35 wrongly fired | ? | alias-quality gate |
| A_TRUE_SANCTION | only 33/50 found | ? | fuzzy/phonetic |
| G_TRUE_UAPA | only 5/7 found | ? | transliteration |

**Honest caveat to state before a judge does:** the realistic cohort holds the FP-trap buckets
at fixed size while diluting only the clean pool, so 0.2% is a *floor* on how bad precision
gets. A real book would also carry proportionally more near-miss names. Say it first.

---

## Definition of done

- [ ] CP0: `main` has contracts, fixtures, docker-compose, schema. Team unblocked.
- [ ] Resolver implements all 7 rungs; every `REJECTED` carries a `rejection_reason`.
- [ ] Blocking reduction ratio measured and reported.
- [ ] Gates are code, not LLM. LLM sees only the ambiguous band.
- [ ] Threshold chosen from a precision/recall sweep, not by hand.
- [ ] `eval/` prints the before/after table at both base rates + the per-bucket table.
- [ ] `GET /api/suppressions` returns the suppression log with reasons. **This is a demo screen.**
- [ ] `make demo-core` runs the full ladder on fixtures with no other package present.

## Datasets you receive

Everything. You are the only one who needs all of it.

```
targets_nested_stock_.json   sebi_stock_.xls        other_stock_.xlsx
targets_nested_sabha_.json   targets_nested_mha_.json
customers_stress.csv         customers_realistic.csv
ground_truth_stress.csv      ground_truth_realistic.csv
watchlist_canonical.csv      build_portfolio.py     evaluate.py
```

## Do not touch

`watchlist/` `signals/` `casefile/` `ui/`. You own `contracts/` — but **freeze it at CP0**.

---

## Pipeline hand-off (direct in-memory architecture — see `docs/06_PIPELINE.md`)

`core/` owns the orchestrator and the two ER/scoring stages. Everything is a typed
`contracts/models.py` object — no dicts, no DB between stages.

```python
# core/orchestrator.py — the entrypoint
def run_pipeline(customer: Customer) -> Case: ...   # blocks->resolves->assesses->builds->persists

# core/resolver.py — Rungs 0-3 (built). Rung 0 blocking (core/blocking.Blocker)
# narrows the watchlist BEFORE resolution:
def resolve(customer: Customer, watchlist_candidates: list[WatchlistEntry]) -> list[Candidate]: ...

# core/scoring.py — LATER SESSION. Not implemented yet; the orchestrator stubs the
# assessment from fixtures until it lands (no scoring introduced by the refactor):
def assess(client_id, candidates, signals, prior_tier) -> RiskAssessment: ...
```

The orchestrator persists ONLY `Case` + `SAR` + `AuditEvent` to SQLite (`db/store.py`);
intermediates flow in memory and ride inside the persisted `Case` where the UI needs them.
