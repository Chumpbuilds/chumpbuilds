import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Wraps an [AndroidView] that hosts a native ExoPlayer [PlayerView] surface,
/// allowing video to render **inline** inside the Flutter widget tree.
///
/// One per-view [MethodChannel] (named
/// `com.x87player/exo_player_view/<viewId>`) is established after the
/// platform view is created. Playback state changes sent by the native side
/// via `onPlaybackStateChanged` are surfaced through the [onStateChanged]
/// callback.
///
/// On non-Android platforms the widget falls back to a black placeholder —
/// the caller ([VlcPlayerWidget]) is expected to handle the fallback UI.
class EmbeddedExoPlayerWidget extends StatefulWidget {
  const EmbeddedExoPlayerWidget({
    super.key,
    required this.url,
    required this.title,
    required this.contentType,
    this.autoPlay = true,
    this.year,
    this.tmdbId,
    this.onStateChanged,
    this.onTapped,
    this.onUnsupportedAudioCodec,
  });

  final String url;
  final String title;
  final String contentType;
  final bool autoPlay;

  /// Optional year and TMDB ID forwarded to the native side for subtitle search.
  final String? year;
  final String? tmdbId;

  /// Called whenever the native player reports a state change.
  final void Function({
    required bool isPlaying,
    required bool isBuffering,
    required bool hasError,
    String? errorMessage,
  })? onStateChanged;

  /// Called when the user taps the native player surface.
  final VoidCallback? onTapped;

  /// Called when ExoPlayer detects a selected audio track that cannot be
  /// decoded on this device (e.g. EAC3/AC3 on Amlogic boxes without Dolby
  /// decoders). The parent should stop the embedded player and launch an
  /// external player (e.g. VLC) that bundles software decoders.
  ///
  /// [codecs] contains the MIME types / codec strings of the unsupported tracks.
  final void Function(List<String> codecs)? onUnsupportedAudioCodec;

  @override
  State<EmbeddedExoPlayerWidget> createState() =>
      _EmbeddedExoPlayerWidgetState();
}

class _EmbeddedExoPlayerWidgetState extends State<EmbeddedExoPlayerWidget> {
  static const String _viewType = 'com.x87player/exo_player_view';

  MethodChannel? _channel;

  bool _isBuffering = true;
  bool _hasError = false;
  String? _errorMessage;

  // ── Lifecycle ─────────────────────────────────────────────────────────────

  @override
  void dispose() {
    _channel?.invokeMethod<void>('dispose').ignore();
    _channel?.setMethodCallHandler(null);
    super.dispose();
  }

  // ── Channel wiring ────────────────────────────────────────────────────────

  void _onPlatformViewCreated(int viewId) {
    final ch = MethodChannel('com.x87player/exo_player_view/$viewId');
    ch.setMethodCallHandler(_handleNativeCall);
    _channel = ch;
  }

  Future<dynamic> _handleNativeCall(MethodCall call) async {
    if (call.method == 'onTapped') {
      widget.onTapped?.call();
    } else if (call.method == 'onPlaybackStateChanged') {
      final args = call.arguments as Map;
      final isPlaying = args['isPlaying'] as bool? ?? false;
      final isBuffering = args['isBuffering'] as bool? ?? false;
      final hasError = args['hasError'] as bool? ?? false;
      final errorMessage = args['errorMessage'] as String?;

      if (mounted) {
        setState(() {
          _isBuffering = isBuffering;
          _hasError = hasError;
          _errorMessage = errorMessage;
        });
      }

      widget.onStateChanged?.call(
        isPlaying: isPlaying,
        isBuffering: isBuffering,
        hasError: hasError,
        errorMessage: errorMessage,
      );
    } else if (call.method == 'onUnsupportedAudioCodec') {
      final args = call.arguments as Map;
      final rawCodecs = args['codecs'];
      final codecs = rawCodecs is List
          ? rawCodecs.map((e) => e.toString()).toList()
          : <String>[];
      debugPrint('[ExoPlayer] Unsupported audio codec detected: $codecs — launching VLC');
      widget.onUnsupportedAudioCodec?.call(codecs);
    }
  }

  // ── Public control API ────────────────────────────────────────────────────
  // These methods can be invoked by a parent widget that holds a GlobalKey
  // to this widget's State, e.g. to implement custom fullscreen controls that
  // need to pause/resume the embedded player programmatically.

  Future<void> play(String url) =>
      _channel?.invokeMethod<void>('play', {'url': url}) ?? Future.value();

  Future<void> pause() =>
      _channel?.invokeMethod<void>('pause') ?? Future.value();

  Future<void> resume() =>
      _channel?.invokeMethod<void>('resume') ?? Future.value();

  Future<void> stop() =>
      _channel?.invokeMethod<void>('stop') ?? Future.value();

  /// Sets volume in [0.0, 1.0] range.
  Future<void> setVolume(double volume) =>
      _channel?.invokeMethod<void>('setVolume', {'volume': volume}) ?? Future.value();

  Future<void> toggleMute() =>
      _channel?.invokeMethod<void>('toggleMute') ?? Future.value();

  /// Sets the resize mode of the player view.
  /// [mode] values: 0=fit, 1=fixedWidth, 2=fixedHeight, 3=fill, 4=zoom.
  Future<void> setResizeMode(int mode) =>
      _channel?.invokeMethod<void>('setResizeMode', {'mode': mode}) ?? Future.value();

  /// Opens the native subtitle search + selection dialog.
  ///
  /// The native side searches the subtitle API using the content title, year
  /// and TMDB ID passed via creation params. The user can pick a subtitle (or
  /// "Off") from the list; the chosen track is downloaded and injected as an
  /// SRT sidecar — the same flow used by the fullscreen [NativePlayerActivity].
  /// Subtitles are NOT auto-enabled on initial playback; this must be called
  /// explicitly (e.g. from a CC button in the parent widget).
  Future<void> showSubtitlePicker() =>
      _channel?.invokeMethod<void>('showSubtitlePicker') ?? Future.value();

  // ── Build ─────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    if (!Platform.isAndroid) {
      return const SizedBox.expand();
    }

    return Stack(
      fit: StackFit.expand,
      children: [
        AndroidView(
          viewType: _viewType,
          onPlatformViewCreated: _onPlatformViewCreated,
          creationParams: {
            'url': widget.url,
            'title': widget.title,
            'contentType': widget.contentType,
            'autoPlay': widget.autoPlay,
            if (widget.year != null) 'year': widget.year!,
            if (widget.tmdbId != null) 'tmdbId': widget.tmdbId!,
          },
          creationParamsCodec: const StandardMessageCodec(),
        ),
        if (_isBuffering && !_hasError)
          const Center(
            child: CircularProgressIndicator(
              color: Color(0xFF3498DB),
            ),
          ),
        if (_hasError)
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error_outline, color: Color(0xFFE74C3C), size: 36),
                const SizedBox(height: 8),
                Text(
                  _errorMessage ?? 'Playback error',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
      ],
    );
  }
}
