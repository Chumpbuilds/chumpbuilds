import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../services/video_player_service.dart';

/// Full-screen video playback screen.
///
/// A thin launcher that invokes [VideoPlayerService.play] (which calls
/// [NativePlayerActivity] via platform channel) and pops when the native
/// activity is dismissed. Flutter renders no video frames — all playback
/// happens in the native ExoPlayer + SurfaceView activity, bypassing
/// Flutter's PlatformView texture bridge entirely.
class AndroidHlsFullscreenScreen extends StatefulWidget {
  const AndroidHlsFullscreenScreen({
    super.key,
    required this.streamUrl,
    required this.title,
    required this.contentType,
    this.year,
    this.tmdbId,
    this.season,
    this.episode,
  });

  final String streamUrl;
  final String title;
  final String contentType;

  /// Optional release year — forwarded to the native player for online subtitle
  /// searches.
  final String? year;

  /// Optional TMDb ID — forwarded to the native player for online subtitle
  /// searches.
  final String? tmdbId;

  /// Optional season number — forwarded to the native player so subtitle
  /// searches are scoped to the correct TV season.
  final int? season;

  /// Optional episode number — forwarded to the native player so subtitle
  /// searches are scoped to the correct episode.
  final int? episode;

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
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersive);
    WakelockPlus.enable();

    WidgetsBinding.instance.addPostFrameCallback((_) async {
      await VideoPlayerService.instance.play(
        widget.streamUrl,
        widget.title,
        widget.contentType,
        year: widget.year,
        tmdbId: widget.tmdbId,
        season: widget.season,
        episode: widget.episode,
      );
      if (mounted) {
        await SystemChrome.setEnabledSystemUIMode(
            SystemUiMode.immersive);
        Navigator.of(context).pop();
      }
    });
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

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      backgroundColor: Colors.black,
      body: Center(
        child: CircularProgressIndicator(
          color: Color(0xFF3498DB),
        ),
      ),
    );
  }
}
