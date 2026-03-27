import 'video_player_service.dart';

/// Legacy service kept for API compatibility.
///
/// All playback now routes through [VideoPlayerService] which launches
/// [NativePlayerActivity] via platform channel. This class delegates every
/// call to [VideoPlayerService.instance].
class VlcPlayerService {
  VlcPlayerService._();
  static final VlcPlayerService instance = VlcPlayerService._();

  final _delegate = VideoPlayerService.instance;

  bool get isMuted => _delegate.isMuted;
  int get volume => _delegate.volume;
  bool get isPlaying => _delegate.isPlaying;
  /// True when the native player is active. In the native-player architecture
  /// there is no persistent loaded-but-paused state, so this mirrors [isPlaying].
  bool get hasStream => _delegate.isPlaying;

  Future<void> play(
    String url,
    String title,
    String contentType, {
    bool useMinimalOptions = false,
  }) =>
      _delegate.play(url, title, contentType);

  Future<void> stop() => _delegate.stop();
  Future<void> pause() => _delegate.pause();
  Future<void> resume() => _delegate.resume();
  Future<void> setVolume(int vol) => _delegate.setVolume(vol);
  Future<void> toggleMute() => _delegate.toggleMute();

  Future<void> loadSettings() async {}
  Future<void> saveCachingSettings({
    int? networkCaching,
    int? liveCaching,
    int? fileCaching,
  }) async {}
}
