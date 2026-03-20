import 'package:flutter/foundation.dart';
import 'package:flutter_vlc_player/flutter_vlc_player.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Singleton service that manages a [VlcPlayerController] and exposes
/// playback controls matching the Windows `EmbeddedVLCPlayer` API.
///
/// Mirrors `clients/windows/player/vlc_player.py` → `EmbeddedVLCPlayer`.
class VlcPlayerService {
  VlcPlayerService._();
  static final VlcPlayerService instance = VlcPlayerService._();

  // ─── Caching defaults ─────────────────────────────────────────────────────
  // Increased to 5 000 ms to give the initial buffer enough time to fill and
  // prevent the initialization future from timing out before playback starts.
  static const int _defaultNetworkCaching = 5000;
  static const int _defaultLiveCaching = 2000;
  static const int _defaultFileCaching = 5000;

  // ─── Preference keys ──────────────────────────────────────────────────────
  static const String _keyNetworkCaching = 'vlc_network_caching';
  static const String _keyLiveCaching = 'vlc_live_caching';
  static const String _keyFileCaching = 'vlc_file_caching';

  // ─── State ────────────────────────────────────────────────────────────────
  VlcPlayerController? _controller;
  String? _currentUrl;
  String? _currentTitle;
  String _currentContentType = 'live';
  bool _isMuted = false;
  int _volume = 80;

  int _networkCaching = _defaultNetworkCaching;
  int _liveCaching = _defaultLiveCaching;
  int _fileCaching = _defaultFileCaching;

  // ─── Public getters ───────────────────────────────────────────────────────

  VlcPlayerController? get controller => _controller;
  String? get currentUrl => _currentUrl;
  String? get currentTitle => _currentTitle;
  bool get isMuted => _isMuted;
  int get volume => _volume;
  int get networkCaching => _networkCaching;
  int get liveCaching => _liveCaching;
  int get fileCaching => _fileCaching;

  bool get isPlaying {
    final c = _controller;
    if (c == null) return false;
    return c.value.playingState == PlayingState.playing;
  }

  bool get hasStream => _currentUrl != null && _currentUrl!.isNotEmpty;

  // ─── Initialisation ───────────────────────────────────────────────────────

  Future<void> loadSettings() async {
    final prefs = await SharedPreferences.getInstance();
    _networkCaching =
        prefs.getInt(_keyNetworkCaching) ?? _defaultNetworkCaching;
    _liveCaching = prefs.getInt(_keyLiveCaching) ?? _defaultLiveCaching;
    _fileCaching = prefs.getInt(_keyFileCaching) ?? _defaultFileCaching;
  }

  Future<void> saveCachingSettings({
    int? networkCaching,
    int? liveCaching,
    int? fileCaching,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    if (networkCaching != null) {
      _networkCaching = networkCaching;
      await prefs.setInt(_keyNetworkCaching, networkCaching);
    }
    if (liveCaching != null) {
      _liveCaching = liveCaching;
      await prefs.setInt(_keyLiveCaching, liveCaching);
    }
    if (fileCaching != null) {
      _fileCaching = fileCaching;
      await prefs.setInt(_keyFileCaching, fileCaching);
    }
  }

  // ─── Playback ─────────────────────────────────────────────────────────────

  /// Creates (or recreates) a [VlcPlayerController] for [url].
  ///
  /// The previous controller is disposed before a new one is created.
  /// Returns the new controller so callers can attach it to a [VlcPlayer]
  /// widget.
  Future<VlcPlayerController> play(
    String url,
    String title,
    String contentType,
  ) async {
    await _disposeController();

    _currentUrl = url;
    _currentTitle = title;
    _currentContentType = contentType;

    final cacheMs =
        contentType == 'live' ? _liveCaching : _fileCaching;

    final options = VlcPlayerOptions(
      advanced: VlcAdvancedOptions([
        '--network-caching=$cacheMs',
        '--live-caching=$_liveCaching',
        '--file-caching=$_fileCaching',
        '--no-video-title-show',
        // Use AudioTrack (modern Android audio output) instead of OpenSLES,
        // which is deprecated on newer Android versions and can cause init hangs.
        '--aout=android_audiotrack',
        // Use TCP for RTSP streams to improve stability through NAT/firewalls.
        '--rtsp-tcp',
        // Keep connection alive for continuous HTTP/HLS streams.
        '--http-continuous',
      ]),
      http: VlcHttpOptions([
        // Automatically reconnect on dropped HTTP connections.
        VlcHttpOptions.httpReconnect(true),
      ]),
    );

    _controller = VlcPlayerController.network(
      url,
      // Software decoding is more compatible across Android devices and ROMs,
      // avoiding playback errors caused by hardware decoder incompatibilities.
      hwAcc: HwAcc.disabled,
      autoPlay: true, // flutter_vlc_player Android bug: isInitialized never fires with autoPlay: false
      options: options,
    );

    if (kDebugMode) {
      _controller!.addOnInitListener(() {
        debugPrint(
          '[VLC] init – state: ${_controller?.value.playingState}',
        );
      });
      _controller!.addListener(() {
        final err = _controller?.value.errorDescription;
        if (err != null && err.isNotEmpty) {
          debugPrint('[VLC] error: $err');
        }
      });
    }

    return _controller!;
  }

  Future<void> stop() async {
    await _disposeController();
  }

  Future<void> pause() async {
    final c = _controller;
    if (c == null) return;
    await c.pause();
  }

  Future<void> resume() async {
    final c = _controller;
    if (c == null) return;
    await c.play();
  }

  Future<void> setVolume(int vol) async {
    _volume = vol.clamp(0, 100);
    final c = _controller;
    if (c != null) {
      await c.setVolume(_volume);
    }
  }

  Future<void> toggleMute() async {
    _isMuted = !_isMuted;
    final c = _controller;
    if (c != null) {
      await c.setVolume(_isMuted ? 0 : _volume);
    }
  }

  // ─── Internal ─────────────────────────────────────────────────────────────

  Future<void> _disposeController() async {
    final c = _controller;
    _controller = null;
    _currentUrl = null;
    _currentTitle = null;
    if (c != null) {
      try {
        await c.dispose();
      } catch (_) {}
    }
  }
}
