import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/theme.dart';

class TimelineTile extends StatelessWidget {
  final DateTime date;
  final String title;
  final String? excerpt;
  final String? sourceUrl;
  final String? severity;
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
                width: 16, // Larger timeline dot
                height: 16,
                margin: const EdgeInsets.only(top: 4),
                decoration: BoxDecoration(
                  color: dotColor,
                  shape: BoxShape.circle,
                  border: Border.all(color: scheme.surface, width: 4),
                  boxShadow: [
                    BoxShadow(
                      color: dotColor.withValues(alpha: 0.4),
                      blurRadius: 8,
                      offset: const Offset(0, 2),
                    )
                  ],
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: scheme.outlineVariant.withValues(alpha: 0.4),
                  ),
                ),
            ],
          ),
          const SizedBox(width: 24), // Expanded gap between line and text
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(bottom: isLast ? 0 : 40), // Vastly increased gap between timeline items
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(DateFormat('d MMM yyyy, HH:mm').format(date.toLocal()),
                      style: TextStyle(
                          fontSize: 13,
                          color: scheme.onSurfaceVariant,
                          letterSpacing: 0.3,
                          fontWeight: FontWeight.w600)),
                  const SizedBox(height: 6),
                  Text(title,
                      style: const TextStyle(
                          fontSize: 16, fontWeight: FontWeight.w700)),
                  if (excerpt != null) ...[
                    const SizedBox(height: 8),
                    Text(excerpt!,
                        style: TextStyle(
                            fontSize: 14.5,
                            height: 1.5,
                            color: scheme.onSurfaceVariant)),
                  ],
                  if (sourceUrl != null) ...[
                    const SizedBox(height: 12),
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
      borderRadius: BorderRadius.circular(4), // Ripple effect constraint
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 2.0),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.link, size: 14, color: scheme.primary),
            const SizedBox(width: 6),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 320),
              child: Text(url,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w500,
                      color: scheme.primary,
                      decoration: TextDecoration.underline,
                      decorationColor: scheme.primary.withValues(alpha: 0.5))),
            ),
          ],
        ),
      ),
    );
  }
}