import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/supabase.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Connects to Supabase when SUPABASE_URL/SUPABASE_ANON_KEY are provided via
  // --dart-define; otherwise the app runs on bundled demo data.
  await initSupabase();
  runApp(const ProviderScope(child: TechMkycApp()));
}
