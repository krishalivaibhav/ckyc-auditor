import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/breakpoints.dart';
import '../../data/repository.dart';
import '../../models/models.dart';
import '../../widgets/decision_dialog.dart';
import '../auth/session.dart';

/// Case detail (Screen 2 + 3 + 4). Everything the pipeline persisted for one
/// client, drilled into from the alert queue:
///   • Entity 360   — customer ←→ matched watchlist entry + risk assessment
///   • Risk timeline — dated tier moves (escalation AND de-escalation)
///   • Evidence      — the three columns confirmed / correlated / missing
/// and a link into the SAR the investigation agent drafted.
///
/// Reads live from ckyc.db via entity360 / timeline / case-by-client. The old
/// schema.md severity/verdict model is gone.
class EntityDetailScreen extends ConsumerWidget {
  final String clientId;
  const EntityDetailScreen({super.key, required this.clientId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final e360 = ref.watch(entity360Provider(clientId));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Case detail',
            style: TextStyle(fontWeight: FontWeight.w600)),
        centerTitle: true,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () =>
              context.canPop() ? context.pop() : context.go('/entities'),
        ),
        actions: const [_TimeSkipButton(), SizedBox(width: 12)],
      ),
      body: e360.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => _ErrorView(message: '$err'),
        data: (data) => _Detail(clientId: clientId, e360: data),
      ),
    );
  }
}

/// TEST-mode only: advance the scripted scenario +15 months — the real-world
/// gap between the first adverse-media report and the sanction. The backend
/// terminal narrates the news + sanctions agents firing; when the call returns
/// the timeline, evidence and SAR re-read from the updated demo sink.
class _TimeSkipButton extends ConsumerStatefulWidget {
  const _TimeSkipButton();

  @override
  ConsumerState<_TimeSkipButton> createState() => _TimeSkipButtonState();
}

class _TimeSkipButtonState extends ConsumerState<_TimeSkipButton> {
  bool _busy = false;

  Future<void> _skip() async {
    if (_busy) return;
    setState(() => _busy = true);
    final messenger = ScaffoldMessenger.of(context);
    messenger.showSnackBar(const SnackBar(
        duration: Duration(seconds: 6),
        content: Text('Skipping 15 months — watch the backend terminal: '
            'two more articles land, then the SEBI sanction…')));
    try {
      await ref.read(repositoryProvider).timeSkip();
      if (mounted) {
        messenger.showSnackBar(const SnackBar(
            content: Text('15 months later: sanction imposed — case '
                'escalated to CRITICAL, SAR ready for download')));
      }
    } catch (e) {
      if (mounted) {
        messenger
            .showSnackBar(SnackBar(content: Text('Time skip failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final status = ref.watch(demoStatusProvider).maybeWhen(
        data: (s) => s, orElse: () => DemoStatus.live);
    if (!status.canTimeSkip) return const SizedBox.shrink();
    const color = Color(0xFFF59E0B);
    return Center(
      child: _busy
          ? const Padding(
              padding: EdgeInsets.symmetric(horizontal: 20),
              child: SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2)),
            )
          : FilledButton.tonalIcon(
              style: FilledButton.styleFrom(
                backgroundColor: color.withValues(alpha: 0.15),
                foregroundColor: color,
              ),
              onPressed: _skip,
              icon: const Icon(Icons.fast_forward, size: 18),
              label: const Text('Time skip +15 months',
                  style: TextStyle(fontWeight: FontWeight.w700)),
            ),
    );
  }
}

// ── formatting helpers ───────────────────────────────────────────────────────

String _inr(double v) {
  if (v <= 0) return '—';
  if (v >= 1e7) {
    final cr = v / 1e7;
    return '₹${cr.toStringAsFixed(cr % 1 == 0 ? 0 : 2)} Cr';
  }
  if (v >= 1e5) {
    final l = v / 1e5;
    return '₹${l.toStringAsFixed(l % 1 == 0 ? 0 : 2)} L';
  }
  return '₹${v.toStringAsFixed(0)}';
}

Color tierColor(RiskTier t) => switch (t) {
      RiskTier.critical => const Color(0xFFDC2626),
      RiskTier.high => const Color(0xFFEA580C),
      RiskTier.edd => const Color(0xFFF59E0B),
      RiskTier.eddLite => const Color(0xFF3B82F6),
      RiskTier.monitor => const Color(0xFF10B981),
      RiskTier.unknown => const Color(0xFF6B7280),
    };

// ── layout ───────────────────────────────────────────────────────────────────

class _Detail extends ConsumerWidget {
  final String clientId;
  final Entity360 e360;
  const _Detail({required this.clientId, required this.e360});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = Breakpoints.isWide(context);
    final timelineAsync = ref.watch(entityTimelineProvider(clientId));
    final caseAsync = ref.watch(caseByClientProvider(clientId));

    final identity = _IdentityPanel(e360: e360);
    final timeline = _TimelinePanel(async: timelineAsync);
    final evidence = _EvidencePanel(async: caseAsync);
    final sar = _SarPanel(clientId: clientId, async: caseAsync);
    final decision = _DecisionPanel(async: caseAsync);

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 40),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1400),
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.0, end: 1.0),
            duration: const Duration(milliseconds: 500),
            curve: Curves.easeOutCubic,
            builder: (context, value, child) => Opacity(
              opacity: value,
              child: Transform.translate(
                  offset: Offset(0, 16 * (1 - value)), child: child),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _Header(e360: e360),
                const SizedBox(height: 32),
                identity,
                const SizedBox(height: 28),
                wide
                    ? Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 5, child: timeline),
                          const SizedBox(width: 28),
                          Expanded(flex: 6, child: evidence),
                        ],
                      )
                    : Column(children: [
                        timeline,
                        const SizedBox(height: 28),
                        evidence,
                      ]),
                const SizedBox(height: 28),
                sar,
                const SizedBox(height: 28),
                decision,
                const SizedBox(height: 48),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

