-- Continuous KYC Autonomous Auditor — persistence sink (SQLite).
--
-- ARCHITECTURE: components hand off contracts/models.py objects IN MEMORY via
-- direct function calls (see core/orchestrator.py). The database is a SINK at the
-- END of the pipeline, not a bus between stages. Only three things persist:
--
--     Case   —  the object the UI renders (embeds its timeline, reviewer actions,
--               SAR, and the RiskAssessment(s) it needs, as JSON)
--     SAR    —  persisted separately so SARs can be queried directly
--     AuditEvent — the append-only trail; every pipeline step writes one here
--
-- Intermediate Signal / Candidate / RiskAssessment objects are NEVER persisted as
-- standalone rows. They flow in memory and, where the UI needs them, ride along
-- embedded inside the Case JSON. That is why the old signals/candidates/
-- risk_assessments tables are gone.
--
-- SQLite types: JSON is stored as TEXT, timestamps as ISO-8601 TEXT.

CREATE TABLE cases (
    case_id    TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL,
    opened_at  TEXT NOT NULL,
    status     TEXT NOT NULL,
    tier       TEXT NOT NULL,
    data       TEXT NOT NULL      -- full Case JSON (timeline, reviewer_actions, sar,
                                  -- and embedded assessments the UI renders)
);
CREATE INDEX idx_cases_client ON cases(client_id);
CREATE INDEX idx_cases_tier   ON cases(tier);
CREATE INDEX idx_cases_status ON cases(status);

CREATE TABLE sars (
    sar_id       TEXT PRIMARY KEY,
    case_id      TEXT NOT NULL REFERENCES cases(case_id),
    drafted_at   TEXT NOT NULL,
    subject_name TEXT,
    subject_pan  TEXT,
    status       TEXT NOT NULL DEFAULT 'DRAFT',
    data         TEXT NOT NULL      -- full SAR JSON (sections, evidence, unverified_claims)
);
CREATE INDEX idx_sars_case ON sars(case_id);

-- ============================================================
-- APPEND-ONLY AUDIT TRAIL. Enforced, not conventional.
-- The risk timeline AND the audit trail derive from this table.
-- ============================================================
CREATE TABLE audit_events (
    audit_id    TEXT PRIMARY KEY,
    at          TEXT NOT NULL,
    actor       TEXT NOT NULL,      -- agent:er | agent:orchestrator | user:analyst_1
    action      TEXT NOT NULL,      -- RESOLVED | ASSESSED | CASE_OPENED | SUPPRESSED ...
    object_type TEXT NOT NULL,
    object_id   TEXT NOT NULL,
    before      TEXT,               -- JSON | NULL
    after       TEXT,               -- JSON | NULL
    rationale   TEXT NOT NULL
);
CREATE INDEX idx_audit_object ON audit_events(object_id, at DESC);

-- SALVAGE 1 (from the retired build): append-only enforced by a RAISING trigger.
-- Not `DO INSTEAD NOTHING` — this FAILS LOUDLY on any UPDATE/DELETE, which is the
-- demo-worthy guarantee: you cannot rewrite history, and an attempt errors.
CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit_events
BEGIN SELECT RAISE(FAIL, 'audit_events is append-only'); END;
CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit_events
BEGIN SELECT RAISE(FAIL, 'audit_events is append-only'); END;
