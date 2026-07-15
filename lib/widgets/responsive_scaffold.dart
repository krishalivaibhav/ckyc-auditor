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
    (path: '/reports', icon: HugeIcons.strokeRoundedFile01, label: 'Reports'),
    (path: '/settings', icon: HugeIcons.strokeRoundedSettings01, label: 'Settings'),
  ];

  int get _index {
    if (location.startsWith('/audit')) return 1;
    if (location.startsWith('/reports')) return 2;
    if (location.startsWith('/settings')) return 3;
    return 0;
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = Breakpoints.isWide(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final colorScheme = Theme.of(context).colorScheme;

    final body = child;

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

