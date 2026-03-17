import 'package:flutter/material.dart';

import '../services/license_service.dart';

/// Post-activation placeholder home screen.
///
/// Displays the customised app name from license settings and confirms
/// that the license is active. The IPTV login screen will be added here
/// in the next iteration.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final customizations = LicenseService().getAppCustomizations();
    final appName = customizations['app_name'] as String? ?? 'X87 Player';

    return Scaffold(
      appBar: AppBar(
        title: Text(appName),
        centerTitle: true,
        backgroundColor: const Color(0xFF1E1E1E),
      ),
      backgroundColor: const Color(0xFF1E1E1E),
      body: const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.play_circle_outline,
              size: 96,
              color: Color(0xFF0D7377),
            ),
            SizedBox(height: 24),
            Text(
              'Welcome to X87 Player',
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            SizedBox(height: 12),
            Text(
              'License: Active ✅',
              style: TextStyle(
                fontSize: 16,
                color: Color(0xFF0D7377),
              ),
            ),
            SizedBox(height: 8),
            Text(
              'IPTV Login coming next',
              style: TextStyle(
                fontSize: 14,
                color: Color(0xFF95A5A6),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
