import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/repository.dart';
import '../../models/models.dart';
import '../../widgets/mode_toggle.dart';

/// Screen 1 — the alert queue (the pipeline dashboard). Reads [alertsProvider]
/// (tier-based contract, served from ckyc.db). The retired watchlist/verdict
/// screens are gone; drill-down (Entity 360 / case / SAR) lands in a later phase.
class EntityListScreen extends ConsumerWidget {
  const EntityListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(alertsProvider);
    return Scaffold(
      body: RefreshIndicator(
        onRefresh: () async => ref.invalidate(alertsProvider),
        child: async.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => _ErrorView(message: '$e'),
          data: (items) => _Queue(items: items),
        ),
      ),
    );
  }
}

// ── formatting helpers ───────────────────────────────────────────────────────

String _inr(double v) {
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

String _statusLabel(String s) => s.isEmpty
    ? '—'
    : s
        .split('_')
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');

Color _tierColor(RiskTier t) => switch (t) {
      RiskTier.critical => const Color(0xFFDC2626), // red-600
      RiskTier.high => const Color(0xFFEA580C), // orange-600
      RiskTier.edd => const Color(0xFFF59E0B), // amber-500
      RiskTier.eddLite => const Color(0xFF3B82F6), // blue-500
      RiskTier.monitor => const Color(0xFF10B981), // emerald-500
      RiskTier.unknown => const Color(0xFF6B7280), // gray-500
    };

// ── the queue ────────────────────────────────────────────────────────────────

class _Queue extends ConsumerStatefulWidget {
  final List<Alert> items;
  const _Queue({required this.items});

  @override
  ConsumerState<_Queue> createState() => _QueueState();
}

class _QueueState extends ConsumerState<_Queue> {
  final _searchCtrl = TextEditingController();
  String _query = '';
  String _tier = 'all'; // wire value or 'all'
  String _status = 'all';
  String _sortCol = 'risk';
  bool _sortAsc = false;

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  List<Alert> get _filtered {
    final q = _query.trim().toLowerCase();
    final list = widget.items.where((a) {
      if (q.isNotEmpty && !a.name.toLowerCase().contains(q)) return false;
      if (_tier != 'all' && a.tier.wire != _tier) return false;
      if (_status != 'all' && a.status != _status) return false;
      return true;
    }).toList();

    int cmp(Alert a, Alert b) {
      final int c;
      switch (_sortCol) {
        case 'name':
          c = a.name.toLowerCase().compareTo(b.name.toLowerCase());
        case 'status':
          c = a.status.compareTo(b.status);
        case 'exposure':
          c = a.exposureInr.compareTo(b.exposureInr);
        default: // 'risk' — tier rank, then exposure
          final byTier = a.tier.rank.compareTo(b.tier.rank);
          c = byTier != 0 ? byTier : a.exposureInr.compareTo(b.exposureInr);
      }
      return _sortAsc ? c : -c;
    }

    list.sort(cmp);
    return list;
  }

  void _onSort(String col) => setState(() {
        if (_sortCol == col) {
          _sortAsc = !_sortAsc;
        } else {
          _sortCol = col;
          _sortAsc = col == 'name'; // text asc; risk/exposure default high-first
        }
      });

  void _clearFilters() => setState(() {
        _query = '';
        _searchCtrl.clear();
        _tier = 'all';
        _status = 'all';
      });

  void _refresh() {
    ref.invalidate(alertsProvider);
    ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Refreshing alert queue…')));
  }

  void _export() {
    final rows = _filtered;
    final buf = StringBuffer('Entity,Type,Tier,Status,Exposure (INR)\n');
    String esc(String s) => '"${s.replaceAll('"', '""')}"';
    for (final a in rows) {
      buf.writeln([
        esc(a.name),
        esc(a.type),
        esc(a.tier.label),
        esc(_statusLabel(a.status)),
        a.exposureInr.toStringAsFixed(0),
      ].join(','));
    }
    Clipboard.setData(ClipboardData(text: buf.toString()));
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Copied ${rows.length} alerts as CSV to clipboard')));
  }

  @override
  Widget build(BuildContext context) {
    final rows = _filtered;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _header(context),
          const SizedBox(height: 20),
          Expanded(
            child: Column(
              children: [
                _TableHeader(
                    sortCol: _sortCol, sortAsc: _sortAsc, onSort: _onSort),
                Expanded(
                  child: rows.isEmpty
                      ? _emptyState(context)
                      : ListView.separated(
                          itemCount: rows.length,
                          separatorBuilder: (_, _) => const SizedBox(height: 12),
                          itemBuilder: (_, i) => _AlertRow(alert: rows[i]),
                        ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _header(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Alert Queue',
            style: Theme.of(context)
                .textTheme
                .headlineLarge
                ?.copyWith(fontWeight: FontWeight.w700, fontSize: 36)),
        const SizedBox(height: 4),
        Text(
            '${_filtered.length} of ${widget.items.length} alerts',
            style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 13)),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            _FilterDropdown(
              label: 'Tier',
              value: _tier,
              options: const [
                ('all', 'All tiers'),
                ('CRITICAL', 'Critical'),
                ('HIGH', 'High'),
                ('EDD', 'EDD'),
                ('EDD_LITE', 'EDD Lite'),
                ('MONITOR', 'Monitor'),
              ],
              onSelected: (v) => setState(() => _tier = v),
            ),
            _FilterDropdown(
              label: 'Status',
              value: _status,
              options: const [
                ('all', 'All'),
                ('open', 'Open'),
                ('in_review', 'In review'),
                ('escalated', 'Escalated'),
                ('closed', 'Closed'),
              ],
              onSelected: (v) => setState(() => _status = v),
            ),
            _SearchBox(
                controller: _searchCtrl,
                onChanged: (v) => setState(() => _query = v)),
            _ActionButton(
                icon: Icons.refresh, label: 'Refresh', onTap: _refresh),
            _ActionButton(
                icon: Icons.file_download_outlined,
                label: 'Export',
                onTap: _export),
            const ModeToggle(),
          ],
        ),
      ],
    );
  }

  Widget _emptyState(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.inbox_outlined, size: 40, color: scheme.onSurfaceVariant),
          const SizedBox(height: 12),
          Text('No alerts match these filters',
              style: TextStyle(color: scheme.onSurfaceVariant)),
          const SizedBox(height: 8),
          TextButton(
              onPressed: _clearFilters, child: const Text('Clear filters')),
        ],
      ),
    );
  }
}

