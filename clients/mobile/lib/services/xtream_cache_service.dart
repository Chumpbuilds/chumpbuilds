import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'epg_service.dart';

/// Top-level helper for [compute]: decode a JSON string into a map.
///
/// Must be top-level to satisfy the [compute] isolate boundary requirement.
Map<String, dynamic> _decodeCacheJson(String raw) =>
    jsonDecode(raw) as Map<String, dynamic>;

/// Top-level helper for [compute]: decode a single cache-entry JSON string.
///
/// Must be top-level to satisfy the [compute] isolate boundary requirement.
Map<String, dynamic> _decodeCacheEntryJson(String raw) =>
    jsonDecode(raw) as Map<String, dynamic>;

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
/// - Persists individual cache entries as separate JSON files in the app's
///   support directory (`xtream_cache/`) for cross-session survival.
/// - JSON decode/encode runs on a background isolate via [compute] to avoid
///   GC storms and dropped frames on the main thread.
/// - Default TTL: 24 hours.
/// - Empty results are never cached.
/// - Disk persistence is best-effort — failures are silently ignored so the
///   in-memory cache still works.
class XtreamCacheService {
  XtreamCacheService._internal();
  static final XtreamCacheService _instance = XtreamCacheService._internal();
  factory XtreamCacheService() => _instance;

  static const int _ttlHours = 24;

  /// Legacy SharedPreferences key used before file-based storage.
  /// Kept only for one-time migration on first launch after update.
  static const String _legacyPrefKey = 'xtream_api_cache';

  final Map<String, _CacheEntry> _cache = {};
  bool _loaded = false;

  /// When true, [set] updates the in-memory cache only and skips the disk
  /// write.  Call [flushToStorage] once when done to persist all entries.
  bool _deferPersistence = false;

  // ─── Public API ───────────────────────────────────────────────────────────

  /// Returns cached data for [key] if it exists and has not expired.
  /// Returns `null` on a miss or when the entry is expired.
  ///
  /// Lazily loads persisted cache from disk on the first call.
  Future<dynamic> get(String key) async {
    await ensureLoaded();

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
  ///
  /// When [_deferPersistence] is true the entry is stored in-memory only;
  /// call [flushToStorage] once when all deferred writes are done to persist
  /// all entries with a single parallel file flush.
  Future<void> set(String key, dynamic data) async {
    // Never cache empty results.
    if (data is List && data.isEmpty) return;
    if (data is Map && data.isEmpty) return;

    await ensureLoaded();

    final now = DateTime.now();
    final expiresAt = now.add(const Duration(hours: _ttlHours));
    _cache[key] = _CacheEntry(data: data, timestamp: now, expiresAt: expiresAt);
    debugPrint(
        '[XtreamCache] Stored: $key (expires at ${expiresAt.toIso8601String()})');

    if (!_deferPersistence) {
      await _saveEntryToDisk(key, _cache[key]!);
    }
  }

  /// Enable or disable deferred disk persistence.
  ///
  /// While [defer] is true, [set] will only update the in-memory cache and
  /// skip the file write.  Call [flushToStorage] once all entries have been
  /// stored to persist them all in parallel.
  void setDeferPersistence({required bool defer}) {
    _deferPersistence = defer;
  }

  /// Flush all in-memory cache entries to disk.
  ///
  /// Each entry is written to its own file in parallel, replacing 6+
  /// sequential disk writes with concurrent I/O.  May also be called at any
  /// time to force an immediate disk sync regardless of [_deferPersistence].
  Future<void> flushToStorage() async {
    await Future.wait(
      _cache.entries.map((e) => _saveEntryToDisk(e.key, e.value)),
    );
    debugPrint('[XtreamCache] Flushed ${_cache.length} entries to file cache');
  }

  /// Clears a single [key], or the entire cache when [key] is omitted.
  Future<void> clear([String? key]) async {
    if (key != null) {
      _cache.remove(key);
      debugPrint('[XtreamCache] Cleared: $key');
      await _deleteEntryFile(key);
    } else {
      _cache.clear();
      debugPrint('[XtreamCache] Cleared all entries');
      await _deleteAllEntryFiles();
    }
  }

  /// Returns true if the core content cache (categories + streams for all 3
  /// types) AND the XMLTV EPG data all have at least [minRemainingHours] hours
  /// of life remaining.
  ///
  /// Checks keys: live_categories, live_streams_all, vod_categories,
  /// vod_streams_all, series_categories, series_all.  EPG freshness is tracked
  /// separately by [EpgService] via the `epg_last_downloaded` SharedPreferences
  /// key (to avoid storing large EPG blobs through the platform channel).
  Future<bool> isCacheFresh({int minRemainingHours = 20}) async {
    await ensureLoaded();
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

    // Check EPG freshness via the lightweight timestamp written by EpgService.
    // This avoids storing the ~96 MB parsed EPG blob in SharedPreferences.
    const epgTtlHours = 24;
    final prefs = await SharedPreferences.getInstance();
    final epgTsStr = prefs.getString(EpgService.epgTimestampKey);
    if (epgTsStr == null) return false;
    final epgTs = DateTime.tryParse(epgTsStr);
    if (epgTs == null) return false;
    final epgExpiresAt = epgTs.add(const Duration(hours: epgTtlHours));
    final epgRemaining = epgExpiresAt.difference(now);
    if (epgRemaining.inHours < minRemainingHours) return false;

    return true;
  }

  /// Returns the number of currently cached (non-expired) entries.
  int get entryCount => _cache.values.where((e) => !e.isExpired).length;

  /// Removes all expired entries from the in-memory cache and persists the
  /// result to disk.
  Future<void> cleanupExpired() async {
    await ensureLoaded();
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
      await Future.wait(expired.map(_deleteEntryFile));
    }
  }

