# AGENTS.md — Backend, audit trail + Flutter dashboard (Person 5)

## Project context

This service is one of five in TechMKYC, a Continuous KYC Autonomous Auditor built for Code by Tech Mahindra. Read `/docs/schema.md` at the repo root before writing any code — you own the database that implements it, so you're the source of truth everyone else builds against.

## Your task

You have two roles compressed into one: the shared backend (DB schema, API, audit trail, integration point) and the Flutter review dashboard. You also sit in every other person's critical path — nothing else fully works until your API exists — so sequencing matters more for you than anyone else. Do the schema and API skeleton first, in the first hour, ideally with Person 1 and Person 4 in the room since it's their contract too.

## Inputs you receive

Everything: `Entity` ingestion, `CandidateMatches`, `ResolutionVerdict`, `RiskEvent`, `InvestigationOutput`, and audit log writes from all four other services (schema.md §1–6).

## Outputs you must produce

- `POST /entities` — ingestion endpoint, generates `entity_id`
- `GET /entities`, `GET /entities/{id}` — for the dashboard
- `GET /entities/{id}/timeline`, `GET /entities/{id}/report` — surfaces Person 4's output
- `POST /reports/{id}/approve`, `POST /reports/{id}/edit`, `POST /reports/{id}/reject` — human review actions, each one writes an audit log entry with `actor: "human:<reviewer_name>"`
- `GET /audit-log?entity_id=` — for demo/inspection

## Tech stack

- SQL / Postgres (your cloud DB) for `entities`, `risk_events`, `evidence`, `draft_reports`, `audit_log` tables — `audit_log` is append-only, no `UPDATE`/`DELETE` statements against it, ever
- FastAPI for the backend
- Flutter for the dashboard: entity list, risk score with Person 2's plain-English explanation, evidence/timeline viewer, approve/edit/reject on the draft report
- Docker Compose — you own the root `docker-compose.yml` wiring all 5 services + Postgres together
- AWS (RDS + container hosting) for the live deploy, once local integration works — don't start here, start local

## Setup & run

```bash
cd services/backend-dashboard/api
pip install -r requirements.txt --break-system-packages
uvicorn main:app --reload --port 8000

cd ../app
flutter pub get
flutter run
```

## Definition of done (hackathon MVP)

- [ ] Schema + API skeleton live before end of hour 1 — everything else in the team depends on this
- [ ] `audit_log` is genuinely append-only (enforce it in code, don't just promise it in the pitch)
- [ ] Full pipeline visible end-to-end in the dashboard: entity → risk score with explanation → evidence timeline → draft report → approve/edit/reject
- [ ] `docker compose up` brings up all 5 services cleanly from a fresh clone
- [ ] AWS deploy works, but only attempt it once local integration is solid — don't let deploy debugging eat into integration time

## File ownership / do not touch

Everything under `services/backend-dashboard/` plus the root `docker-compose.yml` and `.env.example` are yours. You're also the one person who legitimately needs to look at `docs/schema.md` changes closely, since you implement it — but still announce changes before pushing them, same as everyone else.

## Merge coordinator role

Beyond your own service, you're also merging PRs into `main` for the whole team (see root README, git workflow rule 7). Before merging anyone's branch, pull it and run `docker compose up --build` locally to catch integration breaks before they land on `main`.

---

## Git workflow — read this before your first commit

We're 5 people editing one repo for 2 days. The plan below exists to stop pushes from stepping on each other, and to keep `main` a live, trustworthy picture of the whole system — not a pile of untouched branches that collide on the last night.

**1. You own your folder, nobody else's.**
Work only inside your `services/<your-service>/` folder. If you need to change something outside it — especially `docs/schema.md` — post in the team chat first. Silent edits to shared files are the #1 cause of conflicts.

**2. One branch per person, named after your service.**
```bash
git checkout -b feature/sanctions-agent      # Person 1
git checkout -b feature/entity-resolution    # Person 2
git checkout -b feature/media-orchestrator   # Person 3
git checkout -b feature/investigation-agent  # Person 4
git checkout -b feature/backend-dashboard    # Person 5
```
Never commit straight to `main`.

**3. Commit to your own branch periodically — every 30–60 minutes, not once at the end of the day.**
Work-in-progress commits are fine, even if the feature isn't finished. This is your recovery point if something breaks, and it keeps every individual diff small.
```bash
git add .
git commit -m "wip: candidate scoring for name+DOB match"
git push origin feature/sanctions-agent
```

**4. Merge your work into `main` periodically too — don't hoard your branch until it's "done."**
A branch that only lands on day 2 night is where the worst conflicts happen, and nobody else can build against your work until it's on `main`. Whenever you hit a stable checkpoint — an endpoint that returns the right shape, even with rough logic inside — open a PR and merge it in.
- Merge to `main` at least every 2–3 hours, or any time you finish an item on your Definition of Done list.
- It's fine to merge something incomplete or partially stubbed, as long as it doesn't break `docker compose up` for everyone else. Working-but-rough beats polished-but-unmerged.

**5. Pull `main` periodically to see the current state of everyone else's work.**
Before starting each new work block:
```bash
git checkout main
git pull origin main
git checkout feature/<your-service>
git rebase main
```
This is how you find out what teammates have shipped without waiting for a stand-up — and it surfaces conflicts while they're small, not eight hours later.

**6. `docs/schema.md` is the one shared file. Treat changes to it as an announcement, not a commit.**
If you need to change a field in the shared contract, message the group, get a thumbs up, then push — and ping everyone to pull `main` immediately after, since it likely breaks their in-progress code otherwise.

**7. Checkpoint tags at milestones.**
At the end of day 1 and right before the final demo, tag `main` at a known-good state so you can instantly roll back if a last-minute merge breaks something:
```bash
git tag day1-checkpoint
git push origin day1-checkpoint
# to roll back: git checkout day1-checkpoint
```

**8. Person 5 is merge coordinator.**
Since they own `docker-compose.yml` and the integration point, PRs into `main` get merged by them (or reviewed by them before anyone self-merges) — throughout the day, not just once at the end. They should pull and run the full stack locally before merging each PR, to catch integration breaks before `main` does.

**9. If you hit a conflict:** resolve it locally on your branch, never force-push over someone else's commits (`git push --force` on a shared branch is banned; `--force-with-lease` on your *own* feature branch only, if you must).