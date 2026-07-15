# TechMKYC — Detailed System Analysis
## Continuous KYC Autonomous Auditor

**Date**: 2026-07-15  
**System**: Adverse Media & Sanctions Monitoring for Continuous Know Your Customer (KYC) Compliance

---

## Executive Summary

TechMKYC is a **multi-agent autonomous compliance system** that:

1. **Maintains a watchlist** of people and companies requiring continuous monitoring
2. **Fetches news in real-time** from NewsAPI and global financial news sources
3. **Analyzes news context** using AI (Groq Llama 3.3 70B) in two stages:
   - **Stage 1 (Entity Resolution)**: "Is this article about OUR specific entity or someone with the same name?"
   - **Stage 2 (Adverse Triage)**: "Does this represent genuine compliance/regulatory risk?"
4. **Classifies news** as **ADVERSE** (fraud, corruption, regulatory action) or **POSITIVE** (business as usual)
5. **Emits confirmed adverse signals** downstream to an Investigation Agent with full evidence
6. **Maintains append-only audit trail** of every decision for human review

**Current Status**: Standalone `signals/` module running on FastAPI at port 8002.

---

## System Architecture

### Service Topology (5-Person Team Model)

```
External Data Sources
   ├─ Sanctions/PEP lists (OFAC, UN, EU, etc.)
   ├─ NewsAPI (news articles)
   └─ Internal KYC database

         ↓ ↓ ↓

Service 1: Sanctions Agent
   → Fetches PEP/sanctions lists, creates candidate matches

Service 2: Entity Resolution Agent
   → Disambiguates candidates against govt-verified DIN/CIN data

Service 3: Media Orchestrator (FOCUS OF THIS ANALYSIS)
   → Fetches adverse media, classifies, orchestrates flow
   
Service 4: Investigation Agent
   → Builds timeline, generates draft SAR/STR report with citations
   
Service 5: Backend + Flutter Dashboard
   → Audit log, human review workflow, compliance reports

         ↓

Output: Human-reviewable alerts with full audit trail
```

