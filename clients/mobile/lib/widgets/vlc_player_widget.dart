import 'package:flutter/material.dart';
import 'package:media_kit_video/media_kit_video.dart';

import '../screens/android_hls_fullscreen_screen.dart';
import '../services/external_player_service.dart';
import '../services/video_player_service.dart';

/// Embedded video player widget (video area only, no control bar).
///
/// Uses media_kit under the hood which supports hardware and software decoding
/// with automatic fallback, working on Android phones, Android TV boxes
/// (including Amlogic-based devices), iOS, and other platforms.
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

  /// media_kit VideoController returned by [VideoPlayerService.play].
  VideoController? _videoController;

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
    VideoPlayerService.instance.stop();
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
      final ctrl = await VideoPlayerService.instance.play(
        widget.streamUrl,
        widget.title,
        widget.contentType,
      );

      if (!mounted) return;
      setState(() {
        _videoController = ctrl;
        _isPlaying = true;
        _isLoading = false;
      });
    } catch (e) {
      debugPrint('[VlcPlayerWidget] Playback error: $e');
      await VideoPlayerService.instance.stop();
      if (!mounted) return;
      setState(() {
        _videoController = null;
        _isLoading = false;
        _hasError = true;
      });
    }
  }

  Future<void> _stopPlayback() async {
    await VideoPlayerService.instance.stop();
    if (!mounted) return;
    setState(() {
      _videoController = null;
      _isPlaying = false;
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
    if (_videoController == null) return;
    await VideoPlayerService.instance.stop();
    if (!mounted) return;
    setState(() {
      _videoController = null;
      _isPlaying = false;
    });

    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => AndroidHlsFullscreenScreen(
          streamUrl: widget.streamUrl,
          title: widget.title,
          contentType: widget.contentType,
        ),
      ),
    );
    if (mounted && widget.streamUrl.isNotEmpty) {
      await _startPlayback();
    }
  }

  Future<void> _setVolume(double v) async {
    setState(() => _volume = v);
    await VideoPlayerService.instance.setVolume(v.toInt());
  }

  Future<void> _toggleMute() async {
    await VideoPlayerService.instance.toggleMute();
    if (!mounted) return;
    setState(() => _isMuted = VideoPlayerService.instance.isMuted);
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

    final ctrl = _videoController;
    if (ctrl != null) {
      return Video(controller: ctrl);
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