// ── reviewer decision (blacklist / dismiss) ──────────────────────────────────

class _DecisionPanel extends ConsumerWidget {
  final AsyncValue<Case?> async;
  const _DecisionPanel({required this.async});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return async.maybeWhen(
      orElse: () => const SizedBox.shrink(),
      data: (c) {
        if (c == null) return const SizedBox.shrink();
        return _Panel(
          title: 'Reviewer decision',
          icon: Icons.gavel_outlined,
          trailing: c.decision == null
              ? null
              : _DecisionPill(decision: c.decision!),
          child: c.decision != null
              ? _decided(context, c)
              : _actions(context, ref, c),
        );
      },
    );
  }

  Widget _decided(BuildContext context, Case c) {
    final scheme = Theme.of(context).colorScheme;
    final last = c.reviewerActions.isEmpty ? null : c.reviewerActions.last;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
            c.isBlacklisted
                ? 'This entity has been blacklisted. It is retained for filing '
                    'and cannot be dismissed here.'
                : 'This case has been dismissed as a false positive.',
            style: TextStyle(color: scheme.onSurfaceVariant, height: 1.5)),
        if (last != null) ...[
          const SizedBox(height: 10),
          Text('by ${last.reviewer}${last.note.isEmpty ? '' : ' — “${last.note}”'}',
              style: TextStyle(
                  fontSize: 12.5,
                  fontStyle: FontStyle.italic,
                  color: scheme.onSurfaceVariant)),
        ],
      ],
    );
  }

  Widget _actions(BuildContext context, WidgetRef ref, Case c) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
            'Record the terminal decision on this entity. The action is written '
            'to the append-only audit trail under your reviewer name.',
            style: TextStyle(color: scheme.onSurfaceVariant, height: 1.5)),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            FilledButton.icon(
              onPressed: () => _review(context, ref, c, EntityDecision.blacklist),
              style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFFDC2626)),
              icon: const Icon(Icons.block, size: 18),
              label: const Text('Blacklist entity'),
            ),
            OutlinedButton.icon(
              onPressed: () => _review(context, ref, c, EntityDecision.dismiss),
              icon: const Icon(Icons.close, size: 18),
              label: const Text('Dismiss as false positive'),
            ),
          ],
        ),
      ],
    );
  }

  Future<void> _review(
      BuildContext context, WidgetRef ref, Case c, String action) async {
    final blacklist = action == EntityDecision.blacklist;
    final note = await promptDecision(
      context,
      title: blacklist ? 'Blacklist entity' : 'Dismiss case',
      message: blacklist
          ? 'Confirm this entity is a true match and should be blacklisted.'
          : 'Confirm this alert is a false positive and can be dismissed.',
      confirmLabel: blacklist ? 'Blacklist' : 'Dismiss',
      danger: blacklist,
    );
    if (note == null) return; // cancelled
    final reviewer = ref.read(sessionProvider).reviewerName ?? 'unknown';
    try {
      await ref.read(repositoryProvider).reviewCase(
            caseId: c.caseId,
            action: action,
            note: note,
            reviewerName: reviewer,
          );
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(
                '${blacklist ? 'Blacklisted' : 'Dismissed'} · logged as human:$reviewer')));
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Action failed: $e')));
      }
    }
  }
}

