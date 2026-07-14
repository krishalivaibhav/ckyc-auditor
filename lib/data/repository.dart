import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/supabase.dart';
import '../models/models.dart';
import 'demo_data.dart';

/// Data access for the dashboard. Two implementations behind one interface:
///  - [SupabaseRepository]  → live Postgres (Persons 1–4 write here).
///  - [DemoRepository]      → bundled seed data, offline-safe fallback.
abstract class KycRepository {
  /// Watchlist rows: entity + its verdict + risk events (for the severity badge).
  Future<List<EntityDetail>> fetchWatchlist();

  /// Full detail for one entity: verdict, risk events, evidence timeline, report.
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
}

// ─────────────────────────────────────────────────────────────────────────────
// Supabase-backed implementation
// ─────────────────────────────────────────────────────────────────────────────
class SupabaseRepository implements KycRepository {
  final SupabaseClient _db;
  final _changes = StreamController<void>.broadcast();
  RealtimeChannel? _channel;

  SupabaseRepository(this._db) {
    _subscribe();
  }

  void _subscribe() {
    _channel = _db.channel('kyc-changes')
      ..onPostgresChanges(
        event: PostgresChangeEvent.all,
        schema: 'public',
        table: 'risk_events',
        callback: (_) => _changes.add(null),
      )
      ..onPostgresChanges(
        event: PostgresChangeEvent.all,
        schema: 'public',
        table: 'entities',
        callback: (_) => _changes.add(null),
      )
      ..onPostgresChanges(
        event: PostgresChangeEvent.all,
        schema: 'public',
        table: 'resolution_verdicts',
        callback: (_) => _changes.add(null),
      )
      ..subscribe();
  }

  @override
  Stream<void> changes() => _changes.stream;

  /// Tear down the realtime subscription (called from the provider's onDispose).
  Future<void> dispose() async {
    final channel = _channel;
    if (channel != null) await _db.removeChannel(channel);
    await _changes.close();
  }

  @override
  Future<List<EntityDetail>> fetchWatchlist() async {
    final entities = (await _db.from('entities').select().order('created_at'))
        .map((e) => Entity.fromJson(e))
        .toList();
    final verdicts = (await _db.from('resolution_verdicts').select())
        .map((v) => ResolutionVerdict.fromJson(v))
        .toList();
    final events = (await _db.from('risk_events').select())
        .map((r) => RiskEvent.fromJson(r))
        .toList();

    return entities.map((e) {
      final v = verdicts.where((x) => x.queryEntityId == e.entityId);
      final ev = events.where((x) => x.entityId == e.entityId).toList();
      return EntityDetail(
        entity: e,
        verdict: v.isEmpty ? null : v.first,
        riskEvents: ev,
      );
    }).toList();
  }

  @override
  Future<EntityDetail> fetchDetail(String entityId) async {
    final e = Entity.fromJson(
        await _db.from('entities').select().eq('entity_id', entityId).single());
    final verdicts = await _db
        .from('resolution_verdicts')
        .select()
        .eq('query_entity_id', entityId)
        .order('resolved_at', ascending: false);
    final events = await _db
        .from('risk_events')
        .select()
        .eq('entity_id', entityId)
        .order('detected_at', ascending: false);
    final evidence = await _db
        .from('evidence')
        .select()
        .eq('entity_id', entityId)
        .order('event_date', ascending: false);
    final reports = await _db
        .from('draft_reports')
        .select('*, report_citations(*)')
        .eq('entity_id', entityId)
        .order('created_at', ascending: false)
        .limit(1);

    return EntityDetail(
      entity: e,
      verdict: verdicts.isEmpty
          ? null
          : ResolutionVerdict.fromJson(verdicts.first),
      riskEvents: events.map((r) => RiskEvent.fromJson(r)).toList(),
      evidence: evidence.map((r) => Evidence.fromJson(r)).toList(),
      report: reports.isEmpty ? null : DraftReport.fromJson(reports.first),
    );
  }

  @override
  Future<List<AuditEntry>> fetchAudit({String? entityId}) async {
    var q = _db.from('audit_log').select();
    if (entityId != null) q = q.eq('entity_id', entityId);
    final rows = await q.order('timestamp', ascending: false).limit(200);
    return rows.map((r) => AuditEntry.fromJson(r)).toList();
  }

  @override
  Future<Entity> ingestEntity(Entity draft) async {
    final row = await _db
        .from('entities')
        .insert(draft.toInsertJson())
        .select()
        .single();
    return Entity.fromJson(row);
  }

  @override
  Future<void> reviewReport({
    required String reportId,
    required String action,
    required String reviewerName,
    String? editedSummary,
  }) async {
    await _db.rpc('review_report', params: {
      'p_report_id': reportId,
      'p_action': action,
      'p_reviewer_name': reviewerName,
      'p_edited_summary': editedSummary,
    });
    _changes.add(null);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Demo (offline) implementation — mutates in-memory copies of the seed data
// ─────────────────────────────────────────────────────────────────────────────
class DemoRepository implements KycRepository {
  final _changes = StreamController<void>.broadcast();
  late final List<Entity> _entities = [...DemoData.entities];
  late final List<DraftReport> _reports = [...DemoData.reports];
  late final List<AuditEntry> _audit = [...DemoData.audit];
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
      evidence: (DemoData.evidence.where((x) => x.entityId == entityId))
          .toList()
        ..sort((a, b) => b.eventDate.compareTo(a.eventDate)),
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
}

// ─────────────────────────────────────────────────────────────────────────────
// Providers
// ─────────────────────────────────────────────────────────────────────────────

/// Single repository for the app, chosen by whether Supabase is configured.
final repositoryProvider = Provider<KycRepository>((ref) {
  if (SupabaseConfig.isConfigured) {
    final repo = SupabaseRepository(supabase);
    ref.onDispose(repo.dispose);
    return repo;
  }
  return DemoRepository();
});

/// True when running on bundled demo data (surfaced in the UI as a banner).
final isDemoModeProvider =
    Provider<bool>((ref) => !SupabaseConfig.isConfigured);

/// Fires whenever upstream data changes (Realtime in Supabase mode). Screens
/// watch this to auto-refresh — this is the live seam Persons 1–4 plug into.
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