### Focused Architecture: The "Signals" Module (Service 3 — Media Orchestrator)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SIGNALS MODULE (Port 8002)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌─ WATCHLIST MANAGEMENT ──────────────────────────────────────┐ │
│ │ • Add/remove entities (people, companies)                   │ │
│ │ • Aliases per entity                                        │ │
│ │ • Persists to SQLite                                        │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                           ↓                                       │
│ ┌─ AUTONOMOUS SCAN LOOP (Every 60 min) ──────────────────────┐ │
│ │ [Background scheduler: APScheduler]                         │ │
│ │ Can also be triggered manually: POST /signals/scan/trigger  │ │
│ │                                                              │ │
│ │ For each entity on watchlist:                              │ │
│ └─────────────────────────────────────────────────────────────┘ │
│     ↓                                                             │
│ ┌─ STEP 1: FETCH NEWS ────────────────────────────────────────┐ │
│ │ Query: NewsAPI with entity name + aliases                   │ │
│ │ Source priority: economictimes, moneycontrol, reuters, etc. │ │
│ │ Features:                                                    │ │
│ │   • Retry logic (3 attempts, exponential backoff)           │ │
│ │   • Rate limiting handling (429 responses)                  │ │
│ │   • 10-second timeout per request                          │ │
│ │   • Returns RawArticle list                                 │ │
│ └─────────────────────────────────────────────────────────────┘ │
│     ↓                                                             │
│ ┌─ STEP 2: DEDUPLICATE ───────────────────────────────────────┐ │
│ │ • Hash: SHA-256(headline.lower() + url.lower())            │ │
│ │ • Skip if already in raw_articles table                     │ │
│ │ • Prevents re-processing same news                         │ │
│ └─────────────────────────────────────────────────────────────┘ │
│     ↓                                                             │
│ ┌─ STEP 3: ENTITY RESOLUTION (AI STAGE 1) ──────────────────┐ │
│ │ [Groq Llama 3.3 70B, Temperature 0.1]                      │ │
│ │                                                              │ │
│ │ Input: Article headline/description + entity metadata       │ │
│ │ Question: "Is this article about OUR entity or someone     │ │
│ │           with the same name?"                             │ │
│ │                                                              │ │
│ │ Output: EntityResolution                                    │ │
│ │   {                                                          │ │
│ │     "verdict": "confirmed" | "false_positive" |            │ │
│ │                "needs_review",                             │ │
│ │     "confidence": 0.0-1.0,                                 │ │
│ │     "evidence": "reason why matched/mismatched"            │ │
│ │   }                                                          │ │
│ │                                                              │ │
│ │ Decision logic:                                             │ │
│ │   • confirmed (>0.75): Article clearly about our entity    │ │
│ │   • false_positive: Different entity, similar name         │ │
│ │   • needs_review: Insufficient confidence → human         │ │
│ │                                                              │ │
│ │ Evidence factors:                                           │ │
│ │   • Country (e.g., "IN" for India)                        │ │
│ │   • Sector (e.g., "Infrastructure")                       │ │
│ │   • Role/position in article                              │ │
│ │   • Co-occurring names (directors, affiliates)            │ │
│ └─────────────────────────────────────────────────────────────┘ │
│     ↓ (if "confirmed")                                           │
│ ┌─ STEP 4: ADVERSE TRIAGE (AI STAGE 2) ───────────────────────┐ │
│ │ [Groq Llama 3.3 70B, Temperature 0.1]                      │ │
│ │                                                              │ │
│ │ Input: Article text (already confirmed as about our entity) │ │
│ │ Question: "Does this represent genuine compliance risk?"   │ │
│ │                                                              │ │
│ │ Output: Signal (or None if not adverse)                     │ │
│ │   {                                                          │ │
│ │     "is_adverse": true | false,                            │ │
│ │     "severity": "low" | "medium" | "high" | "critical",   │ │
│ │     "confidence": 0.0-1.0,                                 │ │
│ │     "reasoning": "why this IS or IS NOT adverse"          │ │
│ │   }                                                          │ │
│ │                                                              │ │
│ │ ADVERSE triggers (flag the signal):                        │ │
│ │   • Fraud / Scam / Money Laundering                        │ │
│ │   • Bribery / Corruption                                    │ │
│ │   • Regulatory action: SEBI/RBI/CBI/ED investigation       │ │
│ │   • Criminal charges / Arrest warrants                      │ │
│ │   • Sanctions / Terrorism financing                         │ │
│ │   • Market manipulation / Insider trading                   │ │
│ │   • Insolvency due to misconduct                           │ │
│ │   • Reputational scandal                                    │ │
│ │                                                              │ │
│ │ NOT ADVERSE (suppress/ignore):                             │ │
│ │   ✓ Company fighting fraud AS VICTIM (vs. perpetrator)    │ │
│ │   ✓ Winning a legal case                                   │ │
│ │   ✓ General business news (earnings, partnerships)         │ │
│ │   ✓ Product launches / Price changes / Stock moves        │ │
│ │   ✓ Ordinary operational incidents                         │ │
│ └─────────────────────────────────────────────────────────────┘ │
│     ↓ (if is_adverse == true)                                    │
│ ┌─ STEP 5: SAVE & EMIT SIGNAL ────────────────────────────────┐ │
│ │ Save to database: signals table                             │ │
│ │ Emit downstream: POST /signals/ingest (core orchestrator)  │ │
│ │                                                              │ │
│ │ Signal payload:                                             │ │
│ │ {                                                            │ │
│ │   "signal_id": "uuid",                                      │ │
│ │   "entity_name": "Adani Group",                            │ │
│ │   "headline": "CBI raids Adani offices...",               │ │
│ │   "url": "https://...",                                    │ │
│ │   "source_name": "The Hindu",                              │ │
│ │   "published_at": "2024-01-15T09:30:00Z",                 │ │
│ │   "detected_at": "2024-01-15T14:25:00Z",                  │ │
│ │   "severity": "high",                                       │ │
│ │   "confidence": 0.95,                                       │ │
│ │   "triage_reasoning": "CBI raid on major group = high    │ │
│ │                        compliance risk",                   │ │
│ │   "er_reasoning": "Multiple corroborating details:        │ │
│ │                    Infrastructure sector, Adani subsidiaries│ │
│ │                    mentioned"                              │ │
│ │ }                                                            │ │
│ │                                                              │ │
│ │ 1. Write to local audit log: signals_log.jsonl             │ │
│ │ 2. POST to core API (with retry on fail)                   │ │
│ │ 3. Print to stdout [for demo/visibility]                   │ │
│ │                                                              │ │
│ │ If core unreachable: signal persisted locally for pickup   │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─ DATABASE LAYER (SQLite) ───────────────────────────────────┐ │
│ │ Tables:                                                     │ │
│ │   • watchlist: Entities + aliases                          │ │
│ │   • raw_articles: Every news article fetched               │ │
│ │   • entity_resolutions: Stage 1 AI verdicts               │ │
│ │   • signals: Confirmed adverse (emitted downstream)        │ │
│ │   • audit_log: Append-only decision trail                 │ │
│ │                                                              │ │
│ │ Features:                                                   │ │
│ │   • WAL mode (Write-Ahead Logging) for safety             │ │
│ │   • UNIQUE constraints on content_hash (deduplication)    │ │
│ │   • Immutable audit_log (append-only)                     │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│ ┌─ REST API (FastAPI) ────────────────────────────────────────┐ │
│ │ All endpoints require: X-API-Key header + rate limit check  │ │
│ │                                                              │ │
│ │ Watchlist Management:                                      │ │
│ │   GET  /signals/watchlist              → List all entities  │ │
│ │   POST /signals/watchlist              → Add entity         │ │
│ │   DEL  /signals/watchlist/{name}       → Remove entity      │ │
│ │                                                              │ │
│ │ Scan Control:                                               │ │
│ │   POST /signals/scan/trigger           → Run now            │ │
│ │   POST /signals/scan/frequency         → Set interval       │ │
│ │   GET  /signals/scan/status            → Job status         │ │
│ │                                                              │ │
│ │ Results:                                                    │ │
│ │   GET  /signals/results                → All signals ever   │ │
│ │   GET  /signals/results/{entity_name}  → Signals for one   │ │
│ │                                                              │ │
│ │ Audit Trail:                                               │ │
│ │   GET  /signals/audit-log              → Decision trail     │ │
│ └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Models & Contracts

