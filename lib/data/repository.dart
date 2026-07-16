import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../core/api.dart';
import '../models/models.dart';
import 'demo_data.dart';

/// Data access for the dashboard. Two implementations behind one interface:
///  - [ApiRepository]   → the local read API over ckyc.db (api/server.py).
///  - [DemoRepository]  → bundled seed data, offline-safe fallback.
abstract class KycRepository {
  /// Watchlist rows: entity + its verdict + risk events (for the severity badge).
  Future<List<EntityDetail>> fetchWatchlist();

  /// Full detail for one entity: verdict, risk events, and the filed report
  /// (whose report_timeline carries the detailed evidence timeline, if any).
  Future<EntityDetail> fetchDetail(String entityId);

  /// Append-only audit trail, optionally scoped to one entity.
  Future<List<AuditEntry>> fetchAudit({String? entityId});

  /// POST /entities — server generates entity_id.
  Future<Entity> ingestEntity(Entity draft);

  /// Human review action → atomic status change + audit write (review_report RPC).
  Future<void> reviewReport({
    required String reportId,
    required String action, // approve | edit | reject
    required String reviewerName,
    String? editedSummary,
  });

  /// Emits whenever upstream data changes, so the UI can refresh live.
  ///
  /// Carries a monotonically increasing revision — NOT void — deliberately:
  /// [changesProvider] is a StreamProvider, and Riverpod skips notifying
  /// dependents when the new AsyncData equals the previous one. A void stream
  /// emits identical `AsyncData(null)` states, so only the FIRST event would
  /// ever trigger a re-fetch (the time-skip-didn't-refresh bug). Distinct
  /// revision values make every event propagate.
  Stream<int> changes();

  // ── 05_SAMAKSH_ui.md six-screen contract ──────────────────────────────────
  // The tier-based model. Served by ApiRepository from ckyc.db (api/server.py);
  // the schema.md §1–6 methods above are retired and have no DB backing.

  /// Screen 1 — alert queue, optionally filtered by tier and/or status.
  Future<List<Alert>> fetchAlerts({RiskTier? tier, String? status});

  /// Screen 2 — Entity 360: customer ←→ matched watchlist entry + assessment.
  Future<Entity360> fetchEntity360(String clientId);

  /// Screen 3 — risk timeline (tier can go down).
  Future<List<TimelineEvent>> fetchEntityTimeline(String clientId);

  /// Screen 4 + 6 — full case: three-column evidence, SAR, reviewer actions.
  Future<Case> fetchCase(String caseId);

  /// Screen 4 + 6 — the case for a client, when the caller has the client id but
  /// not the case id (the drill-down from Entity 360). Null if none filed yet.
  Future<Case?> fetchCaseByClient(String clientId);

  /// Screen 6 — just the SAR for a case (may be null if none drafted yet).
  Future<Sar?> fetchSar(String caseId);

  /// Entity-detail page — the reviewer's terminal decision on the entity
  /// (EntityDecision.blacklist | EntityDecision.dismiss).
  Future<void> reviewCase({
    required String caseId,
    required String action,
    required String note,
    required String reviewerName,
  });

  /// SAR draft page — approve or deny the SAR (SarDecision.approve | .deny).
  Future<void> reviewSar({
    required String caseId,
    required String action,
    required String reviewerName,
    String note = '',
  });

  /// Screen 5 — the suppression log (alerts we did NOT raise, and why).
  Future<List<Suppression>> fetchSuppressions();

  /// Reports tab — every case that carries a drafted SAR (preview + download).
  Future<List<SarReport>> fetchReports();

  /// Before/after toggle — precision/recall, naive screening vs our system.
  Future<Metrics> fetchMetrics();

  /// Temporal replay control — streams the window from→to at [speed], firing
  /// [changes] so the dashboard lights up live.
  Future<void> replay({
    required DateTime from,
    required DateTime to,
    int speed = 1000,
  });

  // ── live/test mode — the judges' demo ─────────────────────────────────────

  /// Current mode + scenario phase (0 = not started, 1 = first news,
  /// 2 = after the time skip).
  Future<DemoStatus> fetchMode();

