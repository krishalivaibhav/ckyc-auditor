import 'package:flutter/material.dart';

import '../core/theme.dart';

/// Severity chip. Status color is ALWAYS paired with an icon + text label
/// (dataviz rule: status color never carries meaning alone).
class RiskBadge extends StatelessWidget {
  final String severity; // low | medium | high | none
  final bool compact;

  const RiskBadge({super.key, required this.severity, this.compact = false});

  @override
  Widget build(BuildContext context) {
    if (severity == 'none') {
      return _chip(context, AppTheme.severityUnknown, Icons.remove, 'No risk');
    }
    final color = AppTheme.severityColor(severity);
    final icon = AppTheme.severityIcon(severity);
    final label = '${severity[0].toUpperCase()}${severity.substring(1)} risk';
    return _chip(context, color, icon, label);
  }

  Widget _chip(BuildContext context, Color color, IconData icon, String label) {
    return Container(
      padding: EdgeInsets.symmetric(
          horizontal: compact ? 8 : 10, vertical: compact ? 3 : 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: compact ? 14 : 16, color: color),
          const SizedBox(width: 5),
          Text(
            label,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w600,
              fontSize: compact ? 11.5 : 13,
            ),
          ),
        ],
      ),
    );
  }
}

/// Verdict chip (Person 2's output), same icon+label discipline.
class VerdictChip extends StatelessWidget {
  final String? verdict;
  const VerdictChip({super.key, required this.verdict});

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.verdictColor(verdict);
    final label = AppTheme.verdictLabel(verdict);
    final icon = switch (verdict) {
      'confirmed_match' => Icons.gpp_bad_outlined,
      'needs_review' => Icons.pending_actions_outlined,
      'false_positive' => Icons.verified_outlined,
      _ => Icons.help_outline,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 5),
          Text(label,
              style: TextStyle(
                  color: color, fontWeight: FontWeight.w600, fontSize: 13)),
        ],
      ),
    );
  }
}
