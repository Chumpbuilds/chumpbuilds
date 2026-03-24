import 'package:better_player_plus/better_player_plus.dart';
import 'package:flutter/foundation.dart';

/// Singleton service that manages a [BetterPlayerController] for video
/// playback.
///
/// Uses better_player_plus which wraps Android's native Media3/ExoPlayer
/// pipeline (direct SurfaceView rendering) on Android and AVFoundation on iOS.
/// This avoids the libmpv OpenGL texture bridge used by media_kit, which
/// caused severe lag and poor performance on Fire Stick and Amlogic-based
/// Android TV boxes.
///
/// Volume is on a 0–100 scale (same as the previous service).
class VideoPlayerService {
  VideoPlayerService._();
  static final VideoPlayerService instance = VideoPlayerService._();

  // ─── State ────────────────────────────────────────────────────────────────

  BetterPlayerController? _controller;
  bool _isMuted = false;
  int _volume = 80;

  // ─── Public getters ───────────────────────────────────────────────────────

  BetterPlayerController? get controller => _controller;
  bool get isMuted => _isMuted;
  int get volume => _volume;

  bool get isPlaying => _controller?.isPlaying() ?? false;

  // ─── Playback ─────────────────────────────────────────────────────────────

  /// Initializes and starts playback of [url].
  ///
  /// Any previous controller is disposed first. Returns a
  /// [BetterPlayerController] that can be passed to a [BetterPlayer] widget
  /// for rendering.
  Future<BetterPlayerController> play(
    String url,
    String title,
    String contentType,
  ) async {
    await _disposeController();

    if (kDebugMode) {
      debugPrint(
        '[VideoPlayerService] Creating player | '
        'contentType=$contentType '
        'url=${_safeUrl(url)}',
      );
    }

    // ── Buffering configuration tuned per content type ──
    final bufferingConfig = contentType == 'live'
        ? const BetterPlayerBufferingConfiguration(
            minBufferMs: 5000,
            maxBufferMs: 30000,
            bufferForPlaybackMs: 2500,
            bufferForPlaybackAfterRebufferMs: 5000,
          )
        : const BetterPlayerBufferingConfiguration(
            minBufferMs: 15000,
            maxBufferMs: 120000,
            bufferForPlaybackMs: 5000,
            bufferForPlaybackAfterRebufferMs: 10000,
          );

    final configuration = BetterPlayerConfiguration(
      aspectRatio: 16 / 9,
      autoPlay: true,
      fit: BoxFit.contain,
      controlsConfiguration: const BetterPlayerControlsConfiguration(
        showControls: false,
      ),
      bufferingConfiguration: bufferingConfig,
    );

    // ── Data source: HLS vs other ──
    final isHls = url.toLowerCase().contains('.m3u8');
    final dataSource = BetterPlayerDataSource(
      BetterPlayerDataSourceType.network,
      url,
      headers: {'User-Agent': 'X87-IPTV-Player/1.0'},
      videoFormat:
          isHls ? BetterPlayerVideoFormat.hls : BetterPlayerVideoFormat.other,
    );

    final ctrl = BetterPlayerController(configuration);
    await ctrl.setupDataSource(dataSource);
    await ctrl.setVolume(_isMuted ? 0.0 : _volume / 100.0);

    _controller = ctrl;

    if (kDebugMode) {
      debugPrint('[VideoPlayerService] opened | url=${_safeUrl(url)}');
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
        c.dispose();
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
