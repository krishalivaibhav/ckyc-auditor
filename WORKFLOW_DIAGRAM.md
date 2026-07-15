# TechMKYC Adverse News Detection Workflow

## Quick Reference Diagram

```
┌────────────────────────────────────────────────────────────────────────────┐
│                 TECHM KYC — ADVERSE MEDIA DETECTION FLOW                   │
└────────────────────────────────────────────────────────────────────────────┘


                           📋 WATCHLIST
                      People & Companies
                       to Monitor (e.g.,
                       Adani Group, Nirav Modi)
                              │
                              │
                              ↓
         ┌────────────────────────────────────────┐
         │     AUTONOMOUS SCAN (every 60 min)     │
         │        [APScheduler triggered]         │
         └────────────────────────────────────────┘
                              │
                              ↓
         ┌────────────────────────────────────────────────────────┐
         │  1️⃣  FETCH NEWS from NewsAPI                          │
         │  ─────────────────────────────────────                │
         │  Query: entity name + aliases                         │
         │  Sources: economictimes, reuters, bloomberg, etc.     │
         │  Features: retry logic, rate limit handling           │
         │  Output: RawArticle list                              │
         │                                                        │
         │  Example:                                             │
         │  • "CBI raids Adani offices on corruption charges"   │
         │  • "Nirav Modi's extradition case hearing"           │
         │  • "Infosys CEO resigns amid audit queries"          │
         └────────────────────────────────────────────────────────┘
                              │
                              ↓
         ┌────────────────────────────────────────────────────────┐
         │  2️⃣  DEDUPLICATE Articles                             │
         │  ─────────────────────────                            │
         │  Check content_hash (SHA-256)                         │
         │  Skip if already in raw_articles table                │
         │  Prevents re-processing same news                     │
         │  Output: NEW articles only                            │
         └────────────────────────────────────────────────────────┘
                              │
                              ↓
         ┌────────────────────────────────────────────────────────┐
         │  3️⃣  ENTITY RESOLUTION (AI Stage 1)                   │
         │  ─────────────────────────────────────                │
         │  [Groq Llama 3.3 70B, Temp 0.1]                       │
         │                                                        │
         │  Question: "Is this article about OUR entity          │
         │             or someone with the same name?"           │
         │                                                        │
         │  Evidence factors:                                    │
         │  • Country alignment (e.g., "IN" for India)          │
         │  • Sector match (Infrastructure, Jewellery, etc)     │
         │  • Company/person role in article                     │
         │  • Co-occurring names (directors, affiliates)         │
         └────────────────────────────────────────────────────────┘
                              │
                  ┌───────────┼───────────┐
                  ↓           ↓           ↓
            CONFIRMED    FALSE_POSITIVE  NEEDS_REVIEW
          (>0.75 conf)   (skip it)      (human review)
                  │
                  ↓
         ┌────────────────────────────────────────────────────────┐
         │  4️⃣  ADVERSE TRIAGE (AI Stage 2)                      │
         │  ──────────────────────────────────                   │
         │  [Groq Llama 3.3 70B, Temp 0.1]                       │
         │                                                        │
         │  Question: "Does this represent GENUINE              │
         │             COMPLIANCE RISK?"                         │
         └────────────────────────────────────────────────────────┘
                              │
                  ┌───────────┴───────────┐
                  ↓                       ↓
             ADVERSE ✓                NOT ADVERSE ✗
                  │                       │
                  │                       └──→ (suppress, log)
                  ↓
         ┌────────────────────────────────────────────────────────┐
         │ ADVERSE = Any of:                                      │
         │ • Fraud / Scam / Money Laundering                      │
         │ • Bribery / Corruption                                │
         │ • Regulatory action (SEBI/RBI/CBI/ED/RBC investigation│
         │ • Criminal charges / Arrest warrant                   │
         │ • Sanctions / Terrorism financing                     │
         │ • Market manipulation / Insider trading               │
         │ • Insolvency due to misconduct                        │
         │ • Reputational scandal                                │
         │                                                        │
         │ NOT ADVERSE = Any of:                                 │
         │ • Company fighting fraud AS VICTIM                    │
         │ • Winning legal case                                  │
         │ • Business news (earnings, partnership, product)      │
         │ • Price/stock moves                                   │
         │ • Ordinary operations                                 │
         └────────────────────────────────────────────────────────┘
                              │
                              ↓
         ┌────────────────────────────────────────────────────────┐
         │  5️⃣  EMIT SIGNAL Downstream                           │
         │  ────────────────────────────                         │
         │  Save to: signals table (SQLite)                      │
         │  Send to: Investigation Agent (Service 4)              │
         │  Log to: signals_log.jsonl (audit trail)              │
         │                                                        │
         │  Signal payload:                                      │
         │  {                                                     │
         │    "signal_id": "sig-xyz-123",                        │
         │    "entity_name": "Adani Group",                      │
         │    "headline": "CBI raids...",                        │
         │    "severity": "critical",                           │
         │    "confidence": 0.99,                                │
         │    "triage_reasoning": "CBI raid = high risk",       │
         │    "er_reasoning": "Explicit name + sector match"    │
         │  }                                                     │
         └────────────────────────────────────────────────────────┘
                              │
                              ↓
         ┌────────────────────────────────────────────────────────┐
         │  📊 INVESTIGATION AGENT (Service 4)                    │
         │  ──────────────────────────────────                   │
         │  • Receives RiskEvent                                  │
         │  • Builds timeline from related articles               │
         │  • Generates citations (evidence-based)                │
         │  • Drafts SAR/STR report                              │
         │  • Sends to Dashboard (Service 5)                      │
         └────────────────────────────────────────────────────────┘
                              │
                              ↓
         ┌────────────────────────────────────────────────────────┐
         │  👤 HUMAN REVIEWER (Dashboard / Flutter App)           │
         │  ────────────────────────────────────────             │
         │  • Reviews draft report with citations                │
         │  • Sees full audit trail                              │
         │  • Approves / Edits / Rejects                         │
         │  • Generates final SAR/STR for filing                │
         └────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════

## Database State Progression

Initial State:
┌─────────────────────────────────────────┐
│ watchlist    | name: "Adani Group"      │
│              | aliases: [3 items]        │
└─────────────────────────────────────────┘

After Step 1 (Fetch News):
┌─────────────────────────────────────────┐
│ raw_articles | art-1: "CBI raids Adani" │
│              | art-2: "Stock falls 5%"   │
│              | art-3: "Wins contract"   │
└─────────────────────────────────────────┘

After Step 2 (Deduplicate):
[same as above — all 3 are new]

After Step 3 (Entity Resolution):
┌──────────────────────────────────────────────┐
│ entity_resolutions                           │
│ art-1: verdict=CONFIRMED, conf=0.98          │
│ art-2: verdict=CONFIRMED, conf=0.96          │
│ art-3: verdict=CONFIRMED, conf=0.99          │
└──────────────────────────────────────────────┘

After Step 4 (Adverse Triage):
┌──────────────────────────────────────────────┐
│ signals                                       │
│ sig-1: "CBI raids" → is_adverse=TRUE          │
│        severity=CRITICAL, conf=0.99           │
│                                               │
│ (art-2 and art-3 NOT saved here —            │
│  they failed is_adverse check)               │
└──────────────────────────────────────────────┘

After Step 5 (Emit Signal):
┌──────────────────────────────────────────────┐
│ Investigation Agent notified:                │
│ RiskEvent {                                   │
│   event_id: evt-xyz                          │
│   entity_id: adani-group-uuid                │
│   event_type: "adverse_media"                │
│   severity: "critical"                       │
│   source_refs: ["https://economictimes..."]  │
│ }                                             │
└──────────────────────────────────────────────┘

Full Audit Trail:
┌──────────────────────────────────────────────┐
│ audit_log (append-only)                      │
│ • SCAN_STARTED                               │
│ • ARTICLE_FETCHED (art-1, 2, 3)             │
│ • ER_CONFIRMED (art-1, 2, 3)                │
│ • ADVERSE_SIGNAL_EMITTED (sig-1)            │
│ • ARTICLE_TRIAGED_NOT_ADVERSE (art-2, 3)   │
└──────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════

## Example: False Positive Suppression (Stage 1 ER)

Article fetched: "John Smith convicted of fraud"

Watchlist has: "John Smith" (CEO of XYZ Bank, India)

Stage 1 Analysis:
  Question: Is this about OUR John Smith or a different John Smith?
  
  Context:
    • Article from USA Today (about USA case)
    • Defendant is 45 years old (our CEO is 62)
    • No mention of Indian company or banking sector
    • No co-occurring names that match our database
  
  Verdict: FALSE_POSITIVE
  Confidence: 0.99
  Evidence: "Article is about a USA-based offender of different age and sector.
            No evidence this is the monitored Indian banking CEO named John Smith."
  
  Action: SKIP — Do not proceed to Adverse Triage
          (Even if it were adverse, it's about someone else)


═══════════════════════════════════════════════════════════════════════════════

## Example: Positive News Suppression (Stage 2 Triage)

Article: "Infosys wins $100M infrastructure contract"

Stage 1 (ER): CONFIRMED (0.95)
  "Clearly about Infosys Technologies"

Stage 2 (Triage) Question: Is this ADVERSE?

  Context:
    • Winning a contract = normal business success
    • No fraud, corruption, regulatory action, or scandal mentioned
    • Positive business development news
  
  Verdict: NOT ADVERSE
  Severity: LOW
  Confidence: 0.98
  Reasoning: "Winning contracts is ordinary business success and indicates 
            company health. No compliance risk. This is positive business news."
  
  Action: SKIP emission
          Log as "ARTICLE_TRIAGED_NOT_ADVERSE" in audit_log
          (No signal created; no downstream notification)


═══════════════════════════════════════════════════════════════════════════════

## REST API Endpoints (All require X-API-Key header)

Watchlist Management:
  GET    /signals/watchlist                   List all entities
  POST   /signals/watchlist                   Add entity
  DELETE /signals/watchlist/{name}            Remove entity

Scan Control:
  POST   /signals/scan/trigger                Run scan immediately
  POST   /signals/scan/frequency              Set scan interval
  GET    /signals/scan/status                 Check status & stats

Results:
  GET    /signals/results                     All signals ever
  GET    /signals/results/{entity_name}       Signals for one entity

Audit:
  GET    /signals/audit-log?limit=100         Decision trail


═══════════════════════════════════════════════════════════════════════════════

## AI Prompts (Simplified)

Stage 1 (Entity Resolution):
──────────────────────────
We are monitoring: {entity_name} ({entity_type}, {country}, {sector})
Article headline: {headline}
Article text: {description}
Source: {source_name}

Is this article about OUR entity or a different entity with the same name?

Respond ONLY JSON:
{
  "verdict": "confirmed" | "false_positive" | "needs_review",
  "confidence": 0.0-1.0,
  "evidence": "one sentence explanation"
}

Rules:
- "confirmed" (>0.75): clearly about our entity
- "false_positive": different entity, similar name
- "needs_review": uncertain — send to human


Stage 2 (Adverse Triage):
────────────────────────
Confirmed article about: {entity_name}
Article headline: {headline}
Article text: {description}
Source: {source_name}
Published: {published_at}

Does this represent GENUINE COMPLIANCE RISK?

ADVERSE (flag it):
  Fraud, money laundering, bribery, corruption, regulatory investigation,
  criminal charges, arrest, sanctions, market manipulation, insider trading

NOT ADVERSE (suppress):
  Company fighting fraud as victim, winning legal case, business news,
  earnings, partnerships, product launches, price moves

Respond ONLY JSON:
{
  "is_adverse": true | false,
  "severity": "low" | "medium" | "high" | "critical",
  "confidence": 0.0-1.0,
  "reasoning": "one or two sentences explaining why"
}


═══════════════════════════════════════════════════════════════════════════════
```

