import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/theme.dart';

/// One entry in the evidence/risk timeline, with a severity dot, date, and an
/// optional source link.
class TimelineTile extends StatelessWidget {
  final DateTime date;
  final String title;
  final String? excerpt;
  final String? sourceUrl;
  final String? severity; // colors the dot when present
  final bool isLast;

  const TimelineTile({
    super.key,
    required this.date,
    required this.title,
    this.excerpt,
    this.sourceUrl,
    this.severity,
    this.isLast = false,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final dotColor =
        severity == null ? scheme.primary : AppTheme.severityColor(severity);
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 12,
                height: 12,
                margin: const EdgeInsets.only(top: 3),
                decoration: BoxDecoration(
                  color: dotColor,
                  shape: BoxShape.circle,
                  border: Border.all(color: scheme.surface, width: 2),
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: scheme.outlineVariant,
                  ),
                ),
            ],
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(DateFormat('d MMM yyyy, HH:mm').format(date.toLocal()),
                      style: TextStyle(
                          fontSize: 11.5,
                          color: scheme.onSurfaceVariant,
                          fontWeight: FontWeight.w500)),
                  const SizedBox(height: 2),
                  Text(title,
                      style: const TextStyle(
                          fontSize: 14.5, fontWeight: FontWeight.w600)),
                  if (excerpt != null) ...[
                    const SizedBox(height: 3),
                    Text(excerpt!,
                        style: TextStyle(
                            fontSize: 13, color: scheme.onSurfaceVariant)),
                  ],
                  if (sourceUrl != null) ...[
                    const SizedBox(height: 4),
                    _SourceLink(url: sourceUrl!),
                  ],
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SourceLink extends StatelessWidget {
  final String url;
  const _SourceLink({required this.url});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: () => launchUrl(Uri.parse(url),
          mode: LaunchMode.externalApplication),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.link, size: 13, color: scheme.primary),
          const SizedBox(width: 3),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 320),
            child: Text(url,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                    fontSize: 12,
                    color: scheme.primary,
                    decoration: TextDecoration.underline)),
          ),
        ],
      ),
    );
  }
}
