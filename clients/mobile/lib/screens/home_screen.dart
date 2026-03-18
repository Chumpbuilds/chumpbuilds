import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/license_service.dart';
import '../services/xtream_service.dart';
import '../utils/orientation_page.dart';
import 'favorites_screen.dart';
import 'license_screen.dart';
import 'live_tv_screen.dart';
import 'login_screen.dart';
import 'movies_screen.dart';
import 'search_screen.dart';
import 'series_screen.dart';

/// Card-based home page mirroring the Windows desktop app layout.
///
/// Shows gradient cards for Live TV, Movies, Series, Search, and Favorites.
/// Navigation is stack-based (Navigator.push) rather than tab-based.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // ─── Theme ────────────────────────────────────────────────────────────────
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _descColor = Color(0xFFB0B0B0);

  // ─── Card definitions (matching Windows gradient colors) ─────────────────
  static const _cards = [
    _CardDef(
      label: 'Live TV',
      emoji: '📺',
      color1: Color(0xFF667eea),
      color2: Color(0xFF764ba2),
      tag: 'live_tv',
    ),
    _CardDef(
      label: 'Movies',
      emoji: '🎬',
      color1: Color(0xFFf093fb),
      color2: Color(0xFFf5576c),
      tag: 'movies',
    ),
    _CardDef(
      label: 'Series',
      emoji: '📼',
      color1: Color(0xFF4facfe),
      color2: Color(0xFF00f2fe),
      tag: 'series',
    ),
    _CardDef(
      label: 'Search',
      emoji: '🔍',
      color1: Color(0xFF43e97b),
      color2: Color(0xFF38f9d7),
      tag: 'search',
    ),
    _CardDef(
      label: 'Favorites',
      emoji: '⭐',
      color1: Color(0xFFfa709a),
      color2: Color(0xFFfee140),
      tag: 'favorites',
    ),
  ];

  // ─── Lifecycle ────────────────────────────────────────────────────────────

  @override
  void initState() {
    super.initState();
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.landscapeLeft,
      DeviceOrientation.landscapeRight,
    ]);
  }

  @override
  void dispose() {
    SystemChrome.setPreferredOrientations([
      DeviceOrientation.portraitUp,
      DeviceOrientation.portraitDown,
    ]);
    super.dispose();
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  void _navigate(BuildContext context, String tag) {
    Widget screen;
    switch (tag) {
      case 'live_tv':
        screen = const LiveTvScreen();
        break;
      case 'movies':
        screen = const MoviesScreen();
        break;
      case 'series':
        screen = const SeriesScreen();
        break;
      case 'search':
        screen = const SearchScreen();
        break;
      case 'favorites':
        screen = const FavoritesScreen();
        break;
      default:
        return;
    }
    final isLandscapeSection =
        tag == 'live_tv' || tag == 'movies' || tag == 'series';

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => isLandscapeSection
            ? OrientationPage(child: screen)
            : screen,
      ),
    );
  }

  void _openSettings(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const _SettingsScreen()),
    );
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    // enabled_features comes from the server as a Map<String, bool>
    final rawFeatures = LicenseService().getAppCustomizations()['enabled_features'];
    final List<String> enabledFeatures;
    if (rawFeatures is Map) {
      enabledFeatures = rawFeatures.entries
          .where((e) => e.value == true)
          .map((e) => e.key.toString())
          .toList();
    } else if (rawFeatures is List) {
      enabledFeatures = rawFeatures.cast<String>();
    } else {
      enabledFeatures = ['live_tv', 'movies', 'series', 'search', 'favorites'];
    }

    // Filter cards by enabled features.
    final visibleCards = _cards
        .where((c) => enabledFeatures.contains(c.tag))
        .toList();

    // First row: up to 3 cards, second row: remainder.
    final row1 = visibleCards.take(3).toList();
    final row2 = visibleCards.skip(3).toList();

    return Scaffold(
      backgroundColor: _bgColor,
      body: SafeArea(
        child: Column(
          children: [
            // ── Top bar: icon buttons (top-right only) ────────────────────
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  IconButton(
                    icon: const Icon(Icons.account_circle, color: Colors.white),
                    iconSize: 28,
                    onPressed: () => _openSettings(context),
                  ),
                  IconButton(
                    icon: const Icon(Icons.settings, color: Colors.white),
                    iconSize: 28,
                    onPressed: () => _openSettings(context),
                  ),
                ],
              ),
            ),

            // ── Card grid ─────────────────────────────────────────────────
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Column(
                  children: [
                    if (row1.isNotEmpty)
                      Row(
                        children: row1
                            .map(
                              (c) => Expanded(
                                child: Padding(
                                  padding: const EdgeInsets.all(6),
                                  child: _GradientCard(
                                    card: c,
                                    onTap: () => _navigate(context, c.tag),
                                  ),
                                ),
                              ),
                            )
                            .toList(),
                      ),
                    const SizedBox(height: 4),
                    if (row2.isNotEmpty)
                      Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: row2
                            .map(
                              (c) => SizedBox(
                                width: (MediaQuery.of(context).size.width - 32) / 3,
                                child: Padding(
                                  padding: const EdgeInsets.all(6),
                                  child: _GradientCard(
                                    card: c,
                                    onTap: () => _navigate(context, c.tag),
                                  ),
                                ),
                              ),
                            )
                            .toList(),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Card definition data class ───────────────────────────────────────────────

class _CardDef {
  const _CardDef({
    required this.label,
    required this.emoji,
    required this.color1,
    required this.color2,
    required this.tag,
  });

  final String label;
  final String emoji;
  final Color color1;
  final Color color2;
  final String tag;
}

// ─── Gradient card widget ─────────────────────────────────────────────────────

class _GradientCard extends StatelessWidget {
  const _GradientCard({
    required this.card,
    required this.onTap,
  });

  final _CardDef card;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 120,
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [card.color1, card.color2],
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: card.color1.withAlpha(102),
              blurRadius: 12,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(card.emoji,
                style: const TextStyle(fontSize: 36)),
            const SizedBox(height: 8),
            Text(
              card.label,
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

// ─── Settings screen ──────────────────────────────────────────────────────────

class _SettingsScreen extends StatelessWidget {
  const _SettingsScreen();

  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _descColor = Color(0xFFB0B0B0);

  String _formatExpiry(dynamic expDate) {
    if (expDate == null) return 'N/A';
    try {
      final ts = int.parse(expDate.toString());
      final dt = DateTime.fromMillisecondsSinceEpoch(ts * 1000);
      return '${dt.year}-'
          '${dt.month.toString().padLeft(2, '0')}-'
          '${dt.day.toString().padLeft(2, '0')}';
    } catch (_) {
      return expDate.toString();
    }
  }

  @override
  Widget build(BuildContext context) {
    final customizations = LicenseService().getAppCustomizations();
    final appName = customizations['app_name'] as String? ?? 'X87 Player';

    final xtream = XtreamService();
    final userInfo = xtream.userInfo ?? {};
    final xtreamUsername =
        userInfo['username'] as String? ?? xtream.username ?? '';
    final accountStatus = userInfo['status'] as String? ?? 'Unknown';
    final expDate = _formatExpiry(userInfo['exp_date']);
    final profileName = xtream.profileName ?? '';

    return Scaffold(
      backgroundColor: _bgColor,
      appBar: AppBar(
        title: Text(appName),
        centerTitle: true,
        backgroundColor: _bgColor,
        foregroundColor: Colors.white,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(Icons.settings, size: 72, color: _primaryColor),
              const SizedBox(height: 16),
              const Text(
                'Settings',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                  color: Colors.white,
                ),
              ),
              const SizedBox(height: 24),

              // Account info card
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: _surfaceColor,
                  border: Border.all(color: _borderColor),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Column(
                  children: [
                    _infoRow('Username', xtreamUsername),
                    const SizedBox(height: 8),
                    if (profileName.isNotEmpty) ...[
                      _infoRow('Profile', profileName),
                      const SizedBox(height: 8),
                    ],
                    _infoRow('Status', accountStatus,
                        valueColor: accountStatus.toLowerCase() == 'active'
                            ? _primaryColor
                            : Colors.orange),
                    const SizedBox(height: 8),
                    _infoRow('Expires', expDate),
                  ],
                ),
              ),
              const SizedBox(height: 32),

              // Switch Profile
              OutlinedButton.icon(
                onPressed: () => Navigator.of(context).pushReplacement(
                  MaterialPageRoute(builder: (_) => const LoginScreen()),
                ),
                icon: const Icon(Icons.swap_horiz),
                label: const Text('Switch Profile'),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: _borderColor),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
              const SizedBox(height: 12),

              // Deactivate License
              OutlinedButton.icon(
                onPressed: () async {
                  await LicenseService().clearStoredLicense();
                  XtreamService().logout();
                  if (context.mounted) {
                    Navigator.of(context).pushReplacement(
                      MaterialPageRoute(
                          builder: (_) => const LicenseScreen()),
                    );
                  }
                },
                icon: const Icon(Icons.logout, color: Colors.redAccent),
                label: const Text('Deactivate License',
                    style: TextStyle(color: Colors.redAccent)),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.redAccent,
                  side: const BorderSide(color: Colors.redAccent),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _infoRow(String label, String value, {Color? valueColor}) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 80,
          child: Text(
            '$label:',
            style: const TextStyle(fontSize: 13, color: _descColor),
          ),
        ),
        Expanded(
          child: Text(
            value,
            style: TextStyle(
              fontSize: 13,
              color: valueColor ?? Colors.white,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
      ],
    );
  }
}
