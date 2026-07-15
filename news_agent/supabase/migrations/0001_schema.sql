-- TechMKYC — Person 5 backend schema
-- Implements docs/schema.md §1–6. This is THE shared contract; announce any
-- field change in team chat before pushing (root README, git rule 6).
--
-- entity_id (uuid) is the join key across every table. It is generated ONCE,
-- here, when an entity first enters the system (schema.md "Rules for everyone").

create extension if not exists "pgcrypto";

-- ─────────────────────────────────────────────────────────────────────────────
-- §1  entities  (POST /entities generates entity_id via the default below)
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.entities (
    entity_id   uuid primary key default gen_random_uuid(),
    type        text not null check (type in ('person', 'company')),
    name        text not null,
    aliases     text[] not null default '{}',
    dob         date,                          -- null allowed (schema.md)
    nationality text,                          -- ISO-3166 alpha-2 | null
    din_or_cin  text,
    source      text not null check (source in ('internal_kyc', 'client_input')),
    created_at  timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- §2  candidate_matches  (Person 1 output → Person 2 input)
--     One row per candidate; grouped by query_entity_id.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.candidate_matches (
    id              uuid primary key default gen_random_uuid(),
    query_entity_id uuid not null references public.entities(entity_id) on delete cascade,
    candidate_id    text not null,
    matched_name    text not null,
    score           double precision not null,
    source_list     text not null,             -- OFAC | UN | EU | PEP | ...
    matched_fields  text[] not null default '{}',
    raw             jsonb not null default '{}',
    created_at      timestamptz not null default now()
);
create index if not exists idx_candidate_matches_entity on public.candidate_matches(query_entity_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- §3  resolution_verdicts  (Person 2 output → Person 3, Person 5)
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.resolution_verdicts (
    id              uuid primary key default gen_random_uuid(),
    query_entity_id uuid not null references public.entities(entity_id) on delete cascade,
    candidate_id    text,
    verdict         text not null check (verdict in ('confirmed_match', 'false_positive', 'needs_review')),
    confidence      double precision not null,
    explanation     text not null,             -- plain-English, cites matched/mismatched fields
    anchor_used     text not null default 'none' check (anchor_used in ('DIN', 'CIN', 'none')),
    resolved_at     timestamptz not null default now()
);
create index if not exists idx_verdicts_entity on public.resolution_verdicts(query_entity_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- §4  risk_events  (Person 3 output → Person 4)
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.risk_events (
    event_id    uuid primary key default gen_random_uuid(),
    entity_id   uuid not null references public.entities(entity_id) on delete cascade,
    event_type  text not null check (event_type in ('sanctions_hit', 'adverse_media', 'ownership_change')),
    severity    text not null check (severity in ('low', 'medium', 'high')),
    detected_at timestamptz not null default now(),
    source_refs text[] not null default '{}'   -- candidate_id or article_url
);
create index if not exists idx_risk_events_entity on public.risk_events(entity_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- evidence  (timeline entries; Person 4 input/output)
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.evidence (
    id          uuid primary key default gen_random_uuid(),
    entity_id   uuid not null references public.entities(entity_id) on delete cascade,
    event_date  timestamptz not null,
    event       text not null,
    source_url  text,
    excerpt     text                            -- under 25 words (schema.md §5)
);
create index if not exists idx_evidence_entity on public.evidence(entity_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- §5  draft_reports + citations  (Person 4 output → Person 5)
--     Every claim in summary must trace to >=1 citation. The citations child
--     table makes that rule queryable, not just a promise.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.draft_reports (
    report_id   uuid primary key default gen_random_uuid(),
    entity_id   uuid not null references public.entities(entity_id) on delete cascade,
    summary     text not null,
    status      text not null default 'pending'
                check (status in ('pending', 'approved', 'edited', 'rejected')),
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);
create index if not exists idx_reports_entity on public.draft_reports(entity_id);

create table if not exists public.report_citations (
    id          uuid primary key default gen_random_uuid(),
    report_id   uuid not null references public.draft_reports(report_id) on delete cascade,
    claim       text not null,
    source_url  text not null,
    excerpt     text not null
);
create index if not exists idx_citations_report on public.report_citations(report_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- §6  audit_log  (write-only; everyone writes, only Person 5's app reads)
--     Append-only enforcement lives in 0002_audit_append_only.sql.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.audit_log (
    log_id     uuid primary key default gen_random_uuid(),
    actor      text not null,                  -- agent:<name> | human:<reviewer>
    action     text not null,
    entity_id  uuid references public.entities(entity_id) on delete set null,
    timestamp  timestamptz not null default now(),
    details    jsonb not null default '{}'
);
create index if not exists idx_audit_entity on public.audit_log(entity_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- Realtime: publish tables the dashboard subscribes to for live updates.
-- (Wrapped so re-running the migration doesn't error if already added.)
-- ─────────────────────────────────────────────────────────────────────────────
do $$
begin
    alter publication supabase_realtime add table public.entities;
    alter publication supabase_realtime add table public.risk_events;
    alter publication supabase_realtime add table public.resolution_verdicts;
exception when others then null;
end $$;
