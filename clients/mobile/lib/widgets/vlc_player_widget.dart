import 'package:flutter/material.dart';

import '../services/external_player_service.dart';
import '../services/video_player_service.dart';

/// Embedded video area widget.
///
/// Does **not** render video frames in Flutter. Instead it shows a 16:9 black
/// placeholder with a play button that launches [NativePlayerActivity] via
/// [VideoPlayerService.play]. This bypasses Flutter's PlatformView texture
/// bridge entirely, which is the only reliable path on Android 14+ devices.
///
/// Parameters:
///   [streamUrl]   – HLS/RTSP/HTTP stream URL to play.
///   [title]       – Human-readable title shown in UI.
///   [contentType] – 'live', 'movie', or 'series'.
///   [autoPlay]    – When true and [streamUrl] is non-empty, launches the
///                   native player automatically on first mount.
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
  final bool autoPlay;

  @override
  State<VlcPlayerWidget> createState() => _VlcPlayerWidgetState();
}

class _VlcPlayerWidgetState extends State<VlcPlayerWidget> {
  static const Color _sliderActive = Color(0xFF3498DB);
  static const Color _stopColor = Color(0xFFE74C3C);

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
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _startPlayback();
      });
    }
  }

  @override
  void didUpdateWidget(VlcPlayerWidget old) {
    super.didUpdateWidget(old);
    if (widget.streamUrl != old.streamUrl &&
        widget.autoPlay &&
        widget.streamUrl.isNotEmpty) {
      _startPlayback();
    }
  }

  Future<void> _startPlayback() async {
    if (widget.streamUrl.isEmpty) return;
    setState(() {
      _isLoading = true;
      _hasError = false;
    });

    try {
      await VideoPlayerService.instance.play(
        widget.streamUrl,
        widget.title,
        widget.contentType,
      );
    } catch (e) {
      debugPrint('[VlcPlayerWidget] Playback error: $e');
      if (!mounted) return;
      setState(() => _hasError = true);
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  Future<void> _openExternal() async {
    final url = widget.streamUrl;
    if (url.isEmpty) return;

    final launched = await ExternalPlayerService.instance.openInVlc(url);
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('No video player found. URL: $url')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 16 / 9,
      child: Container(
        color: Colors.black,
        child: _buildContent(),
      ),
    );
  }

  Widget _buildContent() {
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
            const SizedBox(height: 12),
            TextButton(
              onPressed: _openExternal,
              child: const Text(
                'Open in VLC',
                style: TextStyle(color: _sliderActive),
              ),
            ),
          ],
        ),
      );
    }

    if (widget.streamUrl.isEmpty) {
      return Center(
        child: Text(
          _placeholder,
          style: const TextStyle(color: Color(0xFF95A5A6), fontSize: 13),
          textAlign: TextAlign.center,
        ),
      );
    }

    // Show play button overlay on black background.
    return GestureDetector(
      onTap: _startPlayback,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Black background fills the area
          const SizedBox.expand(),
          // Play button
          Container(
            decoration: BoxDecoration(
              color: Colors.black54,
              shape: BoxShape.circle,
            ),
            padding: const EdgeInsets.all(16),
            child: const Icon(
              Icons.play_circle_filled,
              color: Colors.white,
              size: 56,
            ),
          ),
          // Channel title
          Positioned(
            bottom: 16,
            left: 16,
            right: 16,
            child: Text(
              widget.title,
              style: const TextStyle(
                color: Colors.white70,
                fontSize: 13,
                shadows: [Shadow(blurRadius: 4, color: Colors.black87)],
              ),
              textAlign: TextAlign.center,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }
}
