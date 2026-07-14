/// Dart mirrors of docs/schema.md §1–6. THIS is the integration contract with
/// Persons 1–4: field names and shapes must match the schema and the Postgres
/// tables. If schema.md changes, change these in lockstep (announce first).
library;

/// Helpers for parsing values coming back from Supabase/Postgres.
List<String> _stringList(dynamic v) =>
    v == null ? const [] : (v as List).map((e) => e.toString()).toList();

DateTime? _dateOrNull(dynamic v) =>
    v == null ? null : DateTime.tryParse(v.toString());

DateTime _date(dynamic v) => DateTime.parse(v.toString());

double _double(dynamic v) => v == null ? 0 : (v as num).toDouble();

/// §1 Entity
class Entity {
  final String entityId;
  final String type; // person | company
  final String name;
  final List<String> aliases;
  final DateTime? dob;
  final String? nationality; // ISO-3166 alpha-2
  final String? dinOrCin;
  final String source; // internal_kyc | client_input

  const Entity({
    required this.entityId,
    required this.type,
    required this.name,
    this.aliases = const [],
    this.dob,
    this.nationality,
    this.dinOrCin,
    required this.source,
  });

  factory Entity.fromJson(Map<String, dynamic> j) => Entity(
        entityId: j['entity_id'].toString(),
        type: j['type'] as String,
        name: j['name'] as String,
        aliases: _stringList(j['aliases']),
        dob: _dateOrNull(j['dob']),
        nationality: j['nationality'] as String?,
        dinOrCin: j['din_or_cin'] as String?,
        source: j['source'] as String,
      );

  /// For POST /entities — omit entity_id so Postgres generates it.
  Map<String, dynamic> toInsertJson() => {
        'type': type,
        'name': name,
        'aliases': aliases,
        'dob': dob?.toIso8601String().split('T').first,
        'nationality': nationality,
        'din_or_cin': dinOrCin,
        'source': source,
      };

  bool get isCompany => type == 'company';
}

/// §3 Resolution verdict (Person 2 output) — the risk score + plain-English why.
/// `candidateId` is always present (schema.md §7): 'none' when there was no
/// direct candidate to anchor against, rather than a null value.
class ResolutionVerdict {
  final String queryEntityId;
  final String candidateId;
  final String verdict; // confirmed_match | false_positive | needs_review
  final double confidence;
  final String explanation;
  final String anchorUsed; // DIN | CIN | none
  final DateTime resolvedAt;

  const ResolutionVerdict({
    required this.queryEntityId,
    required this.candidateId,
    required this.verdict,
    required this.confidence,
    required this.explanation,
    required this.anchorUsed,
    required this.resolvedAt,
  });

  factory ResolutionVerdict.fromJson(Map<String, dynamic> j) =>
      ResolutionVerdict(
        queryEntityId: j['query_entity_id'].toString(),
        candidateId: (j['candidate_id'] as String?) ?? 'none',
        verdict: j['verdict'] as String,
        confidence: _double(j['confidence']),
        explanation: j['explanation'] as String,
        anchorUsed: (j['anchor_used'] as String?) ?? 'none',
        resolvedAt: _date(j['resolved_at']),
      );
}

/// §4 Risk event (Person 3 output)
class RiskEvent {
  final String eventId;
  final String entityId;
  final String eventType; // sanctions_hit | adverse_media | ownership_change
  final String severity; // low | medium | high
  final DateTime detectedAt;
  final List<String> sourceRefs;

  const RiskEvent({
    required this.eventId,
    required this.entityId,
    required this.eventType,
    required this.severity,
    required this.detectedAt,
    this.sourceRefs = const [],
  });

  factory RiskEvent.fromJson(Map<String, dynamic> j) => RiskEvent(
        eventId: j['event_id'].toString(),
        entityId: j['entity_id'].toString(),
        eventType: j['event_type'] as String,
        severity: j['severity'] as String,
        detectedAt: _date(j['detected_at']),
        sourceRefs: _stringList(j['source_refs']),
      );
}

