# Entity Resolution & Scoring (Person 2)

Turns Person 1's candidate sanction/PEP matches into explainable verdicts —
`confirmed_match | false_positive | needs_review` — anchored on the MCA
(India MCA) DIN/CIN government-verified record, not name similarity alone.

## The one-sentence pitch (for judging)

> A pure name-similarity score would flag every "Rajesh Sharma" on the OFAC
> list; we cross-check the client's DIN/CIN against MCA master data, so a hit
> whose verified DOB/nationality doesn't match the list entry is rejected as a
> false positive instead of alarming a compliance officer.

## Run

```bash
pip install -r requirements.txt          # or: python -m venv .venv && .venv/bin/pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

## API

- `POST /resolve` — body is `{ "entity": <schema §1>, "matches": <schema §2> }`,
  returns a list of `ResolutionVerdict` (schema §3), one per candidate.
- `GET /health` — liveness.

```bash
curl -X POST localhost:8002/resolve -H "Content-Type: application/json" \
     -d @fixtures/false_positive_same_name.json
```

## Verdict policy

| Situation | Verdict |
|---|---|
| Anchor (DIN/CIN) resolves **and** DOB/nationality corroborate | `confirmed_match` |
| Anchor resolves **but** DOB/nationality contradict | `false_positive` |
| No DIN/CIN, or MCA can't resolve it | `needs_review` (never confirmed on name alone) |
| Only a weak name match, no anchor | `false_positive` |

## Config (env vars)

- `MCA_MODE` — `mock` (default, uses `fixtures/mca_master_data.json`) or `real`.
- `AUDIT_URL` — optional; if set, audit entries are also POSTed to Person 5's
  backend. Always written to stdout + `audit.log.jsonl` regardless.

## Tests

```bash
pytest          # 7 tests; the three fixtures are the Definition-of-Done proofs
```

Every verdict is written to the audit log (schema §6) with
`action: "resolved_verdict"`, append-only.
