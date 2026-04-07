import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';

/// Singleton that caches the result of the native isTvOrAmlogicDevice() check.
/// On non-Android platforms, always returns false.
class DeviceTypeService {
  DeviceTypeService._();
  static final DeviceTypeService instance = DeviceTypeService._();

  static const _channel = MethodChannel('com.x87player/native_player');

  bool? _isTvDevice;

  /// Returns true on Android TV, Fire Stick, and Amlogic-based boxes.
  /// Caches the result after the first call. Returns false on iOS and
  /// other non-Android platforms.
  Future<bool> isTvDevice() async {
    if (_isTvDevice != null) return _isTvDevice!;
    if (!Platform.isAndroid) {
      _isTvDevice = false;
      return false;
    }
    try {
      final result = await _channel.invokeMethod<bool>('isTvDevice');
      _isTvDevice = result ?? false;
    } catch (e) {
      debugPrint('[DeviceTypeService] isTvDevice call failed: $e');
      _isTvDevice = false;
    }
    return _isTvDevice!;
  }
}
