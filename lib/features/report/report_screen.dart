import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../data/repository.dart';
import '../../models/models.dart';

/// SAR draft review (Screen 6). Renders the Suspicious Activity Report the
/// investigation agent drafted for a case: section-structured body with inline
/// [EV-nnn] citation chips (tap → the backing evidence), citation coverage, and
/// the claims that were deliberately excluded because they could not be
/// verified. Read from ckyc.db via the case-by-client endpoint.
class ReportScreen extends ConsumerWidget {
  final String clientId;
  const ReportScreen({super.key, required this.clientId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(caseByClientProvider(clientId));
    return Scaffold(
      appBar: AppBar(
        title: const Text('SAR draft'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => context.canPop()
              ? context.pop()
              : context.go('/entities/$clientId'),
        ),
      ),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => Center(child: Text('$e')),
        data: (c) {
          final sar = c?.sar;
          if (c == null || sar == null) {
            return const Center(
                child: Text('No SAR has been drafted for this case yet.'));
          }
          return _Report(kase: c, sar: sar);
        },
      ),
    );
  }
}

class _Report extends StatelessWidget {
  final Case kase;
  final Sar sar;
  const _Report({required this.kase, required this.sar});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final evidenceById = {for (final e in kase.evidence) e.evId: e};

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 820),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _StatusBanner(status: sar.status),
              const SizedBox(height: 18),
              Text('Suspicious Activity Report — draft',
                  style: Theme.of(context)
                      .textTheme
                      .titleLarge
                      ?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 4),
              Text('Subject: ${kase.customer.name}  ·  ${kase.caseId}',
                  style: TextStyle(color: scheme.onSurfaceVariant)),
              const SizedBox(height: 18),
              _CoverageBar(coverage: sar.citationCoverage),
              const SizedBox(height: 20),
              _SarBody(body: sar.body, evidenceById: evidenceById),
              if (sar.unverifiedClaims.isNotEmpty) ...[
                const SizedBox(height: 24),
                _ExcludedClaims(claims: sar.unverifiedClaims),
              ],
              const SizedBox(height: 24),
              _CitationLegend(evidence: kase.evidence),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }
}

// ── the SAR body, with section headings + inline [EV-nnn] chips ──────────────

class _SarBody extends StatelessWidget {
  final String body;
  final Map<String, Evidence> evidenceById;
  const _SarBody({required this.body, required this.evidenceById});

  static final _heading = RegExp(r'^[A-Z][A-Z0-9 \-/&]+$');

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final lines = body.split('\n');
    final blocks = <Widget>[];

    for (final raw in lines) {
      final line = raw.trim();
      if (line.isEmpty) continue;
      if (_heading.hasMatch(line) && line.length < 48) {
        blocks.add(Padding(
          padding: EdgeInsets.only(top: blocks.isEmpty ? 0 : 20, bottom: 8),
          child: Text(line,
              style: TextStyle(
                  fontSize: 12.5,
                  letterSpacing: 1.0,
                  fontWeight: FontWeight.w800,
                  color: scheme.primary)),
        ));
      } else {
        blocks.add(Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: _CitedText(text: line, evidenceById: evidenceById),
        ));
      }
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: blocks,
      ),
    );
  }
}

/// A paragraph whose inline [EV-nnn] markers become tappable chips.
class _CitedText extends StatelessWidget {
  final String text;
  final Map<String, Evidence> evidenceById;
  const _CitedText({required this.text, required this.evidenceById});

  static final _marker = RegExp(r'\[(EV-[A-Za-z0-9\-]+)\]');

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final spans = <InlineSpan>[];
    var last = 0;
    for (final m in _marker.allMatches(text)) {
      if (m.start > last) {
        spans.add(TextSpan(text: text.substring(last, m.start)));
      }
      final evId = m.group(1)!;
      spans.add(WidgetSpan(
        alignment: PlaceholderAlignment.middle,
        child: _InlineCite(
            evId: evId, evidence: evidenceById[evId]),
      ));
      last = m.end;
    }
    if (last < text.length) spans.add(TextSpan(text: text.substring(last)));

    return Text.rich(
      TextSpan(
          style: TextStyle(
              fontSize: 14.5, height: 1.6, color: scheme.onSurface),
          children: spans),
    );
  }
}

class _InlineCite extends StatelessWidget {
  final String evId;
  final Evidence? evidence;
  const _InlineCite({required this.evId, this.evidence});

  Color _accent(BuildContext context) {
    switch (evidence?.column) {
      case EvidenceColumn.confirmed:
        return const Color(0xFF10B981);
      case EvidenceColumn.correlated:
        return const Color(0xFFF59E0B);
      case EvidenceColumn.missing:
        return const Color(0xFF6B7280);
      default:
        return Theme.of(context).colorScheme.primary;
    }
  }

