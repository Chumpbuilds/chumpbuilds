import 'package:flutter/foundation.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit_video/media_kit_video.dart';

/// Singleton service that manages a [Player] (media_kit) for video playback.
///
/// Replaces the previous ExoPlayer-backed (video_player) and LibVLC-backed
/// (flutter_vlc_player) services with a single media_kit implementation that
/// works reliably on Android phones, Android TV boxes (including Amlogic
/// hardware), iOS, and other platforms.
///
/// Volume is on a 0–100 scale (same as the old VLC service).
class VideoPlayerService {
  VideoPlayerService._();
  static final VideoPlayerService instance = VideoPlayerService._();

  // ─── State ────────────────────────────────────────────────────────────────

  Player? _player;
  VideoController? _videoController;
  bool _isMuted = false;
  int _volume = 80;

  // ─── Public getters ───────────────────────────────────────────────────────

  VideoController? get controller => _videoController;
  bool get isMuted => _isMuted;
  int get volume => _volume;

  bool get isPlaying => _player?.state.playing ?? false;

  // ─── Playback ─────────────────────────────────────────────────────────────

  /// Initializes and starts playback of [url].
  ///
  /// Any previous player is disposed first.  Returns a [VideoController] that
  /// can be passed to a [Video] widget for rendering.
  Future<VideoController> play(
    String url,
    String title,
    String contentType,
  ) async {
    await _disposePlayer();

    if (kDebugMode) {
      debugPrint(
        '[VideoPlayerService] Creating player | '
        'contentType=$contentType '
        'url=${_safeUrl(url)}',
      );
    }

    final player = Player(
      configuration: PlayerConfiguration(
        bufferSize: 32 * 1024 * 1024, // 32 MB buffer
      ),
    );
    final videoCtrl = VideoController(player);

    _player = player;
    _videoController = videoCtrl;

    // ── mpv tuning for IPTV/HLS streams ──
    // Hardware decoding with automatic software fallback
    await player.setProperty('hwdec', 'auto');
    await player.setProperty('vo', 'gpu');

    // Low-latency profile for live TV — reduces buffering delay
    if (contentType == 'live') {
      await player.setProperty('profile', 'low-latency');
      await player.setProperty('cache-secs', '3');
    } else {
      // Movies/series can tolerate more buffer for smoother playback
      await player.setProperty('cache-secs', '10');
    }

    // General cache/demuxer settings
    await player.setProperty('cache', 'yes');
    await player.setProperty('demuxer-max-bytes', '32MiB');
    await player.setProperty('demuxer-max-back-bytes', '8MiB');

    // Network reconnection for IPTV streams that drop
    await player.setProperty(
      'demuxer-lavf-o',
      'reconnect=1,reconnect_streamed=1,reconnect_delay_max=5',
    );

    await player.setVolume(_isMuted ? 0.0 : _volume.toDouble());
    await player.open(Media(url));

    if (kDebugMode) {
      debugPrint(
        '[VideoPlayerService] opened | '
        'playing=${player.state.playing}',
      );
    }

    return videoCtrl;
  }

  Future<void> stop() async {
    await _disposePlayer();
  }

  Future<void> pause() async {
    await _player?.pause();
  }

  Future<void> resume() async {
    await _player?.play();
  }

  Future<void> setVolume(int vol) async {
    _volume = vol.clamp(0, 100);
    if (!_isMuted) {
      await _player?.setVolume(_volume.toDouble());
    }
  }

  Future<void> toggleMute() async {
    _isMuted = !_isMuted;
    await _player?.setVolume(_isMuted ? 0.0 : _volume.toDouble());
  }

  // ─── Internal ─────────────────────────────────────────────────────────────

  Future<void> _disposePlayer() async {
    final p = _player;
    _player = null;
    _videoController = null;
    if (p != null) {
      try {
        await p.dispose();
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
