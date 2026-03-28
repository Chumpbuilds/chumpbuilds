import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'screens/home_screen.dart';
import 'screens/license_screen.dart';
import 'screens/loading_screen.dart';
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
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

  // Show the app immediately — async init runs inside _BootstrapScreen.
  runApp(const X87App());
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
  const X87App({super.key, this.home});

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
      home: home ?? const _BootstrapScreen(),
    );
  }
}

/// Splash / bootstrap screen shown immediately on launch while async
/// initialization (license validation, auto-login, cache check) runs.
///
/// Visual style matches [LoadingScreen] so the transition feels seamless.
class _BootstrapScreen extends StatefulWidget {
  const _BootstrapScreen();

  @override
  State<_BootstrapScreen> createState() => _BootstrapScreenState();
}

class _BootstrapScreenState extends State<_BootstrapScreen> {
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _primaryColor = Color(0xFF0D7377);

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    try {
      // 1. Silently validate any stored licence.
      final isValid = await LicenseService().validateLicense();

      Widget nextScreen;
      if (isValid) {
        // 2. Licence is valid — attempt silent IPTV auto-login with saved creds.
        final autoLoggedIn = await _tryAutoLogin();
        if (autoLoggedIn) {
          // Check if the core content cache has at least 20 hours remaining.
          final cacheFresh = await XtreamCacheService().isCacheFresh(
            minRemainingHours: 20,
          );
          if (cacheFresh) {
            // Load EPG data from cache so it's available without re-downloading.
            await EpgService().loadFromCache();
            nextScreen = const HomeScreen();
          } else {
            nextScreen = const LoadingScreen();
          }
        } else {
          nextScreen = const LoginScreen();
        }
      } else {
        // 3. No valid licence — show the activation screen.
        nextScreen = const LicenseScreen();
      }

      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(builder: (_) => nextScreen),
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
    return SystemUiWrapper(
      child: Scaffold(
        backgroundColor: _bgColor,
        body: SafeArea(
          child: Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // App icon / logo — matches LoadingScreen style.
                Container(
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
                ),
                const SizedBox(height: 20),

                // App name.
                const Text(
                  'X87 Player',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                    color: Colors.white,
                    letterSpacing: 0.5,
                  ),
                ),
                const SizedBox(height: 40),

                // Subtle loading indicator.
                const CircularProgressIndicator(color: _primaryColor),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
