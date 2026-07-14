# Shared data contracts

This is the single source of truth for every JSON shape and DB table that crosses a service boundary. If you change something here, announce it in the team chat before pushing (see root README, git workflow rule 5). Everything below is a strong starting default — finalize exact field names together in the first hour, then treat it as frozen unless the whole team agrees to a change.

## 1. Entity (input to Person 1 and Person 2)

```json
{
  "entity_id": "uuid",
  "type": "person | company",
  "name": "string",
  "aliases": ["string"],
  "dob": "YYYY-MM-DD | null",
  "nationality": "ISO-3166 alpha-2 | null",
  "din_or_cin": "string | null",
  "source": "internal_kyc | client_input"
}
```

## 2. Candidate matches (Person 1 output → Person 2 input)

```json
{
  "query_entity_id": "uuid",
  "candidates": [
    {
      "candidate_id": "string",
      "matched_name": "string",
      "score": 0.0,
      "source_list": "OFAC | UN | EU | PEP | ...",
      "matched_fields": ["name", "dob", "nationality"],
      "raw": {}
    }
  ]
}
```

## 3. Resolution verdict (Person 2 output → Person 3, Person 5)

```json
{
  "query_entity_id": "uuid",
  "candidate_id": "string",
  "verdict": "confirmed_match | false_positive | needs_review",
  "confidence": 0.0,
  "explanation": "string, human-readable, cites which fields matched/mismatched",
  "anchor_used": "DIN | CIN | none",
  "resolved_at": "ISO 8601 timestamp"
}
```

## 4. Risk event (Person 3 output → Person 4)

```json
{
  "event_id": "uuid",
  "entity_id": "uuid",
  "event_type": "sanctions_hit | adverse_media | ownership_change",
  "severity": "low | medium | high",
  "detected_at": "ISO 8601 timestamp",
  "source_refs": ["candidate_id or article_url"]
}
```

## 5. Investigation output (Person 4 output → Person 5)

```json
{
  "entity_id": "uuid",
  "timeline": [
    {"date": "ISO 8601", "event": "string", "source_url": "string", "excerpt": "string, under 25 words"}
  ],
  "draft_report": {
    "summary": "string",
    "citations": [
      {"claim": "string", "source_url": "string", "excerpt": "string"}
    ]
  }
}
```

Every claim in `draft_report.summary` must trace back to at least one entry in `citations`. No uncited sentences — this is the difference between "AI wrote a report" and "AI assembled a report you can audit."

## 6. Audit log (write-only, everyone writes, only Person 5's API reads/exposes)

```json
{
  "log_id": "uuid",
  "actor": "agent:sanctions-agent | agent:entity-resolution | agent:media-orchestrator | agent:investigation-agent | human:<reviewer_name>",
  "action": "string, e.g. 'screened_entity', 'flagged_risk_event', 'resolved_verdict', 'approved_report', 'edited_report', 'rejected_report'",
  "entity_id": "uuid",
  "timestamp": "ISO 8601",
  "details": {}
}
```

**Append-only. Never update or delete a row.** This table is the audit trail — if it can be edited after the fact, it isn't one.

## 7. Supabase / Postgres tables (Person 5 only)

**Option A is in effect: only Person 5's backend talks to Supabase.** Persons 1–4 never receive Supabase credentials and never call it directly — they only ever call Person 5's FastAPI endpoints, exactly as described in each of their `AGENTS.md` files. This section exists purely so Person 5 has a concrete schema to run; nobody else needs to read it.

```sql
create extension if not exists "pgcrypto";

create table entities (
  entity_id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('person', 'company')),
  name text not null,
  aliases text[] default '{}',
  dob date,
  nationality text,
  din_or_cin text,
  source text check (source in ('internal_kyc', 'client_input')),
  created_at timestamptz default now()
);

create table candidate_matches (
  id uuid primary key default gen_random_uuid(),
  query_entity_id uuid references entities(entity_id) not null,
  candidate_id text not null,
  matched_name text not null,
  score numeric not null,
  source_list text not null,
  matched_fields text[] default '{}',
  raw jsonb default '{}',
  created_at timestamptz default now()
);

create table resolution_verdicts (
  id uuid primary key default gen_random_uuid(),
  query_entity_id uuid references entities(entity_id) not null,
  candidate_id text not null,
  verdict text not null check (verdict in ('confirmed_match', 'false_positive', 'needs_review')),
  confidence numeric not null,
  explanation text not null,
  anchor_used text check (anchor_used in ('DIN', 'CIN', 'none')),
  resolved_at timestamptz default now()
);

create table risk_events (
  event_id uuid primary key default gen_random_uuid(),
  entity_id uuid references entities(entity_id) not null,
  event_type text not null check (event_type in ('sanctions_hit', 'adverse_media', 'ownership_change')),
  severity text not null check (severity in ('low', 'medium', 'high')),
  detected_at timestamptz default now(),
  source_refs text[] default '{}'
);

create table draft_reports (
  report_id uuid primary key default gen_random_uuid(),
  entity_id uuid references entities(entity_id) not null,
  summary text not null,
  status text not null default 'draft' check (status in ('draft', 'approved', 'edited', 'rejected')),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table report_timeline (
  id uuid primary key default gen_random_uuid(),
  report_id uuid references draft_reports(report_id) not null,
  event_date timestamptz not null,
  event text not null,
  source_url text,
  excerpt text
);

create table report_citations (
  id uuid primary key default gen_random_uuid(),
  report_id uuid references draft_reports(report_id) not null,
  claim text not null,
  source_url text,
  excerpt text
);

create table audit_log (
  log_id uuid primary key default gen_random_uuid(),
  actor text not null,
  action text not null,
  entity_id uuid references entities(entity_id),
  "timestamp" timestamptz default now(),
  details jsonb default '{}'
);

-- Append-only enforcement, at the database level — holds even if the
-- backend code has a bug, and even for the service-role key (which
-- would otherwise bypass Row Level Security entirely).
create or replace function prevent_audit_log_mutation()
returns trigger as $$
begin
  raise exception 'audit_log is append-only: % is not allowed', TG_OP;
end;
$$ language plpgsql;

create trigger audit_log_no_update
before update on audit_log
for each row execute function prevent_audit_log_mutation();

create trigger audit_log_no_delete
before delete on audit_log
for each row execute function prevent_audit_log_mutation();
```

**Credential handling:** Person 5's backend uses the Supabase **service role key** (full access, bypasses RLS) — this key lives only in Person 5's `.env`, never committed, never shared with Persons 1–4. If the Flutter app ever needs to query Supabase directly later (e.g. for Realtime subscriptions on `draft_reports` so the dashboard updates live), use the **anon key** with a read-only RLS policy — a separate decision from this section, not required for the MVP.

## Rules for everyone

- Use `entity_id` (uuid) as the join key across every table — generate it once, when an entity first enters the system (Person 5's ingestion endpoint), and pass it through unchanged everywhere else.
- Timestamps are always ISO 8601 UTC. No exceptions, no local time.
- If your service can't produce a required field, send `null` explicitly — never omit the key.
