import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../screens/android_hls_fullscreen_screen.dart';
import '../services/external_player_service.dart';
import '../services/favorites_service.dart';
import '../services/license_service.dart';
import '../services/xtream_service.dart';
import '../widgets/focus_list_item.dart';
import '../widgets/vlc_player_widget.dart';

/// Series screen — categories → series list → seasons/episodes tree + play.
///
/// Ported from `clients/windows/ui/series/series_view.py`.
class SeriesScreen extends StatefulWidget {
  const SeriesScreen({super.key, this.initialSeries});

  final Map<String, dynamic>? initialSeries;

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
  bool _searchVisible = false;

  /// Whether the user has selected a category. On first open this is false,
  /// showing the categories (35%) + portal logo (65%) layout. After a
  /// category tap it becomes true, switching to series list (35%) + detail/player (65%).
  bool _categorySelected = false;

  // ─── VLC embedded player state ────────────────────────────────────────────
  String _vlcStreamUrl = '';
  String _vlcTitle = '';
  int _vlcPlayerKey = 0;
  bool _vlcAutoPlay = false;

  final _headerSearchCtrl = TextEditingController();

  final Map<String, int> _seriesCounts = {};

  // ─── Season / episode quick-select state ─────────────────────────────────
  int? _selectedSeason;
  int? _selectedEpisodeIndex;

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

