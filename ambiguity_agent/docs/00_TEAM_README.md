# Continuous KYC Autonomous Auditor — Team README

> **Read this before you touch a line of code.** Every member's brief assumes it.
> This file lives in `main`. It is the contract between the five of us.

---

## The problem in one line

Traditional KYC batch screening drowns compliance staff in false positives. We built a system
that **suppresses them with evidence** — and can prove it with numbers on real data.

## The pitch in three numbers (all measured, all from real Indian regulatory data)

| | |
|---|---|
| **373** | name collisions *inside* the NSE/SEBI debarred list → resolved by PAN |
| **54** | names on **both** the MP register and the debarred list, sharing **zero identifiers** → must never auto-link |
| **97 of 227** | UAPA aliases are bare tokens (`Salim`, `Hamza`, `Amir Khan`) → must never trigger alone |

**Baseline (naive name screening) on our eval set: precision 0.169, 394 false positives.**
That is the number we beat. Everything we build points at that number.

---

## Data: what is real and what is not

| Layer | Source | Real? |
|---|---|---|
| NSE/SEBI debarred entities | OpenSanctions `in_nse_debarred` — 15,447 entities, 15,998 orders, PAN on 81% | ✅ **real** |
| Lok/Rajya Sabha PEP register | OpenSanctions `in_sansad` — 2,670 PEPs, 3,028 RCAs, family graph | ✅ **real** |
| MHA UAPA designations | OpenSanctions — 80 persons, 66 orgs, name-only | ✅ **real** |
| Adverse media | GDELT + Indian financial RSS | ✅ **real, live** |
| Customer book | synthetic, 2k / 60k | ⚠️ **synthetic — and it has to be** |

**Say this out loud when asked, exactly this way:**

> *No public dataset is a real bank's customer book, and one that was would be a compliance
> breach. Every risk signal we use is real. The synthetic half contains **no labels** — the
> system derives every flag. And we built it ~20× harder than reality on purpose: over half
> the seeded customers are traps designed to make us fail.*

---

## The architectural insight (this is the deck's centre slide)

| Source | Entities | Identifier | Severity |
|---|---|---|---|
| NSE/SEBI debarred | 15,447 | **PAN, 81%** | Medium |
| Sabha PEP register | 5,700 | none (DOB 46%) | Contextual |
| MHA UAPA | **146** | **none at all** | **Maximum** |

> **Identifiability is inversely correlated with severity.**
> The list where a false negative is catastrophic is the one you can least reliably match on.

That is not a bug in our system. It is the state of Indian compliance data. A system that
*acknowledges* it — instead of hiding behind a fuzzy score — is what "AI Delivered Right" means.

**Consequence:** we use agents where non-determinism buys something, and deterministic code
everywhere else. Say that too. "We used agents only where they earn their keep" is itself a
strong AI-Delivered-Right narrative, and judges notice teams who dress up cron jobs as agents.

---

## Repo: ONE monolith, FIVE packages

Not five microservices. One FastAPI app, one Postgres, one `docker-compose up`.

```
ckyc/
├── contracts/        VAIBHAV ONLY.  models.py = the single source of truth.
├── core/             VAIBHAV.  entity resolution, risk scoring, orchestrator.
├── watchlist/        MOHITA.   3 real lists -> canonical store, deltas, temporal replay.
├── signals/          ADITYA.   GDELT/RSS ingest, dedup, mention extraction, triage.
├── casefile/         SNEHA.    investigation agent, SAR, review workflow, audit trail.
├── ui/               SAMAKSH.  analyst dashboard.
├── api/              VAIBHAV.  thin FastAPI. each package exposes a router.
├── fixtures/         VAIBHAV.  golden JSON for every contract object. YOUR LIFELINE.
├── eval/             VAIBHAV.  the harness. the before/after number.
├── data/             raw datasets.
└── tests/            each package owns tests/<package>/
```

### The three rules that stop this build going sloppy

**1. You only ever edit files inside your own package.**
If your change touches someone else's directory, it is the wrong change. This makes git merges
essentially conflict-free — which is the entire reason we are doing it this way.

**2. `contracts/models.py` is frozen at Checkpoint 0.**
Need a field? Ping Vaibhav. Do **not** add it locally. Do **not** work around it by passing
dicts. The moment two people have different ideas of what a `Signal` is, we are back to last time.

**3. Work against `fixtures/` from minute zero. Nobody blocks on anybody.**
Samaksh builds the entire dashboard with no backend. Sneha drafts SARs with no ER. Aditya
tests mention-extraction with no watchlist. If you are ever "waiting on someone", you are
doing it wrong — go read `fixtures/`.

---

## Clean your branch and start fresh