  /// Switch 'live' <-> 'test'. Switching to test runs the scripted scenario on
  /// the backend (watch its terminal) and re-points every read at the demo
  /// sink; the call returns when phase 1 has been persisted.
  Future<DemoStatus> setMode(String mode);

  /// Advance the test scenario +15 months (3 news articles + the sanction).
  Future<DemoStatus> timeSkip();

  // ── risk-alert email (Settings screen) ────────────────────────────────────

  /// Current alert recipient + whether the backend can send (SMTP configured).
  Future<AlertConfig> fetchAlertConfig();

  /// Set the recipient email that HIGH/CRITICAL hits are mailed to.
  Future<AlertConfig> setAlertEmail(String email);

  /// Send a test alert to verify the wiring end-to-end.
  Future<void> sendTestAlert({String? email});
}

/// Live/test mode status. Not part of the six-screen data contract — pure
/// demo-control plumbing, so it lives here rather than in models.dart.
class DemoStatus {
  final String mode; // 'live' | 'test'
  final int phase; // 0 none, 1 first news, 2 after time skip

  // Populated only by the time-skip response, when the escalation to
  // HIGH/CRITICAL triggered a risk-alert email. Null when no alert was attempted.
  final bool? alertSent;
  final String? alertTo;
  final String? alertError;

  const DemoStatus({
    required this.mode,
    required this.phase,
    this.alertSent,
    this.alertTo,
    this.alertError,
  });

  bool get isTest => mode == 'test';
  bool get canTimeSkip => isTest && phase == 1;

  factory DemoStatus.fromJson(Map<String, dynamic> j) {
    final alert = j['alert'] as Map<String, dynamic>?;
    return DemoStatus(
      mode: (j['mode'] as String?) ?? 'live',
      phase: (j['phase'] as num?)?.toInt() ?? 0,
      alertSent: alert?['sent'] as bool?,
      alertTo: alert?['to'] as String?,
      alertError: (alert?['error'] ?? alert?['reason']) as String?,
    );
  }

  static const live = DemoStatus(mode: 'live', phase: 0);
}

/// Risk-alert email config (Settings screen). [email] is the recipient the
/// backend mails on a HIGH/CRITICAL hit; [smtpConfigured] is whether the sender
/// (Gmail app password) is present in the backend's .env.
class AlertConfig {
  final String? email;
  final bool smtpConfigured;

  const AlertConfig({this.email, this.smtpConfigured = false});

  bool get hasRecipient => email != null && email!.trim().isNotEmpty;
  bool get enabled => hasRecipient && smtpConfigured;

  factory AlertConfig.fromJson(Map<String, dynamic> j) => AlertConfig(
        email: j['email'] as String?,
        smtpConfigured: (j['smtp_configured'] as bool?) ?? false,
      );

  static const empty = AlertConfig();
}

// ─────────────────────────────────────────────────────────────────────────────
// Live implementation — the local read API over ckyc.db (api/server.py).
//
// Read-only for now (per "just read operation for now"): the six-screen GET
// endpoints are wired; reviewer WRITES (blacklist/dismiss/approve/deny) will
// POST to the same API in the UI phase so the append-only audit stays in Python.
// The retired schema.md §1–6 entity endpoints (entities/verdicts/risk_events)
// have no backing in this DB and throw — those screens get replaced in the UI
// rewire, not migrated.
// ─────────────────────────────────────────────────────────────────────────────
class ApiRepository implements KycRepository {
  ApiRepository({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _base = baseUrl ?? ApiConfig.baseUrl;

  final http.Client _client;
  final String _base;
  // Emits a fresh revision after every successful write / mode switch so all
  // change-aware providers re-fetch. (No server push yet; local events only.)
  final _changes = StreamController<int>.broadcast();
  var _rev = 0;
  void _bump() => _changes.add(++_rev);

  Uri _uri(String path, [Map<String, String>? query]) =>
      Uri.parse('$_base$path').replace(
          queryParameters: (query == null || query.isEmpty) ? null : query);

  Future<dynamic> _get(String path, [Map<String, String>? query]) async {
    final res = await _client.get(_uri(path, query));
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, path, res.body);
    }
    return jsonDecode(res.body);
  }

