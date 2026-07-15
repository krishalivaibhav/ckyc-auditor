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

// ═════════════════════════════════════════════════════════════════════════════
// New architecture — 05_SAMAKSH_ui.md contract
//
// These models describe the demo dashboard's six-screen contract (tiers,
// exposure, gates/suppressions, three-column evidence, SAR with [EV-nnn]
// citations, metrics, replay). They are ADDITIVE: the schema.md §1–6 models
// above still back the live Supabase tables. Until a migration lands, only
// [DemoRepository] serves these shapes — [SupabaseRepository] stubs them.
// ═════════════════════════════════════════════════════════════════════════════

/// Risk tier. CRITICAL is UAPA — always human, never auto-decided. Ranked for
/// sorting, but note risk = likelihood × exposure: a HIGH on ₹50cr outranks a
/// CRITICAL on ₹2L in practice, so the UI combines [rank] with exposure_inr.
enum RiskTier { critical, high, edd, eddLite, monitor, unknown }

RiskTier riskTierFromString(String? s) => switch (s?.toUpperCase()) {
      'CRITICAL' => RiskTier.critical,
      'HIGH' => RiskTier.high,
      'EDD' => RiskTier.edd,
      'EDD_LITE' => RiskTier.eddLite,
      'MONITOR' => RiskTier.monitor,
      _ => RiskTier.unknown,
    };

extension RiskTierX on RiskTier {
  /// The wire/DB value.
  String get wire => switch (this) {
        RiskTier.critical => 'CRITICAL',
        RiskTier.high => 'HIGH',
        RiskTier.edd => 'EDD',
        RiskTier.eddLite => 'EDD_LITE',
        RiskTier.monitor => 'MONITOR',
        RiskTier.unknown => 'UNKNOWN',
      };

  /// Human label for the badge.
  String get label => switch (this) {
        RiskTier.eddLite => 'EDD Lite',
        _ => wire[0] + wire.substring(1).toLowerCase(),
      };

  /// Severity ordering only (higher = more severe). Not the final queue order —
  /// combine with exposure_inr for that.
  int get rank => switch (this) {
        RiskTier.critical => 5,
        RiskTier.high => 4,
        RiskTier.edd => 3,
        RiskTier.eddLite => 2,
        RiskTier.monitor => 1,
        RiskTier.unknown => 0,
      };

  /// UAPA: always routed to a human, no auto-decisions.
  bool get alwaysHuman => this == RiskTier.critical;
}

/// A row in the alert queue (Screen 1). Sortable by tier × exposure.
class Alert {
  final String clientId;
  final String name;
  final String type; // Individual | Company
  final RiskTier tier;
  final String status; // open | in_review | escalated | closed
  final double exposureInr;
  final String? caseId;

  const Alert({
    required this.clientId,
    required this.name,
    required this.type,
    required this.tier,
    required this.status,
    required this.exposureInr,
    this.caseId,
  });

  factory Alert.fromJson(Map<String, dynamic> j) => Alert(
        clientId: j['client_id'].toString(),
        name: j['name'] as String,
        type: (j['type'] as String?) ?? 'Individual',
        tier: riskTierFromString(j['tier'] as String?),
        status: (j['status'] as String?) ?? 'open',
        exposureInr: _double(j['exposure_inr']),
        caseId: j['case_id']?.toString(),
      );
}

/// A customer record for the new contract — carries the identifiers the
/// side-by-side comparison (Screen 2) aligns against (PAN in particular, which
/// the schema.md [Entity] does not have).
class Customer {
  final String clientId;
  final String name;
  final String type; // Individual | Company
  final String? pan;
  final String? city;

  const Customer({
    required this.clientId,
    required this.name,
    required this.type,
    this.pan,
    this.city,
  });

  factory Customer.fromJson(Map<String, dynamic> j) => Customer(
        clientId: j['client_id'].toString(),
        name: j['name'] as String,
        type: (j['type'] as String?) ?? 'Individual',
        pan: j['pan'] as String?,
        city: j['city'] as String?,
      );
}

/// The computed risk verdict (Screen 2 header). Score is likelihood (0..1);
/// exposure_inr is the money at risk; gates_fired / suppressions explain why.
class RiskAssessment {
  final RiskTier tier;
  final double score; // 0..1 likelihood
  final double exposureInr;
  final List<String> gatesFired;
  final List<String> suppressions; // suppression ids / short codes fired here

  const RiskAssessment({
    required this.tier,
    required this.score,
    required this.exposureInr,
    this.gatesFired = const [],
    this.suppressions = const [],
  });

  factory RiskAssessment.fromJson(Map<String, dynamic> j) => RiskAssessment(
        tier: riskTierFromString(j['tier'] as String?),
        score: _double(j['score']),
        exposureInr: _double(j['exposure_inr']),
        gatesFired: _stringList(j['gates_fired']),
        suppressions: _stringList(j['suppressions']),
      );
}

