import 'dart:io' show Platform;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../screens/android_hls_fullscreen_screen.dart';
import '../services/external_player_service.dart';
import '../services/favorites_service.dart';
import '../services/xtream_service.dart';
import '../widgets/focus_icon_button.dart';
import '../widgets/system_ui_wrapper.dart';

/// Full-screen movie detail page — poster, description, and play actions.
class MovieDetailScreen extends StatefulWidget {
  const MovieDetailScreen({
    super.key,
    required this.movie,
    required this.xtream,
  });

  final Map<String, dynamic> movie;
  final XtreamService xtream;

  @override
  State<MovieDetailScreen> createState() => _MovieDetailScreenState();
}

class _MovieDetailScreenState extends State<MovieDetailScreen> {
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _accentColor = Color(0xFF3498DB);
  static const Color _secondaryTextColor = Color(0xFF95A5A6);

  Map<String, dynamic>? _vodInfo;
  bool _loadingDetail = true;
  bool _isFav = false;
  final _favService = FavoritesService();

  // Focus state for action buttons
  bool _playButtonFocused = false;
  bool _vlcButtonFocused = false;

  late final FocusNode _playFocusNode;
  late final FocusNode _vlcFocusNode;

  @override
  void initState() {
    super.initState();
    _playFocusNode = FocusNode()
      ..addListener(() {
        setState(() => _playButtonFocused = _playFocusNode.hasFocus);
      });
    _vlcFocusNode = FocusNode()
      ..addListener(() {
        setState(() => _vlcButtonFocused = _vlcFocusNode.hasFocus);
      });
    _loadDetail();
    _checkFavorite();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _playFocusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _playFocusNode.dispose();
    _vlcFocusNode.dispose();
    super.dispose();
  }

  Future<void> _loadDetail() async {
    final vodId = widget.movie['stream_id']?.toString() ?? '';
    if (vodId.isNotEmpty) {
      final info = await widget.xtream.getVodInfo(vodId);
      if (!mounted) return;
      setState(() {
        _vodInfo = info;
        _loadingDetail = false;
      });
    } else {
      if (!mounted) return;
      setState(() => _loadingDetail = false);
    }
  }

  Future<void> _checkFavorite() async {
    final favs = await _favService.getFavorites(FavoriteType.movie);
    final id = widget.movie['stream_id']?.toString() ?? '';
    if (!mounted) return;
    setState(() {
      _isFav = favs.any((f) => f['stream_id']?.toString() == id);
    });
  }

  Future<void> _toggleFavorite() async {
    final id = widget.movie['stream_id']?.toString() ?? '';
    await _favService.toggleFavorite(FavoriteType.movie, id, widget.movie);
    await _checkFavorite();
  }