## Decision Trees

### Stage 1: Entity Resolution
```
Article fetched for entity "Adani Group"
       │
       ├─ Is "Adani Group" explicitly named in article?
       │  YES → +40 confidence
       │  NO  → Continue
       │
       ├─ Does article match entity sector (Infrastructure)?
       │  YES → +20 confidence
       │  NO  → Continue
       │
       ├─ Does article mention known locations (Mumbai HQ, subsidiary names)?
       │  YES → +20 confidence
       │  NO  → Continue
       │
       ├─ Does article mention co-occurring names (directors, affiliates)?
       │  YES → +15 confidence
       │  NO  → Continue
       │
       └─ Final confidence score:
          ≥ 0.75 → CONFIRMED (emit to Stage 2)
          0.5-0.74 → NEEDS_REVIEW (send to human)
          < 0.5 → FALSE_POSITIVE (skip)
```

### Stage 2: Adverse Triage
```
Article confirmed about our entity
       │
       ├─ Keywords present?
       │  ["fraud", "scam", "corruption", "CBI", "ED", "investigation",
       │   "arrest", "charges", "sanction", "manipulation", "insider trading"]
       │  → HIGH adverse signal ✓
       │
       ├─ Financial harm mentioned?
       │  ["default", "insolvency", "bankruptcy", "payment default",
       │   "massive losses", "shareholder lawsuit"]
       │  → HIGH adverse signal ✓
       │
       ├─ Positive keywords present?
       │  ["won", "awarded", "contract", "record revenue", "expansion",
       │   "partnership", "growth", "victory", "acquitted"]
       │  → NOT adverse; suppress ✗
       │
       ├─ Regulatory context?
       │  Positive: "agreed to settle", "implemented compliance"
       │  Negative: "investigation", "probe", "action", "violation"
       │  → Determine based on tone
       │
       └─ Final decision:
          Has adverse indicators + no mitigating positive context
          → is_adverse = TRUE; emit Signal ✓
          
          Has positive context or no adverse indicators
          → is_adverse = FALSE; suppress (log only) ✗
```

---

**End of Workflow Diagram**
