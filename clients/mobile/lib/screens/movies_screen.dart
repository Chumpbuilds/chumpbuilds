import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../screens/movie_detail_screen.dart';
import '../services/favorites_service.dart';
import '../services/xtream_service.dart';
import '../widgets/focus_list_item.dart';
import '../widgets/system_ui_wrapper.dart';

/// Movies / VOD screen — categories → movie poster grid → movie detail + play.
///
/// Ported from `clients/windows/ui/movies/movies_view.py`.
class MoviesScreen extends StatefulWidget {
  const MoviesScreen({super.key, this.initialMovie});

  final Map<String, dynamic>? initialMovie;

  @override
  State<MoviesScreen> createState() => _MoviesScreenState();
}

class _MoviesScreenState extends State<MoviesScreen> {
  // ─── Theme constants ──────────────────────────────────────────────────────
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
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

  bool _loadingCategories = true;
  bool _loadingMovies = false;
  bool _searchVisible = false;

  /// Whether the user has selected a category.  On first open this is false,
  /// showing the categories (35%) + portal logo (65%) layout.  After a
  /// category tap it becomes true, switching to full-width movie poster grid.
  bool _categorySelected = false;

  final _headerSearchCtrl = TextEditingController();

  final Map<String, int> _movieCounts = {};

  @override
  void initState() {
    super.initState();
    _loadCategories();
    _loadFavoriteIds();
    _headerSearchCtrl.addListener(_onHeaderSearchChanged);
  }

  @override
  void dispose() {
    _headerSearchCtrl.dispose();
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

    if (widget.initialMovie != null) {
      final catId = widget.initialMovie!['category_id']?.toString();
      final matchingCat = _categories.firstWhere(
        (c) => c['category_id']?.toString() == catId,
        orElse: () => <String, dynamic>{},
      );
      if (matchingCat.isNotEmpty) {
        await _selectCategory(matchingCat);
      }
      if (mounted) {
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => MovieDetailScreen(
              movie: widget.initialMovie!,
              xtream: _xtream,
            ),
          ),
        );
        _loadFavoriteIds();
      }
    }
  }

  Future<void> _selectCategory(Map<String, dynamic> cat) async {
    final catId = cat['category_id']?.toString();
    setState(() {
      _categorySelected = true;
      _selectedCategoryId = catId;
      _selectedCategoryName = cat['category_name']?.toString();
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

  // ─── Favourites ───────────────────────────────────────────────────────────

  Future<void> _loadFavoriteIds() async {
    final favs = await _favService.getFavorites(FavoriteType.movie);
    if (!mounted) return;
    setState(() {
      _favMovieIds
        ..clear()
        ..addAll(favs.map((f) => f['stream_id']?.toString() ?? ''));
    });
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

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return SystemUiWrapper(child: Scaffold(
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
      body: _categorySelected
          ? _buildMovieGrid()
          : Row(
              children: [
                Expanded(flex: 40, child: _buildCategoriesPanel()),
                Expanded(flex: 60, child: _buildPlaceholderPanel()),
              ],
            ),
    ));
  }

  // ─── Panel 1 – Categories ─────────────────────────────────────────────────

  Widget _buildPlaceholderPanel() {
    return const ColoredBox(
      color: _bgColor,
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.movie_outlined, size: 64, color: _secondaryTextColor),
            SizedBox(height: 16),
            Text(
              'Please select a category to proceed',
              style: TextStyle(
                color: _secondaryTextColor,
                fontSize: 14,
              ),
            ),
          ],
        ),
      ),
    );
  }

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
                  return FocusListItem(
                    autofocus: i == 0,
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

  // ─── Full-width movie poster grid (after category selection) ──────────────

  Widget _buildMovieGrid() {
    return Column(
      children: [
        // Header bar with back button + category name
        Container(
          color: const Color(0xFF1A1A1A),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          child: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_back, size: 18, color: _accentColor),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                tooltip: 'Back to categories',
                onPressed: () {
                  setState(() {
                    _categorySelected = false;
                    _selectedCategoryId = null;
                    _selectedCategoryName = null;
                  });
                },
              ),
              const SizedBox(width: 8),
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
              Text(
                '${_filteredMovies.length} movies',
                style: const TextStyle(color: _secondaryTextColor, fontSize: 11),
              ),
            ],
          ),
        ),
        // Loading indicator
        if (_loadingMovies)
          const LinearProgressIndicator(color: _accentColor, backgroundColor: Color(0xFF2D2D2D)),
        // Grid
        if (!_loadingMovies && _filteredMovies.isEmpty)
          const Expanded(
            child: Center(
              child: Text('No movies found', style: TextStyle(color: _secondaryTextColor, fontSize: 13)),
            ),
          )
        else
          Expanded(
            child: GridView.builder(
              padding: const EdgeInsets.all(6),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 5,
                crossAxisSpacing: 6,
                mainAxisSpacing: 6,
                childAspectRatio: 0.55,
              ),
              itemCount: _filteredMovies.length,
              itemBuilder: (_, i) => _buildMovieTile(_filteredMovies[i]),
            ),
          ),
      ],
    );
  }

  Widget _buildMovieTile(Map<String, dynamic> movie) {
    final name = movie['name']?.toString() ?? '';
    final posterUrl = movie['stream_icon']?.toString() ?? '';
    final isFav = _favMovieIds.contains(movie['stream_id']?.toString() ?? '');

    return GestureDetector(
      onTap: () async {
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => MovieDetailScreen(movie: movie, xtream: _xtream),
          ),
        );
        // Refresh favorites when returning from detail screen
        _loadFavoriteIds();
      },
      child: Container(
        decoration: BoxDecoration(
          color: _surfaceColor,
          borderRadius: BorderRadius.circular(6),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Poster image
            Expanded(
              child: ClipRRect(
                borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                child: posterUrl.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: posterUrl,
                        fit: BoxFit.cover,
                        placeholder: (_, __) => Container(
                          color: const Color(0xFF3A3A3A),
                          child: const Center(child: Icon(Icons.movie, color: _secondaryTextColor, size: 24)),
                        ),
                        errorWidget: (_, __, ___) => Container(
                          color: const Color(0xFF3A3A3A),
                          child: const Center(child: Icon(Icons.movie, color: _secondaryTextColor, size: 24)),
                        ),
                      )
                    : Container(
                        color: const Color(0xFF3A3A3A),
                        child: const Center(child: Icon(Icons.movie, color: _secondaryTextColor, size: 24)),
                      ),
              ),
            ),
            // Title + optional fav indicator
            Padding(
              padding: const EdgeInsets.all(4),
              child: Row(
                children: [
                  if (isFav)
                    const Padding(
                      padding: EdgeInsets.only(right: 4),
                      child: Icon(Icons.star, color: Color(0xFFf39c12), size: 10),
                    ),
                  Expanded(
                    child: Text(
                      name,
                      style: const TextStyle(color: Colors.white, fontSize: 9),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
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
}
