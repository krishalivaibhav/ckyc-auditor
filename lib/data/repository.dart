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
  Stream<void> changes();

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
  });

  /// Screen 5 — the suppression log (alerts we did NOT raise, and why).
  Future<List<Suppression>> fetchSuppressions();

  /// Before/after toggle — precision/recall, naive screening vs our system.
  Future<Metrics> fetchMetrics();

  /// Temporal replay control — streams the window from→to at [speed], firing
  /// [changes] so the dashboard lights up live.
  Future<void> replay({
    required DateTime from,
    required DateTime to,
    int speed = 1000,
  });
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
  // No server push yet; the stream stays open but never emits, so change-aware
  // providers simply load once. Replay/Realtime plug in here later.
  final _changes = StreamController<void>.broadcast();

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

  @override
  Stream<void> changes() => _changes.stream;

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
  Future<Metrics> fetchMetrics() async {
    final j = await _get('/api/metrics') as Map<String, dynamic>;
    return Metrics.fromJson(j);
  }

  // ── writes — deferred to the UI phase (read-only for now) ─────────────────
  static Never _readOnly(String what) => throw UnimplementedError(
      '$what is a write — not wired yet. The read-only phase serves GETs from '
      'ckyc.db; reviewer writes POST to the API in the UI rewire.');

  @override
  Future<void> reviewCase({
    required String caseId,
    required String action,
    required String note,
    required String reviewerName,
  }) =>
      _readOnly('reviewCase');

  @override
  Future<void> reviewSar({
    required String caseId,
    required String action,
    required String reviewerName,
  }) =>
      _readOnly('reviewSar');

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
  final _changes = StreamController<void>.broadcast();
  late final List<Entity> _entities = [...DemoData.entities];
  late final List<DraftReport> _reports = [...DemoData.reports];
  late final List<AuditEntry> _audit = [...DemoData.audit];
  // 05_SAMAKSH_ui.md contract — mutable so reviewCase/approveSar can update them.
  late final Map<String, Case> _cases = {...DemoData.cases};
  var _seq = 0;

  @override
  Stream<void> changes() => _changes.stream;

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
    _changes.add(null);
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
    _changes.add(null);
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
    _changes.add(null);
  }

  @override
  Future<void> reviewSar({
    required String caseId,
    required String action,
    required String reviewerName,
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
          details: {'case_id': caseId},
        ));
    _changes.add(null);
  }

  @override
  Future<List<Suppression>> fetchSuppressions() async =>
      [...DemoData.suppressions];

  @override
  Future<Metrics> fetchMetrics() async => DemoData.metrics;

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
      _changes.add(null);
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

/// Fires whenever upstream data changes. Screens watch this to auto-refresh —
/// the live seam for server push/replay (currently inert; loads once).
final changesProvider = StreamProvider<void>(
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

/// Screen 5 — suppression log.
final suppressionsProvider = FutureProvider<List<Suppression>>((ref) async {
  ref.watch(changesProvider);
  return ref.watch(repositoryProvider).fetchSuppressions();
});

/// Before/after toggle metrics.
final metricsProvider = FutureProvider<Metrics>((ref) async {
  return ref.watch(repositoryProvider).fetchMetrics();
});
