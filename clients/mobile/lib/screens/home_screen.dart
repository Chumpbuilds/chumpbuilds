import 'package:flutter/material.dart';

import '../services/license_service.dart';
import '../services/xtream_service.dart';
import 'license_screen.dart';
import 'login_screen.dart';

/// Post-login home screen.
///
/// Shows account info from the authenticated Xtream Codes session and
/// provides options to switch profiles or deactivate the licence.
/// This is a placeholder for the actual IPTV content screens.
class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _descColor = Color(0xFFB0B0B0);

  // ─── Helpers ──────────────────────────────────────────────────────────────

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

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    final customizations = LicenseService().getAppCustomizations();
    final appName = customizations['app_name'] as String? ?? 'X87 Player';

    final xtream = XtreamService();
    final userInfo = xtream.userInfo ?? {};
    final xtreamUsername = userInfo['username'] as String? ?? xtream.username ?? '';
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
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Welcome header
              const Icon(
                Icons.play_circle_outline,
                size: 72,
                color: _primaryColor,
              ),
              const SizedBox(height: 16),
              const Text(
                'Welcome to X87 Player',
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

              // Switch Profile button
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

              // Deactivate License button
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
