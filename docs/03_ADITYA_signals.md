# ADITYA — `signals/`

**You own the trigger layer.** Everything else in the system is a static list. You are the only
live input. Read `00_TEAM_README.md` first.

Your old scope was "the news scraper." The scraping is the easy 20%. The 80% that matters —
and the part that was sloppy last time — is **dedup, mention extraction, and triage**. A scraper
that fires five alerts for one story reported by five outlets is worse than no scraper.

---

## Clean your branch

```bash
git fetch origin && git checkout main && git reset --hard origin/main
git branch -D <your-old-branch>
git push origin --delete <your-old-branch>
git checkout -b feat/signals
docker-compose up -d && pytest tests/ -q
```

Work against `fixtures/signals.json` and `fixtures/watchlist.json` from minute zero.
**Do not wait for Mohita's loaders.**

---

## What everyone else is building

- **Mohita** (`watchlist/`) — the three real regulatory lists. She gives you the **name list** you
  search for. She *also* emits `Signal`s (watchlist deltas), so you are not the only trigger.
- **Vaibhav** (`core/`) — entity resolution. **He consumes your `Signal`s.** You extract *names*;
  he resolves them to *entities*. **Do not try to do his job.** See the boundary below.
- **Sneha** (`casefile/`) — SAR. Your `source_url` + `raw_excerpt` become her citations.
- **Samaksh** (`ui/`) — renders your headlines and excerpts in the evidence panel.

### The boundary that keeps us clean

> **You extract mentions. Vaibhav resolves entities. You never decide who someone *is*.**

Your output says *"this article mentions the string `Anand Sharma`"*. It never says *"this is
customer C1234"*. That's ER, that's his ladder, and if you both do it we get two different
answers and a merge fight. `Signal.mentioned_names` is a list of **strings**.

---

## Your data: none. You pull it live.

That's deliberate — real news costs us nothing from our synthetic budget, and it makes the
"3 real sources + 1 synthetic" story clean.

### Primary: GDELT
Free, no API key, ~15-min update cadence, queryable by name, returns article URL + tone + date.
`https://api.gdeltproject.org/api/v2/doc/doc?query=...&mode=artlist&format=json`

### Secondary: Indian financial RSS
Economic Times, Business Standard, Moneycontrol, LiveMint. Cheap and high-precision for Indian
adverse media — which is exactly our domain.

### Who do you search for?
Mohita's watchlist names + the customer book's high-exposure names. Don't search 18,222 names
every cycle — prioritise by `exposure_inr` and by tier. That prioritisation is itself a good
answer to *"how does this scale?"*

---

## TASK 1 — Fetcher (`signals/fetch.py`)

Poll on an interval. **Do not dress a cron job up as an agent** — judges notice, and we have a
stronger story: *"we used agents only where they earn their keep."* This is a worker.

- Respect `robots.txt`, rate-limit, cache aggressively.
- Store the **raw response** — Sneha's audit trail needs provenance.
- Never let a fetch failure kill the pipeline. Log, skip, continue.

---

## TASK 2 — Dedup (`signals/dedup.py`) — **the part that was sloppy last time**

Three layers, in order:

1. **`content_hash`** — exact duplicate. Same article, fetched twice. Drop.
2. **`story_cluster_id`** — *the same event reported by five outlets.* Cluster on
   (embedding similarity of headline+lede) × (published within 48h). **One story → ONE signal**,
   with all five URLs attached as corroborating evidence. Five alerts for one story is exactly
   what "drowning compliance staff" means.
3. **`is_rehash`** — a *re-report* of an old event. "Five years ago, SEBI barred X…" is not new
   risk. Compare the article's referenced event date to `occurred_at`. Flag it; Vaibhav's
   recency decay will down-weight it, but only if you tell him.

**Report your dedup ratio.** "N articles → M distinct stories" is a real, quotable number.

---

## TASK 3 — Mention extraction (`signals/extract.py`)

