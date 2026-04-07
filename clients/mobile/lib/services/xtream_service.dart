import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'epg_service.dart';
import 'xtream_cache_service.dart';

/// Top-level function used with [compute] to decode a JSON list on a
/// background isolate, avoiding GC pauses on the main isolate for large
/// payloads (VOD streams ~35 MB, Series streams ~47 MB).
List<dynamic> _decodeJsonList(String body) => jsonDecode(body) as List<dynamic>;

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

  final _cache = XtreamCacheService();

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
    _cache.clear();
    debugPrint('[XtreamAPI] Logged out');
  }

  /// Clears all cached API data — useful for pull-to-refresh or manual refresh.
  Future<void> clearCache() => _cache.clear();

  /// Prefetch all core content data (categories + full lists) and cache it.
  ///
  /// [onProgress] is called with (completedSteps, totalSteps, currentLabel)
  /// for UI updates.  Errors in individual steps are swallowed so that a
  /// partial prefetch still navigates forward.
  Future<void> prefetchAll({
    void Function(int completed, int total, String label)? onProgress,
  }) async {
    if (!isAuthenticated) return;

    final steps = <MapEntry<String, Future<void> Function()>>[
      MapEntry('Live TV Categories', () async {
        await getLiveCategories();
      }),
      MapEntry('Live TV Channels', () async {
        await getLiveStreams(null);
      }),
      MapEntry('Movie Categories', () async {
        await getVodCategories();
      }),
      MapEntry('Movies', () async {
        await getVodStreams(null);
      }),
      MapEntry('Series Categories', () async {
        await getSeriesCategories();
      }),
      MapEntry('Series', () async {
        await getSeries(null);
      }),
      MapEntry('EPG Guide', () async {
        await EpgService().downloadAndCacheEpg(baseUrl!, username!, password!);
      }),
    ];

    for (int i = 0; i < steps.length; i++) {
      onProgress?.call(i, steps.length, steps[i].key);
      try {
        await steps[i].value();
      } catch (e) {
        debugPrint('[XtreamAPI] prefetchAll step "${steps[i].key}" error: $e');
      }
    }

    onProgress?.call(steps.length, steps.length, 'Complete');
  }

  // ─── Data retrieval stubs (to be implemented) ─────────────────────────────

  Future<List<dynamic>> getLiveCategories() async {
    const cacheKey = 'live_categories';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return cached as List<dynamic>;
    final result = await _makeApiRequest('get_live_categories');
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  Future<List<dynamic>> getLiveStreams(String? categoryId) async {
    final cacheKey = 'live_streams_${categoryId ?? 'all'}';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return cached as List<dynamic>;
    final result = await _makeApiRequest('get_live_streams',
        extraParams: categoryId != null ? {'category_id': categoryId} : null);
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  Future<List<dynamic>> getVodCategories() async {
    const cacheKey = 'vod_categories';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return cached as List<dynamic>;
    final result = await _makeApiRequest('get_vod_categories');
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  Future<List<dynamic>> getVodStreams(String? categoryId) async {
    final cacheKey = 'vod_streams_${categoryId ?? 'all'}';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return cached as List<dynamic>;
    final result = await _makeApiRequest('get_vod_streams',
        extraParams: categoryId != null ? {'category_id': categoryId} : null);
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  Future<List<dynamic>> getSeriesCategories() async {
    const cacheKey = 'series_categories';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return cached as List<dynamic>;
    final result = await _makeApiRequest('get_series_categories');
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  Future<List<dynamic>> getSeries(String? categoryId) async {
    final cacheKey = 'series_${categoryId ?? 'all'}';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return cached as List<dynamic>;
    final result = await _makeApiRequest('get_series',
        extraParams: categoryId != null ? {'category_id': categoryId} : null);
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  /// Fetch detailed info for a VOD item (plot, cast, director, etc.).
  ///
  /// Returns a Map with `info` and `movie_data` keys, or an empty map on error.
  Future<Map<String, dynamic>> getVodInfo(String vodId) async {
    final cacheKey = 'vod_info_$vodId';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return Map<String, dynamic>.from(cached as Map);
    final result =
        await _makeApiRequestMap('get_vod_info', extraParams: {'vod_id': vodId});
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  /// Fetch detailed info for a series (info, seasons, episodes).
  ///
  /// Returns a Map with `info`, `seasons`, and `episodes` keys, or empty map.
  Future<Map<String, dynamic>> getSeriesInfo(String seriesId) async {
    final cacheKey = 'series_info_$seriesId';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return Map<String, dynamic>.from(cached as Map);
    final result = await _makeApiRequestMap('get_series_info',
        extraParams: {'series_id': seriesId});
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  /// Fetch short EPG data for a live stream.
  ///
  /// Returns a Map (usually with `epg_listings` key), or empty map on error.
  Future<Map<String, dynamic>> getShortEpg(String streamId) async {
    final cacheKey = 'epg_$streamId';
    final cached = await _cache.get(cacheKey);
    if (cached != null) return Map<String, dynamic>.from(cached as Map);
    final result = await _makeApiRequestMap('get_short_epg',
        extraParams: {'stream_id': streamId});
    if (result.isNotEmpty) await _cache.set(cacheKey, result);
    return result;
  }

  /// Build a playback URL for the given stream.
  ///
  /// [type] is one of: `live`, `movie`, `series`.
  /// [extension] overrides the default file extension.
  /// [streamData] can provide `container_extension` as fallback.
  /// [preferTs] when true, uses `.ts` instead of `.m3u8` for live streams.
  /// Many IPTV providers serve AAC audio in the TS container and EAC3/AC3 in
  /// the HLS/m3u8 container — requesting TS avoids codec compatibility issues
  /// on Android TV boxes that lack Dolby audio decoders.
  String getStreamUrl(
    String streamId,
    String type, {
    String? extension,
    Map<String, dynamic>? streamData,
    bool preferTs = false,
  }) {
    if (!isAuthenticated || baseUrl == null) return '';
    String ext;
    if (extension != null && extension.isNotEmpty) {
      ext = extension;
    } else if (streamData != null &&
        streamData['container_extension'] != null &&
        (streamData['container_extension'] as String).isNotEmpty) {
      ext = streamData['container_extension'] as String;
    } else if (type == 'live' && preferTs) {
      ext = 'ts';
    } else {
      ext = type == 'live' ? 'm3u8' : 'mp4';
    }

    // On iOS, always request HLS for movies/series. Even .mp4 containers can
    // hold HEVC (hev1) video that AVPlayer renders as a black screen on some
    // devices. HLS repackaging by the Xtream server normalises codec signaling
    // so AVPlayer handles every codec correctly.
    if (Platform.isIOS && type != 'live') {
      ext = 'm3u8';
    }

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
      // Decode on a background isolate to avoid GC pauses on the main thread
      // for large payloads (e.g. VOD/Series streams are 35-47 MB).
      final body = await compute(_decodeJsonList, response.body);
      return body;
    } catch (e) {
      debugPrint('[XtreamAPI] Error in $action: $e');
      return [];
    }
  }

  /// Like [_makeApiRequest] but returns a [Map] instead of a [List].
  Future<Map<String, dynamic>> _makeApiRequestMap(
    String action, {
    Map<String, String>? extraParams,
  }) async {
    if (!isAuthenticated) return {};
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
      if (response.statusCode != 200) return {};
      final body = jsonDecode(response.body);
      return body is Map ? Map<String, dynamic>.from(body as Map) : {};
    } catch (e) {
      debugPrint('[XtreamAPI] Error in $action: $e');
      return {};
    }
  }
}