class _FilterDropdown extends StatelessWidget {
  final String label;
  final String value;
  final List<(String, String)> options;
  final ValueChanged<String> onSelected;
  const _FilterDropdown({
    required this.label,
    required this.value,
    required this.options,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final active = value != 'all';
    final selectedLabel = options
        .firstWhere((o) => o.$1 == value, orElse: () => ('all', label))
        .$2;
    return PopupMenuButton<String>(
      tooltip: label,
      position: PopupMenuPosition.under,
      onSelected: onSelected,
      itemBuilder: (_) => [
        for (final o in options)
          PopupMenuItem(
            value: o.$1,
            child: Row(children: [
              o.$1 == value
                  ? Icon(Icons.check, size: 16, color: scheme.primary)
                  : const SizedBox(width: 16),
              const SizedBox(width: 8),
              Text(o.$2),
            ]),
          ),
      ],
      child: Container(
        height: 38,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        decoration: BoxDecoration(
          color: active
              ? scheme.primary.withValues(alpha: 0.1)
              : scheme.surfaceContainerLowest,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
              color: active
                  ? scheme.primary.withValues(alpha: 0.5)
                  : scheme.outlineVariant.withValues(alpha: 0.5)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Text(active ? selectedLabel : label,
              style: TextStyle(
                  fontSize: 13.5,
                  color: active ? scheme.primary : scheme.onSurface,
                  fontWeight: active ? FontWeight.w600 : FontWeight.w400)),
          const SizedBox(width: 6),
          Icon(Icons.expand_more,
              size: 18,
              color: active ? scheme.primary : scheme.onSurfaceVariant),
        ]),
      ),
    );
  }
}

class _SearchBox extends StatelessWidget {
  final TextEditingController controller;
  final ValueChanged<String> onChanged;
  const _SearchBox({required this.controller, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return SizedBox(
      width: 240,
      height: 38,
      child: TextField(
        controller: controller,
        onChanged: onChanged,
        style: TextStyle(fontSize: 14, color: scheme.onSurface),
        decoration: InputDecoration(
          hintText: 'Search by name',
          hintStyle: TextStyle(
              color: scheme.onSurfaceVariant.withValues(alpha: 0.7),
              fontSize: 14),
          prefixIcon:
              Icon(Icons.search, size: 18, color: scheme.onSurfaceVariant),
          prefixIconConstraints:
              const BoxConstraints(minWidth: 36, minHeight: 36),
          isDense: true,
          filled: true,
          fillColor: scheme.surfaceContainerLowest,
          contentPadding:
              const EdgeInsets.symmetric(vertical: 0, horizontal: 12),
          enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: BorderSide(
                  color: scheme.outlineVariant.withValues(alpha: 0.5))),
          focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: BorderSide(color: scheme.primary)),
        ),
      ),
    );
  }
}

class _ActionButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;
  const _ActionButton(
      {required this.icon, required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.primary.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          height: 38,
          padding: const EdgeInsets.symmetric(horizontal: 14),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 18, color: scheme.primary),
            const SizedBox(width: 6),
            Text(label,
                style: TextStyle(
                    fontSize: 13.5,
                    color: scheme.primary,
                    fontWeight: FontWeight.w500)),
          ]),
        ),
      ),
    );
  }
}

