import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/favorites_service.dart';
import '../services/xtream_service.dart';

/// Series screen — categories → series list → seasons/episodes tree + play.
///
/// Ported from `clients/windows/ui/series/series_view.py`.
class SeriesScreen extends StatefulWidget {
  const SeriesScreen({super.key});

  @override
  State<SeriesScreen> createState() => _SeriesScreenState();
}

class _SeriesScreenState extends State<SeriesScreen> {
  // ─── Theme constants ──────────────────────────────────────────────────────
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _accentColor = Color(0xFF3498DB);
  static const Color _secondaryTextColor = Color(0xFF95A5A6);
  static const Color _successColor = Color(0xFF27AE60);

  // ─── State ────────────────────────────────────────────────────────────────
  final _xtream = XtreamService();
  final _favService = FavoritesService();
  final Set<String> _favSeriesIds = {};

  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _allSeries = [];
  List<Map<String, dynamic>> _filteredCategories = [];
  List<Map<String, dynamic>> _filteredSeries = [];

  String? _selectedCategoryId;
  String? _selectedCategoryName;
  Map<String, dynamic>? _selectedSeries;
  Map<String, dynamic>? _seriesInfo;

  bool _loadingCategories = true;
  bool _loadingSeriesList = false;
  bool _loadingDetail = false;

  final _categorySearchCtrl = TextEditingController();
  final _seriesSearchCtrl = TextEditingController();

  final Map<String, int> _seriesCounts = {};
  final Set<int> _expandedSeasons = {};

  @override
  void initState() {
    super.initState();
    _loadCategories();
    _loadFavoriteIds();
    _categorySearchCtrl.addListener(_filterCategories);
    _seriesSearchCtrl.addListener(_filterSeries);
  }

  @override
  void dispose() {
    _categorySearchCtrl.dispose();
    _seriesSearchCtrl.dispose();
    super.dispose();
  }

  // ─── Data loading ─────────────────────────────────────────────────────────

  Future<void> _loadCategories() async {
    setState(() => _loadingCategories = true);
    final rawCats = await _xtream.getSeriesCategories();
    final cats = rawCats
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    final rawAll = await _xtream.getSeries(null);
    final all = rawAll
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();

    final counts = <String, int>{};
    for (final s in all) {
      final cid = s['category_id']?.toString() ?? '';
      counts[cid] = (counts[cid] ?? 0) + 1;
    }

    if (!mounted) return;
    setState(() {
      _categories = cats;
      _filteredCategories = cats;
      _allSeries = all;
      _filteredSeries = all;
      _seriesCounts.addAll(counts);
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
      _selectedSeries = null;
      _seriesInfo = null;
      _expandedSeasons.clear();
      _seriesSearchCtrl.clear();
      _loadingSeriesList = true;
    });

    final raw = await _xtream.getSeries(catId);
    final series = raw
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();

    if (!mounted) return;
    setState(() {
      _filteredSeries = series;
      _loadingSeriesList = false;
    });
  }

  Future<void> _selectSeries(Map<String, dynamic> series) async {
    setState(() {
      _selectedSeries = series;
      _seriesInfo = null;
      _expandedSeasons.clear();
      _loadingDetail = true;
    });

    final seriesId = series['series_id']?.toString() ?? '';
    if (seriesId.isNotEmpty) {
      final info = await _xtream.getSeriesInfo(seriesId);
      if (!mounted) return;
      setState(() {
        _seriesInfo = info;
        _loadingDetail = false;
      });
    } else {
      if (!mounted) return;
      setState(() => _loadingDetail = false);
    }
  }

  // ─── Favourites ───────────────────────────────────────────────────────────

  Future<void> _loadFavoriteIds() async {
    final favs = await _favService.getFavorites(FavoriteType.series);
    setState(() {
      _favSeriesIds
        ..clear()
        ..addAll(favs.map((f) => f['series_id']?.toString() ?? ''));
    });
  }

