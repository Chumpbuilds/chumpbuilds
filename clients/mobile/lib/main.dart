import 'package:flutter/material.dart';

import 'screens/home_screen.dart';
import 'screens/license_screen.dart';
import 'services/license_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Silently validate any stored license before showing the first screen.
  final isValid = await LicenseService().validateLicense();
  runApp(X87App(startWithHome: isValid));
}

class X87App extends StatelessWidget {
  const X87App({super.key, required this.startWithHome});

  /// When `true` the app jumps straight to [HomeScreen]; otherwise it shows
  /// [LicenseScreen] so the user can enter their key.
  final bool startWithHome;

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
      home: startWithHome ? const HomeScreen() : const LicenseScreen(),
    );
  }
}

