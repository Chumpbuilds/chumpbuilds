import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../utils/hardware_id.dart';

/// Singleton service that mirrors the logic in `clients/windows/license_validator.py`.
///
/// Responsibilities:
///  - Generate and cache a stable hardware ID.
///  - Store / retrieve the license key and user settings via [SharedPreferences].
///  - Validate the license against the X87 server.
///  - Expose helpers for app-level customisations and cloud profiles.
class LicenseService {
  LicenseService._internal();
  static final LicenseService _instance = LicenseService._internal();
  factory LicenseService() => _instance;

  static const String _licenseServerBase =
      'https://admin.x87player.xyz';
  static const String _prefKeyLicense = 'license_key';
  static const String _prefKeyUserSettings = 'user_settings';
  static const String _prefKeyCloudProfiles = 'cloud_profiles';

  String? _licenseKey;
  Map<String, dynamic> _userSettings = {};
  List<dynamic> _cloudProfiles = [];
  String? _hardwareId;
  bool _isValidated = false;

  // ─── Public getters ───────────────────────────────────────────────────────

  bool get isLicenseValid => _isValidated && _licenseKey != null;

  // ─── Initialisation ───────────────────────────────────────────────────────

  /// Generates (and caches) the hardware ID if not already done.
  Future<String> get hardwareId async {
    _hardwareId ??= await generateHardwareId();
    return _hardwareId!;
  }

  // ─── Public API ───────────────────────────────────────────────────────────

  /// Check for a stored license and silently re-validate it with the server.
  ///
  /// Returns `true` if a valid stored license was found and confirmed.
  /// Returns `false` if no stored license exists or it failed re-validation.
  Future<bool> validateLicense() async {
    debugPrint('[License] Starting license validation...');
    final prefs = await SharedPreferences.getInstance();
    final storedKey = prefs.getString(_prefKeyLicense) ?? '';

    if (storedKey.isEmpty) {
      debugPrint('[License] No stored license found');
      return false;
    }

    debugPrint('[License] Found stored license: ${storedKey.substring(0, 8)}...');
    final result = await validateWithServer(storedKey);

    if (result['success'] == true) {
      _licenseKey = storedKey;
      _userSettings = Map<String, dynamic>.from(
          result['user_settings'] as Map? ?? {});
      _cloudProfiles = result['cloud_profiles'] as List? ?? [];
      _isValidated = true;

      // Merge with cached settings (same logic as Windows client)
      try {
        final cachedRaw = prefs.getString(_prefKeyUserSettings) ?? '{}';
        if (cachedRaw != '{}') {
          final cached = jsonDecode(cachedRaw) as Map<String, dynamic>;
          _userSettings = {...cached, ..._userSettings};
        }
      } catch (e) {
        debugPrint('[License] Error loading cached settings: $e');
      }

      await _persistToPrefs(prefs, storedKey);
      debugPrint(
          '[License] ✅ Stored license validated, ${_cloudProfiles.length} cloud profile(s)');
      return true;
    } else {
      debugPrint(
          '[License] ❌ Stored license invalid: ${result['message']}');
      await clearStoredLicense();
      return false;
    }
  }

