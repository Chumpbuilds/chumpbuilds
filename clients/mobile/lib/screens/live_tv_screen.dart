import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/xtream_service.dart';

/// Live TV screen — categories → channels → EPG + play.
///
/// Ported from `clients/windows/ui/live_tv/live_tv_view.py`.
class LiveTvScreen extends StatefulWidget {
  const LiveTvScreen({super.key});

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

  final _categorySearchCtrl = TextEditingController();
  final _channelSearchCtrl = TextEditingController();

  /// track channel count per category
  final Map<String, int> _channelCounts = {};

  @override
  void initState() {
    super.initState();
    _loadCategories();
    _categorySearchCtrl.addListener(_filterCategories);
    _channelSearchCtrl.addListener(_filterChannels);
  }

  @override
  void dispose() {
    _categorySearchCtrl.dispose();
    _channelSearchCtrl.dispose();
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

    // Auto-select first category
    if (cats.isNotEmpty) {
      _selectCategory(cats.first);
    }
  }

  Future<void> _selectCategory(Map<String, dynamic> cat) async {
    final catId = cat['category_id']?.toString();
    setState(() {
      _selectedCategoryId = catId;
      _selectedCategoryName = cat['category_name']?.toString();
      _selectedChannel = null;
      _epgData = null;
      _channelSearchCtrl.clear();
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

  void _filterChannels() {
    final q = _channelSearchCtrl.text.toLowerCase();
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

  Future<void> _playChannel(Map<String, dynamic> channel) async {
    final streamId = channel['stream_id']?.toString() ?? '';
    if (streamId.isEmpty) return;
    final url = _xtream.getStreamUrl(streamId, 'live');
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
    if (_selectedChannel != null) {
      return _buildChannelDetail();
    }
    if (_selectedCategoryId != null) {
      return _buildChannelList();
    }
    return _buildCategoryList();
  }

  // ─── Category list view ───────────────────────────────────────────────────

  Widget _buildCategoryList() {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text('Live TV'),
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
                  final count = _channelCounts[catId] ?? 0;
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

  // ─── Channel list view ────────────────────────────────────────────────────

  Widget _buildChannelList() {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: Text(_selectedCategoryName ?? 'Channels'),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        leading: BackButton(
          onPressed: () => setState(() {
            _selectedCategoryId = null;
            _selectedCategoryName = null;
            _filteredChannels = _allChannels;
            _channelSearchCtrl.clear();
          }),
        ),
      ),
      body: Column(
        children: [
          _buildSearchBar(_channelSearchCtrl, 'Search all channels…'),
          if (_loadingChannels)
            const Expanded(
                child: Center(
                    child: CircularProgressIndicator(color: _primaryColor)))
          else if (_filteredChannels.isEmpty)
            const Expanded(
                child: Center(
                    child: Text('No channels found',
                        style: TextStyle(color: _secondaryTextColor))))
          else
            Expanded(
              child: ListView.builder(
                itemCount: _filteredChannels.length,
                itemBuilder: (_, i) {
                  final ch = _filteredChannels[i];
                  final iconUrl = ch['stream_icon']?.toString() ?? '';
                  return ListTile(
                    leading: iconUrl.isNotEmpty
                        ? SizedBox(
                            width: 40,
                            height: 40,
                            child: CachedNetworkImage(
                              imageUrl: iconUrl,
                              placeholder: (_, __) => const Text('📺',
                                  style: TextStyle(fontSize: 24)),
                              errorWidget: (_, __, ___) => const Text('📺',
                                  style: TextStyle(fontSize: 24)),
                              fit: BoxFit.contain,
                            ),
                          )
                        : const Text('📺', style: TextStyle(fontSize: 24)),
                    title: Text(
                      ch['name']?.toString() ?? '',
                      style: const TextStyle(color: Colors.white),
                    ),
                    onTap: () => _selectChannel(ch),
                  );
                },
              ),
            ),
        ],
      ),
    );
  }

  // ─── Channel detail / EPG view ────────────────────────────────────────────

  Widget _buildChannelDetail() {
    final ch = _selectedChannel!;
    final name = ch['name']?.toString() ?? '';
    final iconUrl = ch['stream_icon']?.toString() ?? '';
    final epgListings = (_epgData?['epg_listings'] as List?) ?? [];

    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: Text(name),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        leading: BackButton(
          onPressed: () => setState(() {
            _selectedChannel = null;
            _epgData = null;
          }),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Channel logo
            if (iconUrl.isNotEmpty)
              Center(
                child: CachedNetworkImage(
                  imageUrl: iconUrl,
                  height: 80,
                  placeholder: (_, __) => const SizedBox(height: 80),
                  errorWidget: (_, __, ___) => const SizedBox(height: 80),
                  fit: BoxFit.contain,
                ),
              ),
            const SizedBox(height: 16),

            // Channel name
            Text(
              name,
              textAlign: TextAlign.center,
              style: const TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 24),

            // Play button
            ElevatedButton.icon(
              onPressed: () => _playChannel(ch),
              icon: const Icon(Icons.play_arrow),
              label: const Text('Play Channel'),
              style: ElevatedButton.styleFrom(
                backgroundColor: _primaryColor,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4)),
              ),
            ),
            const SizedBox(height: 24),

            // EPG section
            Text(
              'EPG / Programme Guide',
              style: TextStyle(
                  color: _accentColor,
                  fontSize: 16,
                  fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),

            if (_loadingEpg)
              const Center(
                  child: CircularProgressIndicator(color: _primaryColor))
            else if (epgListings.isEmpty)
              const Text('No EPG data available',
                  style: TextStyle(color: _secondaryTextColor))
            else
              ...epgListings.take(5).map((prog) {
                final p = Map<String, dynamic>.from(prog as Map);
                final title = _decodeEpgTitle(p['title']?.toString() ?? '');
                final start = p['start']?.toString() ?? '';
                final end = p['end']?.toString() ?? '';
                final isNow = p['now_playing'] == 1 ||
                    p['now_playing'] == true ||
                    p['now_playing']?.toString() == '1';
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: _surfaceColor,
                    borderRadius: BorderRadius.circular(6),
                    border: isNow
                        ? Border.all(color: _liveColor, width: 1.5)
                        : null,
                  ),
                  child: Row(
                    children: [
                      if (isNow) ...[
                        const Text('🔴',
                            style: TextStyle(fontSize: 12)),
                        const SizedBox(width: 6),
                      ],
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(title,
                                style: TextStyle(
                                    color: isNow ? _liveColor : Colors.white,
                                    fontWeight: isNow
                                        ? FontWeight.bold
                                        : FontWeight.normal)),
                            if (start.isNotEmpty)
                              Text('$start – $end',
                                  style: const TextStyle(
                                      color: _secondaryTextColor,
                                      fontSize: 12)),
                          ],
                        ),
                      ),
                    ],
                  ),
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

  /// EPG titles are sometimes base64-encoded.
  String _decodeEpgTitle(String raw) {
    try {
      // Try base64 decode
      final bytes = Uri.decodeComponent(raw);
      return bytes;
    } catch (_) {
      return raw;
    }
  }
}
