# AGENTS.md — Entity disambiguation & scoring (Person 2)

## Project context

This service is one of five in TechMKYC, a Continuous KYC Autonomous Auditor built for Code by Tech Mahindra. Read `/docs/schema.md` at the repo root before writing any code.

**This is the most important service in the project.** It's the piece named explicitly in the challenge brief ("use semantic analysis and entity-resolution logic to reduce false positives, such as separating a corporate director from an unrelated person with the same name"), and it's the one thing in the architecture that isn't just calling a public API — everything downstream (the investigation agent, the SAR draft, the dashboard) is only as trustworthy as the verdict you produce here. A wrong call here is worse than a wrong call anywhere else, because it looks correct.

## Your task

Take Person 1's candidate matches and turn each one into a verdict: confirmed match, false positive, or needs human review — with a plain-English explanation a compliance officer can actually read and trust. Your key move: don't rely on name similarity alone. Use the MCA (Ministry of Corporate Affairs, India) director/company lookup as a government-verified anchor — cross-check DIN (Director Identification Number) or CIN (Corporate Identification Number) plus DOB and nationality against each candidate. A name-only match with no anchor confirmation should never come out as `confirmed_match` — route it to `needs_review` instead.

## Inputs you receive

`CandidateMatches` from Person 1 (schema.md §2), plus the original `Entity` (schema.md §1) so you have DIN/CIN to check against.

## Outputs you must produce

`ResolutionVerdict` — see schema.md §3. Expose as `POST /resolve`. Every verdict must include a non-empty `explanation` string — this is what gets shown to the human reviewer and what you'll show judges, so write it like you're explaining the decision to a compliance officer, not logging a debug message. Example: `"Name matches OFAC SDN entry at 91%, but DIN 00123456 does not match any entry for this individual — treated as false positive."`

Write every resolution to the audit log (schema.md §6) with `action: "resolved_verdict"`.

## Tech stack

- Python
- MCA master-data lookup (mca.gov.in — free, no login required for basic company/director master data) for the CIN/DIN anchor
- `rapidfuzz` + `jellyfish` (phonetic matching) for any additional scoring
- FastAPI for your service's HTTP interface
- Docker

## Setup & run

```bash
cd services/entity-resolution
pip install -r requirements.txt --break-system-packages
uvicorn main:app --reload --port 8002
```

You can build and test this entirely against mocked `CandidateMatches` before Person 1's real endpoint is live — don't wait on them, start with fixtures.

## Definition of done (hackathon MVP)

- [ ] `POST /resolve` correctly separates a genuine sanctions hit from a same-name false positive using the DIN/CIN anchor, on at least one deliberately constructed test case
- [ ] Every verdict has a human-readable explanation, not just a score
- [ ] `needs_review` is the default when the anchor can't be checked — never silently default to `confirmed_match`
- [ ] Every call writes an audit log entry
- [ ] You can explain, out loud, in one sentence, why this beats a pure name-similarity score — you'll need this exact pitch during judging

## File ownership / do not touch

Everything under `services/entity-resolution/` is yours. Do not edit `docs/schema.md` without announcing it in the team chat first. Do not edit other services' folders.

## Git workflow reminder

Branch: `feature/entity-resolution`. Create my own branch named Vaibhav's branch and Push every 30–60 minutes, not once at the end of the day. If your MCA integration is slow to land, land the scoring/explanation logic against mocked MCA responses first — don't let the whole service block on one integration.
repo link : https://github.com/Samaksh912/TechMKYC