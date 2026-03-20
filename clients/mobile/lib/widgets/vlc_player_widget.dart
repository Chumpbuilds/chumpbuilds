import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_vlc_player/flutter_vlc_player.dart';

import '../screens/fullscreen_player_screen.dart';
import '../services/external_player_service.dart';
import '../services/vlc_player_service.dart';

/// Embedded VLC player widget (video area only, no control bar).
///
/// Matches the Windows desktop player layout from
/// `clients/windows/player/vlc_player.py` → `EmbeddedVLCPlayer`.
///
/// Parameters:
///   [streamUrl]   – HLS/RTSP/HTTP stream URL to play.
///   [title]       – Human-readable title shown in UI.
///   [contentType] – 'live', 'movie', or 'series'.
class VlcPlayerWidget extends StatefulWidget {
  const VlcPlayerWidget({
    super.key,
    required this.streamUrl,
    required this.title,
    required this.contentType,
    this.autoPlay = false,
  });

  final String streamUrl;
  final String title;
  final String contentType;

  /// When [true] and [streamUrl] is non-empty, playback starts automatically
  /// when the widget is first mounted.  Defaults to [false].
  final bool autoPlay;

  @override
  State<VlcPlayerWidget> createState() => _VlcPlayerWidgetState();
}

class _VlcPlayerWidgetState extends State<VlcPlayerWidget> {
  // ─── Theme ────────────────────────────────────────────────────────────────
  static const Color _stopColor = Color(0xFFE74C3C);
  static const Color _sliderActive = Color(0xFF3498DB);

  // ─── State ────────────────────────────────────────────────────────────────
  final _service = VlcPlayerService.instance;
  VlcPlayerController? _controller;
  bool _isPlaying = false;
  bool _isMuted = false;
  double _volume = 80;
  bool _isLoading = false;
  bool _hasError = false;

  String get _placeholder {
    switch (widget.contentType) {
      case 'movie':
        return 'Select a movie to play';
      case 'series':
        return 'Select an episode to play';
      default:
        return 'Select a channel to start watching';
    }
  }