/// A matched watchlist entry (Screen 2 right-hand side). When [rejectionReason]
/// is set the match was NOT accepted — render the reason in plain language.
class Candidate {
  final String candidateId;
  final String matchedName;
  final String? matchedPan;
  final String matchedType;
  final String listName; // e.g. "NSE/SEBI debarred", "MHA UAPA"
  final String matchMethod; // PAN_EXACT | NAME_DOB | ALIAS_BARE | ...
  final double confidence;
  final String? rejectionReason; // plain language, present iff rejected

  const Candidate({
    required this.candidateId,
    required this.matchedName,
    this.matchedPan,
    required this.matchedType,
    required this.listName,
    required this.matchMethod,
    required this.confidence,
    this.rejectionReason,
  });

  bool get rejected => rejectionReason != null;

  factory Candidate.fromJson(Map<String, dynamic> j) => Candidate(
        candidateId: j['candidate_id'].toString(),
        matchedName: j['matched_name'] as String,
        matchedPan: j['matched_pan'] as String?,
        matchedType: (j['matched_type'] as String?) ?? 'Individual',
        listName: j['list_name'] as String,
        matchMethod: j['match_method'] as String,
        confidence: _double(j['confidence']),
        rejectionReason: j['rejection_reason'] as String?,
      );
}

/// Entity 360 aggregate (Screen 2): customer ←→ matched watchlist entry, with
/// the risk assessment header.
class Entity360 {
  final Customer customer;
  final RiskAssessment assessment;
  final Candidate? candidate;

  const Entity360({
    required this.customer,
    required this.assessment,
    this.candidate,
  });
}

/// A suppressed (deliberately NOT raised) alert — Screen 5, the thesis screen.
class Suppression {
  final String customer;
  final String matched; // which list/entry it matched
  final String method; // PAN_MISMATCH_REJECT | ALIAS_BARE_REJECT | CROSS_LIST_NO_LINK
  final String reason; // plain-language "why we suppressed it"

  const Suppression({
    required this.customer,
    required this.matched,
    required this.method,
    required this.reason,
  });

  factory Suppression.fromJson(Map<String, dynamic> j) => Suppression(
        customer: j['customer'] as String,
        matched: j['matched'] as String,
        method: j['method'] as String,
        reason: j['reason'] as String,
      );
}

/// A dated risk-timeline event (Screen 3). Tier can move DOWN
/// ([isDeescalation]) — e.g. a SEBI order gets revoked.
class TimelineEvent {
  final String id;
  final String clientId;
  final DateTime date;
  final String event;
  final List<String> evidenceRefs; // [EV-nnn] chips
  final RiskTier tierBefore;
  final RiskTier tierAfter;

  const TimelineEvent({
    required this.id,
    required this.clientId,
    required this.date,
    required this.event,
    this.evidenceRefs = const [],
    required this.tierBefore,
    required this.tierAfter,
  });

  bool get isDeescalation => tierAfter.rank < tierBefore.rank;
  bool get isEscalation => tierAfter.rank > tierBefore.rank;

  factory TimelineEvent.fromJson(Map<String, dynamic> j) => TimelineEvent(
        id: j['id'].toString(),
        clientId: j['client_id'].toString(),
        date: _date(j['date']),
        event: j['event'] as String,
        evidenceRefs: _stringList(j['evidence_refs']),
        tierBefore: riskTierFromString(j['tier_before'] as String?),
        tierAfter: riskTierFromString(j['tier_after'] as String?),
      );
}

/// Which of the three evidence columns a card belongs to (Screen 4). Never
/// merged: confirmed / correlated / missing stay separate.
enum EvidenceColumn { confirmed, correlated, missing }

EvidenceColumn evidenceColumnFromString(String? s) => switch (s?.toLowerCase()) {
      'confirmed' => EvidenceColumn.confirmed,
      'correlated' => EvidenceColumn.correlated,
      'missing' => EvidenceColumn.missing,
      _ => EvidenceColumn.correlated,
    };

/// One evidence card (Screen 4). The [evId] ("EV-001") is visible because the
/// SAR cites it.
class Evidence {
  final String evId; // EV-nnn
  final EvidenceColumn column;
  final String claim;
  final String? sourceName;
  final String? sourceUrl;
  final String? excerpt;
  final double? confidence;

  const Evidence({
    required this.evId,
    required this.column,
    required this.claim,
    this.sourceName,
    this.sourceUrl,
    this.excerpt,
    this.confidence,
  });

  factory Evidence.fromJson(Map<String, dynamic> j) => Evidence(
        evId: j['ev_id'].toString(),
        column: evidenceColumnFromString(j['column'] as String?),
        claim: j['claim'] as String,
        sourceName: j['source_name'] as String?,
        sourceUrl: j['source_url'] as String?,
        excerpt: j['excerpt'] as String?,
        confidence: j['confidence'] == null ? null : _double(j['confidence']),
      );
}

