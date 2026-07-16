import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/auth/session.dart';
import '../features/auth/login_screen.dart';
import '../features/entities/entity_list_screen.dart';
import '../features/entities/entity_detail_screen.dart';
import '../features/report/report_screen.dart';
import '../features/report/reports_screen.dart';
import '../features/settings/settings_screen.dart';
import '../features/audit/audit_log_screen.dart';
import '../widgets/responsive_scaffold.dart';

/// go_router configuration. Redirects to /login until a reviewer name is set
/// (the reviewer name becomes the audit-log `actor`).
final routerProvider = Provider<GoRouter>((ref) {
  final session = ref.watch(sessionProvider);

  return GoRouter(
    initialLocation: '/entities',
    redirect: (context, state) {
      final loggedIn = session.reviewerName != null;
      final atLogin = state.matchedLocation == '/login';
      if (!loggedIn) return atLogin ? null : '/login';
      if (atLogin) return '/entities';
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (_, _) => const LoginScreen()),
      // Shell keeps the nav rail / bottom bar around the primary tabs.
      ShellRoute(
        builder: (context, state, child) =>
            ResponsiveScaffold(location: state.uri.path, child: child),
        routes: [
          GoRoute(
            path: '/entities',
            builder: (_, _) => const EntityListScreen(),
          ),
          GoRoute(path: '/audit', builder: (_, _) => const AuditLogScreen()),
          GoRoute(path: '/reports', builder: (_, _) => const ReportsScreen()),
          GoRoute(path: '/settings', builder: (_, _) => const SettingsScreen()),
        ],
      ),
      GoRoute(
        path: '/entities/:id',
        builder: (_, state) =>
            EntityDetailScreen(clientId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: '/entities/:id/report',
        builder: (_, state) =>
            ReportScreen(clientId: state.pathParameters['id']!),
      ),
    ],
  );
});
