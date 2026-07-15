import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/breakpoints.dart';
import '../../core/theme.dart';
import '../../data/repository.dart';
import '../../models/models.dart';
import '../../widgets/risk_badge.dart';
import 'ingest_dialog.dart';

class EntityListScreen extends ConsumerWidget {
  const EntityListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(watchlistProvider);
    final scheme = Theme.of(context).colorScheme;

    return Scaffold(
      floatingActionButton: Breakpoints.isWide(context)
          ? FloatingActionButton.extended(
              onPressed: () => showIngestDialog(context, ref),
              backgroundColor: scheme.primary,
              foregroundColor: scheme.onPrimary,
              icon: const Icon(Icons.add),
              label: const Text('Ingest entity',
                  style: TextStyle(fontWeight: FontWeight.bold)),
            )
          : FloatingActionButton(
              onPressed: () => showIngestDialog(context, ref),
              backgroundColor: scheme.primary,
              foregroundColor: scheme.onPrimary,
              child: const Icon(Icons.add),
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

class _List extends ConsumerStatefulWidget {
  final List<EntityDetail> items;
  const _List({required this.items});

  @override
  ConsumerState<_List> createState() => _ListState();
}

class _ListState extends ConsumerState<_List> {
  final _searchCtrl = TextEditingController();
  String _query = '';
  String _jurisdiction = 'all';
  String _status = 'all';
  String _risk = 'all';
  String _dateRange = 'all';
  String _sortCol = 'risk';
  bool _sortAsc = false;

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
  }

  String _statusKey(EntityDetail d) => d.verdict?.verdict ?? 'unscreened';

  DateTime? _latestEvent(EntityDetail d) => d.riskEvents.isEmpty
      ? null
      : d.riskEvents
          .map((e) => e.detectedAt)
          .reduce((a, b) => a.isAfter(b) ? a : b);

  List<EntityDetail> get _filtered {
    final q = _query.trim().toLowerCase();
    final now = DateTime.now();
    final window = switch (_dateRange) {
      '24h' => const Duration(hours: 24),
      '7d' => const Duration(days: 7),
      '30d' => const Duration(days: 30),
      _ => null,
    };

    final list = widget.items.where((d) {
      final e = d.entity;
      if (q.isNotEmpty) {
        final hay = [e.name, e.dinOrCin ?? '', e.nationality ?? '', ...e.aliases]
            .join(' ')
            .toLowerCase();
        if (!hay.contains(q)) return false;
      }
      if (_jurisdiction != 'all' && e.nationality != _jurisdiction) return false;
      if (_status != 'all' && _statusKey(d) != _status) return false;
      if (_risk != 'all' && d.topSeverity != _risk) return false;
      if (window != null) {
        final latest = _latestEvent(d);
        if (latest == null || now.difference(latest) > window) return false;
      }
      return true;
    }).toList();

    int cmp(EntityDetail a, EntityDetail b) {
      final int c;
      switch (_sortCol) {
        case 'name':
          c = a.entity.name.toLowerCase().compareTo(b.entity.name.toLowerCase());
        case 'id':
          c = (a.entity.dinOrCin ?? '').compareTo(b.entity.dinOrCin ?? '');
        case 'jurisdiction':
          c = AppTheme.countryName(a.entity.nationality)
              .compareTo(AppTheme.countryName(b.entity.nationality));
        case 'status':
          c = _statusKey(a).compareTo(_statusKey(b));
        default: // 'risk'
          c = AppTheme.mockRiskScore(a.topSeverity)
              .compareTo(AppTheme.mockRiskScore(b.topSeverity));
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
          _sortAsc = col != 'risk'; // risk defaults to highest-first
        }
      });

  void _clearFilters() => setState(() {
        _query = '';
        _searchCtrl.clear();
        _jurisdiction = 'all';
        _status = 'all';
        _risk = 'all';
        _dateRange = 'all';
      });

  void _refresh() {
    ref.invalidate(watchlistProvider);
    ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Refreshing watchlist…')));
  }

  void _export() {
    final rows = _filtered;
    final buf =
        StringBuffer('Entity Name,ID Number,Jurisdiction,Status,Confidence Level\n');
    String esc(String s) => '"${s.replaceAll('"', '""')}"';
    for (final d in rows) {
      final e = d.entity;
      buf.writeln([
        esc(e.name),
        esc(e.dinOrCin ?? 'REG-${e.entityId.substring(0, 6).toUpperCase()}'),
        esc(AppTheme.countryName(e.nationality)),
        esc(AppTheme.verdictLabel(d.verdict?.verdict)),
        d.topSeverity == 'none' ? 'None' : '${d.topSeverity[0].toUpperCase()}${d.topSeverity.substring(1)}',
      ].join(','));
    }
    Clipboard.setData(ClipboardData(text: buf.toString()));
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Copied ${rows.length} entities as CSV to clipboard')));
  }

  @override
  Widget build(BuildContext context) {
    final rows = _filtered;
    final jurisdictions = {
      for (final d in widget.items)
        if (d.entity.nationality != null) d.entity.nationality!
    }.toList()
      ..sort();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _header(context, jurisdictions),
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
                          itemBuilder: (_, i) => _EntityRow(detail: rows[i]),
                        ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _header(BuildContext context, List<String> jurisdictions) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Entity Watchlist — High Priority',
            style: Theme.of(context)
                .textTheme
                .headlineMedium
                ?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Text(
            '${_filtered.length} of ${widget.items.length} entities under continuous KYC',
            style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 13)),
        const SizedBox(height: 16),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            _FilterDropdown(
              label: 'Date Range',
              value: _dateRange,
              options: const [
                ('all', 'All time'),
                ('24h', 'Last 24h'),
                ('7d', 'Last 7 days'),
                ('30d', 'Last 30 days'),
              ],
              onSelected: (v) => setState(() => _dateRange = v),
            ),
            _FilterDropdown(
              label: 'Jurisdiction',
              value: _jurisdiction,
              options: [
                ('all', 'All'),
                for (final j in jurisdictions) (j, AppTheme.countryName(j)),
              ],
              onSelected: (v) => setState(() => _jurisdiction = v),
            ),
            _FilterDropdown(
              label: 'Status',
              value: _status,
              options: const [
                ('all', 'All'),
                ('confirmed_match', 'Confirmed match'),
                ('needs_review', 'Needs review'),
                ('false_positive', 'False positive'),
                ('unscreened', 'Unscreened'),
              ],
              onSelected: (v) => setState(() => _status = v),
            ),
            _FilterDropdown(
              label: 'Risk Level',
              value: _risk,
              options: const [
                ('all', 'All'),
                ('high', 'High'),
                ('medium', 'Medium'),
                ('low', 'Low'),
                ('none', 'No risk'),
              ],
              onSelected: (v) => setState(() => _risk = v),
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
          Icon(Icons.search_off, size: 40, color: scheme.onSurfaceVariant),
          const SizedBox(height: 12),
          Text('No entities match these filters',
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
          hintText: 'Search entities',
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
              flex: 3,
              child: _HeaderCell('ENTITY NAME', 'name', sortCol, sortAsc, onSort)),
          Expanded(
              flex: 2,
              child: _HeaderCell('ID NUMBER', 'id', sortCol, sortAsc, onSort)),
          Expanded(
              flex: 3,
              child: _HeaderCell(
                  'JURISDICTION', 'jurisdiction', sortCol, sortAsc, onSort)),
          Expanded(
              flex: 2,
              child: _HeaderCell('STATUS', 'status', sortCol, sortAsc, onSort)),
          Expanded(
              flex: 2,
              child: _HeaderCell('CONFIDENCE LEVEL', 'risk', sortCol, sortAsc, onSort)),
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

class _EntityRow extends StatelessWidget {
  final EntityDetail detail;
  const _EntityRow({required this.detail});

  @override
  Widget build(BuildContext context) {
    final e = detail.entity;
    final scheme = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final level = detail.topSeverity == 'none' ? 'None' : '${detail.topSeverity[0].toUpperCase()}${detail.topSeverity.substring(1)}';
    final sevColor = AppTheme.severityColor(detail.topSeverity);

    return InkWell(
      onTap: () => context.push('/entities/${e.entityId}'),
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
        decoration: BoxDecoration(
          color:
              isDark ? const Color(0xFF16161A) : scheme.surfaceContainerLowest,
          borderRadius: BorderRadius.circular(16),
          border:
              Border.all(color: scheme.outlineVariant.withValues(alpha: 0.5)),
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
              flex: 3,
              child: Row(
                children: [
                  Container(
                    width: 42,
                    height: 42,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: scheme.surfaceContainerHigh,
                      border: Border.all(
                          color: isDark
                              ? Colors.white.withValues(alpha: 0.08)
                              : Colors.transparent),
                    ),
                    child: Icon(
                        e.isCompany ? Icons.business : Icons.person_outline,
                        size: 20,
                        color: scheme.secondary),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(e.name,
                            style: const TextStyle(
                                fontWeight: FontWeight.w700, fontSize: 15),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis),
                        const SizedBox(height: 2),
                        Text(e.isCompany ? 'Company' : 'Person',
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
              child: Text(
                e.dinOrCin ?? 'REG-${e.entityId.substring(0, 6).toUpperCase()}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context)
                    .textTheme
                    .labelMedium
                    ?.copyWith(color: scheme.onSurfaceVariant, fontSize: 13),
              ),
            ),
            Expanded(
              flex: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(AppTheme.countryName(e.nationality),
                      style: const TextStyle(fontSize: 14),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                  if (e.nationality != null) ...[
                    const SizedBox(height: 2),
                    Text(e.nationality!,
                        style:
                            TextStyle(fontSize: 12.5, color: scheme.outline)),
                  ],
                ],
              ),
            ),
            Expanded(
              flex: 2,
              child: Align(
                alignment: Alignment.centerLeft,
                child: detail.verdict != null
                    ? VerdictChip(verdict: detail.verdict!.verdict)
                    : RiskBadge(severity: detail.topSeverity, compact: true),
              ),
            ),
            Expanded(
              flex: 2,
              child: Row(
                children: [
                  Container(
                    width: 8,
                    height: 8,
                    decoration:
                        BoxDecoration(shape: BoxShape.circle, color: sevColor),
                  ),
                  const SizedBox(width: 8),
                  Text(level,
                      style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 14,
                          color: scheme.onSurface)),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: scheme.onSurfaceVariant),
          ],
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
