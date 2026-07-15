import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/repository.dart';

/// LIVE / TEST switch (the judges' demo control).
///
/// LIVE serves whatever the real agent pipeline has persisted. Flipping to
/// TEST kicks off the scripted scenario on the backend — the terminal narrates
/// the news agent → ambiguity agent → investigation agent flow — and when the
/// call returns every screen re-reads from the demo sink, so the queue
/// refreshes down to the single scenario entity.
class ModeToggle extends ConsumerStatefulWidget {
  const ModeToggle({super.key});

  @override
  ConsumerState<ModeToggle> createState() => _ModeToggleState();
}

class _ModeToggleState extends ConsumerState<ModeToggle> {
  bool _switching = false;

  Future<void> _switch(String mode) async {
    if (_switching) return;
    setState(() => _switching = true);
    final messenger = ScaffoldMessenger.of(context);
    if (mode == 'test') {
      messenger.showSnackBar(const SnackBar(
          duration: Duration(seconds: 6),
          content: Text('Running the scenario — watch the backend terminal: '
              'news agent → ambiguity agent → investigation agent…')));
    }
    try {
      await ref.read(repositoryProvider).setMode(mode);
      if (mounted) {
        messenger.showSnackBar(SnackBar(
            content: Text(mode == 'test'
                ? 'Test scenario ready — 1 entity in the queue'
                : 'Back to live data')));
      }
    } catch (e) {
      if (mounted) {
        messenger.showSnackBar(
            SnackBar(content: Text('Mode switch failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _switching = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final status = ref.watch(demoStatusProvider).maybeWhen(
        data: (s) => s, orElse: () => DemoStatus.live);

    Widget seg(String label, String mode, {required bool selected}) {
      final color = mode == 'test' ? const Color(0xFFF59E0B) : scheme.primary;
      return InkWell(
        onTap: selected ? null : () => _switch(mode),
        borderRadius: BorderRadius.circular(7),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
          decoration: BoxDecoration(
            color: selected ? color.withValues(alpha: 0.15) : null,
            borderRadius: BorderRadius.circular(7),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Container(
              width: 7,
              height: 7,
              decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: selected ? color : scheme.outlineVariant),
            ),
            const SizedBox(width: 6),
            Text(label,
                style: TextStyle(
                    fontSize: 12.5,
                    fontWeight: selected ? FontWeight.w800 : FontWeight.w500,
                    color: selected ? color : scheme.onSurfaceVariant)),
          ]),
        ),
      );
    }

    return Container(
      height: 38,
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(9),
        border:
            Border.all(color: scheme.outlineVariant.withValues(alpha: 0.5)),
      ),
      child: _switching
          ? const Padding(
              padding: EdgeInsets.symmetric(horizontal: 22),
              child: Center(
                  child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2))),
            )
          : Row(mainAxisSize: MainAxisSize.min, children: [
              seg('LIVE', 'live', selected: !status.isTest),
              seg('TEST', 'test', selected: status.isTest),
            ]),
    );
  }
}