class _DecisionPill extends StatelessWidget {
  final String decision;
  const _DecisionPill({required this.decision});
  @override
  Widget build(BuildContext context) {
    final blacklisted = decision == 'blacklisted';
    final color =
        blacklisted ? const Color(0xFFDC2626) : const Color(0xFF6B7280);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(blacklisted ? 'Blacklisted' : 'Dismissed',
          style: TextStyle(
              fontSize: 12.5, fontWeight: FontWeight.w700, color: color)),
    );
  }
}

class _Header extends StatelessWidget {
  final Entity360 e360;
  const _Header({required this.e360});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final c = e360.customer;
    final a = e360.assessment;
    final tc = tierColor(a.tier);
    final isCompany = c.type.toLowerCase() == 'company';

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        CircleAvatar(
          radius: 36,
          backgroundColor: scheme.secondaryContainer,
          child: Icon(isCompany ? Icons.business : Icons.person_outline,
              color: scheme.onSecondaryContainer, size: 32),
        ),
        const SizedBox(width: 20),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(c.name,
                  style: Theme.of(context)
                      .textTheme
                      .headlineMedium
                      ?.copyWith(fontWeight: FontWeight.w800, height: 1.2)),
              const SizedBox(height: 6),
              Wrap(spacing: 10, runSpacing: 6, children: [
                _MetaChip(icon: Icons.badge_outlined, label: c.type),
                if (c.city != null)
                  _MetaChip(icon: Icons.place_outlined, label: c.city!),
                _MetaChip(
                    icon: Icons.tag,
                    label: c.pan == null ? 'No PAN on file' : 'PAN ${c.pan}'),
              ]),
            ],
          ),
        ),
        const SizedBox(width: 24),
        _ScoreBlock(tier: a.tier, score: a.score, exposure: a.exposureInr,
            color: tc),
      ],
    );
  }
}

class _ScoreBlock extends StatelessWidget {
  final RiskTier tier;
  final double score;
  final double exposure;
  final Color color;
  const _ScoreBlock(
      {required this.tier,
      required this.score,
      required this.exposure,
      required this.color});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            Container(
                width: 10,
                height: 10,
                decoration:
                    BoxDecoration(shape: BoxShape.circle, color: color)),
            const SizedBox(width: 8),
            Text(tier.label,
                style: TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w800, color: color)),
          ]),
          const SizedBox(height: 6),
          Text('score ${(score * 100).round()} · exposure ${_inr(exposure)}',
              style: TextStyle(fontSize: 12.5, color: scheme.onSurfaceVariant)),
        ],
      ),
    );
  }
}

// ── identity resolution (Entity 360) ─────────────────────────────────────────

class _IdentityPanel extends StatelessWidget {
  final Entity360 e360;
  const _IdentityPanel({required this.e360});

