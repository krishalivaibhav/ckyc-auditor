import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/breakpoints.dart';
import '../data/repository.dart';
import '../features/auth/session.dart';

/// Shell around the primary tabs. NavigationRail on wide (web/tablet),
/// BottomNavigationBar on narrow (phone) — one codebase, two layouts.
class ResponsiveScaffold extends ConsumerWidget {
  final Widget child;
  final String location;

  const ResponsiveScaffold(
      {super.key, required this.child, required this.location});

  static const _tabs = [
    (path: '/entities', icon: Icons.shield_outlined, label: 'Watchlist'),
    (path: '/audit', icon: Icons.receipt_long_outlined, label: 'Audit log'),
  ];

  int get _index => location.startsWith('/audit') ? 1 : 0;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final wide = Breakpoints.isWide(context);
    final demo = ref.watch(isDemoModeProvider);

    final body = Column(
      children: [
        if (demo) const _DemoBanner(),
        Expanded(child: child),
      ],
    );

    if (wide) {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              extended: MediaQuery.sizeOf(context).width >= 1200,
              minExtendedWidth: 200,
              selectedIndex: _index,
              onDestinationSelected: (i) => context.go(_tabs[i].path),
              leading: const _RailHeader(),
              trailing: const Expanded(
                  child: Align(
                      alignment: Alignment.bottomCenter,
                      child: Padding(
                          padding: EdgeInsets.only(bottom: 12),
                          child: _SignOutButton()))),
              destinations: [
                for (final t in _tabs)
                  NavigationRailDestination(
                      icon: Icon(t.icon), label: Text(t.label)),
              ],
            ),
            const VerticalDivider(width: 1),
            Expanded(child: body),
          ],
        ),
      );
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(_tabs[_index].label),
        actions: const [_SignOutButton()],
      ),
      body: body,
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => context.go(_tabs[i].path),
        destinations: [
          for (final t in _tabs)
            NavigationDestination(icon: Icon(t.icon), label: t.label),
        ],
      ),
    );
  }
}

class _RailHeader extends StatelessWidget {
  const _RailHeader();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 8),
      child: Column(
        children: [
          Icon(Icons.verified_user,
              color: Theme.of(context).colorScheme.primary, size: 30),
          const SizedBox(height: 6),
          const Text('TechMKYC',
              style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
        ],
      ),
    );
  }
}

class _SignOutButton extends ConsumerWidget {
  const _SignOutButton();
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return IconButton(
      tooltip: 'Sign out',
      icon: const Icon(Icons.logout),
      onPressed: () => ref.read(sessionProvider.notifier).signOut(),
    );
  }
}

class _DemoBanner extends StatelessWidget {
  const _DemoBanner();
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Material(
      color: scheme.tertiaryContainer,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
        child: Row(
          children: [
            Icon(Icons.info_outline,
                size: 15, color: scheme.onTertiaryContainer),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                'Demo mode — bundled sample data. Set SUPABASE_URL / SUPABASE_ANON_KEY to connect the live backend.',
                style: TextStyle(
                    fontSize: 12, color: scheme.onTertiaryContainer),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
