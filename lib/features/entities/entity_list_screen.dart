import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/breakpoints.dart';
import '../../core/theme.dart';
import '../../data/repository.dart';
import '../../models/models.dart';
import '../../widgets/risk_badge.dart';
import 'ingest_dialog.dart';

/// The watchlist: every monitored entity with its risk badge + verdict.
/// Auto-refreshes on Realtime change events (watchlistProvider watches changes).
class EntityListScreen extends ConsumerWidget {
  const EntityListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(watchlistProvider);
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => showIngestDialog(context, ref),
        icon: const Icon(Icons.add),
        label: const Text('Ingest entity'),
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(watchlistProvider),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _ErrorView(message: '$e'),
          data: (items) => _List(items: items),
        ),
      ),
    );
  }
}

class _List extends StatelessWidget {
  final List<EntityDetail> items;
  const _List({required this.items});

  @override
  Widget build(BuildContext context) {
    // Sort highest-risk first so reviewers see what matters at the top.
    const order = {'high': 0, 'medium': 1, 'low': 2, 'none': 3};
    final sorted = [...items]
      ..sort((a, b) =>
          order[a.topSeverity]!.compareTo(order[b.topSeverity]!));

    final wide = Breakpoints.isWide(context);
    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Monitored entities',
                    style: Theme.of(context)
                        .textTheme
                        .titleLarge
                        ?.copyWith(fontWeight: FontWeight.w700)),
                Text('${items.length} accounts under continuous KYC',
                    style: TextStyle(
                        color: Theme.of(context).colorScheme.onSurfaceVariant)),
              ],
            ),
          ),
        ),
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 96),
          sliver: SliverGrid(
            gridDelegate: SliverGridDelegateWithMaxCrossAxisExtent(
              maxCrossAxisExtent: wide ? 460 : 640,
              mainAxisExtent: 150,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
            ),
            delegate: SliverChildBuilderDelegate(
              (context, i) => _EntityCard(detail: sorted[i]),
              childCount: sorted.length,
            ),
          ),
        ),
      ],
    );
  }
}

class _EntityCard extends StatelessWidget {
  final EntityDetail detail;
  const _EntityCard({required this.detail});

  @override
  Widget build(BuildContext context) {
    final e = detail.entity;
    final scheme = Theme.of(context).colorScheme;
    return Card(
      child: InkWell(
        onTap: () => context.push('/entities/${e.entityId}'),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  CircleAvatar(
                    radius: 18,
                    backgroundColor: scheme.secondaryContainer,
                    child: Icon(
                        e.isCompany
                            ? Icons.business
                            : Icons.person_outline,
                        size: 20,
                        color: scheme.onSecondaryContainer),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(e.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: const TextStyle(
                                fontSize: 15.5,
                                fontWeight: FontWeight.w600)),
                        Text(
                            [
                              e.isCompany ? 'Company' : 'Person',
                              if (e.nationality != null) e.nationality,
                              if (e.dinOrCin != null) e.dinOrCin,
                            ].join(' · '),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                                fontSize: 12,
                                color: scheme.onSurfaceVariant)),
                      ],
                    ),
                  ),
                  Icon(Icons.chevron_right, color: scheme.onSurfaceVariant),
                ],
              ),
              const Spacer(),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                children: [
                  RiskBadge(severity: detail.topSeverity, compact: true),
                  if (detail.verdict != null)
                    VerdictChip(verdict: detail.verdict!.verdict),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  const _ErrorView({required this.message});
  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.cloud_off,
                size: 40, color: AppTheme.severityMedium),
            const SizedBox(height: 12),
            Text('Could not load entities',
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 200),
              child: SingleChildScrollView(
                child: Text(message,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        color:
                            Theme.of(context).colorScheme.onSurfaceVariant)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
