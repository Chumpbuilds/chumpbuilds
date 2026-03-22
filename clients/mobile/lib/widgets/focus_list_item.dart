import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A list-item wrapper that participates in Flutter's focus system so that
/// D-pad / remote-control devices (Fire Stick, Android TV) can navigate to it.
///
/// When focused via D-pad:
///  - Shows a bright cyan left-border strip (3 px) and a subtle tinted overlay.
///  - Activates [onTap] when the Enter / Select / game-pad A key is pressed.
///
/// Touch / mouse interaction is unchanged: [onTap] still fires on a normal tap.
///
/// Usage:
/// ```dart
/// FocusListItem(
///   autofocus: i == 0,   // auto-focus the first item in a list
///   onTap: () => _selectCategory(cat),
///   child: Container(
///     color: selected ? const Color(0xFF2C3E50) : Colors.transparent,
///     padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
///     child: Row(...),
///   ),
/// )
/// ```
class FocusListItem extends StatefulWidget {
  const FocusListItem({
    super.key,
    required this.onTap,
    required this.child,
    this.autofocus = false,
  });

  final VoidCallback onTap;
  final Widget child;

  /// If `true`, this item requests focus as soon as it is first built.
  /// Typically set to `true` for index 0 so the user can immediately navigate
  /// when a list appears.
  final bool autofocus;

  @override
  State<FocusListItem> createState() => _FocusListItemState();
}

class _FocusListItemState extends State<FocusListItem> {
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
        child: Stack(
          children: [
            widget.child,
            // Focused: semi-transparent tinted overlay across the whole item.
            if (_focused)
              Positioned.fill(
                child: ColoredBox(
                  color: const Color(0xFF00E5FF).withAlpha(25),
                ),
              ),
            // Focused: bright 3 px left-border strip.
            if (_focused)
              const Positioned(
                left: 0,
                top: 0,
                bottom: 0,
                width: 3,
                child: ColoredBox(color: Color(0xFF00E5FF)),
              ),
          ],
        ),
      ),
    );
  }
}

/// Returns a [ButtonStyle] that adds a visible white border when the button
/// has focus (D-pad / keyboard navigation) while keeping the [base] style
/// intact for all other interaction states.
ButtonStyle tvFocusButtonStyle(ButtonStyle base) {
  return base.copyWith(
    side: WidgetStateProperty.resolveWith<BorderSide?>((states) {
      if (states.contains(WidgetState.focused)) {
        return const BorderSide(color: Colors.white, width: 2);
      }
      return null;
    }),
    overlayColor: WidgetStateProperty.resolveWith<Color?>((states) {
      if (states.contains(WidgetState.focused)) {
        return Colors.white.withAlpha(38);
      }
      return null;
    }),
  );
}

/// Variant of [tvFocusButtonStyle] for [OutlinedButton] which already carries
/// a visible border.  Keeps the original [defaultSide] when not focused and
/// switches to a bright white border when focused.
ButtonStyle tvFocusOutlinedButtonStyle(
  ButtonStyle base, {
  BorderSide defaultSide = const BorderSide(color: Color(0xFF3D3D3D)),
}) {
  return base.copyWith(
    side: WidgetStateProperty.resolveWith<BorderSide?>((states) {
      if (states.contains(WidgetState.focused)) {
        return const BorderSide(color: Colors.white, width: 2);
      }
      return defaultSide;
    }),
    overlayColor: WidgetStateProperty.resolveWith<Color?>((states) {
      if (states.contains(WidgetState.focused)) {
        return Colors.white.withAlpha(38);
      }
      return null;
    }),
  );
}
