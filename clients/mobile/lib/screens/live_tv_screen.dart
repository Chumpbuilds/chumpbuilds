import 'dart:convert';

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

/// Live TV screen — categories → channels → EPG + play.
///
/// Ported from `clients/windows/ui/live_tv/live_tv_view.py`.
class LiveTvScreen extends StatefulWidget {
  const LiveTvScreen({super.key, this.initialChannel});

  final Map<String, dynamic>? initialChannel;

  @override
  State<LiveTvScreen> createState() => _LiveTvScreenState();
}

class _LiveTvScreenState extends State<LiveTvScreen> {
  // ─── Theme constants ──────────────────────────────────────────────────────
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _accentColor = Color(0xFF3498DB);
  static const Color _secondaryTextColor = Color(0xFF95A5A6);
  static const Color _liveColor = Color(0xFFE74C3C);

  // ─── State ────────────────────────────────────────────────────────────────
  final _xtream = XtreamService();
  final _favService = FavoritesService();
  final Set<String> _favChannelIds = {};

  List<Map<String, dynamic>> _categories = [];
  List<Map<String, dynamic>> _allChannels = [];
  List<Map<String, dynamic>> _filteredCategories = [];
  List<Map<String, dynamic>> _filteredChannels = [];

  String? _selectedCategoryId;
  String? _selectedCategoryName;
  Map<String, dynamic>? _selectedChannel;
  Map<String, dynamic>? _epgData;

  bool _loadingCategories = true;
  bool _loadingChannels = false;
  bool _loadingEpg = false;
  bool _searchVisible = false;

  /// Whether the user has selected a category.  On first open this is false,
  /// showing the categories (35%) + portal logo (65%) layout.  After a
  /// category tap it becomes true, switching to channels (35%) + player (65%).
  bool _categorySelected = false;

  // ─── VLC embedded player state ────────────────────────────────────────────
  String _vlcStreamUrl = '';
  String _vlcTitle = '';
  int _vlcPlayerKey = 0;
  bool _vlcAutoPlay = false;

  final _headerSearchCtrl = TextEditingController();

  /// track channel count per category
  final Map<String, int> _channelCounts = {};

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
    final raw = await _xtream.getLiveCategories();
    final cats = raw
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    // Also load all channels once for search & counts
    final allRaw = await _xtream.getLiveStreams(null);
    final all = allRaw
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();

    // Build per-category channel counts
    final counts = <String, int>{};
    for (final ch in all) {
      final cid = ch['category_id']?.toString() ?? '';
      counts[cid] = (counts[cid] ?? 0) + 1;
    }

    if (!mounted) return;
    setState(() {
      _categories = cats;
      _filteredCategories = cats;
      _allChannels = all;
      _filteredChannels = all;
      _channelCounts.addAll(counts);
      _loadingCategories = false;
    });

