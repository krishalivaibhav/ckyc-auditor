import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../models/models.dart';

/// A single citation backing a claim in the SAR draft. The whole point of the
/// challenge: every claim traces to a source the reviewer can open.
class CitationCard extends StatelessWidget {
  final Citation citation;
  final int index;

  const CitationCard({super.key, required this.citation, required this.index});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                CircleAvatar(
                  radius: 11,
                  backgroundColor: scheme.primaryContainer,
                  child: Text('$index',
                      style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w700,
                          color: scheme.onPrimaryContainer)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(citation.claim,
                      style: const TextStyle(
                          fontSize: 14, fontWeight: FontWeight.w600)),
                ),
              ],
            ),
            if (citation.excerpt != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: scheme.surfaceContainerHighest.withValues(alpha: 0.5),
                  borderRadius: BorderRadius.circular(8),
                  border: Border(
                      left: BorderSide(color: scheme.primary, width: 3)),
                ),
                child: Text('“${citation.excerpt}”',
                    style: TextStyle(
                        fontSize: 13,
                        fontStyle: FontStyle.italic,
                        color: scheme.onSurfaceVariant)),
              ),
            ],
            if (citation.sourceUrl != null) ...[
              const SizedBox(height: 8),
              InkWell(
                onTap: () => launchUrl(Uri.parse(citation.sourceUrl!),
                    mode: LaunchMode.externalApplication),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.open_in_new, size: 13, color: scheme.primary),
                    const SizedBox(width: 4),
                    Flexible(
                      child: Text(citation.sourceUrl!,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                              fontSize: 12.5,
                              color: scheme.primary,
                              decoration: TextDecoration.underline)),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
