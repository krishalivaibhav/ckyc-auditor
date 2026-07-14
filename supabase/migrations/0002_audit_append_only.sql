-- Append-only enforcement for audit_log (schema.md §6: "Never update or delete
-- a row. If it can be edited after the fact, it isn't an audit trail.")
--
-- Two layers of defense:
--   1. RLS with INSERT + SELECT policies only  → normal clients can't UPDATE/DELETE.
--   2. A BEFORE UPDATE OR DELETE trigger that raises → blocks even the service_role
--      / SQL editor / a future policy mistake. This is the demo-worthy guarantee.

-- ── Layer 2: hard trigger (fires for every role, RLS-exempt or not) ──────────
create or replace function public.audit_log_block_mutation()
returns trigger
language plpgsql
as $$
begin
    raise exception 'audit_log is append-only: % is not permitted', tg_op
        using errcode = 'insufficient_privilege';
end;
$$;

drop trigger if exists trg_audit_log_no_update on public.audit_log;
create trigger trg_audit_log_no_update
    before update or delete on public.audit_log
    for each row execute function public.audit_log_block_mutation();

-- ── Layer 1: RLS — allow read + insert, deny everything else by omission ─────
alter table public.audit_log enable row level security;

drop policy if exists audit_log_select on public.audit_log;
create policy audit_log_select on public.audit_log
    for select using (true);

drop policy if exists audit_log_insert on public.audit_log;
create policy audit_log_insert on public.audit_log
    for insert with check (true);
-- No UPDATE or DELETE policy exists → those operations are denied under RLS.

-- ── RLS for the other tables (demo-permissive; tighten before production) ────
-- Authenticated reviewers can read everything and ingest/insert. Agents write
-- with the service_role key, which bypasses RLS.
do $$
declare t text;
begin
    foreach t in array array[
        'entities', 'candidate_matches', 'resolution_verdicts',
        'risk_events', 'evidence', 'draft_reports', 'report_citations'
    ]
    loop
        execute format('alter table public.%I enable row level security;', t);
        execute format('drop policy if exists %I_rw on public.%I;', t, t);
        execute format(
            'create policy %I_rw on public.%I for all using (true) with check (true);',
            t, t);
    end loop;
end $$;
