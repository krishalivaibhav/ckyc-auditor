-- Seed data for the demo. Stands in for Persons 1–4 until their agents write to
-- these same tables. Names/sectors/countries echo the Synthetic KYC dataset
-- described in README.md. Fixed UUIDs so reports/citations link deterministically.
--
-- Run AFTER the migrations:  psql < seed.sql   (or paste into the SQL editor)

begin;

-- Idempotent: clear prior seed (children cascade). audit_log is append-only, so
-- we truncate it explicitly here for a clean demo start — the only place that's OK.
truncate public.entities restart identity cascade;
truncate public.audit_log;

-- ── Entities (§1) ────────────────────────────────────────────────────────────
insert into public.entities (entity_id, type, name, aliases, dob, nationality, din_or_cin, source) values
 ('11111111-1111-1111-1111-111111111111','company','Meridian Holdings Pvt Ltd', array['Meridian Group','Meridian Intl'], null,'AE','U74999MH2015PTC271234','internal_kyc'),
 ('22222222-2222-2222-2222-222222222222','person','Viktor A. Kozlov', array['V. Kozlov','Viktor Kozlow'], date '1968-03-12','RU',null,'internal_kyc'),
 ('33333333-3333-3333-3333-333333333333','company','Sunrise Minerals & Trading', array['Sunrise Mining'], null,'ZA','U13100DL2018PTC334455','internal_kyc'),
 ('44444444-4444-4444-4444-444444444444','person','Amara N. Okafor', array['A. Okafor'], date '1981-07-25','NG',null,'client_input'),
 ('55555555-5555-5555-5555-555555555555','company','BlueHarbor Financial Services', array['BlueHarbor FS'], null,'SG','U65999KA2016PTC556677','internal_kyc'),
 ('66666666-6666-6666-6666-666666666666','person','Elena M. Rossi', array['E. Rossi'], date '1975-11-02','IT',null,'internal_kyc'),
 ('77777777-7777-7777-7777-777777777777','company','Cedar Real Estate Ventures', array['Cedar REV'], null,'LB','U70100MH2019PTC778899','internal_kyc'),
 ('88888888-8888-8888-8888-888888888888','person','James P. Whitfield', array['J. Whitfield'], date '1960-01-19','GB',null,'client_input');

-- ── Candidate matches (§2, Person 1 output) ─────────────────────────────────
insert into public.candidate_matches (query_entity_id, candidate_id, matched_name, score, source_list, matched_fields, raw) values
 ('22222222-2222-2222-2222-222222222222','ofac-8842','Viktor Kozlov',0.94,'OFAC', array['name','nationality'], '{"program":"UKRAINE-EO13662"}'),
 ('22222222-2222-2222-2222-222222222222','un-1123','Viktor Kozlow',0.71,'UN', array['name'], '{}'),
 ('44444444-4444-4444-4444-444444444444','pep-5567','Amara Okafor',0.66,'PEP', array['name'], '{"role":"Regional official"}'),
 ('11111111-1111-1111-1111-111111111111','ofac-2201','Meridian Trading LLC',0.58,'OFAC', array['name'], '{}');

-- ── Resolution verdicts (§3, Person 2 output) ───────────────────────────────
insert into public.resolution_verdicts (query_entity_id, candidate_id, verdict, confidence, explanation, anchor_used) values
 ('22222222-2222-2222-2222-222222222222','ofac-8842','confirmed_match',0.94,
  'Name matches OFAC entry "Viktor Kozlov" and nationality (RU) aligns. DOB on the SDN record (1968) matches the client DOB 1968-03-12. High-confidence true positive.','none'),
 ('44444444-4444-4444-4444-444444444444','pep-5567','needs_review',0.55,
  'Name similarity to a PEP list entry is moderate (0.66) but no DOB or nationality on the PEP record to corroborate. Insufficient anchors to confirm — route to human review.','none'),
 ('11111111-1111-1111-1111-111111111111','ofac-2201','false_positive',0.28,
  'Candidate "Meridian Trading LLC" shares only a partial name token. CIN anchor U74999MH2015PTC271234 verified against MCA — distinct legal entity in a different jurisdiction. Cleared.','CIN'),
 ('33333333-3333-3333-3333-333333333333',null,'needs_review',0.50,
  'No direct sanctions candidate, but sector (Mining) and jurisdiction exposure are elevated. Flagged on adverse-media signal rather than list match.','none');

