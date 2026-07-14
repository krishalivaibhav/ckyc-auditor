import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Lightweight reviewer session. The reviewer name becomes the audit-log
/// `actor` (`human:name`) on every approve/edit/reject. For the hackathon this
/// is a name capture; swap for Supabase Auth users when you need real accounts.
class Session {
  final String? reviewerName;
  const Session({this.reviewerName});
}

class SessionNotifier extends Notifier<Session> {
  @override
  Session build() => const Session();

  void signIn(String name) => state = Session(reviewerName: name.trim());
  void signOut() => state = const Session();
}

final sessionProvider =
    NotifierProvider<SessionNotifier, Session>(SessionNotifier.new);
