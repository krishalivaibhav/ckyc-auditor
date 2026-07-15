import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // Data comes from the local read API over ckyc.db (see lib/core/api.dart and
  // api/server.py). Nothing to initialise at boot — the repository connects
  // lazily on the first request.
  runApp(const ProviderScope(child: TechMkycApp()));
}
