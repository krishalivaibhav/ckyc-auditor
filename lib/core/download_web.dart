import 'dart:convert';
import 'dart:js_interop';

import 'package:web/web.dart' as web;

/// Save [content] to the user's downloads as [filename] via a Blob URL and a
/// programmatically-clicked anchor — the standard browser download path.
void downloadFile(String filename, String content, String mime) {
  final bytes = utf8.encode(content).toJS;
  final blob = web.Blob([bytes].toJS, web.BlobPropertyBag(type: mime));
  final url = web.URL.createObjectURL(blob);
  final anchor = web.document.createElement('a') as web.HTMLAnchorElement
    ..href = url
    ..download = filename
    ..style.display = 'none';
  web.document.body?.appendChild(anchor);
  anchor.click();
  anchor.remove();
  web.URL.revokeObjectURL(url);
}

/// Open [html] in a new tab; the document self-prints on load, so the user
/// lands straight on the browser print dialog and can "Save as PDF".
void openHtmlForPrint(String html) {
  final blob = web.Blob([html.toJS].toJS, web.BlobPropertyBag(type: 'text/html'));
  final url = web.URL.createObjectURL(blob);
  web.window.open(url, '_blank');
  // The object URL stays valid for the new tab; the browser reclaims it when
  // that tab is closed.
}
