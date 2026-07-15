import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/breakpoints.dart';
import '../core/theme.dart';
import '../data/repository.dart';
import '../features/auth/session.dart';
import '../models/models.dart';

class ResponsiveScaffold extends ConsumerWidget {
  final Widget child;
  final String location;

  const ResponsiveScaffold(
      {super.key, required this.child, required this.location});

  static const List<({String path, List<List<dynamic>> icon, String label})> _tabs = [
    (path: '/entities', icon: HugeIcons.strokeRoundedView, label: 'Alert Queue'),
    (path: '/audit', icon: HugeIcons.strokeRoundedCheckList, label: 'Audit Log'),
  ];

  int get _index => location.startsWith('/audit') ? 1 : 0;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = Breakpoints.isWide(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final colorScheme = Theme.of(context).colorScheme;

    final body = Column(
      children: [
        _TopNavBar(location: location),
        Expanded(
          child: Stack(
            children: [
              child,
            ],
          ),
        ),
      ],
    );

    if (wide) {
      return Scaffold(
        body: Row(
          children: [
            Container(
              width: 256,
              color: isDark ? const Color(0xFF0A0A0C) : Colors.white,
              child: Column(
                children: [
                  const _RailHeader(),
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      children: [
                        for (int i = 0; i < _tabs.length; i++)
                          _SidebarItem(
                            tab: _tabs[i],
                            isSelected: _index == i,
                            onTap: () => context.go(_tabs[i].path),
                          ),
                      ],
                    ),
                  ),
                  const Divider(height: 1),
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: InkWell(
                      onTap: () => ref.read(sessionProvider.notifier).signOut(),
                      borderRadius: BorderRadius.circular(8),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                        child: Row(
                          children: [
                            HugeIcon(icon: HugeIcons.strokeRoundedLogout01, size: 24, color: colorScheme.onSurfaceVariant),
                            const SizedBox(width: 16),
                            Text('Sign Out', style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                              fontSize: 14, color: colorScheme.onSurfaceVariant,
                            )),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            VerticalDivider(width: 1, color: colorScheme.outlineVariant.withValues(alpha: 0.5)),
            Expanded(child: body),
          ],
        ),
      );
    }

    return Scaffold(
      body: SafeArea(child: body),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          border: Border(top: BorderSide(color: colorScheme.outlineVariant.withValues(alpha: 0.5))),
        ),
        child: NavigationBar(
          selectedIndex: _index,
          onDestinationSelected: (i) => context.go(_tabs[i].path),
          destinations: [
            for (final t in _tabs)
              NavigationDestination(icon: HugeIcon(icon: t.icon, color: Theme.of(context).colorScheme.onSurfaceVariant), label: t.label),
          ],
        ),
      ),
    );
  }
}

class _SidebarItem extends StatelessWidget {
  final ({String path, List<List<dynamic>> icon, String label}) tab;
  final bool isSelected;
  final VoidCallback onTap;

  const _SidebarItem({required this.tab, required this.isSelected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          decoration: BoxDecoration(
            color: isSelected ? scheme.primaryContainer.withValues(alpha: 0.1) : Colors.transparent,
            border: isSelected ? Border(right: BorderSide(color: scheme.primary, width: 4)) : null,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Row(
            children: [
              HugeIcon(icon: tab.icon, size: 24, color: isSelected ? scheme.primary : scheme.onSurfaceVariant),
              const SizedBox(width: 16),
              Text(
                tab.label,
                style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                  fontSize: 14,
                  color: isSelected ? scheme.primary : scheme.onSurfaceVariant,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RailHeader extends StatelessWidget {
  const _RailHeader();
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: scheme.outlineVariant.withValues(alpha: 0.5))),
      ),
      child: Row(
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: scheme.primaryContainer.withValues(alpha: 0.2),
              shape: BoxShape.circle,
              border: Border.all(color: scheme.primary.withValues(alpha: 0.3)),
            ),
            child: HugeIcon(icon: HugeIcons.strokeRoundedUser, size: 24, color: scheme.primary),
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('TechMKYC', style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                color: scheme.primary, fontWeight: FontWeight.bold, fontSize: 20
              )),
              Text('Compliance Auditor', style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: scheme.onSurfaceVariant,
              )),
            ],
          ),
        ],
      ),
    );
  }
}