  @override
  Widget build(BuildContext context) {
    final color = _accent(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 2),
      child: InkWell(
        borderRadius: BorderRadius.circular(5),
        onTap: () => _showEvidence(context),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.14),
            borderRadius: BorderRadius.circular(5),
            border: Border.all(color: color.withValues(alpha: 0.4)),
          ),
          child: Text(evId,
              style: TextStyle(
                  fontSize: 11.5, fontWeight: FontWeight.w800, color: color)),
        ),
      ),
    );
  }

  void _showEvidence(BuildContext context) {
    final e = evidence;
    showDialog<void>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(evId),
        content: e == null
            ? const Text('This citation has no matching evidence card.')
            : Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(e.claim, style: const TextStyle(fontSize: 14, height: 1.4)),
                  if (e.excerpt != null) ...[
                    const SizedBox(height: 12),
                    Text('“${e.excerpt}”',
                        style: const TextStyle(
                            fontStyle: FontStyle.italic, fontSize: 13)),
                  ],
                  if (e.sourceName != null) ...[
                    const SizedBox(height: 12),
                    Text('Source: ${e.sourceName}',
                        style: TextStyle(
                            fontSize: 12.5,
                            color:
                                Theme.of(context).colorScheme.onSurfaceVariant)),
                  ],
                ],
              ),
        actions: [
          if (e?.sourceUrl != null && e!.sourceUrl!.startsWith('http'))
            TextButton.icon(
              onPressed: () => launchUrl(Uri.parse(e.sourceUrl!),
                  mode: LaunchMode.externalApplication),
              icon: const Icon(Icons.open_in_new, size: 16),
              label: const Text('Open source'),
            ),
          TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close')),
        ],
      ),
    );
  }
}

// ── coverage, excluded claims, legend, status ────────────────────────────────

class _CoverageBar extends StatelessWidget {
  final double coverage;
  const _CoverageBar({required this.coverage});
  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final pct = (coverage * 100).round();
    final color = coverage >= 0.9
        ? const Color(0xFF10B981)
        : coverage >= 0.5
            ? const Color(0xFFF59E0B)
            : const Color(0xFFDC2626);
    return Row(
      children: [
        Icon(Icons.verified_outlined, size: 18, color: color),
        const SizedBox(width: 8),
        Text('Citation coverage',
            style: TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
                color: scheme.onSurface)),
        const SizedBox(width: 12),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(
              value: coverage.clamp(0.0, 1.0),
              minHeight: 8,
              backgroundColor: scheme.surfaceContainerHighest,
              valueColor: AlwaysStoppedAnimation(color),
            ),
          ),
        ),
        const SizedBox(width: 12),
        Text('$pct%',
            style: TextStyle(
                fontSize: 14, fontWeight: FontWeight.w800, color: color)),
      ],
    );
  }
}

class _ExcludedClaims extends StatelessWidget {
  final List<String> claims;
  const _ExcludedClaims({required this.claims});
  @override
  Widget build(BuildContext context) {
    const color = Color(0xFF6B7280);
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: const [
            Icon(Icons.block, size: 17, color: color),
            SizedBox(width: 8),
            Text('Excluded — could not be verified',
                style: TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w800, color: color)),
          ]),
          const SizedBox(height: 10),
          for (final claim in claims)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Padding(
                    padding: EdgeInsets.only(top: 6, right: 8),
                    child: Icon(Icons.remove, size: 12, color: color),
                  ),
                  Expanded(
                      child: Text(claim,
                          style: const TextStyle(fontSize: 13, height: 1.45))),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _CitationLegend extends StatelessWidget {
  final List<Evidence> evidence;
  const _CitationLegend({required this.evidence});
  @override
  Widget build(BuildContext context) {
    if (evidence.isEmpty) return const SizedBox.shrink();
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('EVIDENCE CITED',
            style: TextStyle(
                fontSize: 11.5,
                letterSpacing: 1.0,
                fontWeight: FontWeight.w800,
                color: scheme.onSurfaceVariant)),
        const SizedBox(height: 10),
        for (final e in evidence)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  margin: const EdgeInsets.only(top: 2),
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                      color: scheme.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(5)),
                  child: Text(e.evId,
                      style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          color: scheme.primary)),
                ),
                const SizedBox(width: 10),
                Expanded(
                    child: Text(e.claim,
                        style: TextStyle(
                            fontSize: 13,
                            color: scheme.onSurfaceVariant,
                            height: 1.4))),
              ],
            ),
          ),
      ],
    );
  }
}

class _StatusBanner extends StatelessWidget {
  final String status;
  const _StatusBanner({required this.status});
  @override
  Widget build(BuildContext context) {
    final (color, icon, text) = switch (status) {
      'approved' => (const Color(0xFF10B981), Icons.check_circle,
          'Approved & filed'),
      'denied' =>
        (const Color(0xFFDC2626), Icons.cancel, 'Denied by reviewer'),
      _ => (Theme.of(context).colorScheme.primary, Icons.pending,
          'Draft — pending human review'),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(children: [
        Icon(icon, color: color, size: 18),
        const SizedBox(width: 8),
        Text(text,
            style: TextStyle(color: color, fontWeight: FontWeight.w700)),
      ]),
    );
  }
}
