import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/xtream_service.dart';

/// Global search screen — searches Live TV, Movies, and Series simultaneously.
///
/// Ported from `clients/windows/ui/global_search.py` (ModernGlobalSearch).
class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  // ─── Theme ────────────────────────────────────────────────────────────────
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _liveTvColor = Color(0xFF8b9cff);
  static const Color _moviesColor = Color(0xFFff9eff);
  static const Color _seriesColor = Color(0xFF64d4ff);

  // ─── State ────────────────────────────────────────────────────────────────
  final _xtream = XtreamService();
  final _searchCtrl = TextEditingController();

  List<Map<String, dynamic>> _liveResults = [];
  List<Map<String, dynamic>> _movieResults = [];
  List<Map<String, dynamic>> _seriesResults = [];

  bool _loading = false;
  bool _hasSearched = false;

  @override
  void initState() {
    super.initState();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  // ─── Search ───────────────────────────────────────────────────────────────

  Future<void> _search(String query) async {
    final q = query.trim().toLowerCase();
    if (q.isEmpty) return;

    setState(() {
      _loading = true;
      _hasSearched = true;
    });

    try {
      final results = await Future.wait([
        _xtream.getLiveStreams(null),
        _xtream.getVodStreams(null),
        _xtream.getSeries(null),
      ]);

      setState(() {
        _liveResults = (results[0] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .where((e) =>
                (e['name'] as String? ?? '').toLowerCase().contains(q))
            .toList();
        _movieResults = (results[1] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .where((e) =>
                (e['name'] as String? ?? '').toLowerCase().contains(q))
            .toList();
        _seriesResults = (results[2] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .where((e) =>
                (e['name'] as String? ?? '').toLowerCase().contains(q))
            .toList();
        _loading = false;
      });
    } catch (e) {
      debugPrint('[SearchScreen] search error: $e');
      setState(() => _loading = false);
    }
  }

  Future<void> _play(Map<String, dynamic> item, String type) async {
    final id = item['stream_id']?.toString() ?? '';
    final url = _xtream.getStreamUrl(id, type, streamData: item);
    if (url.isNotEmpty) {
      final uri = Uri.parse(url);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      }
    }
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: const Text('Search', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        toolbarHeight: 36,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, size: 18),
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: Column(
        children: [
          // Search bar
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              controller: _searchCtrl,
              autofocus: true,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Search Live TV, Movies, Series…',
                hintStyle:
                    const TextStyle(color: Color(0xFF95A5A6)),
                prefixIcon: const Icon(Icons.search,
                    color: Color(0xFF95A5A6)),
                suffixIcon: _searchCtrl.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear,
                            color: Color(0xFF95A5A6)),
                        onPressed: () {
                          _searchCtrl.clear();
                          setState(() {
                            _liveResults = [];
                            _movieResults = [];
                            _seriesResults = [];
                            _hasSearched = false;
                          });
                        },
                      )
                    : null,
                filled: true,
                fillColor: _surfaceColor,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: _borderColor),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(color: _borderColor),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                  borderSide: const BorderSide(
                      color: Color(0xFF3498DB), width: 2),
                ),
              ),
              onChanged: (v) => setState(() {}),
              onSubmitted: _search,
              textInputAction: TextInputAction.search,
            ),
          ),

          // Results
          Expanded(
            child: _loading
                ? const Center(
                    child: CircularProgressIndicator(
                      color: Color(0xFF3498DB),
                    ),
                  )
                : !_hasSearched
                    ? _buildEmptyPrompt()
                    : _buildResults(),
          ),
        ],
      ),
    );
  }

  Widget _buildEmptyPrompt() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: const [
          Text('🔍', style: TextStyle(fontSize: 64)),
          SizedBox(height: 16),
          Text(
            'Search across Live TV, Movies and Series',
            style: TextStyle(color: Color(0xFF95A5A6), fontSize: 16),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildResults() {
    final total =
        _liveResults.length + _movieResults.length + _seriesResults.length;
    if (total == 0) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text('😕', style: TextStyle(fontSize: 64)),
            const SizedBox(height: 16),
            Text(
              'No results for "${_searchCtrl.text}"',
              style: const TextStyle(
                  color: Color(0xFF95A5A6), fontSize: 16),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      children: [
        if (_liveResults.isNotEmpty)
          _buildSection(
            icon: '📺',
            label: 'LIVE TV',
            color: _liveTvColor,
            items: _liveResults,
            type: 'live',
          ),
        if (_movieResults.isNotEmpty)
          _buildSection(
            icon: '🎬',
            label: 'MOVIES',
            color: _moviesColor,
            items: _movieResults,
            type: 'movie',
          ),
        if (_seriesResults.isNotEmpty)
          _buildSection(
            icon: '📼',
            label: 'SERIES',
            color: _seriesColor,
            items: _seriesResults,
            type: 'series',
          ),
      ],
    );
  }

  Widget _buildSection({
    required String icon,
    required String label,
    required Color color,
    required List<Map<String, dynamic>> items,
    required String type,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Section header
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Row(
            children: [
              Text(icon, style: const TextStyle(fontSize: 20)),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  color: color,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.2,
                ),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withAlpha(51),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  '${items.length}',
                  style: TextStyle(
                    color: color,
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
        ),
        // Items
        ...items.map((item) => _buildResultTile(item, type, color)),
        const SizedBox(height: 8),
      ],
    );
  }

  Widget _buildResultTile(
      Map<String, dynamic> item, String type, Color color) {
    final name = item['name'] as String? ?? '';
    final iconUrl = (item['stream_icon'] as String?) ??
        (item['cover'] as String?) ??
        '';
    final isSeries = type == 'series';

    return Card(
      color: _surfaceColor,
      margin: const EdgeInsets.only(bottom: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: BorderSide(color: _borderColor),
      ),
      child: ListTile(
        leading: iconUrl.isNotEmpty
            ? ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: CachedNetworkImage(
                  imageUrl: iconUrl,
                  width: 48,
                  height: 48,
                  fit: BoxFit.cover,
                  errorWidget: (_, __, ___) => Container(
                    width: 48,
                    height: 48,
                    color: color.withAlpha(51),
                    child: Text(
                      type == 'live'
                          ? '📺'
                          : type == 'movie'
                              ? '🎬'
                              : '📼',
                      style: const TextStyle(fontSize: 22),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
              )
            : Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: color.withAlpha(51),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(
                  type == 'live'
                      ? '📺'
                      : type == 'movie'
                          ? '🎬'
                          : '📼',
                  style: const TextStyle(fontSize: 22),
                  textAlign: TextAlign.center,
                ),
              ),
        title: Text(
          name,
          style: const TextStyle(color: Colors.white, fontSize: 14),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: isSeries
            ? null
            : IconButton(
                icon: const Icon(Icons.play_circle_fill,
                    color: Color(0xFF3498DB)),
                onPressed: () => _play(item, type),
              ),
        onTap: isSeries ? null : () => _play(item, type),
      ),
    );
  }
}
