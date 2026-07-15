# Continuous KYC Autonomous Auditor

**CODE Hackathon — Tech Mahindra · Challenge 03 · "AI Delivered Right"**

Traditional KYC batch screening drowns compliance staff in false positives.
This system **suppresses them with evidence** — and proves it with numbers on real data.

## Read this first

- **Everyone:** [`docs/00_TEAM_README.md`](docs/00_TEAM_README.md) — repo rules, contracts, checkpoints
- **Your brief:** `docs/0N_<YOURNAME>_*.md`
- **The contracts:** [`contracts/models.py`](contracts/models.py) — the single source of truth

## Quickstart

```bash
cp .env.example .env          # add your ANTHROPIC_API_KEY
docker-compose up -d          # postgres + api
pytest tests/ -q              # 11 tests must pass
open http://localhost:8000/docs
```

Every API endpoint serves `fixtures/` out of the box. **You can build your whole package
before anyone else has written a line.**

## The pitch, in three real numbers

| | |
|---|---|
| **373** | name collisions *inside* the NSE/SEBI debarred list → resolved by PAN |
| **54** | names on **both** the MP register and the debarred list, sharing **zero identifiers** → never auto-link |
| **97 / 227** | UAPA aliases are bare tokens (`Salim`, `Hamza`, **`Amir Khan`**) → never trigger alone |

**Baseline (naive name screening), measured on our eval set:**

| | prevalence | precision | recall | false positives |
|---|---|---|---|---|
| stress | 6.10% | 0.452 | 0.656 | 97 |
| realistic | 0.20% | **0.169** | 0.656 | **394** |

At a realistic base rate, **83% of everything a compliance officer reviews is noise.**
That is the number we beat. `make eval` reproduces it.

## Data

| Layer | Source | Real? |
|---|---|---|
| NSE/SEBI debarred | OpenSanctions `in_nse_debarred` — 15,447 entities, PAN on 81% | ✅ |
| Lok/Rajya Sabha PEPs | OpenSanctions `in_sansad` — 2,670 PEPs, 3,028 RCAs, family graph | ✅ |
| MHA UAPA | 80 persons, 66 orgs, **name-only** | ✅ |
| Adverse media | GDELT + Indian financial RSS | ✅ live |
| Customer book | synthetic — 2k / 60k, **no labels**, built to break us | ⚠️ |

> No public dataset is a real bank's customer book, and one that was would be a compliance
> breach. Every risk signal is real. The synthetic half contains **no flags** — the system
> derives all of them.

## Ownership

| Package | Owner | Never edited by anyone else |
|---|---|---|
| `contracts/` `core/` `api/` `fixtures/` `eval/` | **Vaibhav** | ER ladder, risk scoring, orchestrator, eval harness |
| `watchlist/` | **Mohita** | 3 real lists, alias-quality gate, deltas, temporal replay |
| `signals/` | **Aditya** | GDELT/RSS, dedup, mention extraction, triage agent |
| `casefile/` | **Sneha** | Investigation agent, SAR + citation validator, review, audit |
| `ui/` | **Samaksh** | Six screens, replay control, before/after toggle |

**Rule: you only ever edit files inside your own package.** That is what keeps merges clean.

## Architecture

```
Signal ──(ER)──> Candidate ──(scoring)──> RiskAssessment ──> Case ──> SAR
   │                  │                        │              │        │
   └──────────────────┴────────────────────────┴──────────────┴────────┘
                        every step writes AuditEvent (append-only)
                        every claim carries Evidence [EV-nnn]
```

**Identifiability is inversely correlated with severity.** The list where a false negative is
catastrophic (UAPA, 146 entities) is the one with no identifiers at all. The list we can match
deterministically (NSE, PAN on 81%) is the least severe. That is not a bug in our system — it
is the state of Indian compliance data, and a system that *acknowledges* it instead of hiding
behind a fuzzy score is what "AI Delivered Right" means.

Agents go where non-determinism buys something: **adverse-media triage, ER adjudication of the
ambiguous band, investigation, SAR drafting.** Gates, scoring, and deterministic matching are
plain code. We don't dress cron jobs up as agents.

## Architecture

```
Watchlist Δ ──┐
              ├──► Signal ──(ER ladder)──> Candidate ──(gates+score)──> RiskAssessment
News/GDELT ───┘         │                       │                            │
                         └───────────────────────┴────────────────────────────┘
                              flows in memory — never persisted standalone
                                                    │
                                        (tier != NONE) ▼
                                            Evidence ──> SAR
                                                    │
                                                    ▼
                              PERSISTED: Case + SAR + AuditEvent  (SQLite, only sink)
                                                    │
                              every write appends AuditEvent (append-only, raises on UPDATE/DELETE)
                              every claim in a SAR carries Evidence [EV-nnn]
```