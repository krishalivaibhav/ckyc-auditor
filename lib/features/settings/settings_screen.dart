import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/repository.dart';

/// Settings — currently the risk-alert email. The reviewer enters a Gmail (or
/// any) address; the backend emails it whenever a HIGH or CRITICAL entity is
/// hit (in the demo, that's the +15-month time skip escalating to CRITICAL).
class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(alertConfigProvider);
    return Scaffold(
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 640),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Settings',
                    style: Theme.of(context)
                        .textTheme
                        .headlineLarge
                        ?.copyWith(fontWeight: FontWeight.w700, fontSize: 36)),
                const SizedBox(height: 24),
                async.when(
                  loading: () => const Padding(
                      padding: EdgeInsets.all(40),
                      child: Center(child: CircularProgressIndicator())),
                  error: (e, _) => _ErrorCard(message: '$e'),
                  data: (cfg) => _AlertCard(config: cfg),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AlertCard extends ConsumerStatefulWidget {
  final AlertConfig config;
  const _AlertCard({required this.config});

  @override
  ConsumerState<_AlertCard> createState() => _AlertCardState();
}

class _AlertCardState extends ConsumerState<_AlertCard> {
  late final TextEditingController _ctrl =
      TextEditingController(text: widget.config.email ?? '');
  bool _saving = false;
  bool _testing = false;

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  bool _valid(String s) {
    final t = s.trim();
    return t.contains('@') && t.contains('.') && !t.contains(' ');
  }

  void _snack(String msg) =>
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));

  Future<void> _save() async {
    final email = _ctrl.text.trim();
    if (!_valid(email)) {
      _snack('Enter a valid email address.');
      return;
    }
    setState(() => _saving = true);
    try {
      await ref.read(repositoryProvider).setAlertEmail(email);
      ref.invalidate(alertConfigProvider);
      if (mounted) _snack('Alert recipient saved: $email');
    } catch (e) {
      if (mounted) _snack('Could not save: $e');
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _test() async {
    final email = _ctrl.text.trim();
    if (!_valid(email)) {
      _snack('Enter a valid email address first.');
      return;
    }
    setState(() => _testing = true);
    try {
      await ref.read(repositoryProvider).sendTestAlert(email: email);
      if (mounted) _snack('Test alert sent to $email — check the inbox.');
    } catch (e) {
      if (mounted) _snack('Test failed: $e');
    } finally {
      if (mounted) setState(() => _testing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final isDemo = ref.watch(isDemoModeProvider);
    final cfg = widget.config;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: Theme.of(context).brightness == Brightness.dark
            ? const Color(0xFF16161A)
            : Colors.white,
        borderRadius: BorderRadius.circular(18),
        border:
            Border.all(color: scheme.outlineVariant.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.notifications_active_outlined,
                size: 20, color: scheme.primary),
            const SizedBox(width: 10),
            Text('Risk alert email',
                style: Theme.of(context)
                    .textTheme
                    .titleMedium
                    ?.copyWith(fontWeight: FontWeight.w700)),
          ]),
          const SizedBox(height: 8),
          Text(
              'Get an email the moment a HIGH or CRITICAL entity is hit. In the '
              'test-mode demo, the alert fires when the +15-month time skip '
              'escalates the case to CRITICAL.',
              style: TextStyle(color: scheme.onSurfaceVariant, height: 1.5)),
          const SizedBox(height: 20),
          TextField(
            controller: _ctrl,
            keyboardType: TextInputType.emailAddress,
            decoration: InputDecoration(
              labelText: 'Recipient email',
              hintText: 'name@example.com',
              prefixIcon: const Icon(Icons.email_outlined),
              border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12)),
            ),
            onSubmitted: (_) => _save(),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 12,
            children: [
              FilledButton.icon(
                onPressed: _saving ? null : _save,
                icon: _saving
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.save_outlined, size: 18),
                label: const Text('Save'),
              ),
              OutlinedButton.icon(
                onPressed: (_testing || isDemo) ? null : _test,
                icon: _testing
                    ? const SizedBox(
                        width: 16,
                        height: 16,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.send_outlined, size: 18),
                label: const Text('Send test email'),
              ),
            ],
          ),
          const SizedBox(height: 20),
          _StatusRow(config: cfg, isDemo: isDemo),
        ],
      ),
    );
  }
}

class _StatusRow extends StatelessWidget {
  final AlertConfig config;
  final bool isDemo;
  const _StatusRow({required this.config, required this.isDemo});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final (color, icon, text) = switch (null) {
      _ when isDemo => (
          const Color(0xFF6B7280),
          Icons.info_outline,
          'Offline demo — email sending needs the backend running.'
        ),
      _ when !config.smtpConfigured => (
          const Color(0xFFF59E0B),
          Icons.warning_amber_outlined,
          'Sender not configured — set ALERT_SMTP_USER / ALERT_SMTP_PASS in the '
              'backend .env.'
        ),
      _ when !config.hasRecipient => (
          const Color(0xFFF59E0B),
          Icons.warning_amber_outlined,
          'No recipient saved yet — alerts are off.'
        ),
      _ => (
          const Color(0xFF10B981),
          Icons.check_circle_outline,
          'Alerts are on — HIGH/CRITICAL hits will email ${config.email}.'
        ),
    };
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.35)),
      ),
      child: Row(children: [
        Icon(icon, size: 18, color: color),
        const SizedBox(width: 12),
        Expanded(
            child: Text(text,
                style: TextStyle(
                    fontSize: 13,
                    height: 1.4,
                    color: scheme.onSurface,
                    fontWeight: FontWeight.w500))),
      ]),
    );
  }
}

class _ErrorCard extends StatelessWidget {
  final String message;
  const _ErrorCard({required this.message});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: scheme.errorContainer.withValues(alpha: 0.3),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(children: [
        Icon(Icons.error_outline, color: scheme.error),
        const SizedBox(width: 12),
        Expanded(
            child: Text('Could not load settings: $message',
                style: TextStyle(color: scheme.error))),
      ]),
    );
  }
}
