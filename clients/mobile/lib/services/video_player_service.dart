import 'package:flutter/foundation.dart';
import 'package:video_player/video_player.dart';

/// Singleton service that manages a [VideoPlayerController] for Android HLS
/// (ExoPlayer-backed) playback.
///
/// Used as a drop-in alternative to [VlcPlayerService] when playing HLS
/// streams on Android, where LibVLC / flutter_vlc_player has proven
/// unreliable (stuck in `PlayingState.initializing` forever for .m3u8
/// streams despite multiple previous fix attempts).
class VideoPlayerService {
  VideoPlayerService._();
  static final VideoPlayerService instance = VideoPlayerService._();

  // ─── State ────────────────────────────────────────────────────────────────

  VideoPlayerController? _controller;
  bool _isMuted = false;
  int _volume = 80;

  // ─── Public getters ───────────────────────────────────────────────────────

  VideoPlayerController? get controller => _controller;
  bool get isMuted => _isMuted;
  int get volume => _volume;

  bool get isPlaying => _controller?.value.isPlaying ?? false;

  // ─── Playback ─────────────────────────────────────────────────────────────

  /// Initializes and starts playback of [url].
  ///
  /// Any previous controller is disposed first.  Returns the initialized
  /// [VideoPlayerController] so callers can attach it to a [VideoPlayer]
  /// widget.
  ///
  /// Throws if [VideoPlayerController.initialize] fails (e.g. network error).
  Future<VideoPlayerController> play(
    String url,
    String title,
    String contentType,
  ) async {
    await _disposeController();

    if (kDebugMode) {
      debugPrint(
        '[VideoPlayerService] Creating controller | '
        'contentType=$contentType '
        'url=${_safeUrl(url)}',
      );
    }

    final ctrl = VideoPlayerController.networkUrl(
      Uri.parse(url),
      videoPlayerOptions: VideoPlayerOptions(mixWithOthers: false),
    );
    _controller = ctrl;

    await ctrl.initialize();
    await ctrl.setVolume(_isMuted ? 0.0 : _volume / 100.0);
    await ctrl.play();

    if (kDebugMode) {
      debugPrint(
        '[VideoPlayerService] initialized | '
        'isInitialized=${ctrl.value.isInitialized} '
        'isPlaying=${ctrl.value.isPlaying} '
        'size=${ctrl.value.size}',
      );
    }

    return ctrl;
  }

  Future<void> stop() async {
    await _disposeController();
  }

  Future<void> pause() async {
    await _controller?.pause();
  }

  Future<void> resume() async {
    await _controller?.play();
  }

  Future<void> setVolume(int vol) async {
    _volume = vol.clamp(0, 100);
    if (!_isMuted) {
      await _controller?.setVolume(_volume / 100.0);
    }
  }

  Future<void> toggleMute() async {
    _isMuted = !_isMuted;
    await _controller?.setVolume(_isMuted ? 0.0 : _volume / 100.0);
  }

  // ─── Internal ─────────────────────────────────────────────────────────────

  Future<void> _disposeController() async {
    final c = _controller;
    _controller = null;
    if (c != null) {
      try {
        await c.dispose();
      } catch (_) {}
    }
  }

  /// Returns a sanitized URL safe for debug logging (no credentials).
  static String _safeUrl(String url) {
    try {
      final uri = Uri.parse(url);
      final port = uri.hasPort ? ':${uri.port}' : '';
      return '${uri.scheme}://${uri.host}$port${uri.path}';
    } catch (_) {
      return '(unparseable url)';
    }
  }
}
