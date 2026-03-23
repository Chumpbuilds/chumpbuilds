import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// A [TextField] wrapper that implements a two-stage focus model for
/// D-pad / remote-control navigation on Android TV and Fire Stick devices,
/// while behaving exactly like a normal [TextField] on touch-screen devices.
///
/// **D-pad mode – Stage 1 (focused, not editing):**
/// When the widget receives focus via D-pad navigation it shows a highlighted
/// border (using [focusedBorderColor]) but keeps the on-screen keyboard closed.
///
/// **D-pad mode – Stage 2 (editing):**
/// When the user presses the Enter / Select key the field becomes editable and
/// the keyboard opens. Pressing the Back key closes the keyboard and returns
/// the field to Stage 1 so the user can continue navigating away with the
/// D-pad.
///
/// **Touch mode:**
/// Tapping the widget immediately opens the keyboard, just like a normal
/// [TextField]. No two-stage behaviour is required.
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
    if (!_outerFocus.hasFocus && _isEditing) {
      // Lost outer focus entirely while editing – leave editing mode.
      _exitEditingMode();
    } else if (mounted) {
      // No state change is needed, but we must rebuild so the D-pad border
      // highlight (which depends on _outerFocus.hasFocus) appears/disappears.
      setState(() {});
    }
  }

  void _onInnerFocusChange() {
    if (_innerFocus.hasFocus) {
      // Inner TextField gained focus → we are now in editing mode.
      if (!_isEditing) {
        if (kDebugMode) debugPrint('TvTextField: inner focus gained → editing');
        setState(() => _isEditing = true);
      }
    } else if (_isEditing) {
      // Inner TextField lost focus (keyboard closed, Back key, tap elsewhere).
      if (kDebugMode) debugPrint('TvTextField: inner focus lost → exiting editing');
      _exitEditingMode();
      // Return focus to the outer container so D-pad navigation still works.
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _outerFocus.requestFocus();
      });
    }
  }

  /// Activates editing mode in response to a D-pad Enter / Select key press.
  ///
  /// For D-pad, we use a [WidgetsBinding.addPostFrameCallback] before
  /// requesting focus because focus traversal may still be in-progress during
  /// the key-event handler.  [_isEditing] is NOT set here; it will be set to
  /// `true` asynchronously by [_onInnerFocusChange] once the inner focus node
  /// actually receives focus.
  void _enterEditingMode() {
    if (!widget.enabled) return;
    if (kDebugMode) debugPrint('TvTextField: _enterEditingMode (dpad=$_isDpadMode)');
    _innerFocus.canRequestFocus = true;
    // Delay until after the current frame so the focus system is ready.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _innerFocus.requestFocus();
    });
  }

  void _exitEditingMode() {
    _innerFocus.canRequestFocus = false;
    if (_isEditing) setState(() => _isEditing = false);
  }

  /// Called when a touch or stylus pointer-down event is detected.
  ///
  /// Synchronously enables the inner [FocusNode] so the tap that follows
  /// naturally requests focus and opens the on-screen keyboard.  No explicit
  /// [requestFocus] call is needed here because [TextField] handles it
  /// internally when it receives the tap.
  ///
  /// Why synchronous (no postFrameCallback)?  Unlike the D-pad path, the
  /// pointer-down event fires *before* the tap is dispatched to the
  /// [TextField], so setting [FocusNode.canRequestFocus] here takes effect
  /// before the [TextField]'s own focus request runs in the same frame.
  /// A postFrameCallback would fire *after* the tap, too late to unblock
  /// the inner focus node.
  void _onTouchPointerDown() {
    if (!widget.enabled) return;
    if (kDebugMode) {
      debugPrint('TvTextField: touch pointer-down → enabling inner focus');
    }
    // Allow the inner TextField to accept focus so the tap opens the keyboard.
    _innerFocus.canRequestFocus = true;
    // Leaving D-pad mode clears the Stage-1 border highlight on next rebuild.
    if (_isDpadMode) {
      setState(() => _isDpadMode = false);
    }
    // _isEditing will be updated by _onInnerFocusChange once focus is gained.
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

    // Listener (not GestureDetector) is used to detect touch pointer-down
    // events without competing in the gesture arena.  This ensures the tap
    // propagates naturally to the inner TextField so it can request focus and
    // open the IME by itself — avoiding the readOnly + programmatic-focus
    // timing issue that prevented the keyboard from opening on Android phones.
    return Listener(
      onPointerDown: (PointerDownEvent event) {
        if (event.kind == PointerDeviceKind.touch ||
            event.kind == PointerDeviceKind.stylus) {
          _onTouchPointerDown();
        }
      },
      child: Focus(
        focusNode: _outerFocus,
        onKeyEvent: _handleKeyEvent,
        child: TextField(
          controller: widget.controller,
          focusNode: _innerFocus,
          enabled: widget.enabled,
          // Never use readOnly here.  The keyboard is controlled exclusively
          // by whether _innerFocus.canRequestFocus is true — if the inner node
          // cannot accept focus, the TextField never receives focus and the
          // IME stays closed.  Using readOnly: true caused a race condition on
          // Android where the IME was not triggered after a programmatic focus
          // change following a touch tap.
          readOnly: false,
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
              if (mounted) _outerFocus.requestFocus();
            });
          },
        ),
      ),
    );
  }
}
