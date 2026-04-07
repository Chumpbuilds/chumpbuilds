import 'dart:async';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

/// iOS-specific inline video player backed by AVFoundation via [video_player].
///
/// Plays [url] inline inside the Flutter widget tree. If [autoPlay] is true,
/// playback starts immediately after the controller is initialized.
///
/// Tapping the video surface calls [onTapped], which the parent widget can use
/// to trigger fullscreen via the existing platform-channel flow.
///
/// Stall recovery: a periodic timer checks whether the playback position has
/// advanced. If it has not moved for [_stallThreshold] while the player
/// reports [isPlaying] or [isBuffering], the controller is torn down and
/// re-initialised automatically.
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

  // Stall recovery: check every 5 s; if position has not advanced for
  // [_stallThreshold] while the player reports isPlaying/isBuffering, restart.
  static const _stallCheckInterval = Duration(seconds: 5);
  static const _stallThreshold = Duration(seconds: 10);

  VideoPlayerController? _controller;
  bool _initialized = false;
  bool _hasError = false;

  Timer? _stallTimer;
  Duration? _lastKnownPosition;
  DateTime? _lastPositionAdvancedAt;

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
    controller.addListener(_onControllerUpdate);

    try {
      await controller.initialize();
      if (!mounted || _controller != controller) {
        controller.dispose();
        return;
      }
      setState(() => _initialized = true);
      if (widget.autoPlay) {
        await controller.play();
        _startStallMonitor();
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

  // ── Stall detection ────────────────────────────────────────────────────────

  void _onControllerUpdate() {
    final ctrl = _controller;
    if (ctrl == null) return;
    if (ctrl.value.hasError) {
      debugPrint('[IosVideoPlayerWidget] Error: ${ctrl.value.errorDescription}');
      if (mounted) _recover();
    }
  }

  void _startStallMonitor() {
    _stallTimer?.cancel();
    _lastKnownPosition = null;
    _lastPositionAdvancedAt = null;
    _stallTimer = Timer.periodic(_stallCheckInterval, (_) => _checkStall());
  }

  void _stopStallMonitor() {
    _stallTimer?.cancel();
    _stallTimer = null;
  }

  void _checkStall() {
    final ctrl = _controller;
    if (ctrl == null || !_initialized) return;
    final v = ctrl.value;
    // Only act when the player is supposed to be active.
    if (!v.isPlaying && !v.isBuffering) return;

    final pos = v.position;
    final now = DateTime.now();
    if (_lastKnownPosition == null || pos != _lastKnownPosition) {
      _lastKnownPosition = pos;
      _lastPositionAdvancedAt = now;
      return;
    }
    // Position is unchanged — check whether we have exceeded the threshold.
    if (_lastPositionAdvancedAt != null &&
        now.difference(_lastPositionAdvancedAt!) >= _stallThreshold) {
      debugPrint(
        '[IosVideoPlayerWidget] Stall detected '
        '(${_stallThreshold.inSeconds}s without progress), recovering',
      );
      _recover();
    }
  }

  void _recover() {
    _stopStallMonitor();
    if (!mounted) return;
    final url = widget.url;
    _disposeController();
    _initController(url);
  }

  // ── Controller lifecycle ───────────────────────────────────────────────────

  void _disposeController() {
    _stopStallMonitor();
    final c = _controller;
    _controller = null;
    _initialized = false;
    _hasError = false;
    c?.removeListener(_onControllerUpdate);
    c?.dispose();
  }

  @override
  void dispose() {
    _disposeController();
    super.dispose();
  }

  // ── UI ─────────────────────────────────────────────────────────────────────

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
