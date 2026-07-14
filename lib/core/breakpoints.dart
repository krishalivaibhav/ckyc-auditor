import 'package:flutter/widgets.dart';

/// Layout breakpoints for the single-codebase web + mobile app.
class Breakpoints {
  Breakpoints._();

  /// At/above this width we use the desktop/tablet layout (NavigationRail +
  /// master-detail). Below it, the phone layout (BottomNavigationBar).
  static const double wide = 900;

  static bool isWide(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= wide;
}
