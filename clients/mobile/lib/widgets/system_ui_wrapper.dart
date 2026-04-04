import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A wrapper widget that keeps the system status and navigation bars hidden
/// (using [SystemUiMode.immersiveSticky]) and temporarily shows them when the
/// user touches the top ~40 logical pixels of the screen.
///
/// Usage: wrap every screen's root widget with [SystemUiWrapper].
///
/// ```dart
/// return SystemUiWrapper(
///   child: Scaffold(...),
/// );
/// ```
class SystemUiWrapper extends StatefulWidget {
  const SystemUiWrapper({super.key, required this.child});

  final Widget child;

  @override
  State<SystemUiWrapper> createState() => _SystemUiWrapperState();
}

class _SystemUiWrapperState extends State<SystemUiWrapper>
    with WidgetsBindingObserver {
  /// Taps with a `dy` at or below this threshold (in logical pixels) are
  /// treated as top-edge taps and temporarily reveal the system UI.
  static const double _topEdgeTapThreshold = 40.0;

  Timer? _hideTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _hideSystemUI());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _hideTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // Re-hide the system UI when the app is resumed (e.g. after a phone call).
    if (state == AppLifecycleState.resumed) {
      _hideSystemUI();
    }
  }

  void _hideSystemUI() {
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      systemNavigationBarColor: Colors.transparent,
    ));
  }

  void _onTapDown(TapDownDetails details) {
    final dy = details.localPosition.dy;
    if (dy > _topEdgeTapThreshold) return; // only react to touches in the top 40 logical pixels

    // Cancel any running hide timer.
    _hideTimer?.cancel();

    // Show all system overlays temporarily.
    SystemChrome.setEnabledSystemUIMode(
      SystemUiMode.manual,
      overlays: SystemUiOverlay.values,
    );

    // Auto-hide again after 3 seconds.
    _hideTimer = Timer(const Duration(seconds: 3), _hideSystemUI);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.translucent,
      onTapDown: _onTapDown,
      child: widget.child,
    );
  }
}