Pull `mentioned_names` and `mentioned_orgs` from the article. NER (spaCy `en_core_web_trf`, or
an LLM call for the hard ones).

Indian-name specifics that will bite you:
- Honorifics: `Shri`, `Shrimati`, `Smt.`, `Dr.`, `Mohd.` — strip but **record** that you stripped.
- Transliteration: the same person is spelled 8 ways. **Emit the string as written.**
  Do **not** normalise it — Vaibhav's phonetic matcher needs the original surface form.
- Mononyms: a single token that is also a common first name. Emit it, flag it as low-confidence.

---

## TASK 4 — Adverse-media triage agent (`signals/triage.py`) — **the one real agent you own**

This *is* justified as an agent: it's a judgement call, not a lookup. Per deduped story:

```json
{
  "risk_typology": ["FRAUD", "MARKET_MANIPULATION"],
  "severity": 0.0-1.0,
  "source_credibility": 0.0-1.0,
  "is_about_the_entity": true,
  "reasoning": "one paragraph"
}
```

Four judgements it must make:

1. **Is this actually adverse?** *"Anand Sharma appointed to the board"* is not adverse media.
   *"Anand Sharma barred by SEBI"* is. Most naive systems flag both.
2. **Typology** — `FRAUD | SANCTIONS | TERRORISM | CORRUPTION | MARKET_MANIPULATION |
   MONEY_LAUNDERING | REGULATORY_ACTION | NONE`.
3. **Severity** (0–1) — an allegation is not a conviction is not a charge. Grade it.
4. **Source credibility** (0–1) — Reuters ≠ an SEO content farm. Maintain a source-tier table.

> **`NONE` is a valid, valuable answer.** An agent that says "this is not adverse" is doing the
> most important work in the system. Don't build one that always finds something.

Constrain the output to the schema. Ground everything in the article text. **No claim without
a span.** If it can't be supported from the text, it doesn't go in the Signal.

---

## TASK 5 — Emit `Signal`s

Conform exactly to `contracts/models.py`. `raw_excerpt` ≤ 300 chars — Samaksh renders it in the
evidence panel and Sneha cites it in the SAR.

---

## Definition of done

- [ ] GDELT + ≥ 2 RSS sources ingesting on an interval.
- [ ] Three-layer dedup. **Dedup ratio measured and reported.**
- [ ] `story_cluster_id` collapses multi-outlet coverage into ONE signal with N source URLs.
- [ ] `is_rehash` correctly flags re-reports of old events.
- [ ] NER emits `mentioned_names` as **surface strings, unnormalised**.
- [ ] Triage agent returns constrained JSON, grounded in article text, and **can return `NONE`**.
- [ ] Source-credibility tier table exists and is defensible.
- [ ] `make demo-signals` runs standalone against a canned article corpus (record ~50 real
      articles to disk so the demo works **offline** — never let the wifi kill our demo).
- [ ] You never resolve an entity. Not once.

## Datasets you receive

```
watchlist_canonical.csv     (names to search for — Mohita will replace this with the full version)
fixtures/signals.json       (target output shape)
```

Everything else you pull live. **Cache ~50 real articles to disk before demo day.**

## Do not touch

`core/` `watchlist/` `casefile/` `ui/` `contracts/`.

---

## Pipeline hand-off (direct in-memory architecture — see `docs/06_PIPELINE.md`)

The orchestrator calls your package by ONE function. Everything is a typed
`contracts/models.py` object — no dicts, no DB between stages.

```python
def fetch_and_triage(customer: Customer) -> list[Signal]:
    ...
```

This is the **network-touching stage** (GDELT/RSS). The orchestrator ALWAYS calls it via
`safe(fetch_and_triage, customer, default=[])` — if it throws, the pipeline proceeds with
`signals = []` and logs it. One dead feed must not kill the run. Until you ship it,
`core/orchestrator.py` backs this stage with `fixtures/signals.json`.
