// Tiny cross-platform file-download / print bridge.
//
// The dashboard runs on the web (`flutter run -d chrome`), where a real file
// save needs the browser's Blob + anchor dance. Non-web builds get a stub that
// throws, so callers should wrap these in try/catch and surface a snackbar.
//
//   downloadFile      — save `content` as `filename` with the given MIME type.
//   openHtmlForPrint  — open a self-printing HTML document in a new tab (the
//                       user picks "Save as PDF" from the browser print dialog).
export 'download_stub.dart' if (dart.library.js_interop) 'download_web.dart';