  @override
  Widget build(BuildContext context) {
    final cand = e360.candidate;
    final a = e360.assessment;
    final wide = Breakpoints.isWide(context);

    final customerCard = _SideCard(
      title: 'OUR CUSTOMER',
      accent: Theme.of(context).colorScheme.primary,
      rows: [
        ('Name', e360.customer.name),
        ('Type', e360.customer.type),
        ('PAN', e360.customer.pan ?? '—'),
        if (e360.customer.city != null) ('Branch', e360.customer.city!),
      ],
    );

    return _Panel(
      title: 'Identity resolution',
      icon: Icons.compare_arrows,
      trailing: cand == null
          ? null
          : _VerdictPill(rejected: cand.rejected),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (cand == null)
            _emptyMatch(context)
          else
            wide
                ? IntrinsicHeight(
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Expanded(child: customerCard),
                        const _Connector(),
                        Expanded(child: _matchCard(context, cand)),
                      ],
                    ),
                  )
                : Column(children: [
                    customerCard,
                    const SizedBox(height: 12),
                    _matchCard(context, cand),
                  ]),
          if (cand != null && cand.rejectionReason != null) ...[
            const SizedBox(height: 16),
            _ReasonBox(
                color: const Color(0xFF10B981),
                icon: Icons.shield_outlined,
                title: 'Suppressed — not raised as an alert',
                body: cand.rejectionReason!),
          ],
          if (a.gatesFired.isNotEmpty) ...[
            const SizedBox(height: 16),
            _Chips(label: 'Gates fired', items: a.gatesFired, color: tierColor(a.tier)),
          ],
        ],
      ),
    );
  }

  Widget _matchCard(BuildContext context, Candidate cand) => _SideCard(
        title: 'WATCHLIST MATCH · ${cand.listName}',
        accent: cand.rejected
            ? const Color(0xFF10B981)
            : const Color(0xFFDC2626),
        rows: [
          ('Name', cand.matchedName),
          ('Type', cand.matchedType),
          ('PAN', cand.matchedPan ?? '—'),
          ('Method', cand.matchMethod),
          ('Confidence', '${(cand.confidence * 100).round()}%'),
        ],
      );

  Widget _emptyMatch(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 24),
      child: Row(children: [
        Icon(Icons.search_off, color: scheme.onSurfaceVariant),
        const SizedBox(width: 12),
        Expanded(
            child: Text(
                'No watchlist candidate anchored this assessment.',
                style: TextStyle(color: scheme.onSurfaceVariant))),
      ]),
    );
  }
}

class _SideCard extends StatelessWidget {
  final String title;
  final Color accent;
  final List<(String, String)> rows;
  const _SideCard(
      {required this.title, required this.accent, required this.rows});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: accent.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                  fontSize: 11.5,
                  letterSpacing: 1.0,
                  fontWeight: FontWeight.w800,
                  color: accent)),
          const SizedBox(height: 12),
          for (final r in rows)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                      width: 92,
                      child: Text(r.$1,
                          style: TextStyle(
                              fontSize: 13, color: scheme.onSurfaceVariant))),
                  Expanded(
                      child: Text(r.$2,
                          style: const TextStyle(
                              fontSize: 13.5, fontWeight: FontWeight.w600))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _Connector extends StatelessWidget {
  const _Connector();
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: 44,
      alignment: Alignment.center,
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
            shape: BoxShape.circle, color: scheme.surfaceContainerHighest),
        child: Icon(Icons.sync_alt, size: 18, color: scheme.onSurfaceVariant),
      ),
    );
  }
}

class _VerdictPill extends StatelessWidget {
  final bool rejected;
  const _VerdictPill({required this.rejected});
  @override
  Widget build(BuildContext context) {
    final color =
        rejected ? const Color(0xFF10B981) : const Color(0xFFDC2626);
    final label = rejected ? 'Suppressed' : 'Confirmed match';
    final icon = rejected ? Icons.block : Icons.gpp_maybe;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 15, color: color),
        const SizedBox(width: 6),
        Text(label,
            style: TextStyle(
                fontSize: 12.5, fontWeight: FontWeight.w700, color: color)),
      ]),
    );
  }
}

// ── risk timeline ────────────────────────────────────────────────────────────

