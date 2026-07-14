import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../../data/repository.dart';
import '../../models/models.dart';

/// The append-only audit trail. Read-only by construction — the backend rejects
/// any UPDATE/DELETE on audit_log (RLS + trigger), so this screen only ever adds.
class AuditLogScreen extends ConsumerWidget {
  const AuditLogScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(auditProvider(null));
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(auditProvider(null)),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(child: Text('$e')),
          data: (entries) => _AuditList(entries: entries),
        ),
      ),
    );
  }
}

class _AuditList extends StatelessWidget {
  final List<AuditEntry> entries;
  const _AuditList({required this.entries});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 40),
      children: [
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 820),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(children: [
                  Text('Audit trail',
                      style: Theme.of(context)
                          .textTheme
                          .titleLarge
                          ?.copyWith(fontWeight: FontWeight.w700)),
                  const SizedBox(width: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      Icon(Icons.lock_outline,
                          size: 13, color: scheme.onSurfaceVariant),
                      const SizedBox(width: 4),
                      Text('append-only',
                          style: TextStyle(
                              fontSize: 11.5,
                              color: scheme.onSurfaceVariant)),
                    ]),
                  ),
                ]),
                Text('${entries.length} events · newest first',
                    style: TextStyle(color: scheme.onSurfaceVariant)),
                const SizedBox(height: 16),
                for (final e in entries) _AuditRow(entry: e),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _AuditRow extends StatelessWidget {
  final AuditEntry entry;
  const _AuditRow({required this.entry});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final human = entry.isHuman;
    final color = human ? scheme.primary : scheme.onSurfaceVariant;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: (human ? scheme.primary : scheme.outline)
                .withValues(alpha: 0.15),
            child: Icon(human ? Icons.person : Icons.smart_toy_outlined,
                size: 16, color: color),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Flexible(
                    child: Text(entry.actor,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                            fontWeight: FontWeight.w600,
                            fontSize: 13.5,
                            color: color)),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 7, vertical: 2),
                    decoration: BoxDecoration(
                      color: scheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(entry.action,
                        style: const TextStyle(
                            fontSize: 11.5, fontWeight: FontWeight.w500)),
                  ),
                ]),
                const SizedBox(height: 2),
                Text(
                  DateFormat('d MMM yyyy, HH:mm:ss')
                      .format(entry.timestamp.toLocal()),
                  style: TextStyle(
                      fontSize: 11.5, color: scheme.onSurfaceVariant),
                ),
                if (entry.details.isNotEmpty)
                  Text(
                    entry.details.entries
                        .map((e) => '${e.key}: ${e.value}')
                        .join('  ·  '),
                    style: TextStyle(
                        fontSize: 12, color: scheme.onSurfaceVariant),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