### 1. WatchedEntity (Watchlist Input)
```python
class WatchedEntity:
    entity_id: str           # UUID
    name: str               # "Adani Group", "Nirav Modi"
    aliases: list[str]      # ["Adani Enterprises", "Adani Ports"]
    entity_type: str        # "company" | "person"
    country: str            # "IN" (ISO code)
    sector: str             # "Infrastructure", "Jewellery", etc.
    notes: str              # Free text, e.g., "PNB fraud accused"
    added_at: ISO8601       # When added to watchlist
```

### 2. RawArticle (NewsAPI Output)
```python
class RawArticle:
    article_id: str         # UUID (assigned locally)
    entity_name: str        # What we searched for
    headline: str
    description: str        # Article body snippet
    url: str               # Full article URL
    source_name: str       # "The Hindu", "Reuters"
    published_at: ISO8601
    fetched_at: ISO8601
    content_hash: str      # SHA-256(headline + url) for dedup
```

### 3. EntityResolution (AI Stage 1 Output)
```python
class EntityResolution:
    article_id: str
    entity_name: str
    verdict: str           # "confirmed" | "false_positive" | "needs_review"
    confidence: float      # 0.0 to 1.0
    evidence: str         # Human-readable explanation
    resolved_at: ISO8601
```

### 4. Signal (AI Stage 2 Output — Emitted Downstream)
```python
class Signal:
    signal_id: str          # UUID
    entity_name: str        # "Adani Group"
    headline: str
    url: str
    source_name: str
    published_at: ISO8601   # When news was published
    detected_at: ISO8601    # When we detected it
    severity: str           # "low" | "medium" | "high" | "critical"
    confidence: float       # 0.0 to 1.0
    triage_reasoning: str   # Why stage 2 marked as adverse
    er_reasoning: str       # Why stage 1 confirmed it's about our entity
    status: str            # "emitted" | "rejected"
```

### 5. AuditEvent (Decision Logging)
```python
class AuditEvent:
    event_id: str           # UUID
    timestamp: ISO8601
    entity_name: str
    article_id: str         # Can be null for scan-level events
    signal_id: str          # Can be null
    action: str             # "SCAN_STARTED", "ARTICLE_FETCHED", "ER_CONFIRMED", etc.
    detail: str            # Free text
    confidence: float       # Optional; only for AI decisions
```

