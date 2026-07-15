import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/breakpoints.dart';
import '../../core/theme.dart';
import '../../data/repository.dart';
import '../../models/models.dart';
import '../../widgets/timeline_tile.dart';

class EntityDetailScreen extends ConsumerWidget {
  final String entityId;
  const EntityDetailScreen({super.key, required this.entityId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(entityDetailProvider(entityId));
    return Scaffold(
      appBar: AppBar(
        title: const Text('Entity detail', style: TextStyle(fontWeight: FontWeight.w600)),
        centerTitle: true,
        elevation: 0,
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
    final header = _ProfileHeader(detail: detail);
    final timeline = _TimelinePanel(detail: detail);
    final right = _RightColumn(detail: detail);

    return SingleChildScrollView(
      padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 48),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1400),
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.0, end: 1.0),
            duration: const Duration(milliseconds: 600),
            curve: Curves.easeOutCubic,
            builder: (context, value, child) {
              return Opacity(
                opacity: value,
                child: Transform.translate(
                  offset: Offset(0, 20 * (1 - value)),
                  child: child,
                ),
              );
            },
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                header,
                const SizedBox(height: 48), // Added spacing between header and content
                wide
                    ? Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(flex: 6, child: timeline),
                          const SizedBox(width: 48),
                          Expanded(flex: 4, child: right),
                        ],
                      )
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [timeline, const SizedBox(height: 32), right],
                      ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ProfileHeader extends StatelessWidget {
  final EntityDetail detail;
  const _ProfileHeader({required this.detail});

  @override
  Widget build(BuildContext context) {
    final e = detail.entity;
    final scheme = Theme.of(context).colorScheme;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        CircleAvatar(
          radius: 40,
          backgroundColor: scheme.secondaryContainer,
          child: Icon(
            e.isCompany ? Icons.business : Icons.person_outline,
            color: scheme.onSecondaryContainer,
            size: 36,
          ),
        ),
        const SizedBox(width: 24),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(e.name,
                  style: Theme.of(context)
                      .textTheme
                      .headlineMedium
                      ?.copyWith(fontWeight: FontWeight.w800, height: 1.2)),
              if (e.aliases.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text('aka ${e.aliases.join(', ')}',
                    style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                        color: scheme.onSurfaceVariant)),
              ]
            ],
          ),
        ),
      ],
    );
  }
}

class _RightColumn extends StatelessWidget {
  final EntityDetail detail;
  const _RightColumn({required this.detail});

  @override
  Widget build(BuildContext context) {
    final e = detail.entity;
    final v = detail.verdict;
    final scheme = Theme.of(context).colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Panel(
          title: 'Recommended Action',
          icon: Icons.assignment_turned_in_outlined,
          child: v == null
              ? Row(children: [
                  Icon(Icons.hourglass_empty, color: scheme.onSurfaceVariant),
                  const SizedBox(width: 12),
                  const Expanded(child: Text('No resolution verdict yet.')),
                ])
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Icon(Icons.psychology_outlined,
                          size: 20, color: scheme.primary),
                      const SizedBox(width: 10),
                      Text('Action details',
                          style: TextStyle(
                              fontSize: 14,
                              letterSpacing: 0.5,
                              fontWeight: FontWeight.w700,
                              color: scheme.primary)),
                    ]),
                    const SizedBox(height: 16),
                    Text(v.explanation,
                        style: TextStyle(
                            fontSize: 15,
                            height: 1.6,
                            color: scheme.onSurface)),
                    if (v.anchorUsed != 'none') ...[
                      const SizedBox(height: 24),
                      _MetaChip(
                          icon: Icons.anchor,
                          label: 'Verified via ${v.anchorUsed}'),
                    ],
                  ],
                ),
        ),
        const SizedBox(height: 32),
        if (detail.report != null)
          SizedBox(
            width: double.infinity,
            height: 56,
            child: FilledButton.tonalIcon(
              style: FilledButton.styleFrom(
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14)),
              ),
              onPressed: () => context.push('/entities/${e.entityId}/report'),
              icon: const Icon(Icons.description_outlined, size: 22),
              label: Text(
                'View SAR draft · ${detail.report!.status}',
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.w700),
              ),
            ),
          ),
      ],
    );
  }
}

class _TimelinePanel extends StatelessWidget {
  final EntityDetail detail;
  const _TimelinePanel({required this.detail});

  @override
  Widget build(BuildContext context) {
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
    for (final t in detail.timeline) {
      rows.add((
      _Kind.evidence,
      t.eventDate,
      t.event,
      t.sourceUrl,
      null,
      t.excerpt,
      ));
    }
    rows.sort((a, b) => b.$2.compareTo(a.$2));

    final scheme = Theme.of(context).colorScheme;
    return _Panel(
      title: 'Risk & evidence timeline',
      icon: Icons.timeline,
      trailing: rows.isEmpty
          ? null
          : Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Text('${rows.length} Events',
            style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w700,
                color: scheme.onSurfaceVariant)),
      ),
      child: rows.isEmpty
          ? Padding(
        padding: const EdgeInsets.symmetric(vertical: 40),
        child: Center(
          child: Text('No risk signals recorded yet.',
              style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 15)),
        ),
      )
          : Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (detail.timeline.isEmpty)
            Padding(
              padding: const EdgeInsets.only(bottom: 24),
              child: Text(
                  'Detailed evidence appears here once a report is filed.',
                  style: TextStyle(
                      fontSize: 14,
                      fontStyle: FontStyle.italic,
                      color: scheme.onSurfaceVariant)),
            ),
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
    );
  }
}

enum _Kind { risk, evidence }

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
        borderRadius: BorderRadius.circular(20), // Softer, more modern corners
        border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.2)),
        boxShadow: [
          BoxShadow(
            color: scheme.shadow.withValues(alpha: 0.04),
            blurRadius: 16,
            offset: const Offset(0, 6),
          )
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
            decoration: BoxDecoration(
              border: Border(
                  bottom: BorderSide(
                      color: scheme.outlineVariant.withValues(alpha: 0.2))),
            ),
            child: Row(children: [
              Icon(icon, size: 20, color: scheme.primary),
              const SizedBox(width: 12),
              Text(title.toUpperCase(),
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: scheme.onSurfaceVariant,
                      letterSpacing: 1.5,
                      fontWeight: FontWeight.w700)),
              const Spacer(),
              if (trailing != null) trailing!,
            ]),
          ),
          // Substantially increased padding inside the panel
          Padding(padding: const EdgeInsets.all(32), child: child),
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
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.3)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 16, color: scheme.onSurfaceVariant),
        const SizedBox(width: 8),
        Text(label,
            style: TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
                color: scheme.onSurfaceVariant)),
      ]),
    );
  }
}