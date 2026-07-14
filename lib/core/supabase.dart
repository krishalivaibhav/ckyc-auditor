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
  static const String url ='https://gnntfnezidwhmwzhiwcb.supabase.co';
  static const String anonKey ='eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdubnRmbmV6aWR3aG13emhpd2NiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQwMDk5MDMsImV4cCI6MjA5OTU4NTkwM30.4PCYkC4JTWm--SoCXDLCu1QCgpBkTSdKVkTh0CC-0mQ';

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
