import 'dart:io';

import 'package:flutter/material.dart';

import '../services/external_player_service.dart';
import '../services/video_player_service.dart';
import 'embedded_exo_player_widget.dart';

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
    this.onStopRequested,
    this.onFullscreenRequested,
  });

  final String streamUrl;
  final String title;
  final String contentType;
  final bool autoPlay;

  /// Called when the widget needs to stop the embedded player, e.g. before
  /// launching an external player. The parent screen should clear the stream
  /// URL so that the embedded ExoPlayer is fully torn down.
  final VoidCallback? onStopRequested;

  /// Called when the user taps the embedded player area to request fullscreen.
  /// The parent screen should stop embedded playback and launch the fullscreen
  /// player (e.g. via [AndroidHlsFullscreenScreen]).
  final VoidCallback? onFullscreenRequested;

  @override
  State<VlcPlayerWidget> createState() => _VlcPlayerWidgetState();
}

class _VlcPlayerWidgetState extends State<VlcPlayerWidget> {
  static const Color _sliderActive = Color(0xFF3498DB);
  static const Color _stopColor = Color(0xFFE74C3C);

  bool _isLoading = false;
  bool _hasError = false;

  // Key used to force-recreate the embedded player when the URL changes.
  Key _embeddedKey = UniqueKey();

  bool get _useEmbedded =>
      Platform.isAndroid && widget.streamUrl.isNotEmpty;

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
    // On Android, EmbeddedExoPlayerWidget handles autoPlay via creation params.
    // The fullscreen _startPlayback path is only used on non-Android platforms.
    if (!Platform.isAndroid &&
        widget.autoPlay &&
        widget.streamUrl.isNotEmpty) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _startPlayback();
      });
    }
  }

  @override
  void didUpdateWidget(VlcPlayerWidget old) {
    super.didUpdateWidget(old);
    if (widget.streamUrl != old.streamUrl) {
      if (Platform.isAndroid) {
        // Changing the key tears down the old AndroidView and creates a fresh one.
        // Also handles the case where URL becomes empty (shows placeholder).
        setState(() {
          _hasError = false;
          _isLoading = false;
          _embeddedKey = UniqueKey();
        });
      } else if (widget.autoPlay && widget.streamUrl.isNotEmpty) {
        _startPlayback();
      } else if (widget.streamUrl.isEmpty) {
        setState(() {
          _hasError = false;
          _isLoading = false;
        });
      }
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

    // Stop the embedded ExoPlayer before launching the external player to
    // avoid two streams playing simultaneously.
    widget.onStopRequested?.call();

    final launched = await ExternalPlayerService.instance.openInVlc(url);
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('No video player found. URL: $url')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return ExcludeFocus(
      child: AspectRatio(
        aspectRatio: 16 / 9,
        child: Container(
          color: Colors.black,
          child: _buildContent(),
        ),
      ),
    );
  }

  Widget _buildContent() {
    // ── Android: render video inline via ExoPlayer PlatformView ──────────────
    if (_useEmbedded) {
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

      return EmbeddedExoPlayerWidget(
        key: _embeddedKey,
        url: widget.streamUrl,
        title: widget.title,
        contentType: widget.contentType,
        autoPlay: widget.autoPlay,
        onTapped: () {
          if (widget.streamUrl.isNotEmpty) {
            widget.onFullscreenRequested?.call();
          }
        },
        onStateChanged: ({
          required bool isPlaying,
          required bool isBuffering,
          required bool hasError,
          String? errorMessage,
        }) {
          if (!mounted) return;
          setState(() {
            _isLoading = isBuffering;
            _hasError = hasError;
          });
        },
        onUnsupportedAudioCodec: (codecs) {
          // Stop embedded player and auto-launch VLC when ExoPlayer detects
          // an audio codec it cannot decode (e.g. EAC3 on Amlogic TV boxes).
          _openExternal();
        },
      );
    }

    // ── Non-Android / placeholder path ────────────────────────────────────────
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
            decoration: const BoxDecoration(
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
