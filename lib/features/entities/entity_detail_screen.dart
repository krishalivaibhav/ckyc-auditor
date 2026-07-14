import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/breakpoints.dart';
import '../../core/theme.dart';
import '../../data/repository.dart';
import '../../models/models.dart';
import '../../widgets/risk_badge.dart';
import '../../widgets/risk_gauge.dart';
import '../../widgets/timeline_tile.dart';

/// Full entity view: risk score + plain-English explanation (Person 2),
/// evidence/risk timeline (Person 3/4), and a link into the SAR draft (Person 4).
class EntityDetailScreen extends ConsumerWidget {
  final String entityId;
  const EntityDetailScreen({super.key, required this.entityId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(entityDetailProvider(entityId));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Entity detail'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () =>
              context.canPop() ? context.pop() : context.go('/entities'),
        ),
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
        data: (d) => _Detail(detail: d),
      ),
    );
  }
}

class _Detail extends StatelessWidget {
  final EntityDetail detail;
  const _Detail({required this.detail});

  @override
  Widget build(BuildContext context) {
    final wide = Breakpoints.isWide(context);
    final header = _Header(detail: detail);
    final timeline = _Timeline(detail: detail);

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 1100),
        child: wide
            ? Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 5, child: header),
                  const SizedBox(width: 24),
                  Expanded(flex: 4, child: timeline),
                ],
              )
            : Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [header, const SizedBox(height: 20), timeline],
              ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  final EntityDetail detail;
  const _Header({required this.detail});

  @override
  Widget build(BuildContext context) {
    final e = detail.entity;
    final v = detail.verdict;
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            CircleAvatar(
              radius: 24,
              backgroundColor: scheme.secondaryContainer,
              child: Icon(e.isCompany ? Icons.business : Icons.person_outline,
                  color: scheme.onSecondaryContainer),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(e.name,
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w700)),
                  if (e.aliases.isNotEmpty)
                    Text('aka ${e.aliases.join(', ')}',
                        style: TextStyle(
                            fontSize: 12.5,
                            color: scheme.onSurfaceVariant)),
                ],
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Wrap(spacing: 8, runSpacing: 8, children: [
          RiskBadge(severity: detail.topSeverity),
          if (v != null) VerdictChip(verdict: v.verdict),
          _MetaChip(
              icon: Icons.flag_outlined,
              label: e.nationality ?? 'Unknown nationality'),
          if (e.dinOrCin != null)
            _MetaChip(icon: Icons.tag, label: e.dinOrCin!),
          _MetaChip(
              icon: Icons.source_outlined,
              label: e.source.replaceAll('_', ' ')),
        ]),
        const SizedBox(height: 20),

        // Risk score + explanation card (Person 2's output)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: v == null
                ? Row(children: [
                    Icon(Icons.hourglass_empty,
                        color: scheme.onSurfaceVariant),
                    const SizedBox(width: 10),
                    const Expanded(
                        child: Text('No resolution verdict yet.')),
                  ])
                : Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      RiskGauge(
                        value: v.confidence,
                        color: AppTheme.verdictColor(v.verdict),
                        caption: AppTheme.verdictLabel(v.verdict),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(children: [
                              Icon(Icons.psychology_outlined,
                                  size: 16, color: scheme.primary),
                              const SizedBox(width: 6),
                              Text('Why this verdict',
                                  style: TextStyle(
                                      fontSize: 12.5,
                                      fontWeight: FontWeight.w600,
                                      color: scheme.primary)),
                            ]),
                            const SizedBox(height: 6),
                            Text(v.explanation,
                                style: const TextStyle(
                                    fontSize: 13.5, height: 1.4)),
                            if (v.anchorUsed != 'none') ...[
                              const SizedBox(height: 8),
                              _MetaChip(
                                  icon: Icons.anchor,
                                  label: 'Verified via ${v.anchorUsed}'),
                            ],
                          ],
                        ),
                      ),
                    ],
                  ),
          ),
        ),
        const SizedBox(height: 12),
        if (detail.report != null)
          FilledButton.tonalIcon(
            onPressed: () =>
                context.push('/entities/${e.entityId}/report'),
            icon: const Icon(Icons.description_outlined),
            label: Text('View SAR draft · ${detail.report!.status}'),
          ),
      ],
    );
  }
}

class _Timeline extends StatelessWidget {
  final EntityDetail detail;
  const _Timeline({required this.detail});

  @override
  Widget build(BuildContext context) {
    // Merge risk events + evidence into one chronological stream.
    final rows = <(_Kind, DateTime, String, String?, String?, String?)>[];
    for (final r in detail.riskEvents) {
      rows.add((
        _Kind.risk,
        r.detectedAt,
        r.eventType.replaceAll('_', ' '),
        r.sourceRefs.isEmpty ? null : r.sourceRefs.first,
        r.severity,
        null,
      ));
    }
    for (final ev in detail.evidence) {
      rows.add((
        _Kind.evidence,
        ev.eventDate,
        ev.event,
        ev.sourceUrl,
        null,
        ev.excerpt,
      ));
    }
    rows.sort((a, b) => b.$2.compareTo(a.$2));

    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.timeline, size: 18, color: scheme.primary),
              const SizedBox(width: 8),
              const Text('Risk & evidence timeline',
                  style:
                      TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
            ]),
            const SizedBox(height: 16),
            if (rows.isEmpty)
              Text('No risk signals recorded yet.',
                  style: TextStyle(color: scheme.onSurfaceVariant))
            else
              for (var i = 0; i < rows.length; i++)
                TimelineTile(
                  date: rows[i].$2,
                  title: rows[i].$3 +
                      (rows[i].$1 == _Kind.risk ? '  ·  risk event' : ''),
                  sourceUrl: (rows[i].$4?.startsWith('http') ?? false)
                      ? rows[i].$4
                      : null,
                  severity: rows[i].$5,
                  excerpt: rows[i].$6,
                  isLast: i == rows.length - 1,
                ),
          ],
        ),
      ),
    );
  }
}

enum _Kind { risk, evidence }

class _MetaChip extends StatelessWidget {
  final IconData icon;
  final String label;
  const _MetaChip({required this.icon, required this.label});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 13, color: scheme.onSurfaceVariant),
        const SizedBox(width: 5),
        Text(label,
            style: TextStyle(fontSize: 12, color: scheme.onSurfaceVariant)),
      ]),
    );
  }
}
