import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/favorites_service.dart';
import '../services/xtream_service.dart';

/// Movies / VOD screen — categories → movie list → movie detail + play.
///
/// Ported from `clients/windows/ui/movies/movies_view.py`.
class MoviesScreen extends StatefulWidget {
  const MoviesScreen({super.key});

  @override
  State<MoviesScreen> createState() => _MoviesScreenState();
}

class _MoviesScreenState extends State<MoviesScreen> {
  // ─── Theme constants ──────────────────────────────────────────────────────
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _accentColor = Color(0xFF3498DB);
  static const Color _secondaryTextColor = Color(0xFF95A5A6);

  // ─── State ────────────────────────────────────────────────────────────────
  final _xtream = XtreamService();
  final _favService = FavoritesService();
  final Set<String> _favMovieIds = {};

  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _allMovies = [];
  List<Map<String, dynamic>> _filteredCategories = [];
  List<Map<String, dynamic>> _filteredMovies = [];

  String? _selectedCategoryId;
  String? _selectedCategoryName;
  Map<String, dynamic>? _selectedMovie;
  Map<String, dynamic>? _vodInfo;

  bool _loadingCategories = true;
  bool _loadingMovies = false;
  bool _loadingDetail = false;

  bool _categorySearchVisible = false;
  bool _movieSearchVisible = false;

  final _categorySearchCtrl = TextEditingController();
  final _movieSearchCtrl = TextEditingController();

  final Map<String, int> _movieCounts = {};

  @override
  void initState() {
    super.initState();
    _loadCategories();
    _loadFavoriteIds();
    _categorySearchCtrl.addListener(_filterCategories);
    _movieSearchCtrl.addListener(_filterMovies);
  }

  @override
  void dispose() {
    _categorySearchCtrl.dispose();
    _movieSearchCtrl.dispose();
    super.dispose();
  }

  // ─── Data loading ─────────────────────────────────────────────────────────

  Future<void> _loadCategories() async {
    setState(() => _loadingCategories = true);
    final rawCats = await _xtream.getVodCategories();
    final cats = rawCats
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    // Load all movies for search & counts
    final rawAll = await _xtream.getVodStreams(null);
    final all = rawAll
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();

    final counts = <String, int>{};
    for (final m in all) {
      final cid = m['category_id']?.toString() ?? '';
      counts[cid] = (counts[cid] ?? 0) + 1;
    }

    if (!mounted) return;
    setState(() {
      _categories = cats;
      _filteredCategories = cats;
      _allMovies = all;
      _filteredMovies = all;
      _movieCounts.addAll(counts);
      _loadingCategories = false;
    });

    if (cats.isNotEmpty) {
      _selectCategory(cats.first);
    }
  }

  Future<void> _selectCategory(Map<String, dynamic> cat) async {
    final catId = cat['category_id']?.toString();
    setState(() {
      _selectedCategoryId = catId;
      _selectedCategoryName = cat['category_name']?.toString();
      _selectedMovie = null;
      _vodInfo = null;
      _movieSearchCtrl.clear();
      _loadingMovies = true;
    });

    final raw = await _xtream.getVodStreams(catId);
    final movies = raw
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();

    if (!mounted) return;
    setState(() {
      _filteredMovies = movies;
      _loadingMovies = false;
    });
  }

