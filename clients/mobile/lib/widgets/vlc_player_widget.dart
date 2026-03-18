import 'package:flutter/material.dart';
import 'package:flutter_vlc_player/flutter_vlc_player.dart';
import 'package:url_launcher/url_launcher.dart';

import '../screens/fullscreen_player_screen.dart';
import '../services/vlc_player_service.dart';

/// Embedded VLC player widget with control bar.
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
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _playColor = Color(0xFF27AE60);
  static const Color _stopColor = Color(0xFFE74C3C);
  static const Color _fsColor = Color(0xFF3498DB);
  static const Color _extColor = Color(0xFF7F8C8D);
  static const Color _muteColor = Color(0xFF2C3E50);
  static const Color _disabledColor = Color(0xFF95A5A6);
  static const Color _sliderTrack = Color(0xFF34495E);
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

  Future<void> _startPlayback() async {
    if (widget.streamUrl.isEmpty) return;
    setState(() {
      _isLoading = true;
      _hasError = false;
    });

    try {
      final ctrl = await _service.play(
        widget.streamUrl,
        widget.title,
        widget.contentType,
      );

      // Apply current volume/mute
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
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
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
    return Column(
      children: [
        _buildVideoArea(),
        _buildControlBar(),
      ],
    );
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

  Widget _buildControlBar() {
    final hasStream = widget.streamUrl.isNotEmpty;
    return Container(
      color: _surfaceColor,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          // ▶ Play
          _ControlButton(
            icon: Icons.play_arrow,
            color: hasStream ? _playColor : _disabledColor,
            tooltip: 'Play',
            onPressed: hasStream && !_isPlaying ? _startPlayback : null,
          ),
          // ⏹ Stop
          _ControlButton(
            icon: Icons.stop,
            color: _controller != null ? _stopColor : _disabledColor,
            tooltip: 'Stop',
            onPressed: _controller != null ? _stopPlayback : null,
          ),
          // ⛶ Fullscreen
          _ControlButton(
            icon: Icons.fullscreen,
            color: _controller != null ? _fsColor : _disabledColor,
            tooltip: 'Fullscreen',
            onPressed: _controller != null ? _goFullscreen : null,
          ),
          // ↗ Open in VLC
          _ControlButton(
            icon: Icons.open_in_new,
            color: hasStream ? _extColor : _disabledColor,
            tooltip: 'Open in VLC',
            onPressed: hasStream ? _openExternal : null,
          ),
          // 🔊 Mute
          _ControlButton(
            icon: _isMuted ? Icons.volume_off : Icons.volume_up,
            color: _muteColor,
            tooltip: _isMuted ? 'Unmute' : 'Mute',
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
                    const RoundSliderThumbShape(enabledThumbRadius: 6),
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

// ─── Helper widget ────────────────────────────────────────────────────────────

const Color _kDisabledColor = Color(0xFF95A5A6);

class _ControlButton extends StatelessWidget {
  const _ControlButton({
    required this.icon,
    required this.color,
    required this.tooltip,
    this.onPressed,
  });

  final IconData icon;
  final Color color;
  final String tooltip;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return Tooltip(
      message: tooltip,
      child: IconButton(
        icon: Icon(
          icon,
          color: onPressed != null ? color : _kDisabledColor,
        ),
        iconSize: 20,
        padding: const EdgeInsets.symmetric(horizontal: 4),
        constraints: const BoxConstraints(),
        splashRadius: 16,
        onPressed: onPressed,
      ),
    );
  }
}
