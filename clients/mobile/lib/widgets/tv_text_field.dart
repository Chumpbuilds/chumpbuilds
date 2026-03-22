import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A [TextField] wrapper that implements a two-stage focus model for
/// D-pad / remote-control navigation on Android TV and Fire Stick devices.
///
/// **Stage 1 – focused, not editing:**  
/// When the widget receives focus via D-pad navigation it shows a highlighted
/// border (using [focusedBorderColor]) but keeps the underlying [TextField] in
/// read-only mode so the on-screen keyboard is *not* opened.
///
/// **Stage 2 – editing:**  
/// When the user presses the Enter / Select key (or taps the widget on a
/// touch-screen device) the field becomes editable and the keyboard opens.
/// Pressing the Back key closes the keyboard and returns the field to
/// Stage 1 so the user can continue navigating away with the D-pad.
///
/// On regular touch-screen phones and tablets the widget behaves like a
/// normal [TextField] – tapping it immediately opens the keyboard (no
/// two-stage behaviour is needed).
class TvTextField extends StatefulWidget {
  const TvTextField({
    super.key,
    required this.controller,
    this.focusNode,
    this.enabled = true,
    this.obscureText = false,
    this.style,
    this.decoration,
    this.maxLength,
    this.textCapitalization = TextCapitalization.none,
    this.onSubmitted,
    this.focusedBorderColor = const Color(0xFF0D7377),
  });

  final TextEditingController controller;
  final FocusNode? focusNode;
  final bool enabled;
  final bool obscureText;
  final TextStyle? style;
  final InputDecoration? decoration;
  final int? maxLength;
  final TextCapitalization textCapitalization;
  final ValueChanged<String>? onSubmitted;

  /// The border color used when the widget is focused but not yet in editing
  /// mode (Stage 1).  Defaults to the app's primary teal color.
  final Color focusedBorderColor;

  @override
  State<TvTextField> createState() => _TvTextFieldState();
}

class _TvTextFieldState extends State<TvTextField> {
  late final FocusNode _outerFocus;
  late final FocusNode _innerFocus;

  /// Whether the field is currently in editing mode (keyboard visible).
  bool _isEditing = false;

  /// Whether a D-pad / hardware-keyboard is driving focus (no touch-screen).
  bool _isDpadMode = false;

  @override
  void initState() {
    super.initState();
    _outerFocus = widget.focusNode ?? FocusNode();
    _innerFocus = FocusNode();
    _innerFocus.canRequestFocus = false;

    _outerFocus.addListener(_onOuterFocusChange);
    _innerFocus.addListener(_onInnerFocusChange);
  }

  @override
  void dispose() {
    _outerFocus.removeListener(_onOuterFocusChange);
    _innerFocus.removeListener(_onInnerFocusChange);

    // Only dispose nodes that we created internally.
    if (widget.focusNode == null) _outerFocus.dispose();
    _innerFocus.dispose();
    super.dispose();
  }

  void _onOuterFocusChange() {
    if (!_outerFocus.hasFocus) {
      // Lost focus entirely – leave editing mode.
      if (_isEditing) {
        _exitEditingMode();
      }
    }
  }

  void _onInnerFocusChange() {
    if (!_innerFocus.hasFocus && _isEditing) {
      // The inner text field lost focus (e.g. keyboard closed by Back key).
      _exitEditingMode();
      // Return focus to the outer container so D-pad navigation still works.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _outerFocus.requestFocus();
      });
    }
  }

  void _enterEditingMode() {
    if (!widget.enabled) return;
    _innerFocus.canRequestFocus = true;
    setState(() => _isEditing = true);
    // Delay slightly to let the widget rebuild before requesting focus.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _innerFocus.requestFocus();
    });
  }

  void _exitEditingMode() {
    _innerFocus.canRequestFocus = false;
    setState(() => _isEditing = false);
  }

  KeyEventResult _handleKeyEvent(FocusNode node, KeyEvent event) {
    // Detect D-pad / remote: once we see a hardware-key event we know the
    // device is being driven by a remote or keyboard (not purely touch).
    if (!_isDpadMode) {
      setState(() => _isDpadMode = true);
    }

    if (!_isEditing &&
        event is KeyDownEvent &&
        (event.logicalKey == LogicalKeyboardKey.enter ||
            event.logicalKey == LogicalKeyboardKey.numpadEnter ||
            event.logicalKey == LogicalKeyboardKey.select ||
            event.logicalKey == LogicalKeyboardKey.gameButtonA)) {
      _enterEditingMode();
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  @override
  Widget build(BuildContext context) {
    final bool isFocused = _outerFocus.hasFocus || _innerFocus.hasFocus;

    // In D-pad mode, show a highlighted border when focused but not editing.
    InputDecoration? decoration = widget.decoration;
    if (_isDpadMode && isFocused && !_isEditing && decoration != null) {
      final existingBorder = decoration.enabledBorder;
      final borderRadius = existingBorder is OutlineInputBorder
          ? existingBorder.borderRadius
          : BorderRadius.circular(4);
      decoration = decoration.copyWith(
        enabledBorder: OutlineInputBorder(
          borderRadius: borderRadius,
          borderSide: BorderSide(color: widget.focusedBorderColor, width: 2),
        ),
      );
    }

    return Focus(
      focusNode: _outerFocus,
      onKeyEvent: _handleKeyEvent,
      child: GestureDetector(
        onTap: () {
          // Touch-screen tap: always enter editing mode immediately.
          if (!_isEditing) _enterEditingMode();
        },
        child: TextField(
          controller: widget.controller,
          focusNode: _innerFocus,
          enabled: widget.enabled,
          // Keep read-only while not editing so the keyboard stays closed.
          readOnly: !_isEditing,
          obscureText: widget.obscureText,
          style: widget.style,
          decoration: decoration,
          maxLength: widget.maxLength,
          textCapitalization: widget.textCapitalization,
          onSubmitted: (value) {
            widget.onSubmitted?.call(value);
            // After submitting, return to non-editing state.
            _exitEditingMode();
            WidgetsBinding.instance.addPostFrameCallback((_) {
              _outerFocus.requestFocus();
            });
          },
        ),
      ),
    );
  }
}
