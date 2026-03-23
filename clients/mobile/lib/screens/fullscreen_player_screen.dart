import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_vlc_player/flutter_vlc_player.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../services/external_player_service.dart';
import '../services/vlc_player_service.dart';
import '../widgets/system_ui_wrapper.dart';

/// Full-screen video playback screen.
///
/// Mirrors the fullscreen QDialog from
/// `clients/windows/player/vlc_player.py` → `EmbeddedVLCPlayer.go_fullscreen()`.
///
/// - Fills the entire screen with the VLC player.
/// - Tap to show/hide controls overlay (play/pause, stop, volume, back).
/// - Back button or Android back gesture returns to the previous screen.
/// - Landscape orientation is enforced for the duration of this screen.
class FullscreenPlayerScreen extends StatefulWidget {
  const FullscreenPlayerScreen({
    super.key,
    required this.streamUrl,
    required this.title,
    required this.contentType,
  });

  final String streamUrl;
  final String title;
  final String contentType;

  @override
  State<FullscreenPlayerScreen> createState() =>
      _FullscreenPlayerScreenState();
}

class _FullscreenPlayerScreenState extends State<FullscreenPlayerScreen> {
  // ─── Theme ────────────────────────────────────────────────────────────────
  static const Color _stopColor = Color(0xFFE74C3C);
  static const Color _sliderTrack = Color(0xFF34495E);
  static const Color _sliderActive = Color(0xFF3498DB);

