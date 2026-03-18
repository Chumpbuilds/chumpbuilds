import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

/// Wraps [child] and forces a specific set of device orientations while this
/// page is visible, restoring the previous set when it is disposed.
class OrientationPage extends StatefulWidget {
  const OrientationPage({
    super.key,
    required this.child,
    this.orientations = const [
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ],
    this.restoreOrientations = const [
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ],
  });

  final Widget child;

  /// Orientations to enforce while this widget is alive.
  final List<DeviceOrientation> orientations;

  /// Orientations to restore when this widget is disposed.
  final List<DeviceOrientation> restoreOrientations;

  @override
  State<OrientationPage> createState() => _OrientationPageState();
}

class _OrientationPageState extends State<OrientationPage> {
  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations(widget.orientations);
  }

  @override
  void dispose() {
    SystemChrome.setPreferredOrientations(widget.restoreOrientations);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
