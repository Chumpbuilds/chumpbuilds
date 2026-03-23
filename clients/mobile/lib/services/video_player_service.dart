import 'package:flutter/foundation.dart';
import 'package:media_kit/media_kit.dart';
import 'package:media_kit/src/player/native/player/player.dart';
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
        bufferSize: 32 * 1024 * 1024, // 32 MB demuxer cache
      ),
    );

    // ── Set mpv properties for IPTV/HLS optimization ──
    // These must be set BEFORE player.open() and AFTER Player() creation.
    // The setProperty method is on NativePlayer (the platform implementation),
    // not the public Player class.
    if (!kIsWeb) {
      final nativePlayer = player.platform;
      if (nativePlayer is NativePlayer) {
        // Low-latency profile for live TV — reduces internal buffering
        if (contentType == 'live') {
          await nativePlayer.setProperty('profile', 'low-latency');
          await nativePlayer.setProperty('cache-secs', '3');
        } else {
          // Movies/series can tolerate more buffer for smoother playback
          await nativePlayer.setProperty('cache-secs', '10');
        }

        // General cache/demuxer settings
        await nativePlayer.setProperty('cache', 'yes');
        await nativePlayer.setProperty('demuxer-max-bytes', '32MiB');
        await nativePlayer.setProperty('demuxer-max-back-bytes', '8MiB');

        // Network reconnection for IPTV streams that may drop
        await nativePlayer.setProperty(
          'demuxer-lavf-o',
          'reconnect=1,reconnect_streamed=1,reconnect_delay_max=5',
        );

        if (kDebugMode) {
          debugPrint('[VideoPlayerService] mpv properties set for $contentType');
        }
      }
    }

    // Create VideoController — this is where hwdec and vo are configured.
    // On Android, media_kit's AndroidVideoController already defaults to:
    //   vo=gpu, hwdec=auto-safe, hwdec-codecs=h264,hevc,mpeg4,...
    // So we don't need to override those — they're already optimal.
    // On other platforms (Windows/Linux/macOS/iOS), NativeVideoController
    // defaults to vo=libmpv, hwdec=auto.
    final videoCtrl = VideoController(
      player,
      configuration: const VideoControllerConfiguration(
        enableHardwareAcceleration: true, // explicit — ensures hwdec is enabled
      ),
    );

    _player = player;
    _videoController = videoCtrl;

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
