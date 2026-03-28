import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:xml/xml.dart';

/// Parses an XMLTV timestamp string ("YYYYMMDDHHmmss +HHMM") into a UTC
/// [DateTime]. Returns `null` if the string cannot be parsed.
///
/// This is a top-level helper so it can be used inside [compute] isolates.
DateTime? _parseXmltvTime(String? raw) {
  if (raw == null || raw.isEmpty) return null;
  final s = raw.trim();
  if (s.length < 14 || !RegExp(r'^\d{14}').hasMatch(s)) return null;
  try {
    final year   = int.parse(s.substring(0, 4));
    final month  = int.parse(s.substring(4, 6));
    final day    = int.parse(s.substring(6, 8));
    final hour   = int.parse(s.substring(8, 10));
    final minute = int.parse(s.substring(10, 12));
    final second = int.parse(s.substring(12, 14));
    final rest   = s.substring(14).trim();
    if (rest.isNotEmpty &&
        (rest.startsWith('+') || rest.startsWith('-')) &&
        rest.length >= 5) {
      final sign       = rest[0] == '+' ? 1 : -1;
      final offH       = int.tryParse(rest.substring(1, 3)) ?? 0;
      final offM       = int.tryParse(rest.substring(3, 5)) ?? 0;
      final offsetMins = sign * (offH * 60 + offM);
      // Convert to UTC: local time = UTC + offset, so UTC = local - offset
      return DateTime.utc(year, month, day, hour, minute, second)
          .subtract(Duration(minutes: offsetMins));
    }
    return DateTime.utc(year, month, day, hour, minute, second);
  } catch (_) {
    return null;
  }
}

/// Top-level isolate function for parsing XMLTV content.
///
/// Accepts raw UTF-8 bytes to avoid re-encoding overhead during isolate
/// message passing. Returns a map keyed by `epg_channel_id` (the XMLTV
/// `channel` attribute on each `<programme>` element). Each value is a list
/// of programme maps with `title`, `description`, `start` (UTC ISO-8601), and
/// `stop` (UTC ISO-8601).
///
/// Must be top-level for use with [compute].
Map<String, List<Map<String, dynamic>>> _parseXmltvIsolate(List<int> bytes) {
  final result = <String, List<Map<String, dynamic>>>{};
  try {
    final xmlContent = utf8.decode(bytes);
    final document = XmlDocument.parse(xmlContent);
    for (final programme in document.findAllElements('programme')) {
      final channelId = programme.getAttribute('channel');
      if (channelId == null || channelId.isEmpty) continue;

      final startRaw = programme.getAttribute('start');
      final stopRaw  = programme.getAttribute('stop');
      final start    = _parseXmltvTime(startRaw);
      final stop     = _parseXmltvTime(stopRaw);

      final title       = programme.findElements('title').firstOrNull?.innerText ?? '';
      final description = programme.findElements('desc').firstOrNull?.innerText ?? '';

      result.putIfAbsent(channelId, () => []);
      result[channelId]!.add({
        'title':       title,
        'description': description,
        'start':       start?.toIso8601String() ?? '',
        'stop':        stop?.toIso8601String() ?? '',
      });
    }
  } catch (_) {
    // Return whatever was successfully parsed before the error.
  }
  return result;
}

/// Singleton service that downloads the full XMLTV EPG file from the Xtream
/// Codes server, parses it, and provides fast in-memory lookups.
///
/// The raw XMLTV XML is saved to a file on disk so that large EPG data never
/// passes through SharedPreferences / the Flutter platform channel (which has
/// a hard memory limit that causes OutOfMemoryError with ~96 MB payloads).
///
/// Usage:
/// ```dart
/// // During startup prefetch:
/// await EpgService().downloadAndCacheEpg(baseUrl, username, password);
///
/// // When a channel is selected:
/// final listings = EpgService().getEpgForChannel(channel['epg_channel_id']);
/// final nowPlaying = EpgService().getNowPlaying(channel['epg_channel_id']);
/// ```
class EpgService {
  EpgService._internal();
  static final EpgService _instance = EpgService._internal();
  factory EpgService() => _instance;

  /// SharedPreferences key for the ISO-8601 download timestamp.
  /// Also read by [XtreamCacheService.isCacheFresh] to verify EPG freshness.
  static const String epgTimestampKey = 'epg_last_downloaded';

