import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/external_player_service.dart';
import '../services/favorites_service.dart';
import '../services/license_service.dart';
import '../services/xtream_service.dart';
import '../widgets/vlc_player_widget.dart';

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
  bool _searchVisible = false;

  /// Whether the user has selected a category.  On first open this is false,
  /// showing the categories (35%) + portal logo (65%) layout.  After a
  /// category tap it becomes true, switching to movies list (35%) + detail/player (65%).
  bool _categorySelected = false;

  // ─── VLC embedded player state ────────────────────────────────────────────
  String _vlcStreamUrl = '';
  String _vlcTitle = '';
  int _vlcPlayerKey = 0;
  bool _vlcAutoPlay = false;

  final _headerSearchCtrl = TextEditingController();

  final Map<String, int> _movieCounts = {};

  @override
  void initState() {
    super.initState();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _loadCategories();
    _loadFavoriteIds();
    _headerSearchCtrl.addListener(_onHeaderSearchChanged);
  }

  @override
  void dispose() {
    _headerSearchCtrl.dispose();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
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
  }

  Future<void> _selectCategory(Map<String, dynamic> cat) async {
    final catId = cat['category_id']?.toString();
    setState(() {
      _categorySelected = true;
      _selectedCategoryId = catId;
      _selectedCategoryName = cat['category_name']?.toString();
      _selectedMovie = null;
      _vodInfo = null;
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
    _filterMovies();
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

  void _onHeaderSearchChanged() {
    _filterCategories();
    _filterMovies();
  }

  void _filterCategories() {
    final q = _headerSearchCtrl.text.toLowerCase();
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
    final q = _headerSearchCtrl.text.toLowerCase();
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

  void _playMovie(Map<String, dynamic> movie) {
    final streamId = movie['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = _xtream.getStreamUrl(streamId, 'movie', streamData: movie);
    if (url.isEmpty) return;
    final name = movie['name']?.toString() ?? '';
    setState(() {
      _vlcStreamUrl = url;
      _vlcTitle = name;
      _vlcAutoPlay = true;
      _vlcPlayerKey++;
    });
  }

  /// Stops the embedded player and resets it to the idle (placeholder) state.
  ///
  /// Incrementing [_vlcPlayerKey] disposes the active [VlcPlayerWidget], whose
  /// [dispose] stops whichever service (VLC or ExoPlayer) is currently active.
  void _stopEmbeddedPlayback() {
    setState(() {
      _vlcStreamUrl = '';
      _vlcTitle = '';
      _vlcAutoPlay = false;
      _vlcPlayerKey++;
    });
  }

  Future<void> _openMovieExternal(Map<String, dynamic> movie) async {
    final streamId = movie['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = _xtream.getStreamUrl(streamId, 'movie', streamData: movie);
    if (url.isEmpty) return;
    final launched = await ExternalPlayerService.instance.openInVlc(url);
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Unable to open video in external player.')),
      );
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
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        toolbarHeight: 48,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 18),
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: _searchVisible
            ? TextField(
                controller: _headerSearchCtrl,
                autofocus: true,
                style: const TextStyle(color: Colors.white, fontSize: 13),
                decoration: InputDecoration(
                  hintText: '🔍 Search movies & categories...',
                  hintStyle: const TextStyle(color: Color(0xFF95A5A6), fontSize: 13),
                  filled: true,
                  fillColor: const Color(0xFF2D2D2D),
                  isDense: true,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                    borderSide: BorderSide.none,
                  ),
                ),
              )
            : const Text('Movies', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: Icon(_searchVisible ? Icons.close : Icons.search, size: 20),
            onPressed: () {
              setState(() {
                _searchVisible = !_searchVisible;
                if (!_searchVisible) {
                  _headerSearchCtrl.clear();
                }
              });
            },
          ),
        ],
      ),
      body: Row(
        children: [
          // ── Panel 1 (35%): Categories → Movies list after selection ──────
          Expanded(
            flex: 35,
            child: _categorySelected
                ? _buildMoviesPanel()
                : _buildCategoriesPanel(),
          ),
          // ── Panel 2 (65%): Portal logo → Movie detail/player after selection
          Expanded(
            flex: 65,
            child: _categorySelected ? _buildDetailPanel() : _buildLogoPanel(),
          ),
        ],
      ),
    );
  }

  // ─── Panel 1 – Categories ─────────────────────────────────────────────────

  Widget _buildCategoriesPanel() {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF1A1A1A),
        border: Border(right: BorderSide(color: Color(0xFF3A3A3A))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header
          const Padding(
            padding: EdgeInsets.fromLTRB(12, 12, 12, 4),
            child: Text(
              'Categories',
              style: TextStyle(
                color: _accentColor,
                fontSize: 14,
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
          // List
          if (_loadingCategories)
            const Expanded(
                child: Center(
                    child: CircularProgressIndicator(color: _accentColor)))
          else if (_filteredCategories.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No categories',
                        style: TextStyle(
                            color: _secondaryTextColor, fontSize: 12))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredCategories.length,
                itemBuilder: (_, i) {
                  final cat = _filteredCategories[i];
                  final catId = cat['category_id']?.toString() ?? '';
                  final count = _movieCounts[catId] ?? 0;
                  final selected = catId == _selectedCategoryId;
                  return GestureDetector(
                    onTap: () => _selectCategory(cat),
                    child: Container(
                      color: selected
                          ? const Color(0xFF2C3E50)
                          : Colors.transparent,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 6),
                      child: Row(
                        children: [
                          const Text('📁', style: TextStyle(fontSize: 14)),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              cat['category_name']?.toString() ?? '',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 12),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (count > 0)
                            Text(
                              '$count',
                              style: const TextStyle(
                                  color: _secondaryTextColor, fontSize: 11),
                            ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          // Footer count
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text(
              '${_filteredCategories.length} categories',
              style: const TextStyle(
                  color: _secondaryTextColor, fontSize: 11),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }

  // ─── Panel 2 – Portal logo (initial state) ───────────────────────────────

  Widget _buildLogoPanel() {
    final customizations = LicenseService().getAppCustomizations();
    final logoUrl = customizations['logo_url'] as String? ?? '';
    final appName = customizations['app_name'] as String? ?? 'X87 Player';

    return ColoredBox(
      color: _bgColor,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (logoUrl.isNotEmpty)
              CachedNetworkImage(
                imageUrl: logoUrl,
                width: 160,
                height: 160,
                placeholder: (_, __) => const SizedBox(
                  width: 160,
                  height: 160,
                  child: Center(
                    child: CircularProgressIndicator(color: _accentColor),
                  ),
                ),
                errorWidget: (_, __, ___) => const Icon(
                  Icons.movie,
                  size: 80,
                  color: _accentColor,
                ),
                fit: BoxFit.contain,
              )
            else
              const Icon(Icons.movie, size: 80, color: _accentColor),
            const SizedBox(height: 16),
            Text(
              appName,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Select a category to browse movies',
              style: TextStyle(color: _secondaryTextColor, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Panel 1 (after selection) – Movies ──────────────────────────────────

  Widget _buildMoviesPanel() {
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xFF1E1E1E),
        border: Border(right: BorderSide(color: Color(0xFF3A3A3A))),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header with back button and category name
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 8, 8, 4),
            child: Row(
              children: [
                IconButton(
                  icon: const Icon(Icons.arrow_back, size: 16,
                      color: _accentColor),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  tooltip: 'Back to categories',
                  onPressed: () {
                    setState(() {
                      _categorySelected = false;
                      _selectedCategoryId = null;
                      _selectedCategoryName = null;
                      _selectedMovie = null;
                      _vodInfo = null;
                      _vlcStreamUrl = '';
                      _vlcTitle = '';
                      _vlcAutoPlay = false;
                      _vlcPlayerKey++;
                    });
                  },
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    _selectedCategoryName ?? 'Movies',
                    style: const TextStyle(
                      color: _accentColor,
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
          // Loading bar
          if (_loadingMovies)
            const LinearProgressIndicator(
              color: _accentColor,
              backgroundColor: Color(0xFF2D2D2D),
            ),
          // List
          if (!_loadingMovies && _filteredMovies.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No movies found',
                        style: TextStyle(
                            color: _secondaryTextColor, fontSize: 12))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredMovies.length,
                itemBuilder: (_, i) {
                  final movie = _filteredMovies[i];
                  final streamId = movie['stream_id']?.toString() ?? '';
                  final posterUrl = movie['stream_icon']?.toString() ?? '';
                  final selected =
                      _selectedMovie != null &&
                      _selectedMovie!['stream_id']?.toString() == streamId;
                  final isFav = _favMovieIds.contains(streamId);
                  return GestureDetector(
                    onTap: () => _selectMovie(movie),
                    child: Container(
                      color: selected
                          ? const Color(0xFF2C3E50)
                          : Colors.transparent,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 4),
                      child: Row(
                        children: [
                          // Poster thumbnail
                          SizedBox(
                            width: 40,
                            height: 40,
                            child: posterUrl.isNotEmpty
                                ? CachedNetworkImage(
                                    imageUrl: posterUrl,
                                    placeholder: (_, __) => const Text('🎬',
                                        style: TextStyle(fontSize: 20)),
                                    errorWidget: (_, __, ___) => const Text(
                                        '🎬',
                                        style: TextStyle(fontSize: 20)),
                                    fit: BoxFit.contain,
                                  )
                                : const Text('🎬',
                                    style: TextStyle(fontSize: 20)),
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              movie['name']?.toString() ?? '',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 12),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          // Favourite star
                          GestureDetector(
                            onTap: () => _toggleMovieFav(movie),
                            child: Icon(
                              isFav ? Icons.star : Icons.star_border,
                              color: const Color(0xFFFFD700),
                              size: 18,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          // Footer count
          Padding(
            padding: const EdgeInsets.all(8),
            child: Text(
              '${_filteredMovies.length} movies',
              style: const TextStyle(
                  color: _secondaryTextColor, fontSize: 11),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }

  // ─── Panel 2 (after selection) – Movie Detail ────────────────────────────

  Widget _buildDetailPanel() {
    final playerWidget = VlcPlayerWidget(
      key: ValueKey(_vlcPlayerKey),
      streamUrl: _vlcStreamUrl,
      title: _vlcTitle,
      contentType: 'movie',
      autoPlay: _vlcAutoPlay,
    );

    if (_selectedMovie == null) {
      return ColoredBox(
        color: _bgColor,
        child: Column(
          children: [
            // ── Row 1 (60%): 30% artwork placeholder | 70% player (idle) ──
            Expanded(
              flex: 60,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Expanded(
                    flex: 30,
                    child: Container(
                      color: const Color(0xFF2D2D2D),
                      child: const Center(
                        child: Text('🎬', style: TextStyle(fontSize: 32)),
                      ),
                    ),
                  ),
                  Expanded(flex: 70, child: playerWidget),
                ],
              ),
            ),
            // ── Row 2 (40%): prompt ──────────────────────────────────────
            const Expanded(
              flex: 40,
              child: Center(
                child: Text(
                  '🎬  Select a movie to see details',
                  style: TextStyle(color: _secondaryTextColor, fontSize: 14),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ],
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

    return ColoredBox(
      color: _bgColor,
      child: _loadingDetail
          ? const Center(
              child: CircularProgressIndicator(color: _primaryColor))
          : Column(
              children: [
                // ── Row 1 (60%): 30% poster | 70% player ──────────────────
                Expanded(
                  flex: 60,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // 30% – movie poster/artwork
                      Expanded(
                        flex: 30,
                        child: Container(
                          color: const Color(0xFF2D2D2D),
                          child: posterUrl.isNotEmpty
                              ? CachedNetworkImage(
                                  imageUrl: posterUrl,
                                  fit: BoxFit.contain,
                                  placeholder: (_, __) => const Center(
                                      child: Text('🎬',
                                          style: TextStyle(fontSize: 32))),
                                  errorWidget: (_, __, ___) => const Center(
                                      child: Text('🎬',
                                          style: TextStyle(fontSize: 32))),
                                )
                              : const Center(
                                  child: Text('🎬',
                                      style: TextStyle(fontSize: 32))),
                        ),
                      ),
                      // 70% – player
                      Expanded(flex: 70, child: playerWidget),
                    ],
                  ),
                ),

                // ── Row 2 (40%): metadata/details full width ───────────────
                Expanded(
                  flex: 40,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Compact player controls (Play / Stop / VLC)
                      _buildPlayerControls(movie, movieData),

                      // Scrollable movie info
                      Expanded(
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(16),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              // Title
                              Text(
                                name,
                                textAlign: TextAlign.center,
                                style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 16,
                                    fontWeight: FontWeight.bold),
                              ),
                              const SizedBox(height: 4),

                              // Quick-info line
                              Center(
                                child: Text(
                                  [
                                    if (year != null) year,
                                    if (rating != null) '⭐ $rating',
                                    if (genre != null) genre,
                                  ].join('   '),
                                  style: const TextStyle(
                                      color: _secondaryTextColor, fontSize: 11),
                                  textAlign: TextAlign.center,
                                ),
                              ),
                              const SizedBox(height: 8),

                              const Divider(color: Color(0xFF3D3D3D)),
                              const SizedBox(height: 6),

                              // Plot
                              if (plot != null) ...[
                                Text(plot,
                                    style: const TextStyle(
                                        color: Colors.white,
                                        fontSize: 13,
                                        height: 1.5)),
                                const SizedBox(height: 12),
                              ],

                              // Extra info
                              if (director != null)
                                _infoField('Director', director),
                              if (cast != null) _infoField('Cast', cast),
                              const SizedBox(height: 8),

                              // Favourite toggle
                              OutlinedButton.icon(
                                onPressed: () => _toggleMovieFav(movie),
                                icon: Icon(
                                  isFav ? Icons.star : Icons.star_border,
                                  color: const Color(0xFFFFD700),
                                ),
                                label: Text(
                                  isFav
                                      ? 'Remove from Favourites'
                                      : 'Add to Favourites',
                                  style: const TextStyle(color: Colors.white),
                                ),
                                style: OutlinedButton.styleFrom(
                                  side: const BorderSide(
                                      color: Color(0xFF3D3D3D)),
                                  padding: const EdgeInsets.symmetric(
                                      vertical: 12),
                                  shape: RoundedRectangleBorder(
                                      borderRadius: BorderRadius.circular(4)),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  /// Compact control row immediately below the player – mirrors the live TV
  /// screen layout: `[movie name] [Play ▶] [Stop ■] [↗ VLC]`.
  Widget _buildPlayerControls(
    Map<String, dynamic> movie,
    Map<String, dynamic> movieData,
  ) {
    final merged = {...movie, ...movieData};
    final name = movie['name']?.toString() ?? '';
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Text(
              name,
              style: const TextStyle(color: Colors.white, fontSize: 12),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          SizedBox(
            height: 28,
            child: ElevatedButton.icon(
              onPressed: () => _playMovie(merged),
              icon: const Icon(Icons.play_arrow, size: 14),
              label: const Text('Play', style: TextStyle(fontSize: 11)),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF27AE60),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4)),
              ),
            ),
          ),
          const SizedBox(width: 4),
          SizedBox(
            height: 28,
            child: ElevatedButton.icon(
              onPressed: _stopEmbeddedPlayback,
              icon: const Icon(Icons.stop, size: 14),
              label: const Text('Stop', style: TextStyle(fontSize: 11)),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFE74C3C),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4)),
              ),
            ),
          ),
          const SizedBox(width: 4),
          SizedBox(
            height: 28,
            child: OutlinedButton(
              onPressed: () => _openMovieExternal(merged),
              style: OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Color(0xFF3D3D3D)),
                padding: const EdgeInsets.symmetric(horizontal: 6),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4)),
              ),
              child: const Text('↗ VLC', style: TextStyle(fontSize: 11)),
            ),
          ),
        ],
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
