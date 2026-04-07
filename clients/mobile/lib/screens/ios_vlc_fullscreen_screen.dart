import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_vlc_player/flutter_vlc_player.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

/// iOS fullscreen video player backed by VLC.
///
/// Used for movies and series on iOS where AVPlayer cannot handle all container
/// formats (MKV, AVI, etc.). VLC's codec library plays everything.
/// Live TV continues to use AVPlayer via the native platform channel.
class IosVlcFullscreenScreen extends StatefulWidget {
  const IosVlcFullscreenScreen({
    super.key,
    required this.streamUrl,
    required this.title,
    required this.contentType,
  });

  final String streamUrl;
  final String title;
  final String contentType;

  @override
  State<IosVlcFullscreenScreen> createState() => _IosVlcFullscreenScreenState();
}

class _IosVlcFullscreenScreenState extends State<IosVlcFullscreenScreen> {
  late VlcPlayerController _controller;
  bool _isBuffering = true;
  bool _showControls = true;
  Timer? _hideTimer;

  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersive);
    WakelockPlus.enable();

    _controller = VlcPlayerController.network(
      widget.streamUrl,
      hwAcc: HwAcc.full,
      autoPlay: true,
      options: VlcPlayerOptions(
        http: VlcHttpOptions([
          VlcHttpOptions.httpReconnect(true),
        ]),
      ),
    );

    _controller.addListener(_onPlayerEvent);
    _startHideTimer();
  }

  void _onPlayerEvent() {
    if (!mounted) return;
    final playing = _controller.value.isPlaying;
    final buffering = _controller.value.isBuffering;
    setState(() {
      _isBuffering = buffering && !playing;
    });

    // Auto-pop if playback ended
    if (_controller.value.isEnded) {
      Navigator.of(context).pop();
    }
  }

  void _startHideTimer() {
    _hideTimer?.cancel();
    _hideTimer = Timer(const Duration(seconds: 4), () {
      if (mounted) setState(() => _showControls = false);
    });
  }

  void _toggleControls() {
    setState(() => _showControls = !_showControls);
    if (_showControls) _startHideTimer();
  }

  @override
  void dispose() {
    _hideTimer?.cancel();
    _controller.removeListener(_onPlayerEvent);
    _controller.stop();
    _controller.dispose();
    WakelockPlus.disable();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: GestureDetector(
        onTap: _toggleControls,
        child: Stack(
          fit: StackFit.expand,
          children: [
            // VLC video surface
            Center(
              child: VlcPlayer(
                controller: _controller,
                aspectRatio: 16 / 9,
                placeholder: const Center(
                  child: CircularProgressIndicator(
                    color: Color(0xFF3498DB),
                  ),
                ),
              ),
            ),
            // Buffering overlay
            if (_isBuffering)
              const Center(
                child: CircularProgressIndicator(
                  color: Color(0xFF3498DB),
                ),
              ),
            // Controls overlay
            if (_showControls)
              Container(
                color: Colors.black38,
                child: SafeArea(
                  child: Column(
                    children: [
                      // Top bar with title and close button
                      Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 8),
                        child: Row(
                          children: [
                            IconButton(
                              icon: const Icon(Icons.arrow_back,
                                  color: Colors.white, size: 28),
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
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                          ],
                        ),
                      ),
                      const Spacer(),
                      // Center play/pause button
                      IconButton(
                        iconSize: 64,
                        icon: Icon(
                          _controller.value.isPlaying
                              ? Icons.pause_circle_filled
                              : Icons.play_circle_filled,
                          color: Colors.white,
                        ),
                        onPressed: () async {
                          if (_controller.value.isPlaying) {
                            await _controller.pause();
                          } else {
                            await _controller.play();
                          }
                          _startHideTimer();
                        },
                      ),
                      const Spacer(),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
