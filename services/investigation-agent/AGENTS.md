# AGENTS.md — Investigation agent + draft generation (Person 4)

## Project context

This service is one of five in TechMKYC, a Continuous KYC Autonomous Auditor built for Code by Tech Mahindra. Read `/docs/schema.md` at the repo root before writing any code.

## Your task

When a `RiskEvent` fires (from Person 3), pull together all available evidence about that entity, build a timeline of what happened and when, and draft a SAR/STR-style report a compliance officer can review and sign off on. The non-negotiable rule: **every claim in the draft must cite a specific evidence snippet with a source.** No free-floating LLM narration — this is a retrieval-grounded generation problem, not a creative-writing one. That distinction is the whole point of this service; an ungrounded LLM paragraph is not a usable compliance artifact.

Note on terminology: the brief says "SAR" (US usage). In India this maps to an STR (Suspicious Transaction Report) filed to FIU-IND under PMLA — worth knowing for the pitch, doesn't change what you build.

## Inputs you receive

`RiskEvent` (schema.md §4) from Person 3. `ResolutionVerdict` (schema.md §3) from Person 2, so you know which candidate the event is actually about. Raw evidence documents (news articles, internal KYC docs) — you'll need to build or stub a small corpus of these for the demo since there's no existing pipeline to pull from.

## Outputs you must produce

`InvestigationOutput` — see schema.md §5. Expose as `POST /investigate` accepting a `RiskEvent`. Write to the audit log (schema.md §6) with `action: "generated_draft_report"`.

## Tech stack

- Python
- An embedding model + a vector DB (e.g. `sentence-transformers` + ChromaDB, or any combination your team is comfortable with) for semantic retrieval over evidence documents — you're finding *meaning* matches, not string matches, so this is not the same job as Person 1/2's name matching
- An LLM via API for timeline synthesis and draft generation, constrained to only write from retrieved evidence (retrieval-augmented generation — retrieve first, generate strictly from what's retrieved, cite every sentence)
- FastAPI, Docker

## Setup & run

```bash
cd services/investigation-agent
pip install -r requirements.txt --break-system-packages
uvicorn main:app --reload --port 8004
```

You have no existing pipeline to build on — start with a small synthetic evidence corpus (5–10 fake articles/documents covering your demo entities) so you're not blocked waiting on Person 3's live feed.

## Definition of done (hackathon MVP)

- [ ] Given a `RiskEvent`, retrieves relevant evidence and builds an ordered timeline
- [ ] Every sentence in `draft_report.summary` traces to at least one `citations` entry — spot-check this yourself before demo day, an uncited claim is the single easiest thing for a judge to catch
- [ ] Draft is genuinely editable — Person 5's dashboard needs to let a reviewer change it, so keep the structure simple (plain text + citation list, not a rigid template that's painful to edit)
- [ ] Every generation writes an audit log entry

## File ownership / do not touch

Everything under `services/investigation-agent/` is yours. Do not edit `docs/schema.md` without announcing it in the team chat first. Do not edit other services' folders.

## Git workflow reminder

Branch: `feature/investigation-agent`. Rebase onto `origin/sneha` at the start of every session. Push every 30–60 minutes. You're the heaviest downstream dependency in the pipeline — build and test against mocked `RiskEvent`s and a synthetic corpus from hour one rather than waiting for Person 2 and Person 3's real output.
