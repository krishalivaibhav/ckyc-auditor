# SNEHA — `casefile/`

**You own the compliance vertical: investigation → SAR → human review → audit trail.**
Read `00_TEAM_README.md` first.

Your old scope was "SAR report generation." It's grown, and in the right direction: the SAR is
worthless without the **evidence chain** behind it and the **human sign-off** in front of it.
The problem statement asks for all three and they are one coherent vertical. It's yours.

**Your package is where "AI Delivered Right" actually lives.** Everyone else reduces false
positives. You are the one who makes the system *refuse to make things up*.

---

## Clean your branch

```bash
git fetch origin && git checkout main && git reset --hard origin/main
git branch -D <your-old-branch>
git push origin --delete <your-old-branch>
git checkout -b feat/casefile
docker-compose up -d && pytest tests/ -q
```

**You are the least blocked person on the team.** `fixtures/assessments.json` and
`fixtures/cases.json` contain everything you need. Build the entire SAR pipeline against them
and never wait for ER or news.

---

## What everyone else is building

- **Vaibhav** (`core/`) — ER + scoring. Hands you a `RiskAssessment` with `gates_fired`,
  `suppressions`, and `Evidence[]`. **That's your input.**
- **Mohita** (`watchlist/`) — the real lists. Her `source_url` fields are **real NSE circular
  PDFs** (`archives.nseindia.com/content/circulars/INVG50070.pdf`). Those are your citations.
- **Aditya** (`signals/`) — news. His `source_url` + `raw_excerpt` are your other citations.
- **Samaksh** (`ui/`) — renders your Case, timeline, evidence panel, and SAR review screen.

---

## TASK 1 — Investigation agent (`casefile/investigate.py`)

**A genuine agent** — plan/execute loop, non-deterministic, earns its place.

Triggered when a `RiskAssessment` opens or escalates a case. Its job is **not** "query more
sources" in the abstract. It's specific:

> **Resolve a name-only match against context.**

Remember the architecture: MHA UAPA has **zero identifiers**. The Sabha PEP register has **zero
PAN**. When Vaibhav's ladder returns `AMBIGUOUS`, there is no identifier left to check — the
*only* path to a confident answer is corroboration. That's you.

The loop:
```
given: customer, candidate watchlist entry, triggering signal
plan:  what would confirm or refute this link?
       - does the article mention a designated org the entry is tied to?
       - does the geography match?
       - is there a co-accused SEBI order linking them? (Mohita's order_id)
       - is there a shared relative in the Sabha family graph?
       - does an age in the article match a DOB we hold?
execute: query watchlist/, signals/, and the web
emit:  Evidence[] with status ∈ {CONFIRMED, CORRELATED, MISSING}
```

**The agent must be able to conclude `INSUFFICIENT_EVIDENCE`.** That routes to human review and
it is a *correct* answer, not a failure. Do not build an agent that always finds something.

### `Evidence.status` — three values, never collapsed

The PS explicitly demands we separate these. It shows up in the SAR and on screen.

| Status | Meaning |
|---|---|
| `CONFIRMED` | Directly evidenced. PAN exact match. A named SEBI order. |
| `CORRELATED` | Suggestive but not proof. Same name + same city, no identifier. |
| `MISSING` | **We looked and could not find it.** Say so explicitly. |

`MISSING` is the one everyone forgets and it is the one that makes us look serious.

---

## TASK 2 — SAR drafter (`casefile/sar.py`) — **your centrepiece**

A SAR is a **structured artifact**, not a generic LLM report. Fixed sections:

```
subject_identification    who, PAN, entity type, exposure, onboarding date
basis_for_suspicion       what triggered this, and why it survived our suppression gates
chronology_of_events      dated timeline. include DE-ESCALATIONS.
evidence_summary          CONFIRMED / CORRELATED / MISSING, split out explicitly
risk_assessment           tier, gates fired, score, ER confidence
recommended_action        file / monitor / dismiss / request more info
```

### The citation rule (non-negotiable)

**Every factual sentence carries at least one `[EV-nnn]`.** Build a **validator that rejects
uncited sentences** — not a warning, a rejection. Uncited claims are stripped and listed under
`unverified_claims`.

```python
def validate_sar(sar: SAR) -> SAR:
    """Every factual sentence must resolve to an Evidence id. No exceptions."""
    for section, text in sar.sections.items():
        for sentence in split_sentences(text):
            if is_factual(sentence) and not extract_ev_ids(sentence):
                sar.unverified_claims.append(sentence)
                text = text.replace(sentence, "")     # STRIP IT.
    sar.citation_coverage = cited_sentences / factual_sentences
    return sar
```

**Target `citation_coverage >= 0.95`, and print the number in the demo.**

### `unverified_claims` — the refusal, and the best slide in the deck

Anything the model wanted to assert but could not source goes here, visibly, in the output:

> *"Could not verify: the subject's directorship of Meridian Infra Pvt Ltd. No registry record
> was retrievable. **This claim has been excluded from the report.**"*

> Every other team's LLM will confidently hallucinate a plausible SAR. Ours will hand the
> analyst a report and a short list of things it **refused to say**. Demo that side by side —
> a generic LLM SAR next to ours — and let the judges see the difference. That's the whole
> theme of the hackathon in one screen.

---

## TASK 3 — Human review workflow (`casefile/review.py`)

Four actions: `CONFIRM` / `DISMISS` / `ESCALATE` / `REQUEST_INFO`. Each writes a
`ReviewerAction`. Nothing files without human sign-off — **especially** UAPA, where the gate
ladder says *always human, no auto-decisions, in either direction*.

### The feedback loop (this is the PS's "continuously improve" requirement)

A `DISMISS` is not just a state change. It becomes:
- a **suppression rule** (this customer × this watchlist entry → don't re-alert), and
- a **negative example** fed back into ER threshold tuning.

Wire this and say it out loud. Most teams will hand-wave "continuous improvement." We'll have
a mechanism.

---

## TASK 4 — Append-only audit trail (`casefile/audit.py`)

Every agent and every human writes an `AuditEvent`. **No UPDATE. No DELETE.**
Enforce it at the DB level with a trigger — it's five lines and it's a great Q&A answer.

```sql
CREATE RULE audit_no_update AS ON UPDATE TO audit_events DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO audit_events DO INSTEAD NOTHING;
```

**The risk timeline and the audit trail both derive from this one table.** Build it right and
the PS's *"compile a timeline of key events showing how and why the risk profile changed"*
requirement falls out for free — including the tier going **down** when a SEBI order is revoked.

---

## Definition of done

- [ ] Investigation agent runs a plan/execute loop and **can return `INSUFFICIENT_EVIDENCE`**.
- [ ] `Evidence.status` correctly splits `CONFIRMED` / `CORRELATED` / `MISSING`. Never collapsed.
- [ ] SAR generates all six fixed sections.
- [ ] **Citation validator strips uncited factual sentences** into `unverified_claims`.
- [ ] `citation_coverage >= 0.95`, printed in the demo.
- [ ] Side-by-side demo ready: generic-LLM SAR vs ours, with the refusals visible.
- [ ] Review workflow: 4 actions, all writing `ReviewerAction`.
- [ ] `DISMISS` produces a suppression rule + a negative example. The loop is closed.
- [ ] `audit_events` is append-only, enforced by a DB rule.
- [ ] Timeline (including a **de-escalation**) reconstructs purely from `audit_events`.
- [ ] `make demo-casefile` runs standalone against fixtures.

## Datasets you receive

**None.** You work entirely from `fixtures/`:

```
fixtures/assessments.json    your input (RiskAssessment + Evidence)
fixtures/cases.json          your output shape
fixtures/sar.json            a worked example with [EV-nnn] citations
fixtures/audit.json          audit event shapes
```

That's a feature — it means you are unblocked from minute zero.

## Do not touch

`core/` `watchlist/` `signals/` `ui/` `contracts/`.

---

## Pipeline hand-off (direct in-memory architecture — see `docs/06_PIPELINE.md`)

The orchestrator calls your package by TWO functions, only when `assessment.tier != "NONE"`.
Everything is a typed `contracts/models.py` object — no dicts, no DB between stages.

```python
def investigate(assessment: RiskAssessment) -> list[Evidence]:
    ...
def draft_sar(assessment: RiskAssessment, evidence: list[Evidence]) -> SAR:
    ...
```

Until you ship them, `core/orchestrator.py` backs both with `fixtures/` (SAR reuses the
golden `fixtures/sar.json` when the subject matches, else synthesizes a minimal draft).

### REQUIRED — Salvage 2: atomic review action (owned by you, `casefile/`)

Port this guarantee from the retired build's `review_report()`: a reviewer action MUST
flip the `Case` status **and** append the `AuditEvent` in **one transaction — both or
neither**. You can never approve/dismiss a case without leaving an immutable trail.

```python
def review(case_id: str, action: ReviewerAction) -> Case:
    with store.connect() as conn:      # single transaction
        # 1) update case status (INSERT OR REPLACE the Case row)
        # 2) append AuditEvent(action=..., object_type="Case", object_id=case_id)
        # commit both or roll back both
```

The `audit_events` table is append-only, enforced by a RAISING trigger (Salvage 1, in
`db/schema.sql`) — an attempt to UPDATE/DELETE an audit row FAILS LOUDLY. `db/store.py`
already writes audit rows inside a single `with conn:` transaction; extend that pattern
for the reviewer flip. **This is a requirement for `casefile/`, noted here because the
refactor session did not implement it in another package.**