/// A Suspicious Activity Report (Screen 6). [body] contains inline [EV-nnn]
/// citations that the UI turns into clickable chips; [unverifiedClaims] were
/// deliberately excluded because they could not be verified.
class Sar {
  final String caseId;
  final String body; // free text with inline [EV-nnn] markers
  final double citationCoverage; // 0..1
  final List<String> unverifiedClaims;
  final String status; // draft | approved

  const Sar({
    required this.caseId,
    required this.body,
    required this.citationCoverage,
    this.unverifiedClaims = const [],
    this.status = 'draft',
  });

  factory Sar.fromJson(Map<String, dynamic> j) => Sar(
        caseId: j['case_id'].toString(),
        body: j['body'] as String,
        citationCoverage: _double(j['citation_coverage']),
        unverifiedClaims: _stringList(j['unverified_claims']),
        status: (j['status'] as String?) ?? 'draft',
      );
}

/// Reviewer decisions — deliberately minimal for now. The entity-detail page
/// offers Blacklist / Dismiss; the SAR draft page offers Approve / Deny.
/// Escalate, request-info and case routing come later.
class EntityDecision {
  EntityDecision._();
  static const blacklist = 'BLACKLIST';
  static const dismiss = 'DISMISS';
  static const all = [blacklist, dismiss];
}

class SarDecision {
  SarDecision._();
  static const approve = 'APPROVE';
  static const deny = 'DENY';
  static const all = [approve, deny];
}

/// A reviewer action recorded on a case.
class CaseAction {
  final String action; // one of ReviewActions.*
  final String note;
  final String reviewer;
  final DateTime at;

  const CaseAction({
    required this.action,
    required this.note,
    required this.reviewer,
    required this.at,
  });

  factory CaseAction.fromJson(Map<String, dynamic> j) => CaseAction(
        action: j['action'] as String,
        note: (j['note'] as String?) ?? '',
        reviewer: (j['reviewer'] as String?) ?? 'unknown',
        at: _date(j['at']),
      );
}

/// A case (Screen 4 + 6): the entity, its evidence, the SAR, reviewer actions.
class Case {
  final String caseId;
  final String clientId;
  final Customer customer;
  final RiskAssessment assessment;
  final List<Evidence> evidence;
  final Sar? sar;
  final List<CaseAction> reviewerActions;

  /// The reviewer's terminal decision on the entity: null (undecided),
  /// 'blacklisted' or 'dismissed'. Kept simple on purpose — no state machine yet.
  final String? decision;

  const Case({
    required this.caseId,
    required this.clientId,
    required this.customer,
    required this.assessment,
    this.evidence = const [],
    this.sar,
    this.reviewerActions = const [],
    this.decision,
  });

  bool get isBlacklisted => decision == 'blacklisted';
  bool get isDismissed => decision == 'dismissed';

  Iterable<Evidence> column(EvidenceColumn c) =>
      evidence.where((e) => e.column == c);

  factory Case.fromJson(Map<String, dynamic> j) => Case(
        caseId: j['case_id'].toString(),
        clientId: j['client_id'].toString(),
        customer: Customer.fromJson(j['customer'] as Map<String, dynamic>),
        assessment:
            RiskAssessment.fromJson(j['assessment'] as Map<String, dynamic>),
        evidence: (j['evidence'] as List? ?? const [])
            .map((e) => Evidence.fromJson(e as Map<String, dynamic>))
            .toList(),
        sar: j['sar'] == null
            ? null
            : Sar.fromJson(j['sar'] as Map<String, dynamic>),
        reviewerActions: (j['reviewer_actions'] as List? ?? const [])
            .map((a) => CaseAction.fromJson(a as Map<String, dynamic>))
            .toList(),
        decision: j['decision'] as String?,
      );
}

/// One side of the before/after metrics toggle (Screen "before/after").
class MetricsSnapshot {
  final String label; // "BASELINE" | "OURS"
  final int alerts;
  final double precision;
  final double recall;

  const MetricsSnapshot({
    required this.label,
    required this.alerts,
    required this.precision,
    required this.recall,
  });

  factory MetricsSnapshot.fromJson(Map<String, dynamic> j) => MetricsSnapshot(
        label: (j['label'] as String?) ?? '',
        alerts: (j['alerts'] as num?)?.toInt() ?? 0,
        precision: _double(j['precision']),
        recall: _double(j['recall']),
      );
}

/// Precision/recall, naive screening vs our system.
class Metrics {
  final MetricsSnapshot baseline;
  final MetricsSnapshot ours;

  const Metrics({required this.baseline, required this.ours});

  /// False positives our system suppressed vs the baseline — the Screen 5
  /// headline "394 → N false positives suppressed".
  int get falsePositivesSuppressed => baseline.alerts - ours.alerts;

  factory Metrics.fromJson(Map<String, dynamic> j) => Metrics(
        baseline:
            MetricsSnapshot.fromJson(j['baseline'] as Map<String, dynamic>),
        ours: MetricsSnapshot.fromJson(j['ours'] as Map<String, dynamic>),
      );
}
