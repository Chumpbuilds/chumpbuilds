import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A grid-tile wrapper that participates in Flutter's focus system so that
/// D-pad / remote-control devices (Android TV, Fire Stick) can navigate to it.
///
/// When focused via D-pad:
///  - Shows a white border around the tile.
///  - Scales up slightly (1.05×) to give a "pop" effect.
///  - Activates [onTap] when the Enter / Select / game-pad A key is pressed.
///
/// Touch / mouse interaction is unchanged: [onTap] still fires on a normal tap.
///
/// Usage:
/// ```dart
/// FocusGridTile(
///   autofocus: i == 0,   // auto-focus the first tile in a grid
///   onTap: () => _openDetail(item),
///   child: Container(
///     decoration: BoxDecoration(
///       color: _surfaceColor,
///       borderRadius: BorderRadius.circular(6),
///     ),
///     child: ...,
///   ),
/// )
/// ```
class FocusGridTile extends StatefulWidget {
  const FocusGridTile({
    super.key,
    required this.onTap,
    required this.child,
    this.autofocus = false,
  });

  final VoidCallback onTap;
  final Widget child;

  /// If `true`, this tile requests focus as soon as it is first built.
  /// Typically set to `true` for index 0 so the user can immediately navigate
  /// when a grid appears.
  final bool autofocus;

  @override
  State<FocusGridTile> createState() => _FocusGridTileState();
}

class _FocusGridTileState extends State<FocusGridTile> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    return Focus(
      autofocus: widget.autofocus,
      onFocusChange: (hasFocus) => setState(() => _focused = hasFocus),
      onKeyEvent: (node, event) {
        if (event is KeyDownEvent &&
            (event.logicalKey == LogicalKeyboardKey.select ||
                event.logicalKey == LogicalKeyboardKey.enter ||
                event.logicalKey == LogicalKeyboardKey.numpadEnter ||
                event.logicalKey == LogicalKeyboardKey.gameButtonA)) {
          widget.onTap();
          return KeyEventResult.handled;
        }
        return KeyEventResult.ignored;
      },
      child: GestureDetector(
        onTap: widget.onTap,
        child: Transform.scale(
          scale: _focused ? 1.05 : 1.0,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(6),
              border: Border.all(
                color: _focused ? Colors.white : Colors.transparent,
                width: 2,
              ),
            ),
            child: widget.child,
          ),
        ),
      ),
    );
  }
}
