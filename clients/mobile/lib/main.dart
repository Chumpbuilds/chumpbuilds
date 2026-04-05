import 'dart:convert';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'screens/home_screen.dart';
import 'screens/license_screen.dart';
import 'screens/login_screen.dart';
import 'services/epg_service.dart';
import 'services/license_service.dart';
import 'services/xtream_cache_service.dart';
import 'services/xtream_service.dart';
import 'widgets/system_ui_wrapper.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock the entire app to landscape.
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  // Hide system bars globally on startup.
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersive);

  // Ensure the status bar and navigation bar are solid black when briefly visible.
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
    statusBarColor: Colors.black,
    statusBarIconBrightness: Brightness.light,
    systemNavigationBarColor: Colors.black,
    systemNavigationBarIconBrightness: Brightness.light,
  ));

  // Read cached branding from SharedPreferences (fast disk read, no network).
  // This ensures the bootstrap screen shows the portal-configured name and
  // logo before any network call is made.
  String cachedAppName = 'X87 Player';
  String cachedLogoUrl = '';
  try {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString('user_settings');
    if (raw != null && raw.isNotEmpty) {
      final settings = jsonDecode(raw) as Map<String, dynamic>;
      cachedAppName = settings['app_name'] as String? ?? 'X87 Player';
      cachedLogoUrl = settings['logo_url'] as String? ?? '';
    }
  } catch (_) {
    // Silently fall back to defaults — branding is cosmetic and must never
    // prevent the app from launching.
  }

  // Show the app immediately — async init runs inside _BootstrapScreen.
  runApp(X87App(appName: cachedAppName, logoUrl: cachedLogoUrl));
}

/// Attempt to auto-login using the last-used cloud profile's saved credentials.
///
/// Returns `true` if login succeeds, `false` otherwise.
Future<bool> _tryAutoLogin() async {
  final profiles = LicenseService().getCloudProfiles();
  if (profiles.isEmpty) return false;

  try {
    final prefs = await SharedPreferences.getInstance();
    final lastProfile = prefs.getString('last_used_profile');

    // Find the profile to use (last-used or first available).
    Map<String, dynamic>? profile;
    if (lastProfile != null) {
      for (final p in profiles) {
        if ((p as Map)['name'] == lastProfile) {
          profile = Map<String, dynamic>.from(p);
          break;
        }
      }
    }
    profile ??= Map<String, dynamic>.from(profiles[0] as Map);

    final profileName = profile['name'] as String? ?? '';
    final url = profile['url'] as String? ?? '';
    if (url.isEmpty) return false;

    // Load saved credentials for this profile.
    final credsKey = 'cloud_creds_$profileName';
    final credsRaw = prefs.getString(credsKey);
    if (credsRaw == null || credsRaw.isEmpty) return false;

    final creds = jsonDecode(credsRaw) as Map<String, dynamic>;
    final username = creds['username'] as String? ?? '';
    final password = creds['password'] as String? ?? '';
    if (username.isEmpty || password.isEmpty) return false;

    final xtream = XtreamService();
    final result = await xtream.login(url, username, password);
    if (result['success'] == true) {
      xtream.profileName = profileName;
      return true;
    }
    return false;
  } catch (e) {
    debugPrint('[main] Auto-login error: $e');
    return false;
  }
}

/// Root application widget. Wraps everything in a [MaterialApp] with the
/// app's dark theme. [home] defaults to [_BootstrapScreen], which performs
/// all async initialization and navigates to the correct screen when done.
class X87App extends StatelessWidget {
  const X87App({
    super.key,
    this.appName = 'X87 Player',
    this.logoUrl = '',
    this.home,
  });

  /// Portal-configured app name read from cached SharedPreferences.
  final String appName;

  /// Portal-configured logo URL read from cached SharedPreferences.
  final String logoUrl;

  /// Override the initial screen. Defaults to [_BootstrapScreen].
  final Widget? home;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'X87 Player',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF0D7377),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF1E1E1E),
      ),
      home: home ?? _BootstrapScreen(appName: appName, logoUrl: logoUrl),
    );
  }
}

/// Splash / bootstrap screen shown immediately on launch while async
/// initialization (license validation, auto-login, cache check) runs.
///
/// Displays the portal-configured app name and logo so the user sees branded
/// content instantly rather than a blank white screen.
class _BootstrapScreen extends StatefulWidget {
  const _BootstrapScreen({required this.appName, required this.logoUrl});

  /// Portal-configured app name (e.g. "My IPTV App").
  final String appName;

  /// Portal-configured logo URL. If empty, a default icon is shown instead.
  final String logoUrl;

  @override
  State<_BootstrapScreen> createState() => _BootstrapScreenState();
}

class _BootstrapScreenState extends State<_BootstrapScreen> {
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _descColor = Color(0xFFB0B0B0);

