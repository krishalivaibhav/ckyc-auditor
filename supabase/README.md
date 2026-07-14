# Supabase backend (Person 5)

Implements `docs/schema.md` §1–6: entities, candidate_matches, resolution_verdicts,
risk_events, evidence, draft_reports (+ citations), and an **append-only** audit_log.

## Apply the schema

**Hosted project (fastest for the hackathon):**
1. Create a project at https://supabase.com → copy the Project URL and anon key.
2. In the SQL editor, run the migrations in order:
   `0001_schema.sql` → `0002_audit_append_only.sql` → `0003_review_rpc.sql`
3. Run `seed.sql` to load demo data.
4. Put the URL + anon key in the Flutter app via `--dart-define` (see repo root README /
   `lib/core/supabase.dart`).

**Local (Supabase CLI):**
```bash
supabase start
supabase db reset          # applies migrations/ in order
psql "$(supabase status -o json | jq -r .DB_URL)" -f seed.sql
```

## What to show in the demo
- **Append-only audit:** in the SQL editor run `update audit_log set action='x';` → it errors
  (`audit_log is append-only`). Same for `delete`. This is enforced by a trigger *and* RLS.
- **Atomic review:** `select review_report('aaaaaaaa-0000-0000-0000-000000000001','approve','asha');`
  flips the report status **and** writes one `human:asha` audit row in a single transaction.
- **Realtime seam for the agents:** insert a `risk_event` while the app is open and the watchlist
  updates live — this is exactly where Persons 1–4's agents plug in.