class _TopNavBar extends StatelessWidget {
  final String location;
  const _TopNavBar({required this.location});

  void _comingSoon(BuildContext context, String label) =>
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$label — coming soon')));

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final onWatchlist = location.startsWith('/entities');
    final onAudit = location.startsWith('/audit');

    return Container(
      height: 64,
      decoration: BoxDecoration(
        color: isDark ? const Color(0xFF0A0A0C) : scheme.surfaceContainerLowest,
        border: Border(
            bottom: BorderSide(
                color: scheme.outlineVariant.withValues(alpha: 0.5))),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                _TopNavItem(
                    icon: HugeIcons.strokeRoundedView,
                    label: 'Alert Queue',
                    isSelected: onWatchlist,
                    onTap: () => context.go('/entities')),
                _TopNavItem(
                    icon: HugeIcons.strokeRoundedCheckList,
                    label: 'Audit Log',
                    isSelected: onAudit,
                    onTap: () => context.go('/audit')),
                _TopNavItem(
                    icon: HugeIcons.strokeRoundedShield01,
                    label: 'Investigations',
                    onTap: () => _comingSoon(context, 'Investigations')),
                _TopNavItem(
                    icon: HugeIcons.strokeRoundedFile01,
                    label: 'Reports',
                    onTap: () => _comingSoon(context, 'Reports')),
                _TopNavItem(
                    icon: HugeIcons.strokeRoundedSettings01,
                    label: 'Settings',
                    onTap: () => _comingSoon(context, 'Settings')),
              ],
            ),
          ),
          Row(
            children: [
              IconButton(
                icon: const HugeIcon(icon: HugeIcons.strokeRoundedSearch01, color: Colors.grey),
                tooltip: 'Search the alert queue',
                onPressed: () => context.go('/entities'),
              ),
              const _NotificationsBell(),
            ],
          ),
        ],
      ),
    );
  }
}

/// High-risk alert bell: reads the alert queue, shows a dot when any alert is
/// CRITICAL or HIGH tier, and lists them. Selecting one opens the alert queue.
class _NotificationsBell extends ConsumerWidget {
  const _NotificationsBell();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final scheme = Theme.of(context).colorScheme;
    final highRisk = ref.watch(alertsProvider).maybeWhen(
          data: (items) => items
              .where((a) =>
                  a.tier == RiskTier.critical || a.tier == RiskTier.high)
              .toList(),
          orElse: () => const <Alert>[],
        );

    return PopupMenuButton<String>(
      tooltip: 'High-risk alerts',
      position: PopupMenuPosition.under,
      onSelected: (_) => context.go('/entities'),
      itemBuilder: (_) => highRisk.isEmpty
          ? [
              const PopupMenuItem(
                  enabled: false, child: Text('No high-risk alerts')),
            ]
          : [
              for (final a in highRisk)
                PopupMenuItem(
                  value: a.clientId,
                  child: Row(children: [
                    HugeIcon(icon: HugeIcons.strokeRoundedAlert01,
                        size: 18, color: AppTheme.severityHigh),
                    const SizedBox(width: 10),
                    Flexible(
                        child: Text('${a.name} · ${a.tier.label}',
                            overflow: TextOverflow.ellipsis)),
                  ]),
                ),
            ],
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            HugeIcon(icon: HugeIcons.strokeRoundedNotification01, size: 24, color: scheme.onSurfaceVariant),
            if (highRisk.isNotEmpty)
              Positioned(
                top: -2,
                right: -2,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                      color: scheme.error, shape: BoxShape.circle),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _TopNavItem extends StatelessWidget {
  final List<List<dynamic>> icon;
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _TopNavItem({
    required this.icon,
    required this.label,
    required this.onTap,
    this.isSelected = false,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Container(
        decoration: BoxDecoration(
          border: Border(
              bottom: BorderSide(
                  color: isSelected ? scheme.primary : Colors.transparent,
                  width: 2)),
        ),
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 20),
            child: Row(
              children: [
                HugeIcon(icon: icon,
                    size: 20,
                    color:
                        isSelected ? scheme.primary : scheme.onSurfaceVariant),
                const SizedBox(width: 8),
                Text(
                  label,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        color: isSelected
                            ? scheme.primary
                            : scheme.onSurfaceVariant,
                        fontWeight:
                            isSelected ? FontWeight.w600 : FontWeight.w500,
                      ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
