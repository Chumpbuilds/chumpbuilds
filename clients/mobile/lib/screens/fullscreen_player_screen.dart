import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_vlc_player/flutter_vlc_player.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/vlc_player_service.dart';

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
    _startPlayback();
  }

  @override
  void dispose() {
    _controller?.removeListener(_onControllerChanged);
    _service.stop();
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
    try {
      final ctrl = await _service.play(
        widget.streamUrl,
        widget.title,
        widget.contentType,
      );

      await ctrl.setVolume(_isMuted ? 0 : _volume.toInt());
      ctrl.addListener(_onControllerChanged);

      if (!mounted) return;
      setState(() {
        _controller = ctrl;
        _isPlaying = true;
        _isLoading = false;
      });
    } catch (e) {
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
    await _stop();
    final uri = Uri.parse(widget.streamUrl);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
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
