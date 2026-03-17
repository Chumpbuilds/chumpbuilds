import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Types of content that can be favourited.
enum FavoriteType { channel, movie, series }

/// Singleton service that persists favourites in SharedPreferences.
///
/// Keys:
///   `favorites_channels` — JSON array of channel metadata maps
///   `favorites_movies`   — JSON array of movie metadata maps
///   `favorites_series`   — JSON array of series metadata maps
///
/// Each stored item contains at minimum:
///   `stream_id` (or `series_id`), `name`, `stream_icon` / `cover`.
class FavoritesService {
  FavoritesService._();
  static final FavoritesService _instance = FavoritesService._();
  factory FavoritesService() => _instance;

  // ─── Preference keys ──────────────────────────────────────────────────────

  static const _keyChannels = 'favorites_channels';
  static const _keyMovies = 'favorites_movies';
  static const _keySeries = 'favorites_series';

  // ─── In-memory cache ──────────────────────────────────────────────────────

  List<Map<String, dynamic>>? _channels;
  List<Map<String, dynamic>>? _movies;
  List<Map<String, dynamic>>? _series;

  // ─── Helpers ──────────────────────────────────────────────────────────────

  String _key(FavoriteType type) {
    switch (type) {
      case FavoriteType.channel:
        return _keyChannels;
      case FavoriteType.movie:
        return _keyMovies;
      case FavoriteType.series:
        return _keySeries;
    }
  }

  List<Map<String, dynamic>> _cache(FavoriteType type) {
    switch (type) {
      case FavoriteType.channel:
        return _channels ??= [];
      case FavoriteType.movie:
        return _movies ??= [];
      case FavoriteType.series:
        return _series ??= [];
    }
  }

  void _setCache(FavoriteType type, List<Map<String, dynamic>> value) {
    switch (type) {
      case FavoriteType.channel:
        _channels = value;
        break;
      case FavoriteType.movie:
        _movies = value;
        break;
      case FavoriteType.series:
        _series = value;
        break;
    }
  }

  String _idField(FavoriteType type) =>
      type == FavoriteType.series ? 'series_id' : 'stream_id';

  // ─── Public API ───────────────────────────────────────────────────────────

  /// Load favourites of [type] from SharedPreferences into the cache.
  Future<List<Map<String, dynamic>>> getFavorites(FavoriteType type) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_key(type));
      if (raw == null || raw.isEmpty) {
        _setCache(type, []);
      } else {
        final decoded = jsonDecode(raw) as List<dynamic>;
        _setCache(
            type,
            decoded
                .whereType<Map>()
                .map((e) => Map<String, dynamic>.from(e))
                .toList());
      }
    } catch (e) {
      debugPrint('[FavoritesService] getFavorites error: $e');
      _setCache(type, []);
    }
    return List.unmodifiable(_cache(type));
  }

  /// Returns `true` if [streamId] is in the favourites for [type].
  Future<bool> isFavorite(FavoriteType type, String streamId) async {
    final list = await getFavorites(type);
    final field = _idField(type);
    return list.any((item) => item[field]?.toString() == streamId);
  }

  /// Toggle favourite state for [streamId].
  ///
  /// If not yet favourite, [streamData] is stored (must contain at least
  /// `stream_id`/`series_id`, `name`, and optionally `stream_icon`/`cover`).
  /// If already favourite, the item is removed.
  ///
  /// Returns the new favourite state (`true` = added, `false` = removed).
  Future<bool> toggleFavorite(
    FavoriteType type,
    String streamId,
    Map<String, dynamic> streamData,
  ) async {
    final list = List<Map<String, dynamic>>.from(await getFavorites(type));
    final field = _idField(type);
    final idx = list.indexWhere((item) => item[field]?.toString() == streamId);

    final bool added;
    if (idx >= 0) {
      list.removeAt(idx);
      added = false;
    } else {
      list.add(Map<String, dynamic>.from(streamData));
      added = true;
    }

    _setCache(type, list);
    await _persist(type, list);
    return added;
  }

  /// Persist [list] to SharedPreferences under the key for [type].
  Future<void> _persist(
      FavoriteType type, List<Map<String, dynamic>> list) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_key(type), jsonEncode(list));
    } catch (e) {
      debugPrint('[FavoritesService] _persist error: $e');
    }
  }
}
