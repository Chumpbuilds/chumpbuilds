import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../screens/android_hls_fullscreen_screen.dart';
import '../services/external_player_service.dart';
import '../services/favorites_service.dart';
import '../services/xtream_service.dart';
import '../widgets/system_ui_wrapper.dart';

/// Full-screen series detail page — cover, description, season/episode
/// selection, and play actions.
class SeriesDetailScreen extends StatefulWidget {
  const SeriesDetailScreen({
    super.key,
    required this.series,
    required this.xtream,
  });

  final Map<String, dynamic> series;
  final XtreamService xtream;

  @override
  State<SeriesDetailScreen> createState() => _SeriesDetailScreenState();
}

class _SeriesDetailScreenState extends State<SeriesDetailScreen> {
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _accentColor = Color(0xFF3498DB);
  static const Color _secondaryTextColor = Color(0xFF95A5A6);

  Map<String, dynamic>? _seriesInfo;
  bool _loadingDetail = true;
  bool _isFav = false;
  final _favService = FavoritesService();

  // Season / episode selection
  Map<int, List<Map<String, dynamic>>> _episodesBySeason = {};
  List<int> _sortedSeasons = [];
  int? _selectedSeason;
  int? _selectedEpisodeIndex;

  // Focus state for dropdowns and action buttons
  bool _seasonDropdownFocused = false;
  bool _episodeDropdownFocused = false;
  bool _playButtonFocused = false;
  bool _vlcButtonFocused = false;

  late final FocusNode _seasonFocusNode;
  late final FocusNode _episodeFocusNode;
  late final FocusNode _playFocusNode;
  late final FocusNode _vlcFocusNode;

  @override
  void initState() {
    super.initState();
    _seasonFocusNode = FocusNode()
      ..addListener(() {
        setState(() => _seasonDropdownFocused = _seasonFocusNode.hasFocus);
      });
    _episodeFocusNode = FocusNode()
      ..addListener(() {
        setState(() => _episodeDropdownFocused = _episodeFocusNode.hasFocus);
      });
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
      _seasonFocusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _seasonFocusNode.dispose();
    _episodeFocusNode.dispose();
    _playFocusNode.dispose();
    _vlcFocusNode.dispose();
    super.dispose();
  }

  Future<void> _loadDetail() async {
    final seriesId = widget.series['series_id']?.toString() ?? '';
    if (seriesId.isNotEmpty) {
      final info = await widget.xtream.getSeriesInfo(seriesId);
      if (!mounted) return;
      final episodesBySeason = _parseEpisodes(info['episodes']);
      final sortedSeasons = episodesBySeason.keys.toList()..sort();
      setState(() {
        _seriesInfo = info;
        _episodesBySeason = episodesBySeason;
        _sortedSeasons = sortedSeasons;
        _loadingDetail = false;
        if (sortedSeasons.isNotEmpty) {
          _selectedSeason = sortedSeasons.first;
          _selectedEpisodeIndex = 0;
        }
      });
    } else {
      if (!mounted) return;
      setState(() => _loadingDetail = false);
    }
  }

  Future<void> _checkFavorite() async {
    final favs = await _favService.getFavorites(FavoriteType.series);
    final id = widget.series['series_id']?.toString() ?? '';
    if (!mounted) return;
    setState(() {
      _isFav = favs.any((f) => f['series_id']?.toString() == id);
    });
  }

  Future<void> _toggleFavorite() async {
    final id = widget.series['series_id']?.toString() ?? '';
    await _favService.toggleFavorite(FavoriteType.series, id, widget.series);
    await _checkFavorite();
  }