-- ── Risk events (§4, Person 3 output) ───────────────────────────────────────
insert into public.risk_events (entity_id, event_type, severity, detected_at, source_refs) values
 ('22222222-2222-2222-2222-222222222222','sanctions_hit','high', now() - interval '2 days', array['ofac-8842']),
 ('22222222-2222-2222-2222-222222222222','adverse_media','high', now() - interval '1 day', array['https://news.example.com/kozlov-probe']),
 ('33333333-3333-3333-3333-333333333333','adverse_media','medium', now() - interval '5 days', array['https://news.example.com/sunrise-minerals-inquiry']),
 ('33333333-3333-3333-3333-333333333333','ownership_change','medium', now() - interval '3 days', array['https://registry.example.com/sunrise-ubo']),
 ('44444444-4444-4444-4444-444444444444','adverse_media','low', now() - interval '8 days', array['https://news.example.com/okafor-mention']),
 ('77777777-7777-7777-7777-777777777777','adverse_media','medium', now() - interval '6 days', array['https://news.example.com/cedar-aml-fine']);

-- ── Evidence timelines (Person 4 input/output) ──────────────────────────────
insert into public.evidence (entity_id, event_date, event, source_url, excerpt) values
 ('22222222-2222-2222-2222-222222222222', now() - interval '2 days','Added to OFAC SDN list','https://www.treasury.gov/ofac/downloads/sdn.csv','Designated under Ukraine-related sanctions program.'),
 ('22222222-2222-2222-2222-222222222222', now() - interval '1 day','Named in international corruption probe','https://news.example.com/kozlov-probe','Reportedly under investigation for cross-border laundering.'),
 ('33333333-3333-3333-3333-333333333333', now() - interval '5 days','Regulatory inquiry opened','https://news.example.com/sunrise-minerals-inquiry','Local regulator queries source of mineral export funds.'),
 ('33333333-3333-3333-3333-333333333333', now() - interval '3 days','Ultimate beneficial owner changed','https://registry.example.com/sunrise-ubo','New UBO registered in a high-risk jurisdiction.'),
 ('77777777-7777-7777-7777-777777777777', now() - interval '6 days','AML penalty reported','https://news.example.com/cedar-aml-fine','Fined for weak transaction-monitoring controls.');

-- ── Draft reports + citations (§5, Person 4 output) ─────────────────────────
insert into public.draft_reports (report_id, entity_id, summary, status) values
 ('aaaaaaaa-0000-0000-0000-000000000001','22222222-2222-2222-2222-222222222222',
  'Viktor A. Kozlov is a confirmed match against the OFAC SDN list (Ukraine-related program), corroborated by matching nationality and date of birth. Adverse media within the last 24 hours reports an active corruption investigation involving cross-border transfers. Combined sanctions and media exposure warrant filing a Suspicious Activity Report.',
  'pending'),
 ('aaaaaaaa-0000-0000-0000-000000000002','33333333-3333-3333-3333-333333333333',
  'Sunrise Minerals & Trading shows no direct sanctions match but presents elevated risk: a regulatory inquiry into export fund sources and a recent change of ultimate beneficial owner to a high-risk jurisdiction. Recommend enhanced due diligence and human review before any transaction approval.',
  'pending');

insert into public.report_citations (report_id, claim, source_url, excerpt) values
 ('aaaaaaaa-0000-0000-0000-000000000001','Confirmed match against the OFAC SDN list','https://www.treasury.gov/ofac/downloads/sdn.csv','Designated under Ukraine-related sanctions program.'),
 ('aaaaaaaa-0000-0000-0000-000000000001','Active corruption investigation involving cross-border transfers','https://news.example.com/kozlov-probe','Reportedly under investigation for cross-border laundering.'),
 ('aaaaaaaa-0000-0000-0000-000000000002','Regulatory inquiry into export fund sources','https://news.example.com/sunrise-minerals-inquiry','Local regulator queries source of mineral export funds.'),
 ('aaaaaaaa-0000-0000-0000-000000000002','Change of ultimate beneficial owner to a high-risk jurisdiction','https://registry.example.com/sunrise-ubo','New UBO registered in a high-risk jurisdiction.');

-- ── A few agent audit entries so the trail isn't empty at demo start ────────
insert into public.audit_log (actor, action, entity_id, details) values
 ('agent:sanctions-agent','screened_entity','22222222-2222-2222-2222-222222222222','{"candidates":2}'),
 ('agent:entity-resolution','resolved_verdict','22222222-2222-2222-2222-222222222222','{"verdict":"confirmed_match"}'),
 ('agent:media-orchestrator','flagged_risk_event','22222222-2222-2222-2222-222222222222','{"severity":"high"}'),
 ('agent:investigation-agent','drafted_report','22222222-2222-2222-2222-222222222222','{"report_id":"aaaaaaaa-0000-0000-0000-000000000001"}');

commit;
