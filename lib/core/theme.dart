import 'package:flutter/material.dart';

/// App theme + the severity/status palette.
///
/// Severity colors come from the dataviz status palette (fixed, never themed):
/// good/warning/critical. They are always shown WITH an icon + text label
/// (see [RiskBadge]) so meaning is never carried by color alone — required
/// because warning/serious are sub-3:1 on a light surface by design.
class AppTheme {
  AppTheme._();

  static const Color _seed = Color(0xFF2A78D6); // dataviz series-1 blue

  // Status palette (severity). Same hues in both modes; contrast holds because
  // they always sit next to a label + icon.
  static const Color severityLow = Color(0xFF0CA30C); // good
  static const Color severityMedium = Color(0xFFFAB219); // warning
  static const Color severityHigh = Color(0xFFD03B3B); // critical
  static const Color severityUnknown = Color(0xFF8A8A85);

  static Color severityColor(String? severity) {
    switch (severity) {
      case 'low':
        return severityLow;
      case 'medium':
        return severityMedium;
      case 'high':
        return severityHigh;
      default:
        return severityUnknown;
    }
  }

  static IconData severityIcon(String? severity) {
    switch (severity) {
      case 'low':
        return Icons.check_circle_outline;
      case 'medium':
        return Icons.warning_amber_rounded;
      case 'high':
        return Icons.gpp_bad_outlined;
      default:
        return Icons.help_outline;
    }
  }

  // Verdict → color/label, reusing the status palette semantics.
  static Color verdictColor(String? verdict) {
    switch (verdict) {
      case 'confirmed_match':
        return severityHigh;
      case 'needs_review':
        return severityMedium;
      case 'false_positive':
        return severityLow;
      default:
        return severityUnknown;
    }
  }

  static String verdictLabel(String? verdict) {
    switch (verdict) {
      case 'confirmed_match':
        return 'Confirmed match';
      case 'needs_review':
        return 'Needs review';
      case 'false_positive':
        return 'False positive';
      default:
        return 'Unscreened';
    }
  }

  static ThemeData light() => _base(Brightness.light);
  static ThemeData dark() => _base(Brightness.dark);

  static ThemeData _base(Brightness brightness) {
    final scheme = ColorScheme.fromSeed(
      seedColor: _seed,
      brightness: brightness,
    );
    return ThemeData(
      useMaterial3: true,
      colorScheme: scheme,
      scaffoldBackgroundColor: brightness == Brightness.dark
          ? const Color(0xFF141413)
          : const Color(0xFFF7F7F5),
      cardTheme: CardThemeData(
        elevation: 0,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14),
          side: BorderSide(color: scheme.outlineVariant),
        ),
      ),
      appBarTheme: AppBarTheme(
        centerTitle: false,
        backgroundColor: scheme.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
      ),
      chipTheme: const ChipThemeData(
        side: BorderSide.none,
        padding: EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      ),
    );
  }
}
