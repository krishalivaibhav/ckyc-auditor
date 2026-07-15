# Shared data contracts

This is the single source of truth for every JSON shape and DB table that crosses a service boundary. If you change something here, announce it in the team chat before pushing (see root README, git workflow rule 5). Everything below is a strong starting default — finalize exact field names together in the first hour, then treat it as frozen unless the whole team agrees to a change.

## 1. Entity (input to Person 1 and Person 2)

```json
{
  "entity_id": "uuid",
  "type": "person | company",
  "name": "string",
  "aliases": ["string"],
  "dob": "YYYY-MM-DD | null",
  "nationality": "ISO-3166 alpha-2 | null",
  "din_or_cin": "string | null",
  "source": "internal_kyc | client_input"
}
```

## 2. Candidate matches (Person 1 output → Person 2 input)

```json
{
  "query_entity_id": "uuid",
  "candidates": [
    {
      "candidate_id": "string",
      "matched_name": "string",
      "score": 0.0,
      "source_list": "OFAC | UN | EU | PEP | ...",
      "matched_fields": ["name", "dob", "nationality"],
      "raw": {}
    }
  ]
}
```

## 3. Resolution verdict (Person 2 output → Person 3, Person 5)

```json
{
  "query_entity_id": "uuid",
  "candidate_id": "string",
  "verdict": "confirmed_match | false_positive | needs_review",
  "confidence": 0.0,
  "explanation": "string, human-readable, cites which fields matched/mismatched",
  "anchor_used": "DIN | CIN | none",
  "resolved_at": "ISO 8601 timestamp"
}
```

## 4. Risk event (Person 3 output → Person 4)

```json
{
  "event_id": "uuid",
  "entity_id": "uuid",
  "event_type": "sanctions_hit | adverse_media | ownership_change",
  "severity": "low | medium | high",
  "detected_at": "ISO 8601 timestamp",
  "source_refs": ["candidate_id or article_url"]
}
```

## 5. Investigation output (Person 4 output → Person 5)

```json
{
  "entity_id": "uuid",
  "timeline": [
    {"date": "ISO 8601", "event": "string", "source_url": "string", "excerpt": "string, under 25 words"}
  ],
  "draft_report": {
    "summary": "string",
    "citations": [
      {"claim": "string", "source_url": "string", "excerpt": "string"}
    ]
  }
}
```

Every claim in `draft_report.summary` must trace back to at least one entry in `citations`. No uncited sentences — this is the difference between "AI wrote a report" and "AI assembled a report you can audit."

## 6. Audit log (write-only, everyone writes, only Person 5's API reads/exposes)

```json
{
  "log_id": "uuid",
  "actor": "agent:sanctions-agent | agent:entity-resolution | agent:media-orchestrator | agent:investigation-agent | human:<reviewer_name>",
  "action": "string, e.g. 'screened_entity', 'flagged_risk_event', 'resolved_verdict', 'approved_report', 'edited_report', 'rejected_report'",
  "entity_id": "uuid",
  "timestamp": "ISO 8601",
  "details": {}
}
```

**Append-only. Never update or delete a row.** This table is the audit trail — if it can be edited after the fact, it isn't one.

## Rules for everyone

- Use `entity_id` (uuid) as the join key across every table — generate it once, when an entity first enters the system (Person 5's ingestion endpoint), and pass it through unchanged everywhere else.
- Timestamps are always ISO 8601 UTC. No exceptions, no local time.
- If your service can't produce a required field, send `null` explicitly — never omit the key.