  static const String _epgFileName = 'xmltv_epg.xml';
  static const int _ttlHours = 24;
  static const Map<String, String> _headers = {
    'User-Agent':
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept':          '*/*',
    'Accept-Encoding': 'gzip, deflate',
    'Connection':      'keep-alive',
  };

  /// In-memory EPG data keyed by `epg_channel_id`.
  ///
  /// Values are lists of programme maps with `title`, `description`, `start`,
  /// and `stop` fields. The `is_current` field is computed dynamically in
  /// [getEpgForChannel].
  Map<String, List<Map<String, dynamic>>>? _epgData;

  // ─── Private helpers ───────────────────────────────────────────────────────

  /// Returns the on-disk XMLTV cache file using the app documents directory.
  Future<File> _getEpgFile() async {
    final dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/$_epgFileName');
  }

  // ─── Public API ────────────────────────────────────────────────────────────

  /// Returns true if the EPG file was downloaded recently enough that
  /// [minRemainingHours] hours are still remaining on its 24-hour TTL.
  Future<bool> isEpgFresh({int minRemainingHours = 20}) async {
    final prefs = await SharedPreferences.getInstance();
    final tsStr = prefs.getString(epgTimestampKey);
    if (tsStr == null) return false;
    final ts = DateTime.tryParse(tsStr);
    if (ts == null) return false;
    final expiresAt = ts.add(const Duration(hours: _ttlHours));
    final remaining = expiresAt.difference(DateTime.now());
    return remaining.inHours >= minRemainingHours;
  }

  /// Downloads the full XMLTV EPG file from
  /// `{baseUrl}/xmltv.php?username=…&password=…`, saves the raw bytes to disk,
  /// parses the result in a background isolate, and keeps it in memory.
  ///
  /// If a fresh on-disk copy already exists it is loaded without
  /// re-downloading. Errors are swallowed so a failure never blocks navigation.
  Future<void> downloadAndCacheEpg(
    String baseUrl,
    String username,
    String password,
  ) async {
    // If data is already in memory and still fresh, nothing to do.
    final fresh = await isEpgFresh();
    if (_epgData != null && fresh) return;

    // If the on-disk file is still fresh, parse it instead of re-downloading.
    if (fresh) {
      await loadFromCache();
      if (_epgData != null) return;
    }

    // Download the XMLTV file.
    final url = '$baseUrl/xmltv.php?username=$username&password=$password';
    debugPrint('[EpgService] Downloading XMLTV from $url');
    try {
      final response = await http
          .get(Uri.parse(url), headers: _headers)
          .timeout(const Duration(minutes: 5));

      if (response.statusCode != 200) {
        debugPrint('[EpgService] XMLTV HTTP ${response.statusCode}');
        return;
      }

      final bytes = response.bodyBytes;
      final sizeMb = (bytes.length / 1024 / 1024).toStringAsFixed(1);
      debugPrint('[EpgService] Parsing XMLTV ($sizeMb MB) in isolate…');

      // Parse in a background isolate to avoid blocking the UI thread.
      final epgData = await compute(_parseXmltvIsolate, bytes);

      _epgData = epgData;
      debugPrint('[EpgService] Parsed EPG for ${epgData.length} channels');

      // Save raw bytes to disk — avoids SharedPreferences size limits entirely.
      final file = await _getEpgFile();
      await file.writeAsBytes(bytes, flush: true);

      // Store only the download timestamp in SharedPreferences (a few bytes).
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(epgTimestampKey, DateTime.now().toIso8601String());
      debugPrint('[EpgService] EPG saved to disk and timestamp recorded');
    } catch (e) {
      debugPrint('[EpgService] Error downloading/parsing XMLTV: $e');
    }
  }

  /// Loads EPG data from the on-disk XMLTV file into memory without
  /// re-downloading. Call this at app startup when the cache is already fresh
  /// (i.e., the loading screen is skipped).
  ///
  /// Returns immediately if data is already in memory.
  Future<void> loadFromCache() async {
    if (_epgData != null) return;
    try {
      final file = await _getEpgFile();
      if (!await file.exists()) return;
      final bytes = await file.readAsBytes();
      if (bytes.isEmpty) return;
      debugPrint('[EpgService] Re-parsing XMLTV from disk in isolate…');
      final epgData = await compute(_parseXmltvIsolate, bytes);
      if (epgData.isNotEmpty) {
        _epgData = epgData;
        debugPrint('[EpgService] Loaded EPG from disk (${_epgData!.length} channels)');
      }
    } catch (e) {
      debugPrint('[EpgService] Error loading from disk: $e');
    }
  }

  /// Returns the EPG programme listings for [epgChannelId].
  ///
  /// Each entry contains:
  /// - `title`       – programme title (plain text)
  /// - `description` – programme description
  /// - `start`       – ISO-8601 UTC start time string
  /// - `stop`        – ISO-8601 UTC stop time string
  /// - `is_current`  – `true` if the programme is currently airing
  ///
  /// Returns an empty list if [epgChannelId] is empty, unknown, or EPG data
  /// has not been loaded.
  List<Map<String, dynamic>> getEpgForChannel(String epgChannelId) {
    if (epgChannelId.isEmpty || _epgData == null) return [];
    final raw = _epgData![epgChannelId];
    if (raw == null || raw.isEmpty) return [];

    final now = DateTime.now().toUtc();
    return raw.map((p) {
      final start = p['start'] != null ? DateTime.tryParse(p['start'] as String) : null;
      final stop  = p['stop']  != null ? DateTime.tryParse(p['stop']  as String) : null;
      final isCurrent = start != null &&
          stop  != null &&
          now.isAfter(start) &&
          now.isBefore(stop);
      return {...p, 'is_current': isCurrent};
    }).toList();
  }

  /// Returns the currently-airing programme for [epgChannelId], or `null` if
  /// nothing is currently airing (or no EPG data is available).
  Map<String, dynamic>? getNowPlaying(String epgChannelId) {
    for (final p in getEpgForChannel(epgChannelId)) {
      if (p['is_current'] == true) return p;
    }
    return null;
  }
}
