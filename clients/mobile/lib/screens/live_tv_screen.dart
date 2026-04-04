import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../screens/android_hls_fullscreen_screen.dart';
import '../services/epg_service.dart';
import '../services/external_player_service.dart';
import '../services/favorites_service.dart';
import '../services/license_service.dart';
import '../services/xtream_service.dart';
import '../widgets/focus_list_item.dart';
import '../widgets/vlc_player_widget.dart';
import '../widgets/system_ui_wrapper.dart';

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
  List<Map<String, dynamic>>? _epgData;

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
    WakelockPlus.disable();
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
    final tappedId = channel['stream_id']?.toString() ?? '';
    final currentId = _selectedChannel?['stream_id']?.toString() ?? '';

    // Second tap on the already-playing channel → go fullscreen.
    if (tappedId.isNotEmpty && tappedId == currentId && _vlcStreamUrl.isNotEmpty) {
      await _goFullscreen();
      return;
    }

    // Look up EPG from the local XMLTV cache — instant, no API call.
    final epgChannelId = channel['epg_channel_id']?.toString() ?? '';
    final listings = EpgService().getEpgForChannel(epgChannelId);

    setState(() {
      _selectedChannel = channel;
      _epgData = listings;
      _loadingEpg = false;
    });

    // Auto-start playback immediately on first select.
    _playChannel(channel);
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
    WakelockPlus.enable();
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
    WakelockPlus.disable();
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
    // Re-apply immersive mode after returning from fullscreen.
    await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  Future<void> _openChannelExternal(Map<String, dynamic> channel) async {
    final streamId = channel['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = _xtream.getStreamUrl(streamId, 'live');
    if (url.isEmpty) return;

    // Stop the embedded player before launching VLC to avoid dual playback.
    _stopEmbeddedPlayback();

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
    return SystemUiWrapper(child: Scaffold(
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
          // ── Panel 1 (30%): Categories → Channel list after selection ─────
          Expanded(
            flex: 30,
            child: _categorySelected
                ? _buildChannelsPanel()
                : _buildCategoriesPanel(),
          ),
          // ── Panel 2 (70%): Portal logo → Player/EPG after selection ──────
          Expanded(
            flex: 70,
            child: _categorySelected ? _buildEpgPanel() : _buildLogoPanel(),
          ),
        ],
      ),
    ));
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
      onStopRequested: _stopEmbeddedPlayback,
      onFullscreenRequested: _goFullscreen,
    );

    if (_selectedChannel == null) {
      return ColoredBox(
        color: const Color(0xFF1E1E1E),
        child: Column(
          children: [
            // ── Row 1 (53%): 30% logo placeholder | 70% player (idle) ──
            Expanded(
              flex: 53,
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
            // ── Row 2 (47%): prompt ──────────────────────────────────────
            const Expanded(
              flex: 47,
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
    final epgListings = _epgData ?? [];

    return ColoredBox(
      color: const Color(0xFF1E1E1E),
      child: Column(
        children: [
          // ── Row 1 (53%): 30% channel info | 70% player ─────────────
          Expanded(
            flex: 53,
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 30% – channel name + current programme
                Expanded(
                  flex: 30,
                  child: Container(
                    color: const Color(0xFF2D2D2D),
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        // "🔴 NOW PLAYING" badge
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: Color(0x26E74C3C),
                            borderRadius: BorderRadius.circular(4),
                            border: Border.all(color: _liveColor, width: 0.8),
                          ),
                          child: const Text(
                            '🔴  NOW PLAYING',
                            style: TextStyle(
                              color: _liveColor,
                              fontSize: 9,
                              fontWeight: FontWeight.bold,
                              letterSpacing: 0.5,
                            ),
                          ),
                        ),
                        const SizedBox(height: 8),
                        // Channel name
                        Text(
                          name,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                          ),
                          textAlign: TextAlign.center,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 8),
                        // Programme title + time
                        if (_loadingEpg)
                          const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 1.5, color: _accentColor),
                          )
                        else
                          Builder(
                            builder: (_) {
                              final info = _currentProgrammeInfo();
                              return Column(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    info.title,
                                    style: const TextStyle(
                                      color: _accentColor,
                                      fontSize: 12,
                                    ),
                                    textAlign: TextAlign.center,
                                    maxLines: 3,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                  if (info.time.isNotEmpty) ...[
                                    const SizedBox(height: 4),
                                    Text(
                                      info.time,
                                      style: const TextStyle(
                                        color: _secondaryTextColor,
                                        fontSize: 11,
                                      ),
                                      textAlign: TextAlign.center,
                                    ),
                                  ],
                                ],
                              );
                            },
                          ),
                      ],
                    ),
                  ),
                ),
                // 70% – player
                Expanded(flex: 70, child: player),
              ],
            ),
          ),

          // ── Row 2 (47%): EPG full width ──────────────────────────────
          Expanded(
            flex: 47,
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
                        : Builder(builder: (context) {
                            final upcomingListings = epgListings.where((e) {
                              final m = e as Map;
                              return m['is_current'] != true;
                            }).toList();
                            return ListView.builder(
                              padding:
                                  const EdgeInsets.symmetric(horizontal: 8),
                              itemCount: upcomingListings.length,
                              itemBuilder: (context, index) {
                                final p = Map<String, dynamic>.from(
                                    upcomingListings[index] as Map);
                                final title = p['title']?.toString() ?? '';
                                final start = _formatEpgTime(p['start']?.toString());
                                final stop = _formatEpgTime(p['stop']?.toString());
                                return Container(
                                  margin: const EdgeInsets.only(bottom: 2),
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 6),
                                  decoration: BoxDecoration(
                                    color: _surfaceColor,
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.center,
                                    children: [
                                      if (start.isNotEmpty) ...[
                                        Text(
                                          '$start–$stop',
                                          style: const TextStyle(
                                              color: _secondaryTextColor,
                                              fontSize: 10),
                                        ),
                                        const SizedBox(width: 6),
                                      ],
                                      Expanded(
                                        child: Text(
                                          title,
                                          style: const TextStyle(
                                            color: Colors.white,
                                            fontWeight: FontWeight.normal,
                                            fontSize: 12,
                                          ),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ),
                                    ],
                                  ),
                                );
                              },
                            );
                          }),
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

  /// Parses an EPG time field and returns it formatted as "HH:mm" (local time).
  /// Handles Unix-seconds integers, "YYYY-MM-DD HH:mm:ss", and
  /// "YYYYMMDDHHmmss[ +HHMM]" (XMLTV compact format).
  /// Returns '' if the value cannot be parsed.
  String _formatEpgTime(String? raw) {
    if (raw == null || raw.isEmpty) return '';

    // 1. Pure integer → Unix seconds
    final ts = int.tryParse(raw.trim());
    if (ts != null && ts > 0) {
      final dt = DateTime.fromMillisecondsSinceEpoch(ts * 1000);
      return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    }

    // 2. "YYYY-MM-DD HH:mm:ss"
    try {
      final dt = DateTime.parse(raw.trim());
      return '${dt.toLocal().hour.toString().padLeft(2, '0')}:${dt.toLocal().minute.toString().padLeft(2, '0')}';
    } catch (_) {}

    // 3. XMLTV compact: "YYYYMMDDHHmmss[ +HHMM]"
    final compact = raw.trim();
    if (compact.length >= 14 && RegExp(r'^\d{14}').hasMatch(compact)) {
      try {
        final year   = int.parse(compact.substring(0, 4));
        final month  = int.parse(compact.substring(4, 6));
        final day    = int.parse(compact.substring(6, 8));
        final hour   = int.parse(compact.substring(8, 10));
        final minute = int.parse(compact.substring(10, 12));
        final second = int.parse(compact.substring(12, 14));
        DateTime dt;
        final rest = compact.substring(14).trim();
        if (rest.isNotEmpty && (rest.startsWith('+') || rest.startsWith('-')) && rest.length >= 5) {
          final sign       = rest[0] == '+' ? 1 : -1;
          final offH       = int.tryParse(rest.substring(1, 3)) ?? 0;
          final offM       = int.tryParse(rest.substring(3, 5)) ?? 0;
          final offsetMins = sign * (offH * 60 + offM);
          dt = DateTime.utc(year, month, day, hour, minute, second)
              .subtract(Duration(minutes: offsetMins))
              .toLocal();
        } else {
          dt = DateTime.utc(year, month, day, hour, minute, second).toLocal();
        }
        return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
      } catch (_) {}
    }

    return '';
  }

  /// Returns a record with the title and formatted time (HH:mm – HH:mm) of the
  /// currently-playing EPG entry.
  ({String title, String time}) _currentProgrammeInfo() {
    const fallback = (title: 'No programme info', time: '');
    final listings = _epgData;
    if (listings == null || listings.isEmpty) return fallback;

    // Pass 1: is_current flag.
    Map<String, dynamic>? match;
    for (final p in listings) {
      if (p['is_current'] == true) { match = p; break; }
    }

    // Pass 2: first entry fallback.
    match ??= listings.first;

    final title = match['title']?.toString() ?? '';

    // Format start/stop timestamps as HH:mm – HH:mm.
    String time = '';
    final startStr = _formatEpgTime(match['start']?.toString());
    final stopStr  = _formatEpgTime(match['stop']?.toString());
    if (startStr.isNotEmpty && stopStr.isNotEmpty) {
      time = '$startStr – $stopStr';
    }

    return (title: title.isNotEmpty ? title : 'No programme info', time: time);
  }
}