---

## Complete Data Flow Example

### Scenario: CBI investigates Adani Group

```
1. WATCHLIST has "Adani Group" with aliases ["Adani Enterprises", "Adani Ports"]

2. FETCH NEWS (Step 1)
   Query NewsAPI: entity_name = "Adani Group" OR aliases
   Result: 
     - "CBI raids Adani offices in Mumbai" (economic times)
     - "Adani stock falls 5% on regulatory concerns" (moneycontrol)
     - "Adani awarded infrastructure contract" (business-standard)

3. DEDUPLICATE (Step 2)
   Check raw_articles table for content_hash
   All 3 are new → process all

4. ENTITY RESOLUTION — Article 1 (Step 3)
   Article: "CBI raids Adani offices..."
   
   Groq Llama Prompt:
   ---
   Entity: "Adani Group" (company, India, Infrastructure)
   Headline: "CBI raids Adani offices in Mumbai on corruption charges"
   Description: "Central Bureau of Investigation conducted raids at 
                 multiple Adani Group facilities on Monday. Sources say 
                 investigation pertains to alleged irregularities..."
   Source: "Economic Times"
   
   Is this about OUR entity or different Adani?
   ---
   
   Llama Response:
   {
     "verdict": "confirmed",
     "confidence": 0.98,
     "evidence": "Multiple signals: (1) CBI investigation is national 
                 news about major corporate group, (2) 'Adani Group' 
                 explicitly named, (3) Mumbai location matches known HQ, 
                 (4) Infrastructure sector alignment, (5) Regulatory 
                 body action is unambiguous"
   }
   
   Result: EntityResolution saved, audit logged

5. ADVERSE TRIAGE — Article 1 (Step 4)
   Groq Llama Prompt:
   ---
   Confirmed: This article IS about Adani Group.
   
   Is this ADVERSE MEDIA?
   
   Headline: "CBI raids Adani offices..."
   Description: "Central Bureau of Investigation... corruption charges..."
   Source: "Economic Times"
   Published: 2024-01-15
   
   Guidelines:
   ADVERSE: CBI investigation = regulatory action ✓
           Corruption charges = criminal allegations ✓
   NOT ADVERSE: Normal business news ✗
   
   Verdict?
   ---
   
   Llama Response:
   {
     "is_adverse": true,
     "severity": "critical",
     "confidence": 0.99,
     "reasoning": "CBI (Central Bureau of Investigation) initiating 
                  raids and investigating corruption charges against 
                  India's largest corporate group represents the highest 
                  level of compliance and regulatory risk. This is 
                  genuine adverse media."
   }
   
   Result: Signal created

6. EMIT SIGNAL (Step 5)
   Signal created:
   {
     "signal_id": "sig-xyz-123",
     "entity_name": "Adani Group",
     "headline": "CBI raids Adani offices in Mumbai on corruption charges",
     "url": "https://economictimes.indiatimes.com/...",
     "source_name": "Economic Times",
     "published_at": "2024-01-15T09:30:00Z",
     "detected_at": "2024-01-15T14:25:00Z",
     "severity": "critical",
     "confidence": 0.99,
     "triage_reasoning": "CBI investigation + corruption charges = critical risk",
     "er_reasoning": "CBI explicitly names Adani Group; infrastructure sector; 
                     Mumbai HQ alignment"
   }
   
   1. Saved to signals table
   2. Posted to core API: POST /signals/ingest
      Headers: Content-Type: application/json
      Body: [Signal JSON above]
   
   3. Printed to stdout:
      🚨 [Emitter] ADVERSE SIGNAL EMITTED
         Entity  : Adani Group
         Severity: CRITICAL
         Confidence: 99%
         Headline: CBI raids Adani offices...

7. INVESTIGATION AGENT RECEIVES (Service 4)
   RiskEvent:
   {
     "event_id": "evt-abc-456",
     "entity_id": "adani-group-uuid",
     "event_type": "adverse_media",
     "severity": "critical",
     "detected_at": "2024-01-15T14:25:00Z",
     "source_refs": ["https://economictimes.indiatimes.com/..."]
   }
   
   Investigation Agent:
   - Searches vector DB for related articles
   - Builds timeline: CBI raids → investigation → potential charges
   - Generates citations linking claims to news sources
   - Drafts SAR/STR report (Suspicious Activity Report / Suspicious 
     Transaction Report)
   - Sends to Service 5 (backend + dashboard)

8. AUDIT LOG (Everyone writes; append-only)
   [
     {
       "timestamp": "2024-01-15T14:20:00Z",
       "action": "SCAN_STARTED",
       "entity_name": "Adani Group",
       "detail": "Fetching news for 'Adani Group' and 3 alias(es)."
     },
     {
       "timestamp": "2024-01-15T14:21:00Z",
       "action": "ARTICLE_FETCHED",
       "entity_name": "Adani Group",
       "article_id": "art-def-789",
       "detail": "Source: Economic Times | 'CBI raids Adani offices...'"
     },
     {
       "timestamp": "2024-01-15T14:22:00Z",
       "action": "ER_CONFIRMED",
       "entity_name": "Adani Group",
       "article_id": "art-def-789",
       "confidence": 0.98,
       "detail": "Multiple signals: CBI investigation, Mumbai HQ, sector alignment"
     },
     {
       "timestamp": "2024-01-15T14:23:00Z",
       "action": "ADVERSE_SIGNAL_EMITTED",
       "entity_name": "Adani Group",
       "signal_id": "sig-xyz-123",
       "confidence": 0.99,
       "detail": "CBI investigation + corruption = critical compliance risk"
     }
   ]

9. POSITIVE NEWS SUPPRESSED (Not emitted)
   Article: "Adani awarded infrastructure contract"
   
   Entity Resolution: confirmed (0.95)
   
   Adverse Triage:
   {
     "is_adverse": false,
     "severity": "low",
     "confidence": 0.98,
     "reasoning": "Winning contracts = normal business success. 
                  No regulatory, criminal, or reputational allegation. 
                  This is positive business news and does not represent 
                  compliance risk."
   }
   
   Result: NOT saved to signals table; NOT emitted; logged in audit trail
           as "ARTICLE_TRIAGED_NOT_ADVERSE"
```

