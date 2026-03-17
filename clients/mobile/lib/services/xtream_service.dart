import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

/// Singleton service that mirrors the logic in `clients/windows/auth/xtreme_codes.py`.
///
/// Handles Xtream Codes API authentication and data retrieval.
class XtreamService {
  XtreamService._internal();
  static final XtreamService _instance = XtreamService._internal();
  factory XtreamService() => _instance;

  static const Map<String, String> _headers = {
    'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Cache-Control': 'no-cache',
  };

  String? baseUrl;
  String? username;
  String? password;
  String? profileName;
  Map<String, dynamic>? userInfo;
  Map<String, dynamic>? serverInfo;

  // ─── Public getters ───────────────────────────────────────────────────────

  bool get isAuthenticated => userInfo != null;

  // ─── Authentication ───────────────────────────────────────────────────────

  /// Authenticate with the Xtream Codes API.
  ///
  /// Mirrors `XtremeCodesAPI.login()` from the Windows client.
  ///
  /// Returns a map with keys:
  ///   - `success` (bool)
  ///   - `message` (String)
  ///   - `user_info` (Map, on success)
  ///   - `server_info` (Map, on success)
  Future<Map<String, dynamic>> login(
    String url,
    String username,
    String password,
  ) async {
    // Clean URL: strip trailing slashes and ensure protocol prefix.
    String cleanUrl = url.replaceAll(RegExp(r'/+$'), '');
    if (!cleanUrl.startsWith('http://') && !cleanUrl.startsWith('https://')) {
      cleanUrl = 'http://$cleanUrl';
    }

    debugPrint('[XtreamAPI] Login attempt to: $cleanUrl');

    try {
      final uri = Uri.parse('$cleanUrl/player_api.php').replace(
        queryParameters: {'username': username, 'password': password},
      );

      final response = await http
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 30));

      debugPrint('[XtreamAPI] Response status: ${response.statusCode}');

      if (response.statusCode != 200) {
        return {
          'success': false,
          'message': 'HTTP error ${response.statusCode}',
        };
      }

      Map<String, dynamic> data;
      try {
        data = jsonDecode(response.body) as Map<String, dynamic>;
      } on FormatException {
        debugPrint('[XtreamAPI] JSON decode error');
        return {
          'success': false,
          'message': 'Invalid JSON response from server',
        };
      }

      if (data['user_info'] != null) {
        baseUrl = cleanUrl;
        this.username = username;
        this.password = password;
        userInfo = Map<String, dynamic>.from(data['user_info'] as Map);
        serverInfo = data['server_info'] != null
            ? Map<String, dynamic>.from(data['server_info'] as Map)
            : {};

        debugPrint(
            '[XtreamAPI] ✅ Login successful for user: ${userInfo!['username']}');
        return {
          'success': true,
          'message': 'Login successful',
          'user_info': userInfo,
          'server_info': serverInfo,
        };
      } else {
        debugPrint('[XtreamAPI] ❌ No user_info in response');
        return {
          'success': false,
          'message': 'Invalid credentials or server error',
        };
      }
    } on SocketException catch (e) {
      final msg = e.toString();
      debugPrint('[XtreamAPI] SocketException: $msg');
      if (msg.contains('10054') || msg.toLowerCase().contains('connection reset')) {
        return {
          'success': false,
          'message':
              'Server closed connection (rate limiting?). Wait 10 minutes and try again.',
        };
      }
      return {
        'success': false,
        'message':
            'Cannot connect to server. Please check your internet connection.',
      };
    } on TimeoutException {
      debugPrint('[XtreamAPI] Timeout');
      return {
        'success': false,
        'message': 'Connection timeout. Server took too long to respond.',
      };
    } on http.ClientException catch (e) {
      debugPrint('[XtreamAPI] ClientException: $e');
      return {
        'success': false,
        'message':
            'Cannot connect to server. Please check your internet connection.',
      };
    } catch (e) {
      debugPrint('[XtreamAPI] Unexpected error: $e');
      return {
        'success': false,
        'message': '${e.runtimeType}: $e',
      };
    }
  }

  /// Clear all authentication data (logout).
  void logout() {
    baseUrl = null;
    username = null;
    password = null;
    profileName = null;
    userInfo = null;
    serverInfo = null;
    debugPrint('[XtreamAPI] Logged out');
  }

  // ─── Data retrieval stubs (to be implemented) ─────────────────────────────

  Future<List<dynamic>> getLiveCategories() async =>
      _makeApiRequest('get_live_categories');

  Future<List<dynamic>> getLiveStreams(String? categoryId) async =>
      _makeApiRequest('get_live_streams',
          extraParams: categoryId != null ? {'category_id': categoryId} : null);

  Future<List<dynamic>> getVodCategories() async =>
      _makeApiRequest('get_vod_categories');

  Future<List<dynamic>> getVodStreams(String? categoryId) async =>
      _makeApiRequest('get_vod_streams',
          extraParams: categoryId != null ? {'category_id': categoryId} : null);

  Future<List<dynamic>> getSeriesCategories() async =>
      _makeApiRequest('get_series_categories');

  Future<List<dynamic>> getSeriesStreams(String? categoryId) async =>
      _makeApiRequest('get_series',
          extraParams: categoryId != null ? {'category_id': categoryId} : null);

  /// Build a playback URL for the given stream.
  String getStreamUrl(String streamId, String type, {String? extension}) {
    if (!isAuthenticated || baseUrl == null) return '';
    final ext = extension ?? (type == 'live' ? 'm3u8' : 'mp4');
    return '$baseUrl/$type/$username/$password/$streamId.$ext';
  }

  // ─── Private helpers ──────────────────────────────────────────────────────

  Future<List<dynamic>> _makeApiRequest(
    String action, {
    Map<String, String>? extraParams,
  }) async {
    if (!isAuthenticated) return [];
    try {
      final params = <String, String>{
        'username': username!,
        'password': password!,
        'action': action,
        ...?extraParams,
      };
      final uri = Uri.parse('$baseUrl/player_api.php').replace(
        queryParameters: params,
      );
      final response = await http
          .get(uri, headers: _headers)
          .timeout(const Duration(seconds: 30));
      response.statusCode == 200
          ? debugPrint('[XtreamAPI] $action OK')
          : debugPrint('[XtreamAPI] $action HTTP ${response.statusCode}');
      if (response.statusCode != 200) return [];
      final body = jsonDecode(response.body);
      return body is List ? body : [];
    } catch (e) {
      debugPrint('[XtreamAPI] Error in $action: $e');
      return [];
    }
  }
}
