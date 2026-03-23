import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:video_player/video_player.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../services/external_player_service.dart';
import '../services/video_player_service.dart';

/// Full-screen video playback screen for Android HLS streams.
///
/// Used instead of [FullscreenPlayerScreen] when playing HLS (.m3u8) content
/// on Android, routing through the ExoPlayer-backed [video_player] package
/// rather than the LibVLC / flutter_vlc_player path that has proven
/// unreliable on Android for these streams.
///
/// UX is intentionally kept identical to [FullscreenPlayerScreen]:
/// - Fills the entire screen with the video player.
/// - Tap to show/hide controls overlay (play/pause, stop, volume, back).
/// - Back button or Android back gesture returns to the previous screen.
/// - Landscape orientation is enforced for the duration of this screen.
class AndroidHlsFullscreenScreen extends StatefulWidget {
  const AndroidHlsFullscreenScreen({
    super.key,
    required this.streamUrl,
    required this.title,
    required this.contentType,
  });

  final String streamUrl;
  final String title;
  final String contentType;

  @override
  State<AndroidHlsFullscreenScreen> createState() =>
      _AndroidHlsFullscreenScreenState();
}

class _AndroidHlsFullscreenScreenState
    extends State<AndroidHlsFullscreenScreen> {
  // ─── Theme ────────────────────────────────────────────────────────────────
  static const Color _stopColor = Color(0xFFE74C3C);
  static const Color _sliderTrack = Color(0xFF34495E);
  static const Color _sliderActive = Color(0xFF3498DB);

  // ─── State ────────────────────────────────────────────────────────────────
  final _service = VideoPlayerService.instance;
  VideoPlayerController? _controller;
  bool _isPlaying = false;
  bool _isMuted = false;
  double _volume = 80;
  bool _showControls = true;
  bool _isLoading = true;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
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

  Future<void> _startPlayback() async {
    VideoPlayerController? ctrl;
    try {
      ctrl = await _service.play(
        widget.streamUrl,
        widget.title,
        widget.contentType,
      );

      ctrl.addListener(_onControllerChanged);

      if (!mounted) return;
      setState(() {
        _controller = ctrl;
        _isPlaying = true;
        _isLoading = false;
      });

      await ctrl.setVolume(_isMuted ? 0.0 : _volume / 100.0);
    } catch (e) {
      debugPrint('[HlsFullscreen] Playback error: $e');
      ctrl?.removeListener(_onControllerChanged);
      await _service.stop();
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _hasError = true;
      });
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
    _controller?.removeListener(_onControllerChanged);
    await _service.stop();

    final url = widget.streamUrl;
    if (url.isEmpty) return;

    await ExternalPlayerService.instance.openInVlc(url);

    if (mounted) Navigator.of(context).pop();
  }

  void _onControllerChanged() {
    if (!mounted) return;
    setState(() {
      _isPlaying = _controller?.value.isPlaying ?? false;
    });
  }

  void _toggleControls() {
    setState(() => _showControls = !_showControls);
  }

  Future<void> _setVolume(double v) async {
    setState(() => _volume = v);
    await _service.setVolume(v.toInt());
    if (!_isMuted) {
      await _controller?.setVolume(v / 100.0);
    }
  }

  Future<void> _toggleMute() async {
    await _service.toggleMute();
    if (!mounted) return;
    setState(() => _isMuted = _service.isMuted);
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return PopScope(
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
    );
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

    final ctrl = _controller;
    if (ctrl != null && ctrl.value.isInitialized) {
      return Center(
        child: AspectRatio(
          aspectRatio: ctrl.value.aspectRatio,
          child: VideoPlayer(ctrl),
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
          _buildTopBar(),
          const Spacer(),
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
          IconButton(
            icon: const Icon(Icons.open_in_new, color: Color(0xFF7F8C8D)),
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
          IconButton(
            icon: Icon(
              _isPlaying ? Icons.pause : Icons.play_arrow,
              color: Colors.white,
              size: 28,
            ),
            onPressed: _togglePlayPause,
          ),
          IconButton(
            icon: const Icon(Icons.stop, color: _stopColor, size: 28),
            onPressed: _stop,
          ),
          IconButton(
            icon: Icon(
              _isMuted ? Icons.volume_off : Icons.volume_up,
              color: Colors.white,
              size: 24,
            ),
            onPressed: _toggleMute,
          ),
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
