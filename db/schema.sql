-- Continuous KYC Autonomous Auditor — schema
-- Mirrors contracts/models.py. If you change one, change the other.

CREATE TABLE customers (
    client_id        TEXT PRIMARY KEY,
    client_name      TEXT NOT NULL,
    client_type      TEXT NOT NULL,
    pan              TEXT,
    country          TEXT DEFAULT 'IN',
    sector           TEXT,
    branch           TEXT,
    onboarding_date  DATE,
    exposure_inr     BIGINT,
    last_kyc_refresh DATE
);
CREATE INDEX idx_cust_pan  ON customers(pan);
CREATE INDEX idx_cust_name ON customers(client_name);

-- MOHITA
CREATE TABLE watchlist_entries (
    watchlist_id  TEXT PRIMARY KEY,
    list          TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    name          TEXT NOT NULL,
    aliases       JSONB DEFAULT '[]',
    alias_quality JSONB DEFAULT '{}',   -- {alias: full_name|org_acronym|bare_token}
    pan           TEXT,
    dob           DATE,
    party         TEXT,
    status        TEXT NOT NULL,        -- active|revoked|current|former
    order_id      TEXT,                 -- co-accused clustering
    order_date    DATE,
    source_url    JSONB DEFAULT '[]',   -- real NSE circular PDFs -> citations
    first_seen    TIMESTAMPTZ,
    last_change   TIMESTAMPTZ
);
CREATE INDEX idx_wl_pan   ON watchlist_entries(pan);
CREATE INDEX idx_wl_name  ON watchlist_entries(name);
CREATE INDEX idx_wl_list  ON watchlist_entries(list);
CREATE INDEX idx_wl_order ON watchlist_entries(order_id);

-- ADITYA + MOHITA
CREATE TABLE signals (
    signal_id         TEXT PRIMARY KEY,
    signal_type       TEXT NOT NULL,
    occurred_at       TIMESTAMPTZ NOT NULL,
    ingested_at       TIMESTAMPTZ NOT NULL,
    source            TEXT,
    source_url        TEXT,
    source_credibility REAL DEFAULT 0.5,
    headline          TEXT,
    raw_excerpt       TEXT,
    content_hash      TEXT UNIQUE,      -- exact-dup guard, at the DB level
    story_cluster_id  TEXT,
    mentioned_names   JSONB DEFAULT '[]',
    mentioned_orgs    JSONB DEFAULT '[]',
    risk_typology     JSONB DEFAULT '[]',
    severity          REAL DEFAULT 0,
    is_rehash         BOOLEAN DEFAULT FALSE
);
CREATE INDEX idx_sig_cluster ON signals(story_cluster_id);
CREATE INDEX idx_sig_time    ON signals(occurred_at DESC);

-- VAIBHAV. REJECTED rows are the product, not garbage. Never delete them.
CREATE TABLE candidates (
    candidate_id     TEXT PRIMARY KEY,
    client_id        TEXT REFERENCES customers(client_id),
    watchlist_id     TEXT REFERENCES watchlist_entries(watchlist_id),
    signal_id        TEXT REFERENCES signals(signal_id),
    match_method     TEXT NOT NULL,
    confidence       REAL NOT NULL,
    decision         TEXT NOT NULL,    -- CONFIRMED|AMBIGUOUS|REJECTED
    rejection_reason TEXT,             -- MANDATORY when decision='REJECTED'
    features         JSONB DEFAULT '{}',
    CONSTRAINT reject_needs_reason
        CHECK (decision <> 'REJECTED' OR rejection_reason IS NOT NULL)
);
CREATE INDEX idx_cand_client   ON candidates(client_id);
CREATE INDEX idx_cand_decision ON candidates(decision);

CREATE TABLE evidence (
    evidence_id  TEXT PRIMARY KEY,     -- "EV-001" — cited inline in the SAR
    kind         TEXT NOT NULL,
    status       TEXT NOT NULL,        -- CONFIRMED|CORRELATED|MISSING  (never collapse)
    claim        TEXT NOT NULL,
    source_name  TEXT,
    source_url   TEXT,
    excerpt      TEXT,
    retrieved_at TIMESTAMPTZ,
    confidence   REAL DEFAULT 1.0
);