  bool _showProgress = false;
  int _completed = 0;
  int _total = 4;
  String _currentLabel = '';

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    try {
      // 1. Silently validate any stored licence.
      final isValid = await LicenseService().validateLicense();

      if (!isValid) {
        // No valid licence — navigate immediately.
        if (!mounted) return;
        Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const LicenseScreen()),
        );
        return;
      }

      // 2. Licence is valid — run auto-login, cache freshness check, and EPG
      // disk load concurrently; they are all independent of each other.
      final results = await Future.wait<dynamic>([
        _tryAutoLogin(),
        XtreamCacheService().isCacheFresh(minRemainingHours: 20),
        EpgService().loadFromCache(),
      ]);
      final autoLoggedIn = results[0] as bool;
      final cacheFresh = results[1] as bool;

      if (!autoLoggedIn) {
        if (!mounted) return;
        Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
        );
        return;
      }

      // 3. Cache freshness check — EPG is already loaded from the parallel
      // call above, so navigate directly if cache is still fresh.
      if (cacheFresh) {
        if (!mounted) return;
        Navigator.of(context).pushReplacement(
          MaterialPageRoute<void>(builder: (_) => const HomeScreen()),
        );
        return;
      }

      // 4. Cache is stale — show progress bar and run a parallel prefetch inline
      // (no separate LoadingScreen needed).
      if (!mounted) return;
      setState(() {
        _showProgress = true;
        _currentLabel = 'Loading content…';
      });

      final xtream = XtreamService();
      final cache = XtreamCacheService();

      // Defer disk writes so we do a single fsync at the end instead of one
      // after every API response (saves ~3-4 s on cold start).
      cache.setDeferPersistence(defer: true);

      // Run all 4 groups in parallel — they are fully independent.
      // `groupsDone` is incremented in the setState callbacks of each group.
      // Dart's event loop is single-threaded so concurrent increments from
      // different futures are safe (no two microtasks run simultaneously).
      int groupsDone = 0;
      await Future.wait([
        // Group 1: Live TV (categories + streams in parallel)
        () async {
          try {
            await Future.wait([
              xtream.getLiveCategories(),
              xtream.getLiveStreams(null),
            ]);
          } catch (e) {
            debugPrint('[BootstrapScreen] Live TV group error: $e');
          }
          if (mounted) setState(() => _completed = ++groupsDone);
        }(),
        // Group 2: Movies (categories + streams in parallel)
        () async {
          try {
            await Future.wait([
              xtream.getVodCategories(),
              xtream.getVodStreams(null),
            ]);
          } catch (e) {
            debugPrint('[BootstrapScreen] Movies group error: $e');
          }
          if (mounted) setState(() => _completed = ++groupsDone);
        }(),
        // Group 3: Series (categories + streams in parallel)
        () async {
          try {
            await Future.wait([
              xtream.getSeriesCategories(),
              xtream.getSeries(null),
            ]);
          } catch (e) {
            debugPrint('[BootstrapScreen] Series group error: $e');
          }
          if (mounted) setState(() => _completed = ++groupsDone);
        }(),
        // Group 4: EPG (independent, runs alongside everything else)
        () async {
          try {
            await EpgService().downloadAndCacheEpg(
              xtream.baseUrl!,
              xtream.username!,
              xtream.password!,
            );
          } catch (e) {
            debugPrint('[BootstrapScreen] EPG group error: $e');
          }
          if (mounted) setState(() => _completed = ++groupsDone);
        }(),
      ]);

      // Re-enable normal persistence and flush all deferred entries in one write.
      cache.setDeferPersistence(defer: false);
      await cache.flushToStorage();

      if (!mounted) return;
      setState(() {
        _completed = _total;
        _currentLabel = 'Done!';
      });

      await Future<void>.delayed(const Duration(milliseconds: 300));
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => const HomeScreen()),
      );
    } catch (e) {
      debugPrint('[BootstrapScreen] init error: $e');
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => const LicenseScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final progress = _total > 0 ? _completed / _total : 0.0;
    return SystemUiWrapper(
      child: Scaffold(
        backgroundColor: _bgColor,
        resizeToAvoidBottomInset: false,
        body: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 40),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Show portal logo if available, otherwise fall back to the
                    // default teal TV icon.
                    if (widget.logoUrl.isNotEmpty)
                      ClipRRect(
                        borderRadius: BorderRadius.circular(20),
                        child: CachedNetworkImage(
                          imageUrl: widget.logoUrl,
                          width: 80,
                          height: 80,
                          fit: BoxFit.cover,
                          placeholder: (_, __) => _defaultIcon(),
                          errorWidget: (_, __, ___) => _defaultIcon(),
                        ),
                      )
                    else
                      _defaultIcon(),
                    const SizedBox(height: 20),

                    // Portal app name with "Welcome to" prefix.
                    Text(
                      'Welcome to ${widget.appName}',
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        letterSpacing: 0.5,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 12),

                    // "Loading..." text replaces the circular spinner.
                    const Text(
                      'Loading...',
                      style: TextStyle(
                        fontSize: 14,
                        color: _descColor,
                      ),
                    ),

                    // Progress section — animates in only when cache is stale.
                    AnimatedSize(
                      duration: const Duration(milliseconds: 300),
                      child: _showProgress
                          ? Column(
                              children: [
                                const SizedBox(height: 32),
                                ClipRRect(
                                  borderRadius: BorderRadius.circular(4),
                                  child: LinearProgressIndicator(
                                    value: progress,
                                    minHeight: 6,
                                    backgroundColor: _surfaceColor,
                                    valueColor:
                                        const AlwaysStoppedAnimation<Color>(
                                      _primaryColor,
                                    ),
                                  ),
                                ),
                                const SizedBox(height: 16),
                                Row(
                                  mainAxisAlignment:
                                      MainAxisAlignment.spaceBetween,
                                  children: [
                                    Expanded(
                                      child: Text(
                                        _currentLabel,
                                        style: const TextStyle(
                                          fontSize: 12,
                                          color: _descColor,
                                        ),
                                        overflow: TextOverflow.ellipsis,
                                      ),
                                    ),
                                    Text(
                                      '$_completed / $_total',
                                      style: const TextStyle(
                                        fontSize: 12,
                                        color: _descColor,
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            )
                          : const SizedBox.shrink(),
                    ),
                  ],
                ),
              ),
            ),
        ),
      ),
    );
  }

  Widget _defaultIcon() {
    return Container(
      width: 80,
      height: 80,
      decoration: BoxDecoration(
        color: _primaryColor,
        borderRadius: BorderRadius.circular(20),
      ),
      child: const Icon(
        Icons.tv,
        size: 48,
        color: Colors.white,
      ),
    );
  }
}
