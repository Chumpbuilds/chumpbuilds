import 'package:flutter_vlc_player/flutter_vlc_player.dart';

import 'video_player_service.dart';

/// Legacy service kept for API compatibility.
///
/// All playback now goes through [VideoPlayerService] which uses
/// flutter_vlc_player (LibVLC) under the hood. This class delegates every
/// call to [VideoPlayerService.instance].
class VlcPlayerService {
  VlcPlayerService._();
  static final VlcPlayerService instance = VlcPlayerService._();

  final _delegate = VideoPlayerService.instance;

  VlcPlayerController? get controller => _delegate.controller;
  bool get isMuted => _delegate.isMuted;
  int get volume => _delegate.volume;
  bool get isPlaying => _delegate.isPlaying;
  bool get hasStream => _delegate.controller != null;

  Future<VlcPlayerController> play(
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

