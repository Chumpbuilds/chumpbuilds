import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/favorites_service.dart';
import '../services/xtream_service.dart';
import '../widgets/system_ui_wrapper.dart';

/// Favorites screen — Channels, Movies, and Series favourites.
///
/// Ported from `clients/windows/ui/favorites/favorites_view.py`.
class FavoritesScreen extends StatefulWidget {
  const FavoritesScreen({super.key});

  @override
  State<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends State<FavoritesScreen> {
  // ─── Theme ────────────────────────────────────────────────────────────────
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _channelsColor = Color(0xFF8b9cff);
  static const Color _moviesColor = Color(0xFFff9eff);
  static const Color _seriesColor = Color(0xFF64d4ff);

  // ─── State ────────────────────────────────────────────────────────────────
  final _favService = FavoritesService();

  List<Map<String, dynamic>> _channels = [];
  List<Map<String, dynamic>> _movies = [];
  List<Map<String, dynamic>> _series = [];

  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadFavorites();
  }

  @override
  void dispose() {
    super.dispose();
  }

  Future<void> _loadFavorites() async {
    setState(() => _loading = true);
    final results = await Future.wait([
      _favService.getFavorites(FavoriteType.channel),
      _favService.getFavorites(FavoriteType.movie),
      _favService.getFavorites(FavoriteType.series),
    ]);
    setState(() {
      _channels = List<Map<String, dynamic>>.from(results[0]);
      _movies = List<Map<String, dynamic>>.from(results[1]);
      _series = List<Map<String, dynamic>>.from(results[2]);
      _loading = false;
    });
  }

  Future<void> _remove(FavoriteType type, String streamId) async {
    // We call toggleFavorite which removes it when already favourite.
    // We need a dummy streamData — the remove path only uses the ID.
    await _favService.toggleFavorite(
        type, streamId, {_idField(type): streamId});
    await _loadFavorites();
  }

  String _idField(FavoriteType type) =>
      type == FavoriteType.series ? 'series_id' : 'stream_id';

  Future<void> _play(Map<String, dynamic> item, FavoriteType type) async {
    final xtream = XtreamService();
    final id = item['stream_id']?.toString() ?? '';
    final streamType = switch (type) {
      FavoriteType.channel => 'live',
      FavoriteType.movie => 'movie',
      FavoriteType.series => 'series',
    };
    final url = xtream.getStreamUrl(id, streamType, streamData: item);
    if (url.isNotEmpty) {
      final uri = Uri.parse(url);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    }
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return SystemUiWrapper(child: Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text('Favorites',
            style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        toolbarHeight: 48,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 18),
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFF0D7377)))
          : Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(
                  child: _buildFavoritesColumn(
                    icon: '📺',
                    label: 'Channels',
                    color: _channelsColor,
                    items: _channels,
                    type: FavoriteType.channel,
                  ),
                ),
                Container(width: 1, color: _borderColor),
                Expanded(
                  child: _buildFavoritesColumn(
                    icon: '🎬',
                    label: 'Movies',
                    color: _moviesColor,
                    items: _movies,
                    type: FavoriteType.movie,
                  ),
                ),
                Container(width: 1, color: _borderColor),
                Expanded(
                  child: _buildFavoritesColumn(
                    icon: '📼',
                    label: 'Series',
                    color: _seriesColor,
                    items: _series,
                    type: FavoriteType.series,
                  ),
                ),
              ],
            ),
    ));
  }

  Widget _buildFavoritesColumn({
    required String icon,
    required String label,
    required Color color,
    required List<Map<String, dynamic>> items,
    required FavoriteType type,
  }) {
    return Container(
      color: _bgColor,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // ── Header ──────────────────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
            child: Row(
              children: [
                Text(icon, style: const TextStyle(fontSize: 16)),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    label.toUpperCase(),
                    style: TextStyle(
                      color: color,
                      fontSize: 12,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.0,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: color.withAlpha(51),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    '${items.length}',
                    style: TextStyle(
                        color: color,
                        fontSize: 11,
                        fontWeight: FontWeight.bold),
                  ),
                ),
              ],
            ),
          ),
          Divider(height: 1, color: _borderColor),
          // ── List ────────────────────────────────────────────────────────
          Expanded(
            child: items.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(icon,
                            style: const TextStyle(fontSize: 40)),
                        const SizedBox(height: 12),
                        const Text(
                          'No favorites yet',
                          style: TextStyle(
                              color: Color(0xFF95A5A6), fontSize: 13),
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 6, vertical: 6),
                    itemCount: items.length,
                    itemBuilder: (context, i) =>
                        _buildFavoriteItem(items[i], type),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildFavoriteItem(
      Map<String, dynamic> item, FavoriteType type) {
    final name = item['name'] as String? ?? '';
    final iconUrl = (item['stream_icon'] as String?) ??
        (item['cover'] as String?) ??
        '';
    final idField = _idField(type);
    final streamId = item[idField]?.toString() ?? '';

    return Card(
      color: _surfaceColor,
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: _borderColor),
      ),
      child: ListTile(
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        leading: iconUrl.isNotEmpty
            ? ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: CachedNetworkImage(
                  imageUrl: iconUrl,
                  width: 40,
                  height: 40,
                  fit: BoxFit.cover,
                  errorWidget: (_, __, ___) => _fallbackIcon(type),
                ),
              )
            : _fallbackIcon(type),
        title: Text(
          name,
          style: const TextStyle(color: Colors.white, fontSize: 13),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Play button (not for series — no direct stream)
            if (type != FavoriteType.series)
              IconButton(
                icon: const Icon(Icons.play_circle_fill,
                    color: Color(0xFF3498DB), size: 20),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                onPressed: () => _play(item, type),
              ),
            const SizedBox(width: 4),
            // Remove favourite
            IconButton(
              icon: const Icon(Icons.star,
                  color: Color(0xFFFFD700), size: 20),
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(),
              onPressed: () async {
                final confirmed = await _confirmRemove(context, name);
                if (confirmed == true) {
                  await _remove(type, streamId);
                }
              },
            ),
          ],
        ),
        onTap:
            type != FavoriteType.series ? () => _play(item, type) : null,
      ),
    );
  }

  Widget _fallbackIcon(FavoriteType type) {
    final emoji = switch (type) {
      FavoriteType.channel => '📺',
      FavoriteType.movie => '🎬',
      FavoriteType.series => '📼',
    };
    return Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        color: const Color(0xFF3D3D3D),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        emoji,
        style: const TextStyle(fontSize: 22),
        textAlign: TextAlign.center,
      ),
    );
  }

  Future<bool?> _confirmRemove(BuildContext context, String name) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surfaceColor,
        title: const Text('Remove Favourite',
            style: TextStyle(color: Colors.white)),
        content: Text(
          'Remove "$name" from favourites?',
          style: const TextStyle(color: Color(0xFFB0B0B0)),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            style: TextButton.styleFrom(
                foregroundColor: Colors.redAccent),
            child: const Text('Remove'),
          ),
        ],
      ),
    );
  }
}
