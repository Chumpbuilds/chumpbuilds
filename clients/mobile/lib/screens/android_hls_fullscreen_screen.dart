import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_vlc_player/flutter_vlc_player.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../widgets/system_ui_wrapper.dart';

// Network-caching values mirrored from VideoPlayerService constants.
const int _kLiveCachingMs = 1000;
const int _kVodCachingMs = 3000;

/// Full-screen video playback screen using flutter_vlc_player (LibVLC).
///
/// Replaces the previous thin launcher that called [NativePlayerActivity] via
/// platform channel. Now renders VLC directly in Flutter for reliable playback
/// on Android TV boxes, Fire Stick, and Amlogic-based devices.
///
/// Features:
///   - Landscape orientation lock
///   - Immersive sticky mode (hides status/navigation bars)
///   - Wakelock while playing
///   - Tap-to-show overlay controls (play/pause, back, title) that auto-hide
///     after 5 seconds (matching the previous NativePlayerActivity behaviour)
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
  late VlcPlayerController _vlcController;
  bool _showControls = true;
  Timer? _hideTimer;

  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    WakelockPlus.enable();

    final networkCaching =
        widget.contentType == 'live' ? _kLiveCachingMs : _kVodCachingMs;

    _vlcController = VlcPlayerController.network(
      widget.streamUrl,
      hwAcc: HwAcc.full,
      autoPlay: true,
      options: VlcPlayerOptions(
        advanced: VlcAdvancedOptions([
          '--network-caching=$networkCaching',
          '--http-user-agent=X87-IPTV-Player/1.0',
          '--no-audio-resampling',
          '--codec=avcodec',
        ]),
      ),
    );

    _startHideTimer();
  }

  @override
  void dispose() {
    _hideTimer?.cancel();
    WakelockPlus.disable();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    _vlcController.dispose();
    super.dispose();
  }

  void _startHideTimer() {
    _hideTimer?.cancel();
    _hideTimer = Timer(const Duration(seconds: 5), () {
      if (mounted) setState(() => _showControls = false);
    });
  }

  void _onTap() {
    setState(() => _showControls = !_showControls);
    if (_showControls) _startHideTimer();
  }

  Future<void> _togglePlayPause() async {
    final isPlaying = _vlcController.value.isPlaying;
    if (isPlaying) {
      await _vlcController.pause();
    } else {
      await _vlcController.play();
    }
    _startHideTimer();
  }

  @override
  Widget build(BuildContext context) {
    return SystemUiWrapper(
      child: Scaffold(
        backgroundColor: Colors.black,
        body: GestureDetector(
          onTap: _onTap,
          child: Stack(
            fit: StackFit.expand,
            children: [
              // ── Video surface ──
              VlcPlayer(
                controller: _vlcController,
                aspectRatio: 16 / 9,
                placeholder: const Center(
                  child: CircularProgressIndicator(
                    color: Color(0xFF3498DB),
                  ),
                ),
              ),

              // ── Overlay controls ──
              if (_showControls) _buildControls(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildControls() {
    return AnimatedOpacity(
      opacity: _showControls ? 1.0 : 0.0,
      duration: const Duration(milliseconds: 300),
      child: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [
              Color(0xCC000000),
              Colors.transparent,
              Colors.transparent,
              Color(0xCC000000),
            ],
            stops: [0.0, 0.3, 0.7, 1.0],
          ),
        ),
        child: Column(
          children: [
            // ── Top bar: back + title ──
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: 8.0,
                vertical: 4.0,
              ),
              child: Row(
                children: [
                  IconButton(
                    icon: const Icon(
                      Icons.arrow_back,
                      color: Colors.white,
                      size: 28,
                    ),
                    onPressed: () => Navigator.of(context).pop(),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      widget.title,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        shadows: [
                          Shadow(blurRadius: 4, color: Colors.black54),
                        ],
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ),

            const Spacer(),

            // ── Centre play/pause ──
            ValueListenableBuilder<VlcPlayerValue>(
              valueListenable: _vlcController,
              builder: (_, value, __) {
                return IconButton(
                  iconSize: 56,
                  icon: Icon(
                    value.isPlaying ? Icons.pause_circle_filled : Icons.play_circle_filled,
                    color: Colors.white,
                  ),
                  onPressed: _togglePlayPause,
                );
              },
            ),

            const Spacer(),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }
}