  Future<void> _toggleSeriesFav(Map<String, dynamic> series) async {
    final id = series['series_id']?.toString() ?? '';
    await _favService.toggleFavorite(FavoriteType.series, id, series);
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

  void _filterSeries() {
    final q = _seriesSearchCtrl.text.toLowerCase();
    if (q.isEmpty) {
      if (_selectedCategoryId != null) {
        setState(() {
          _filteredSeries = _allSeries
              .where((s) =>
                  s['category_id']?.toString() == _selectedCategoryId)
              .toList();
        });
      }
    } else {
      setState(() {
        _filteredSeries = _allSeries
            .where((s) =>
                (s['name'] as String? ?? '').toLowerCase().contains(q))
            .toList();
      });
    }
  }

  // ─── Playback ─────────────────────────────────────────────────────────────

  Future<void> _playEpisode(Map<String, dynamic> episode) async {
    final episodeId = episode['id']?.toString() ?? '';
    if (episodeId.isEmpty) return;
    final ext = episode['container_extension']?.toString() ?? 'mp4';
    final url = _xtream.getStreamUrl(episodeId, 'series', extension: ext);
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

  // ─── Episode data normalisation ───────────────────────────────────────────

  /// Normalise the `episodes` field from getSeriesInfo into a map of
  /// `seasonNumber → List<Map>`.
  ///
  /// Handles three data shapes from the server (mirroring series_view.py):
  ///   1. `{"1": [...], "2": [...]}` — season-keyed dict
  ///   2. `{"ep_id": {...}, ...}` — episode-keyed dict
  ///   3. `[{...}, {...}]` — flat list
  Map<int, List<Map<String, dynamic>>> _parseEpisodes(dynamic raw) {
    final result = <int, List<Map<String, dynamic>>>{};
    if (raw == null) return result;

    if (raw is Map) {
      // Check if values are lists (season-keyed) vs plain maps (episode-keyed)
      final firstVal = raw.values.isNotEmpty ? raw.values.first : null;
      if (firstVal is List) {
        // Shape 1: season-keyed  {"1": [...], "2": [...]}
        for (final entry in raw.entries) {
          final season = int.tryParse(entry.key.toString()) ?? 0;
          final eps = (entry.value as List)
              .map((e) => Map<String, dynamic>.from(e as Map))
              .toList();
          result[season] = eps;
        }
      } else {
        // Shape 2: episode-keyed dict — group by 'season'
        for (final ep in raw.values) {
          final e = Map<String, dynamic>.from(ep as Map);
          final season = int.tryParse(e['season']?.toString() ?? '1') ?? 1;
          result.putIfAbsent(season, () => []).add(e);
        }
      }
    } else if (raw is List) {
      // Shape 3: flat list
      for (final ep in raw) {
        final e = Map<String, dynamic>.from(ep as Map);
        final season = int.tryParse(e['season']?.toString() ?? '1') ?? 1;
        result.putIfAbsent(season, () => []).add(e);
      }
    }

    // Sort episodes within each season by episode_num
    for (final episodes in result.values) {
      episodes.sort((a, b) {
        final aN = int.tryParse(a['episode_num']?.toString() ?? '0') ?? 0;
        final bN = int.tryParse(b['episode_num']?.toString() ?? '0') ?? 0;
        return aN.compareTo(bN);
      });
    }

    return result;
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    if (_selectedSeries != null) {
      return _buildSeriesDetail();
    }
    if (_selectedCategoryId != null) {
      return _buildSeriesList();
    }
    return _buildCategoryList();
  }

  // ─── Category list ────────────────────────────────────────────────────────

  Widget _buildCategoryList() {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text('Series'),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
      ),
      body: Column(
        children: [
          _buildSearchBar(_categorySearchCtrl, 'Search categories…'),
          if (_loadingCategories)
            const Expanded(
                child: Center(
                    child: CircularProgressIndicator(color: _primaryColor)))
          else if (_filteredCategories.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No categories found',
                        style: TextStyle(color: _secondaryTextColor))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredCategories.length,
                itemBuilder: (_, i) {
                  final cat = _filteredCategories[i];
                  final catId = cat['category_id']?.toString() ?? '';
                  final count = _seriesCounts[catId] ?? 0;
                  return ListTile(
                    leading: const Text('📁',
                        style: TextStyle(fontSize: 20)),
                    title: Text(
                      cat['category_name']?.toString() ?? '',
                      style: const TextStyle(color: Colors.white),
                    ),
                    trailing: count > 0
                        ? Text('$count',
                            style: const TextStyle(
                                color: _secondaryTextColor, fontSize: 12))
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

  // ─── Series list ──────────────────────────────────────────────────────────

  Widget _buildSeriesList() {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: Text(_selectedCategoryName ?? 'Series'),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        leading: BackButton(
          onPressed: () => setState(() {
            _selectedCategoryId = null;
            _selectedCategoryName = null;
            _filteredSeries = _allSeries;
            _seriesSearchCtrl.clear();
          }),
        ),
      ),
      body: Column(
        children: [
          _buildSearchBar(_seriesSearchCtrl, 'Search all series…'),
          if (_loadingSeriesList)
            const Expanded(
                child: Center(
                    child: CircularProgressIndicator(color: _primaryColor)))
          else if (_filteredSeries.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No series found',
                        style: TextStyle(color: _secondaryTextColor))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredSeries.length,
                itemBuilder: (_, i) {
                  final s = _filteredSeries[i];
                  final coverUrl = s['cover']?.toString() ?? '';
                  final rating = s['rating']?.toString() ?? '';
                  final year = s['year']?.toString() ?? '';
                  return ListTile(
                    leading: coverUrl.isNotEmpty
                        ? SizedBox(
                            width: 40,
                            height: 56,
                            child: CachedNetworkImage(
                              imageUrl: coverUrl,
                              placeholder: (_, __) => const Text('📼',
                                  style: TextStyle(fontSize: 24)),
                              errorWidget: (_, __, ___) => const Text('📼',
                                  style: TextStyle(fontSize: 24)),
                              fit: BoxFit.cover,
                            ),
                          )
                        : const Text('📼', style: TextStyle(fontSize: 24)),
                    title: Text(
                      s['name']?.toString() ?? '',
                      style: const TextStyle(color: Colors.white),
                    ),
                    subtitle: Text(
                      [if (year.isNotEmpty) year, if (rating.isNotEmpty) '⭐ $rating']
                          .join('  '),
                      style: const TextStyle(
                          color: _secondaryTextColor, fontSize: 12),
                    ),
                    trailing: IconButton(
                      icon: Icon(
                        _favSeriesIds.contains(
                                s['series_id']?.toString() ?? '')
                            ? Icons.star
                            : Icons.star_border,
                        color: const Color(0xFFFFD700),
                        size: 20,
                      ),
                      onPressed: () => _toggleSeriesFav(s),
                    ),
                    onTap: () => _selectSeries(s),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }

  // ─── Series detail ────────────────────────────────────────────────────────

  Widget _buildSeriesDetail() {
    final series = _selectedSeries!;
    final name = series['name']?.toString() ?? '';
    final coverUrl = series['cover']?.toString() ?? '';
    final info =
        _seriesInfo != null && _seriesInfo!['info'] is Map
            ? Map<String, dynamic>.from(_seriesInfo!['info'] as Map)
            : <String, dynamic>{};

    final plot = info['plot']?.toString() ?? '';
    final genre = info['genre']?.toString() ?? '';
    final rating = info['rating']?.toString() ?? series['rating']?.toString() ?? '';
    final year = info['releaseDate']?.toString() ??
        info['release_date']?.toString() ??
        series['year']?.toString() ?? '';

    final episodesBySeasonRaw =
        _seriesInfo != null ? _parseEpisodes(_seriesInfo!['episodes']) : <int, List<Map<String, dynamic>>>{};
    final sortedSeasons = episodesBySeasonRaw.keys.toList()..sort();

    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: Text(name),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        leading: BackButton(
          onPressed: () => setState(() {
            _selectedSeries = null;
            _seriesInfo = null;
            _expandedSeasons.clear();
          }),
        ),
      ),
      body: _loadingDetail
          ? const Center(child: CircularProgressIndicator(color: _primaryColor))
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Cover image
                  if (coverUrl.isNotEmpty)
                    Center(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: CachedNetworkImage(
                          imageUrl: coverUrl,
                          height: 200,
                          placeholder: (_, __) => const SizedBox(height: 200),
                          errorWidget: (_, __, ___) =>
                              const SizedBox(height: 200),
                          fit: BoxFit.contain,
                        ),
                      ),
                    ),
                  const SizedBox(height: 16),

                  // Title
                  Text(
                    name,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        color: Colors.white,
                        fontSize: 20,
                        fontWeight: FontWeight.bold),
                  ),
                  const SizedBox(height: 8),

                  // Meta
                  Center(
                    child: Text(
                      [
                        if (year.isNotEmpty) year,
                        if (rating.isNotEmpty) '⭐ $rating',
                        if (genre.isNotEmpty) genre,
                      ].join('   '),
                      style: const TextStyle(
                          color: _secondaryTextColor, fontSize: 13),
                    ),
                  ),
                  const SizedBox(height: 16),

                  // Plot
                  if (plot.isNotEmpty) ...[
                    Text('Plot',
                        style: TextStyle(
                            color: _accentColor,
                            fontWeight: FontWeight.bold,
                            fontSize: 15)),
                    const SizedBox(height: 6),
                    Text(plot,
                        style: const TextStyle(
                            color: Colors.white, height: 1.5)),
                    const SizedBox(height: 20),
                  ],

                  // Seasons & Episodes
                  if (sortedSeasons.isEmpty && !_loadingDetail)
                    const Text('No episode data available',
                        style: TextStyle(color: _secondaryTextColor))
                  else
                    ...sortedSeasons.map((season) {
                      final episodes = episodesBySeasonRaw[season]!;
                      final isExpanded = _expandedSeasons.contains(season);
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          // Season header
                          InkWell(
                            onTap: () => setState(() {
                              if (isExpanded) {
                                _expandedSeasons.remove(season);
                              } else {
                                _expandedSeasons.add(season);
                              }
                            }),
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                  horizontal: 12, vertical: 10),
                              margin: const EdgeInsets.only(bottom: 4),
                              decoration: BoxDecoration(
                                color: _surfaceColor,
                                borderRadius: BorderRadius.circular(6),
                              ),
                              child: Row(
                                children: [
                                  Text(
                                    isExpanded ? '📂' : '📁',
                                    style: const TextStyle(fontSize: 18),
                                  ),
                                  const SizedBox(width: 10),
                                  Expanded(
                                    child: Text(
                                      'Season $season',
                                      style: TextStyle(
                                          color: _accentColor,
                                          fontWeight: FontWeight.bold,
                                          fontSize: 15),
                                    ),
                                  ),
                                  Text(
                                    '${episodes.length} ep',
                                    style: const TextStyle(
                                        color: _secondaryTextColor,
                                        fontSize: 12),
                                  ),
                                  Icon(
                                    isExpanded
                                        ? Icons.expand_less
                                        : Icons.expand_more,
                                    color: _secondaryTextColor,
                                  ),
                                ],
                              ),
                            ),
                          ),

                          // Episode list
                          if (isExpanded)
                            ...episodes.map((ep) {
                              final epNum =
                                  ep['episode_num']?.toString() ?? '';
                              final title = ep['title']?.toString() ?? '';
                              final label = [
                                if (epNum.isNotEmpty) 'Ep $epNum',
                                if (title.isNotEmpty) title,
                              ].join(': ');
                              return Padding(
                                padding: const EdgeInsets.only(
                                    left: 16, bottom: 4),
                                child: Container(
                                  decoration: BoxDecoration(
                                    color: _bgColor,
                                    borderRadius: BorderRadius.circular(4),
                                    border: Border.all(
                                        color: _surfaceColor, width: 1),
                                  ),
                                  child: ListTile(
                                    leading: const Text('▶',
                                        style: TextStyle(
                                            color: _successColor,
                                            fontSize: 16)),
                                    title: Text(
                                      label.isEmpty ? 'Episode' : label,
                                      style: const TextStyle(
                                          color: Colors.white, fontSize: 14),
                                    ),
                                    onTap: () => _playEpisode(ep),
                                  ),
                                ),
                              );
                            }),
                          const SizedBox(height: 8),
                        ],
                      );
                    }),
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
}
