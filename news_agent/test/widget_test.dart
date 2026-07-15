// Smoke test: the app boots to the reviewer login screen (demo mode, no
// Supabase configured), and signing in reveals the watchlist.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:wkyc/app.dart';

void main() {
  testWidgets('boots to login, then shows the watchlist after sign-in',
      (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: TechMkycApp()));
    await tester.pumpAndSettle();

    // Login gate.
    expect(find.text('Enter console'), findsOneWidget);

    await tester.enterText(find.byType(TextField).first, 'Test Reviewer');
    await tester.tap(find.text('Enter console'));
    await tester.pumpAndSettle();

    // Watchlist loads bundled demo entities.
    expect(find.text('Monitored entities'), findsOneWidget);
    expect(find.text('Viktor A. Kozlov'), findsWidgets);
  });
}