  Future<dynamic> _post(String path, Map<String, dynamic> body) async {
    final res = await _client.post(_uri(path),
        headers: {'Content-Type': 'application/json'}, body: jsonEncode(body));
    if (res.statusCode != 200) {
      throw ApiException(res.statusCode, path, res.body);
    }
    return res.body.isEmpty ? null : jsonDecode(res.body);
  }

  @override
  Stream<int> changes() => _changes.stream;

  Future<void> dispose() async {
    _client.close();
    await _changes.close();
  }

  // ── 05_SAMAKSH_ui.md six-screen reads ─────────────────────────────────────
  @override
  Future<List<Alert>> fetchAlerts({RiskTier? tier, String? status}) async {
    final q = <String, String>{};
    if (tier != null) q['tier'] = tier.wire;
    if (status != null) q['status'] = status;
    final list = await _get('/api/alerts', q) as List;
    return list.map((e) => Alert.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  Future<Entity360> fetchEntity360(String clientId) async {
    final j = await _get('/api/entity/$clientId') as Map<String, dynamic>;
    final cand = j['candidate'];
    return Entity360(
      customer: Customer.fromJson(j['customer'] as Map<String, dynamic>),
      assessment:
          RiskAssessment.fromJson(j['assessment'] as Map<String, dynamic>),
      candidate: cand == null
          ? null
          : Candidate.fromJson(cand as Map<String, dynamic>),
    );
  }

  @override
  Future<List<TimelineEvent>> fetchEntityTimeline(String clientId) async {
    final list = await _get('/api/entity/$clientId/timeline') as List;
    return list
        .map((e) => TimelineEvent.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<Case> fetchCase(String caseId) async {
    final j = await _get('/api/case/$caseId') as Map<String, dynamic>;
    return Case.fromJson(j);
  }

  @override
  Future<Case?> fetchCaseByClient(String clientId) async {
    try {
      final j = await _get('/api/entity/$clientId/case') as Map<String, dynamic>;
      return Case.fromJson(j);
    } on ApiException catch (e) {
      if (e.statusCode == 404) return null; // no case filed for this client yet
      rethrow;
    }
  }

  @override
  Future<Sar?> fetchSar(String caseId) async {
    final j = await _get('/api/case/$caseId/sar');
    return j == null ? null : Sar.fromJson(j as Map<String, dynamic>);
  }

  @override
  Future<List<AuditEntry>> fetchAudit({String? entityId}) async {
    final list = await _get(
        '/api/audit', entityId == null ? null : {'object_id': entityId}) as List;
    return list
        .map((e) => AuditEntry.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<List<Suppression>> fetchSuppressions() async {
    final list = await _get('/api/suppressions') as List;
    return list
        .map((e) => Suppression.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<List<SarReport>> fetchReports() async {
    final list = await _get('/api/reports') as List;
    return list
        .map((e) => SarReport.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<Metrics> fetchMetrics() async {
    final j = await _get('/api/metrics') as Map<String, dynamic>;
    return Metrics.fromJson(j);
  }

  // ── writes — the reviewer's terminal decision, POSTed to the read-API ─────
  // These are the ONLY mutations: the read-API applies them to the same sink
  // the pipeline persists to (flip Case status + append one audit row, atomic).
  // Firing [_changes] afterwards makes every change-aware provider re-fetch.
  @override
  Future<void> reviewCase({
    required String caseId,
    required String action,
    required String note,
    required String reviewerName,
  }) async {
    await _post('/api/case/$caseId/review',
        {'action': action, 'note': note, 'reviewer': reviewerName});
    _bump();
  }

  @override
  Future<void> reviewSar({
    required String caseId,
    required String action,
    required String reviewerName,
    String note = '',
  }) async {
    await _post('/api/case/$caseId/sar/review',
        {'action': action, 'note': note, 'reviewer': reviewerName});
    _bump();
  }

  // ── still deferred (retired schema.md ingest/report model) ────────────────
  static Never _readOnly(String what) => throw UnimplementedError(
      '$what is a write with no backing in this contract — the ingest form and '
      'the schema.md draft-report review belong to the retired model.');

  @override
  Future<Entity> ingestEntity(Entity draft) => _readOnly('ingestEntity');

  @override
  Future<void> reviewReport({
    required String reportId,
    required String action,
    required String reviewerName,
    String? editedSummary,
  }) =>
      _readOnly('reviewReport');

  @override
  Future<void> replay({
    required DateTime from,
    required DateTime to,
    int speed = 1000,
  }) async {
    // No server-side replay endpoint yet; no-op so callers don't crash.
  }

  // ── live/test mode ─────────────────────────────────────────────────────────
  @override
  Future<DemoStatus> fetchMode() async {
    final j = await _get('/api/mode') as Map<String, dynamic>;
    return DemoStatus.fromJson(j);
  }

  @override
  Future<DemoStatus> setMode(String mode) async {
    // Switching to test runs the whole phase-1 scenario server-side before
    // returning — the caller should show progress while awaiting this.
    final j = await _post('/api/mode', {'mode': mode}) as Map<String, dynamic>;
    _bump(); // every screen re-reads from the newly-pointed sink
    return DemoStatus.fromJson(j);
  }

  @override
  Future<DemoStatus> timeSkip() async {
    final j = await _post('/api/demo/timeskip', {}) as Map<String, dynamic>;
    _bump();
    return DemoStatus.fromJson(j);
  }

  // ── risk-alert email ───────────────────────────────────────────────────────
  @override
  Future<AlertConfig> fetchAlertConfig() async {
    final j = await _get('/api/alert-config') as Map<String, dynamic>;
    return AlertConfig.fromJson(j);
  }

  @override
  Future<AlertConfig> setAlertEmail(String email) async {
    final j = await _post('/api/alert-config', {'email': email})
        as Map<String, dynamic>;
    _bump();
    return AlertConfig.fromJson(j);
  }

  @override
  Future<void> sendTestAlert({String? email}) async {
    await _post('/api/alert-config/test', email == null ? {} : {'email': email});
  }

  // ── retired schema.md §1–6 (entities/verdicts/risk_events) — no DB backing ─
  static Never _retired(String what) => throw UnimplementedError(
      '$what belongs to the retired schema.md §1–6 model (severity/entities). '
      'The tier-based contract replaced it; those screens are rebuilt in the '
      'UI phase against fetchAlerts/fetchEntity360/fetchCase.');

  @override
  Future<List<EntityDetail>> fetchWatchlist() => _retired('fetchWatchlist');

  @override
  Future<EntityDetail> fetchDetail(String entityId) => _retired('fetchDetail');
}

/// A non-200 from the read API, surfaced with enough context to debug.
class ApiException implements Exception {
  final int statusCode;
  final String path;
  final String body;
  ApiException(this.statusCode, this.path, this.body);
  @override
  String toString() => 'ApiException($statusCode on $path): $body';
}

// ─────────────────────────────────────────────────────────────────────────────
// Demo (offline) implementation — mutates in-memory copies of the seed data
// ─────────────────────────────────────────────────────────────────────────────
class DemoRepository implements KycRepository {
  final _changes = StreamController<int>.broadcast();
  var _rev = 0;
  void _bump() => _changes.add(++_rev);
  late final List<Entity> _entities = [...DemoData.entities];
  late final List<DraftReport> _reports = [...DemoData.reports];
  late final List<AuditEntry> _audit = [...DemoData.audit];
  // 05_SAMAKSH_ui.md contract — mutable so reviewCase/approveSar can update them.
  late final Map<String, Case> _cases = {...DemoData.cases};
  var _seq = 0;

  @override
  Stream<int> changes() => _changes.stream;

  @override
  Future<List<EntityDetail>> fetchWatchlist() async {
    return _entities.map((e) {
      final v = DemoData.verdicts.where((x) => x.queryEntityId == e.entityId);
      final ev =
          DemoData.riskEvents.where((x) => x.entityId == e.entityId).toList();
      return EntityDetail(
        entity: e,
        verdict: v.isEmpty ? null : v.first,
        riskEvents: ev,
      );
    }).toList();
  }

  @override
  Future<EntityDetail> fetchDetail(String entityId) async {
    final e = _entities.firstWhere((x) => x.entityId == entityId);
    final v = DemoData.verdicts.where((x) => x.queryEntityId == entityId);
    final report = _reports.where((r) => r.entityId == entityId);
    return EntityDetail(
      entity: e,
      verdict: v.isEmpty ? null : v.first,
      riskEvents: (DemoData.riskEvents.where((x) => x.entityId == entityId)
            ..toList())
          .toList()
        ..sort((a, b) => b.detectedAt.compareTo(a.detectedAt)),
      report: report.isEmpty ? null : report.first,
    );
  }

  @override
  Future<List<AuditEntry>> fetchAudit({String? entityId}) async {
    final list = entityId == null
        ? _audit
        : _audit.where((a) => a.entityId == entityId).toList();
    return [...list]..sort((a, b) => b.timestamp.compareTo(a.timestamp));
  }

  @override
  Future<Entity> ingestEntity(Entity draft) async {
    final e = Entity(
      entityId: 'demo-${++_seq}-${DateTime.now().millisecondsSinceEpoch}',
      type: draft.type,
      name: draft.name,
      aliases: draft.aliases,
      dob: draft.dob,
      nationality: draft.nationality,
      dinOrCin: draft.dinOrCin,
      source: draft.source,
    );
    _entities.insert(0, e);
    _audit.insert(
        0,
        AuditEntry(
          logId: 'demo-al-${++_seq}',
          actor: 'agent:ingestion',
          action: 'ingested_entity',
          entityId: e.entityId,
          timestamp: DateTime.now().toUtc(),
        ));
    _bump();
    return e;
  }

  @override
  Future<void> reviewReport({
    required String reportId,
    required String action,
    required String reviewerName,
    String? editedSummary,
  }) async {
    final idx = _reports.indexWhere((r) => r.reportId == reportId);
    if (idx == -1) return;
    final r = _reports[idx];
    final newStatus = switch (action) {
      'approve' => 'approved',
      'edit' => 'edited',
      'reject' => 'rejected',
      _ => r.status,
    };
    _reports[idx] = DraftReport(
      reportId: r.reportId,
      entityId: r.entityId,
      summary: editedSummary ?? r.summary,
      status: newStatus,
      citations: r.citations,
    );
    _audit.insert(
        0,
        AuditEntry(
          logId: 'demo-al-${++_seq}',
          actor: 'human:$reviewerName',
          action: '$action${action == 'approve' ? 'd' : 'ed'}_report',
          entityId: r.entityId,
          timestamp: DateTime.now().toUtc(),
          details: {'report_id': reportId, 'new_status': newStatus},
        ));
    _bump();
  }

  // ── 05_SAMAKSH_ui.md six-screen contract ──────────────────────────────────

  @override
  Future<List<Alert>> fetchAlerts({RiskTier? tier, String? status}) async {
    final list = DemoData.alerts.where((a) {
      if (tier != null && a.tier != tier) return false;
      if (status != null && a.status != status) return false;
      return true;
    }).toList();
    // Risk = likelihood × exposure: order by tier rank, then exposure, so a
    // HIGH on ₹50cr can sit above a CRITICAL on ₹2L when the UI wants that.
    list.sort((a, b) {
      final byTier = b.tier.rank.compareTo(a.tier.rank);
      return byTier != 0 ? byTier : b.exposureInr.compareTo(a.exposureInr);
    });
    return list;
  }

  @override
  Future<Entity360> fetchEntity360(String clientId) async {
    final e = DemoData.entity360[clientId];
    if (e == null) {
      throw StateError('No Entity360 fixture for client $clientId');
    }
    return e;
  }

  @override
  Future<List<TimelineEvent>> fetchEntityTimeline(String clientId) async {
    final list = [...(DemoData.timelines[clientId] ?? const <TimelineEvent>[])];
    list.sort((a, b) => a.date.compareTo(b.date));
    return list;
  }

  @override
  Future<Case> fetchCase(String caseId) async {
    final c = _cases[caseId];
    if (c == null) throw StateError('No case fixture for $caseId');
    return c;
  }

  @override
  Future<Case?> fetchCaseByClient(String clientId) async {
    for (final c in _cases.values) {
      if (c.clientId == clientId) return c;
    }
    return null;
  }

  @override
  Future<Sar?> fetchSar(String caseId) async => _cases[caseId]?.sar;

  @override
  Future<void> reviewCase({
    required String caseId,
    required String action,
    required String note,
    required String reviewerName,
  }) async {
    final c = _cases[caseId];
    if (c == null) return;
    final decision = switch (action) {
      EntityDecision.blacklist => 'blacklisted',
      EntityDecision.dismiss => 'dismissed',
      _ => c.decision,
    };
    _cases[caseId] = Case(
      caseId: c.caseId,
      clientId: c.clientId,
      customer: c.customer,
      assessment: c.assessment,
      evidence: c.evidence,
      sar: c.sar,
      reviewerActions: [
        ...c.reviewerActions,
        CaseAction(
          action: action,
          note: note,
          reviewer: reviewerName,
          at: DateTime.now().toUtc(),
        ),
      ],
      decision: decision,
    );
    _audit.insert(
        0,
        AuditEntry(
          logId: 'demo-al-${++_seq}',
          actor: 'human:$reviewerName',
          action: 'case_${action.toLowerCase()}',
          entityId: c.clientId,
          timestamp: DateTime.now().toUtc(),
          details: {'case_id': caseId, 'note': note},
        ));
    _bump();
  }

  @override
  Future<void> reviewSar({
    required String caseId,
    required String action,
    required String reviewerName,
    String note = '',
  }) async {
    final c = _cases[caseId];
    final sar = c?.sar;
    if (c == null || sar == null) return;
    final newStatus = action == SarDecision.approve ? 'approved' : 'denied';
    _cases[caseId] = Case(
      caseId: c.caseId,
      clientId: c.clientId,
      customer: c.customer,
      assessment: c.assessment,
      evidence: c.evidence,
      sar: Sar(
        caseId: sar.caseId,
        body: sar.body,
        citationCoverage: sar.citationCoverage,
        unverifiedClaims: sar.unverifiedClaims,
        status: newStatus,
      ),
      reviewerActions: c.reviewerActions,
      decision: c.decision,
    );
    _audit.insert(
        0,
        AuditEntry(
          logId: 'demo-al-${++_seq}',
          actor: 'human:$reviewerName',
          action: 'sar_$newStatus',
          entityId: c.clientId,
          timestamp: DateTime.now().toUtc(),
          details: {'case_id': caseId, 'note': note},
        ));
    _bump();
  }

  @override
  Future<List<Suppression>> fetchSuppressions() async =>
      [...DemoData.suppressions];

  @override
  Future<List<SarReport>> fetchReports() async {
    final out = <SarReport>[];
    for (final c in _cases.values) {
      final sar = c.sar;
      if (sar == null) continue;
      out.add(SarReport(
        clientId: c.clientId,
        caseId: c.caseId,
        name: c.customer.name,
        type: c.customer.type,
        tier: c.assessment.tier,
        sarStatus: sar.status,
        citationCoverage: sar.citationCoverage,
      ));
    }
    out.sort((a, b) => b.tier.rank.compareTo(a.tier.rank));
    return out;
  }

  @override
  Future<Metrics> fetchMetrics() async => DemoData.metrics;

  // Offline fixtures have no backend to run the scripted scenario against.
  @override
  Future<DemoStatus> fetchMode() async => DemoStatus.live;

  @override
  Future<DemoStatus> setMode(String mode) async => DemoStatus.live;

  @override
  Future<DemoStatus> timeSkip() async => DemoStatus.live;

  // Offline demo has no backend to send mail from — keep the recipient in
  // memory so the Settings screen still works, but sending is unavailable.
  String? _alertEmail;

  @override
  Future<AlertConfig> fetchAlertConfig() async =>
      AlertConfig(email: _alertEmail, smtpConfigured: false);

  @override
  Future<AlertConfig> setAlertEmail(String email) async {
    _alertEmail = email;
    return AlertConfig(email: email, smtpConfigured: false);
  }

  @override
  Future<void> sendTestAlert({String? email}) async => throw StateError(
      'Email alerts require the backend — not available in offline demo mode.');

  @override
  Future<void> replay({
    required DateTime from,
    required DateTime to,
    int speed = 1000,
  }) async {
    // Compress the window into a handful of ticks; each fires [changes] so the
    // dashboard re-fetches and appears to light up live. Higher speed → shorter
    // tick, floored so it stays visible.
    const ticks = 6;
    final ms = (2000 / (speed <= 0 ? 1 : speed) * 1000).round().clamp(120, 800);
    final step = Duration(milliseconds: ms);
    for (var i = 0; i < ticks; i++) {
      await Future.delayed(step);
      _bump();
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Providers
// ─────────────────────────────────────────────────────────────────────────────

/// Single repository for the app. Defaults to the live read API over ckyc.db;
/// `--dart-define=USE_DEMO_DATA=true` forces the bundled offline fixtures.
final repositoryProvider = Provider<KycRepository>((ref) {
  if (ApiConfig.useDemoData) return DemoRepository();
  final repo = ApiRepository();
  ref.onDispose(repo.dispose);
  return repo;
});

/// True when running on bundled demo data (surfaced in the UI as a banner).
final isDemoModeProvider = Provider<bool>((ref) => ApiConfig.useDemoData);

/// Fires whenever upstream data changes. Screens watch this to auto-refresh.
/// Carries the repository's revision counter — every event is a DISTINCT
/// AsyncData, so Riverpod re-notifies dependents on each one (a void stream
/// would dedupe to the first event and later writes would never refresh).
final changesProvider = StreamProvider<int>(
    (ref) => ref.watch(repositoryProvider).changes());

/// Watchlist, auto-refreshed on any change event.
final watchlistProvider = FutureProvider<List<EntityDetail>>((ref) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchWatchlist();
});

/// Full detail for one entity, auto-refreshed on change events.
final entityDetailProvider =
    FutureProvider.family<EntityDetail, String>((ref, id) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchDetail(id);
});

/// Audit trail (all, or scoped to an entity id), auto-refreshed on change.
final auditProvider =
    FutureProvider.family<List<AuditEntry>, String?>((ref, entityId) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchAudit(entityId: entityId);
});

// ── 05_SAMAKSH_ui.md six-screen providers ────────────────────────────────────

/// Screen 1 — alert queue (unfiltered; the UI sorts/filters client-side).
final alertsProvider = FutureProvider<List<Alert>>((ref) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchAlerts();
});

/// Screen 2 — Entity 360 for one client.
final entity360Provider =
    FutureProvider.family<Entity360, String>((ref, clientId) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchEntity360(clientId);
});

/// Screen 3 — risk timeline for one client.
final entityTimelineProvider =
    FutureProvider.family<List<TimelineEvent>, String>((ref, clientId) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchEntityTimeline(clientId);
});

/// Screen 4 + 6 — full case (evidence + SAR + reviewer actions).
final caseProvider =
    FutureProvider.family<Case, String>((ref, caseId) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchCase(caseId);
});

/// Screen 4 + 6 — the case for a client id (drill-down from the alert queue),
/// null when nothing has been filed on that client yet.
final caseByClientProvider =
    FutureProvider.family<Case?, String>((ref, clientId) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchCaseByClient(clientId);
});

/// Screen 5 — suppression log.
final suppressionsProvider = FutureProvider<List<Suppression>>((ref) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchSuppressions();
});

/// Reports tab — cases with a drafted SAR, auto-refreshed on change events.
final reportsProvider = FutureProvider<List<SarReport>>((ref) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchReports();
});

/// Before/after toggle metrics.
final metricsProvider = FutureProvider<Metrics>((ref) async {
  return ref.watch(repositoryProvider).fetchMetrics();
});

/// Risk-alert email config (Settings screen) — recipient + SMTP availability.
final alertConfigProvider = FutureProvider<AlertConfig>((ref) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchAlertConfig();
});

/// Live/test mode + scenario phase. Re-fetched on every change event so the
/// mode toggle and the time-skip button stay in sync after scenario runs.
final demoStatusProvider = FutureProvider<DemoStatus>((ref) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchMode();
});
