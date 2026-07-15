# MOHITA — amendment to `02_MOHITA_watchlist.md`

> **This does not replace your brief.** Read `02_MOHITA_watchlist.md` as written — all four
> tasks, every judgement call, the alias gate, the replay engine. This file changes **two lines**
> in it and adds one build step.
>
> Short version: **you no longer write to a database at all.** Postgres is gone from your package.

---

## What changed, team-wide

Two decisions, both final. No more DB debate.

1. **SQLite, and Docker is gone.** Nothing to install, works offline, no shared cloud DB.
2. **Components connect directly, in memory.** Your package exposes a function that takes
   contract objects and returns contract objects. An orchestrator chains them. The DB is a
   **sink for finished output only** — `Case`, `SAR`, `AuditEvent`. Nothing else.

Those three objects are Sneha's. **She is now the only person on the team who writes to the DB.**

---

## Line-by-line diff to your brief

### 1. Clean your branch — the `docker-compose` line is dead

Your brief says:
```bash
docker-compose up -d && pytest tests/ -q
```

It's now:
```bash
git clone https://github.com/krishalivaibhav/ckyc-auditor && cd ckyc-auditor
python3 -m venv .venv && source .venv/bin/activate    # use a FRESH venv
pip install -r requirements.txt
pytest tests/ -q                                       # must say: 11 passed
git checkout -b feat/watchlist
```

Two more things your brief gets wrong because it predates the repo:

- **Skip the "delete your old branch" step.** This is a brand-new repo. There is nothing to delete.
- **`git pull` before you run anything.** Two fixes landed after the briefs went out
  (`pyproject.toml` for the pytest path, a relaxed pydantic pin). Without them `pytest` fails
  on a fresh clone and it looks like the repo is broken. It isn't.

### 2. Task 1 — "into Postgres" becomes "in memory"

Your brief opens Task 1 with *"Produce `WatchlistEntry` objects into Postgres."*

It's now:

```python
def load_watchlist() -> list[WatchlistEntry]:
    """The canonical store. Returned, not persisted."""
```

That's it. Same objects, same schema, same everything — they just get returned instead of
INSERTed. **Task 2 (`ScreeningIndex`) is completely unaffected** — it was already plain
in-memory dicts (`by_pan`, `by_name`, `by_phonetic`, `by_surname_block`). Nothing to change there.

### 3. Definition of done

> ~~All three lists load into one canonical `WatchlistEntry` schema, **in Postgres**.~~
> All three lists load into one canonical `WatchlistEntry` schema, returned by `load_watchlist()`
> and cached to `data/watchlist_canonical.json`.

Every other checkbox in your brief stands exactly as written.

---

## The one new thing: build once, load fast

Parsing 44 MB of JSON + XLS on every single run is miserable, and you'll run it a hundred times.
Split your package in two:

```
watchlist/build.py     SLOW. Run it once (and after any rule change).
                       Reads the raw files -> does ALL the hard work:
                         - PAN 4th-char entity_type
                         - duration normalisation (active/revoked + end_date)
                         - alias_quality classification      <- the important one
                         - order_id hashing (co-accused clusters)
                         - Sabha occupancy status + family graph
                       Writes data/watchlist_canonical.json

watchlist/load.py      FAST. load_watchlist() reads that artifact -> list[WatchlistEntry].
                       No raw files needed. Deterministic. Sub-second.
```

**This is not a database.** It's a derived artifact — like a compiled asset. Your judgement
lives in `build.py`; `load.py` just deserialises. If someone questions a label, they re-run
`build.py` and diff the artifact. That's a better audit story than a DB table anyway.

**Commit the artifact** (if it lands under ~20 MB). Two reasons:

- It **replaces the stub**. `data/watchlist_canonical.csv` currently in the repo is a quick
  flatten Vaibhav generated. It has no `source_url`, no aliases, no `alias_quality`, and an
  `extra` column that means five different things depending on the row. Aditya is building
  against it right now and needs to swap to yours at CP1. **Tell him when it lands.**