  void _playMovie() {
    final streamId = widget.movie['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = widget.xtream.getStreamUrl(streamId, 'movie', streamData: widget.movie);
    if (url.isEmpty) return;
    final name = widget.movie['name']?.toString() ?? '';

    // Extract year from vodInfo (if loaded) or fall back to the movie map.
    final info = _vodInfo?['info'] as Map<String, dynamic>? ?? {};
    final rawDate = info['releasedate']?.toString() ??
        info['release_date']?.toString() ??
        widget.movie['year']?.toString() ??
        '';
    final year = rawDate.isNotEmpty ? rawDate.substring(0, rawDate.length >= 4 ? 4 : rawDate.length) : null;
    final tmdbId = info['tmdb_id']?.toString() ??
        info['tmdb']?.toString() ??
        widget.movie['tmdb_id']?.toString();

    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => AndroidHlsFullscreenScreen(
          streamUrl: url,
          title: name,
          contentType: 'movie',
          year: year,
          tmdbId: tmdbId,
        ),
      ),
    );
  }

  Future<void> _openExternal() async {
    final streamId = widget.movie['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = widget.xtream.getStreamUrl(streamId, 'movie', streamData: widget.movie);
    if (url.isEmpty) return;
    final launched = await ExternalPlayerService.instance.openInVlc(url);
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Unable to open video in external player.')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final movie = widget.movie;
    final name = movie['name']?.toString() ?? '';
    final posterUrl = movie['stream_icon']?.toString() ?? '';

    // Extract info from vodInfo if available
    final info = _vodInfo?['info'] as Map<String, dynamic>? ?? {};
    final movieData = _vodInfo?['movie_data'] as Map<String, dynamic>? ?? {};
    final plot = info['plot']?.toString() ?? info['description']?.toString() ?? '';
    final genre = info['genre']?.toString() ?? '';
    final duration = info['duration']?.toString() ?? movieData['duration']?.toString() ?? '';
    final rating = info['rating']?.toString() ?? '';
    final releaseDate = info['releasedate']?.toString() ?? info['release_date']?.toString() ?? '';
    final cast = info['cast']?.toString() ?? '';
    final director = info['director']?.toString() ?? '';

    return SystemUiWrapper(
      child: Scaffold(
        backgroundColor: _bgColor,
        body: Row(
          children: [
            // ── Left side (35%): Poster ──
            Expanded(
              flex: 35,
              child: Container(
                color: Colors.black,
                child: posterUrl.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: posterUrl,
                        fit: BoxFit.contain,
                        placeholder: (_, __) => const Center(
                          child: CircularProgressIndicator(color: _accentColor),
                        ),
                        errorWidget: (_, __, ___) => const Center(
                          child: Icon(Icons.movie, size: 64, color: _secondaryTextColor),
                        ),
                      )
                    : const Center(
                        child: Icon(Icons.movie, size: 64, color: _secondaryTextColor),
                      ),
              ),
            ),
            // ── Right side (65%): Info + actions ──
            Expanded(
              flex: 65,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // ── Header with back button and title ──
                  Container(
                    color: _surfaceColor,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    child: Row(
                      children: [
                        FocusIconButton(
                          icon: Icons.arrow_back,
                          iconSize: 20,
                          onPressed: () => Navigator.of(context).pop(),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Text(
                            name,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.bold,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        // Favorite button
                        FocusIconButton(
                          icon: _isFav ? Icons.star : Icons.star_border,
                          iconSize: 22,
                          iconColor: _isFav ? const Color(0xFFf39c12) : _secondaryTextColor,
                          onPressed: _toggleFavorite,
                        ),
                      ],
                    ),
                  ),
                  // ── Scrollable info area ──
                  Expanded(
                    child: _loadingDetail
                        ? const Center(child: CircularProgressIndicator(color: _accentColor))
                        : SingleChildScrollView(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Meta info row (genre, duration, rating, year)
                                Wrap(
                                  spacing: 12,
                                  runSpacing: 4,
                                  children: [
                                    if (genre.isNotEmpty)
                                      _metaChip(Icons.category, genre),
                                    if (duration.isNotEmpty)
                                      _metaChip(Icons.schedule, duration),
                                    if (rating.isNotEmpty)
                                      _metaChip(Icons.star, rating),
                                    if (releaseDate.isNotEmpty)
                                      _metaChip(Icons.calendar_today, releaseDate),
                                  ],
                                ),
                                if (plot.isNotEmpty) ...[
                                  const SizedBox(height: 12),
                                  Text(
                                    plot,
                                    style: const TextStyle(
                                      color: _secondaryTextColor,
                                      fontSize: 12,
                                      height: 1.5,
                                    ),
                                  ),
                                ],
                                if (director.isNotEmpty) ...[
                                  const SizedBox(height: 10),
                                  Text(
                                    'Director: $director',
                                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                                  ),
                                ],
                                if (cast.isNotEmpty) ...[
                                  const SizedBox(height: 6),
                                  Text(
                                    'Cast: $cast',
                                    style: const TextStyle(color: Colors.white70, fontSize: 11),
                                    maxLines: 3,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ],
                              ],
                            ),
                          ),
                  ),
                  // ── Bottom action buttons ──
                  Container(
                    color: _surfaceColor,
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    child: Row(
                      children: [
                        // ▶ Play button
                        Expanded(
                          child: ElevatedButton.icon(
                            focusNode: _playFocusNode,
                            onPressed: _playMovie,
                            icon: const Icon(Icons.play_arrow, size: 22),
                            label: const Text('Play'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _vlcButtonFocused ? _surfaceColor : _accentColor,
                              foregroundColor: Colors.white,
                              side: _playButtonFocused ? const BorderSide(color: Colors.white, width: 2) : null,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                            ),
                          ),
                        ),
                        if (!Platform.isIOS) ...[
                        const SizedBox(width: 12),
                        // Play in VLC button
                        Expanded(
                          child: ElevatedButton.icon(
                            focusNode: _vlcFocusNode,
                            onPressed: _openExternal,
                            icon: const Icon(Icons.open_in_new, size: 18),
                            label: const Text('Play in VLC'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _vlcButtonFocused ? _accentColor : _surfaceColor,
                              foregroundColor: Colors.white,
                              side: _vlcButtonFocused ? const BorderSide(color: Colors.white, width: 2) : const BorderSide(color: Color(0xFF3D3D3D)),
                              padding: const EdgeInsets.symmetric(vertical: 14),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                            ),
                          ),
                        ),
                        ],
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _metaChip(IconData icon, String text) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 13, color: _accentColor),
        const SizedBox(width: 4),
        Flexible(
          child: Text(
            text,
            style: const TextStyle(color: _secondaryTextColor, fontSize: 11),
            overflow: TextOverflow.ellipsis,
          ),
        ),
      ],
    );
  }
}
