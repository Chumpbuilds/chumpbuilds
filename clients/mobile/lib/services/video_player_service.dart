import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Singleton service that manages video playback via the native platform channel.
///
/// All playback is routed through [NativePlayerActivity] (ExoPlayer + SurfaceView)
/// via the platform channel `com.x87player/native_player`. Flutter renders no video
/// frames directly — the native activity handles the entire video pipeline, which
/// bypasses Flutter's PlatformView texture bridge and works reliably on Android 14+.
///
/// Volume is on a 0–100 scale for API compatibility, but note the native player
/// manages its own volume independently.
class VideoPlayerService {
  VideoPlayerService._();
  static final VideoPlayerService instance = VideoPlayerService._();

  static const _channel = MethodChannel('com.x87player/native_player');

  // ─── State ────────────────────────────────────────────────────────────────

  bool _isPlaying = false;
  bool _isMuted = false;
  int _volume = 80;

  // ─── Public getters ───────────────────────────────────────────────────────

  bool get isPlaying => _isPlaying;
  bool get isMuted => _isMuted;
  int get volume => _volume;

  // ─── Playback ─────────────────────────────────────────────────────────────

  /// Launches [NativePlayerActivity] via the platform channel and awaits its
  /// dismissal. [_isPlaying] is true while the native activity is active.
  Future<void> play(
    String url,
    String title,
    String contentType,
  ) async {
    if (kDebugMode) {
      debugPrint(
        '[VideoPlayerService] Launching NativePlayerActivity | '
        'contentType=$contentType url=${_safeUrl(url)}',
      );
    }

    _isPlaying = true;
    try {
      await _channel.invokeMethod<void>('launchPlayer', {
        'url': url,
        'title': title,
        'contentType': contentType,
      });
    } finally {
      _isPlaying = false;
      if (kDebugMode) {
        debugPrint('[VideoPlayerService] NativePlayerActivity dismissed');
      }
    }
  }

  /// Same as [play] — all playback is native fullscreen.
  Future<void> playFullscreenNative(
    String url,
    String title,
    String contentType,
  ) =>
      play(url, title, contentType);

  // ─── Common controls ──────────────────────────────────────────────────────

  /// Resets the local [isPlaying] flag. The native activity manages its own
  /// lifecycle — calling this does not forcibly stop an active native player.
  /// It is safe to call as a cleanup hook when the Flutter side no longer
  /// tracks an active stream.
  Future<void> stop() async {
    _isPlaying = false;
  }

  /// No-op: the native activity manages its own playback state.
  Future<void> pause() async {}

  /// No-op: the native activity manages its own playback state.
  Future<void> resume() async {}

  Future<void> setVolume(int vol) async {
    _volume = vol.clamp(0, 100);
  }

  Future<void> toggleMute() async {
    _isMuted = !_isMuted;
  }

  // ─── Internal ─────────────────────────────────────────────────────────────

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
