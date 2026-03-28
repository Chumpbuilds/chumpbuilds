import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// A single cache entry holding the cached data, its creation timestamp,
/// and the expiry time.
class _CacheEntry {
  final dynamic data;
  final DateTime timestamp;
  final DateTime expiresAt;

  _CacheEntry({
    required this.data,
    required this.timestamp,
    required this.expiresAt,
  });

  bool get isExpired => DateTime.now().isAfter(expiresAt);

  Map<String, dynamic> toJson() => {
        'data': data,
        'timestamp': timestamp.toIso8601String(),
        'expires_at': expiresAt.toIso8601String(),
      };

  factory _CacheEntry.fromJson(Map<String, dynamic> json) => _CacheEntry(
        data: json['data'],
        timestamp: DateTime.parse(json['timestamp'] as String),
        expiresAt: DateTime.parse(json['expires_at'] as String),
      );
}

/// Singleton cache service for Xtream Codes API responses.
///
/// Mirrors the Windows [EPGCache] pattern
/// (`clients/windows/epg/epg_cache.py`) but covers all content types
/// (live TV, movies, series, EPG).
///
/// - In-memory map for fast lookups during the current session.
/// - Persists to SharedPreferences (single JSON blob) for cross-session
///   survival.
/// - Default TTL: 24 hours.
/// - Empty results are never cached.
/// - Disk persistence is best-effort — failures are silently ignored so the
///   in-memory cache still works.
class XtreamCacheService {
  XtreamCacheService._internal();
  static final XtreamCacheService _instance = XtreamCacheService._internal();
  factory XtreamCacheService() => _instance;

  static const int _ttlHours = 24;
  static const String _prefKey = 'xtream_api_cache';

  final Map<String, _CacheEntry> _cache = {};
  bool _loaded = false;

  // ─── Public API ───────────────────────────────────────────────────────────

  /// Returns cached data for [key] if it exists and has not expired.
  /// Returns `null` on a miss or when the entry is expired.
  ///
  /// Lazily loads persisted cache from disk on the first call.
  Future<dynamic> get(String key) async {
    await _ensureLoaded();

    final entry = _cache[key];
    if (entry == null) {
      debugPrint('[XtreamCache] Miss: $key (not in cache)');
      return null;
    }

    if (entry.isExpired) {
      final diff = DateTime.now().difference(entry.expiresAt);
      debugPrint('[XtreamCache] Expired: $key (expired ${diff.inMinutes}m ago)');
      _cache.remove(key);
      return null;
    }

    final remaining = entry.expiresAt.difference(DateTime.now());
    debugPrint(
        '[XtreamCache] Hit: $key (${(remaining.inMinutes / 60).toStringAsFixed(1)}h remaining)');
    return entry.data;
  }

  /// Stores [data] under [key] with a 24-hour expiry.
  ///
  /// Does nothing if [data] is an empty [List] or empty [Map].
  Future<void> set(String key, dynamic data) async {
    // Never cache empty results.
    if (data is List && data.isEmpty) return;
    if (data is Map && data.isEmpty) return;

    await _ensureLoaded();

    final now = DateTime.now();
    final expiresAt = now.add(const Duration(hours: _ttlHours));
    _cache[key] = _CacheEntry(data: data, timestamp: now, expiresAt: expiresAt);
    debugPrint(
        '[XtreamCache] Stored: $key (expires at ${expiresAt.toIso8601String()})');

    await _saveToDisk();
  }

  /// Clears a single [key], or the entire cache when [key] is omitted.
  Future<void> clear([String? key]) async {
    if (key != null) {
      _cache.remove(key);
      debugPrint('[XtreamCache] Cleared: $key');
    } else {
      _cache.clear();
      debugPrint('[XtreamCache] Cleared all entries');
    }
    await _saveToDisk();
  }

  /// Returns true if the core content cache (categories + streams for all 3
  /// types) has at least [minRemainingHours] hours of life remaining.
  ///
  /// Checks keys: live_categories, live_streams_all, vod_categories,
  /// vod_streams_all, series_categories, series_all
  Future<bool> isCacheFresh({int minRemainingHours = 20}) async {
    await _ensureLoaded();
    const coreKeys = [
      'live_categories',
      'live_streams_all',
      'vod_categories',
      'vod_streams_all',
      'series_categories',
      'series_all',
    ];
    final now = DateTime.now();
    for (final key in coreKeys) {
      final entry = _cache[key];
      if (entry == null || entry.isExpired) return false;
      final remaining = entry.expiresAt.difference(now);
      if (remaining.inHours < minRemainingHours) return false;
    }
    return true;
  }

  /// Returns the number of currently cached (non-expired) entries.
  int get entryCount => _cache.values.where((e) => !e.isExpired).length;

  /// Removes all expired entries from the in-memory cache and persists the
  /// result to disk.
  Future<void> cleanupExpired() async {
    await _ensureLoaded();
    final now = DateTime.now();
    final expired = _cache.entries
        .where((e) => now.isAfter(e.value.expiresAt))
        .map((e) => e.key)
        .toList();
    for (final k in expired) {
      _cache.remove(k);
    }
    if (expired.isNotEmpty) {
      debugPrint('[XtreamCache] Cleaned up ${expired.length} expired entries');
      await _saveToDisk();
    }
  }

  // ─── Disk persistence ─────────────────────────────────────────────────────

  Future<void> _ensureLoaded() async {
    if (_loaded) return;
    _loaded = true; // set eagerly to prevent re-entrant calls
    await _loadFromDisk();
  }

  /// Loads persisted cache entries from SharedPreferences.
  ///
  /// Only entries that have not yet expired are restored.
  Future<void> _loadFromDisk() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_prefKey);
      if (raw == null || raw.isEmpty) return;

      final Map<String, dynamic> stored =
          jsonDecode(raw) as Map<String, dynamic>;
      int loaded = 0;
      for (final entry in stored.entries) {
        try {
          final cacheEntry =
              _CacheEntry.fromJson(entry.value as Map<String, dynamic>);
          if (!cacheEntry.isExpired) {
            _cache[entry.key] = cacheEntry;
            loaded++;
          }
        } catch (_) {
          // Skip malformed entries silently.
        }
      }
      debugPrint('[XtreamCache] Loaded $loaded non-expired entries from disk');
    } catch (e) {
      // Disk load is best-effort; in-memory cache still works.
      debugPrint('[XtreamCache] Could not load from disk: $e');
    }
  }

  /// Persists the current in-memory cache to SharedPreferences.
  Future<void> _saveToDisk() async {
    try {
      final Map<String, dynamic> serializable = {};
      for (final entry in _cache.entries) {
        try {
          serializable[entry.key] = entry.value.toJson();
        } catch (_) {
          // Skip entries that cannot be serialized.
        }
      }
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_prefKey, jsonEncode(serializable));
      debugPrint('[XtreamCache] Saved ${serializable.length} entries to disk');
    } catch (e) {
      debugPrint('[XtreamCache] Could not save to disk: $e');
    }
  }
}
