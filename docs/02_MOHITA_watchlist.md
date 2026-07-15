# MOHITA — `watchlist/`

**You own the reference data spine.** Every other package depends on what you produce. Read
`00_TEAM_README.md` first.

Your old scope was "the sanctions part." It's bigger and more interesting than that: you own
**all three real regulatory lists**, the **delta feed** that triggers alerts without any news,
and the **temporal replay engine** that makes the whole demo work live.

**Nobody else touches real watchlist data.** They consume `WatchlistEntry` objects from you.

---

## Clean your branch

```bash
git fetch origin && git checkout main && git reset --hard origin/main
git branch -D <your-old-branch>
git push origin --delete <your-old-branch>
git checkout -b feat/watchlist
docker-compose up -d && pytest tests/ -q
```

Work against `fixtures/watchlist.json` until your loaders run. Do not wait for anyone.

---

## What everyone else is building

- **Vaibhav** (`core/`) — entity resolution + risk scoring. **Your biggest consumer.** He queries
  your screening index with a messy customer name and needs back a small candidate set.
- **Aditya** (`signals/`) — news ingestion. He needs your **name list** to know who to search for.
- **Sneha** (`casefile/`) — SAR + audit. She needs your **`source_url`** fields for citations.
- **Samaksh** (`ui/`) — dashboard. Renders your entries in the evidence panel.

---

## Your three real datasets

| File | What it is |
|---|---|
| `targets_nested_stock_.json` | OpenSanctions `in_nse_debarred` — 15,447 entities, 15,998 sanction orders, dates 2004-02-01 → 2026-07-09 |
| `sebi_stock_.xls` | **raw NSE source** — 11,698 rows. Has `Order Particulars`, `DIN/CIN`, circular numbers |
| `other_stock_.xlsx` | **raw NSE source** — 4,437 rows, same schema |
| `targets_nested_sabha_.json` | OpenSanctions `in_sansad` — 2,670 PEPs, 3,028 RCAs, family graph, occupancy dates |
| `targets_nested_mha_.json` | OpenSanctions MHA — 80 persons, 66 orgs, **name + alias only** |

**Important:** the raw XLS beats the OpenSanctions export in one respect — OpenSanctions
**dropped the DIN/CIN** and kept `registrationNumber` on only 693 entities. Join raw XLS →
OpenSanctions **on PAN** and take the union. (Caveat: DIN/CIN is sparse — 9,910 of its values
are literally `"-"`. Only ~748 real DINs + 46 CINs exist. Use it opportunistically, don't
architect on it.)

---

## TASK 1 — Canonical loader (`watchlist/load.py`)

Produce `WatchlistEntry` objects (see `contracts/models.py`) into Postgres. Three loaders, one
schema. Every entry needs `source_url` — those are **real NSE circular PDFs**
(`archives.nseindia.com/content/circulars/INVG50070.pdf`) and they become our citations.

### 1a. Entity type from PAN 4th character
The OpenSanctions schema flattens **everything** to `LegalEntity` — no person/company
distinction at all. PAN gives it back, deterministically:

```python
PAN_TYPE = {"P": "Individual", "C": "Corporate", "H": "HUF", "F": "Firm", "T": "Trust"}
entity_type = PAN_TYPE.get(pan[3], "Unknown") if len(pan) == 10 else "Unknown"
# observed: P=9,686  C=2,332  H=296  F=130
```

### 1b. Active vs revoked
`duration` values are filthy — `TILL FURTHER ORDERS` (3,672), `REVOKED` (2,596),
`Revoked 20072018` (1,308), `DEBARMENT REVOKED` (519), `PAN REVOKED` (116), `10 Years`, `48`…
Normalise to `status ∈ {active, revoked}` + an `end_date` where computable.
**144 revocations exist in the SEBI file.** They matter — see Task 3.

### 1c. Alias quality classification — **THIS IS CRITICAL, DO NOT SKIP**

MHA has 227 aliases. **97 are single tokens.** Classify every alias:

```python
def classify_alias(a: str) -> str:
    if re.fullmatch(r"\(?[A-Z][A-Z\-()]{1,7}\)?", a):  return "org_acronym"   # (LTTE), PREPAK
    if len(a.split()) == 1:                            return "bare_token"    # Salim, Hamza
    if a.lower() in COMMON_INDIAN_NAMES:               return "bare_token"    # Amir Khan!!
    return "full_name"
```

The `bare_token` bucket includes: `Salim` `Salman` `Hamza` `Zakir` `Ismail` `Sultan` `Aziz`
`Mustafa` `Mushtaq` `Sikander` `Fareed` `Khursheed` `Mufti` `Moulvi` `Ustad` `Doctor` `Chief`
`chacha` — and in two-token form, **`Amir Khan`**, **`Gulshan Kumar`**, **`Abdul Manan`**.

> A naive alias screen flags **every customer named Amir Khan as a UAPA-designated terrorist.**
> Vaibhav's resolver enforces "bare tokens never trigger alone" — **but only if you label them.**
> If you get this wrong, his alias gate cannot work and we lose one of our three headline numbers.

Meanwhile the *real* matching challenge is the opposite end: `Hafiz Muhammad Saeed` carries
8 transliterations. Keep every one of those as `full_name` — Vaibhav's phonetic matcher needs them.

