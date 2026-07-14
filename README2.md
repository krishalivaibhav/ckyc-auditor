# TechMKYC — Continuous KYC Autonomous Auditor

Built for Code by Tech Mahindra — Challenge 3: Continuous KYC Autonomous Auditor.

An agent network that continuously monitors high-risk corporate accounts against sanctions/PEP lists and adverse media, resolves entity name collisions against verified government identifiers, and drafts human-reviewable SAR/STR reports with a full audit trail.

## Architecture

```
Sanctions/PEP feed ─┐
Adverse media feed  ├─▶ Entity resolution & scoring ─▶ Investigation agent ─▶ SAR/STR draft ─▶ Human review (Flutter)
Internal KYC data  ─┘                                                                        └─▶ Audit trail (SQL)
```

Five services, one per team member. See each service's `AGENTS.md` for full task scope and contracts.

| # | Owner | Service | Folder |
|---|---|---|---|
| 1 | _name_ | Sanctions/PEP data agent | `services/sanctions-agent` |
| 2 | _name_ | Entity disambiguation & scoring | `services/entity-resolution` |
| 3 | _name_ | Adverse media + orchestration | `services/media-orchestrator` |
| 4 | _name_ | Investigation agent + draft generation | `services/investigation-agent` |
| 5 | _name_ | Backend, audit trail + Flutter dashboard | `services/backend-dashboard` |

Fill in names above once assigned — every `AGENTS.md` references this table.

## Repo structure

```
TechMKYC/
├── README.md                    ← this file
├── docker-compose.yml           ← brings up all 5 services + Postgres, owned by Person 5
├── .env.example
├── docs/
│   └── schema.md                ← THE shared contract. Read before writing any integration code.
└── services/
    ├── sanctions-agent/         ← Person 1
    ├── entity-resolution/       ← Person 2
    ├── media-orchestrator/      ← Person 3
    ├── investigation-agent/     ← Person 4
    └── backend-dashboard/       ← Person 5 (api/ + app/ for Flutter)
```

Each service folder is self-contained: its own `AGENTS.md`, its own `Dockerfile`, its own tests. This isn't arbitrary — it's the conflict-avoidance strategy (see below).

## Setup

```bash
git clone https://github.com/Samaksh912/TechMKYC.git
cd TechMKYC
cp .env.example .env          # fill in API keys: OPENSANCTIONS, GDELT, MCA, LLM provider
docker compose up --build     # brings up all services once each person has pushed
```

Each service can also run standalone during development — see the `AGENTS.md` in that folder for its own run command.

## Git workflow — read this before your first commit

We're 5 people editing one repo for 2 days. The plan below exists to stop pushes from stepping on each other, not to slow anyone down.

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

**3. Pull before you start, every session.**
```bash
git fetch origin
git rebase origin/main
```
Do this at the start of every work block, not just once a day. Rebasing (not merging) keeps history clean and surfaces conflicts early, while they're small.

**4. Push small and often — every 30–60 minutes, not once at the end of the day.**
A conflict in a 20-line diff takes 2 minutes to resolve. A conflict in an 8-hour diff can eat an hour and lose work. Small pushes are also your recovery point if something breaks.

**5. `docs/schema.md` is the one shared file. Treat changes to it as an announcement, not a commit.**
If you need to change a field in the shared contract, message the group, get a thumbs up, then push — and ping everyone to pull immediately after, since it likely breaks their in-progress code otherwise.

**6. Checkpoint tags at milestones.**
At the end of day 1 and right before the final demo, tag a known-good state so you can instantly roll back if a last-minute merge breaks something:
```bash
git tag day1-checkpoint
git push origin day1-checkpoint
# to roll back: git checkout day1-checkpoint
```

**7. Person 5 is merge coordinator.**
Since they own `docker-compose.yml` and the integration point, PRs into `main` get merged by them (or reviewed by them before anyone self-merges) — they should pull and run the full stack locally before merging, to catch integration breaks before `main` does.

**8. If you hit a conflict:** resolve it locally on your branch, never force-push over someone else's commits (`git push --force` on a shared branch is banned; `--force-with-lease` on your *own* feature branch only, if you must).
