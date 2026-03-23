import 'package:media_kit_video/media_kit_video.dart';

import 'video_player_service.dart';

/// Legacy service kept for API compatibility.
///
/// All playback now goes through [VideoPlayerService] which uses media_kit
/// under the hood (libmpv-based, hardware + software decoding with automatic
/// fallback). This class delegates every call to [VideoPlayerService.instance].
class VlcPlayerService {
  VlcPlayerService._();
  static final VlcPlayerService instance = VlcPlayerService._();

  final _delegate = VideoPlayerService.instance;

  VideoController? get controller => _delegate.controller;
  bool get isMuted => _delegate.isMuted;
  int get volume => _delegate.volume;
  bool get isPlaying => _delegate.isPlaying;
  bool get hasStream => _delegate.controller != null;

  Future<VideoController> play(
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
