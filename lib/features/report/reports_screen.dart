import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';
import '../../data/repository.dart';
import '../../models/models.dart';

/// Reports tab — every entity that has a drafted SAR, each previewable and
/// downloadable. Reads [reportsProvider] (cases carrying a SAR, served from
/// ckyc.db). Tapping a card opens the full in-app SAR draft.
class ReportsScreen extends ConsumerWidget {
  const ReportsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(reportsProvider);
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(reportsProvider),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _ErrorView(message: '$e'),
          data: (items) => _ReportsList(items: items),
        ),
      ),
    );
  }
}

Color _tierColor(RiskTier t) => switch (t) {
      RiskTier.critical => const Color(0xFFDC2626),
      RiskTier.high => const Color(0xFFEA580C),
      RiskTier.edd => const Color(0xFFF59E0B),
      RiskTier.eddLite => const Color(0xFF3B82F6),
      RiskTier.monitor => const Color(0xFF10B981),
      RiskTier.unknown => const Color(0xFF6B7280),
    };

class _ReportsList extends ConsumerWidget {
  final List<SarReport> items;
  const _ReportsList({required this.items});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Reports',
              style: Theme.of(context)
                  .textTheme
                  .headlineLarge
                  ?.copyWith(fontWeight: FontWeight.w700, fontSize: 36)),
          const SizedBox(height: 4),
          Text(
              '${items.length} SAR draft${items.length == 1 ? '' : 's'} — '
              'preview or download each',
              style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 13)),
          const SizedBox(height: 20),
          Expanded(
            child: items.isEmpty
                ? _empty(context)
                : Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 900),
                      child: ListView.separated(
                        itemCount: items.length,
                        separatorBuilder: (_, _) => const SizedBox(height: 12),
                        itemBuilder: (_, i) => _ReportCard(report: items[i]),
                      ),
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _empty(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.description_outlined,
              size: 40, color: scheme.onSurfaceVariant),
          const SizedBox(height: 12),
          Text('No SAR drafts yet',
              style: TextStyle(color: scheme.onSurfaceVariant)),
        ],
      ),
    );
  }
}

class _ReportCard extends ConsumerWidget {
  final SarReport report;
  const _ReportCard({required this.report});

  bool get _isCompany => report.type.toLowerCase() == 'company';

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final isDemo = ref.watch(isDemoModeProvider);
    final tc = _tierColor(report.tier);

    return InkWell(
      onTap: () => context.push('/entities/${report.clientId}/report'),
      borderRadius: BorderRadius.circular(16),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        decoration: BoxDecoration(
          color:
              isDark ? const Color(0xFF16161A) : scheme.surfaceContainerLowest,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: scheme.outlineVariant),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 22,
                  backgroundColor: scheme.secondaryContainer,
                  child: Icon(
                      _isCompany ? Icons.business : Icons.person_outline,
                      color: scheme.onSecondaryContainer,
                      size: 22),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(report.name,
                          style: const TextStyle(
                              fontWeight: FontWeight.w700, fontSize: 17),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis),
                      const SizedBox(height: 2),
                      Text('${report.type} · ${report.caseId}',
                          style: TextStyle(
                              fontSize: 12.5, color: scheme.onSurfaceVariant)),
                    ],
                  ),
                ),
                const SizedBox(width: 12),
                _TierBadge(tier: report.tier, color: tc),
                const SizedBox(width: 8),
                _SarStatusPill(status: report.sarStatus),
              ],
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Icon(Icons.verified_outlined,
                    size: 15, color: scheme.onSurfaceVariant),
                const SizedBox(width: 6),
                Text(
                    '${(report.citationCoverage * 100).round()}% citation coverage',
                    style: TextStyle(
                        fontSize: 12.5, color: scheme.onSurfaceVariant)),
                const Spacer(),
                OutlinedButton.icon(
                  onPressed: isDemo
                      ? () => context.push('/entities/${report.clientId}/report')
                      : () => _preview(context),
                  icon: const Icon(Icons.visibility_outlined, size: 17),
                  label: const Text('Preview'),
                ),
                const SizedBox(width: 8),
                FilledButton.tonalIcon(
                  onPressed: isDemo ? null : () => _download(context),
                  icon: const Icon(Icons.picture_as_pdf_outlined, size: 17),
                  label: const Text('Download PDF'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _preview(BuildContext context) async {
    final uri = Uri.parse(
        '${ApiConfig.baseUrl}/api/entity/${report.clientId}/sar/html');
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open the SAR preview.')));
    }
  }

  Future<void> _download(BuildContext context) async {
    final uri = Uri.parse(
        '${ApiConfig.baseUrl}/api/entity/${report.clientId}/sar/pdf');
    final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
    if (!ok && context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open the PDF download.')));
    }
  }
}

class _TierBadge extends StatelessWidget {
  final RiskTier tier;
  final Color color;
  const _TierBadge({required this.tier, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(tier.label,
          style: TextStyle(
              fontSize: 12, fontWeight: FontWeight.w700, color: color)),
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
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Text(label,
          style: TextStyle(
              fontSize: 12, fontWeight: FontWeight.w700, color: color)),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  const _ErrorView({required this.message});
  @override
  Widget build(BuildContext context) {
    // ListView so RefreshIndicator still works when the load errored.
    return ListView(
      children: [
        const SizedBox(height: 120),
        Icon(Icons.error_outline,
            size: 48, color: Theme.of(context).colorScheme.error),
        const SizedBox(height: 16),
        Text(message,
            textAlign: TextAlign.center,
            style: TextStyle(color: Theme.of(context).colorScheme.error)),
      ],
    );
  }
}
