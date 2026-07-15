/// Local read API config.
///
/// The dashboard reads everything from the SQLite sink (`ckyc.db`) through a
/// small Python HTTP server on this machine (see `api/server.py`). A browser
/// cannot open a local SQLite file directly, so that server is the bridge —
/// same role Supabase used to play, but pointed at our own DB on 127.0.0.1.
///
/// Override the base URL at run time if the server runs elsewhere:
///   flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:9000
class ApiConfig {
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8787',
  );

  /// Force the bundled offline fixtures instead of the live API (demo escape
  /// hatch): `--dart-define=USE_DEMO_DATA=true`.
  static const bool useDemoData =
      bool.fromEnvironment('USE_DEMO_DATA', defaultValue: false);
}