- Nobody else should ever need the raw 44 MB.

Add the raw files to `.gitignore` (they already are). Commit only the artifact.

---

## Task 3 — replay, with one signature change

`ReplayClock` no longer writes. It **yields**:

```python
def replay(start: date, end: date, speed: int) -> Iterator[Signal]:
    """Set the clock to 2024-01-01, stream orders forward at 1000x.
    Same code path as the live poller — only the clock source differs."""
```

The orchestrator consumes the iterator and drives the pipeline. That was always the design —
"same code path, different clock" — it just now means the same *function*, not the same table.

Same for deltas: `WATCHLIST_DELTA` signals are returned, not INSERTed. **They still fire
independently of news.** That requirement is unchanged and it's still the reason a news-only
design is a single point of failure.

`POST /api/replay?from=&to=&speed=` still exists. `api/` is Vaibhav's — you expose a router,
he mounts it. Samaksh has a button wired to it.

---

## What has NOT changed — and it matters more now, not less

**`contracts/models.py` is still frozen. It is still the only thing that crosses a boundary.**

Read that twice. Removing the database removed the *schema* — the thing that was silently
forcing everyone's shapes to match. Now **nothing** catches a wrong shape except the contract
itself. So:

- Never return a dict. Return `WatchlistEntry`.
- Never add a field to `contracts/models.py`. If one seems missing, ping Vaibhav — don't add it,
  and don't work around it by stuffing data somewhere it doesn't belong.
- If your coding agent wants to "just add a field so this fits" — that's the hour-20 bug from
  the last build, arriving early.

---

## Before you write anything: 30-second check

If you've already started and leaned on Postgres features, find out now:

```bash
grep -rin "jsonb\|::json\|gen_random_uuid\|SERIAL\|TIMESTAMPTZ\|psycopg2\|create_engine" \
  watchlist/ 2>/dev/null
```

Anything? Tell Vaibhav before you build on it. Nothing? You're clean — your package was never
DB-coupled in the first place.

---

## Your package's entire public surface

These four things are the whole contract between you and the rest of the system. Everything else
in `watchlist/` is yours and nobody else's business.

```python
def load_watchlist() -> list[WatchlistEntry]
def replay(start: date, end: date, speed: int) -> Iterator[Signal]
def relatives(watchlist_id: str) -> list[WatchlistEntry]

class ScreeningIndex:
    def candidates(self, name: str, pan: str | None) -> list[WatchlistEntry]
```

---

## Nothing else moved

To be explicit, because this is the part that matters and the DB noise obscures it:

- **Task 1c — the alias-quality gate is unchanged and it is still the most important thing you
  own.** 97 of 227 UAPA aliases are bare tokens (`Salim`, `Hamza`, `Amir Khan`, `Doctor`).
  If you don't label them, Vaibhav's `ALIAS_BARE_REJECT` gate is dead code, Samaksh's
  suppression screen loses an entire row type, and we lose one of our three headline numbers.
  Meanwhile `Hafiz Muhammad Saeed`'s 8 transliterations must stay `full_name` or the phonetic
  matcher can never catch him. That line — never-fire vs only-way-we-catch-him — is yours to draw,
  on the one list with zero identifiers and maximum severity.
- **Task 1d — co-accused clusters.** 11,698 rows → 1,515 orders. One Pyramid Saimira order names
  254 entities. Real relationship graph, zero synthesis.
- **Task 3b — temporal replay.** Still the thing that makes the live demo exist at all, including
  the revocation that drives a tier **down**.
- **`source_url` on every entry.** Real NSE circular PDFs. Sneha's citations and Samaksh's
  evidence panel both dead-end without them.

You're not combining datasets. You're deciding what the truth is that three other packages
resolve, search, and cite against.
