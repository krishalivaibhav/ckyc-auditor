import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';

import '../core/theme.dart';

class RiskBadge extends StatelessWidget {
  final String severity;
  final bool compact;

  const RiskBadge({super.key, required this.severity, this.compact = false});

  @override
  Widget build(BuildContext context) {
    if (severity == 'none') {
      return _chip(context, AppTheme.severityUnknown, 'No risk', HugeIcons.strokeRoundedCheckmarkCircle01);
    }
    final color = AppTheme.severityColor(severity);
    final icon = AppTheme.severityIcon(severity);
    final label = '${severity[0].toUpperCase()}${severity.substring(1)} Risk';
    return _chip(context, color, label, icon);
  }

  Widget _chip(BuildContext context, Color color, String label, List<List<dynamic>> icon) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: isDark ? 0.2 : 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: isDark ? 0.3 : 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          HugeIcon(icon: icon, size: 14, color: color),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.3,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}

class VerdictChip extends StatelessWidget {
  final String? verdict;
  const VerdictChip({super.key, required this.verdict});

  List<List<dynamic>> _verdictIcon(String? verdict) {
    switch (verdict) {
      case 'confirmed_match': return HugeIcons.strokeRoundedShield01;
      case 'needs_review': return HugeIcons.strokeRoundedAlert01;
      case 'false_positive': return HugeIcons.strokeRoundedCheckmarkCircle01;
      default: return HugeIcons.strokeRoundedHelpCircle;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = AppTheme.verdictColor(verdict);
    final label = AppTheme.verdictLabel(verdict);
    final icon = _verdictIcon(verdict);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: isDark ? 0.2 : 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: isDark ? 0.3 : 0.2)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          HugeIcon(icon: icon, size: 14, color: color),
          const SizedBox(width: 6),
          Flexible(
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: color,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 0.3,
              ),
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