class _TableHeader extends StatelessWidget {
  final String sortCol;
  final bool sortAsc;
  final ValueChanged<String> onSort;
  const _TableHeader(
      {required this.sortCol, required this.sortAsc, required this.onSort});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 16, right: 16, bottom: 8, top: 4),
      child: Row(
        children: [
          Expanded(
              flex: 4,
              child: _HeaderCell('ENTITY', 'name', sortCol, sortAsc, onSort)),
          Expanded(
              flex: 2,
              child: _HeaderCell('TIER', 'risk', sortCol, sortAsc, onSort)),
          Expanded(
              flex: 2,
              child:
                  _HeaderCell('STATUS', 'status', sortCol, sortAsc, onSort)),
          Expanded(
              flex: 2,
              child: _HeaderCell(
                  'EXPOSURE', 'exposure', sortCol, sortAsc, onSort)),
          const SizedBox(width: 32),
        ],
      ),
    );
  }
}

class _HeaderCell extends StatelessWidget {
  final String label;
  final String col;
  final String sortCol;
  final bool sortAsc;
  final ValueChanged<String> onSort;
  const _HeaderCell(
      this.label, this.col, this.sortCol, this.sortAsc, this.onSort);

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final active = sortCol == col;
    return InkWell(
      onTap: () => onSort(col),
      borderRadius: BorderRadius.circular(4),
      child: Row(
        children: [
          Flexible(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: active
                        ? scheme.primary
                        : scheme.onSurfaceVariant.withValues(alpha: 0.8),
                    letterSpacing: 1.0,
                    fontWeight: active ? FontWeight.w700 : FontWeight.w500,
                  ),
            ),
          ),
          const SizedBox(width: 4),
          Icon(
            active
                ? (sortAsc ? Icons.arrow_upward : Icons.arrow_downward)
                : Icons.unfold_more,
            size: 13,
            color: active
                ? scheme.primary
                : scheme.onSurfaceVariant.withValues(alpha: 0.6),
          ),
        ],
      ),
    );
  }
}

class _AlertRow extends StatelessWidget {
  final Alert alert;
  const _AlertRow({required this.alert});

  bool get _isCompany => alert.type.toLowerCase() == 'company';

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final tierColor = _tierColor(alert.tier);

    return InkWell(
      // Drill into the full case: Entity 360, risk timeline, three-column
      // evidence and the SAR the investigation agent drafted.
      onTap: () => context.push('/entities/${alert.clientId}'),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
        decoration: BoxDecoration(
          color:
              isDark ? const Color(0xFF16161A) : scheme.surfaceContainerLowest,
          borderRadius: BorderRadius.circular(16),
          border:
              Border.all(color: scheme.outlineVariant),
          boxShadow: [
            BoxShadow(
              color: scheme.shadow.withValues(alpha: 0.04),
              blurRadius: 12,
              offset: const Offset(0, 4),
            )
          ],
        ),
        child: Row(
          children: [
            Expanded(
              flex: 4,
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(alert.name,
                            style: const TextStyle(
                                fontWeight: FontWeight.w700, fontSize: 18),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis),
                        const SizedBox(height: 2),
                        Text(alert.type,
                            style: TextStyle(
                                fontSize: 12.5, color: scheme.outline)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              flex: 2,
              child: Align(
                alignment: Alignment.centerLeft,
                child: _TierBadge(tier: alert.tier, color: tierColor),
              ),
            ),
            Expanded(
              flex: 2,
              child: Text(_statusLabel(alert.status),
                  style: TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: scheme.onSurface)),
            ),
            Expanded(
              flex: 2,
              child: Text(
                  alert.exposureInr > 0 ? _inr(alert.exposureInr) : '—',
                  style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 14,
                      color: scheme.onSurface)),
            ),
            Icon(Icons.chevron_right, color: scheme.onSurfaceVariant),
          ],
        ),
      ),
    );
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
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 8,
          height: 8,
          decoration: BoxDecoration(shape: BoxShape.circle, color: color),
        ),
        const SizedBox(width: 8),
        Text(tier.label,
            style: TextStyle(
                fontSize: 12.5, fontWeight: FontWeight.w700, color: color)),
      ]),
    );
  }
}

class _ErrorView extends StatelessWidget {
  final String message;
  const _ErrorView({required this.message});
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.error_outline,
              size: 48, color: Theme.of(context).colorScheme.error),
          const SizedBox(height: 16),
          Text(message,
              textAlign: TextAlign.center,
              style: TextStyle(color: Theme.of(context).colorScheme.error)),
        ],
      ),
    );
  }
}
