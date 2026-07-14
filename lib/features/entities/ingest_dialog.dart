import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../data/repository.dart';
import '../../models/models.dart';

/// POST /entities from the UI — the ingestion endpoint that generates entity_id.
/// Demonstrates the front door of the pipeline for the demo.
Future<void> showIngestDialog(BuildContext context, WidgetRef ref) async {
  await showDialog<void>(
    context: context,
    builder: (_) => const _IngestDialog(),
  );
}

class _IngestDialog extends ConsumerStatefulWidget {
  const _IngestDialog();
  @override
  ConsumerState<_IngestDialog> createState() => _IngestDialogState();
}

class _IngestDialogState extends ConsumerState<_IngestDialog> {
  final _name = TextEditingController();
  final _nationality = TextEditingController();
  final _dinCin = TextEditingController();
  String _type = 'company';
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _nationality.dispose();
    _dinCin.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_name.text.trim().isEmpty) return;
    setState(() => _busy = true);
    final draft = Entity(
      entityId: '', // server generates
      type: _type,
      name: _name.text.trim(),
      nationality:
          _nationality.text.trim().isEmpty ? null : _nationality.text.trim(),
      dinOrCin: _dinCin.text.trim().isEmpty ? null : _dinCin.text.trim(),
      source: 'client_input',
    );
    try {
      await ref.read(repositoryProvider).ingestEntity(draft);
      if (mounted) Navigator.of(context).pop();
    } catch (e) {
      if (mounted) {
        setState(() => _busy = false);
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Ingest failed: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Ingest entity'),
      content: SizedBox(
        width: 380,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'company', label: Text('Company')),
                ButtonSegment(value: 'person', label: Text('Person')),
              ],
              selected: {_type},
              onSelectionChanged: (s) => setState(() => _type = s.first),
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _name,
              autofocus: true,
              decoration: const InputDecoration(
                  labelText: 'Name', border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _nationality,
              decoration: const InputDecoration(
                  labelText: 'Nationality (ISO-2, optional)',
                  border: OutlineInputBorder()),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _dinCin,
              decoration: const InputDecoration(
                  labelText: 'DIN / CIN (optional)',
                  border: OutlineInputBorder()),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: _busy ? null : () => Navigator.of(context).pop(),
            child: const Text('Cancel')),
        FilledButton(
          onPressed: _busy ? null : _submit,
          child: _busy
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2))
              : const Text('Ingest'),
        ),
      ],
    );
  }
}
