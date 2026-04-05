import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../services/epg_service.dart';
import '../services/license_service.dart';
import '../services/xtream_cache_service.dart';
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
  int _total = 4;
  String _currentLabel = 'Preparing…';
  bool _done = false;

  @override
  void initState() {
    super.initState();
    _runPrefetch();
  }

  Future<void> _runPrefetch() async {
    final xtream = XtreamService();
    final cache = XtreamCacheService();

    if (!mounted) return;
    setState(() {
      _currentLabel = 'Loading content…';
      _completed = 0;
      _total = 4;
      _done = false;
    });

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
          debugPrint('[LoadingScreen] Live TV group error: $e');
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
          debugPrint('[LoadingScreen] Movies group error: $e');
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
          debugPrint('[LoadingScreen] Series group error: $e');
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
          debugPrint('[LoadingScreen] EPG group error: $e');
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
      _done = true;
    });

    // Small pause so the user sees "Done!" before navigating.
    if (mounted) {
      await Future<void>.delayed(const Duration(milliseconds: 300));
    }

    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => const HomeScreen()),
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

  @override
  Widget build(BuildContext context) {
    final progress = _total > 0 ? _completed / _total : 0.0;
    final customizations = LicenseService().getAppCustomizations();
    final logoUrl = customizations['logo_url'] as String? ?? '';
    final appName = customizations['app_name'] as String? ?? 'X87 Player';

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
                    // App icon / logo
                    if (logoUrl.isNotEmpty)
                      ClipRRect(
                        borderRadius: BorderRadius.circular(20),
                        child: CachedNetworkImage(
                          imageUrl: logoUrl,
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

                    // App name
                    Text(
                      appName,
                      style: const TextStyle(
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
    );
  }
}
