import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _prefKeyFallbackId = 'hardware_id_fallback';

/// Generates a stable, unique hardware identifier for the current device.
///
/// On Android: SHA-256 of androidId + model + manufacturer + brand.
/// On iOS:     SHA-256 of identifierForVendor + model + name.
/// Fallback:   A random 32-byte hex string generated once, then persisted in
///             [SharedPreferences] so it remains stable across app launches.
Future<String> generateHardwareId() async {
  try {
    final plugin = DeviceInfoPlugin();
    String combined;

    if (Platform.isAndroid) {
      final info = await plugin.androidInfo;
      final androidId = info.id; // stable per-device ID
      combined =
          '${androidId}_${info.model}_${info.manufacturer}_${info.brand}';
    } else if (Platform.isIOS) {
      final info = await plugin.iosInfo;
      final vendor = info.identifierForVendor ?? 'unknown';
      combined = '${vendor}_${info.model}_${info.name}';
    } else {
      // Web / desktop fallback (shouldn't reach in production mobile builds)
      combined = '${Platform.operatingSystem}-fallback';
    }

    final bytes = utf8.encode(combined);
    return sha256.convert(bytes).toString();
  } catch (e) {
    debugPrint('[HardwareID] Error generating hardware ID: $e');
    return _stableFallbackId();
  }
}

/// Returns a stable fallback ID.
///
/// On the first call a random 32-byte hex string is generated and stored
/// in [SharedPreferences].  Subsequent calls return the same stored value.
Future<String> _stableFallbackId() async {
  try {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getString(_prefKeyFallbackId);
    if (stored != null && stored.isNotEmpty) return stored;

    // Generate a new random 32-byte hex string and persist it.
    final rng = Random.secure();
    final randomBytes = List<int>.generate(32, (_) => rng.nextInt(256));
    final id = randomBytes
        .map((b) => b.toRadixString(16).padLeft(2, '0'))
        .join();
    await prefs.setString(_prefKeyFallbackId, id);
    return id;
  } catch (e) {
    // If even SharedPreferences fails (very unlikely), return a session-only value.
    debugPrint('[HardwareID] Fallback ID error: $e');
    final rng = Random.secure();
    final randomBytes = List<int>.generate(32, (_) => rng.nextInt(256));
    return randomBytes
        .map((b) => b.toRadixString(16).padLeft(2, '0'))
        .join();
  }
}
