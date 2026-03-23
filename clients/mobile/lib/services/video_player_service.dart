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
        // ── A/V sync & frame dropping ──
        // Allow mpv to drop frames at both decoder and display level when
        // video falls behind audio. Without this, every frame is rendered
        // late → visual lag and progressive lip-sync drift on weak GPUs.
        await nativePlayer.setProperty('framedrop', 'decoder+vo');

        // ── Decoder performance ──
        // Let libavcodec use all available CPU cores for any software
        // decode paths (fallback when HW decoder rejects a frame).
        await nativePlayer.setProperty('vd-lavc-threads', '0');
        // Skip deblocking filter on non-reference frames — reduces CPU
        // load with minimal visual impact on live and VOD streams.
        await nativePlayer.setProperty('vd-lavc-skiploopfilter', 'nonref');
        // Enable the "fast" flag for libavcodec — trades minor quality
        // for significant decode speed on ARM CPUs.
        await nativePlayer.setProperty('vd-lavc-fast', 'yes');

        // ── GPU / rendering ──
        // Flush OpenGL commands early to reduce frame latency on embedded
        // GPUs (Amlogic Mali, etc.).
        await nativePlayer.setProperty('opengl-early-flush', 'yes');

        // ── Buffering / cache ──
        await nativePlayer.setProperty('cache', 'yes');
        if (contentType == 'live') {
          // Live TV: small buffer to stay near real-time, but enough to
          // absorb network jitter without rebuffering.
          await nativePlayer.setProperty('cache-secs', '5');
          await nativePlayer.setProperty('demuxer-max-bytes', '16MiB');
          await nativePlayer.setProperty('demuxer-max-back-bytes', '4MiB');
        } else {
          // Movies/series: larger buffer for smooth playback and seeking.
          await nativePlayer.setProperty('cache-secs', '30');
          await nativePlayer.setProperty('demuxer-max-bytes', '64MiB');
          await nativePlayer.setProperty('demuxer-max-back-bytes', '16MiB');
        }

        // ── Network resilience ──
        await nativePlayer.setProperty(
          'demuxer-lavf-o',
          'reconnect=1,reconnect_streamed=1,reconnect_delay_max=5',
        );

        // ── Hardware codec eligibility ──
        // Ensure ALL codecs are sent to the hardware decoder, not just
        // the default shortlist.
        await nativePlayer.setProperty('hwdec-codecs', 'all');

        if (kDebugMode) {
          debugPrint(
            '[VideoPlayerService] mpv properties set for $contentType',
          );
        }
      }
    }

    // Create VideoController — this is where hwdec and vo are configured.
    final videoCtrl = VideoController(
      player,
      configuration: const VideoControllerConfiguration(
        enableHardwareAcceleration: true,
        // Force full hardware decoding. The default 'auto-safe' is too
        // conservative on Amlogic/ARM TV boxes — it falls back to software
        // decode for many IPTV stream types (HEVC, interlaced H.264), which
        // causes slow-motion playback on HD/FHD channels. 'auto' tries HW
        // decode for everything and only falls back to software if HW
        // actually fails, which is the correct behavior for set-top boxes.
        // On mainstream Android phones (Qualcomm/MediaTek) this is equally
        // safe — those SoCs handle all common codecs in hardware reliably.
        hwdec: 'auto',
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