class _TimelinePanel extends StatelessWidget {
  final AsyncValue<List<TimelineEvent>> async;
  const _TimelinePanel({required this.async});

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Risk timeline',
      icon: Icons.timeline,
      child: async.when(
        loading: () => const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator())),
        error: (e, _) => Text('$e'),
        data: (events) {
          if (events.isEmpty) {
            return _empty(context, 'No risk events recorded yet.');
          }
          final ordered = [...events]..sort((a, b) => b.date.compareTo(a.date));
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              for (var i = 0; i < ordered.length; i++)
                _TimelineRow(e: ordered[i], isLast: i == ordered.length - 1),
            ],
          );
        },
      ),
    );
  }
}

class _TimelineRow extends StatelessWidget {
  final TimelineEvent e;
  final bool isLast;
  const _TimelineRow({required this.e, required this.isLast});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final moved = e.tierAfter != e.tierBefore;
    final dot = moved ? tierColor(e.tierAfter) : scheme.outline;

    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(children: [
            Container(
              width: 14,
              height: 14,
              margin: const EdgeInsets.only(top: 4),
              decoration: BoxDecoration(
                color: dot,
                shape: BoxShape.circle,
                border: Border.all(color: scheme.surface, width: 3),
              ),
            ),
            if (!isLast)
              Expanded(
                  child: Container(
                      width: 2,
                      color: scheme.outlineVariant.withValues(alpha: 0.4))),
          ]),
          const SizedBox(width: 16),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(DateFormat('d MMM yyyy, HH:mm').format(e.date.toLocal()),
                      style: TextStyle(
                          fontSize: 12,
                          color: scheme.onSurfaceVariant,
                          fontWeight: FontWeight.w600)),
                  const SizedBox(height: 4),
                  Text(e.event,
                      style: const TextStyle(
                          fontSize: 14.5, fontWeight: FontWeight.w600,
                          height: 1.4)),
                  if (moved) ...[
                    const SizedBox(height: 8),
                    _TierMove(before: e.tierBefore, after: e.tierAfter,
                        deescalation: e.isDeescalation),
                  ],
                  if (e.evidenceRefs.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        for (final ref in e.evidenceRefs) _EvChip(ref: ref),
                      ],
                    ),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _TierMove extends StatelessWidget {
  final RiskTier before;
  final RiskTier after;
  final bool deescalation;
  const _TierMove(
      {required this.before, required this.after, required this.deescalation});

  @override
  Widget build(BuildContext context) {
    final color = deescalation ? const Color(0xFF10B981) : tierColor(after);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text(before.label,
            style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600)),
        const SizedBox(width: 6),
        Icon(deescalation ? Icons.south_east : Icons.north_east,
            size: 14, color: color),
        const SizedBox(width: 6),
        Text(after.label,
            style: TextStyle(
                fontSize: 12, color: color, fontWeight: FontWeight.w800)),
      ]),
    );
  }
}

class _EvChip extends StatelessWidget {
  final String ref;
  const _EvChip({required this.ref});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: scheme.primary.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(ref,
          style: TextStyle(
              fontSize: 11.5,
              fontWeight: FontWeight.w700,
              fontFeatures: const [],
              color: scheme.primary)),
    );
  }
}

// ── evidence three columns ───────────────────────────────────────────────────

class _EvidencePanel extends StatelessWidget {
  final AsyncValue<Case?> async;
  const _EvidencePanel({required this.async});

  @override
  Widget build(BuildContext context) {
    return _Panel(
      title: 'Evidence',
      icon: Icons.fact_check_outlined,
      child: async.when(
        loading: () => const Padding(
            padding: EdgeInsets.all(24),
            child: Center(child: CircularProgressIndicator())),
        error: (e, _) => Text('$e'),
        data: (c) {
          final ev = c?.evidence ?? const <Evidence>[];
          if (ev.isEmpty) {
            return _empty(context, 'No evidence chain recorded yet.');
          }
          Widget col(EvidenceColumn column) => _EvidenceColumn(
              column: column,
              items: ev.where((e) => e.column == column).toList());
          final wide = Breakpoints.isWide(context);
          return wide
              ? IntrinsicHeight(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: col(EvidenceColumn.confirmed)),
                      const SizedBox(width: 12),
                      Expanded(child: col(EvidenceColumn.correlated)),
                      const SizedBox(width: 12),
                      Expanded(child: col(EvidenceColumn.missing)),
                    ],
                  ),
                )
              : Column(children: [
                  col(EvidenceColumn.confirmed),
                  const SizedBox(height: 12),
                  col(EvidenceColumn.correlated),
                  const SizedBox(height: 12),
                  col(EvidenceColumn.missing),
                ]);
        },
      ),
    );
  }
}

