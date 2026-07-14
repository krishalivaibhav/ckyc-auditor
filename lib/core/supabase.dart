import 'package:supabase_flutter/supabase_flutter.dart';

/// Supabase connection config.
///
/// Pass credentials at run time so keys never live in source control:
///   flutter run -d chrome \
///     --dart-define=SUPABASE_URL=https://xxxx.supabase.co \
///     --dart-define=SUPABASE_ANON_KEY=eyJhbGci...
///
/// The anon key is safe to ship in a client — Row Level Security (see
/// migration 0002) is what actually protects the data.
class SupabaseConfig {
  static const String url =
      String.fromEnvironment('SUPABASE_URL', defaultValue: '');
  static const String anonKey =
      String.fromEnvironment('SUPABASE_ANON_KEY', defaultValue: '');

  /// True when both values were provided. When false the app runs against
  /// [DemoData] so the UI is still fully explorable without a backend.
  static bool get isConfigured => url.isNotEmpty && anonKey.isNotEmpty;
}

/// Initialise Supabase. No-ops (returns false) when unconfigured so the app
/// can fall back to bundled demo data instead of crashing.
Future<bool> initSupabase() async {
  if (!SupabaseConfig.isConfigured) return false;
  await Supabase.initialize(
    url: SupabaseConfig.url,
    // Accepts either the legacy "anon" key or a new publishable key.
    publishableKey: SupabaseConfig.anonKey,
  );
  return true;
}

/// Convenience accessor. Only valid after a successful [initSupabase].
SupabaseClient get supabase => Supabase.instance.client;
