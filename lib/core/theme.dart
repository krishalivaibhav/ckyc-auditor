import 'package:flutter/material.dart';
import 'package:hugeicons/hugeicons.dart';

class AppTheme {
  AppTheme._();

  static const Color severityLow = Color(0xFF10B981); // emerald-500
  static const Color severityMedium = Color(0xFFF59E0B); // amber-500
  static const Color severityHigh = Color(0xFFEF4444); // red-500
  static const Color severityUnknown = Color(0xFF6B7280); // gray-500

  static Color severityColor(String? severity) {
    switch (severity) {
      case 'low': return severityLow;
      case 'medium': return severityMedium;
      case 'high': return severityHigh;
      default: return severityUnknown;
    }
  }

  static List<List<dynamic>> severityIcon(String? severity) {
    switch (severity) {
      case 'low': return HugeIcons.strokeRoundedCheckmarkCircle01;
      case 'medium': return HugeIcons.strokeRoundedAlert01;
      case 'high': return HugeIcons.strokeRoundedShield01;
      default: return HugeIcons.strokeRoundedHelpCircle;
    }
  }

  static Color verdictColor(String? verdict) {
    switch (verdict) {
      case 'confirmed_match': return severityHigh;
      case 'needs_review': return severityMedium;
      case 'false_positive': return severityLow;
      default: return severityUnknown;
    }
  }

  static String verdictLabel(String? verdict) {
    switch (verdict) {
      case 'confirmed_match': return 'Confirmed match';
      case 'needs_review': return 'Needs review';
      case 'false_positive': return 'False positive';
      default: return 'Unscreened';
    }
  }

  /// Placeholder composite risk index (0–100), derived from severity so the
  /// watchlist and detail page show one consistent number. Swap for the real
  /// backend score once the scoring step exists (see the target-flow notes).
  static double mockRiskScore(String severity) {
    switch (severity) {
      case 'high': return 94.2;
      case 'medium': return 65.3;
      case 'low': return 21.8;
      default: return 0.0;
    }
  }

  static const Map<String, String> _countryNames = {
    'AE': 'United Arab Emirates', 'RU': 'Russia', 'ZA': 'South Africa',
    'NG': 'Nigeria', 'SG': 'Singapore', 'IT': 'Italy', 'LB': 'Lebanon',
    'GB': 'United Kingdom', 'US': 'United States', 'IN': 'India',
  };

  /// Friendly country name for an ISO-3166 alpha-2 code, falling back to the
  /// raw code (then 'Unknown' when absent).
  static String countryName(String? code) =>
      code == null ? 'Unknown' : (_countryNames[code] ?? code);

  static ThemeData light() => _base(Brightness.light);
  static ThemeData dark() => _base(Brightness.dark);

  static ThemeData _base(Brightness brightness) {
    final isDark = brightness == Brightness.dark;
    
    final colorScheme = ColorScheme(
      brightness: brightness,
      primary: isDark ? const Color(0xFF60A5FA) : const Color(0xFF5932EA),
      onPrimary: isDark ? const Color(0xFF00174B) : const Color(0xFFFFFFFF),
      primaryContainer: isDark ? const Color(0xFF003EA8) : const Color(0xFFEAE4FF),
      onPrimaryContainer: isDark ? const Color(0xFFDBE1FF) : const Color(0xFF1A0063),
      secondary: isDark ? const Color(0xFFB7C8E1) : const Color(0xFF605A71),
      onSecondary: isDark ? const Color(0xFF0B1C30) : const Color(0xFFFFFFFF),
      secondaryContainer: isDark ? const Color(0xFF38485D) : const Color(0xFFE6DFF9),
      onSecondaryContainer: isDark ? const Color(0xFFD3E4FE) : const Color(0xFF1D172B),
      tertiary: isDark ? const Color(0xFFFFB59D) : const Color(0xFF7E525D),
      onTertiary: isDark ? const Color(0xFF390C00) : const Color(0xFFFFFFFF),
      tertiaryContainer: isDark ? const Color(0xFF832700) : const Color(0xFFFFD9E2),
      onTertiaryContainer: isDark ? const Color(0xFFFFDBD0) : const Color(0xFF31101B),
      error: isDark ? const Color(0xFFFFB4AB) : const Color(0xFFBA1A1A),
      onError: isDark ? const Color(0xFF690005) : const Color(0xFFFFFFFF),
      errorContainer: isDark ? const Color(0xFF93000A) : const Color(0xFFFFDAD6),
      onErrorContainer: isDark ? const Color(0xFFFFDAD6) : const Color(0xFF410002),
      surface: isDark ? const Color(0xFF0A0A0C) : const Color(0xFFFAFBFF),
      onSurface: isDark ? const Color(0xFFFFFFFF) : const Color(0xFF1C1B20),
      surfaceContainerHighest: isDark ? const Color(0xFF16161A) : const Color(0xFFE6E0EC),
      onSurfaceVariant: isDark ? const Color(0xFFC2C6D9) : const Color(0xFF48454E),
      outline: isDark ? const Color(0xFF8C90A4) : const Color(0xFF79757F),
      outlineVariant: isDark ? const Color(0xFF424656) : const Color(0xFFC9C4D0),
    );

    final textTheme = TextTheme(
      displayLarge: const TextStyle(fontFamily: 'Geist', fontSize: 48, fontWeight: FontWeight.w600, letterSpacing: -0.02, height: 56/48),
      headlineLarge: const TextStyle(fontFamily: 'Geist', fontSize: 32, fontWeight: FontWeight.w600, letterSpacing: -0.02, height: 40/32),
      headlineMedium: const TextStyle(fontFamily: 'Geist', fontSize: 20, fontWeight: FontWeight.w500, letterSpacing: -0.01, height: 28/20),
      bodyLarge: const TextStyle(fontFamily: 'Inter', fontSize: 16, fontWeight: FontWeight.w400, height: 24/16),
      bodyMedium: const TextStyle(fontFamily: 'Inter', fontSize: 14, fontWeight: FontWeight.w400, height: 20/14),
      labelMedium: const TextStyle(fontFamily: 'Geist', fontSize: 12, fontWeight: FontWeight.w500, letterSpacing: 0.02, height: 16/12),
      labelSmall: const TextStyle(fontFamily: 'Geist Mono', fontSize: 12, fontWeight: FontWeight.w400, height: 16/12), // mono-sm
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: colorScheme.surface,
      textTheme: textTheme,
      cardTheme: CardThemeData(
        elevation: 0,
        clipBehavior: Clip.antiAlias,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: isDark ? Colors.white.withValues(alpha: 0.05) : colorScheme.outlineVariant),
        ),
        color: isDark ? const Color(0xFF16161A) : const Color(0xFFFFFFFF),
      ),
      appBarTheme: AppBarTheme(
        centerTitle: false,
        backgroundColor: colorScheme.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        iconTheme: IconThemeData(color: colorScheme.onSurfaceVariant),
      ),
      navigationRailTheme: NavigationRailThemeData(
        backgroundColor: isDark ? const Color(0xFF0A0A0C) : const Color(0xFFFFFFFF),
        selectedIconTheme: IconThemeData(color: colorScheme.primary),
        unselectedIconTheme: IconThemeData(color: colorScheme.onSurfaceVariant),
        selectedLabelTextStyle: textTheme.labelMedium?.copyWith(color: colorScheme.primary),
        unselectedLabelTextStyle: textTheme.labelMedium?.copyWith(color: colorScheme.onSurfaceVariant),
      ),
    );
  }
}