class _EvidenceColumn extends StatelessWidget {
  final EvidenceColumn column;
  final List<Evidence> items;
  const _EvidenceColumn({required this.column, required this.items});

  (String, Color, IconData) get _meta => switch (column) {
        EvidenceColumn.confirmed =>
          ('Confirmed', const Color(0xFF10B981), Icons.verified),
        EvidenceColumn.correlated =>
          ('Correlated', const Color(0xFFF59E0B), Icons.link),
        EvidenceColumn.missing =>
          ('Missing', const Color(0xFF6B7280), Icons.help_outline),
      };

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (label, color, icon) = _meta;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(icon, size: 15, color: color),
            const SizedBox(width: 6),
            Text('$label · ${items.length}',
                style: TextStyle(
                    fontSize: 12.5, fontWeight: FontWeight.w800, color: color)),
          ]),
          const SizedBox(height: 10),
          if (items.isEmpty)
            Text('—',
                style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 13))
          else
            for (final e in items) _EvidenceCard(e: e, accent: color),
        ],
      ),
    );
  }
}

class _EvidenceCard extends StatelessWidget {
  final Evidence e;
  final Color accent;
  const _EvidenceCard({required this.e, required this.accent});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(5)),
              child: Text(e.evId,
                  style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: accent)),
            ),
            const Spacer(),
            if (e.confidence != null)
              Text('${(e.confidence! * 100).round()}%',
                  style: TextStyle(
                      fontSize: 11.5, color: scheme.onSurfaceVariant)),
          ]),
          const SizedBox(height: 8),
          Text(e.claim,
              style: const TextStyle(fontSize: 13, height: 1.4)),
          if (e.excerpt != null) ...[
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(6),
                border: Border(left: BorderSide(color: accent, width: 2.5)),
              ),
              child: Text('“${e.excerpt}”',
                  style: TextStyle(
                      fontSize: 12,
                      fontStyle: FontStyle.italic,
                      color: scheme.onSurfaceVariant)),
            ),
          ],
          if (e.sourceName != null || e.sourceUrl != null) ...[
            const SizedBox(height: 8),
            _SourceRow(name: e.sourceName, url: e.sourceUrl),
          ],
        ],
      ),
    );
  }
}

class _SourceRow extends StatelessWidget {
  final String? name;
  final String? url;
  const _SourceRow({this.name, this.url});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final label = name ?? url ?? '';
    final hasLink = url != null && url!.startsWith('http');
    final child = Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(hasLink ? Icons.open_in_new : Icons.source_outlined,
          size: 12,
          color: hasLink ? scheme.primary : scheme.onSurfaceVariant),
      const SizedBox(width: 4),
      Flexible(
        child: Text(label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
                fontSize: 11.5,
                color: hasLink ? scheme.primary : scheme.onSurfaceVariant,
                decoration:
                    hasLink ? TextDecoration.underline : TextDecoration.none)),
      ),
    ]);
    if (!hasLink) return child;
    return InkWell(
      onTap: () =>
          launchUrl(Uri.parse(url!), mode: LaunchMode.externalApplication),
      child: child,
    );
  }
}

// ── SAR link ─────────────────────────────────────────────────────────────────

class _SarPanel extends StatelessWidget {
  final String clientId;
  final AsyncValue<Case?> async;
  const _SarPanel({required this.clientId, required this.async});

