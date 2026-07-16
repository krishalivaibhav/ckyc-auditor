/// Non-web fallback: there's no browser to drive, so downloading/printing is
/// unsupported. Callers catch this and show a message.
void downloadFile(String filename, String content, String mime) =>
    throw UnsupportedError('File download is only available on the web build.');

void openHtmlForPrint(String html) =>
    throw UnsupportedError('Printing is only available on the web build.');
