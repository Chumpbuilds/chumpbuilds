import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/favorites_service.dart';
import '../services/xtream_service.dart';

/// Favorites screen — Channels, Movies, and Series favourites.
///
/// Ported from `clients/windows/ui/favorites/favorites_view.py`.
class FavoritesScreen extends StatefulWidget {
  const FavoritesScreen({super.key});

  @override
  State<FavoritesScreen> createState() => _FavoritesScreenState();
}

class _FavoritesScreenState extends State<FavoritesScreen>
    with SingleTickerProviderStateMixin {
  // ─── Theme ────────────────────────────────────────────────────────────────
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _primaryColor = Color(0xFF0D7377);

  // ─── State ────────────────────────────────────────────────────────────────
  final _favService = FavoritesService();

  late TabController _tabController;

  List<Map<String, dynamic>> _channels = [];
  List<Map<String, dynamic>> _movies = [];
  List<Map<String, dynamic>> _series = [];

  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadFavorites();
  }

  @override
  void dispose() {
    _tabController.dispose();
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
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text('Favorites', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        toolbarHeight: 36,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 18),
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(),
          onPressed: () => Navigator.of(context).pop(),
        ),
        bottom: TabBar(
          controller: _tabController,
          labelColor: _primaryColor,
          unselectedLabelColor: const Color(0xFF95A5A6),
          indicatorColor: _primaryColor,
          tabs: [
            Tab(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('📺', style: TextStyle(fontSize: 16)),
                  const SizedBox(width: 4),
                  const Text('Channels'),
                ],
              ),
            ),
            Tab(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('🎬', style: TextStyle(fontSize: 16)),
                  const SizedBox(width: 4),
                  const Text('Movies'),
                ],
              ),
            ),
            Tab(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Text('📼', style: TextStyle(fontSize: 16)),
                  const SizedBox(width: 4),
                  const Text('Series'),
                ],
              ),
            ),
          ],
        ),
      ),
      body: _loading
          ? const Center(
              child: CircularProgressIndicator(color: Color(0xFF0D7377)))
          : TabBarView(
              controller: _tabController,
              children: [
                _buildFavoritesList(FavoriteType.channel, _channels),
                _buildFavoritesList(FavoriteType.movie, _movies),
                _buildFavoritesList(FavoriteType.series, _series),
              ],
            ),
    );
  }

  Widget _buildFavoritesList(
      FavoriteType type, List<Map<String, dynamic>> items) {
    if (items.isEmpty) {
      final (emoji, label) = switch (type) {
        FavoriteType.channel => ('📺', 'channels'),
        FavoriteType.movie => ('🎬', 'movies'),
        FavoriteType.series => ('📼', 'series'),
      };
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(emoji, style: const TextStyle(fontSize: 64)),
            const SizedBox(height: 16),
            Text(
              'No favourite $label yet',
              style: const TextStyle(
                  color: Color(0xFF95A5A6), fontSize: 16),
            ),
            const SizedBox(height: 8),
            const Text(
              'Tap the ⭐ icon on any item to add it here',
              style: TextStyle(
                  color: Color(0xFF666666), fontSize: 13),
            ),
          ],
        ),
      );
    }

    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      itemCount: items.length,
      itemBuilder: (context, i) {
        final item = items[i];
        final name = item['name'] as String? ?? '';
        final iconUrl = (item['stream_icon'] as String?) ??
            (item['cover'] as String?) ??
            '';
        final idField = _idField(type);
        final streamId = item[idField]?.toString() ?? '';

        return Card(
          color: _surfaceColor,
          margin: const EdgeInsets.only(bottom: 8),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: const BorderSide(color: _borderColor),
          ),
          child: ListTile(
            leading: iconUrl.isNotEmpty
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: CachedNetworkImage(
                      imageUrl: iconUrl,
                      width: 48,
                      height: 48,
                      fit: BoxFit.cover,
                      errorWidget: (_, __, ___) => _fallbackIcon(type),
                    ),
                  )
                : _fallbackIcon(type),
            title: Text(
              name,
              style: const TextStyle(
                  color: Colors.white, fontSize: 14),
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
                        color: Color(0xFF3498DB)),
                    onPressed: () => _play(item, type),
                  ),
                // Remove favourite
                IconButton(
                  icon: const Icon(Icons.star,
                      color: Color(0xFFFFD700)),
                  onPressed: () async {
                    final confirmed =
                        await _confirmRemove(context, name);
                    if (confirmed == true) {
                      await _remove(type, streamId);
                    }
                  },
                ),
              ],
            ),
            onTap: type != FavoriteType.series
                ? () => _play(item, type)
                : null,
          ),
        );
      },
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
