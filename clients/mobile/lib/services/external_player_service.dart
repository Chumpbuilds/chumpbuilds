import 'dart:io';

import 'package:android_intent_plus/android_intent.dart';
import 'package:flutter/foundation.dart';
import 'package:url_launcher/url_launcher.dart';

/// Shared helper for opening a stream URL in VLC (or any external video player).
///
/// On Android a targeted [AndroidIntent] is used so the OS routes directly to
/// the VLC app instead of falling through to the browser.  On other platforms
/// [url_launcher] is used as a fallback.
class ExternalPlayerService {
  ExternalPlayerService._();
  static final ExternalPlayerService instance = ExternalPlayerService._();

  /// Open [url] in VLC (or any external video player).
  ///
  /// Returns `true` if an app was successfully launched, `false` otherwise.
  Future<bool> openInVlc(String url) async {
    if (url.isEmpty) return false;

    if (Platform.isAndroid) {
      // First, try a targeted intent directly at VLC.
      try {
        final intent = AndroidIntent(
          action: 'action_view',
          data: url,
          type: 'video/*',
          package: 'org.videolan.vlc',
        );
        await intent.launch();
        return true;
      } catch (e) {
        debugPrint('[ExternalPlayer] VLC intent failed: $e');
      }

      // VLC is not installed – fall back to a generic video intent.
      try {
        final genericIntent = AndroidIntent(
          action: 'action_view',
          data: url,
          type: 'video/*',
        );
        await genericIntent.launch();
        return true;
      } catch (e) {
        debugPrint('[ExternalPlayer] Generic video intent also failed: $e');
        return false;
      }
    } else {
      // Non-Android: use url_launcher.
      final uri = Uri.parse(url);
      try {
        return await launchUrl(uri, mode: LaunchMode.externalApplication);
      } catch (e) {
        debugPrint('[ExternalPlayer] launchUrl failed: $e');
        return false;
      }
    }
  }
}