/// report_timeline entry (Person 4 output, schema.md §7). Scoped to a
/// draft_report, not the entity directly — an entity only has a detailed
/// timeline once Person 4 has filed a report on it; until then only
/// [RiskEvent]s (entity-scoped) are known.
class TimelineEntry {
  final String id;
  final String reportId;
  final DateTime eventDate;
  final String event;
  final String? sourceUrl;
  final String? excerpt;

  const TimelineEntry({
    required this.id,
    required this.reportId,
    required this.eventDate,
    required this.event,
    this.sourceUrl,
    this.excerpt,
  });

  factory TimelineEntry.fromJson(Map<String, dynamic> j) => TimelineEntry(
        id: j['id'].toString(),
        reportId: j['report_id'].toString(),
        eventDate: _date(j['event_date']),
        event: j['event'] as String,
        sourceUrl: j['source_url'] as String?,
        excerpt: j['excerpt'] as String?,
      );
}

/// §5 Draft report citation — every claim must trace to one of these.
class Citation {
  final String claim;
  final String? sourceUrl;
  final String? excerpt;

  const Citation({
    required this.claim,
    this.sourceUrl,
    this.excerpt,
  });

  factory Citation.fromJson(Map<String, dynamic> j) => Citation(
        claim: j['claim'] as String,
        sourceUrl: j['source_url'] as String?,
        excerpt: j['excerpt'] as String?,
      );
}

/// §5 Draft report (Person 4 output)
class DraftReport {
  final String reportId;
  final String entityId;
  final String summary;
  final String status; // draft | approved | edited | rejected
  final List<Citation> citations;
  final List<TimelineEntry> timeline;

  const DraftReport({
    required this.reportId,
    required this.entityId,
    required this.summary,
    required this.status,
    this.citations = const [],
    this.timeline = const [],
  });

  factory DraftReport.fromJson(Map<String, dynamic> j) => DraftReport(
        reportId: j['report_id'].toString(),
        entityId: j['entity_id'].toString(),
        summary: j['summary'] as String,
        status: (j['status'] as String?) ?? 'draft',
        citations: (j['report_citations'] as List? ?? const [])
            .map((c) => Citation.fromJson(c as Map<String, dynamic>))
            .toList(),
        timeline: (j['report_timeline'] as List? ?? const [])
            .map((t) => TimelineEntry.fromJson(t as Map<String, dynamic>))
            .toList(),
      );
}

/// §6 Audit log entry (append-only)
class AuditEntry {
  final String logId;
  final String actor; // agent:<name> | human:<reviewer>
  final String action;
  final String? entityId;
  final DateTime timestamp;
  final Map<String, dynamic> details;

  const AuditEntry({
    required this.logId,
    required this.actor,
    required this.action,
    this.entityId,
    required this.timestamp,
    this.details = const {},
  });

  factory AuditEntry.fromJson(Map<String, dynamic> j) => AuditEntry(
        logId: j['log_id'].toString(),
        actor: j['actor'] as String,
        action: j['action'] as String,
        entityId: j['entity_id']?.toString(),
        timestamp: _date(j['timestamp']),
        details: (j['details'] as Map?)?.cast<String, dynamic>() ?? const {},
      );

  bool get isHuman => actor.startsWith('human:');
  String get actorName => actor.contains(':') ? actor.split(':').last : actor;
}

/// Convenience aggregate the dashboard renders per entity. Not a DB table —
/// assembled client-side by joining the tables above on entity_id.
class EntityDetail {
  final Entity entity;
  final ResolutionVerdict? verdict;
  final List<RiskEvent> riskEvents;
  final DraftReport? report;

  const EntityDetail({
    required this.entity,
    this.verdict,
    this.riskEvents = const [],
    this.report,
  });

  /// Detailed timeline only exists once Person 4 has filed a report — before
  /// that, only [riskEvents] are known.
  List<TimelineEntry> get timeline => report?.timeline ?? const [];

  /// Highest severity among risk events — drives the watchlist badge.
  String get topSeverity {
    if (riskEvents.any((e) => e.severity == 'high')) return 'high';
    if (riskEvents.any((e) => e.severity == 'medium')) return 'medium';
    if (riskEvents.any((e) => e.severity == 'low')) return 'low';
    return 'none';
  }
}