  Future<void> _selectMovie(Map<String, dynamic> movie) async {
    setState(() {
      _selectedMovie = movie;
      _vodInfo = null;
      _loadingDetail = true;
    });

    final vodId = movie['stream_id']?.toString() ?? '';
    if (vodId.isNotEmpty) {
      final info = await _xtream.getVodInfo(vodId);
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

  // ─── Favourites ───────────────────────────────────────────────────────────

  Future<void> _loadFavoriteIds() async {
    final favs = await _favService.getFavorites(FavoriteType.movie);
    setState(() {
      _favMovieIds
        ..clear()
        ..addAll(favs.map((f) => f['stream_id']?.toString() ?? ''));
    });
  }

  Future<void> _toggleMovieFav(Map<String, dynamic> movie) async {
    final id = movie['stream_id']?.toString() ?? '';
    await _favService.toggleFavorite(FavoriteType.movie, id, movie);
    await _loadFavoriteIds();
  }

  // ─── Filtering ────────────────────────────────────────────────────────────

  void _filterCategories() {
    final q = _categorySearchCtrl.text.toLowerCase();
    setState(() {
      _filteredCategories = q.isEmpty
          ? _categories
          : _categories
              .where((c) =>
                  (c['category_name'] as String? ?? '')
                      .toLowerCase()
                      .contains(q))
              .toList();
    });
  }

  void _filterMovies() {
    final q = _movieSearchCtrl.text.toLowerCase();
    if (q.isEmpty) {
      if (_selectedCategoryId != null) {
        setState(() {
          _filteredMovies = _allMovies
              .where((m) =>
                  m['category_id']?.toString() == _selectedCategoryId)
              .toList();
        });
      }
    } else {
      setState(() {
        _filteredMovies = _allMovies
            .where((m) =>
                (m['name'] as String? ?? '').toLowerCase().contains(q))
            .toList();
      });
    }
  }

  // ─── Playback ─────────────────────────────────────────────────────────────

  Future<void> _playMovie(Map<String, dynamic> movie) async {
    final streamId = movie['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = _xtream.getStreamUrl(streamId, 'movie', streamData: movie);
    if (url.isEmpty) return;
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } else {
      if (!mounted) return;
      _showUrlDialog(url);
    }
  }

  void _showUrlDialog(String url) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surfaceColor,
        title: const Text('Stream URL', style: TextStyle(color: Colors.white)),
        content: SelectableText(url,
            style: const TextStyle(color: _secondaryTextColor, fontSize: 12)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child:
                const Text('Close', style: TextStyle(color: _primaryColor)),
          ),
        ],
      ),
    );
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text('Movies'),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
      ),
      body: Row(
        children: [
          Expanded(flex: 7, child: _buildCategoriesPanel()),
          Expanded(flex: 5, child: _buildMoviesPanel()),
          Expanded(flex: 8, child: _buildDetailPanel()),
        ],
      ),
    );
  }

  // ─── Panel 1 – Categories ─────────────────────────────────────────────────

  Widget _buildCategoriesPanel() {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF1A1A1A),
        border: Border(right: BorderSide(color: Color(0xFF3D3D3D))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 4, 0),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'Categories',
                    style: TextStyle(
                      color: _accentColor,
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                    ),
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.search, size: 18, color: Colors.white70),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  onPressed: () {
                    setState(() {
                      _categorySearchVisible = !_categorySearchVisible;
                    });
                  },
                ),
              ],
            ),
          ),
          if (_categorySearchVisible)
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 6),
              child: TextField(
                controller: _categorySearchCtrl,
                autofocus: true,
                style: const TextStyle(color: Colors.white, fontSize: 12),
                decoration: InputDecoration(
                  hintText: 'Search categories…',
                  hintStyle:
                      const TextStyle(color: Colors.white38, fontSize: 12),
                  isDense: true,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  filled: true,
                  fillColor: const Color(0xFF2D2D2D),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
          if (_loadingCategories)
            const Expanded(
                child: Center(
                    child: CircularProgressIndicator(color: _primaryColor)))
          else if (_filteredCategories.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No categories',
                        style: TextStyle(color: _secondaryTextColor))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredCategories.length,
                itemBuilder: (_, i) {
                  final cat = _filteredCategories[i];
                  final catId = cat['category_id']?.toString() ?? '';
                  final count = _movieCounts[catId] ?? 0;
                  final isSelected = catId == _selectedCategoryId;
                  return ListTile(
                    dense: true,
                    selected: isSelected,
                    selectedTileColor: _surfaceColor,
                    leading: const Text('📁', style: TextStyle(fontSize: 16)),
                    title: Text(
                      cat['category_name']?.toString() ?? '',
                      style: TextStyle(
                        color: isSelected ? _accentColor : Colors.white,
                        fontSize: 13,
                      ),
                    ),
                    trailing: count > 0
                        ? Text('$count',
                            style: const TextStyle(
                                color: _secondaryTextColor, fontSize: 11))
                        : null,
                    onTap: () => _selectCategory(cat),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }

  // ─── Panel 2 – Movies ─────────────────────────────────────────────────────

  Widget _buildMoviesPanel() {
    return Container(
      color: _bgColor,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(8, 8, 4, 0),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    _selectedCategoryName ?? 'Movies',
                    style: TextStyle(
                      color: _accentColor,
                      fontSize: 13,
                      fontWeight: FontWeight.bold,
                    ),
                    overflow: TextOverflow.ellipsis,
                    maxLines: 1,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.search, size: 18, color: Colors.white70),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  onPressed: () {
                    setState(() {
                      _movieSearchVisible = !_movieSearchVisible;
                    });
                  },
                ),
              ],
            ),
          ),
          if (_movieSearchVisible)
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 6),
              child: TextField(
                controller: _movieSearchCtrl,
                autofocus: true,
                style: const TextStyle(color: Colors.white, fontSize: 12),
                decoration: InputDecoration(
                  hintText: 'Search movies…',
                  hintStyle:
                      const TextStyle(color: Colors.white38, fontSize: 12),
                  isDense: true,
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                  filled: true,
                  fillColor: const Color(0xFF2D2D2D),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),
          if (_loadingMovies)
            const Expanded(
                child: Center(
                    child: CircularProgressIndicator(color: _primaryColor)))
          else if (_filteredMovies.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No movies found',
                        style: TextStyle(color: _secondaryTextColor))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredMovies.length,
                itemBuilder: (_, i) {
                  final movie = _filteredMovies[i];
                  final streamId = movie['stream_id']?.toString() ?? '';
                  final posterUrl = movie['stream_icon']?.toString() ?? '';
                  final isSelected =
                      _selectedMovie != null &&
                      _selectedMovie!['stream_id']?.toString() == streamId;
                  final isFav = _favMovieIds.contains(streamId);
                  return ListTile(
                    dense: true,
                    selected: isSelected,
                    selectedTileColor: _surfaceColor,
                    leading: posterUrl.isNotEmpty
                        ? SizedBox(
                            width: 32,
                            height: 48,
                            child: CachedNetworkImage(
                              imageUrl: posterUrl,
                              placeholder: (_, __) => const Text('🎬',
                                  style: TextStyle(fontSize: 18)),
                              errorWidget: (_, __, ___) => const Text('🎬',
                                  style: TextStyle(fontSize: 18)),
                              fit: BoxFit.cover,
                            ),
                          )
                        : const Text('🎬', style: TextStyle(fontSize: 18)),
                    title: Text(
                      movie['name']?.toString() ?? '',
                      style: TextStyle(
                        color: isSelected ? _accentColor : Colors.white,
                        fontSize: 13,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: GestureDetector(
                      onTap: () => _toggleMovieFav(movie),
                      child: Icon(
                        isFav ? Icons.star : Icons.star_border,
                        color: const Color(0xFFFFD700),
                        size: 18,
                      ),
                    ),
                    onTap: () => _selectMovie(movie),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }

  // ─── Panel 3 – Movie Detail ───────────────────────────────────────────────

  Widget _buildDetailPanel() {
    if (_selectedMovie == null) {
      return Container(
        color: _bgColor,
        child: const Center(
          child: Text(
            'Select a movie to see details',
            style: TextStyle(color: _secondaryTextColor),
          ),
        ),
      );
    }

    final movie = _selectedMovie!;
    final name = movie['name']?.toString() ?? '';
    final posterUrl = movie['stream_icon']?.toString() ?? '';
    final info =
        _vodInfo != null && _vodInfo!['info'] is Map
            ? Map<String, dynamic>.from(_vodInfo!['info'] as Map)
            : <String, dynamic>{};
    final movieData =
        _vodInfo != null && _vodInfo!['movie_data'] is Map
            ? Map<String, dynamic>.from(_vodInfo!['movie_data'] as Map)
            : <String, dynamic>{};

    final plot = _notNa(info['plot']?.toString() ??
        info['description']?.toString() ?? '');
    final director = _notNa(info['director']?.toString() ?? '');
    final cast = _notNa(info['cast']?.toString() ?? info['actors']?.toString() ?? '');
    final genre = _notNa(info['genre']?.toString() ?? '');
    final year = _notNa(
        info['releasedate']?.toString() ??
            info['release_date']?.toString() ??
            movie['year']?.toString() ?? '');
    final rating = _notNa(info['rating']?.toString() ??
        movie['rating']?.toString() ?? '');
    final movieId = movie['stream_id']?.toString() ?? '';
    final isFav = _favMovieIds.contains(movieId);

    return Container(
      color: _bgColor,
      child: _loadingDetail
          ? const Center(
              child: CircularProgressIndicator(color: _primaryColor))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Poster
                  if (posterUrl.isNotEmpty)
                    Center(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: CachedNetworkImage(
                          imageUrl: posterUrl,
                          width: 140,
                          height: 210,
                          placeholder: (_, __) =>
                              const SizedBox(width: 140, height: 210),
                          errorWidget: (_, __, ___) =>
                              const SizedBox(width: 140, height: 210),
                          fit: BoxFit.cover,
                        ),
                      ),
                    ),
                  const SizedBox(height: 12),

                  // Title
                  Text(
                    name,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 6),

                  // Quick-info line
                  Center(
                    child: Text(
                      [
                        if (year != null) year,
                        if (rating != null) '⭐ $rating',
                        if (genre != null) genre,
                      ].join('   '),
                      style: const TextStyle(
                          color: _secondaryTextColor, fontSize: 12),
                      textAlign: TextAlign.center,
                    ),
                  ),
                  const SizedBox(height: 10),

                  const Divider(color: Color(0xFF3D3D3D)),
                  const SizedBox(height: 6),

                  // Plot
                  if (plot != null) ...[
                    Text(plot,
                        style: const TextStyle(
                            color: Colors.white, fontSize: 13, height: 1.5)),
                    const SizedBox(height: 14),
                  ],

                  // Extra info
                  if (director != null) _infoField('Director', director),
                  if (cast != null) _infoField('Cast', cast),
                  const SizedBox(height: 8),

                  // Play button
                  ElevatedButton.icon(
                    onPressed: () {
                      final merged = {...movie, ...movieData};
                      _playMovie(merged);
                    },
                    icon: const Icon(Icons.play_arrow),
                    label: const Text('Play Movie'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF27AE60),
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(4)),
                    ),
                  ),
                  const SizedBox(height: 10),

                  // Favourite toggle
                  OutlinedButton.icon(
                    onPressed: () => _toggleMovieFav(movie),
                    icon: Icon(
                      isFav ? Icons.star : Icons.star_border,
                      color: const Color(0xFFFFD700),
                    ),
                    label: Text(
                      isFav ? 'Remove from Favourites' : 'Add to Favourites',
                      style: const TextStyle(color: Colors.white),
                    ),
                    style: OutlinedButton.styleFrom(
                      side: const BorderSide(color: Color(0xFF3D3D3D)),
                      padding: const EdgeInsets.symmetric(vertical: 12),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(4)),
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  Widget _buildSearchBar(TextEditingController ctrl, String hint) {
    return Padding(
      padding: const EdgeInsets.all(8),
      child: TextField(
        controller: ctrl,
        style: const TextStyle(color: Colors.white),
        decoration: InputDecoration(
          hintText: hint,
          hintStyle: const TextStyle(color: _secondaryTextColor),
          prefixIcon: const Icon(Icons.search, color: _secondaryTextColor),
          filled: true,
          fillColor: _surfaceColor,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: BorderSide.none,
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(8),
            borderSide: const BorderSide(color: _primaryColor),
          ),
        ),
      ),
    );
  }

  Widget _infoField(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(label,
                style: const TextStyle(
                    color: _secondaryTextColor, fontSize: 13)),
          ),
          Expanded(
            child: Text(value,
                style: const TextStyle(color: Colors.white, fontSize: 13)),
          ),
        ],
      ),
    );
  }

  /// Returns null if value is null, empty, or 'N/A' (case-insensitive).
  String? _notNa(String? value) {
    if (value == null || value.isEmpty) return null;
    if (value.trim().toUpperCase() == 'N/A') return null;
    return value;
  }
}
