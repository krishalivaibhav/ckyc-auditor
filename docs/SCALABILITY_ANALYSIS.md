# TechMKYC — Scalability Analysis

> **Purpose.** A ground-up, source-grounded analysis of how this system scales:
> which parts carry to production volume unchanged, which parts break and at what
> point, and what each fix actually costs. Reasoned from the code (file:line
> references are real), not from the pitch.
>
> Companions: `docs/TECHNICAL_DEEP_DIVE.md` (how everything works),
> `docs/LIMITATIONS_AND_ROADMAP.md` (§1.4 / §3.2 cover scale at a summary level —
> this document is the detailed reasoning behind them).

---

## Table of contents

1. [The axes that actually stress the system](#1-the-axes-that-actually-stress-the-system)
2. [The O(C·W) screening wall](#2-the-ocw-screening-wall)
3. [What already scales: blocking + the ER ladder](#3-what-already-scales-blocking--the-er-ladder)
4. [The read-API: O(N) per request](#4-the-read-api-on-per-request)
5. [The sink: single-writer, ephemeral, blob-shaped](#5-the-sink-single-writer-ephemeral-blob-shaped)
6. [Audit table: unbounded, super-linear on re-runs](#6-audit-table-unbounded-super-linear-on-re-runs)
7. [Producers: sequential scan, no queue](#7-producers-sequential-scan-no-queue)
8. [LLM seams: gated, scale with ambiguity not volume](#8-llm-seams-gated-scale-with-ambiguity-not-volume)
9. [Other serial chokepoints](#9-other-serial-chokepoints)
10. [Capacity envelope — where it breaks, in order](#10-capacity-envelope--where-it-breaks-in-order)
11. [Vertical vs horizontal](#11-vertical-vs-horizontal)
12. [What the architecture got right for scale](#12-what-the-architecture-got-right-for-scale)
13. [Bottom line](#13-bottom-line)

---

## 1. The axes that actually stress the system

Scalability is not one number. This system is stressed along **six independent
axes**, and they fail at very different points:

| Axis | Symbol | Demo scale | Real bank scale | Component it stresses |
|---|---|---|---|---|
| Customer book size | **C** | ~10³ | 10⁶–10⁸ | Sanctions screening, news matching |
| Watchlist size | **W** | ~1.8×10⁴ | 10⁶+ (OFAC+UN+EU+PEP) | Blocking, screening |
| Signal throughput | **S** | a few/scan | 10³–10⁵/day | Pipeline, LLM seams, producers |
| Concurrent reviewers | **R** | 1 | 10²–10³ | Read-API, SQLite writer |
| Case + audit accumulation | **N** | dozens | 10⁷–10⁹ rows | Sink, read-API, audit |
| Tenancy / jurisdictions | **T** | 1 | many | Everything (no isolation today) |

The central finding: **the parts that were engineered carefully (the ER ladder)
scale beautifully; the parts that were "good enough for a demo" (the screening
loop, the read-API, the sink) hit walls surprisingly early.** The two walls hit
*first* are near-free to fix.

---

## 2. The O(C·W) screening wall

`Sanctions_agent/watchlist/monitor.py:87` — `find_hits`:

```python
for entry in active:          # W_active entries
    for cust in customers:    # C customers
        matched = index.candidates(cust.client_name, cust.pan)   # recomputed every pair!
        if any(m.watchlist_id == entry.watchlist_id for m in matched):
            yield SanctionHit(...)
```

This is the single worst scalability defect, and it is **both an algorithmic bug
and a scale wall**:

- Complexity is **O(W_active × C × cost(candidates))**. At C=10⁶, W_active=10⁵
  that is **~10¹¹ candidate computations per full pass**.
- Worse: `index.candidates(cust)` depends only on the *customer*, yet it is
  recomputed **once per (entry, customer) pair** — W_active times more often than
  necessary. The blocking index it calls was built precisely so you compute
  candidates **once per customer** (O(C · avg_block), avg_block < 50) and then
  check membership. The loop is inverted.

**The fix is free and enormous.** Invert to:

```python
for cust in customers:                      # O(C)
    for m in index.candidates(cust.client_name, cust.pan):   # avg_block < 50
        yield SanctionHit(cust, entry_by_id[m.watchlist_id], ...)
```

That drops it from O(W·C) to **O(C · avg_block)** — roughly a 10⁵× reduction at
scale — and removes the redundant recomputation entirely. This should be the #1
change; it needs no new infrastructure.

---

## 3. What already scales: blocking + the ER ladder

`investigation_agent/core/blocking.py` is the well-designed core. The `Blocker`
builds inverted indices (`by_pan`, `by_surname`, `by_phon_surname`, metaphone
keys) once at O(W), then `candidates(name, pan)` returns a **capped blocked set
targeted at < 50 entries per customer**. So resolution is:

- **O(1) amortized per customer regardless of W** — a customer is never compared
  against the full list.
- The resolver (Rungs 0–3, `core/resolver.py`) then does a handful of
  deterministic comparisons per blocked pair.

This is textbook entity-resolution blocking and carries to millions of watchlist
entries. **Two caveats at scale:**

- The indices are **in-process Python dicts** (`defaultdict(list)`). At W=10⁶
  that is a few hundred MB of RAM per process, rebuilt on every boot — acceptable,
  but it caps horizontal scaling because each pipeline replica holds a full copy.
  At W ≫ 10⁷ this wants an external index (Elasticsearch / Redis / pg trigram).
- Single Metaphone (a `jellyfish` limitation, noted in `blocking.py`)
  under-blocks on some names → a **recall-at-scale** (correctness) risk that grows
  with C, not a throughput problem.

---

## 4. The read-API: O(N) per request

`api/server.py` is a stdlib `ThreadingHTTPServer`, and the hot read path is
brutal at scale (`api/server.py:256`):

```python
return [json.loads(r["data"])
        for r in conn.execute("SELECT data FROM cases ORDER BY opened_at DESC")]
```

- **`/api/alerts` deserializes every case blob on every request.** No
  `LIMIT`/`OFFSET`, no cache. Blobs are 5–20 KB each (they embed customer +
  assessments + candidates + timeline + SAR). At N=10⁵ cases that is **0.5–2 GB of
  JSON parsed per page load**; at N=10⁶ the endpoint is unusable.
- `/api/audit` does `SELECT * FROM audit_events ORDER BY at DESC` — the **entire
  audit table** (which grows unbounded, see §6).
- `ThreadingHTTPServer` = one Python thread per connection under the GIL. Fine for
  R=1–10 reviewers; the megabyte-scale JSON deserialization is CPU-bound and
  serializes under the GIL well before R=100.

**This is the second bottleneck after the screening loop, and the one reviewers
*feel* first.** Fixes are conventional: server-side pagination + filtering (push
`tier`/`status`/`limit`/`offset` into SQL), a projected/denormalized "alert row"
table so the list view never touches full blobs, a short-TTL cache keyed on the
`changesProvider` revision the Flutter app already tracks, and a real ASGI server
(uvicorn workers) for R.

---

## 5. The sink: single-writer, ephemeral, blob-shaped

Three separate scaling properties of `investigation_agent/db/{schema.sql, store.py}`:

**(a) Single-writer serialization.** SQLite allows one writer at a time. Reviewer
writes (`review_case`, `review_sar`) and pipeline `persist()` all contend. With
WAL mode reads stay concurrent, but write throughput caps at roughly **hundreds
of small txns/sec on one box** — fine for R ≈ tens, a wall for a busy pipeline
(high S) writing cases while reviewers act. This is the stated "the DB is a sink,
not a bus" trade-off — correct for the demo, but it means **stages cannot scale
horizontally**, because they would all write one file.

**(b) The sink is ephemeral.** `store.init_db` (`db/store.py:45`) runs
`DROP TABLE IF EXISTS` on every boot — it rebuilds the schema from scratch each
start. Deliberate for a reproducible demo, but it means **there is no durable case
store today**; production replaces this with migrations (Alembic) against a
persistent DB, not a rebuild-on-boot.

**(c) Blob shape.** One `Case` = one row with a JSON `data` blob. Excellent for
the read path (UI reads one row, no joins) and for schema evolution — but you
**cannot index or query intermediates** (candidates, assessments, signals live
inside JSON). At scale, analytics ("all cases where a REJECTED `PAN_MISMATCH`
fired last month") require a warehouse ETL, or moving to Postgres `JSONB` with GIN
indexes. The `DATABASE_URL` seam is already shaped for the Postgres swap — the
logic does not change, only the driver.

---

## 6. Audit table: unbounded, super-linear on re-runs

`audit_events` is append-only by trigger (`RAISE(FAIL)` on UPDATE/DELETE) —
correct for integrity, but it has **no rotation and no partitioning**, and
`_merge_with_prior` re-ingests append a *fresh* audit trail every time (unique
`audit_id` per emission). So audit rows grow as **O(signals × re-runs per case)**,
not O(cases). A customer who trips 50 signals over a year, each re-assessed,
generates hundreds of audit rows. At bank throughput this is the table that
reaches 10⁸–10⁹ rows first, and the read-API reads it whole (§4). Needs:
time-partitioning, idempotent re-run audit (dedupe on a natural key), and
cold-archive to a warehouse with WORM retention for the regulated subset.

---

## 7. Producers: sequential scan, no queue

- **News agent** (`news_agent/signals/scanner.py:40`):
  `for entity in entities: news_fetcher.fetch(...)` — sequential, once per
  `SCAN_INTERVAL_MINUTES` (default 60, `router.py:36`). Throughput is **O(C)
  external API calls per cycle**, gated by the news provider's rate limit, not by
  CPU. At C=10⁶ you cannot scan every customer every hour through one NewsAPI key —
  you need entity prioritization (only watched/high-risk), fan-out workers, and
  provider-quota management. This axis scales with **money and API quota**, not
  code.
- **Both producers are fire-and-forget HTTP** with graceful degradation but **no
  durable queue, no retry-with-backoff, no dead-letter**. A dropped POST = a signal
  lost until the next scan. At low S the "next scan catches it" is acceptable; at
  high S with SLA requirements, a missed sanctions delta is a compliance miss. This
  is the classic case for Kafka/PubSub between producers and pipeline — correctly
  deferred, because a bus at demo scale is pure ops cost for zero benefit.

---

## 8. LLM seams: gated, scale with ambiguity not volume

Two LLM calls exist (news triage, investigation adjudication), and crucially
**both are gated**:

- Investigation only runs on CRITICAL/EDD/AMBIGUOUS — a settled PAN-exact match
  spends **zero** LLM.
- Adjudication uses forced tool-use (schema-bounded) with a deterministic offline
  fallback.

So LLM cost/latency scales with the number of *ambiguous* cases, not total
volume — the right design. The scaling concerns are ordinary: **per-call latency
(~seconds) serializes the pipeline** unless investigation is made async/batched;
**provider rate limits and cost** at high S (needs request pooling + caching on
`content_hash`); and news triage runs per-article, so at high article volume that
is the larger LLM bill. None are architectural walls — throughput-tuning and
budget.

---

## 9. Other serial chokepoints

- **PDF via headless Chrome** (`/sar/pdf`): spawns a Chrome process per render —
  hundreds of MB and ~1 s each, serialized. Fine for occasional reviewer
  downloads; a wall if SARs are batch-generated. Needs a render pool/queue or a
  server-side PDF library.
- **Alerting** fires only on the demo time-skip, not on live HIGH/CRITICAL
  crossings — so there is **no alert scaling path in live mode yet** (no fan-out,
  dedup, throttling, or SLA escalation). It is a demo channel (single Gmail
  sender), not a system.
- **Three separate ER implementations** (news LLM ER, sanctions `ScreeningIndex`
  soundex, ambiguity `Blocker` metaphone) — a *maintenance* scalability problem:
  they drift as the book grows, and blocking recall is tuned in three places.
  Consolidating behind one normalization/blocking library is a prerequisite to
  scaling matching quality.

---

## 10. Capacity envelope — where it breaks, in order

Ranked by which wall you hit *first* as you scale up from the demo:

| # | Bottleneck | Breaks around | Nature | Fix cost |
|---|---|---|---|---|
| 1 | `find_hits` O(W·C) + redundant recompute | C·W ≳ 10⁷ (minutes→hours/pass) | **Algorithmic bug** | **Trivial** — invert the loop |
| 2 | Read-API loads all blobs, no pagination | N ≳ 10⁴–10⁵ cases | Missing pagination/cache | Low — SQL LIMIT + projected list table |
| 3 | SQLite single writer | R ≳ tens, or high S | Architectural | Medium — Postgres via `DATABASE_URL` |
| 4 | Audit unbounded growth | N ≳ 10⁷ rows | Missing lifecycle | Medium — partition + idempotent + archive |
| 5 | Producers no queue/backpressure | high S with SLA | Missing durability | Medium — Kafka/PubSub + DLQ |
| 6 | News scan sequential O(C)/cycle | C ≳ 10⁵ | External-quota bound | Medium — prioritize + fan-out |
| 7 | In-process pipeline (no HZ scaling of stages) | sustained high S | Architectural | High — but seams already shaped |
| 8 | In-RAM blocking index per replica | W ≳ 10⁷ | Memory | Medium — external index |

The pleasing property: **#1 and #2 — the first two walls — are cheap to fix and
need no new infrastructure.** They are demo shortcuts, not architectural debt. The
genuinely architectural items (#3, #5, #7) are exactly the ones the design left
seams for (`DATABASE_URL`, HTTP producer boundaries, the load-bearing Pydantic
contract).

---

## 11. Vertical vs horizontal

- **Scales up (vertical) well:** the pipeline is one process; a bigger box with
  more RAM (for indices) and cores buys a lot, because the expensive work
  (blocking) is already O(1)/customer. With #1 and #2 fixed, a mid-size bank
  likely runs on one beefy box + Postgres.
- **Does NOT scale out (horizontal) today:** three things block replicas —
  (a) the SQLite single-writer sink, (b) each replica holding a full in-RAM
  blocking index, (c) no idempotency/dedup keys on ingest, so two replicas
  processing the same signal would double-write (merge logic protects same-case,
  not concurrent duplicate ingests). Horizontal scaling requires a shared Postgres
  sink, a shared/external index, and idempotency keys on `content_hash` — all on
  the roadmap, none requiring a logic rewrite.

---

## 12. What the architecture got right for scale

Worth stating plainly, because it is why the roadmap is "replace stubs and harden
edges" rather than "rewrite":

1. **The Pydantic contract is the load-bearing wall.** Because stages exchange
   typed objects, any stage can later be pulled into its own service without
   touching the others. The single most important scalability decision.
2. **Blocking-before-resolution** — the matching core is already sub-linear in W.
3. **Gated LLM** — cost scales with ambiguity, not volume.
4. **`safe()`-wrapped stages + degrading producers** — the failure model is
   already "degrade, don't crash," which is what you need under load.
5. **`DATABASE_URL` + HTTP producer seams** — the two hardest migrations
   (Postgres, message bus) have designated insertion points.

---

## 13. Bottom line

> The matching **core** (blocking + PAN ladder + gated LLM) is genuinely
> scale-shaped and will carry to millions of customers. The **plumbing around it** —
> the O(W·C) screening loop, the un-paginated read-API, the ephemeral
> single-writer SQLite sink, and the queue-less producers — is demo-grade and will
> break between 10⁴ and 10⁷ on the various axes. The two walls you hit *first*
> (screening loop, pagination) are near-free to fix; the rest are the ordinary
> Postgres/queue/ASGI hardening the roadmap already sequences, made cheap by the
> typed contract.