  @override
  void initState() {
    super.initState();
    if (widget.autoPlay && widget.streamUrl.isNotEmpty) {
      // Defer to next frame so the widget tree is fully built
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _startPlayback();
      });
    }
  }

  @override
  void dispose() {
    _controller?.removeListener(_onControllerChanged);
    super.dispose();
  }

  // ─── Playback ─────────────────────────────────────────────────────────────

  Future<void> _startPlayback({bool isRetry = false}) async {
    if (widget.streamUrl.isEmpty) return;
    setState(() {
      _isLoading = true;
      _hasError = false;
    });

    if (kDebugMode) {
      debugPrint(
        '[VlcPlayer] _startPlayback | '
        'isRetry=$isRetry '
        'contentType=${widget.contentType} '
        'title="${widget.title}"',
      );
    }

    VlcPlayerController? ctrl;
    try {
      ctrl = await _service.play(
        widget.streamUrl,
        widget.title,
        widget.contentType,
        useMinimalOptions: isRetry,
      );

      ctrl.addListener(_onControllerChanged);

      if (!mounted) return;
      // Set controller into state FIRST so VlcPlayer widget mounts and the
      // native surface is created (mirrors Windows: attach to frame, then play)
      setState(() {
        _controller = ctrl;
      });

      // Wait for the native surface + autoPlay to initialize
      await _waitForInitialized(ctrl);

      // Apply volume/mute after init (autoPlay already started playback)
      if (!mounted) return;
      await ctrl.setVolume(_isMuted ? 0 : _volume.toInt());

      if (!mounted) return;
      setState(() {
        _isPlaying = true;
        _isLoading = false;
      });
    } on TimeoutException catch (e) {
      // Timeout alone is not a confirmed failure.  Check whether the
      // controller reported a concrete error before giving up.
      final errorDesc = _service.controller?.value.errorDescription;
      final hasConcreteError = errorDesc != null && errorDesc.isNotEmpty;

      debugPrint(
        '[VlcPlayer] _startPlayback timeout | '
        'isRetry=$isRetry '
        'hasConcreteError=$hasConcreteError '
        'errorDescription=${errorDesc ?? "(none)"} '
        'error=$e',
      );

      if (!isRetry && !hasConcreteError) {
        // First attempt timed out with no concrete error – try once more
        // using bare LibVLC defaults (no custom flags).
        debugPrint('[VlcPlayer] Retrying with minimal options...');
        ctrl?.removeListener(_onControllerChanged);
        await _startPlayback(isRetry: true);
        return;
      }

      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _hasError = true;
      });
    } catch (e) {
      debugPrint('[VlcPlayer] Playback error: $e');
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _hasError = true;
      });
    }
  }

  /// Wait until the controller reports initialized (or playback begins), with a timeout.
  ///
  /// On some Android devices/ROMs, flutter_vlc_player never fires the
  /// `isInitialized` event even though playback starts successfully.  Accepting
  /// [PlayingState.playing] and [PlayingState.buffering] as "ready" states
  /// prevents a spurious [TimeoutException] in those cases.
  ///
  /// The timeout is set to 25 s to accommodate slow IPTV servers and live
  /// streams that need time to reach the first segment before LibVLC emits any
  /// state change.
  Future<void> _waitForInitialized(
    VlcPlayerController ctrl, {
    Duration timeout = const Duration(seconds: 25),
  }) async {
    bool isReady(VlcPlayerValue v) =>
        v.isInitialized ||
        v.playingState == PlayingState.playing ||
        v.playingState == PlayingState.buffering;

    if (kDebugMode) {
      debugPrint(
        '[VlcPlayer] _waitForInitialized start | '
        'timeout=${timeout.inSeconds}s '
        'conditions=[isInitialized, playing, buffering] '
        'isInitialized=${ctrl.value.isInitialized} '
        'playingState=${ctrl.value.playingState} '
        'errorDescription=${ctrl.value.errorDescription ?? "(none)"}',
      );
    }

    if (isReady(ctrl.value)) {
      if (kDebugMode) debugPrint('[VlcPlayer] _waitForInitialized: already ready');
      return;
    }
    final completer = Completer<void>();
    void listener() {
      if (isReady(ctrl.value) && !completer.isCompleted) {
        completer.complete();
      }
    }
    ctrl.addListener(listener);
    try {
      await completer.future.timeout(timeout);
      if (kDebugMode) {
        debugPrint(
          '[VlcPlayer] _waitForInitialized: success | '
          'isInitialized=${ctrl.value.isInitialized} '
          'playingState=${ctrl.value.playingState}',
        );
      }
    } on TimeoutException {
      debugPrint(
        '[VlcPlayer] _waitForInitialized: TIMEOUT after ${timeout.inSeconds}s | '
        'isInitialized=${ctrl.value.isInitialized} '
        'playingState=${ctrl.value.playingState} '
        'errorDescription=${ctrl.value.errorDescription ?? "(none)"}',
      );
      rethrow;
    } finally {
      ctrl.removeListener(listener);
    }
  }

  Future<void> _stopPlayback() async {
    _controller?.removeListener(_onControllerChanged);
    await _service.stop();
    if (!mounted) return;
    setState(() {
      _controller = null;
      _isPlaying = false;
    });
  }

  void _onControllerChanged() {
    if (!mounted) return;
    final state = _controller?.value.playingState;
    setState(() {
      _isPlaying = state == PlayingState.playing;
    });
  }

  Future<void> _openExternal() async {
    await _stopPlayback();
    final url = widget.streamUrl;
    if (url.isEmpty) return;

    final launched = await ExternalPlayerService.instance.openInVlc(url);
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('No video player found. URL: $url')),
      );
    }
  }

  Future<void> _goFullscreen() async {
    if (_controller == null) return;
    // Stop embedded playback before pushing fullscreen route
    _controller?.removeListener(_onControllerChanged);
    await _service.stop();
    if (!mounted) return;
    setState(() {
      _controller = null;
      _isPlaying = false;
    });

    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => FullscreenPlayerScreen(
          streamUrl: widget.streamUrl,
          title: widget.title,
          contentType: widget.contentType,
        ),
      ),
    );
    // After returning from fullscreen, restart embedded playback
    if (mounted && widget.streamUrl.isNotEmpty) {
      await _startPlayback();
    }
  }

  Future<void> _setVolume(double v) async {
    setState(() => _volume = v);
    await _service.setVolume(v.toInt());
    if (!_isMuted) {
      await _controller?.setVolume(v.toInt());
    }
  }

  Future<void> _toggleMute() async {
    await _service.toggleMute();
    if (!mounted) return;
    setState(() => _isMuted = _service.isMuted);
    await _controller?.setVolume(_isMuted ? 0 : _volume.toInt());
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return _buildVideoArea();
  }

  Widget _buildVideoArea() {
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: Container(
        color: Colors.black,
        child: _buildVideoContent(),
      ),
    );
  }

  Widget _buildVideoContent() {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(color: _sliderActive),
      );
    }

    if (_hasError) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline, color: _stopColor, size: 36),
            const SizedBox(height: 8),
            const Text(
              'Playback failed. Try "Open in VLC".',
              style: TextStyle(color: Colors.white70, fontSize: 12),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    if (_controller != null) {
      return VlcPlayer(
        controller: _controller!,
        aspectRatio: 16 / 9,
        placeholder: const Center(
          child: CircularProgressIndicator(color: _sliderActive),
        ),
      );
    }

    return Center(
      child: Text(
        _placeholder,
        style: const TextStyle(color: Color(0xFF95A5A6), fontSize: 13),
        textAlign: TextAlign.center,
      ),
    );
  }
}
