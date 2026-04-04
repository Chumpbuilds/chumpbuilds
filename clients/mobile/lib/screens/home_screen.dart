import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/license_service.dart';
import '../services/xtream_cache_service.dart';
import '../services/xtream_service.dart';
import '../widgets/tv_text_field.dart';
import '../widgets/system_ui_wrapper.dart';
import 'favorites_screen.dart';
import 'license_screen.dart';
import 'live_tv_screen.dart';
import 'loading_screen.dart';
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
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
  }

  @override
  void dispose() {
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    super.dispose();
  }

  // ─── Helpers ──────────────────────────────────────────────────────────────

  String _formatExpiry(dynamic expDate) {
    if (expDate == null) return 'N/A';
    try {
      final ts = int.parse(expDate.toString());
      final dt = DateTime.fromMillisecondsSinceEpoch(ts * 1000);
      return '${dt.day.toString().padLeft(2, '0')}-'
          '${dt.month.toString().padLeft(2, '0')}-'
          '${dt.year}';
    } catch (_) {
      return 'N/A';
    }
  }

  Future<void> _navigate(BuildContext context, String tag) async {
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

    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => screen),
    );
    // Small delay to ensure child's dispose() async work completes
    // before re-applying immersive mode.
    await Future.delayed(const Duration(milliseconds: 100));
    if (mounted) {
      SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    }
  }

  Future<void> _openSettings(BuildContext context) async {
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const _SettingsScreen()),
    );
    await Future.delayed(const Duration(milliseconds: 100));
    if (mounted) {
      SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    }
  }

  Future<void> _showSwitchProfileDialog(BuildContext context) async {
    final profiles = LicenseService().getCloudProfiles();
    if (profiles.isEmpty) return;

    await showDialog<void>(
      context: context,
      barrierDismissible: true,
      builder: (dialogContext) => _SwitchProfileDialog(
        profiles: profiles,
        parentContext: context,
      ),
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

    final xtream = XtreamService();
    final userInfo = xtream.userInfo ?? {};
    final username =
        userInfo['username'] as String? ?? xtream.username ?? '';
    final expiry = _formatExpiry(userInfo['exp_date']);

    final customizations = LicenseService().getAppCustomizations();
    final appName = customizations['app_name'] as String? ?? 'X87 Player';
    final profileName =
        (xtream.profileName?.isNotEmpty ?? false) ? xtream.profileName! : appName;

    return SystemUiWrapper(child: Scaffold(
      backgroundColor: _bgColor,
      body: SafeArea(
        bottom: false,
        child: Column(
          children: [
            // ── Top bar: user info (left) + icon buttons (right) ──────────
            SizedBox(
              height: 32,
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 8),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    // Left side: username and expiry date
                    Text(
                      '👤 $username  |  📅 Exp: $expiry',
                      style: const TextStyle(
                        fontSize: 11,
                        color: _descColor,
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                    // Right side: icon buttons
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          icon: const Icon(Icons.account_circle,
                              color: Colors.white),
                          iconSize: 20,
                          constraints: const BoxConstraints(),
                          padding: EdgeInsets.zero,
                          onPressed: () => _showSwitchProfileDialog(context),
                        ),
                        const SizedBox(width: 8),
                        IconButton(
                          icon: const Icon(Icons.settings, color: Colors.white),
                          iconSize: 20,
                          constraints: const BoxConstraints(),
                          padding: EdgeInsets.zero,
                          onPressed: () => _openSettings(context),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            // ── Card grid ─────────────────────────────────────────────────
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final availableHeight = constraints.maxHeight;
                  // Scale card height proportionally; clamp so cards never
                  // become too tiny on very small screens or too tall on
                  // large tablets.
                  final cardHeight =
                      (availableHeight * 0.28).clamp(72.0, 130.0);
                  final welcomeFontSize = availableHeight < 350 ? 13.0 : 16.0;
                  final welcomeBoldFontSize =
                      availableHeight < 350 ? 15.0 : 18.0;

                  return SizedBox(
                    height: availableHeight,
                    child: Padding(
                      padding:
                          const EdgeInsets.symmetric(horizontal: 16),
                      child: Column(
                        children: [
                          const Spacer(),
                          if (row1.isNotEmpty)
                            Row(
                              children: row1
                                  .asMap()
                                  .entries
                                  .map(
                                    (entry) => Expanded(
                                      child: Padding(
                                        padding:
                                            const EdgeInsets.all(6),
                                        child: _GradientCard(
                                          card: entry.value,
                                          height: cardHeight,
                                          autofocus: entry.key == 0,
                                          onTap: () => _navigate(
                                              context, entry.value.tag),
                                        ),
                                      ),
                                    ),
                                  )
                                  .toList(),
                            ),
                          const Spacer(),
                          if (row2.isNotEmpty)
                            Row(
                              mainAxisAlignment:
                                  MainAxisAlignment.center,
                              children: row2
                                  .map(
                                    (c) => SizedBox(
                                      width:
                                          (MediaQuery.of(context)
                                                      .size
                                                      .width -
                                                  32) /
                                              3,
                                      child: Padding(
                                        padding:
                                            const EdgeInsets.all(6),
                                        child: _GradientCard(
                                          card: c,
                                          height: cardHeight,
                                          onTap: () => _navigate(
                                              context, c.tag),
                                        ),
                                      ),
                                    ),
                                  )
                                  .toList(),
                            ),
                          // ── Welcome message ──────────────────────
                          const Spacer(),
                          Text.rich(
                            TextSpan(
                              children: [
                                TextSpan(
                                  text: 'Welcome to ',
                                  style: GoogleFonts.dancingScript(
                                    color: _descColor,
                                    fontSize: welcomeFontSize,
                                  ),
                                ),
                                TextSpan(
                                  text: '"$profileName"',
                                  style: GoogleFonts.dancingScript(
                                    color: Colors.white,
                                    fontSize: welcomeBoldFontSize,
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                            textAlign: TextAlign.center,
                          ),
                          const Spacer(),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    ));
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

class _GradientCard extends StatefulWidget {
  const _GradientCard({
    required this.card,
    required this.onTap,
    this.height = 120,
    this.autofocus = false,
  });

  final _CardDef card;
  final VoidCallback onTap;
  final double height;
  final bool autofocus;

  @override
  State<_GradientCard> createState() => _GradientCardState();
}

class _GradientCardState extends State<_GradientCard> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    return Focus(
      autofocus: widget.autofocus,
      onFocusChange: (hasFocus) => setState(() => _focused = hasFocus),
      onKeyEvent: (node, event) {
        if (event is KeyDownEvent &&
            (event.logicalKey == LogicalKeyboardKey.select ||
                event.logicalKey == LogicalKeyboardKey.enter ||
                event.logicalKey == LogicalKeyboardKey.gameButtonA)) {
          widget.onTap();
          return KeyEventResult.handled;
        }
        return KeyEventResult.ignored;
      },
      child: GestureDetector(
        onTap: widget.onTap,
        child: Transform.scale(
          scale: _focused ? 1.05 : 1.0,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            height: widget.height,
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [widget.card.color1, widget.card.color2],
              ),
              borderRadius: BorderRadius.circular(16),
              border: _focused
                  ? Border.all(color: Colors.white, width: 3)
                  : null,
              boxShadow: [
                BoxShadow(
                  color: widget.card.color1.withAlpha(102),
                  blurRadius: 12,
                  offset: const Offset(0, 6),
                ),
              ],
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(widget.card.emoji,
                    style: const TextStyle(fontSize: 36)),
                const SizedBox(height: 8),
                Text(
                  widget.card.label,
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
        ),
      ),
    );
  }
}

// ─── Switch Profile dialog ─────────────────────────────────────────────────────

class _SwitchProfileDialog extends StatefulWidget {
  const _SwitchProfileDialog({
    required this.profiles,
    required this.parentContext,
  });

  final List<dynamic> profiles;
  final BuildContext parentContext;

  @override
  State<_SwitchProfileDialog> createState() => _SwitchProfileDialogState();
}

class _SwitchProfileDialogState extends State<_SwitchProfileDialog> {
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _descColor = Color(0xFFB0B0B0);

  int _selectedIndex = 0;
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isLoading = false;
  String _statusMessage = '';
  bool _isError = false;

  String _credsKey(String profileName) => 'cloud_creds_$profileName';

  @override
  void initState() {
    super.initState();
    if (widget.profiles.isNotEmpty) {
      final name = widget.profiles[0]['name'] as String? ?? '';
      _loadSavedCredentials(name);
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _loadSavedCredentials(String profileName) async {
    if (profileName.isEmpty) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getString(_credsKey(profileName)) ?? '{}';
      final creds = jsonDecode(raw) as Map<String, dynamic>;
      if (mounted) {
        _usernameController.text = creds['username'] as String? ?? '';
        _passwordController.text = creds['password'] as String? ?? '';
      }
    } catch (e) {
      debugPrint('[SwitchProfile] Error loading credentials: $e');
    }
  }

  void _onProfileChanged(int index) {
    setState(() {
      _selectedIndex = index;
      _statusMessage = '';
    });
    final name = widget.profiles[index]['name'] as String? ?? '';
    _loadSavedCredentials(name);
  }

  void _showStatus(String message, {required bool isError}) {
    if (mounted) {
      setState(() {
        _statusMessage = message;
        _isError = isError;
      });
    }
  }

  Future<void> _switchProfile() async {
    final profile = widget.profiles[_selectedIndex] as Map;
    final url = profile['url'] as String? ?? '';
    final profileName = profile['name'] as String? ?? '';
    final username = _usernameController.text.trim();
    final password = _passwordController.text.trim();

    if (username.isEmpty || password.isEmpty) {
      _showStatus('Please fill in all required fields', isError: true);
      return;
    }

    if (url.isEmpty) {
      _showStatus('No server URL available for the selected profile',
          isError: true);
      return;
    }

    setState(() => _isLoading = true);
    _showStatus('Connecting to server...', isError: false);

    final xtream = XtreamService();
    final result = await xtream.login(url, username, password);

    if (!mounted) return;
    setState(() => _isLoading = false);

    if (result['success'] == true) {
      xtream.profileName = profileName;

      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _credsKey(profileName),
        jsonEncode({'username': username, 'password': password}),
      );
      await prefs.setString('last_used_profile', profileName);

      if (!mounted) return;
      Navigator.of(context).pop();
      Navigator.of(widget.parentContext).pushReplacement(
        MaterialPageRoute(builder: (_) => const LoadingScreen()),
      );
    } else {
      _showStatus(
        result['message'] as String? ?? 'Login failed.',
        isError: true,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final profiles = widget.profiles;
    final singleProfile = profiles.length == 1;

    return Dialog(
      backgroundColor: _surfaceColor,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: _borderColor),
      ),
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: 360,
          maxHeight: MediaQuery.of(context).size.height * 0.8,
        ),
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: SingleChildScrollView(
            child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Title
              Row(
                children: [
                  const Icon(Icons.swap_horiz, color: _primaryColor, size: 22),
                  const SizedBox(width: 8),
                  const Text(
                    'Switch Profile',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),

              // Profile selector
              if (singleProfile)
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                  decoration: BoxDecoration(
                    border: Border.all(color: _borderColor),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    profiles[0]['name'] as String? ?? '',
                    style: const TextStyle(color: Colors.white, fontSize: 13),
                  ),
                )
              else
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    border: Border.all(color: _borderColor),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<int>(
                      value: _selectedIndex,
                      isExpanded: true,
                      dropdownColor: _surfaceColor,
                      style: const TextStyle(color: Colors.white, fontSize: 13),
                      items: List.generate(
                        profiles.length,
                        (i) => DropdownMenuItem<int>(
                          value: i,
                          child: Text(
                              profiles[i]['name'] as String? ?? 'Profile $i'),
                        ),
                      ),
                      onChanged: (i) {
                        if (i != null) _onProfileChanged(i);
                      },
                    ),
                  ),
                ),
              const SizedBox(height: 12),

              // Username field
              TvTextField(
                controller: _usernameController,
                style: const TextStyle(color: Colors.white, fontSize: 13),
                decoration: InputDecoration(
                  labelText: 'Username',
                  labelStyle: const TextStyle(color: _descColor, fontSize: 12),
                  enabledBorder: OutlineInputBorder(
                    borderSide: const BorderSide(color: _borderColor),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderSide: const BorderSide(color: _primaryColor),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                ),
              ),
              const SizedBox(height: 12),

              // Password field
              TvTextField(
                controller: _passwordController,
                obscureText: true,
                style: const TextStyle(color: Colors.white, fontSize: 13),
                decoration: InputDecoration(
                  labelText: 'Password',
                  labelStyle: const TextStyle(color: _descColor, fontSize: 12),
                  enabledBorder: OutlineInputBorder(
                    borderSide: const BorderSide(color: _borderColor),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderSide: const BorderSide(color: _primaryColor),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                ),
              ),

              // Status message
              if (_statusMessage.isNotEmpty) ...[
                const SizedBox(height: 10),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  decoration: BoxDecoration(
                    color: _isError
                        ? const Color(0xFFDC3545).withAlpha(30)
                        : const Color(0xFF17A2B8).withAlpha(30),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: _isError
                          ? const Color(0xFFDC3545)
                          : const Color(0xFF17A2B8),
                    ),
                  ),
                  child: Text(
                    _statusMessage,
                    style: TextStyle(
                      fontSize: 12,
                      color: _isError
                          ? const Color(0xFFDC3545)
                          : const Color(0xFF17A2B8),
                    ),
                  ),
                ),
              ],
              const SizedBox(height: 20),

              // Buttons
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed:
                          _isLoading ? null : () => Navigator.of(context).pop(),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: Colors.white,
                        side: const BorderSide(color: _borderColor),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                      child: const Text('Cancel', style: TextStyle(fontSize: 13)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _isLoading ? null : _switchProfile,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _primaryColor,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 10),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                      child: _isLoading
                          ? const SizedBox(
                              height: 16,
                              width: 16,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text('Switch Profile',
                              style: TextStyle(fontSize: 13)),
                    ),
                  ),
                ],
              ),
            ],
          ),
          ),
        ),
      ),
    );
  }
}

// ─── Settings screen ──────────────────────────────────────────────────────────

class _SettingsScreen extends StatefulWidget {
  const _SettingsScreen();

  @override
  State<_SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<_SettingsScreen> {
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
        title: Text(appName, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        centerTitle: true,
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
      body: SafeArea(
        bottom: false,
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

              // Clear Cached Data
              OutlinedButton.icon(
                onPressed: () async {
                  await XtreamCacheService().clear();
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        content: Text('Cache cleared'),
                        duration: Duration(seconds: 2),
                      ),
                    );
                  }
                },
                icon: const Icon(Icons.delete_outline),
                label: const Text('Clear Cached Data'),
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

              // Refresh Data
              OutlinedButton.icon(
                onPressed: () async {
                  await XtreamCacheService().clear();
                  if (context.mounted) {
                    Navigator.of(context).pushAndRemoveUntil(
                      MaterialPageRoute(
                          builder: (_) => const LoadingScreen()),
                      (route) => false,
                    );
                  }
                },
                icon: const Icon(Icons.refresh),
                label: const Text('Refresh Data'),
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