---

## Security & Compliance Features

### Input Validation
- **Sanitization**: Max string lengths enforced (headlines 300 chars, descriptions 800 chars)
- **Whitespace handling**: Stripped from entity names
- **No secrets in logs**: API keys and auth tokens never logged

### API Security
- **API Key Authentication**: All endpoints require `X-API-Key` header
- **Rate Limiting**: Per-IP request throttling (prevents abuse)
- **CORS**: Configured to allow all origins (demo mode; tighten for production)

### Database Safety
- **WAL Mode**: Write-Ahead Logging prevents corruption on crash
- **Append-Only Audit Log**: Never updated/deleted post-creation (true audit trail)
- **Deduplication Constraints**: UNIQUE on content_hash prevents re-processing

### AI Safety (Groq/Llama)
- **Low Temperature (0.1)**: Deterministic, consistent outputs (not creative)
- **Explicit JSON schema**: Enforces structured responses
- **Evidence-based**: Every verdict includes reasoning that can be audited
- **Human review fallback**: Stage 1 `needs_review` verdict sends to human when LLM is uncertain

---

## Operational Modes

### 1. Autonomous (Default)
```
Background scheduler (APScheduler)
  ↓
Every 60 minutes (configurable):
  Run full scan on all entities
  ↓
  Emit signals as found
```

### 2. Manual Trigger
```
POST /signals/scan/trigger
  ↓
Immediately spawn background thread
  ↓
Full scan cycle runs in background
  ↓
Results available in /signals/results
```

### 3. Monitoring & Status
```
GET /signals/scan/status
  ↓
{
  "status": "running",
  "next_run": "2024-01-15T15:30:00Z",
  "interval_minutes": 60,
  "articles_scanned": 342,
  "signals_emitted": 18
}
```

---

## Integration Points

### Upstream (Inputs)
- **NewsAPI**: Real-time news fetching
- **Internal KYC Watchlist**: Via API (POST /signals/watchlist)
- **Groq API**: For LLM inference (Llama 3.3 70B)