  /// Normalise the `episodes` field from getSeriesInfo into a map of
  /// `seasonNumber → List<Map>`.
  ///
  /// Handles three data shapes from the server:
  ///   1. `{"1": [...], "2": [...]}` — season-keyed dict
  ///   2. `{"ep_id": {...}, ...}` — episode-keyed dict
  ///   3. `[{...}, {...}]` — flat list
  Map<int, List<Map<String, dynamic>>> _parseEpisodes(dynamic raw) {
    final result = <int, List<Map<String, dynamic>>>{};
    if (raw == null) return result;

    if (raw is Map) {
      final firstVal = raw.values.isNotEmpty ? raw.values.first : null;
      if (firstVal is List) {
        // Shape 1: season-keyed
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

  List<Map<String, dynamic>> get _currentEpisodes {
    if (_selectedSeason == null) return [];
    return _episodesBySeason[_selectedSeason] ?? [];
  }

  Map<String, dynamic>? get _selectedEpisode {
    final eps = _currentEpisodes;
    if (_selectedEpisodeIndex == null || _selectedEpisodeIndex! >= eps.length) {
      return null;
    }
    return eps[_selectedEpisodeIndex!];
  }

  void _playEpisode() {
    final ep = _selectedEpisode;
    if (ep == null) return;
    final episodeId = ep['id']?.toString() ?? '';
    if (episodeId.isEmpty) return;
    final ext = ep['container_extension']?.toString() ?? 'mp4';
    final url = widget.xtream.getStreamUrl(episodeId, 'series', extension: ext);
    if (url.isEmpty) return;

    final epNum = ep['episode_num']?.toString() ?? '';
    final epTitle = ep['title']?.toString() ?? '';
    final label = [
      if (epNum.isNotEmpty) 'Ep $epNum',
      if (epTitle.isNotEmpty) epTitle,
    ].join(': ');
    final displayTitle = label.isNotEmpty
        ? label
        : (widget.series['name']?.toString() ?? 'Episode');

    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => AndroidHlsFullscreenScreen(
          streamUrl: url,
          title: displayTitle,
          contentType: 'series',
        ),
      ),
    );
  }

  Future<void> _openExternal() async {
    final ep = _selectedEpisode;
    if (ep == null) return;
    final episodeId = ep['id']?.toString() ?? '';
    if (episodeId.isEmpty) return;
    final ext = ep['container_extension']?.toString() ?? 'mp4';
    final url = widget.xtream.getStreamUrl(episodeId, 'series', extension: ext);
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
    final series = widget.series;
    final name = series['name']?.toString() ?? '';
    final coverUrl = series['cover']?.toString() ?? '';

    // Series-level info from the loaded detail
    final info = _seriesInfo?['info'] is Map
        ? Map<String, dynamic>.from(_seriesInfo!['info'] as Map)
        : <String, dynamic>{};
    final plot = info['plot']?.toString() ?? '';
    final genre = info['genre']?.toString() ?? series['genre']?.toString() ?? '';
    final rating = info['rating']?.toString() ?? series['rating']?.toString() ?? '';
    final year = info['releaseDate']?.toString() ??
        info['release_date']?.toString() ??
        series['year']?.toString() ??
        '';

    // Episode-level info for the selected episode
    final ep = _selectedEpisode;
    final epInfo = ep != null && ep['info'] is Map
        ? Map<String, dynamic>.from(ep['info'] as Map)
        : <String, dynamic>{};
    final epPlot = epInfo['plot']?.toString() ??
        epInfo['overview']?.toString() ??
        ep?['plot']?.toString() ??
        '';

    final hasEpisode = ep != null;

    // Build episode title label ("S1 E3: Episode Title")
    final epNum = ep?['episode_num']?.toString() ?? '';
    final epTitle = ep?['title']?.toString() ?? '';
    final seasonNum = _selectedSeason?.toString() ?? '';
    final epLabelPrefix = (seasonNum.isNotEmpty && epNum.isNotEmpty)
        ? 'S$seasonNum E$epNum'
        : (epNum.isNotEmpty ? 'Ep $epNum' : '');
    final episodeLabel = [
      if (epLabelPrefix.isNotEmpty) epLabelPrefix,
      if (epTitle.isNotEmpty) epTitle,
    ].join(': ');

    // Episode-specific meta fields
    final epAirDate = epInfo['air_date']?.toString() ?? '';
    final epDurationRaw = epInfo['duration']?.toString() ?? epInfo['duration_secs']?.toString() ?? '';
    final epRating = epInfo['rating']?.toString() ?? '';
    final canPlay = hasEpisode && (ep['id']?.toString() ?? '').isNotEmpty;

    return SystemUiWrapper(
      child: Scaffold(
        backgroundColor: _bgColor,
        body: Row(
          children: [
            // ── Left side (35%): Cover image ──
            Expanded(
              flex: 35,
              child: Container(
                color: Colors.black,
                child: coverUrl.isNotEmpty
                    ? CachedNetworkImage(
                        imageUrl: coverUrl,
                        fit: BoxFit.contain,
                        placeholder: (_, __) => const Center(
                          child: CircularProgressIndicator(color: _accentColor),
                        ),
                        errorWidget: (_, __, ___) => const Center(
                          child: Icon(Icons.video_library, size: 64, color: _secondaryTextColor),
                        ),
                      )
                    : const Center(
                        child: Icon(Icons.video_library, size: 64, color: _secondaryTextColor),
                      ),
              ),
            ),
            // ── Right side (65%): Info + controls ──
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
                        IconButton(
                          icon: const Icon(Icons.arrow_back, size: 20, color: Colors.white),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(),
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
                        IconButton(
                          icon: Icon(
                            _isFav ? Icons.star : Icons.star_border,
                            color: _isFav ? const Color(0xFFf39c12) : _secondaryTextColor,
                            size: 22,
                          ),
                          padding: EdgeInsets.zero,
                          constraints: const BoxConstraints(),
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
                                // Series-level meta chips (genre, rating, year)
                                Wrap(
                                  spacing: 12,
                                  runSpacing: 4,
                                  children: [
                                    if (genre.isNotEmpty)
                                      _metaChip(Icons.category, genre),
                                    if (rating.isNotEmpty)
                                      _metaChip(Icons.star, rating),
                                    if (year.isNotEmpty)
                                      _metaChip(Icons.calendar_today, year),
                                  ],
                                ),
                                const SizedBox(height: 12),

                                // Episode info (when selected) or series plot
                                if (hasEpisode) ...[
                                  if (episodeLabel.isNotEmpty)
                                    Padding(
                                      padding: const EdgeInsets.only(bottom: 8),
                                      child: Text(
                                        episodeLabel,
                                        style: const TextStyle(
                                          color: Colors.white,
                                          fontSize: 13,
                                          fontWeight: FontWeight.bold,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                  if (epAirDate.isNotEmpty || epDurationRaw.isNotEmpty || epRating.isNotEmpty)
                                    Padding(
                                      padding: const EdgeInsets.only(bottom: 8),
                                      child: Wrap(
                                        spacing: 12,
                                        runSpacing: 4,
                                        children: [
                                          if (epAirDate.isNotEmpty)
                                            _metaChip(Icons.event, epAirDate),
                                          if (epDurationRaw.isNotEmpty)
                                            _metaChip(Icons.timer, epDurationRaw),
                                          if (epRating.isNotEmpty)
                                            _metaChip(Icons.star_half, epRating),
                                        ],
                                      ),
                                    ),
                                  Text(
                                    epPlot.isNotEmpty ? epPlot : plot,
                                    style: const TextStyle(
                                      color: _secondaryTextColor,
                                      fontSize: 12,
                                      height: 1.5,
                                    ),
                                  ),
                                ] else if (plot.isNotEmpty)
                                  Text(
                                    plot,
                                    style: const TextStyle(
                                      color: _secondaryTextColor,
                                      fontSize: 12,
                                      height: 1.5,
                                    ),
                                  ),
                                const SizedBox(height: 16),

                                // ── Season dropdown ──
                                if (_sortedSeasons.isNotEmpty) ...[
                                  const Text(
                                    'Season',
                                    style: TextStyle(color: _secondaryTextColor, fontSize: 11),
                                  ),
                                  const SizedBox(height: 4),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10),
                                    decoration: BoxDecoration(
                                      color: _surfaceColor,
                                      borderRadius: BorderRadius.circular(6),
                                      border: Border.all(
                                        color: _seasonDropdownFocused ? Colors.white : const Color(0xFF3D3D3D),
                                        width: _seasonDropdownFocused ? 3 : 1,
                                      ),
                                    ),
                                    child: DropdownButton<int>(
                                      value: _selectedSeason,
                                      focusNode: _seasonFocusNode,
                                      isExpanded: true,
                                      underline: const SizedBox.shrink(),
                                      dropdownColor: _surfaceColor,
                                      style: const TextStyle(color: Colors.white, fontSize: 13),
                                      items: _sortedSeasons.map((s) {
                                        return DropdownMenuItem<int>(
                                          value: s,
                                          child: Text('Season $s'),
                                        );
                                      }).toList(),
                                      onChanged: (s) {
                                        if (s != null) {
                                          setState(() {
                                            _selectedSeason = s;
                                            _selectedEpisodeIndex = 0;
                                          });
                                        }
                                      },
                                    ),
                                  ),
                                  const SizedBox(height: 12),
                                ],

                                // ── Episode dropdown ──
                                if (_currentEpisodes.isNotEmpty) ...[
                                  const Text(
                                    'Episode',
                                    style: TextStyle(color: _secondaryTextColor, fontSize: 11),
                                  ),
                                  const SizedBox(height: 4),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10),
                                    decoration: BoxDecoration(
                                      color: _surfaceColor,
                                      borderRadius: BorderRadius.circular(6),
                                      border: Border.all(
                                        color: _episodeDropdownFocused ? Colors.white : const Color(0xFF3D3D3D),
                                        width: _episodeDropdownFocused ? 3 : 1,
                                      ),
                                    ),
                                    child: DropdownButton<int>(
                                      value: _selectedEpisodeIndex,
                                      focusNode: _episodeFocusNode,
                                      isExpanded: true,
                                      underline: const SizedBox.shrink(),
                                      dropdownColor: _surfaceColor,
                                      style: const TextStyle(color: Colors.white, fontSize: 13),
                                      items: List.generate(_currentEpisodes.length, (i) {
                                        final e = _currentEpisodes[i];
                                        final num = e['episode_num']?.toString() ?? '';
                                        final title = e['title']?.toString() ?? '';
                                        final label = [
                                          if (num.isNotEmpty) 'Ep $num',
                                          if (title.isNotEmpty) title,
                                        ].join(': ');
                                        return DropdownMenuItem<int>(
                                          value: i,
                                          child: Text(
                                            label.isNotEmpty ? label : 'Episode ${i + 1}',
                                            overflow: TextOverflow.ellipsis,
                                          ),
                                        );
                                      }),
                                      onChanged: (i) {
                                        if (i != null) {
                                          setState(() => _selectedEpisodeIndex = i);
                                        }
                                      },
                                    ),
                                  ),
                                  const SizedBox(height: 12),
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
                            onPressed: canPlay ? _playEpisode : null,
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
                        const SizedBox(width: 12),
                        // Play in VLC button
                        Expanded(
                          child: ElevatedButton.icon(
                            focusNode: _vlcFocusNode,
                            onPressed: canPlay ? _openExternal : null,
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
