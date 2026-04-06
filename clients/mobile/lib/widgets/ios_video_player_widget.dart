import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

/// iOS-specific inline video player backed by AVFoundation via [video_player].
///
/// Plays [url] inline inside the Flutter widget tree. If [autoPlay] is true,
/// playback starts immediately after the controller is initialized.
///
/// Tapping the video surface calls [onTapped], which the parent widget can use
/// to trigger fullscreen via the existing platform-channel flow.
class IosVideoPlayerWidget extends StatefulWidget {
  const IosVideoPlayerWidget({
    super.key,
    required this.url,
    required this.title,
    required this.contentType,
    this.autoPlay = true,
    this.onTapped,
  });

  final String url;
  final String title;
  final String contentType;
  final bool autoPlay;
  final VoidCallback? onTapped;

  @override
  State<IosVideoPlayerWidget> createState() => _IosVideoPlayerWidgetState();
}

class _IosVideoPlayerWidgetState extends State<IosVideoPlayerWidget> {
  static const Color _accentColor = Color(0xFF3498DB);

  VideoPlayerController? _controller;
  bool _initialized = false;
  bool _hasError = false;

  @override
  void initState() {
    super.initState();
    _initController(widget.url);
  }

  @override
  void didUpdateWidget(IosVideoPlayerWidget old) {
    super.didUpdateWidget(old);
    if (widget.url != old.url) {
      _disposeController();
      _initController(widget.url);
    }
  }

  Future<void> _initController(String url) async {
    if (url.isEmpty) return;

    setState(() {
      _initialized = false;
      _hasError = false;
    });

    final Uri uri;
    try {
      uri = Uri.parse(url);
    } catch (_) {
      debugPrint('[IosVideoPlayerWidget] Invalid URL: $url');
      if (mounted) setState(() => _hasError = true);
      return;
    }

    final controller = VideoPlayerController.networkUrl(uri);
    _controller = controller;

    try {
      await controller.initialize();
      if (!mounted || _controller != controller) {
        controller.dispose();
        return;
      }
      setState(() => _initialized = true);
      if (widget.autoPlay) {
        await controller.play();
      }
    } catch (e) {
      debugPrint('[IosVideoPlayerWidget] Init error: $e');
      if (!mounted || _controller != controller) {
        controller.dispose();
        return;
      }
      setState(() => _hasError = true);
    }
  }

  void _disposeController() {
    final c = _controller;
    _controller = null;
    _initialized = false;
    _hasError = false;
    c?.dispose();
  }

  @override
  void dispose() {
    _disposeController();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_hasError) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, color: Color(0xFFE74C3C), size: 36),
            SizedBox(height: 8),
            Text(
              'Playback failed.',
              style: TextStyle(color: Colors.white70, fontSize: 12),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    if (!_initialized || _controller == null) {
      return const Center(
        child: CircularProgressIndicator(color: _accentColor),
      );
    }

    return GestureDetector(
      onTap: widget.onTapped,
      child: AspectRatio(
        aspectRatio: _controller!.value.aspectRatio,
        child: VideoPlayer(_controller!),
      ),
    );
  }
}