    if (widget.initialSeries != null) {
      final catId = widget.initialSeries!['category_id']?.toString();
      final matchingCat = _categories.firstWhere(
        (c) => c['category_id']?.toString() == catId,
        orElse: () => <String, dynamic>{},
      );
      if (matchingCat.isNotEmpty) {
        await _selectCategory(matchingCat);
      }
      if (mounted) {
        _selectSeries(widget.initialSeries!);
      }
    }
  }

  Future<void> _selectCategory(Map<String, dynamic> cat) async {
    final catId = cat['category_id']?.toString();
    setState(() {
      _categorySelected = true;
      _selectedCategoryId = catId;
      _selectedCategoryName = cat['category_name']?.toString();
      _selectedSeries = null;
      _seriesInfo = null;
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
    _filterSeries();
  }

  Future<void> _selectSeries(Map<String, dynamic> series) async {
    setState(() {
      _selectedSeries = series;
      _seriesInfo = null;
      _loadingDetail = true;
    });

    final seriesId = series['series_id']?.toString() ?? '';
    if (seriesId.isNotEmpty) {
      final info = await _xtream.getSeriesInfo(seriesId);
      if (!mounted) return;
      final episodesBySeason = _parseEpisodes(info?['episodes']);
      final sortedSeasons = episodesBySeason.keys.toList()..sort();
      setState(() {
        _seriesInfo = info;
        _loadingDetail = false;
        if (sortedSeasons.isNotEmpty) {
          _selectedSeason = sortedSeasons.first;
          _selectedEpisodeIndex = 0;
        } else {
          _selectedSeason = null;
          _selectedEpisodeIndex = null;
        }
      });
    } else {
      if (!mounted) return;
      setState(() {
        _loadingDetail = false;
        _selectedSeason = null;
        _selectedEpisodeIndex = null;
      });
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

  void _onHeaderSearchChanged() {
    _filterCategories();
    _filterSeries();
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

  void _filterSeries() {
    final q = _headerSearchCtrl.text.toLowerCase();
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

  void _playEpisode(Map<String, dynamic> episode) {
    final episodeId = episode['id']?.toString() ?? '';
    if (episodeId.isEmpty) return;
    final ext = episode['container_extension']?.toString() ?? 'mp4';
    final url = _xtream.getStreamUrl(episodeId, 'series', extension: ext);
    if (url.isEmpty) return;
    final epNum = episode['episode_num']?.toString() ?? '';
    final title = episode['title']?.toString() ?? '';
    final label = [
      if (epNum.isNotEmpty) 'Ep $epNum',
      if (title.isNotEmpty) title,
    ].join(': ');
    setState(() {
      _vlcStreamUrl = url;
      _vlcTitle = label.isNotEmpty
          ? label
          : (_selectedSeries?['name']?.toString() ?? 'Episode');
      _vlcAutoPlay = true;
      _vlcPlayerKey++;
    });
  }

  /// Plays the episode currently selected via [_selectedSeason] and
  /// [_selectedEpisodeIndex]. Used by the Play button and the episode dropdown.
  void _playSelectedEpisode() {
    if (_seriesInfo == null ||
        _selectedSeason == null ||
        _selectedEpisodeIndex == null) return;
    final episodesBySeason = _parseEpisodes(_seriesInfo!['episodes']);
    final episodes = episodesBySeason[_selectedSeason];
    if (episodes == null || _selectedEpisodeIndex! >= episodes.length) return;
    _playEpisode(episodes[_selectedEpisodeIndex!]);
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

  Future<void> _goFullscreen() async {
    if (_vlcStreamUrl.isEmpty) return;
    final url = _vlcStreamUrl;
    final title = _vlcTitle;
    _stopEmbeddedPlayback();
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => AndroidHlsFullscreenScreen(
          streamUrl: url,
          title: title,
          contentType: 'series',
        ),
      ),
    );
  }

  /// Replays the current stream by reinitializing the player with autoplay enabled.
  void _replayCurrentStream() {
    if (_vlcStreamUrl.isEmpty) return;
    setState(() {
      _vlcAutoPlay = true;
      _vlcPlayerKey++;
    });
  }

  /// Opens the currently loaded stream URL in an external player (VLC).
  Future<void> _openCurrentStreamExternal() async {
    if (_vlcStreamUrl.isEmpty) return;
    final launched =
        await ExternalPlayerService.instance.openInVlc(_vlcStreamUrl);
    if (!launched && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Unable to open video in external player.')),
      );
    }
  }

  Future<void> _openEpisodeExternal(Map<String, dynamic> episode) async {
    final episodeId = episode['id']?.toString() ?? '';
    if (episodeId.isEmpty) return;
    final ext = episode['container_extension']?.toString() ?? 'mp4';
    final url = _xtream.getStreamUrl(episodeId, 'series', extension: ext);
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
                  hintText: '🔍 Search series & categories...',
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
            : const Text('Series', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
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
          Expanded(
            flex: 35,
            child: _categorySelected
                ? _buildSeriesPanel()
                : _buildCategoriesPanel(),
          ),
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
                  final count = _seriesCounts[catId] ?? 0;
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
              style: const TextStyle(color: _secondaryTextColor, fontSize: 11),
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
                  Icons.video_library,
                  size: 80,
                  color: _accentColor,
                ),
                fit: BoxFit.contain,
              )
            else
              const Icon(Icons.video_library, size: 80, color: _accentColor),
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
              'Select a category to browse series',
              style: TextStyle(color: _secondaryTextColor, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Panel 2 – Series list ────────────────────────────────────────────────

  Widget _buildSeriesPanel() {
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
                  icon: const Icon(Icons.arrow_back,
                      size: 16, color: _accentColor),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(),
                  tooltip: 'Back to categories',
                  onPressed: () {
                    setState(() {
                      _categorySelected = false;
                      _selectedCategoryId = null;
                      _selectedCategoryName = null;
                      _selectedSeries = null;
                      _seriesInfo = null;
                      _selectedSeason = null;
                      _selectedEpisodeIndex = null;
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
                    _selectedCategoryName ?? 'Series',
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
          if (_loadingSeriesList)
            const LinearProgressIndicator(
              color: _accentColor,
              backgroundColor: Color(0xFF2D2D2D),
            ),
          // List
          if (!_loadingSeriesList && _filteredSeries.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No series found',
                        style: TextStyle(
                            color: _secondaryTextColor, fontSize: 12))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredSeries.length,
                itemBuilder: (_, i) {
                  final s = _filteredSeries[i];
                  final seriesId = s['series_id']?.toString() ?? '';
                  final coverUrl = s['cover']?.toString() ?? '';
                  final isSelected = _selectedSeries != null &&
                      _selectedSeries!['series_id']?.toString() == seriesId;
                  final isFav = _favSeriesIds.contains(seriesId);
                  return FocusListItem(
                    autofocus: i == 0,
                    onTap: () => _selectSeries(s),
                    child: Container(
                      color: isSelected
                          ? const Color(0xFF2C3E50)
                          : Colors.transparent,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 4),
                      child: Row(
                        children: [
                          // Cover thumbnail
                          SizedBox(
                            width: 40,
                            height: 40,
                            child: coverUrl.isNotEmpty
                                ? CachedNetworkImage(
                                    imageUrl: coverUrl,
                                    placeholder: (_, __) => const Text('📼',
                                        style: TextStyle(fontSize: 20)),
                                    errorWidget: (_, __, ___) => const Text(
                                        '📼',
                                        style: TextStyle(fontSize: 20)),
                                    fit: BoxFit.contain,
                                  )
                                : const Text('📼',
                                    style: TextStyle(fontSize: 20)),
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              s['name']?.toString() ?? '',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 12),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          // Favourite star
                          GestureDetector(
                            onTap: () => _toggleSeriesFav(s),
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
              '${_filteredSeries.length} series',
              style:
                  const TextStyle(color: _secondaryTextColor, fontSize: 11),
              textAlign: TextAlign.center,
            ),
          ),
        ],
      ),
    );
  }

  // ─── Panel 2 – Series Detail / Episodes ──────────────────────────────────

  Widget _buildDetailPanel() {
    final playerWidget = VlcPlayerWidget(
      key: ValueKey(_vlcPlayerKey),
      streamUrl: _vlcStreamUrl,
      title: _vlcTitle,
      contentType: 'series',
      autoPlay: _vlcAutoPlay,
    );

    if (_selectedSeries == null) {
      return ColoredBox(
        color: _bgColor,
        child: Column(
          children: [
            // ── Row 1 (60%): 35% artwork placeholder | 65% player (idle) ──
            Expanded(
              flex: 60,
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Expanded(
                    flex: 35,
                    child: Container(
                      color: _surfaceColor,
                      child: const Center(
                        child: Text('📼', style: TextStyle(fontSize: 32)),
                      ),
                    ),
                  ),
                  Expanded(flex: 65, child: playerWidget),
                ],
              ),
            ),
            // ── Row 2 (40%): prompt ──────────────────────────────────────
            const Expanded(
              flex: 40,
              child: Center(
                child: Text(
                  '📼  Select a series to see details',
                  style: TextStyle(color: _secondaryTextColor, fontSize: 14),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ],
        ),
      );
    }

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

    final seriesId = series['series_id']?.toString() ?? '';
    final isFav = _favSeriesIds.contains(seriesId);

    return ColoredBox(
      color: _bgColor,
      child: _loadingDetail
          ? const Center(
              child: CircularProgressIndicator(color: _primaryColor))
          : Column(
              children: [
                // ── Row 1 (60%): 35% cover artwork | 65% player ───────────
                Expanded(
                  flex: 60,
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // 35% – series cover artwork
                      Expanded(
                        flex: 35,
                        child: Container(
                          color: _surfaceColor,
                          child: coverUrl.isNotEmpty
                              ? CachedNetworkImage(
                                  imageUrl: coverUrl,
                                  fit: BoxFit.contain,
                                  placeholder: (_, __) => const Center(
                                      child: Text('📼',
                                          style: TextStyle(fontSize: 32))),
                                  errorWidget: (_, __, ___) => const Center(
                                      child: Text('📼',
                                          style: TextStyle(fontSize: 32))),
                                )
                              : const Center(
                                  child: Text('📼',
                                      style: TextStyle(fontSize: 32))),
                        ),
                      ),
                      // 65% – player
                      Expanded(flex: 65, child: playerWidget),
                    ],
                  ),
                ),

                // ── Row 2 (40%): controls + scrollable metadata ────────────
                Expanded(
                  flex: 40,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      // Compact player controls (Play / Stop / VLC)
                      _buildPlayerControls(episodesBySeasonRaw),

                      // Scrollable series/episode info
                      Expanded(
                        child: SingleChildScrollView(
                          padding: const EdgeInsets.all(16),
                          child: _buildMetadataSection(
                            series: series,
                            name: name,
                            year: year,
                            rating: rating,
                            genre: genre,
                            plot: plot,
                            isFav: isFav,
                            episodesBySeason: episodesBySeasonRaw,
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
  /// screen layout: `[episode title] [Play ▶] [Stop ■] [↗ VLC]`.
  Widget _buildPlayerControls(
      Map<int, List<Map<String, dynamic>>> episodesBySeason) {
    final sortedSeasons = episodesBySeason.keys.toList()..sort();

    // Season label shown on the button
    final seasonLabel =
        _selectedSeason != null ? 'S$_selectedSeason' : 'Season';

    // Current season's episodes
    final currentEpisodes = _selectedSeason != null
        ? (episodesBySeason[_selectedSeason] ?? <Map<String, dynamic>>[])
        : <Map<String, dynamic>>[];

    // Episode label shown on the button
    String episodeLabel = 'Episode';
    if (_selectedEpisodeIndex != null &&
        _selectedEpisodeIndex! < currentEpisodes.length) {
      final ep = currentEpisodes[_selectedEpisodeIndex!];
      final num = ep['episode_num']?.toString() ?? '';
      episodeLabel = num.isNotEmpty ? 'Ep $num' : 'Ep ${_selectedEpisodeIndex! + 1}';
    }

    final outlinedStyle = tvFocusOutlinedButtonStyle(
      OutlinedButton.styleFrom(
        foregroundColor: Colors.white,
        side: const BorderSide(color: Color(0xFF3D3D3D)),
        padding: const EdgeInsets.symmetric(horizontal: 6),
        shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(4))),
      ),
    );

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: Text(
              _vlcTitle,
              style: const TextStyle(color: Colors.white, fontSize: 12),
              overflow: TextOverflow.ellipsis,
            ),
          ),

          // ── Season dropdown ──────────────────────────────────────────────
          if (sortedSeasons.isNotEmpty) ...[
            SizedBox(
              height: 28,
              child: OutlinedButton(
                style: outlinedStyle,
                onPressed: sortedSeasons.isEmpty
                    ? null
                    : () async {
                        final RenderBox button =
                            context.findRenderObject()! as RenderBox;
                        final RenderBox overlay = Overlay.of(context)
                            .context
                            .findRenderObject()! as RenderBox;
                        final RelativeRect position = RelativeRect.fromRect(
                          Rect.fromPoints(
                            button.localToGlobal(
                                button.size.bottomRight(Offset.zero),
                                ancestor: overlay),
                            button.localToGlobal(
                                button.size.bottomRight(Offset.zero),
                                ancestor: overlay),
                          ),
                          Offset.zero & overlay.size,
                        );
                        final selected = await showMenu<int>(
                          context: context,
                          position: position,
                          color: const Color(0xFF2D2D2D),
                          constraints: const BoxConstraints(maxHeight: 300),
                          items: sortedSeasons
                              .map(
                                (s) => PopupMenuItem<int>(
                                  value: s,
                                  child: Text(
                                    'Season $s',
                                    style: TextStyle(
                                      color: s == _selectedSeason
                                          ? _accentColor
                                          : Colors.white,
                                      fontSize: 13,
                                    ),
                                  ),
                                ),
                              )
                              .toList(),
                        );
                        if (selected != null && mounted) {
                          setState(() {
                            _selectedSeason = selected;
                            _selectedEpisodeIndex = 0;
                          });
                        }
                      },
                child: Text(
                  '$seasonLabel ▼',
                  style: const TextStyle(fontSize: 11),
                ),
              ),
            ),
            const SizedBox(width: 4),
          ],

          // ── Episode dropdown ─────────────────────────────────────────────
          if (currentEpisodes.isNotEmpty) ...[
            SizedBox(
              height: 28,
              child: OutlinedButton(
                style: outlinedStyle,
                onPressed: () async {
                  final RenderBox button =
                      context.findRenderObject()! as RenderBox;
                  final RenderBox overlay = Overlay.of(context)
                      .context
                      .findRenderObject()! as RenderBox;
                  final RelativeRect position = RelativeRect.fromRect(
                    Rect.fromPoints(
                      button.localToGlobal(
                          button.size.bottomRight(Offset.zero),
                          ancestor: overlay),
                      button.localToGlobal(
                          button.size.bottomRight(Offset.zero),
                          ancestor: overlay),
                    ),
                    Offset.zero & overlay.size,
                  );
                  final selected = await showMenu<int>(
                    context: context,
                    position: position,
                    color: const Color(0xFF2D2D2D),
                    constraints: const BoxConstraints(maxHeight: 300),
                    items: List.generate(
                      currentEpisodes.length,
                      (i) {
                        final ep = currentEpisodes[i];
                        final num = ep['episode_num']?.toString() ?? '';
                        final title = ep['title']?.toString() ?? '';
                        final label = [
                          if (num.isNotEmpty) 'Ep $num',
                          if (title.isNotEmpty) title,
                        ].join(': ');
                        return PopupMenuItem<int>(
                          value: i,
                          child: Text(
                            label.isNotEmpty ? label : 'Episode ${i + 1}',
                            style: TextStyle(
                              color: i == _selectedEpisodeIndex
                                  ? _accentColor
                                  : Colors.white,
                              fontSize: 13,
                            ),
                          ),
                        );
                      },
                    ),
                  );
                  if (selected != null && mounted) {
                    setState(() => _selectedEpisodeIndex = selected);
                    if (selected < currentEpisodes.length) {
                      _playEpisode(currentEpisodes[selected]);
                    }
                  }
                },
                child: Text(
                  '$episodeLabel ▼',
                  style: const TextStyle(fontSize: 11),
                ),
              ),
            ),
            const SizedBox(width: 4),
          ],

          // ── Play button ──────────────────────────────────────────────────
          SizedBox(
            height: 28,
            child: ElevatedButton.icon(
              onPressed: _playSelectedEpisode,
              icon: const Icon(Icons.play_arrow, size: 14),
              label: const Text('Play', style: TextStyle(fontSize: 11)),
              style: tvFocusButtonStyle(ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF27AE60),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4)),
              )),
            ),
          ),
          const SizedBox(width: 4),
          SizedBox(
            height: 28,
            child: ElevatedButton.icon(
              onPressed: _stopEmbeddedPlayback,
              icon: const Icon(Icons.stop, size: 14),
              label: const Text('Stop', style: TextStyle(fontSize: 11)),
              style: tvFocusButtonStyle(ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFE74C3C),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4)),
              )),
            ),
          ),
          const SizedBox(width: 4),
          SizedBox(
            height: 28,
            child: OutlinedButton(
              onPressed: _openCurrentStreamExternal,
              style: tvFocusOutlinedButtonStyle(OutlinedButton.styleFrom(
                foregroundColor: Colors.white,
                side: const BorderSide(color: Color(0xFF3D3D3D)),
                padding: const EdgeInsets.symmetric(horizontal: 6),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4)),
              )),
              child: const Text('↗ VLC', style: TextStyle(fontSize: 11)),
            ),
          ),
          const SizedBox(width: 4),
          SizedBox(
            height: 28,
            child: ElevatedButton.icon(
              onPressed: _vlcStreamUrl.isNotEmpty ? _goFullscreen : null,
              icon: const Icon(Icons.fullscreen, size: 14),
              label: const Text('Fullscreen', style: TextStyle(fontSize: 11)),
              style: tvFocusButtonStyle(ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF8E44AD),
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4)),
              )),
            ),
          ),
        ],
      ),
    );
  }

  /// Builds the scrollable metadata content below the player controls.
  ///
  /// When an episode is selected (via [_selectedSeason] and
  /// [_selectedEpisodeIndex]), shows episode-specific info (title, plot,
  /// duration, rating). Falls back to series-level metadata otherwise.
  Widget _buildMetadataSection({
    required Map<String, dynamic> series,
    required String name,
    required String year,
    required String rating,
    required String genre,
    required String plot,
    required bool isFav,
    required Map<int, List<Map<String, dynamic>>> episodesBySeason,
  }) {
    // Try to get the currently selected episode
    Map<String, dynamic>? selectedEpisode;
    if (_selectedSeason != null && _selectedEpisodeIndex != null) {
      final episodes = episodesBySeason[_selectedSeason];
      if (episodes != null && _selectedEpisodeIndex! < episodes.length) {
        selectedEpisode = episodes[_selectedEpisodeIndex!];
      }
    }

    // Extract episode-level info when available
    final epInfo = selectedEpisode != null && selectedEpisode['info'] is Map
        ? Map<String, dynamic>.from(selectedEpisode['info'] as Map)
        : <String, dynamic>{};

    final bool showEpisode = selectedEpisode != null;

    // Episode display fields
    final epNum = selectedEpisode?['episode_num']?.toString() ?? '';
    final epTitle = selectedEpisode?['title']?.toString() ?? '';
    final epTitleLabel = [
      if (epNum.isNotEmpty) 'Ep $epNum',
      if (epTitle.isNotEmpty) epTitle,
    ].join(': ');

    final epPlot = epInfo['plot']?.toString() ?? '';
    final epDuration = epInfo['duration']?.toString() ?? '';
    final epRating = epInfo['rating']?.toString() ?? '';
    final epReleaseDate = epInfo['releasedate']?.toString() ??
        epInfo['release_date']?.toString() ??
        epInfo['releaseDate']?.toString() ??
        '';

    final displayTitle = showEpisode
        ? (epTitleLabel.isNotEmpty ? epTitleLabel : 'Episode')
        : name;
    final displayPlot = showEpisode
        ? (epPlot.isNotEmpty ? epPlot : plot)
        : plot;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Primary title
        Text(
          displayTitle,
          textAlign: TextAlign.center,
          style: const TextStyle(
              color: Colors.white,
              fontSize: 16,
              fontWeight: FontWeight.bold),
        ),

        // Series name shown as subtitle when episode is selected
        if (showEpisode) ...[
          const SizedBox(height: 2),
          Text(
            name,
            textAlign: TextAlign.center,
            style: const TextStyle(
                color: _secondaryTextColor, fontSize: 12),
          ),
        ],

        const SizedBox(height: 4),

        // Meta line
        Center(
          child: Text(
            showEpisode
                ? [
                    if (_selectedSeason != null) 'Season $_selectedSeason',
                    if (epDuration.isNotEmpty) epDuration,
                    if (epRating.isNotEmpty) '⭐ $epRating',
                    if (epReleaseDate.isNotEmpty) epReleaseDate,
                  ].join('   ')
                : [
                    if (year.isNotEmpty) year,
                    if (rating.isNotEmpty) '⭐ $rating',
                    if (genre.isNotEmpty) genre,
                  ].join('   '),
            style: const TextStyle(
                color: _secondaryTextColor, fontSize: 11),
            textAlign: TextAlign.center,
          ),
        ),
        const SizedBox(height: 8),

        const Divider(color: Color(0xFF3D3D3D)),
        const SizedBox(height: 6),

        // Plot / description
        if (displayPlot.isNotEmpty) ...[
          Text(displayPlot,
              style: const TextStyle(
                  color: Colors.white, fontSize: 13, height: 1.5)),
          const SizedBox(height: 12),
        ],

        // Favourite toggle (always for the series)
        OutlinedButton.icon(
          onPressed: () => _toggleSeriesFav(series),
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
        const SizedBox(height: 16),
      ],
    );
  }

}
