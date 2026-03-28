import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/license_service.dart';
import '../services/xtream_service.dart';
import '../widgets/tv_text_field.dart';
import '../widgets/system_ui_wrapper.dart';
import 'loading_screen.dart';

/// IPTV Login screen — mirrors the Windows client's `ModernLoginDialog`.
///
/// The server URL is never shown to the user; it comes from `cloud_profiles`
/// stored by [LicenseService].  The user picks a provider (if multiple
/// profiles exist) and enters their Xtream Codes username / password.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _hintColor = Color(0xFF95A5A6);
  static const Color _descColor = Color(0xFFB0B0B0);
  static const Color _errorBgColor = Color(0xFFDC3545);
  static const Color _infoBgColor = Color(0xFF17A2B8);

  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _dropdownFocusNode = FocusNode();
  bool _dropdownFocused = false;
  late void Function() _dropdownFocusListener;

  List<dynamic> _profiles = [];
  int _selectedIndex = 0;
  bool _isLoading = false;

  // Status message shown below the fields.
  String _statusMessage = '';
  bool _isError = false;

  @override
  void initState() {
    super.initState();
    _dropdownFocusListener = () {
      setState(() => _dropdownFocused = _dropdownFocusNode.hasFocus);
    };
    _dropdownFocusNode.addListener(_dropdownFocusListener);
    _profiles = LicenseService().getCloudProfiles();
    if (_profiles.isNotEmpty) {
      _selectedIndex = 0;
      _loadSavedCredentials(_profiles[0]['name'] as String? ?? '');
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    _dropdownFocusNode.removeListener(_dropdownFocusListener);
    _dropdownFocusNode.dispose();
    super.dispose();
  }

  // ─── Credential persistence ───────────────────────────────────────────────

  /// SharedPreferences key for a profile's saved credentials.
  /// Mirrors Windows `cloud_creds/{profile_name}` → `cloud_creds_{profile_name}`.
  String _credsKey(String profileName) => 'cloud_creds_$profileName';

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
    } catch (_) {}
  }

  Future<void> _saveCredentials(
      String profileName, String username, String password) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        _credsKey(profileName),
        jsonEncode({'username': username, 'password': password}),
      );
    } catch (e) {
      debugPrint('[Login] Error saving credentials: $e');
    }
  }

  // ─── Actions ──────────────────────────────────────────────────────────────

  void _onProfileChanged(int index) {
    setState(() {
      _selectedIndex = index;
      _statusMessage = '';
    });
    final name = _profiles[index]['name'] as String? ?? '';
    _loadSavedCredentials(name);
  }

  Future<void> _login() async {
    final profile = _profiles[_selectedIndex] as Map;
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
      await _saveCredentials(profileName, username, password);

      // Remember which profile was last used for auto-login.
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('last_used_profile', profileName);

      if (!mounted) return;
      _showStatus('Login successful!', isError: false);

      await Future<void>.delayed(const Duration(milliseconds: 400));
      if (!mounted) return;

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const LoadingScreen()),
      );
    } else {
      _showStatus(
          result['message'] as String? ?? 'Login failed.',
          isError: true);
    }
  }

  void _cancel() => SystemNavigator.pop();

  void _showStatus(String message, {required bool isError}) {
    setState(() {
      _statusMessage = message;
      _isError = isError;
    });
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return SystemUiWrapper(child: Scaffold(
      backgroundColor: _bgColor,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Title
                const Text(
                  '📺 IPTV Player Login',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w600,
                    color: Colors.white,
                  ),
                ),
                const SizedBox(height: 24),

                // Profile section
                if (_profiles.isEmpty) ...[
                  _buildNoProfilesSection(),
                ] else ...[
                  _buildProfileSection(),
                  const SizedBox(height: 16),
                  _buildUsernameField(),
                  const SizedBox(height: 12),
                  _buildPasswordField(),
                ],

                // Status / error area
                if (_statusMessage.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  _buildStatusBanner(),
                ],

                const SizedBox(height: 24),

                // Buttons
                Row(
                  children: [
                    Expanded(child: _buildCancelButton()),
                    const SizedBox(width: 12),
                    Expanded(
                      flex: 2,
                      child: _buildLoginButton(),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    ));
  }

  // ─── Widget builders ──────────────────────────────────────────────────────

  Widget _buildNoProfilesSection() {
    return Column(
      children: [
        const Text(
          'No DNS profiles have been configured.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 14, color: _descColor),
        ),
        const SizedBox(height: 8),
        const Text(
          'Please add DNS (Cloud) profiles in the customer portal to connect.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12, color: _hintColor),
        ),
        const SizedBox(height: 8),
        InkWell(
          onTap: () {
            // URL launching requires url_launcher package — show info instead.
            ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(
                content: Text(
                    'Visit https://portal.x87player.xyz to configure profiles'),
                duration: Duration(seconds: 4),
              ),
            );
          },
          child: const Text(
            'https://portal.x87player.xyz',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 13,
              color: _primaryColor,
              decoration: TextDecoration.underline,
              decorationColor: _primaryColor,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildProfileSection() {
    if (_profiles.length == 1) {
      // Single profile — show as a read-only label.
      final name = _profiles[0]['name'] as String? ?? '';
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Profile:',
              style: TextStyle(fontSize: 12, color: _descColor)),
          const SizedBox(height: 4),
          Container(
            width: double.infinity,
            padding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              color: _surfaceColor,
              border: Border.all(color: _borderColor),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Text(
              name,
              style: const TextStyle(color: Colors.white, fontSize: 13),
            ),
          ),
        ],
      );
    }

    // Multiple profiles — show a dropdown.
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Profile:',
            style: TextStyle(fontSize: 12, color: _descColor)),
        const SizedBox(height: 4),
        Container(
          decoration: BoxDecoration(
            color: _surfaceColor,
            border: Border.all(
              color: _dropdownFocused ? Colors.white : _borderColor,
              width: _dropdownFocused ? 3 : 1,
            ),
            borderRadius: BorderRadius.circular(4),
          ),
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: DropdownButtonHideUnderline(
            child: DropdownButton<int>(
              value: _selectedIndex,
              focusNode: _dropdownFocusNode,
              dropdownColor: _surfaceColor,
              isExpanded: true,
              style: const TextStyle(color: Colors.white, fontSize: 13),
              icon: const Icon(Icons.arrow_drop_down, color: _descColor),
              items: List.generate(_profiles.length, (i) {
                final name = _profiles[i]['name'] as String? ?? '';
                return DropdownMenuItem(value: i, child: Text(name));
              }),
              onChanged: _isLoading
                  ? null
                  : (value) {
                      if (value != null) _onProfileChanged(value);
                    },
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildUsernameField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Username:',
            style: TextStyle(fontSize: 12, color: _descColor)),
        const SizedBox(height: 4),
        TvTextField(
          controller: _usernameController,
          enabled: !_isLoading,
          style: const TextStyle(color: Colors.white, fontSize: 13),
          decoration: _inputDecoration('Enter your username'),
        ),
      ],
    );
  }

  Widget _buildPasswordField() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('Password:',
            style: TextStyle(fontSize: 12, color: _descColor)),
        const SizedBox(height: 4),
        TvTextField(
          controller: _passwordController,
          enabled: !_isLoading,
          obscureText: true,
          style: const TextStyle(color: Colors.white, fontSize: 13),
          decoration: _inputDecoration('Enter your password'),
          onSubmitted: _isLoading ? null : (_) => _login(),
        ),
      ],
    );
  }

  InputDecoration _inputDecoration(String hint) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: _hintColor),
      filled: true,
      fillColor: _surfaceColor,
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(4),
        borderSide: const BorderSide(color: _borderColor),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(4),
        borderSide: const BorderSide(color: Colors.white, width: 3),
      ),
      disabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(4),
        borderSide: const BorderSide(color: _borderColor),
      ),
    );
  }

  Widget _buildStatusBanner() {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: _isError ? _errorBgColor : _infoBgColor,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        children: [
          if (_isLoading && !_isError)
            const Padding(
              padding: EdgeInsets.only(right: 8),
              child: SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  color: Colors.white,
                ),
              ),
            ),
          Expanded(
            child: Text(
              _isError ? '⚠ $_statusMessage' : _statusMessage,
              style: const TextStyle(color: Colors.white, fontSize: 12),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoginButton() {
    return SizedBox(
      height: 44,
      child: ElevatedButton(
        onPressed: (_isLoading || _profiles.isEmpty) ? null : _login,
        style: ElevatedButton.styleFrom(
          backgroundColor: _primaryColor,
          disabledBackgroundColor: _primaryColor.withAlpha(100),
          foregroundColor: Colors.white,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(4),
          ),
        ).copyWith(
          side: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.focused)) {
              return const BorderSide(color: Colors.white, width: 3);
            }
            return BorderSide.none;
          }),
        ),
        child: _isLoading
            ? const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                    strokeWidth: 2, color: Colors.white),
              )
            : const Text(
                'Login',
                style:
                    TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
              ),
      ),
    );
  }

  Widget _buildCancelButton() {
    return SizedBox(
      height: 44,
      child: OutlinedButton(
        onPressed: _isLoading ? null : _cancel,
        style: OutlinedButton.styleFrom(
          foregroundColor: _descColor,
          side: const BorderSide(color: _borderColor),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(4),
          ),
        ).copyWith(
          side: WidgetStateProperty.resolveWith((states) {
            if (states.contains(WidgetState.focused)) {
              return const BorderSide(color: Colors.white, width: 3);
            }
            return const BorderSide(color: _borderColor);
          }),
        ),
        child: const Text('Cancel', style: TextStyle(fontSize: 14)),
      ),
    );
  }
}