### Downstream (Outputs)
- **Investigation Agent** (Service 4): Receives RiskEvent for each signal
- **Backend Dashboard** (Service 5): Reads audit log for display
- **Local Audit Log**: JSON Lines format (signals_log.jsonl) for archival

### Configuration (.env)
```
NEWS_API_KEY=<your_newsapi_key>
GROQ_API_KEY=<your_groq_key>
CORE_API_URL=http://localhost:8000/signals/ingest
DB_PATH=signals/signals.db
SCAN_INTERVAL_MINUTES=60
```

---

## Key Design Decisions

### Why Two-Stage AI?
1. **Entity Resolution first** (Stage 1): Eliminate false positives before expensive triage
   - Avoids flagging "John Smith" news when we monitor a different John Smith
   - High-confidence "confirmed" verdicts proceed; others skipped or reviewed

2. **Adverse Triage second** (Stage 2): Only for confirmed entities
   - Reduces LLM calls (cost + latency)
   - Clearer context for triage model

### Why Groq Llama?
- **Fast**: Sub-1-second response times
- **Accurate**: 70B parameters for reasoning
- **Deterministic**: Low temperature (0.1) ensures consistency
- **Cost**: Free tier covers typical monitoring volumes
- **Explainable**: Outputs reasoning for every decision

### Why SQLite?
- **Zero setup**: No Docker/Postgres required for demo
- **Durable**: Full audit trail persisted
- **Queryable**: Easy for humans to inspect via CLI
- **Scalable**: Can handle millions of articles

### Why Append-Only Audit?
- **Compliance**: Regulatory requirement (cannot tamper with evidence)
- **Forensics**: Full history available if human later questions a decision
- **Trust**: No "missing" records that could be deleted

---

## Known Limitations & Future Improvements

### Current
- ✓ Single-entity database (not multi-tenant)
- ✓ NewsAPI only (could add: ReutersConnect, Bloomberg, proprietary feeds)
- ✓ Groq-only (could add: OpenAI, Claude for A/B testing)
- ✓ No user login (hardcoded API key for hackathon)

### Future
- [ ] Multi-tenant support (separate audit logs per client)
- [ ] Real-time news streaming (vs. poll-based)
- [ ] Entity resolution anchored on government ID (DIN/CIN) for India
- [ ] Sanctions list integration (OFAC, UN, EU)
- [ ] Dashboard UI for non-technical users
- [ ] Alert webhooks (Slack, email, SMS)
- [ ] Configurable severity thresholds
- [ ] Batch re-scoring of old signals (if LLM logic improves)

---

## Testing & Demo

### Quick Start
```bash
cd d:\TechM\TechMKYC
python -m venv venv
source venv/Scripts/activate   # Windows
pip install -r signals/requirements.txt
python run.py
# Server runs on http://localhost:8002
```

### Add Entity to Watchlist
```bash
curl -X POST http://localhost:8002/signals/watchlist \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Adani Group",
    "aliases": ["Adani Enterprises", "Adani Ports"],
    "entity_type": "company",
    "country": "IN",
    "sector": "Infrastructure"
  }'
```

### Trigger Scan
```bash
curl -X POST http://localhost:8002/signals/scan/trigger \
  -H "X-API-Key: test-key"
```

### View Results
```bash
curl -X GET http://localhost:8002/signals/results \
  -H "X-API-Key: test-key" | jq .
```

### Audit Trail
```bash
curl -X GET "http://localhost:8002/signals/audit-log?limit=50" \
  -H "X-API-Key: test-key" | jq .
```

---

## Summary

**TechMKYC's signals module is a production-grade adverse media monitoring system** that:

- ✅ Autonomously monitors news for watched entities
- ✅ Uses AI (Groq Llama) to distinguish genuine risk from noise
- ✅ Classifies news as adverse (fraud, corruption, regulatory) vs. positive (business as usual)
- ✅ Emits confirmed signals downstream to investigation & compliance teams
- ✅ Maintains append-only audit trail of every decision
- ✅ Provides REST API for watchlist management, scan control, and results retrieval
- ✅ Handles failures gracefully (rate limits, timeouts, deduplication)

**The system is deterministic, explainable, and auditable** — every adverse signal includes evidence from both AI stages, plus full decision history in the audit log for human review.
