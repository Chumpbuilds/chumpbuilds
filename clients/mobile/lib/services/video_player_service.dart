import 'package:flutter/foundation.dart';
import 'package:flutter_vlc_player/flutter_vlc_player.dart';

/// Network-caching values (milliseconds) tuned per content type.
const int _kLiveCachingMs = 1000;
const int _kVodCachingMs = 3000;

/// Singleton service that manages video playback.
///
/// ### Embedded playback
/// Uses flutter_vlc_player (LibVLC) for embedded in-app playback — the same
/// VLC engine that powers the external "Play in VLC" option which works
/// reliably on Android TV boxes, Fire Stick, and Amlogic-based devices.
///
/// ### Fullscreen playback
/// [playFullscreenNative] is kept for API compatibility but is no longer
/// invoked for normal playback.  Fullscreen is now handled by the Flutter
/// [AndroidHlsFullscreenScreen] widget using [VlcPlayer].
///
/// Volume is on a 0–100 scale (same as the previous service).
class VideoPlayerService {
  VideoPlayerService._();
  static final VideoPlayerService instance = VideoPlayerService._();

  // ─── State ────────────────────────────────────────────────────────────────

  VlcPlayerController? _controller;
  bool _isMuted = false;
  int _volume = 80;

  // ─── Public getters ───────────────────────────────────────────────────────

  VlcPlayerController? get controller => _controller;
  bool get isMuted => _isMuted;
  int get volume => _volume;

  bool get isPlaying => _controller?.value.isPlaying ?? false;

  // ─── Embedded playback (flutter_vlc_player) ───────────────────────────────

  /// Initializes and starts **embedded** playback of [url].
  ///
  /// Any previous controller is disposed first. Returns a
  /// [VlcPlayerController] that can be passed to a [VlcPlayer] widget
  /// for rendering.
  Future<VlcPlayerController> play(
    String url,
    String title,
    String contentType,
  ) async {
    await _disposeController();

    if (kDebugMode) {
      debugPrint(
        '[VideoPlayerService] Creating VLC player | '
        'contentType=$contentType '
        'url=[34m${_safeUrl(url)}[0m',
      );
    }

    // ── VLC options tuned per content type ──
    final networkCaching =
        contentType == 'live' ? _kLiveCachingMs : _kVodCachingMs;

    final vlcOptions = [
      '--network-caching=$networkCaching',
      '--http-user-agent=X87-IPTV-Player/1.0',
      '--no-audio-resampling',
      '--codec=avcodec',
    ];

    final ctrl = VlcPlayerController.network(
      url,
      hwAcc: HwAcc.full,
      autoPlay: true,
      options: VlcPlayerOptions(
        advanced: VlcAdvancedOptions(vlcOptions),
      ),
    );

    await ctrl.setVolume(_isMuted ? 0 : _volume);

    _controller = ctrl;

    if (kDebugMode) {
      debugPrint('[VideoPlayerService] VLC controller opened | url=[34m${_safeUrl(url)}[0m');
    }

    return ctrl;
  }

  // ─── Fullscreen native playback (kept for API compatibility) ──────────────

  /// Kept for API compatibility. Fullscreen playback is now handled by the
  /// Flutter [AndroidHlsFullscreenScreen] widget using [VlcPlayer] directly.
  /// This method is no longer invoked during normal playback.
  Future<void> playFullscreenNative(
    String url,
    String title,
    String contentType,
  ) async {
    await _disposeController();

    if (kDebugMode) {
      debugPrint(
        '[VideoPlayerService] playFullscreenNative called (no-op since VLC migration) | '
        'contentType=$contentType '
        'url=[34m${_safeUrl(url)}[0m',
      );
    }
  }

  // ─── Common controls ──────────────────────────────────────────────────────

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
      await _controller?.setVolume(_volume);
    }
  }

  Future<void> toggleMute() async {
    _isMuted = !_isMuted;
    await _controller?.setVolume(_isMuted ? 0 : _volume);
  }

  // ─── Internal ─────────────────────────────────────────────────────────────

  Future<void> _disposeController() async {
    final c = _controller;
    _controller = null;
    if (c != null) {
      try {
        await c.stop();
        await c.dispose();
      } catch (_) {}
    }
  }

  /// Returns a sanitized URL safe for debug logging (no credentials).
  static String _safeUrl(String url) {
    try {
      final uri = Uri.parse(url);
      final port = uri.hasPort ? ':${uri.port}' : '';
      return '[35m${uri.scheme}://${uri.host}$port${uri.path}[0m';
    } catch (_) {
      return '(unparseable url)';
    }
  }
}