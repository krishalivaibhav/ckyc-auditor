import 'package:flutter/material.dart';

/// A confirm dialog with an optional free-text note, shared by the reviewer
/// decision flows (blacklist / dismiss an entity, approve / deny a SAR). The
/// note rides along into the append-only audit trail.
///
/// Returns the note on confirm (empty string if the reviewer left it blank),
/// or null if they cancelled.
Future<String?> promptDecision(
  BuildContext context, {
  required String title,
  required String message,
  required String confirmLabel,
  bool danger = false,
}) {
  final controller = TextEditingController();
  return showDialog<String>(
    context: context,
    builder: (_) => AlertDialog(
      title: Text(title),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(message),
          const SizedBox(height: 16),
          TextField(
            controller: controller,
            maxLines: 3,
            autofocus: true,
            decoration: const InputDecoration(
              labelText: 'Note (optional)',
              border: OutlineInputBorder(),
            ),
          ),
        ],
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel')),
        FilledButton(
          onPressed: () => Navigator.pop(context, controller.text),
          style: danger
              ? FilledButton.styleFrom(backgroundColor: const Color(0xFFDC2626))
              : null,
          child: Text(confirmLabel),
        ),
      ],
    ),
  );
}
