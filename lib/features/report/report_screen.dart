import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/theme.dart';
import '../../data/repository.dart';
import '../../models/models.dart';
import '../../widgets/citation_card.dart';
import '../auth/session.dart';

/// SAR/STR draft review. Shows the draft summary, every backing citation, and
/// the human review actions. Approve/edit/reject call the review_report RPC,
/// which flips status AND writes a `human:name` audit entry atomically.
class ReportScreen extends ConsumerWidget {
  final String entityId;
  const ReportScreen({super.key, required this.entityId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(entityDetailProvider(entityId));
    return Scaffold(
      appBar: AppBar(
        title: const Text('SAR draft'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.canPop()
              ? context.pop()
              : context.go('/entities/$entityId'),
        ),
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
        data: (d) => d.report == null
            ? const Center(child: Text('No draft report for this entity.'))
            : _Report(detail: d),
      ),
    );
  }
}

class _Report extends ConsumerWidget {
  final EntityDetail detail;
  const _Report({required this.detail});

  Future<void> _review(
      BuildContext context, WidgetRef ref, String action) async {
    final report = detail.report!;
    final reviewer =
        ref.read(sessionProvider).reviewerName ?? 'unknown';
    String? editedSummary;

    if (action == 'edit') {
      editedSummary = await _promptEdit(context, report.summary);
      if (editedSummary == null) return;
    }

    try {
      await ref.read(repositoryProvider).reviewReport(
            reportId: report.reportId,
            action: action,
            reviewerName: reviewer,
            editedSummary: editedSummary,
          );
      if (context.mounted) {
        final past = switch (action) {
          'approve' => 'approved',
          'edit' => 'edited',
          'reject' => 'rejected',
          _ => action,
        };
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Report $past · logged as human:$reviewer')),
        );
      }
    } catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Action failed: $e')));
      }
    }
  }

  Future<String?> _promptEdit(BuildContext context, String current) {
    final controller = TextEditingController(text: current);
    return showDialog<String>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Edit draft summary'),
        content: SizedBox(
          width: 520,
          child: TextField(
            controller: controller,
            maxLines: 10,
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, controller.text),
              child: const Text('Save & mark edited')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final r = detail.report!;
    final scheme = Theme.of(context).colorScheme;
    final decided = r.status != 'draft';

    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _StatusBanner(status: r.status),
              const SizedBox(height: 16),
              Text('Suspicious Activity Report — draft',
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w700)),
              Text('Subject: ${detail.entity.name}',
                  style: TextStyle(color: scheme.onSurfaceVariant)),
              const SizedBox(height: 16),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Summary',
                          style: TextStyle(
                              fontWeight: FontWeight.w700,
                              color: scheme.primary)),
                      const SizedBox(height: 8),
                      Text(r.summary,
                          style: const TextStyle(fontSize: 14.5, height: 1.5)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Row(children: [
                Icon(Icons.verified_outlined, size: 18, color: scheme.primary),
                const SizedBox(width: 8),
                Text('Evidence · ${r.citations.length} citations',
                    style: const TextStyle(
                        fontWeight: FontWeight.w700, fontSize: 15)),
              ]),
              const SizedBox(height: 4),
              Text('Every claim above traces to a source below.',
                  style: TextStyle(
                      fontSize: 12.5, color: scheme.onSurfaceVariant)),
              const SizedBox(height: 12),
              for (var i = 0; i < r.citations.length; i++)
                CitationCard(citation: r.citations[i], index: i + 1),
              const SizedBox(height: 8),
              if (decided)
                _DecidedNote(status: r.status)
              else
                _Actions(onReview: (a) => _review(context, ref, a)),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }
}

class _Actions extends StatelessWidget {
  final void Function(String action) onReview;
  const _Actions({required this.onReview});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 12,
      runSpacing: 12,
      children: [
        FilledButton.icon(
          onPressed: () => onReview('approve'),
          style: FilledButton.styleFrom(
              backgroundColor: AppTheme.severityLow),
          icon: const Icon(Icons.check),
          label: const Text('Approve & file'),
        ),
        OutlinedButton.icon(
          onPressed: () => onReview('edit'),
          icon: const Icon(Icons.edit_outlined),
          label: const Text('Edit'),
        ),
        OutlinedButton.icon(
          onPressed: () => onReview('reject'),
          style: OutlinedButton.styleFrom(
              foregroundColor: AppTheme.severityHigh),
          icon: const Icon(Icons.close),
          label: const Text('Reject'),
        ),
      ],
    );
  }
}

class _StatusBanner extends StatelessWidget {
  final String status;
  const _StatusBanner({required this.status});
  @override
  Widget build(BuildContext context) {
    final (color, icon, text) = switch (status) {
      'approved' => (AppTheme.severityLow, Icons.check_circle, 'Approved & filed'),
      'edited' => (AppTheme.severityMedium, Icons.edit, 'Edited by reviewer'),
      'rejected' => (AppTheme.severityHigh, Icons.cancel, 'Rejected'),
      _ => (Theme.of(context).colorScheme.primary, Icons.pending,
          'Pending human review'),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 8),
        Text(text,
            style: TextStyle(color: color, fontWeight: FontWeight.w600)),
      ]),
    );
  }
}

class _DecidedNote extends StatelessWidget {
  final String status;
  const _DecidedNote({required this.status});
  @override
  Widget build(BuildContext context) {
    return Text(
      'This report has been $status. The decision is recorded in the append-only audit trail.',
      style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
    );
  }
}