  // ─── Disk persistence ─────────────────────────────────────────────────────

  /// Ensures the cache is loaded from disk exactly once per session.
  ///
  /// Public so it can be called from [main.dart] to pre-warm the cache in
  /// parallel with the license-validation network call, hiding the I/O latency
  /// behind the network round-trip.
  Future<void> ensureLoaded() async {
    if (_loaded) return;
    _loaded = true; // set eagerly to prevent re-entrant calls
    await _loadFromDisk();
  }

  // ─── File helpers ──────────────────────────────────────────────────────────

  /// The directory where individual cache-entry files are stored.
  Future<Directory> get _cacheDir async {
    final appDir = await getApplicationSupportDirectory();
    final dir = Directory('${appDir.path}/xtream_cache');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  /// Converts a cache [key] to a safe filename component.
  String _sanitizeKey(String key) => key.replaceAll(RegExp(r'[^\w\-]'), '_');

  /// Recovers the cache key from a file path (inverse of [_sanitizeKey] for
  /// the simple alphanumeric keys we use).
  String _keyFromPath(String path) =>
      path.split(Platform.pathSeparator).last.replaceAll('.json', '');

  /// Writes a single cache entry to its own file.
  Future<void> _saveEntryToDisk(String key, _CacheEntry entry) async {
    try {
      final dir = await _cacheDir;
      final file = File('${dir.path}/${_sanitizeKey(key)}.json');
      await file.writeAsString(jsonEncode(entry.toJson()));
    } catch (e) {
      debugPrint('[XtreamCache] Failed to save $key: $e');
    }
  }

  /// Deletes the file for a single cache [key] (best-effort).
  Future<void> _deleteEntryFile(String key) async {
    try {
      final dir = await _cacheDir;
      final file = File('${dir.path}/${_sanitizeKey(key)}.json');
      if (await file.exists()) await file.delete();
    } catch (e) {
      debugPrint('[XtreamCache] Failed to delete file for $key: $e');
    }
  }

  /// Deletes all entry files in the cache directory (best-effort).
  Future<void> _deleteAllEntryFiles() async {
    try {
      final dir = await _cacheDir;
      if (!await dir.exists()) return;
      final entities =
          await dir.list().where((e) => e.path.endsWith('.json')).toList();
      await Future.wait(entities.map((e) => File(e.path).delete()));
    } catch (e) {
      debugPrint('[XtreamCache] Failed to delete all entry files: $e');
    }
  }

  // ─── Load ─────────────────────────────────────────────────────────────────

  /// Loads all non-expired cache entries from individual files.
  ///
  /// Each file is decoded on a background isolate via [compute] to avoid GC
  /// pressure on the main thread.  Files are read in parallel.
  Future<void> _loadFromDisk() async {
    // One-time migration: move old SharedPreferences blob to individual files.
    await _migrateFromSharedPreferences();

    try {
      final dir = await _cacheDir;
      if (!await dir.exists()) return;

      final entities =
          await dir.list().where((e) => e.path.endsWith('.json')).toList();
      if (entities.isEmpty) return;

      // Read all files concurrently, then decode each on a background isolate.
      final raws = await Future.wait(
        entities.map((e) => File(e.path).readAsString()),
      );

      int loaded = 0;
      for (int i = 0; i < entities.length; i++) {
        try {
          final decoded = await compute(_decodeCacheEntryJson, raws[i]);
          final entry = _CacheEntry.fromJson(decoded);
          if (!entry.isExpired) {
            final key = _keyFromPath(entities[i].path);
            _cache[key] = entry;
            loaded++;
          } else {
            // Remove stale file proactively.
            await File(entities[i].path).delete();
          }
        } catch (_) {
          // Skip malformed entries silently.
        }
      }
      debugPrint('[XtreamCache] Loaded $loaded entries from file cache');
    } catch (e) {
      debugPrint('[XtreamCache] Failed to load file cache: $e');
    }
  }

  // ─── Migration ────────────────────────────────────────────────────────────

  /// Migrates the old single SharedPreferences blob to individual files.
  ///
  /// Runs once on the first launch after an update that switches to
  /// file-based storage.  After migration the old key is deleted so this
  /// method becomes a no-op on all subsequent launches.
  Future<void> _migrateFromSharedPreferences() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_legacyPrefKey);
      if (raw == null || raw.isEmpty) return;

      debugPrint('[XtreamCache] Migrating SharedPreferences blob to file cache…');

      // Decode on a background isolate — the blob can be 80-100 MB.
      final decoded = await compute(_decodeCacheJson, raw);

      int migrated = 0;
      for (final entry in decoded.entries) {
        try {
          final ce = _CacheEntry.fromJson(entry.value as Map<String, dynamic>);
          if (!ce.isExpired) {
            _cache[entry.key] = ce;
            await _saveEntryToDisk(entry.key, ce);
            migrated++;
          }
        } catch (_) {}
      }

      // Remove the old blob so SharedPreferences stays lean.
      await prefs.remove(_legacyPrefKey);
      debugPrint(
          '[XtreamCache] Migrated $migrated entries; removed legacy SharedPreferences blob');
    } catch (e) {
      debugPrint('[XtreamCache] Migration from SharedPreferences failed: $e');
    }
  }
}
