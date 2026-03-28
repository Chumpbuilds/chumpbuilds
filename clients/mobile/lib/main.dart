import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'screens/home_screen.dart';
import 'screens/license_screen.dart';
import 'screens/loading_screen.dart';
import 'screens/login_screen.dart';
import 'services/license_service.dart';
import 'services/xtream_cache_service.dart';
import 'services/xtream_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock the entire app to landscape.
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  // Hide system bars globally on startup.
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

  // 1. Silently validate any stored licence.
  final isValid = await LicenseService().validateLicense();

  Widget startScreen;
  if (isValid) {
    // 2. Licence is valid — attempt silent IPTV auto-login with saved creds.
    final autoLoggedIn = await _tryAutoLogin();
    if (autoLoggedIn) {
      // Check if the core content cache has at least 20 hours remaining.
      final cacheFresh = await XtreamCacheService().isCacheFresh(
        minRemainingHours: 20,
      );
      startScreen = cacheFresh ? const HomeScreen() : const LoadingScreen();
    } else {
      startScreen = const LoginScreen();
    }
  } else {
    // 3. No valid licence — show the activation screen.
    startScreen = const LicenseScreen();
  }

  runApp(X87App(home: startScreen));
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

class X87App extends StatelessWidget {
  const X87App({super.key, required this.home});

  final Widget home;

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
      home: home,
    );
  }
}