    if (widget.initialChannel != null) {
      final catId = widget.initialChannel!['category_id']?.toString();
      final matchingCat = _categories.firstWhere(
        (c) => c['category_id']?.toString() == catId,
        orElse: () => <String, dynamic>{},
      );
      if (matchingCat.isNotEmpty) {
        await _selectCategory(matchingCat);
      }
      if (mounted) {
        _selectChannel(widget.initialChannel!);
      }
    }
  }

  Future<void> _selectCategory(Map<String, dynamic> cat) async {
    final catId = cat['category_id']?.toString();
    setState(() {
      _categorySelected = true;
      _selectedCategoryId = catId;
      _selectedCategoryName = cat['category_name']?.toString();
      _selectedChannel = null;
      _epgData = null;
      _loadingChannels = true;
    });

    final raw = catId != null
        ? await _xtream.getLiveStreams(catId)
        : await _xtream.getLiveStreams(null);
    final channels = raw
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();

    if (!mounted) return;
    setState(() {
      _filteredChannels = channels;
      _loadingChannels = false;
    });
  }

  Future<void> _selectChannel(Map<String, dynamic> channel) async {
    setState(() {
      _selectedChannel = channel;
      _epgData = null;
      _loadingEpg = true;
    });

    final streamId = channel['stream_id']?.toString() ?? '';
    if (streamId.isNotEmpty) {
      final epg = await _xtream.getShortEpg(streamId);
      if (!mounted) return;
      setState(() {
        _epgData = epg;
        _loadingEpg = false;
      });
    } else {
      if (!mounted) return;
      setState(() => _loadingEpg = false);
    }
  }

  // ─── Favourites ───────────────────────────────────────────────────────────

  Future<void> _loadFavoriteIds() async {
    final favs = await _favService.getFavorites(FavoriteType.channel);
    setState(() {
      _favChannelIds
        ..clear()
        ..addAll(favs.map((f) => f['stream_id']?.toString() ?? ''));
    });
  }

  Future<void> _toggleChannelFav(Map<String, dynamic> ch) async {
    final id = ch['stream_id']?.toString() ?? '';
    await _favService.toggleFavorite(FavoriteType.channel, id, ch);
    await _loadFavoriteIds();
  }

  // ─── Filtering ────────────────────────────────────────────────────────────

  void _onHeaderSearchChanged() {
    _filterCategories();
    _filterChannels();
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

  void _filterChannels() {
    final q = _headerSearchCtrl.text.toLowerCase();
    if (q.isEmpty) {
      // Show channels for the current category
      if (_selectedCategoryId != null) {
        setState(() {
          _filteredChannels = _allChannels
              .where((ch) =>
                  ch['category_id']?.toString() == _selectedCategoryId)
              .toList();
        });
      }
    } else {
      // Search ALL channels
      setState(() {
        _filteredChannels = _allChannels
            .where((ch) =>
                (ch['name'] as String? ?? '').toLowerCase().contains(q))
            .toList();
      });
    }
  }

  // ─── Playback ─────────────────────────────────────────────────────────────

  void _playChannel(Map<String, dynamic> channel) {
    final streamId = channel['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = _xtream.getStreamUrl(streamId, 'live');
    if (url.isEmpty) return;
    final name = channel['name']?.toString() ?? '';
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
          contentType: 'live',
        ),
      ),
    );
  }

  Future<void> _openChannelExternal(Map<String, dynamic> channel) async {
    final streamId = channel['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = _xtream.getStreamUrl(streamId, 'live');
    if (url.isEmpty) return;

    final launched = await ExternalPlayerService.instance.openInVlc(url);
    if (!launched && mounted) {
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
      appBar: _categorySelected
          ? null
          : AppBar(
              title: _searchVisible
                  ? TextField(
                      controller: _headerSearchCtrl,
                      autofocus: true,
                      style: const TextStyle(color: Colors.white, fontSize: 13),
                      decoration: InputDecoration(
                        hintText: '🔍 Search channels & categories...',
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
                  : const Text('Live TV', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
              backgroundColor: _bgColor,
              foregroundColor: Colors.white,
              toolbarHeight: 48,
              leading: IconButton(
                icon: const Icon(Icons.arrow_back, size: 18),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                onPressed: () => Navigator.pop(context),
              ),
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
          // ── Panel 1 (35%): Categories → Channel list after selection ─────
          Expanded(
            flex: 35,
            child: _categorySelected
                ? _buildChannelsPanel()
                : _buildCategoriesPanel(),
          ),
          // ── Panel 2 (65%): Portal logo → Player/EPG after selection ──────
          Expanded(
            flex: 65,
            child: _categorySelected ? _buildEpgPanel() : _buildLogoPanel(),
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
                  final count = _channelCounts[catId] ?? 0;
                  final selected = catId == _selectedCategoryId;
                  return FocusListItem(
                    autofocus: i == 0,
                    onTap: () => _selectCategory(cat),
                    child: Container(
                      color:
                          selected ? const Color(0xFF2C3E50) : Colors.transparent,
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
                  Icons.tv,
                  size: 80,
                  color: _accentColor,
                ),
                fit: BoxFit.contain,
              )
            else
              const Icon(Icons.tv, size: 80, color: _accentColor),
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
              'Select a category to browse channels',
              style: TextStyle(color: _secondaryTextColor, fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  // ─── Panel 2 – Channels ───────────────────────────────────────────────────

  Widget _buildChannelsPanel() {
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
                      _selectedChannel = null;
                      _epgData = null;
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
                    _selectedCategoryName ?? 'Channels',
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
          if (_loadingChannels)
            const LinearProgressIndicator(
              color: _accentColor,
              backgroundColor: Color(0xFF2D2D2D),
            ),
          // List
          if (!_loadingChannels && _filteredChannels.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No channels',
                        style: TextStyle(
                            color: _secondaryTextColor, fontSize: 12))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredChannels.length,
                itemBuilder: (_, i) {
                  final ch = _filteredChannels[i];
                  final iconUrl = ch['stream_icon']?.toString() ?? '';
                  final streamId = ch['stream_id']?.toString() ?? '';
                  final selected =
                      streamId == _selectedChannel?['stream_id']?.toString();
                  final isFav = _favChannelIds.contains(streamId);
                  return FocusListItem(
                    autofocus: i == 0,
                    onTap: () => _selectChannel(ch),
                    child: Container(
                      color: selected
                          ? const Color(0xFF2C3E50)
                          : Colors.transparent,
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 4),
                      child: Row(
                        children: [
                          // Logo
                          SizedBox(
                            width: 40,
                            height: 40,
                            child: iconUrl.isNotEmpty
                                ? CachedNetworkImage(
                                    imageUrl: iconUrl,
                                    placeholder: (_, __) => const Text('📺',
                                        style: TextStyle(fontSize: 20)),
                                    errorWidget: (_, __, ___) => const Text(
                                        '📺',
                                        style: TextStyle(fontSize: 20)),
                                    fit: BoxFit.contain,
                                  )
                                : const Text('📺',
                                    style: TextStyle(fontSize: 20)),
                          ),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              ch['name']?.toString() ?? '',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 12),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          // Favourite star
                          GestureDetector(
                            onTap: () => _toggleChannelFav(ch),
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
        ],
      ),
    );
  }

  // ─── Panel 3 – EPG / Detail ───────────────────────────────────────────────

  Widget _buildEpgPanel() {
    final player = VlcPlayerWidget(
      key: ValueKey(_vlcPlayerKey),
      streamUrl: _vlcStreamUrl,
      title: _vlcTitle,
      contentType: 'live',
      autoPlay: _vlcAutoPlay,
    );

    if (_selectedChannel == null) {
      return ColoredBox(
        color: const Color(0xFF1E1E1E),
        child: Column(
          children: [
            // ── Row 1 (60%): 30% logo placeholder | 70% player (idle) ──
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
                        child: Text('📺',
                            style: TextStyle(fontSize: 32)),
                      ),
                    ),
                  ),
                  Expanded(flex: 70, child: player),
                ],
              ),
            ),
            // ── Row 2 (40%): prompt ──────────────────────────────────────
            const Expanded(
              flex: 40,
              child: Center(
                child: Text(
                  '📺  Select a channel and click Play to start streaming',
                  style:
                      TextStyle(color: _secondaryTextColor, fontSize: 14),
                  textAlign: TextAlign.center,
                ),
              ),
            ),
          ],
        ),
      );
    }

    final ch = _selectedChannel!;
    final name = ch['name']?.toString() ?? '';
    final iconUrl = ch['stream_icon']?.toString() ?? '';
    final epgListings = (_epgData?['epg_listings'] as List?) ?? [];

    return ColoredBox(
      color: const Color(0xFF1E1E1E),
      child: Column(
        children: [
          // ── Row 1 (60%): 30% channel logo | 70% player ─────────────
          Expanded(
            flex: 60,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 30% – channel logo
                Expanded(
                  flex: 30,
                  child: Container(
                    color: const Color(0xFF2D2D2D),
                    child: iconUrl.isNotEmpty
                        ? CachedNetworkImage(
                            imageUrl: iconUrl,
                            fit: BoxFit.contain,
                            placeholder: (_, __) => const Center(
                                child: Text('📺',
                                    style: TextStyle(fontSize: 32))),
                            errorWidget: (_, __, ___) => const Center(
                                child: Text('📺',
                                    style: TextStyle(fontSize: 32))),
                          )
                        : const Center(
                            child: Text('📺',
                                style: TextStyle(fontSize: 32))),
                  ),
                ),
                // 70% – player
                Expanded(flex: 70, child: player),
              ],
            ),
          ),

          // ── Row 2 (40%): EPG full width ──────────────────────────────
          Expanded(
            flex: 40,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Compact channel name + action buttons
                Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          name,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 13,
                            fontWeight: FontWeight.bold,
                          ),
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      SizedBox(
                        height: 28,
                        child: ElevatedButton.icon(
                          onPressed: () => _playChannel(ch),
                          icon: const Icon(Icons.play_arrow, size: 14),
                          label: const Text('Play',
                              style: TextStyle(fontSize: 11)),
                          style: tvFocusButtonStyle(ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF27AE60),
                            foregroundColor: Colors.white,
                            padding:
                                const EdgeInsets.symmetric(horizontal: 8),
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
                          label: const Text('Stop',
                              style: TextStyle(fontSize: 11)),
                          style: tvFocusButtonStyle(ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFE74C3C),
                            foregroundColor: Colors.white,
                            padding:
                                const EdgeInsets.symmetric(horizontal: 8),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(4)),
                          )),
                        ),
                      ),
                      const SizedBox(width: 4),
                      SizedBox(
                        height: 28,
                        child: OutlinedButton(
                          onPressed: () => _openChannelExternal(ch),
                          style: tvFocusOutlinedButtonStyle(
                            OutlinedButton.styleFrom(
                              foregroundColor: Colors.white,
                              side: const BorderSide(color: Color(0xFF3D3D3D)),
                              padding:
                                  const EdgeInsets.symmetric(horizontal: 6),
                              shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(4)),
                            ),
                          ),
                          child: const Text('↗ VLC',
                              style: TextStyle(fontSize: 11)),
                        ),
                      ),
                      const SizedBox(width: 4),
                      SizedBox(
                        height: 28,
                        child: ElevatedButton.icon(
                          onPressed: _vlcStreamUrl.isNotEmpty
                              ? _goFullscreen
                              : null,
                          icon: const Icon(Icons.fullscreen, size: 14),
                          label: const Text('Fullscreen',
                              style: TextStyle(fontSize: 11)),
                          style: tvFocusButtonStyle(ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF8E44AD),
                            foregroundColor: Colors.white,
                            padding:
                                const EdgeInsets.symmetric(horizontal: 8),
                            shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(4)),
                          )),
                        ),
                      ),
                    ],
                  ),
                ),

                const Divider(color: Color(0xFF3D3D3D), height: 1),

                // EPG header
                Padding(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  child: Row(
                    children: [
                      const Text(
                        '📅 Program Guide',
                        style: TextStyle(
                            color: _accentColor,
                            fontSize: 12,
                            fontWeight: FontWeight.bold),
                      ),
                      const SizedBox(width: 6),
                      if (_loadingEpg)
                        const SizedBox(
                          width: 12,
                          height: 12,
                          child: CircularProgressIndicator(
                            strokeWidth: 1.5,
                            color: _accentColor,
                          ),
                        ),
                    ],
                  ),
                ),

                // EPG list (100% width, fills remaining Row 2 space)
                Expanded(
                  child: ClipRect(
                    child: (!_loadingEpg && epgListings.isEmpty)
                        ? const Center(
                            child: Text('No EPG data available',
                                style: TextStyle(
                                    color: _secondaryTextColor,
                                    fontSize: 12)),
                          )
                        : ListView.builder(
                            padding:
                                const EdgeInsets.symmetric(horizontal: 8),
                            itemCount: epgListings.length,
                            itemBuilder: (context, index) {
                              final p = Map<String, dynamic>.from(
                                  epgListings[index] as Map);
                              final title = _decodeEpgTitle(
                                  p['title']?.toString() ?? '');
                              final start = p['start']?.toString() ?? '';
                              final end = p['end']?.toString() ?? '';
                              final isNow = p['now_playing'] == 1 ||
                                  p['now_playing'] == true ||
                                  p['now_playing']?.toString() == '1';
                              return Container(
                                margin: const EdgeInsets.only(bottom: 2),
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 6),
                                decoration: BoxDecoration(
                                  color: _surfaceColor,
                                  borderRadius: BorderRadius.circular(4),
                                  border: isNow
                                      ? Border.all(
                                          color: _liveColor, width: 1)
                                      : null,
                                ),
                                child: Row(
                                  crossAxisAlignment:
                                      CrossAxisAlignment.start,
                                  children: [
                                    if (isNow) ...[
                                      const Text('🔴',
                                          style: TextStyle(fontSize: 10)),
                                      const SizedBox(width: 4),
                                    ],
                                    Expanded(
                                      child: Column(
                                        crossAxisAlignment:
                                            CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            title,
                                            style: TextStyle(
                                              color: isNow
                                                  ? _liveColor
                                                  : Colors.white,
                                              fontWeight: isNow
                                                  ? FontWeight.bold
                                                  : FontWeight.normal,
                                              fontSize: 12,
                                            ),
                                          ),
                                          if (start.isNotEmpty)
                                            Text(
                                              '$start – $end',
                                              style: const TextStyle(
                                                  color: _secondaryTextColor,
                                                  fontSize: 10),
                                            ),
                                        ],
                                      ),
                                    ),
                                  ],
                                ),
                              );
                            },
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

  /// EPG titles are sometimes base64-encoded.
  String _decodeEpgTitle(String raw) {
    if (raw.isEmpty) return raw;
    try {
      final decoded = utf8.decode(base64.decode(raw));
      return decoded;
    } catch (_) {
      return raw; // fallback to raw if not valid base64
    }
  }
}