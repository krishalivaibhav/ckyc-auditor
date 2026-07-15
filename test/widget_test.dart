// Smoke test: the app boots to the reviewer login gate without crashing — this
// exercises the full startup wiring after the Supabase→local-API migration
// (ProviderScope, router, repository provider). It stops at the login gate on
// purpose: the post-login watchlist screens are mid-UI-rewrite and currently
// have layout overflows in the nav shell, tracked separately from the data layer.
//
// Pinned to DemoRepository so it runs offline without api/server.py.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:wkyc/app.dart';
import 'package:wkyc/data/repository.dart';

void main() {
  testWidgets('boots to the reviewer login gate', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1440, 900);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(ProviderScope(
      overrides: [repositoryProvider.overrideWithValue(DemoRepository())],
      child: const TechMkycApp(),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Enter console'), findsOneWidget);
  });
}
