import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:wkyc/data/repository.dart';
import 'package:wkyc/models/models.dart';

/// Regression test for the time-skip-didn't-refresh bug.
///
/// changesProvider is a StreamProvider; Riverpod does not re-notify dependents
/// when the new AsyncData equals the previous one. The old Stream<void> change
/// stream emitted identical `AsyncData(null)` states, so only the FIRST write
/// event ever triggered a re-fetch — the mode toggle refreshed the UI, but the
/// time skip (the second emission) silently didn't. The stream now carries a
/// monotonically increasing revision, making every event a distinct state.
void main() {
  test('every change event re-fires dependent providers, not just the first',
      () async {
    final repo = DemoRepository();
    var fetches = 0;

    // Mirrors how every screen provider depends on the change stream.
    final probe = FutureProvider<int>((ref) async {
      ref.watch(changesProvider);
      return ++fetches;
    });

    final container = ProviderContainer(
      overrides: [repositoryProvider.overrideWithValue(repo)],
    );
    addTearDown(container.dispose);

    // Keep both alive the way widgets do.
    container.listen(changesProvider, (_, _) {});
    container.listen(probe, (_, _) {});
    await container.read(probe.future);
    expect(fetches, 1);

    // First write — this always worked (loading -> data is a state change).
    await repo.reviewCase(
        caseId: 'case-2001',
        action: EntityDecision.blacklist,
        note: '',
        reviewerName: 't');
    await Future<void>.delayed(Duration.zero);
    await container.read(probe.future);
    expect(fetches, 2, reason: 'first change event must re-fetch');

    // Second write — the time-skip case. With a void stream this NEVER fired.
    await repo.reviewSar(
        caseId: 'case-2001', action: SarDecision.approve, reviewerName: 't');
    await Future<void>.delayed(Duration.zero);
    await container.read(probe.future);
    expect(fetches, 3, reason: 'second change event must re-fetch too');
  });
}