  /// POST the given [licenseKey] to the validation endpoint and return the
  /// raw server response map.
  Future<Map<String, dynamic>> validateWithServer(String licenseKey) async {
    final hwId = await hardwareId;
    final platform = Platform.isIOS ? 'iOS' : 'Android';

    final payload = {
      'license_key': licenseKey,
      'hardware_id': hwId,
      'app_version': '1.0.0',
      'platform': platform,
    };

    debugPrint('[License] Validating with server...');
    debugPrint('[License] Sending key: $licenseKey');

    try {
      final response = await http
          .post(
            Uri.parse('$_licenseServerBase/api/license/validate'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 10));

      debugPrint('[License] Server response status: ${response.statusCode}');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        debugPrint('[License] Server success: ${data['success']}');
        return data;
      } else {
        return {
          'success': false,
          'message': 'Server error: HTTP ${response.statusCode}',
        };
      }
    } on SocketException {
      debugPrint('[License] Connection error — server unreachable');
      return {
        'success': false,
        'message':
            'Cannot connect to license server. Please check your internet connection.',
      };
    } on http.ClientException {
      debugPrint('[License] HTTP client error');
      return {
        'success': false,
        'message':
            'Cannot connect to license server. Please check your internet connection.',
      };
    } catch (e) {
      // Covers TimeoutException and any other error.
      debugPrint('[License] Validation error: $e');
      final isTimeout = e.toString().toLowerCase().contains('timeout');
      return {
        'success': false,
        'message': isTimeout
            ? 'License server timeout. Please try again.'
            : 'Validation error: $e',
      };
    }
  }

  /// Activate a new license entered by the user.
  ///
  /// On success, persists everything and returns `{'success': true}`.
  /// On failure, returns `{'success': false, 'message': ...}`.
  Future<Map<String, dynamic>> activateLicense(String licenseKey) async {
    final result = await validateWithServer(licenseKey);

    if (result['success'] == true) {
      _licenseKey = licenseKey;
      _userSettings = Map<String, dynamic>.from(
          result['user_settings'] as Map? ?? {});
      _cloudProfiles = result['cloud_profiles'] as List? ?? [];
      _isValidated = true;

      final prefs = await SharedPreferences.getInstance();
      await _persistToPrefs(prefs, licenseKey);
      debugPrint('[License] ✅ License activation successful');
    }

    return result;
  }

  /// Returns a human-readable status map (mirrors Windows `get_license_info`).
  Future<Map<String, String>> getLicenseInfo() async {
    final hwId = await hardwareId;
    final truncatedHw = '${hwId.substring(0, 16)}...';

    if (!_isValidated || _licenseKey == null) {
      return {
        'status': 'Not Activated',
        'license_key': 'None',
        'hardware_id': truncatedHw,
      };
    }
    final maskedKey = '${_licenseKey!.substring(0, 8)}...';
    return {
      'status': 'Active',
      'license_key': maskedKey,
      'hardware_id': truncatedHw,
    };
  }

  /// Wipe all stored license data (deactivation / sign-out).
  Future<void> clearStoredLicense() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_prefKeyLicense);
    await prefs.remove(_prefKeyUserSettings);
    await prefs.remove(_prefKeyCloudProfiles);
    _licenseKey = null;
    _userSettings = {};
    _cloudProfiles = [];
    _isValidated = false;
    debugPrint('[License] Cleared stored license data');
  }

  /// Returns app-level customisation values (mirrors Windows `get_app_customizations`).
  Map<String, dynamic> getAppCustomizations() {
    final s = _userSettings;
    return {
      'theme': s['theme'] ?? 'dark',
      'app_name': s['app_name'] ?? 'X87 Player',
      'primary_color': s['primary_color'] ?? '#0d7377',
      'accent_color': s['accent_color'] ?? '#64b5f6',
      'logo_url': s['logo_url'] ?? '',
      'background_image': s['background_image'] ?? '',
      'enabled_features': s['enabled_features'] ??
          {
            'live_tv': true,
            'movies': true,
            'search': true,
            'epg': true,
            'series': true,
            'favorites': true,
            'downloads': true,
            'quality_selection': true,
          },
    };
  }

  /// Returns cached cloud profiles.
  List<dynamic> getCloudProfiles() => List.unmodifiable(_cloudProfiles);

  // ─── Private helpers ──────────────────────────────────────────────────────

  Future<void> _persistToPrefs(
      SharedPreferences prefs, String licenseKey) async {
    await prefs.setString(_prefKeyLicense, licenseKey);
    await prefs.setString(_prefKeyUserSettings, jsonEncode(_userSettings));
    await prefs.setString(_prefKeyCloudProfiles, jsonEncode(_cloudProfiles));
  }
}