  // ─── State ────────────────────────────────────────────────────────────────
  final _service = VlcPlayerService.instance;
  VlcPlayerController? _controller;
  bool _isPlaying = false;
  bool _isMuted = false;
  double _volume = 80;
  bool _showControls = true;
  bool _isLoading = true;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    // Force landscape for fullscreen
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    WakelockPlus.enable();
    _startPlayback();
  }

  @override
  void dispose() {
    _controller?.removeListener(_onControllerChanged);
    _service.stop();
    WakelockPlus.disable();
    // Restore app-level orientation
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  // ─── Playback ─────────────────────────────────────────────────────────────

  Future<void> _startPlayback({bool isRetry = false}) async {
    if (kDebugMode) {
      debugPrint(
        '[FullscreenPlayer] _startPlayback | '
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

      // Wait for the native surface to be ready
      await _waitForInitialized(ctrl);

      if (!mounted) return;
      // autoPlay: true already started playback; just apply volume
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
        '[FullscreenPlayer] _startPlayback timeout | '
        'isRetry=$isRetry '
        'hasConcreteError=$hasConcreteError '
        'errorDescription=${errorDesc ?? "(none)"} '
        'error=$e',
      );

      if (!isRetry && !hasConcreteError) {
        // First attempt timed out with no concrete error – try once more
        // using bare LibVLC defaults (no custom flags).
        debugPrint('[FullscreenPlayer] Retrying with minimal options...');
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
      debugPrint('[FullscreenPlayer] Playback error: $e');
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
        '[FullscreenPlayer] _waitForInitialized start | '
        'timeout=${timeout.inSeconds}s '
        'conditions=[isInitialized, playing, buffering] '
        'isInitialized=${ctrl.value.isInitialized} '
        'playingState=${ctrl.value.playingState} '
        'errorDescription=${ctrl.value.errorDescription ?? "(none)"}',
      );
    }

    if (isReady(ctrl.value)) {
      if (kDebugMode) debugPrint('[FullscreenPlayer] _waitForInitialized: already ready');
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
          '[FullscreenPlayer] _waitForInitialized: success | '
          'isInitialized=${ctrl.value.isInitialized} '
          'playingState=${ctrl.value.playingState}',
        );
      }
    } on TimeoutException {
      debugPrint(
        '[FullscreenPlayer] _waitForInitialized: TIMEOUT after ${timeout.inSeconds}s | '
        'isInitialized=${ctrl.value.isInitialized} '
        'playingState=${ctrl.value.playingState} '
        'errorDescription=${ctrl.value.errorDescription ?? "(none)"}',
      );
      rethrow;
    } finally {
      ctrl.removeListener(listener);
    }
  }

  Future<void> _togglePlayPause() async {
    if (_isPlaying) {
      await _service.pause();
    } else {
      await _service.resume();
    }
  }

  Future<void> _stop() async {
    _controller?.removeListener(_onControllerChanged);
    await _service.stop();
    if (!mounted) return;
    Navigator.of(context).pop();
  }

  Future<void> _openExternal() async {
    // Stop embedded playback without popping the screen
    _controller?.removeListener(_onControllerChanged);
    await _service.stop();

    final url = widget.streamUrl;
    if (url.isEmpty) return;

    await ExternalPlayerService.instance.openInVlc(url);

    if (mounted) Navigator.of(context).pop();
  }

  void _onControllerChanged() {
    if (!mounted) return;
    final state = _controller?.value.playingState;
    setState(() {
      _isPlaying = state == PlayingState.playing;
    });
  }

  void _toggleControls() {
    setState(() => _showControls = !_showControls);
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
    return SystemUiWrapper(child: PopScope(
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) _service.stop();
      },
      child: Scaffold(
        backgroundColor: Colors.black,
        body: GestureDetector(
          onTap: _toggleControls,
          child: Stack(
            fit: StackFit.expand,
            children: [
              _buildPlayer(),
              if (_showControls) _buildOverlay(),
            ],
          ),
        ),
      ),
    ));
  }

  Widget _buildPlayer() {
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
            const Icon(Icons.error_outline, color: _stopColor, size: 48),
            const SizedBox(height: 12),
            const Text(
              'Playback failed.',
              style: TextStyle(color: Colors.white70, fontSize: 14),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _openExternal,
              icon: const Icon(Icons.open_in_new),
              label: const Text('Open in External Player'),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF7F8C8D),
                foregroundColor: Colors.white,
              ),
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

    return const SizedBox.shrink();
  }

  Widget _buildOverlay() {
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xCC000000), Colors.transparent, Color(0xCC000000)],
          stops: [0.0, 0.5, 1.0],
        ),
      ),
      child: Column(
        children: [
          // Top bar – title + back
          _buildTopBar(),
          const Spacer(),
          // Bottom bar – controls
          _buildBottomBar(),
        ],
      ),
    );
  }

  Widget _buildTopBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          IconButton(
            icon: const Icon(Icons.arrow_back, color: Colors.white),
            onPressed: () => Navigator.of(context).pop(),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              widget.title,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.bold,
              ),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          // Open external
          IconButton(
            icon: const Icon(Icons.open_in_new,
                color: Color(0xFF7F8C8D)),
            tooltip: 'Open in VLC',
            onPressed: _openExternal,
          ),
        ],
      ),
    );
  }

  Widget _buildBottomBar() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          // Play/Pause
          IconButton(
            icon: Icon(
              _isPlaying ? Icons.pause : Icons.play_arrow,
              color: Colors.white,
              size: 28,
            ),
            onPressed: _togglePlayPause,
          ),
          // Stop
          IconButton(
            icon: const Icon(Icons.stop, color: _stopColor, size: 28),
            onPressed: _stop,
          ),
          // Mute
          IconButton(
            icon: Icon(
              _isMuted ? Icons.volume_off : Icons.volume_up,
              color: Colors.white,
              size: 24,
            ),
            onPressed: _toggleMute,
          ),
          // Volume slider
          Expanded(
            child: SliderTheme(
              data: SliderThemeData(
                trackHeight: 3,
                activeTrackColor: _sliderActive,
                inactiveTrackColor: _sliderTrack,
                thumbColor: _sliderActive,
                thumbShape:
                    const RoundSliderThumbShape(enabledThumbRadius: 8),
                overlayShape: SliderComponentShape.noOverlay,
              ),
              child: Slider(
                value: _volume,
                min: 0,
                max: 100,
                onChanged: _setVolume,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