CREATE TABLE risk_assessments (
    assessment_id          TEXT PRIMARY KEY,
    client_id              TEXT REFERENCES customers(client_id),
    assessed_at            TIMESTAMPTZ NOT NULL,
    prior_tier             TEXT NOT NULL,
    tier                   TEXT NOT NULL,
    score                  REAL NOT NULL,
    gates_fired            JSONB DEFAULT '[]',
    suppressions           JSONB DEFAULT '[]',   -- why we did NOT alert
    contributing_signals   JSONB DEFAULT '[]',
    contributing_candidates JSONB DEFAULT '[]',
    evidence_ids           JSONB DEFAULT '[]',
    explanation            TEXT
);
CREATE INDEX idx_asm_client ON risk_assessments(client_id, assessed_at DESC);

-- SNEHA
CREATE TABLE cases (
    case_id       TEXT PRIMARY KEY,
    client_id     TEXT REFERENCES customers(client_id),
    opened_at     TIMESTAMPTZ NOT NULL,
    status        TEXT NOT NULL,
    tier          TEXT NOT NULL,
    assessment_ids JSONB DEFAULT '[]'
);

CREATE TABLE timeline_events (
    id           BIGSERIAL PRIMARY KEY,
    case_id      TEXT REFERENCES cases(case_id),
    at           TIMESTAMPTZ NOT NULL,
    kind         TEXT,
    summary      TEXT,
    evidence_ids JSONB DEFAULT '[]',
    tier_before  TEXT,
    tier_after   TEXT       -- CAN GO DOWN. de-escalation is a feature.
);

CREATE TABLE reviewer_actions (
    action_id TEXT PRIMARY KEY,
    case_id   TEXT REFERENCES cases(case_id),
    at        TIMESTAMPTZ NOT NULL,
    reviewer  TEXT NOT NULL,
    action    TEXT NOT NULL,   -- CONFIRM|DISMISS|ESCALATE|REQUEST_INFO
    note      TEXT
);

CREATE TABLE sars (
    sar_id            TEXT PRIMARY KEY,
    case_id           TEXT REFERENCES cases(case_id),
    drafted_at        TIMESTAMPTZ NOT NULL,
    subject_name      TEXT,
    subject_pan       TEXT,
    sections          JSONB DEFAULT '{}',
    evidence_ids      JSONB DEFAULT '[]',
    unverified_claims JSONB DEFAULT '[]',  -- THE REFUSAL. what we would not say.
    citation_coverage REAL DEFAULT 0,
    status            TEXT DEFAULT 'DRAFT'
);

-- suppression rules produced by DISMISS -> "continuously improve"
CREATE TABLE suppression_rules (
    id           BIGSERIAL PRIMARY KEY,
    client_id    TEXT REFERENCES customers(client_id),
    watchlist_id TEXT REFERENCES watchlist_entries(watchlist_id),
    created_at   TIMESTAMPTZ DEFAULT now(),
    created_by   TEXT,
    reason       TEXT,
    UNIQUE (client_id, watchlist_id)
);

-- ============================================================
-- APPEND-ONLY AUDIT TRAIL. This is not a convention — it is enforced.
-- The risk timeline AND the audit trail both derive from this table.
-- ============================================================
CREATE TABLE audit_events (
    audit_id    TEXT PRIMARY KEY,
    at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor       TEXT NOT NULL,      -- agent:er | agent:sar | user:analyst_1
    action      TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id   TEXT NOT NULL,
    before      JSONB,
    after       JSONB,
    rationale   TEXT NOT NULL
);
CREATE INDEX idx_audit_object ON audit_events(object_id, at DESC);

CREATE RULE audit_no_update AS ON UPDATE TO audit_events DO INSTEAD NOTHING;
CREATE RULE audit_no_delete AS ON DELETE TO audit_events DO INSTEAD NOTHING;