### 1d. Co-accused clusters (free relationship graph, no synthesis)
`sebi_stock_.xls`: 11,698 rows → **1,515 unique `Order Particulars`.** Entities sharing an
order are co-accused. One Pyramid Saimira order names **254 entities**.

Emit `order_id` (hash the order text) on every entry. Vaibhav uses it for network exposure:
*"your client's director was debarred in the same SEBI order as 253 other parties."*
Nobody can fake this and almost nobody else will have it.

### 1e. PEP currency + family graph (Sabha)
- **794 current** occupancies vs 1,876 former. `status ∈ {current, former}`.
  A former MP doesn't stop being a PEP the day they leave office — there's a cooldown.
  Model `current → EDD` / `former + within N years → EDD decaying` / `beyond → MONITOR`.
- **3,028 RCAs**, 3,129 family links (spouse 1,222 / mother 1,035 / father 874).
  Expose a `relatives(watchlist_id)` lookup. *"Your customer's spouse is a sitting MP"* is a
  genuine EDD trigger and it is **real data**.

---

## TASK 2 — Screening index (`watchlist/index.py`)

Vaibhav queries this. It must be fast and it must not return 18,222 rows.

```python
class ScreeningIndex:
    by_pan:    dict[str, WatchlistEntry]        # exact, O(1). the deterministic gate.
    by_name:   dict[str, list[WatchlistEntry]]  # normalised
    by_phonetic: dict[str, list]                # double-metaphone -> for UAPA translits
    by_surname_block: dict[str, list]           # blocking key

    def candidates(self, name: str, pan: str | None) -> list[WatchlistEntry]:
        """Return < 50 candidates. Never the whole list."""
```

Normalisation must strip `Shri / Shrimati / Smt / Mr / Dr / Mohd`, handle `SURNAME, First`
comma inversion, and collapse whitespace. Our customer book is deliberately messy.

---

## TASK 3 — Delta feed + temporal replay (`watchlist/replay.py`)

**This is what makes the demo work. Without it, nothing happens while the judges watch.**

### 3a. Deltas as Signals
A watchlist change emits a `Signal(signal_type="WATCHLIST_DELTA")` — **independent of news.**
Someone quietly added to a designated list with zero press coverage must still fire. That is
exactly the scenario KYC exists for, and it is the failure mode of a news-only design.

### 3b. Temporal replay engine
The data has `first_seen`, `last_change`, `Order Date`, and 144 revocations. So:

```python
class ReplayClock:
    """Set the clock to 2024-01-01, stream orders forward at 1000x.
    Same code path as the live poller — only the clock source differs."""
    def run(self, start: date, end: date, speed: int): ...
```

This gives you three things nobody else will have:
1. **"Near real-time monitoring" demonstrated, not claimed.** The dashboard lights up live.
2. **Risk timelines that actually populate** — the PS demands *"how and why the risk profile changed."*
3. **DE-ESCALATION.** An order gets revoked → risk goes **down**. The system is willing to say
   *"no longer risky."* Almost nobody builds that, and it is a very strong AI-Delivered-Right beat.

Expose `POST /api/replay?from=&to=&speed=`. Samaksh puts a button on it.

---

## Definition of done

- [ ] All three lists load into one canonical `WatchlistEntry` schema, in Postgres.
- [ ] `entity_type` derived from PAN 4th char. `status` normalised (active/revoked/current/former).
- [ ] **`alias_quality` classified on every alias.** 97 bare tokens correctly labelled.
- [ ] `source_url` populated on every entry (Sneha's citations depend on it).
- [ ] `order_id` emitted → co-accused clusters queryable.
- [ ] `relatives()` lookup works off the Sabha family graph.
- [ ] `ScreeningIndex.candidates()` returns < 50 for any input. Reduction ratio measured.
- [ ] `WATCHLIST_DELTA` signals emit **without any news input**.
- [ ] `ReplayClock` streams 2024→2026 at speed; at least one **revocation → downgrade** visible.
- [ ] `make demo-watchlist` runs standalone.

## Datasets you receive

```
targets_nested_stock_.json      (primary — NSE/SEBI debarred)
sebi_stock_.xls                 (raw — has Order Particulars + DIN/CIN)
other_stock_.xlsx               (raw)
targets_nested_sabha_.json      (PEP + RCA + family graph)
targets_nested_mha_.json        (UAPA — name + alias only)
```

Ignore any `senzing_*`, `entities_ftm_*`, `targets_simple_*`, `names_*` variants — they are the
same data in other export formats and will only confuse you.

## Do not touch

`core/` `signals/` `casefile/` `ui/` `contracts/`.

---

## Pipeline hand-off (direct in-memory architecture — see `docs/06_PIPELINE.md`)

The orchestrator calls your package by ONE function. Everything is a typed
`contracts/models.py` object — no dicts, no DB between stages.

```python
def load_watchlist() -> list[WatchlistEntry]:
    ...
```

Until you ship it, `core/orchestrator.py` backs this stage with `fixtures/watchlist.json`.
When your real function lands at this exact signature, the orchestrator swaps the import
and nothing else changes.
