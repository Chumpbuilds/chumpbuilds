import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A small icon button that participates in Flutter's focus system so that
/// D-pad / remote-control devices (Fire Stick, Android TV) can navigate to it
/// and see a visual highlight.
///
/// When focused via D-pad:
///  - Shows a circular white border around the icon.
///  - Activates [onPressed] when the Enter / Select / game-pad A key is pressed.
///
/// Touch / mouse interaction is unchanged: [onPressed] still fires on a normal tap.
///
/// Usage:
/// ```dart
/// FocusIconButton(
///   icon: Icons.arrow_back,
///   onPressed: () => Navigator.of(context).pop(),
/// )
/// ```
class FocusIconButton extends StatefulWidget {
  const FocusIconButton({
    super.key,
    required this.icon,
    required this.onPressed,
    this.iconSize = 20,
    this.color,
    this.iconColor = Colors.white,
  });

  final IconData icon;
  final VoidCallback onPressed;

  /// Size of the icon in logical pixels.
  final double iconSize;

  /// Background / border highlight color when focused. Defaults to [Colors.white].
  final Color? color;

  /// Color of the icon itself. Defaults to [Colors.white].
  final Color iconColor;

  @override
  State<FocusIconButton> createState() => _FocusIconButtonState();
}

class _FocusIconButtonState extends State<FocusIconButton> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    final borderColor = widget.color ?? Colors.white;
    return Focus(
      onFocusChange: (hasFocus) => setState(() => _focused = hasFocus),
      onKeyEvent: (node, event) {
        if (event is KeyDownEvent &&
            (event.logicalKey == LogicalKeyboardKey.select ||
                event.logicalKey == LogicalKeyboardKey.enter ||
                event.logicalKey == LogicalKeyboardKey.gameButtonA)) {
          widget.onPressed();
          return KeyEventResult.handled;
        }
        return KeyEventResult.ignored;
      },
      child: GestureDetector(
        onTap: widget.onPressed,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(
              color: _focused ? borderColor : Colors.transparent,
              width: 2,
            ),
          ),
          child: Icon(widget.icon, color: widget.iconColor, size: widget.iconSize),
        ),
      ),
    );
  }
}
