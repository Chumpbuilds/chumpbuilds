import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../services/license_service.dart';
import '../widgets/tv_text_field.dart';
import '../widgets/system_ui_wrapper.dart';
import 'login_screen.dart';

/// License activation screen — mirrors the Windows client's LicenseDialog.
///
/// Dark background (#1e1e1e), teal primary (#0d7377), same UX flow.
class LicenseScreen extends StatefulWidget {
  const LicenseScreen({super.key});

  @override
  State<LicenseScreen> createState() => _LicenseScreenState();
}

class _LicenseScreenState extends State<LicenseScreen> {
  final _controller = TextEditingController();
  final _focusNode = FocusNode();
  bool _isLoading = false;
  String _hardwareIdDisplay = '';

  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _borderColor = Color(0xFF3D3D3D);
  static const Color _hintColor = Color(0xFF95A5A6);
  static const Color _descColor = Color(0xFFB0B0B0);

  @override
  void initState() {
    super.initState();
    _loadHardwareId();
  }

  Future<void> _loadHardwareId() async {
    final hwId = await LicenseService().hardwareId;
    if (mounted) {
      setState(() {
        _hardwareIdDisplay = '${hwId.substring(0, 16)}...';
      });
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  // ─── Actions ──────────────────────────────────────────────────────────────

  Future<void> _activate() async {
    final raw = _controller.text.trim().toUpperCase();
    final clean = raw.replaceAll('-', '');

    if (clean.length < 12) {
      _showErrorDialog(
          'Please enter a valid license key (e.g. X87-RR9X-A3GV-6UZR).');
      return;
    }

    setState(() => _isLoading = true);
    final result = await LicenseService().activateLicense(raw);
    if (!mounted) return;
    setState(() => _isLoading = false);

    if (result['success'] == true) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('License activated successfully!'),
          backgroundColor: _primaryColor,
        ),
      );
      Navigator.of(context).pushReplacement(
        MaterialPageRoute(builder: (_) => const LoginScreen()),
      );
    } else {
      _showErrorDialog(
          result['message'] as String? ?? 'License validation failed.');
    }
  }

  void _exitApp() {
    SystemNavigator.pop();
  }

  void _showErrorDialog(String message) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _surfaceColor,
        title: const Text(
          'License Error',
          style: TextStyle(color: Colors.white),
        ),
        content: Text(
          message,
          style: const TextStyle(color: _descColor),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(),
            child: const Text('OK', style: TextStyle(color: _primaryColor)),
          ),
        ],
      ),
    );
  }

  // ─── Build ────────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    return SystemUiWrapper(child: Scaffold(
      backgroundColor: _bgColor,
      resizeToAvoidBottomInset: false,
      body: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Title
                const Text(
                  '🔑 License Activation',
                  style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    color: _primaryColor,
                  ),
                ),
                const SizedBox(height: 16),

                // Description
                const Text(
                  'Please enter your license key to activate the IPTV Player:',
                  style: TextStyle(fontSize: 14, color: _descColor),
                ),
                const SizedBox(height: 20),

                // License key input
                TvTextField(
                  controller: _controller,
                  focusNode: _focusNode,
                  maxLength: 19,
                  textCapitalization: TextCapitalization.characters,
                  style: const TextStyle(color: Colors.white, fontSize: 14),
                  decoration: InputDecoration(
                    hintText: 'X87-XXXX-XXXX-XXXX',
                    hintStyle: const TextStyle(color: _hintColor),
                    counterStyle: const TextStyle(color: _hintColor),
                    filled: true,
                    fillColor: _surfaceColor,
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(4),
                      borderSide: const BorderSide(color: _borderColor),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(4),
                      borderSide:
                          const BorderSide(color: Colors.white, width: 3),
                    ),
                    contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 12),
                  ),
                ),
                // Paste button
                Row(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    TextButton.icon(
                      onPressed: () async {
                        try {
                          final data =
                              await Clipboard.getData(Clipboard.kTextPlain);
                          debugPrint('Clipboard data: ${data?.text}');
                          if (data?.text != null &&
                              data!.text!.trim().isNotEmpty) {
                            setState(() {
                              _controller.text = data.text!.trim();
                              _controller.selection = TextSelection.collapsed(
                                offset: _controller.text.length,
                              );
                            });
                          }
                        } catch (e) {
                          debugPrint('Paste error: $e');
                        }
                      },
                      icon: const Icon(Icons.content_paste, size: 14),
                      label:
                          const Text('Paste', style: TextStyle(fontSize: 12)),
                      style:
                          TextButton.styleFrom(foregroundColor: _descColor),
                    ),
                  ],
                ),

                // Format hint
                const Text(
                  'Enter key exactly as provided e.g. X87-RR9X-A3GV-6UZR',
                  style: TextStyle(fontSize: 11, color: _hintColor),
                ),
                const SizedBox(height: 8),

                // Hardware ID display
                Text(
                  'Hardware ID: $_hardwareIdDisplay',
                  style:
                      const TextStyle(fontSize: 11, color: _hintColor),
                ),
                const SizedBox(height: 32),

                // Activate button
                SizedBox(
                  height: 48,
                  child: ElevatedButton(
                    onPressed: _isLoading ? null : _activate,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _primaryColor,
                      disabledBackgroundColor: _primaryColor.withAlpha(128),
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
                            width: 22,
                            height: 22,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Text(
                            'Activate License',
                            style: TextStyle(
                                fontSize: 15, fontWeight: FontWeight.w600),
                          ),
                  ),
                ),
                const SizedBox(height: 12),

                // Exit button
                SizedBox(
                  height: 48,
                  child: OutlinedButton(
                    onPressed: _isLoading ? null : _exitApp,
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
                    child: const Text(
                      'Exit Application',
                      style: TextStyle(fontSize: 15),
                    ),
                  ),
                ),
              ],
            ),
          ),
      ),
    ));
  }
}
