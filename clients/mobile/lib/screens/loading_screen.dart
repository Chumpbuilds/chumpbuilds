import 'package:flutter/material.dart';

import '../services/xtream_service.dart';
import '../widgets/system_ui_wrapper.dart';
import 'home_screen.dart';

/// Full-screen loading/caching screen shown during startup prefetch.
///
/// Calls [XtreamService.prefetchAll] and shows progress, then navigates to
/// [HomeScreen] when complete (or if an error occurs — partial data is better
/// than blocking the user).
class LoadingScreen extends StatefulWidget {
  const LoadingScreen({super.key});

  @override
  State<LoadingScreen> createState() => _LoadingScreenState();
}

class _LoadingScreenState extends State<LoadingScreen> {
  static const Color _bgColor = Color(0xFF1E1E1E);
  static const Color _primaryColor = Color(0xFF0D7377);
  static const Color _surfaceColor = Color(0xFF2D2D2D);
  static const Color _descColor = Color(0xFFB0B0B0);

  int _completed = 0;
  int _total = 6;
  String _currentLabel = 'Preparing…';
  bool _done = false;

  @override
  void initState() {
    super.initState();
    _runPrefetch();
  }

  Future<void> _runPrefetch() async {
    try {
      await XtreamService().prefetchAll(
        onProgress: (completed, total, label) {
          if (!mounted) return;
          setState(() {
            _completed = completed;
            _total = total;
            _currentLabel = label == 'Complete' ? 'Done!' : 'Loading $label…';
            _done = label == 'Complete';
          });
        },
      );
    } catch (e) {
      debugPrint('[LoadingScreen] prefetchAll error: $e');
    }

    // Small pause so the user sees "Done!" before navigating.
    if (mounted) {
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }

    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const HomeScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final progress = _total > 0 ? _completed / _total : 0.0;

    return SystemUiWrapper(
      child: Scaffold(
        backgroundColor: _bgColor,
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 40),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // App icon / logo
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

                    // App name
                    const Text(
                      'X87 Player',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: Colors.white,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Loading your content…',
                      style: TextStyle(
                        fontSize: 13,
                        color: _descColor,
                      ),
                    ),
                    const SizedBox(height: 40),

                    // Progress bar
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        value: _done ? 1.0 : progress,
                        minHeight: 6,
                        backgroundColor: _surfaceColor,
                        valueColor: const AlwaysStoppedAnimation<Color>(
                          _primaryColor,
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Step label + counter row
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
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
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
