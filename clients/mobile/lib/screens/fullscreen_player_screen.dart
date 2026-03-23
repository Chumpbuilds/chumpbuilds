import 'package:flutter/material.dart';

import 'android_hls_fullscreen_screen.dart';

/// Full-screen video playback screen.
///
/// Delegates to [AndroidHlsFullscreenScreen] which uses media_kit for
/// cross-platform playback (Android phones, Android TV boxes, iOS, etc.).
class FullscreenPlayerScreen extends StatelessWidget {
  const FullscreenPlayerScreen({
    super.key,
    required this.streamUrl,
    required this.title,
    required this.contentType,
  });

  final String streamUrl;
  final String title;
  final String contentType;

  @override
  Widget build(BuildContext context) {
    return AndroidHlsFullscreenScreen(
      streamUrl: streamUrl,
      title: title,
      contentType: contentType,
    );
  }
}

