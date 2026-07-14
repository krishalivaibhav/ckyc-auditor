-- Human review actions as ONE atomic transaction (maps the AGENTS.md endpoints
-- POST /reports/{id}/approve | /edit | /reject).
--
-- Each call flips draft_reports.status AND writes an audit_log row with
-- actor = 'human:<reviewer_name>'. Doing both in a SECURITY DEFINER function
-- guarantees you can never approve a report without leaving an audit entry.

create or replace function public.review_report(
    p_report_id     uuid,
    p_action        text,                       -- 'approve' | 'edit' | 'reject'
    p_reviewer_name text,
    p_edited_summary text default null
)
returns public.draft_reports
language plpgsql
security definer
set search_path = public
as $$
declare
    v_status  text;
    v_action  text;
    v_entity  uuid;
    v_report  public.draft_reports;
begin
    if p_action not in ('approve', 'edit', 'reject') then
        raise exception 'invalid action: %', p_action;
    end if;

    v_status := case p_action
        when 'approve' then 'approved'
        when 'edit'    then 'edited'
        when 'reject'  then 'rejected'
    end;
    v_action := case p_action
        when 'approve' then 'approved_report'
        when 'edit'    then 'edited_report'
        when 'reject'  then 'rejected_report'
    end;

    update public.draft_reports
       set status  = v_status,
           summary = coalesce(p_edited_summary, summary),
           updated_at = now()
     where report_id = p_report_id
    returning * into v_report;

    if not found then
        raise exception 'report % not found', p_report_id;
    end if;

    v_entity := v_report.entity_id;

    insert into public.audit_log (actor, action, entity_id, details)
    values (
        'human:' || p_reviewer_name,
        v_action,
        v_entity,
        jsonb_build_object(
            'report_id', p_report_id,
            'new_status', v_status,
            'edited', (p_edited_summary is not null)
        )
    );

    return v_report;
end;
$$;

grant execute on function public.review_report(uuid, text, text, text) to anon, authenticated;
