import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../services/video_player_service.dart';
import '../widgets/system_ui_wrapper.dart';

/// Full-screen video playback screen.
///
/// On Android and iOS this launches the **native** player via a platform
/// channel ([VideoPlayerService.playFullscreenNative]):
///   - Android: [NativePlayerActivity] (ExoPlayer + SurfaceView, zero-copy
///     hardware compositor — same rendering path as XCIPTV).
///   - iOS: [NativePlayerViewController] (AVPlayerViewController).
///
/// This screen acts as a thin launcher: it calls the native player in
/// [initState] and pops itself when the native player returns.  This keeps
/// the Flutter UI stack consistent (callers can `await` the navigation push
/// and receive control back after playback ends).
class AndroidHlsFullscreenScreen extends StatefulWidget {
  const AndroidHlsFullscreenScreen({
    super.key,
    required this.streamUrl,
    required this.title,
    required this.contentType,
  });

  final String streamUrl;
  final String title;
  final String contentType;

  @override
  State<AndroidHlsFullscreenScreen> createState() =>
      _AndroidHlsFullscreenScreenState();
}

class _AndroidHlsFullscreenScreenState
    extends State<AndroidHlsFullscreenScreen> {
  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    WakelockPlus.enable();
    _launchNativePlayer();
  }

  @override
  void dispose() {
    WakelockPlus.disable();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  Future<void> _launchNativePlayer() async {
    try {
      await VideoPlayerService.instance.playFullscreenNative(
        widget.streamUrl,
        widget.title,
        widget.contentType,
      );
    } catch (e) {
      debugPrint('[AndroidHlsFullscreenScreen] Native player error: $e');
    }
    // Return to the calling screen regardless of whether playback succeeded.
    if (mounted) Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    // Show a black loading screen while the native player is launching.
    return SystemUiWrapper(
      child: Scaffold(
        backgroundColor: Colors.black,
        body: const Center(
          child: CircularProgressIndicator(color: Color(0xFF3498DB)),
        ),
      ),
    );
  }
}


