-- Aligns the live schema with the schema.md §7 update:
--   - candidate_matches.score / resolution_verdicts.confidence -> numeric
--   - resolution_verdicts.candidate_id -> NOT NULL (was nullable)
--   - resolution_verdicts.anchor_used -> no default (was 'none')
--   - draft_reports.status initial value renamed 'pending' -> 'draft'
--   - evidence (entity-scoped) replaced by report_timeline (report-scoped):
--     timeline entries now belong to a filed report, not the entity directly.
--   - report_citations.source_url / excerpt -> nullable
-- Run this AFTER 0001–0003 have already been applied.

-- ── candidate_matches.score, resolution_verdicts.confidence -> numeric ───────
alter table public.candidate_matches
    alter column score type numeric using score::numeric;

alter table public.resolution_verdicts
    alter column confidence type numeric using confidence::numeric;

-- ── resolution_verdicts.candidate_id -> NOT NULL ──────────────────────────────
-- Backfill any existing nulls (a verdict with no direct candidate match) with a
-- sentinel before tightening the constraint.
update public.resolution_verdicts set candidate_id = 'none' where candidate_id is null;
alter table public.resolution_verdicts
    alter column candidate_id set not null;

-- ── resolution_verdicts.anchor_used -> drop default (still required + checked) ─
alter table public.resolution_verdicts
    alter column anchor_used drop default;

-- ── draft_reports.status: 'pending' -> 'draft' ────────────────────────────────
-- Drop the old check FIRST: it still forbids 'draft', so updating the data
-- below would violate it before the new constraint is in place. Also drop the
-- default before touching rows so nothing re-inserts 'pending' mid-migration.
alter table public.draft_reports alter column status drop default;
alter table public.draft_reports drop constraint if exists draft_reports_status_check;
update public.draft_reports set status = 'draft' where status = 'pending';
alter table public.draft_reports
    add constraint draft_reports_status_check
    check (status in ('draft', 'approved', 'edited', 'rejected'));
alter table public.draft_reports alter column status set default 'draft';

-- ── report_citations: source_url / excerpt now nullable ──────────────────────
alter table public.report_citations alter column source_url drop not null;
alter table public.report_citations alter column excerpt drop not null;

-- ── evidence -> report_timeline (report-scoped, not entity-scoped) ───────────
-- Existing evidence rows can't be preserved 1:1 (no report_id to attach them
-- to for entities with no filed report yet); this is demo/seed data, so we
-- drop and let seed.sql repopulate against draft_reports instead.
drop table if exists public.evidence cascade;

create table if not exists public.report_timeline (
    id          uuid primary key default gen_random_uuid(),
    report_id   uuid not null references public.draft_reports(report_id) on delete cascade,
    event_date  timestamptz not null,
    event       text not null,
    source_url  text,
    excerpt     text
);
create index if not exists idx_report_timeline_report on public.report_timeline(report_id);

alter table public.report_timeline enable row level security;
drop policy if exists report_timeline_rw on public.report_timeline;
create policy report_timeline_rw on public.report_timeline
    for all using (true) with check (true);

-- ── audit_log triggers: split to mirror schema.md's two named triggers ───────
drop trigger if exists trg_audit_log_no_update on public.audit_log;

drop trigger if exists audit_log_no_update on public.audit_log;
create trigger audit_log_no_update
    before update on public.audit_log
    for each row execute function public.audit_log_block_mutation();

drop trigger if exists audit_log_no_delete on public.audit_log;
create trigger audit_log_no_delete
    before delete on public.audit_log
    for each row execute function public.audit_log_block_mutation();