  @override
  Widget build(BuildContext context) {
    return async.maybeWhen(
      orElse: () => const SizedBox.shrink(),
      data: (c) {
        final sar = c?.sar;
        if (sar == null) return const SizedBox.shrink();
        final scheme = Theme.of(context).colorScheme;
        return _Panel(
          title: 'Suspicious Activity Report',
          icon: Icons.description_outlined,
          trailing: _SarStatusPill(status: sar.status),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                  'The investigation agent drafted a SAR with '
                  '${(sar.citationCoverage * 100).round()}% of its claims cited '
                  'to evidence.',
                  style: TextStyle(color: scheme.onSurfaceVariant, height: 1.5)),
              const SizedBox(height: 16),
              SizedBox(
                height: 52,
                child: FilledButton.tonalIcon(
                  style: FilledButton.styleFrom(
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12))),
                  onPressed: () =>
                      context.push('/entities/$clientId/report'),
                  icon: const Icon(Icons.article_outlined),
                  label: const Text('View full SAR draft',
                      style: TextStyle(
                          fontSize: 15, fontWeight: FontWeight.w700)),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _SarStatusPill extends StatelessWidget {
  final String status;
  const _SarStatusPill({required this.status});
  @override
  Widget build(BuildContext context) {
    final (color, label) = switch (status) {
      'approved' => (const Color(0xFF10B981), 'Approved'),
      'denied' => (const Color(0xFFDC2626), 'Denied'),
      _ => (Theme.of(context).colorScheme.primary, 'Draft'),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(label,
          style: TextStyle(
              fontSize: 12.5, fontWeight: FontWeight.w700, color: color)),
    );
  }
}

// ── shared bits ──────────────────────────────────────────────────────────────

Widget _empty(BuildContext context, String msg) => Padding(
      padding: const EdgeInsets.symmetric(vertical: 28),
      child: Center(
        child: Text(msg,
            style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontSize: 14)),
      ),
    );

class _Chips extends StatelessWidget {
  final String label;
  final List<String> items;
  final Color color;
  const _Chips({required this.label, required this.items, required this.color});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label.toUpperCase(),
            style: TextStyle(
                fontSize: 11,
                letterSpacing: 0.8,
                fontWeight: FontWeight.w700,
                color: scheme.onSurfaceVariant)),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final it in items)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: color.withValues(alpha: 0.3)),
                ),
                child: Text(it,
                    style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: color)),
              ),
          ],
        ),
      ],
    );
  }
}

class _ReasonBox extends StatelessWidget {
  final Color color;
  final IconData icon;
  final String title;
  final String body;
  const _ReasonBox(
      {required this.color,
      required this.icon,
      required this.title,
      required this.body});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: color),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title,
                    style: TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w800,
                        color: color)),
                const SizedBox(height: 4),
                Text(body,
                    style: const TextStyle(fontSize: 13, height: 1.5)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  final IconData icon;
  final String label;
  const _MetaChip({required this.icon, required this.label});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 14, color: scheme.onSurfaceVariant),
        const SizedBox(width: 6),
        Text(label,
            style: TextStyle(
                fontSize: 12.5,
                fontWeight: FontWeight.w600,
                color: scheme.onSurfaceVariant)),
      ]),
    );
  }
}

class _Panel extends StatelessWidget {
  final String title;
  final IconData icon;
  final Widget child;
  final Widget? trailing;
  const _Panel(
      {required this.title,
      required this.icon,
      required this.child,
      this.trailing});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF16161A) : Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.25)),
        boxShadow: [
          BoxShadow(
              color: scheme.shadow.withValues(alpha: 0.04),
              blurRadius: 16,
              offset: const Offset(0, 6)),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 16),
            decoration: BoxDecoration(
              border: Border(
                  bottom: BorderSide(
                      color: scheme.outlineVariant.withValues(alpha: 0.2))),
            ),
            child: Row(children: [
              Icon(icon, size: 19, color: scheme.primary),
              const SizedBox(width: 10),
              Text(title.toUpperCase(),
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: scheme.onSurfaceVariant,
                      letterSpacing: 1.2,
                      fontWeight: FontWeight.w700)),
              const Spacer(),
              ?trailing,
            ]),
          ),
          Padding(padding: const EdgeInsets.all(22), child: child),
        ],
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  const _ErrorView({required this.message});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 44, color: scheme.error),
            const SizedBox(height: 14),
            Text(message,
                textAlign: TextAlign.center,
                style: TextStyle(color: scheme.error)),
          ],
        ),
      ),
    );
  }
}