Vaibhav resets `main` to the new scaffold first. **Do not do this until he says main is ready.**

```bash
# 1. get the new main
git fetch origin
git checkout main
git reset --hard origin/main        # discards local main; the new scaffold is authoritative

# 2. nuke your old branch (local + remote). the old build is dead.
git branch -D <your-old-branch>
git push origin --delete <your-old-branch>

# 3. fresh branch off the new main
git checkout -b feat/<your-package>     # feat/watchlist, feat/signals, feat/casefile, feat/ui

# 4. sanity check — this must pass before you write anything
docker-compose up -d
pytest tests/ -q
python -c "from contracts.models import Signal, RiskAssessment; print('contracts ok')"
```

**Commit to your branch often. Rebase on `main` daily. Never merge another feature branch into yours.**

---

## Integration checkpoints (these are hard gates, not suggestions)

| | What must be true |
|---|---|
| **CP0** | `main` has contracts + fixtures + docker-compose + DB schema. Everyone has branched. **Contracts freeze here.** |
| **CP1** | Every package runs standalone against fixtures. `make demo-<pkg>` works for all five. **Merge all five to main. Full pipeline runs end-to-end on fixtures.** |
| **CP2** | Real data flowing. `eval/` reports precision/recall at both base rates. UI renders a real case with real citations. |
| **CP3** | Temporal replay demo works. SAR generates with citation coverage ≥ 0.95. Deck done. |

> **CP1 is the one that saves us.** Last time integration happened at the end and nothing fit.
> This time the full pipeline runs on fake data *early*, then we swap fake for real. If your
> package isn't merged at CP1, we cut it.

---

## Contracts (abridged — full version in `contracts/models.py`)

The pipeline is a straight line. Learn it:

```
Signal ──(ER)──> Candidate ──(scoring)──> RiskAssessment ──> Case ──> SAR
   │                  │                        │              │        │
   └──────────────────┴────────────────────────┴──────────────┴────────┘
                            every step writes AuditEvent
                            every claim carries Evidence[EV-nnn]
```

| Object | Produced by | Consumed by |
|---|---|---|
| `Customer` | (given) | core, casefile, ui |
| `WatchlistEntry` | **Mohita** | core, signals, casefile |
| `Signal` | **Aditya** (news), **Mohita** (deltas) | core |
| `Candidate` | **Vaibhav** | core, casefile, ui |
| `RiskAssessment` | **Vaibhav** | casefile, ui |
| `Evidence` | everyone | casefile, ui |
| `Case`, `SAR`, `ReviewerAction`, `AuditEvent` | **Sneha** | ui |

### Two contract rules everyone must internalise

**`Evidence.status` has three values and you may not collapse them.** The problem statement
explicitly demands we separate *confirmed evidence*, *correlated signals*, and *missing
evidence*. `CONFIRMED` / `CORRELATED` / `MISSING`. This shows up in the UI and in the SAR.

**A `REJECTED` Candidate is not garbage — it is the product.** `rejection_reason` is
**mandatory** on rejection, and those rejections populate the suppression log, which is the
screen that wins us the hackathon. Never silently drop a non-match.

---

## Risk tier ladder (deterministic gates, then soft score)

```
GATES (hard, no scoring involved):
  MHA UAPA, corroborated           -> CRITICAL   SAR mandatory, human sign-off, ALWAYS
  NSE debarred, PAN-exact, active  -> HIGH       escalate
  NSE debarred, order REVOKED      -> DOWNGRADE  risk goes DOWN. show it. nobody else does.
  PEP current / RCA                -> EDD        NOT adverse media. different workflow.
  name-only match, no corroboration-> SUPPRESS   logged with reason, never surfaced

SOFT SCORE (0..1), only for things no gate caught:
  severity x source_credibility x recency_decay x ER_confidence
  + PEP status, + network exposure (co-accused in the same SEBI order)
```

**The threshold is not picked by vibes.** Sweep it on `eval/`, plot precision/recall, pick the
point where precision hits target. In the deck we say *"0.62, because that's where precision
reaches 0.90 on our benchmark"* — with the actual number. That answer wins Q&A.

---

## What we are NOT building

Say no to these out loud, early:

- ❌ Kafka / Celery / microservices. One process, one DB.
- ❌ A "no-code agent builder". Wrong problem statement.
- ❌ Transaction monitoring / AML typologies. Wrong problem statement.
- ❌ Fine-tuning anything.
- ❌ An agent for every step. Scoring, gates, and deterministic matching are **code**.
      Agents go where non-determinism buys something: adverse-media triage, ER adjudication
      of the ambiguous band, investigation, SAR drafting. That is four. That is enough.
