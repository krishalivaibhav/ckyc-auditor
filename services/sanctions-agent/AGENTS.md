# AGENTS.md — Sanctions/PEP data agent (Person 1)

## Project context

This service is one of five in TechMKYC, a Continuous KYC Autonomous Auditor built for Code by Tech Mahindra. Read `/docs/schema.md` at the repo root before writing any code — it defines every JSON shape you consume and produce, and it's shared across all five services.

## Your task

Given a corporate entity (a director, beneficial owner, or the company itself), retrieve candidate matches from global sanctions and PEP watchlists, and score them for name/attribute similarity. You are producing *candidates*, not final verdicts — Person 2 (entity-resolution) makes the confirmed/false-positive call using your output plus a government-ID anchor. Don't try to do their job; a wide, well-scored candidate list is your entire deliverable.

## Inputs you receive

`Entity` objects — see schema.md §1. Comes from Person 5's ingestion endpoint (`POST /entities`) or from Person 3's re-screening trigger.

## Outputs you must produce

`CandidateMatches` — see schema.md §2. Expose as `POST /screen` accepting an `Entity`, returning candidates. Write every screening call to the audit log (schema.md §6) with `action: "screened_entity"`.

## Tech stack

- Python
- OpenSanctions `/match` API (free for non-commercial use) — https://www.opensanctions.org/docs/api/ — this is your primary data source, covers OFAC, UN, EU, and PEP lists in one call
- `rapidfuzz` for any additional local fuzzy scoring you need beyond what OpenSanctions returns
- FastAPI for your service's HTTP interface
- Docker — your service needs its own `Dockerfile`, added to the root `docker-compose.yml` (coordinate with Person 5, don't edit their compose file yourself without a heads-up)

## Setup & run

```bash
cd services/sanctions-agent
pip install -r requirements.txt --break-system-packages   # if working outside Docker
uvicorn main:app --reload --port 8001
```

Get a free OpenSanctions API key at opensanctions.org (business email = free trial key). Store it in `.env`, never commit it.

## Definition of done (hackathon MVP)

- [ ] `POST /screen` returns candidates for a test entity within ~2 seconds
- [ ] Handles both person and company schema types
- [ ] Every call writes an audit log entry
- [ ] Works against 3–4 curated demo entities including at least one deliberate name collision (same name, different DIN) — this is what Person 2 needs to demonstrate disambiguation

## File ownership / do not touch

Everything under `services/sanctions-agent/` is yours. Do not edit `docs/schema.md` without announcing it in the team chat first (see root README, git workflow). Do not edit other services' folders.

## Git workflow reminder

### Working branch

My working branch is:

```text
mohitha
```

At the start of every development session:

```bash
git fetch origin
git rebase origin/mohitha
```

Commit small changes frequently:

```bash
git add .
git commit -m "<message>"
git push origin mohitha
```

Do not suggest Git commands using `feature/sanctions-agent` unless I explicitly ask. The repository README uses that as the generic team convention, but my active development branch is `mohitha`.

## AI Agent Workflow

Before generating any code:

1. Read `README.md`.
2. Read `docs/schema.md`.
3. Read this `AGENTS.md`.
4. Explain your understanding.
5. Propose an implementation plan.
6. Wait for my approval.

Implementation rules:

- Work only inside `services/sanctions-agent/`.
- Follow the JSON contracts defined in `docs/schema.md`.
- If a contract is unclear, stop and ask instead of changing it.
- Do not modify other services.
- Do not modify `docs/schema.md`.
- Do not modify `docker-compose.yml`.
- Implement one milestone at a time.
- Show which files will be created or modified.
- Wait for my approval before writing or modifying any files.
- Run the service locally whenever possible and fix build/import errors.
- Show the Git diff before committing.
- Wait for my approval before committing.
- Never push to GitHub unless I explicitly ask.


